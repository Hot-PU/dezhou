"""历史规律：从栏目全部公告里成对识别「启动 → 终止」，估算本次响应持续时间与预计解除时间。"""
from __future__ import annotations

import math
import re
import statistics
from datetime import datetime, timedelta

from .common import CST, now_cst

# 扩散条件对时长的修正（天）
DISPERSION_ADJUST = {"好": -1, "一般": 0, "差": 2}
# 区域联动修正（天）：京津冀还在污染时不容易单独解除，反之会提前
REGION_ADJUST = {"好": -1, "一般": 0, "差": 1}
# 北京官方公告修正（天）由 src/beijing.py 给出：北京先解除 = 解除临近，北京仍在响应 = 延后


def classify(title: str) -> dict:
    """公告类型与级别（只看标题，标题里的信息最可靠）。"""
    if "终止" in title or "解除" in title:
        kind = "terminate"
    elif "启动" in title:
        kind = "startup"
    elif "升级" in title:
        kind = "upgrade"
    else:
        kind = "other"
    m = re.search(r"([ⅠⅡⅢⅣ])\s*级", title)
    level = m.group(1) if m else ""
    color = re.search(r"(红色|橙色|黄色|蓝色)预警", title)
    return {"kind": kind, "level": level, "color": color.group(1) + "预警" if color else ""}


def _rank(level: str | None) -> int:
    """预警级别高低：Ⅰ > Ⅱ > Ⅲ > Ⅳ。"""
    return {"Ⅰ": 4, "Ⅱ": 3, "Ⅲ": 2, "Ⅳ": 1}.get(level or "", 0)


def _date(item: dict) -> datetime | None:
    try:
        return datetime.fromisoformat(item["publish_date"]).replace(tzinfo=CST)
    except (KeyError, TypeError, ValueError):
        return None


def episodes(items: list[dict]) -> list[dict]:
    """把原始公告列表还原成「一次响应 = 启动 + 终止」。"""
    ordered = sorted(
        [i for i in items if _date(i)],
        key=lambda i: (_date(i), i.get("id", "")),
    )
    out: list[dict] = []
    open_ep: dict | None = None

    for item in ordered:
        meta = classify(item.get("title", ""))
        day = _date(item)
        if meta["kind"] in ("startup", "upgrade"):
            same_day = open_ep and open_ep["start"].date() == day.date()
            if open_ep and not same_day:
                # 没有终止公告就来了新启动：把上段按覆盖日截止，标记为不完整
                open_ep["end"] = day
                open_ep["incomplete"] = True
                _finish(open_ep)
                out.append(open_ep)
                open_ep = None
            if open_ep and same_day:
                # 同日升级（启动Ⅲ级 → 升级Ⅱ级），不新开一段，只升级级别
                open_ep["upgrades"].append({"date": day, "level": meta["level"]})
                if _rank(meta["level"]) > _rank(open_ep.get("level")):
                    open_ep["level"] = meta["level"]
                    open_ep["color"] = meta["color"] or open_ep.get("color")
                continue
            open_ep = {
                "start": day,
                "level": meta["level"],
                "color": meta["color"],
                "start_title": item.get("title", ""),
                "start_url": item.get("url", ""),
                "upgrades": [],
            }
        elif meta["kind"] == "terminate" and open_ep:
            if meta["level"]:
                open_ep["upgrades"].append({"date": day, "level": meta["level"]})
            open_ep["end"] = day
            open_ep["end_title"] = item.get("title", "")
            open_ep["end_url"] = item.get("url", "")
            open_ep["incomplete"] = False
            _finish(open_ep)
            out.append(open_ep)
            open_ep = None

    if open_ep:  # 当前仍在响应的这一段
        open_ep["end"] = None
        open_ep["incomplete"] = False
        open_ep["ongoing"] = True
        out.append(open_ep)

    return out


def _finish(ep: dict) -> None:
    if ep.get("end") and ep.get("start"):
        days = (ep["end"] - ep["start"]).days
        ep["days"] = max(1, days)
    else:
        ep["days"] = None


def _signed(days: int) -> str:
    """带符号的天数，用排版用的减号（−）而不是连字符。"""
    return ("+" if days > 0 else "−" if days < 0 else "") + str(abs(days))


def _parse_iso(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=CST)


def _estimate(base_pool: list[int], median: float, basis_note: str,
              current_start: datetime | None, dispersion_level: str | None,
              now: datetime, regional_level: str | None = None) -> dict:
    """把「历史中位 + 扩散/区域修正」落到一个不会倒退的预计解除时间上。

    响应持续时间越长，历史样本里还没结束的那部分越少，所以要按「已持续 N 天」
    重新切片：只用比 N 天更长的样本估剩余天数；若已超过历史最长样本，就不再外推。
    """
    disp_adjust = DISPERSION_ADJUST.get(dispersion_level or "", 0)
    region_adjust = REGION_ADJUST.get(regional_level or "", 0)
    adjust = max(-2, min(3, disp_adjust + region_adjust))
    base_days = max(1, round(median + adjust))
    days = base_days
    conditional = False
    conditional_samples = 0
    overdue = False
    elapsed_days = None
    remaining = None

    if current_start:
        elapsed = max(0.0, (now - current_start).total_seconds() / 86400)
        elapsed_days = int(elapsed)
        if elapsed >= base_days:
            survivors = [d for d in base_pool if d > elapsed]
            conditional_samples = len(survivors)
            if survivors:
                conditional = True
                remaining = statistics.median([d - elapsed for d in survivors])
                days = max(base_days, math.ceil(elapsed) + max(1, round(remaining + adjust)))
            else:
                overdue = True
                days = max(base_days, math.ceil(elapsed))

    predicted_end = None
    if current_start and not overdue:
        predicted_end = (current_start + timedelta(days=days)).isoformat(timespec="minutes")

    disp = dispersion_level or "未知"
    adjust_note = (f"扩散条件{disp}（{_signed(disp_adjust)} 天）" if disp_adjust
                   else f"扩散条件{disp}")
    if regional_level:
        adjust_note += (f"、区域联动{regional_level}（{_signed(region_adjust)} 天）"
                        if region_adjust else f"、区域联动{regional_level}")
    if overdue:
        basis = (f"{basis_note}，中位 {median:g} 天；本次已持续 {elapsed_days} 天，"
                 f"超过历史最长 {max(base_pool)} 天，不再外推解除日期")
    elif conditional:
        basis = (f"{basis_note}，中位 {median:g} 天；本次已持续 {elapsed_days} 天，"
                 f"按 {conditional_samples} 次更长样本的剩余中位 {round(remaining or 0, 1):g} 天顺延"
                 f"（{adjust_note}）")
    else:
        basis = f"{basis_note}，中位 {median:g} 天；{adjust_note}"

    return {
        "predicted_days": days,
        "predicted_end": predicted_end,
        "elapsed_days": elapsed_days,
        "as_of": now.isoformat(timespec="minutes"),
        "conditional": conditional,
        "conditional_samples": conditional_samples,
        "remaining_days": round(remaining, 1) if remaining is not None else None,
        "overdue": overdue,
        "adjust": adjust,
        "dispersion_adjust": disp_adjust,
        "region_adjust": region_adjust,
        "regional_level": regional_level,
        "basis": basis,
    }


def _apply_beijing(estimate: dict, bj: dict, current_start: datetime | None,
                   now: datetime) -> None:
    """把「北京→德州历史滞后」并入预计解除：北京先解除取较早，仍在响应取较晚。

    依据是北京历次预警与德州历次响应的配对标定（见 src/beijing.py 的 attach_history）：
    德州通常在北京解除后 1–3 天解除，所以北京解除日 + 中位滞后就是一个独立的预计日期。
    """
    bj_est = (bj or {}).get("estimate") or {}
    estimate["beijing_estimate"] = bj_est or None
    if not bj_est:
        return
    date = _parse_iso(bj_est.get("predicted_end"))
    if not (date and current_start and estimate.get("predicted_end")
            and not estimate.get("overdue")):
        return
    base_date = _parse_iso(estimate["predicted_end"])
    state = (bj or {}).get("state")
    stale = bool((bj or {}).get("stale"))
    moved = False
    if base_date and not stale:
        if state == "lifted" and date < base_date and date >= now:
            moved = True
        elif state == "in_force" and date > base_date:
            moved = True
    if moved:
        days = max(1, math.ceil((date - current_start).total_seconds() / 86400))
        estimate["predicted_days"] = days
        estimate["predicted_end"] = (current_start + timedelta(days=days)).isoformat(
            timespec="minutes")
        estimate["beijing_bound"] = True

    lag = bj_est.get("median_end_lag_days")
    sample = bj_est.get("sample_size")
    if not stale and lag is not None and sample:
        overdue = "，已到期未终止" if bj_est.get("overdue") else ""
        estimate["basis"] += (
            f"；按北京→德州历史关系（{sample} 次可比，德州通常在北京解除后 "
            f"{lag:g} 天解除）推算 {date.strftime('%m-%d')}{overdue}")
    else:
        estimate["beijing_bound"] = False


def predict(items: list[dict], current_start: datetime | None = None,
            dispersion_level: str | None = None, level: str | None = None,
            now: datetime | None = None, regional_level: str | None = None,
            beijing: dict | None = None) -> dict:
    """基于历史响应时长 + 扩散条件 + 区域联动 + 北京官方状态 + 已持续天数，给出预计解除日期。

    结果随时间推进自动顺延：每次巡检都可以重新调用，不需要公告有变化。
    """
    eps = episodes(items)
    completed = [e for e in eps if e.get("days") and not e.get("incomplete")]
    durations = [e["days"] for e in completed]

    same_level = [e["days"] for e in completed if e.get("level") == level and level]
    base_pool = same_level if len(same_level) >= 3 else durations
    basis_note = (f"同级别（{level}级）历史 {len(same_level)} 次" if len(same_level) >= 3
                  else f"全部历史 {len(durations)} 次响应")

    if not base_pool:
        return {"available": False, "reason": "历史样本不足"}

    median = statistics.median(base_pool)
    mean = round(statistics.fmean(base_pool), 1)
    p75 = sorted(base_pool)[min(len(base_pool) - 1, int(len(base_pool) * 0.75))]

    bj = beijing or {}
    now = now or now_cst()
    estimate = _estimate(base_pool, median, basis_note, current_start,
                         dispersion_level, now, regional_level)
    _apply_beijing(estimate, bj, current_start, now)

    # 最近的样本，供前端展示
    recent = [
        {
            "start": e["start"].strftime("%Y-%m-%d"),
            "end": e["end"].strftime("%Y-%m-%d") if e.get("end") else None,
            "days": e.get("days"),
            "level": e.get("level"),
            "incomplete": e.get("incomplete", False),
        }
        for e in eps[-12:]
    ]

    return {
        "available": True,
        **estimate,
        "median_days": median,
        "mean_days": mean,
        "p75_days": p75,
        "range": [min(base_pool), max(base_pool)],
        "sample_size": len(base_pool),
        "recent": recent,
    }
