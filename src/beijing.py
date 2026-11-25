"""北京官方「预警信息」动态：把北京每一次空气重污染预警当作独立信息源，
并与德州本次应急响应做时间重叠比对。

德州的响应是按「京津冀及周边区域联防联控」启动/解除的。此前只能靠空气质量
（WAQI / Open-Meteo）推测区域是否转好；北京这个栏目把每一次空气重污染预警的
发布/启动/解除都挂在同一个列表里，且标题写明了实际生效时刻，口径比 AQI 更权威：

- 北京已解除、德州仍在响应 → 区域联防联控的窗口已经打开，德州解除临近；
- 北京仍在响应 → 德州很少单独解除，预计解除大概率延后。

栏目页末尾有一个隐藏的 ``<abbr id="json">``，内含整栏（2000+ 条）的 JSON 数组，
比正则爬列表稳定，这里直接用它；解析失败只记日志，不影响主流程。
"""
from __future__ import annotations

import html as html_lib
import json
import re
import statistics
from datetime import datetime, timedelta
from urllib.parse import quote

from .common import (CST, env, get_with_retry, http_session, log, now_cst)
from .history import episodes as dz_episodes

COLUMN_URL = "https://yjglj.beijing.gov.cn/col/col2472/index.html"
COLUMN_NAME = "北京市应急管理局 · 预警信息"
POLLUTION = "空气重污染"
# 北京解除后 N 天内，才算「德州即将跟随解除」的有效信号；更久说明两地已脱钩
LIFT_FRESH_DAYS = 3
# 两地启动日相差 ≤N 天，才认为是同一轮区域污染过程
PAIR_WINDOW_DAYS = 3

JSON_RE = re.compile(r'<abbr[^>]*id="json"[^>]*>(?P<json>.*?)</abbr>', re.S | re.I)
TITLE_TIME_RE = re.compile(
    r"(?P<y>\d{4})\s*年\s*(?P<m>\d{1,2})\s*月\s*(?P<d>\d{1,2})\s*日"
    r"(?:\s*(?P<H>\d{1,2})\s*[时點]\s*(?:(?P<M>\d{1,2})\s*分)?)?"
)
COLOR_RANK = {"蓝色预警": 1, "黄色预警": 2, "橙色预警": 3, "红色预警": 4}

SIGNAL_ZH = {
    "beijing_lifted": "已解除、德州滞后",
    "beijing_in_force": "仍在响应",
    "both_closed": "两地均已解除",
    "dezhou_closed": "德州已终止",
    "none": "",
}


def _parse_iso(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=CST)


def _title_time(title: str) -> datetime | None:
    """从标题里取实际生效/解除时刻（栏目 time 只是发布日期，差一天很常见）。"""
    m = TITLE_TIME_RE.search(title or "")
    if not m:
        return None
    try:
        day = datetime(int(m["y"]), int(m["m"]), int(m["d"]), tzinfo=CST)
        hour = int(m["H"]) if m["H"] else 0
        minute = int(m["M"]) if m["M"] else 0
    except ValueError:
        return None
    # 公文里的「24 时」= 次日 0 时
    return day + timedelta(hours=hour, minutes=minute)


def _kind(title: str) -> str:
    if "解除" in title or "终止" in title:
        return "terminate"
    if "启动" in title or "发布" in title:
        return "startup"
    if "升级" in title:
        return "upgrade"
    return "other"


def _color(title: str) -> str:
    m = re.search(r"(红色|橙色|黄色|蓝色)\s*预警", title or "")
    return f"{m.group(1)}预警" if m else ""


def _fetch_html(cfg: dict) -> str:
    bj = cfg.get("beijing") or {}
    relay = env("BEIJING_RELAY") or bj.get("relay")
    proxy = env("BEIJING_PROXY") or bj.get("proxy")
    session = http_session(cfg, proxy=proxy)
    # 该站直连即可（不像德州源站在境外只走 IPv6），UA 用较新的 Edge/Chrome
    session.headers.update({
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36 Edg/157.0.0.0"),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": COLUMN_URL,
        "DNT": "1",
    })
    url = COLUMN_URL
    if relay:
        sep = "&" if "?" in relay else "?"
        url = f"{relay}{sep}url={quote(COLUMN_URL, safe='')}"
    resp = get_with_retry(session, url, timeout=bj.get("timeout", 45), tries=2)
    return resp.text


def _load_items(html: str) -> list[dict]:
    m = JSON_RE.search(html)
    if not m:
        raise ValueError("栏目页里没有找到 <abbr id=\"json\"> 数据块")
    raw = m.group("json").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = json.loads(html_lib.unescape(raw))
    if not isinstance(data, list):
        raise ValueError("abbr 里的 JSON 不是数组")
    return data


def parse_items(data: list[dict]) -> list[dict]:
    """只留下与空气重污染相关的发布/启动/解除条目，时间取标题里的实际时刻。"""
    out: list[dict] = []
    for raw in data:
        if not isinstance(raw, dict):
            continue
        title = re.sub(r"\s+", " ", (raw.get("title") or "").replace("\u3000", " ")).strip()
        # 源站 JSON 里偶有夹在汉字中间的空格（「橙色预 警」），呈现前清掉
        title = re.sub(r"(?<=[\u4e00-\u9fa5])\s+(?=[\u4e00-\u9fa5])", "", title)
        if POLLUTION not in title:
            continue
        kind = _kind(title)
        if kind == "other":
            continue
        published = _parse_iso((raw.get("time") or "")[:10])
        effective = _title_time(title) or published
        if not effective:
            continue
        out.append({
            "title": title,
            "url": raw.get("url") or "",
            "published_date": published.strftime("%Y-%m-%d") if published else None,
            "effective": effective.isoformat(timespec="minutes"),
            "kind": kind,
            "color": _color(title),
        })
    out.sort(key=lambda i: (i["effective"], i["url"]))
    return out


def episodes(items: list[dict]) -> list[dict]:
    """把北京的公告还原成「一次预警 = 启动 → 解除」。"""
    out: list[dict] = []
    open_ep: dict | None = None
    for item in items:
        kind = item["kind"]
        if kind in ("startup", "upgrade"):
            if open_ep and item["effective"][:10] == open_ep["started_at"][:10]:
                # 同日升级（黄色 → 橙色），不新开一段，只提级
                if COLOR_RANK.get(item["color"], 0) > COLOR_RANK.get(open_ep.get("color"), 0):
                    open_ep["color"] = item["color"]
                continue
            if open_ep:
                open_ep["incomplete"] = True
                out.append(open_ep)
            open_ep = {
                "started_at": item["effective"],
                "ended_at": None,
                "color": item["color"],
                "start_title": item["title"],
                "start_url": item["url"],
                "incomplete": False,
            }
        elif kind == "terminate" and open_ep:
            open_ep["ended_at"] = item["effective"]
            open_ep["end_title"] = item["title"]
            open_ep["end_url"] = item["url"]
            open_ep["incomplete"] = False
            start, end = _parse_iso(open_ep["started_at"]), _parse_iso(open_ep["ended_at"])
            if start and end:
                open_ep["days"] = max(1, round((end - start).total_seconds() / 86400))
            out.append(open_ep)
            open_ep = None
    if open_ep:
        open_ep["ongoing"] = True
        out.append(open_ep)
    return out


def attach_history(status: dict, dz_items: list[dict]) -> dict:
    """把北京历次预警与德州历次「启动→终止」配对，统计两地的起止滞后关系。

    配对规则：两地启动日相差 ≤ PAIR_WINDOW_DAYS 天（同一轮区域污染过程），
    取时间上最近的北京预警；终结滞后 = 德州终止日 − 北京解除日（天）。
    这是「北京已解除 → 德州何时解除」最直接的历史依据。
    """
    if not status or not status.get("available"):
        return status
    bj_eps = status.get("episodes") or []
    try:
        dz_eps = [e for e in dz_episodes(dz_items or [])
                  if e.get("start") and not e.get("incomplete")]
    except Exception as exc:  # noqa: BLE001 - 配对失败不影响北京状态展示
        log(f"北京↔德州历史配对失败: {type(exc).__name__}: {exc}")
        return status
    if not bj_eps or not dz_eps:
        return status

    pairs = []
    for dz in dz_eps:
        dz_start = dz["start"]
        best = None
        for ep in bj_eps:
            bj_start = _parse_iso(ep.get("started_at"))
            if not bj_start:
                continue
            lag = (dz_start.date() - bj_start.date()).days
            if abs(lag) > PAIR_WINDOW_DAYS:
                continue
            if best is None or abs(lag) < abs(best["start_lag"]):
                best = {**ep, "start_lag": lag}
        if not best:
            continue
        bj_end = _parse_iso(best.get("ended_at"))
        dz_end = dz.get("end")
        pairs.append({
            "bj_start": best["started_at"][:10],
            "bj_end": bj_end.strftime("%Y-%m-%d") if bj_end else None,
            "dz_start": dz_start.strftime("%Y-%m-%d"),
            "dz_end": dz_end.strftime("%Y-%m-%d") if dz_end else None,
            "start_lag": best["start_lag"],
            "end_lag": (dz_end.date() - bj_end.date()).days if (dz_end and bj_end) else None,
            "color": best.get("color"),
            "ongoing": bool(dz.get("ongoing")),
        })

    def _stat(values: list) -> dict | None:
        vals = [v for v in values if v is not None]
        if not vals:
            return None
        return {
            "n": len(vals),
            "median": statistics.median(vals),
            "mean": round(statistics.fmean(vals), 1),
            "min": min(vals),
            "max": max(vals),
        }

    start_stat = _stat([p["start_lag"] for p in pairs])
    end_stat = _stat([p["end_lag"] for p in pairs])
    bj_days_stat = _stat([e.get("days") for e in bj_eps])
    status["history"] = {
        "available": bool(pairs),
        "pairs": pairs[-8:],
        "pair_count": len(pairs),
        "start_lag": start_stat,
        "end_lag": end_stat,
        "beijing_days": bj_days_stat,
        "window_days": PAIR_WINDOW_DAYS,
        "note": (f"共 {len(pairs)} 次与德州启动日相差 ≤{PAIR_WINDOW_DAYS} 天的可比过程"
                 f"（两端齐全 {end_stat['n'] if end_stat else 0} 次）"),
        "generated_at": now_cst().isoformat(timespec="seconds"),
    }
    if end_stat:
        log(f"北京↔德州历史关系: {status['history']['note']}，德州通常在京解除后 "
            f"{end_stat['median']:g} 天解除")
    return status


def summarize(cfg: dict | None = None) -> dict:
    """抓北京栏目 → 最近一次空气重污染预警的官方状态 + 最近几条动态。"""
    from .common import settings  # 延迟导入，保持模块可直接单测
    cfg = cfg or settings()
    bj = cfg.get("beijing") or {}
    if not bj.get("enabled", True):
        return {"available": False, "reason": "北京官方联动已在配置中关闭"}
    try:
        data = _load_items(_fetch_html(cfg))
    except Exception as exc:  # noqa: BLE001 - 北京站失败不影响德州主流程
        log(f"北京预警信息获取失败: {type(exc).__name__}: {exc}")
        return {"available": False, "reason": f"北京预警信息获取失败：{type(exc).__name__}"}

    items = parse_items(data)
    eps = episodes(items)
    if not eps:
        return {
            "available": True,
            "state": "none",
            "items": items[-8:][::-1],
            "episodes": [],
            "source": COLUMN_NAME,
            "url": COLUMN_URL,
            "generated_at": now_cst().isoformat(timespec="seconds"),
        }

    now = now_cst()
    last = eps[-1]
    started = _parse_iso(last["started_at"])
    ended = _parse_iso(last.get("ended_at"))
    status = {
        "available": True,
        "state": "lifted" if ended else "in_force",
        "level": last.get("color") or "",
        "started_at": last["started_at"],
        "ended_at": last.get("ended_at"),
        "days": last.get("days"),
        "elapsed_days": (int((now - (ended or started)).total_seconds() // 86400)
                         if (ended or started) else None),
        "latest": items[-1] if items else None,
        "episodes": [
            {
                "started_at": e["started_at"],
                "ended_at": e.get("ended_at"),
                "days": e.get("days"),
                "color": e.get("color"),
                "incomplete": e.get("incomplete", False),
            }
            for e in eps
        ],
        "items": [
            {**i, "effective_date": i["effective"][:10]} for i in items[-8:][::-1]
        ],
        "total": len(items),
        "source": COLUMN_NAME,
        "url": COLUMN_URL,
        "generated_at": now.isoformat(timespec="seconds"),
    }
    log(f"北京官方联动: 最近一次 {status['level'] or '空气重污染'} "
        f"{'已解除' if ended else '响应中'}（{last['started_at'][:10]} → "
        f"{(last.get('ended_at') or '至今')[:10]}）")
    return status


def _dezhou_window(notice: dict) -> tuple[datetime | None, datetime | None, str]:
    start = _parse_iso(notice.get("effective_time")) or _parse_iso(notice.get("publish_date"))
    if notice.get("kind") == "terminate":
        end = _parse_iso(notice.get("effective_time")) or _parse_iso(notice.get("publish_date"))
        return start, end, "terminated"
    return start, None, "in_force"


def _estimate(hist: dict, dz_start: datetime | None, bj_start: datetime | None,
              bj_end: datetime | None, now: datetime) -> dict | None:
    """「北京解除（或预计解除）+ 德州历史滞后」→ 德州预计解除日期。"""
    if not dz_start or not (hist or {}).get("available"):
        return None
    end_stat = hist.get("end_lag") or {}
    lag = end_stat.get("median")
    if lag is None:
        return None
    if bj_end:
        anchor, kind = bj_end, "beijing_lifted"
    elif bj_start:
        median_days = (hist.get("beijing_days") or {}).get("median")
        if median_days is None:
            return None
        # 北京已超过历史中位还没解除：按「随时可能」处理，锚点取今天
        anchor = max(bj_start + timedelta(days=median_days), now)
        kind = "beijing_projected"
    else:
        return None
    est = anchor + timedelta(days=lag)
    note = (f"北京{'已解除' if bj_end else '预计'} {anchor.strftime('%m-%d')}"
            f" + 历史中位滞后 {lag:g} 天（{end_stat.get('n')} 次）")
    return {
        "predicted_end": est.isoformat(timespec="minutes"),
        "anchor_at": anchor.isoformat(timespec="minutes"),
        "anchor_kind": kind,
        "median_end_lag_days": lag,
        "sample_size": end_stat.get("n"),
        "lag_range": [end_stat.get("min"), end_stat.get("max")],
        "beijing_days_median": (hist.get("beijing_days") or {}).get("median"),
        "overdue": est <= now,
        "note": note,
    }


def link(beijing: dict, notice: dict) -> dict:
    """把北京官方状态与德州本次响应做时间重叠比对（纯函数，巡检可反复调用）。"""
    if not beijing or not beijing.get("available"):
        return beijing or {}
    now = now_cst()
    started, ended, dz_state = _dezhou_window(notice or {})
    stop = ended or now

    matched = None
    # 被下一次启动打断的旧预警（incomplete）结束时刻未知，不能当作「仍在响应」
    usable = [ep for ep in (beijing.get("episodes") or []) if not ep.get("incomplete")]
    if dz_state == "terminated":
        # 终止公告的 effective_time 是解除时刻，本轮起点未知：取「终止前已启动」的最近一段
        for ep in usable:
            s = _parse_iso(ep.get("started_at"))
            if s and ended and s <= ended:
                matched = ep
    else:
        for ep in usable:
            s, e = _parse_iso(ep.get("started_at")), _parse_iso(ep.get("ended_at"))
            if s and started and s <= stop and (e or now) >= started:
                matched = ep  # 取最后一个与德州窗口相交的北京预警
    overlapped = matched is not None
    if matched is None and usable:
        matched = usable[-1]

    bj_start = _parse_iso((matched or {}).get("started_at"))
    bj_end = _parse_iso((matched or {}).get("ended_at"))
    signal = "none"
    if overlapped and dz_state == "in_force" and bj_end:
        signal = "beijing_lifted"
    elif overlapped and dz_state == "in_force" and bj_start and not bj_end:
        signal = "beijing_in_force"
    elif overlapped and dz_state == "terminated":
        signal = "both_closed" if bj_end else "dezhou_closed"

    lifted_days = (now.date() - bj_end.date()).days if bj_end else None
    # 北京解除超过 N 天德州还没动：两地已脱钩，关系信号不算「临近」
    stale = bool(signal == "beijing_lifted" and lifted_days is not None
                 and lifted_days > LIFT_FRESH_DAYS)
    estimate = _estimate(beijing.get("history") or {}, started, bj_start, bj_end, now)

    start_lag = (started.date() - bj_start.date()).days if started and bj_start else None
    end_lag = (ended.date() - bj_end.date()).days if ended and bj_end else None

    if signal == "beijing_lifted":
        day = bj_end.strftime("%m-%d")
        note = (f"北京 {day} 已解除{matched.get('color') or ''}"
                f"（持续 {matched.get('days')} 天），德州 {started.strftime('%m-%d') if started else '—'} "
                f"启动至今未终止，已滞后 {lifted_days} 天")
    elif signal == "beijing_in_force":
        note = (f"北京 {bj_start.strftime('%m-%d')} 启动的{matched.get('color') or ''}仍在生效"
                f"（第 {(now - bj_start).days + 1} 天），德州跟进解除的概率较低")
    elif signal == "both_closed":
        note = f"北京 {bj_end.strftime('%m-%d')} 解除，德州也已发布终止公告"
    elif signal == "dezhou_closed":
        note = "德州已终止本次响应"
    elif beijing.get("state") == "none":
        note = "北京栏目里暂无空气重污染预警记录"
    elif started:
        note = (f"北京最近一次预警（{bj_start.strftime('%m-%d') if bj_start else '—'} 起）"
                f"与德州本次响应（{started.strftime('%m-%d')} 起）无时间重叠，不作为解除信号")
    else:
        note = "未找到与德州本次响应时间重叠的北京预警"

    feed = []
    span_start = bj_start if dz_state == "terminated" else started
    for item in beijing.get("items") or []:
        eff = _parse_iso(item.get("effective"))
        inside = bool(eff and span_start and span_start.date() <= eff.date() <= stop.date())
        feed.append({**item, "overlap": inside})

    return {
        **beijing,
        "items": feed,
        "signal": signal,
        "signal_label": SIGNAL_ZH.get(signal, ""),
        "stale": stale,
        "estimate": estimate,
        "history": beijing.get("history"),
        "note": note,
        "link": {
            "signal": signal,
            "signal_label": SIGNAL_ZH.get(signal, ""),
            "matched": matched,
            "start_lag_days": start_lag,
            "end_lag_days": end_lag,
            "beijing_lifted_days": lifted_days,
            "dezhou": {
                "state": dz_state,
                "started_at": started.isoformat(timespec="minutes") if started else None,
                "ended_at": ended.isoformat(timespec="minutes") if ended else None,
            },
            "note": note,
        },
    }
