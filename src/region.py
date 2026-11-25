"""区域联动：京津冀及周边城市的空气质量，用于判断响应会不会解除。

德州的应急响应不是本地单独决定的：公告原文写的是「京津冀及周边区域将出现一次中重度
污染过程…按照区域联防联控要求」。本地风速只回答「污染物能不能吹走」；区域里其他城市
（尤其北京、天津、石家庄）还没转好时，德州很少单独解除，反过来区域转好时解除会提前。

这里用城市级 WAQI 实况（与德州市区同口径）+ Open-Meteo 区域逐时 PM2.5 预报，
给出一个可解释的区域状态，以及它对预计解除时长的修正（天）。
"""
from __future__ import annotations

import statistics
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from .aqi import aqi_level
from .common import CST, env, get_with_retry, http_session, log, settings

# 与德州同处一个污染过程的代表城市，北京排第一：西北风来的时候它最先转好
CITIES = [
    {"key": "beijing", "name": "北京", "lat": 39.90, "lon": 116.41, "core": True},
    {"key": "tianjin", "name": "天津", "lat": 39.08, "lon": 117.20, "core": True},
    {"key": "langfang", "name": "廊坊", "lat": 39.54, "lon": 116.68, "core": True},
    {"key": "tangshan", "name": "唐山", "lat": 39.63, "lon": 118.18, "core": True},
    {"key": "baoding", "name": "保定", "lat": 38.87, "lon": 115.46, "core": True},
    {"key": "shijiazhuang", "name": "石家庄", "lat": 38.04, "lon": 114.51},
    {"key": "hengshui", "name": "衡水", "lat": 37.74, "lon": 115.67},
    {"key": "cangzhou", "name": "沧州", "lat": 38.30, "lon": 116.84},
    {"key": "xingtai", "name": "邢台", "lat": 37.07, "lon": 114.50},
    {"key": "handan", "name": "邯郸", "lat": 36.63, "lon": 114.54},
    {"key": "jinan", "name": "济南", "lat": 36.65, "lon": 117.12},
]

HOT = 150        # 中度污染起点：区域里还有城市到这个水平，说明污染过程没结束
CLEAN = 100      # 良的终点
TREND_STEP = 0.15  # 未来 24h 区域 PM2.5 中位变化超过 ±15% 才算转好/转差
AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
LEVEL_ADJUST = {"差": 1, "一般": 0, "好": -1}


def _fetch_city(cfg: dict, city: dict) -> dict | None:
    token = env("WAQI_TOKEN") or cfg["aqi"]["waqi_token"]
    try:
        session = http_session(cfg)
        r = get_with_retry(session, f"https://api.waqi.info/feed/{city['key']}/?token={token}",
                           timeout=25, tries=2)
        payload = r.json()
        if payload.get("status") != "ok":
            return None
        d = payload.get("data") or {}
        raw = d.get("aqi")
        if raw in (None, "-"):
            return None
        aqi = round(float(raw))
        return {
            **city,
            "aqi": aqi,
            "level": aqi_level(aqi),
            "time": (d.get("time") or {}).get("s"),
        }
    except Exception as exc:  # noqa: BLE001 - 单个城市失败不影响整体
        log(f"区域城市 {city['name']} 空气质量获取失败: {type(exc).__name__}: {exc}")
        return None


def _fetch_forecast(cfg: dict) -> dict:
    """一次请求取全部城市未来 24h 的 PM2.5，用于判断区域是在转好还是转差。"""
    lat = ",".join(str(c["lat"]) for c in CITIES)
    lon = ",".join(str(c["lon"]) for c in CITIES)
    try:
        session = http_session(cfg)
        r = get_with_retry(session, AQ_URL, timeout=60, params={
            "latitude": lat, "longitude": lon,
            "hourly": "pm2_5",
            "past_days": 1, "forecast_days": 2,
            "timezone": "Asia/Shanghai",
        })
        data = r.json()
    except Exception as exc:  # noqa: BLE001 - 预报失败只影响趋势描述
        log(f"区域预报获取失败: {type(exc).__name__}: {exc}")
        return {}
    if isinstance(data, dict):
        data = [data]

    now = datetime.now(CST)
    out: dict = {}
    for city, point in zip(CITIES, data):
        hourly = (point or {}).get("hourly") or {}
        times = hourly.get("time") or []
        values = hourly.get("pm2_5") or []
        past, ahead = [], []
        for t, v in zip(times, values):
            if v is None:
                continue
            try:
                ts = datetime.fromisoformat(t).replace(tzinfo=CST)
            except ValueError:
                continue
            (past if ts <= now else ahead).append(float(v))
        if not past and not ahead:
            continue
        out[city["key"]] = {
            "pm25_now": round(statistics.fmean(past[-24:]), 1) if past else None,
            "pm25_24h": round(statistics.fmean(ahead[:24]), 1) if ahead else None,
        }
    return out


def _level(median_aqi: float, hot_count: int, city_count: int,
           delta: float | None, beijing_aqi: int | None) -> tuple[str, str]:
    """区域状态与 24h 趋势方向；阈值全部写在这里，便于复核。"""
    if delta is None:
        direction = "flat"
    elif delta <= -TREND_STEP:
        direction = "improving"
    elif delta >= TREND_STEP:
        direction = "worsening"
    else:
        direction = "flat"

    if median_aqi >= HOT or hot_count >= max(2, city_count // 2):
        return "差", direction
    if delta is not None and delta >= TREND_STEP and median_aqi >= CLEAN:
        return "差", direction
    # 北京是区域风向标：它还没到「良」就不算区域转好
    if (median_aqi < CLEAN and hot_count <= 1 and direction != "worsening"
            and (beijing_aqi is None or beijing_aqi < CLEAN)):
        return "好", direction
    return "一般", direction


def summarize(cfg: dict | None = None) -> dict:
    """区域联动摘要：城市实况 + 24h 趋势 + 对预计解除时长的修正。"""
    cfg = cfg or settings()
    if not (cfg.get("region") or {}).get("enabled", True):
        return {"available": False, "reason": "区域联动已在配置中关闭"}

    with ThreadPoolExecutor(max_workers=6) as pool:
        cities = [c for c in pool.map(lambda c: _fetch_city(cfg, c), CITIES) if c]
    if len(cities) < 3:
        log("区域城市空气质量样本不足，跳过区域联动")
        return {"available": False, "reason": "区域城市空气质量样本不足"}

    forecast = _fetch_forecast(cfg)
    for c in cities:
        f = forecast.get(c["key"]) or {}
        c["pm25_now"] = f.get("pm25_now")
        c["pm25_24h"] = f.get("pm25_24h")

    values = [c["aqi"] for c in cities]
    median_aqi = statistics.median(values)
    hot = [c for c in cities if c["aqi"] >= HOT]
    beijing = next((c for c in cities if c["key"] == "beijing"), None)

    changes = [(c["pm25_24h"] - c["pm25_now"]) / c["pm25_now"]
               for c in cities
               if c.get("pm25_now") and c.get("pm25_24h") is not None and c["pm25_now"] > 0]
    delta = statistics.median(changes) if changes else None
    level, direction = _level(median_aqi, len(hot), len(cities), delta,
                             beijing["aqi"] if beijing else None)

    forecast_values = [c["pm25_24h"] for c in cities if c.get("pm25_24h") is not None]
    log(f"区域联动: {len(cities)} 城，中位 AQI {median_aqi:g}，{len(hot)} 城达中度污染以上，"
        f"北京 {beijing['aqi'] if beijing else '—'}，状态 {level}")

    return {
        "available": True,
        "level": level,
        "adjust": LEVEL_ADJUST[level],
        "median_aqi": median_aqi,
        "max_aqi": max(values),
        "hot_count": len(hot),
        "city_count": len(cities),
        "beijing": ({"aqi": beijing["aqi"], "level": beijing["level"]} if beijing else None),
        "trend": {
            "direction": direction,
            "delta_pct": round(delta * 100, 1) if delta is not None else None,
            "pm25_24h": (round(statistics.fmean(forecast_values), 1) if forecast_values else None),
        },
        "cities": cities,
        "note": (f"区域 {len(cities)} 城中位 AQI {median_aqi:g}，{len(hot)} 城达中度污染以上"
                 f"（北京 {beijing['aqi'] if beijing else '—'}）"),
        "source": "WAQI 城市实况 + Open-Meteo 区域 PM2.5 预报",
        "generated_at": datetime.now(CST).isoformat(timespec="seconds"),
    }
