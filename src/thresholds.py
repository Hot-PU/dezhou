"""预警阈值：用历史空气质量 + 历次发文日期，反推「多少个观测点超标会触发文件」。

做法（全部可复现）：
1. 取德州市域 3×3 九个网格点的历史逐时 AQI（Open-Meteo 再分析/预报模型，非国控站原始值）；
2. 汇总为日值：某日某点日均 AQI ≥ hot_theta 记为「该点暴雷」；
3. 把栏目历次「启动」公告的发布日当作正样本（发文当天或前一日）；
4. 对「暴雷点数 0..9」逐个做判别，取 F1 最高者为阈值，并给出召回/精确率与公告日分布；
5. 同样的方法给出「全市 3 日滑动均值 AQI」阈值作为交叉验证。
"""
from __future__ import annotations

import os
import statistics
from datetime import date, datetime, timedelta

from .common import ROOT, CST, get_with_retry, http_session, log, read_json, settings, write_json

CACHE = ROOT / "data" / "air_history.json"
AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

# 德州市域 3×3 网格（覆盖德城、陵城、平原、临邑、武城、夏津等方向）
GRID_LAT = (36.95, 37.35, 37.75)
GRID_LON = (116.00, 116.40, 116.80)
HOT_THETA = 150      # 单点日均 AQI ≥150（中度污染）记为暴雷
CACHE_DAYS = 7       # 历史缓存有效期，超过则重新拉取
HISTORY_START = "2022-08-01"


def _grid() -> tuple[list[str], list[str]]:
    return ([str(x) for y in GRID_LAT for x in GRID_LON],
            [str(x) for y in GRID_LAT for x in GRID_LON])


def _fetch_history(cfg: dict, start: str, end: str) -> dict | None:
    lat = ",".join(str(v) for v in GRID_LAT for _ in GRID_LON)
    lon = ",".join(str(v) for _ in GRID_LAT for v in GRID_LON)
    try:
        session = http_session(cfg)
        r = get_with_retry(session, AQ_URL, timeout=180, params={
            "latitude": lat, "longitude": lon,
            "hourly": "us_aqi,pm2_5",
            "start_date": start, "end_date": end,
            "timezone": "Asia/Shanghai",
        })
        data = r.json()
    except Exception as exc:  # noqa: BLE001
        log(f"历史空气质量获取失败: {type(exc).__name__}: {exc}")
        return None
    if not isinstance(data, list):
        data = [data]

    points = []
    for p in data:
        h = p.get("hourly") or {}
        times = h.get("time") or []
        aqi = h.get("us_aqi") or []
        pm25 = h.get("pm2_5") or []
        daily: dict[str, list[float]] = {}
        for i, t in enumerate(times):
            if i >= len(aqi) or aqi[i] is None:
                continue
            day = str(t)[:10]
            daily.setdefault(day, []).append(float(aqi[i]))
        points.append({
            "lat": p.get("latitude"), "lon": p.get("longitude"),
            "daily": {d: round(statistics.fmean(v), 1) for d, v in daily.items() if v},
        })

    return {
        "fetched_at": datetime.now(CST).isoformat(timespec="seconds"),
        "start": start, "end": end,
        "hot_theta": HOT_THETA,
        "points": points,
    }


def load_history(cfg: dict | None = None, force: bool = False) -> dict | None:
    cfg = cfg or settings()
    cached = read_json(CACHE, None)
    today = datetime.now(CST).date()
    if (not force and cached and cached.get("points")
            and len(cached["points"]) == len(GRID_LAT) * len(GRID_LON)):
        try:
            fetched = datetime.fromisoformat(cached["fetched_at"]).date()
            if (today - fetched).days <= CACHE_DAYS:
                # 缓存末尾若不是昨天，也重新拉（保持最新）
                last_day = max(max(p["daily"]) for p in cached["points"] if p["daily"])
                if last_day >= (today - timedelta(days=1)).isoformat():
                    return cached
        except (ValueError, TypeError):
            pass

    log("拉取德州市域 9 个网格点的历史空气质量（约 4 年）")
    data = _fetch_history(cfg, HISTORY_START, today.isoformat())
    if data:
        write_json(CACHE, data)
        log(f"历史空气质量已缓存: {len(data['points'])} 个点，{data['start']} → {data['end']}")
    return data or cached


def _notices(items: list[dict], level: str | None = None) -> list[dict]:
    out = []
    for it in items:
        title = it.get("title", "")
        if "启动" not in title and "升级" not in title:
            continue
        if level and f"{level}级" not in title:
            continue
        try:
            d = date.fromisoformat(it["publish_date"])
        except (KeyError, ValueError):
            continue
        out.append({"date": d, "title": title, "url": it.get("url")})
    return out


def _series(data: dict) -> tuple[list[str], dict[str, float], dict[str, int]]:
    """返回 (日期序列, 城市日均 AQI, 每日暴雷点数)。"""
    per_point = [p["daily"] for p in data["points"]]
    days = sorted({d for daily in per_point for d in daily})
    city: dict[str, float] = {}
    hot: dict[str, int] = {}
    for d in days:
        vals = [daily[d] for daily in per_point if d in daily]
        if not vals:
            continue
        city[d] = round(statistics.fmean(vals), 1)
        hot[d] = sum(1 for v in vals if v >= data.get("hot_theta", HOT_THETA))
    return days, city, hot


def _trailing_mean(series: dict[str, float], day: str, window: int = 3) -> float | None:
    d0 = date.fromisoformat(day)
    vals = [series.get((d0 - timedelta(days=i)).isoformat()) for i in range(window)]
    vals = [v for v in vals if v is not None]
    return round(statistics.fmean(vals), 1) if vals else None


def _sweep(values: dict[str, int | float], positives: set[str], candidates: list) -> dict | None:
    """在候选阈值上找 F1 最高的判别点。"""
    best = None
    for t in candidates:
        tp = fp = fn = 0
        for day, v in values.items():
            if v is None:
                continue
            pred = v >= t
            actual = day in positives
            if pred and actual:
                tp += 1
            elif pred and not actual:
                fp += 1
            elif actual and not pred:
                fn += 1
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        cand = {"threshold": t, "precision": round(precision, 2),
                "recall": round(recall, 2), "f1": round(f1, 2),
                "tp": tp, "fp": fp, "fn": fn}
        if best is None or cand["f1"] > best["f1"]:
            best = cand
    return best


def analyze(items: list[dict], air: dict, cfg: dict | None = None,
            force_refresh: bool = False) -> dict:
    """输出阈值结论：暴雷点数阈值 + 城市 AQI 交叉验证 + 当前状态。"""
    cfg = cfg or settings()
    data = load_history(cfg, force=force_refresh)
    if not data or not data.get("points"):
        return {"available": False, "reason": "历史空气质量不可用"}

    days, city, hot = _series(data)
    if not days:
        return {"available": False, "reason": "历史空气质量为空"}

    # 正样本：Ⅱ级（橙色）启动公告；样本不足时退回全部启动公告
    positives_2 = {n["date"].isoformat() for n in _notices(items, "Ⅱ")}
    positives_all = {n["date"].isoformat() for n in _notices(items)}
    scope = "Ⅱ级"
    positives = {d for d in positives_2 if d in hot} | {
        (date.fromisoformat(d) + timedelta(days=1)).isoformat() for d in positives_2
        if (date.fromisoformat(d) + timedelta(days=1)).isoformat() in hot}
    if len(positives) < 5:
        scope = "全部"
        positives = {d for d in positives_all if d in hot}

    if not positives:
        return {"available": False, "reason": "公告与历史数据没有重叠区间"}

    city3 = {d: _trailing_mean(city, d) for d in days}
    hot_threshold = _sweep(hot, positives, list(range(0, len(data["points"]) + 1)))
    city_threshold = _sweep(city3, positives, list(range(100, 260, 5)))

    pos_hot = [hot[d] for d in positives if d in hot]
    pos_city = [city3[d] for d in positives if city3.get(d) is not None]

    # 今日及未来 48h 的预报峰值（单点，用主数据）
    now = datetime.now(CST)
    forecast_peak = None
    for h in (air.get("hourly") or []):
        try:
            ts = datetime.fromisoformat(h.get("t", "")).replace(tzinfo=CST)
        except ValueError:
            continue
        if ts >= now and h.get("aqi") is not None:
            forecast_peak = max(forecast_peak or 0, float(h["aqi"]))
    forecast_peak = round(forecast_peak, 0) if forecast_peak is not None else None

    # 当前状态：今日各点 AQI（用最近一个历史日 + 主数据里的今日 AQI 近似今日城市值）
    today = datetime.now(CST).date()
    today_key = today.isoformat()
    current_hot = hot.get(today_key)
    current_city3 = city3.get(today_key)
    if current_city3 is None:
        # 历史缓存到昨天时，用 WAQI 今日 AQI 补最后一个点
        waqi = (air.get("current") or {}).get("aqi")
        prev = [city.get((today - timedelta(days=i)).isoformat()) for i in (1, 2)]
        vals = [v for v in prev if v is not None] + ([float(waqi)] if waqi else [])
        current_city3 = round(statistics.fmean(vals), 1) if vals else None
    if current_hot is None:
        current_hot = hot.get(max(days)) if days else None

    t_hot = hot_threshold["threshold"] if hot_threshold else None
    t_city = city_threshold["threshold"] if city_threshold else None

    def _status(current, threshold):
        if current is None or threshold is None:
            return "unknown"
        if current >= threshold:
            return "trigger"
        if current >= threshold * 0.75:
            return "watch"
        return "safe"

    # 临近警戒：当前值达到警戒线 75%，或未来 48h 预报峰值达到单点暴雷线
    status = _status(current_hot, t_hot)
    if status == "safe" and forecast_peak is not None and forecast_peak >= HOT_THETA:
        status = "watch"

    stations = air.get("stations") or []
    exceed = sum(1 for s in stations if (s.get("aqi") or 0) >= HOT_THETA)
    exceed100 = sum(1 for s in stations if (s.get("aqi") or 0) >= 100)

    return {
        "available": True,
        "scope": scope,
        "window": {"start": data["start"], "end": data["end"], "days": len(days)},
        "grid_points": len(data["points"]),
        "hot_theta": data.get("hot_theta", HOT_THETA),
        "hot_count": {
            **(hot_threshold or {}),
            "max": len(data["points"]),
            "typical": statistics.median(pos_hot) if pos_hot else None,
            "distribution": {
                "p25": sorted(pos_hot)[len(pos_hot) // 4] if pos_hot else None,
                "p50": statistics.median(pos_hot) if pos_hot else None,
                "p75": sorted(pos_hot)[(len(pos_hot) * 3) // 4] if pos_hot else None,
            },
        },
        "city_aqi": {
            **(city_threshold or {}),
            "typical": statistics.median(pos_city) if pos_city else None,
            "distribution": {
                "p25": sorted(pos_city)[len(pos_city) // 4] if pos_city else None,
                "p50": statistics.median(pos_city) if pos_city else None,
                "p75": sorted(pos_city)[(len(pos_city) * 3) // 4] if pos_city else None,
            },
        },
        "current": {
            "hot_count": current_hot,
            "city_aqi_3d": current_city3,
            "forecast_peak": forecast_peak,
            "status": status,
            "city_status": _status(current_city3, t_city),
        },
        "stations": {
            "total": len(stations),
            "exceed_hot": exceed,
            "exceed_100": exceed100,
            "share": round(exceed / len(stations) * 100, 1) if stations else None,
        },
        "samples": {"positive_days": len(positives), "history_days": len(days)},
        "generated_at": datetime.now(CST).isoformat(timespec="seconds"),
    }
