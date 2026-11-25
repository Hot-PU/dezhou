"""分析引擎：只看「这家企业本身会受到什么影响」——政策事实 + 历史时长 + 大模型总结。

不做我方库存/断供测算：那需要采购方内部数据，程序无从得知，也不应假设。
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta

import requests

from .common import env, log, now_cst, rules, settings

COLOR_ORDER = {"红色预警": 3, "橙色预警": 2, "黄色预警": 1}
LINE_RE = re.compile(r"(\d+)\s*条生产线")

REGION_LEVEL_ZH = {"差": "区域仍在大范围污染", "一般": "区域分化", "好": "区域转好"}
REGION_LEVEL_EN = {"差": "still polluted across the region", "一般": "mixed across the region",
                   "好": "clearing across the region"}
REGION_TREND_ZH = {"improving": "未来 24h 转好", "flat": "未来 24h 大致持平",
                   "worsening": "未来 24h 转差"}
REGION_TREND_EN = {"improving": "improving over the next 24h", "flat": "flat over the next 24h",
                   "worsening": "worsening over the next 24h"}
BJ_SIGNAL_EN = {
    "beijing_lifted": ("Beijing has already lifted its alert while Dezhou has not — "
                       "the regional control window is open, so the lift is likely close"),
    "beijing_in_force": ("Beijing is still under the same regional control — "
                         "Dezhou is unlikely to lift alone"),
    "both_closed": "Both Beijing and Dezhou have lifted their alerts",
    "dezhou_closed": "Dezhou has terminated the response",
}
BJ_SIGNAL_ZH = {
    "beijing_lifted": "北京先解除、德州尚未终止，解除临近",
    "beijing_in_force": "北京仍在响应，德州很少单独解除",
    "both_closed": "两地均已解除",
    "dezhou_closed": "德州已终止本次响应",
}


def _parse_iso(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _line_counts(process: str, measure: str) -> tuple[int | None, int | None]:
    """从清单文字里取「共几条线 / 停几条线」，例如（4条生产线）停产 2 条。"""
    total = LINE_RE.search(process or "")
    hit = LINE_RE.search(measure or "")
    return (int(total.group(1)) if total else None,
            int(hit.group(1)) if hit else None)


def _impact_level(reduction_pct: int, affected: int) -> tuple[str, str]:
    """(影响等级 key, 中文标签)"""
    if affected == 0 or reduction_pct <= 0:
        return "none", "不受影响"
    if reduction_pct >= 100:
        return "stop", "全部停产"
    if reduction_pct >= 50:
        return "heavy", f"限产 {reduction_pct}%"
    return "partial", f"限产 {reduction_pct}%"


def duration_window(notice: dict, prediction: dict | None,
                   cfg: dict) -> tuple[float, str | None, str | None]:
    """影响窗口：起点是公告生效时刻，终点是「预计解除」——随巡检推进自动顺延。"""
    duration = float(cfg["analysis"].get("default_duration_days", 5))
    if prediction and prediction.get("predicted_days"):
        duration = float(prediction["predicted_days"])
    if notice.get("kind") == "terminate":
        duration = 0.0   # 响应已终止：没有“持续天数”，窗口收在解除时刻
    eff = _parse_iso(notice.get("effective_time", ""))
    window_start = eff.isoformat(timespec="minutes") if eff else None
    window_end = (eff + timedelta(days=duration)).isoformat(timespec="minutes") if eff else None
    return duration, window_start, window_end


def duration_display(duration: float) -> int | float:
    return int(duration) if float(duration).is_integer() else round(duration, 1)


def duration_texts(duration: float, window_end: str | None,
                   prediction: dict | None) -> tuple[str, str]:
    """「影响时长」证据的文案：已超出历史最长的响应只能写“已持续”，不能写未来的解除日。"""
    shown = duration_display(duration)
    if (prediction or {}).get("overdue"):
        return (f"已持续 {shown} 天（等待终止公告）",
                f"{shown} days so far (awaiting termination notice)")
    return (f"{shown} 天（至 {str(window_end)[:10]}）",
            f"{shown} days (until {str(window_end)[:10]})")


def refresh_duration(assessment: dict, notice: dict, prediction: dict | None,
                     cfg: dict) -> bool:
    """公告没变、但预计解除时间被重算时，刷新企业侧时长、窗口与证据链。"""
    if assessment.get("impact", "none") == "none":
        return False
    duration, window_start, window_end = duration_window(notice, prediction, cfg)
    shown = duration_display(duration)
    changed = (assessment.get("duration_days") != shown
               or assessment.get("window_end") != window_end)
    assessment["duration_days"] = shown
    assessment["window_start"] = window_start
    assessment["window_end"] = window_end
    assessment["predicted_end"] = (prediction or {}).get("predicted_end")
    value, value_en = duration_texts(duration, window_end, prediction)
    for ev in assessment.get("evidence") or []:
        if ev.get("field") != "影响时长":
            continue
        ev["value"] = value
        ev["value_en"] = value_en
        ev["raw"] = (f"预测 {prediction.get('predicted_days') if prediction else '?'} 天；"
                     f"历史中位 {prediction.get('median_days') if prediction else '?'} 天；"
                     f"样本 {prediction.get('sample_size') if prediction else 0} 次")
        break
    return changed


def assess_supplier(supplier: dict, profile: dict, notice: dict,
                    rules_cfg: dict, cfg: dict, prediction: dict | None = None) -> dict:
    """企业侧影响：哪些工序/产线被限，减产多少，持续多久。"""
    color = notice.get("warning_color") or "无预警"
    terminated = notice.get("kind") == "terminate"
    level_data = (profile.get("by_color") or {}).get(color) or {}

    reduction_pct = 0 if terminated else int(level_data.get("reduction_pct", 0))
    lines = [] if terminated else (level_data.get("lines") or [])

    affected_lines = []
    for l in lines:
        if l["way"] in ("", "正常生产"):
            continue
        total, hit = _line_counts(l["process"], l["measure"])
        affected_lines.append({
            "process": l["process"],
            "measure": l["measure"],
            "way": l["way"],
            "total_lines": total,
            "stopped_lines": hit if hit is not None else (total if l["way"] == "停产" else None),
            "cost_per_day": l["cost_per_day"],
            "row": l.get("row"),
            "is_mobile": l["way"] == "移动源管控",
        })

    production = [a for a in affected_lines if not a["is_mobile"]]
    mobile = [a for a in affected_lines if a["is_mobile"]]

    duration, window_start, window_end = duration_window(notice, prediction, cfg)

    impact_key, impact_label = _impact_level(reduction_pct, len(production))
    duration_shown = duration_display(duration)
    reduction = reduction_pct / 100.0

    total_lines = sum(a["total_lines"] or 0 for a in production)
    stopped_lines = sum(a["stopped_lines"] or 0 for a in production)
    if total_lines and stopped_lines:
        line_text = f"{total_lines} 条生产线中 {stopped_lines} 条受限"
        line_text_en = f"{stopped_lines} of {total_lines} production lines restricted"
    elif production:
        line_text = f"{len(production)} 道工序受限"
        line_text_en = f"{len(production)} processes restricted"
    else:
        line_text = "无生产工序受限"
        line_text_en = "no production process restricted"

    parts = []
    for a in production:
        seg = a["process"]
        if a["total_lines"] and a["stopped_lines"]:
            seg += f"：{a['total_lines']} 条线停 {a['stopped_lines']} 条"
        seg += f"（{a['way']}）"
        parts.append(seg)

    summary_text = "正常生产，无强制限产" if not impacted_label(impact_key) else "；".join(parts)
    if impacted_label(impact_key) and mobile:
        summary_text += "；厂内运输：" + "、".join(m["way"] for m in mobile)

    pb = rules_cfg["playbook"].get(impact_key, {}) if impacted_label(impact_key) else {}
    actions = list(pb.get("zh") or [])
    actions_en = list(pb.get("en") or [])

    # 证据链：每个数字都能追到出处，标明是官方原文 / 算术 / 推算
    sheet_ref = f"{profile.get('source_file') or '2-固定源应急减排措施清单.xlsx'} › 固定源"
    sheet_ref_en = (f"{profile.get('source_file') or '2-固定源应急减排措施清单.xlsx'}"
                    f" › sheet “固定源”")
    evidence = [
        {
            "field": "绩效等级", "value": profile.get("performance"),
            "value_en": perf_en(profile.get("performance")),
            "tier": "official",
            "source": f"{sheet_ref} › 第 {profile.get('row')} 行 › 绩效等级*",
            "source_en": f"{sheet_ref_en} › row {profile.get('row')} › column “绩效等级*”",
            "raw": str(profile.get("performance") or ""),
        },
        {
            "field": "本次预警", "value": color or "无",
            "value_en": COLOR_EN.get(color, color or "none"),
            "tier": "official",
            "source": f"公告《{notice.get('title', '')}》",
            "source_en": f"Notice “{notice.get('title', '')}”",
            "raw": f"{notice.get('kind_label', '')} / {notice.get('level_label', '')}",
            "url": notice.get("url") or notice.get("source_url"),
        },
    ]
    for l in affected_lines:
        row_ref = f"第 {l.get('row')} 行" if l.get("row") else "对应行"
        row_ref_en = f"row {l.get('row')}" if l.get("row") else "the matching row"
        evidence.append({
            "field": f"工序与措施 · {l['process']}",
            "value": f"{l['measure'] or l['way']} · {l['way']}",
            "value_en": f"{l['measure'] or way_en(l['way'])} · control: {way_en(l['way'])}",
            "tier": "official",
            "source": f"{sheet_ref} › {row_ref} › 生产线、工序* / {color}_减排措施* / {color}_管控方式*",
            "source_en": (f"{sheet_ref_en} › {row_ref_en} › columns “生产线、工序*” / "
                          f"“{color}_减排措施*” / “{color}_管控方式*”"),
            "raw": f"{l['process']} | {l['measure']} | {l['way']}",
        })
    if production:
        evidence.append({
            "field": "受限产线合计", "value": line_text,
            "value_en": line_text_en,
            "tier": "derived",
            "source": "由清单各行「生产线、工序」「减排措施」中的条数相加",
            "source_en": "Sum of the line counts parsed from the process and measure columns",
            "raw": f"{total_lines} 条（{' + '.join(str(a['total_lines']) for a in production if a['total_lines'])}）"
                   f" / 受限 {stopped_lines} 条",
        })
    if reduction_pct:
        evidence.append({
            "field": "预计减产", "value": f"{reduction_pct}%",
            "value_en": f"{reduction_pct}%",
            "tier": "derived",
            "source": level_data.get("reduction_method") or "取清单管控方式对应压降比例",
            "source_en": ("Weighted by the number of production lines; each row's control type gives its cut factor"),
            "raw": "；".join(f"{a['total_lines'] or '?'} 条 × {a['way']}" for a in production) or "无",
        })
    if level_data.get("daily_cost"):
        evidence.append({
            "field": "企业日应急成本", "value": f"{level_data['daily_cost']:,} 元/天",
            "value_en": f"{level_data['daily_cost']:,} CNY/day",
            "tier": "derived",
            "source": f"{sheet_ref} › {color}_应急成本（元/天）各行相加（清单无企业级合计）",
            "source_en": (f"Sum of “{color}_应急成本（元/天）” across rows — the list has no company-level total"),
            "raw": " + ".join(f"{int(l['cost_per_day'])}" for l in affected_lines if l["cost_per_day"]),
        })
    if impacted_label(impact_key):
        value, value_en = duration_texts(duration, window_end, prediction)
        evidence.append({
            "field": "影响时长", "value": value,
            "value_en": value_en,
            "tier": "inferred",
            "source": "历史同级响应的中位时长 + 当前扩散条件修正（非官方公布，仅为预估）",
            "source_en": ("Historical median duration adjusted for dispersion — an estimate, not an official figure"),
            "raw": f"预测 {prediction.get('predicted_days') if prediction else '?'} 天；"
                   f"历史中位 {prediction.get('median_days') if prediction else '?'} 天；"
                   f"样本 {prediction.get('sample_size') if prediction else 0} 次",
        })

    return {
        "evidence": evidence,
        "name": supplier["name"],
        "product": supplier.get("product") or profile.get("product"),
        "district": profile.get("district"),
        "address": profile.get("address"),
        "lon": profile.get("lon"),
        "lat": profile.get("lat"),
        "industry": profile.get("industry"),
        "industry_branch": profile.get("industry_branch"),
        "performance": profile.get("performance"),
        "capacity": profile.get("capacity"),
        "capacity_unit": profile.get("capacity_unit"),
        "warning_color": color,
        "warning_level": notice.get("warning_level"),
        "reduction_pct": reduction_pct,
        "reduction_method": level_data.get("reduction_method"),
        "impact": impact_key,
        "impact_label": impact_label,
        "impact_summary": summary_text,
        "impact_detail": "；".join(parts) if parts else "",
        "line_text": line_text,
        "line_text_en": line_text_en,
        "affected_lines": production,
        "mobile_lines": mobile,
        "stopped_processes": len([a for a in production if a["way"] == "停产"]),
        "daily_cost": level_data.get("daily_cost", 0),
        "duration_days": duration_shown,
        "window_start": window_start,
        "window_end": window_end,
        "predicted_end": (prediction or {}).get("predicted_end"),
        "actions": actions,
        "actions_en": actions_en,
    }


def impacted_label(key: str) -> bool:
    return key != "none"


COLOR_EN = {"红色预警": "Red alert", "橙色预警": "Orange alert",
            "黄色预警": "Yellow alert", "蓝色预警": "Blue alert", "无预警": "no alert"}
DISP_EN = {"好": "good", "一般": "fair", "差": "poor"}
WAY_EN = {"停产": "shutdown", "限产50%": "50% cut", "限产30%": "30% cut",
          "限产20%": "20% cut", "限产10%": "10% cut", "自主减排": "voluntary reduction",
          "移动源管控": "mobile-source control", "正常生产": "normal production"}
PERF_EN = {"非绩效引领": "non-leading (非绩效引领)", "绩效引领": "performance-leading (绩效引领)",
           "民生豁免-A": "livelihood exemption A", "民生豁免-B": "livelihood exemption B"}


def way_en(way: str) -> str:
    return WAY_EN.get(way, way)


def perf_en(perf: str | None) -> str:
    perf = perf or ""
    return PERF_EN.get(perf, perf)


def _impact_text(a: dict, lang: str) -> str:
    if lang == "en":
        return {
            "stop": "full shutdown",
            "heavy": f"output cut {a['reduction_pct']}%",
            "partial": f"output cut {a['reduction_pct']}%",
            "none": "not affected",
        }.get(a["impact"], a["impact_label"])
    return a["impact_label"]


def _line_text(a: dict, lang: str) -> str:
    total = sum(l.get("total_lines") or 0 for l in a.get("affected_lines") or [])
    stop = sum(l.get("stopped_lines") or 0 for l in a.get("affected_lines") or [])
    if lang == "en":
        if total:
            return f"{stop} of {total} lines restricted"
        return f"{len(a.get('affected_lines') or [])} processes restricted"
    return a["line_text"]


def _sections(assessments: list[dict], notice: dict, aq: dict,
              prediction: dict | None, lang: str) -> dict:
    """规则版总结，按 lang 生成中文或英文文本。"""
    en = lang == "en"
    affected = [a for a in assessments if a["impact"] != "none"]
    stop = [a for a in affected if a["impact"] == "stop"]
    heavy = [a for a in affected if a["impact"] == "heavy"]
    current = aq.get("current") or {}
    dispersion = aq.get("dispersion") or {}
    color_zh = notice.get("warning_color") or "无预警"
    color = COLOR_EN.get(color_zh, color_zh) if en else color_zh
    level = notice.get("level_label") or ""
    duration = affected[0]["duration_days"] if affected else None
    disp_level = dispersion.get("level") or ("未知" if not en else "unknown")
    disp_show = DISP_EN.get(disp_level, disp_level) if en else disp_level
    eff = str(notice.get("effective_time") or "").replace("T", " ")[:16]
    names = "、".join(a["name"] for a in affected)

    # 区域联动：德州按京津冀联防联控启动/解除，只看本地风速是不够的
    region = aq.get("region") or {}
    reg_ok = bool(region.get("available"))
    reg_level = region.get("level") or "未知"
    bj = region.get("beijing") or {}
    reg_trend = (region.get("trend") or {}).get("direction") or "flat"
    if reg_ok and en:
        region_line = (f"Region ({region['city_count']} cities): median AQI {region['median_aqi']:g}, "
                       f"{region['hot_count']} at moderate pollution or worse, Beijing {bj.get('aqi', '—')}, "
                       f"{REGION_TREND_EN.get(reg_trend, reg_trend)} — "
                       f"{REGION_LEVEL_EN.get(reg_level, reg_level)}.")
    elif reg_ok:
        region_line = (f"区域联动（{region['city_count']} 城）：中位 AQI {region['median_aqi']:g}，"
                       f"{region['hot_count']} 城达中度污染以上，北京 {bj.get('aqi', '—')}（{bj.get('level', '—')}），"
                       f"{REGION_TREND_ZH.get(reg_trend, reg_trend)}，"
                       f"{REGION_LEVEL_ZH.get(reg_level, reg_level)}。")
    else:
        region_line = ""

    # 北京官方公告：比 AQI 更权威的解除信号（同一轮区域联防联控）
    bjo = aq.get("beijing") or {}
    bjo_ok = bool(bjo.get("available")) and bjo.get("state") in ("in_force", "lifted")
    bj_signal = bjo.get("signal") or "none"
    bj_line = ""
    if bjo_ok:
        bj_start = str(bjo.get("started_at") or "")[:10]
        bj_end = str(bjo.get("ended_at") or "")[:10]
        bj_level = bjo.get("level") or ("heavy-pollution alert" if en else "空气重污染预警")
        if en:
            window = (f"{bj_level} from {bj_start}"
                      + (f" to {bj_end} ({bjo.get('days')} days)" if bj_end
                         else f" (still in force, day {bjo.get('elapsed_days')})"))
            tail = BJ_SIGNAL_EN.get(bj_signal, "")
            bj_est = bjo.get("estimate") or {}
            if bj_est.get("predicted_end") and bj_est.get("sample_size"):
                tail += (f"; across {bj_est['sample_size']} comparable episodes Dezhou ended a median of "
                         f"{bj_est.get('median_end_lag_days'):g} days after Beijing, pointing to "
                         f"{str(bj_est['predicted_end'])[:10]}"
                         + (" (already due)" if bj_est.get("overdue") else ""))
            bj_line = f"Beijing official: {window}" + (f" — {tail}." if tail else ".")
        else:
            window = (f"{bj_level} {bj_start} 启动"
                      + (f"、{bj_end} 解除（持续 {bjo.get('days')} 天）" if bj_end
                         else f"（第 {bjo.get('elapsed_days')} 天仍在响应）"))
            tail = BJ_SIGNAL_ZH.get(bj_signal, "")
            lag = ((bjo.get("link") or {}).get("beijing_lifted_days"))
            if bj_signal == "beijing_lifted" and lag is not None:
                tail = f"北京先解除、德州滞后 {lag} 天，解除临近"
            bj_est = bjo.get("estimate") or {}
            if bj_est.get("predicted_end") and bj_est.get("sample_size"):
                tail += (f"；按历史 {bj_est['sample_size']} 次可比过程（德州通常在北京解除后 "
                         f"{bj_est.get('median_end_lag_days'):g} 天解除）推算 "
                         f"{str(bj_est['predicted_end'])[:10]}"
                         + ("（已到期）" if bj_est.get("overdue") else ""))
            bj_line = f"北京官方：{window}" + (f"；{tail}。" if tail else "。")

    if notice.get("kind") == "terminate":
        headline = ("Emergency response terminated — production restrictions lifted" if en
                    else "应急响应已终止，供应商限产要求解除")
    elif not affected:
        headline = (f"{color} in force, but no monitored supplier faces mandatory cuts" if en
                    else f"{color}响应生效，但本次未触及在监控供应商的强制限产工序")
    else:
        headline = (f"{color} level {level}: {names} — {_impact_text(affected[0], lang)}, "
                    f"~{duration} days" if en else
                    f"{color}（{level}）响应生效：{names} "
                    f"{affected[0]['impact_label']}，预计持续 {duration} 天")

    # 明细表已由页面「03 影响」区块承担，这里不再重复输出表格
    rows = []

    def _n(v):
        return "—" if v is None else f"{round(float(v))}"

    history_block = []
    if prediction and prediction.get("available"):
        end = (prediction.get("predicted_end") or "")[:10]
        applicable = prediction.get("applicable", True)
        overdue = bool(prediction.get("overdue"))
        conditional = bool(prediction.get("conditional"))
        elapsed = prediction.get("elapsed_days")
        max_days = prediction["range"][1]
        if en:
            if not applicable:
                tail = "The response has already been terminated, so no further duration estimate applies."
            elif overdue:
                tail = (f"This episode has already run {elapsed} days — longer than the {max_days}-day record — "
                        f"so the end date is left to the official termination notice.")
            elif conditional:
                tail = (f"It has already run {elapsed} days, past the median; extrapolating from the longer "
                        f"episodes with current dispersion ({disp_show})"
                        f"{f' and {REGION_LEVEL_EN.get(reg_level, reg_level)}' if reg_ok else ''}, "
                        f"it is expected to end around **{end}**.")
            else:
                tail = (f"With current dispersion ({disp_show})"
                        f"{f' and {REGION_LEVEL_EN.get(reg_level, reg_level)}' if reg_ok else ''}, "
                        f"this episode is expected to end around **{end}**.")
            history_block = [
                f"### Historical pattern\n"
                f"The notice column yields {prediction['sample_size']} complete start→terminate episodes; "
                f"median **{prediction['median_days']} days** (mean {prediction['mean_days']}, "
                f"P75 {prediction['p75_days']}, range {prediction['range'][0]}–{max_days}). {tail}",
            ]
        else:
            if not applicable:
                tail = "本次响应已终止，不再适用时长推算。"
            elif overdue:
                tail = (f"本次已持续 {elapsed} 天，超过历史最长 {max_days} 天，"
                        f"不再外推解除日期，需以官方终止公告为准。")
            elif conditional:
                tail = (f"本次已持续 {elapsed} 天，已超出中位时长，按历史更长的 {prediction.get('conditional_samples')} "
                        f"次样本顺延，结合当前扩散条件「{disp_level}」"
                        f"{f'与区域联动「{reg_level}」' if reg_ok else ''}，预计 **{end}** 前后解除。")
            else:
                tail = (f"结合当前扩散条件「{disp_level}」"
                        f"{f'与区域联动「{reg_level}」' if reg_ok else ''}，本次预计 **{end}** 前后解除。")
            history_block = [
                f"### 历史规律\n"
                f"栏目共识别出 {prediction['sample_size']} 次「启动→终止」完整的同类响应，"
                f"中位持续 **{prediction['median_days']} 天**（均值 {prediction['mean_days']} 天，"
                f"P75 {prediction['p75_days']} 天，范围 {prediction['range'][0]}–{max_days} 天）。{tail}",
            ]

    impact_lines = []
    for a in affected:
        detail = a["impact_detail"] or a["impact_summary"]
        if en:
            impact_lines.append(
                f"- **{a['name']}**: {_impact_text(a, lang)}. {a['line_text_en']}; "
                f"from {str(a['window_start'] or '')[:10]} for about {a['duration_days']} days "
                f"(listed emergency cost ≈ {a['daily_cost']:,} CNY/day)."
            )
        else:
            impact_lines.append(
                f"- **{a['name']}**：{a['impact_label']}，{detail}；"
                f"影响时段 {str(a['window_start'] or '')[:10]} 起，约 {a['duration_days']} 天"
                f"（清单填报日应急成本约 {a['daily_cost']:,} 元）。"
            )

    wind = (aq.get("weather") or {}).get("wind_speed", "—")
    if en:
        summary = "\n".join([
            f"### Situation today\n"
            f"Dezhou published “{notice.get('title', '')}” on **{notice.get('publish_date', '')}**, "
            f"alert level **{color} ({level})**, effective {eff}. "
            f"City AQI **{_n(current.get('aqi'))}**, PM2.5 {_n(current.get('pm25'))} μg/m³, "
            f"wind {wind} m/s, dispersion **{disp_show}**."
            + (f"\n{region_line}" if region_line else "")
            + (f"\n{bj_line}" if bj_line else ""),
            "### Impact on suppliers\n"
            + ("\n".join(impact_lines) if impact_lines
               else "This alert level does not trigger mandatory measures for any monitored supplier.")
            + "\n\nAll processes and cut percentages come from the official fixed-source reduction list, "
              "not from rules of thumb; a red alert turns the same rows into a full shutdown.",
            *history_block,
        ])
    else:
        summary = "\n".join([
            f"### 今日态势\n"
            f"德州市于 **{notice.get('publish_date', '')}** 发布公告《{notice.get('title', '')}》，"
            f"预警级别为 **{color}（{level}应急响应）**，生效时间 {eff}。"
            f"当前市区 AQI **{_n(current.get('aqi'))}（{current.get('level', '未知')}）**，"
            f"PM2.5 {_n(current.get('pm25'))} μg/m³，风速 {wind} m/s，"
            f"扩散条件**{disp_level}**（{dispersion.get('note', '')}）。"
            + (f"\n{region_line}" if region_line else "")
            + (f"\n{bj_line}" if bj_line else ""),
            "### 对供应商的影响\n"
            + ("\n".join(impact_lines) if impact_lines
               else "本次预警级别未触发在监控供应商的强制减排措施，生产不受影响。")
            + "\n\n以上工序与减产比例全部取自《固定源应急减排措施清单》，"
              "不是按经验估算；红色预警升级时同一份清单里对应的是全工序停产。",
            *history_block,
        ])

    counter = []
    for a in affected:
        counter.extend((a.get("actions_en") if en else a.get("actions"))[:3] or [])
    if notice.get("kind") == "terminate":
        counter = (["Restrictions are lifted — ask suppliers to resume normal delivery and reconcile outstanding orders"]
                   if en else ["限产约束解除，通知供应商恢复正常交付，并核对前期欠交与在途数量"])
    elif not counter:
        counter = list((rules_cfg_playbook_low() if not en else
                        (rules()["playbook"].get("partial") or {}).get("en") or []))

    alerts = []
    if stop:
        alerts.append((f"{len(stop)} supplier(s) required to shut down all processes: {', '.join(a['name'] for a in stop)}"
                       if en else f"{len(stop)} 家供应商被要求全工序停产：" + "、".join(a["name"] for a in stop)))
    elif heavy:
        alerts.append((f"{len(heavy)} supplier(s) cutting output by 50% or more: {', '.join(a['name'] for a in heavy)}"
                       if en else f"{len(heavy)} 家供应商限产 50% 及以上：" + "、".join(a["name"] for a in heavy)))
    if current.get("aqi") and current["aqi"] > 200:
        alerts.append((f"AQI {current['aqi']} — heavy pollution, restrictions likely to continue or escalate" if en
                       else f"AQI {current['aqi']}，已达重度污染，预计管控持续或升级"))
    if dispersion.get("level") == "差":
        alerts.append(("Poor dispersion — the response is likely to stay in force; plan for the historical maximum"
                       if en else "扩散条件差，应急响应大概率维持，需按历史上限天数准备"))
    if reg_ok and reg_level == "差":
        alerts.append((f"{region['hot_count']} of {region['city_count']} tracked cities are still at moderate "
                       f"pollution or worse (Beijing {bj.get('aqi', '—')}) — joint regional control usually delays the lift"
                       if en else
                       f"区域 {region['city_count']} 城中仍有 {region['hot_count']} 城达中度污染以上"
                       f"（北京 {bj.get('aqi', '—')}），按联防联控解除大概率延后"))
    if bj_signal == "beijing_in_force":
        alerts.append((f"Beijing is still under the same {bjo.get('level') or 'heavy-pollution'} control "
                       f"(day {bjo.get('elapsed_days')}) — Dezhou rarely lifts alone"
                       if en else
                       f"北京仍在响应（{bjo.get('level') or '空气重污染预警'}第 {bjo.get('elapsed_days')} 天），"
                       f"德州很少单独解除，预计解除大概率延后"))
    elif bj_signal == "beijing_lifted" and bjo.get("stale"):
        alerts.append((f"Beijing lifted on {str(bjo.get('ended_at'))[:10]} but Dezhou has not — the two cities "
                       f"have decoupled; do not shorten the impact window on that basis alone"
                       if en else
                       f"北京已于 {str(bjo.get('ended_at'))[:10]} 解除而德州未终止，两地已脱钩："
                       f"不要据此提前缩短影响窗口，以德州官方公告为准"))
    if notice.get("kind") == "terminate":
        alerts.append(("Response terminated — ask suppliers to resume normal delivery and reconcile backlogs"
                       if en else "响应已终止，可要求供应商恢复正常交付并复核前期欠交量"))

    # 北京官方状态对解除节奏的补充判断
    bj_outlook = ""
    bj_est = bjo.get("estimate") or {}
    bj_est_date = str(bj_est.get("predicted_end") or "")[:10]
    if bj_signal == "beijing_lifted":
        if bj_est_date and bj_est.get("sample_size"):
            bj_outlook = (
                f"Beijing lifted on {str(bjo.get('ended_at'))[:10]}; across {bj_est['sample_size']} comparable "
                f"episodes Dezhou ended a median of {bj_est.get('median_end_lag_days'):g} days after Beijing, "
                f"pointing to {bj_est_date}."
                if en else
                f"北京已于 {str(bjo.get('ended_at'))[:10]} 解除；按 {bj_est['sample_size']} 次可比过程的"
                f"中位滞后 {bj_est.get('median_end_lag_days'):g} 天，德州预计 {bj_est_date} 前后解除。"
            )
        else:
            bj_outlook = (
                f"Beijing lifted on {str(bjo.get('ended_at'))[:10]} while Dezhou has not; if Dezhou follows within "
                f"days the window can close at the days already elapsed, otherwise keep extending towards the upper bound."
                if en else
                f"北京已于 {str(bjo.get('ended_at'))[:10]} 解除而德州尚未终止：若数日内跟进终止，"
                f"影响窗口可按当前已持续天数收口；若仍无公告，则继续按上限顺延。"
            )
    elif bj_signal == "beijing_in_force":
        bj_outlook = (
            f"Beijing is still under the same control (day {bjo.get('elapsed_days')}), so Dezhou is unlikely "
            f"to lift before it does."
            if en else
            f"北京仍在响应（第 {bjo.get('elapsed_days')} 天），德州大概率不会先于北京解除。"
        )

    if prediction and prediction.get("available") and prediction.get("applicable") is not False:
        end = (prediction.get("predicted_end") or "")[:10]
        max_days = prediction["range"][1]
        if prediction.get("overdue"):
            outlook = (
                f"This episode has already run {prediction.get('elapsed_days')} days, beyond the {max_days}-day "
                f"maximum on record; no end date is extrapolated — treat the official termination notice as the "
                f"only reliable trigger, and plan weekly capacity checks in the meantime." if en else
                f"本次响应已持续 {prediction.get('elapsed_days')} 天，超过历史最长 {max_days} 天，"
                f"已不再外推解除日期：后续以官方终止公告为准，期间按周核对供应商排产与实际出货。"
            )
        elif en:
            region_tail = (f", and {REGION_LEVEL_EN.get(reg_level, reg_level)}" if reg_ok else "")
            outlook = (f"Across {prediction['sample_size']} comparable episodes the median was "
                       f"{prediction['median_days']} days (range {prediction['range'][0]}–{max_days}); "
                       f"with dispersion {disp_show}{region_tail} the response is expected to end around {end}. "
                       f"If no termination notice appears, dispersion worsens, or the region stays polluted, "
                       f"extend towards the upper bound.")
        else:
            elapsed_note = (f"，本次已持续 {prediction.get('elapsed_days')} 天并按时长分布顺延"
                            if prediction.get("conditional") else "")
            region_note = (f"与区域联动「{reg_level}」" if reg_ok else "")
            outlook = (
                f"按历史 {prediction['sample_size']} 次同类响应的中位时长 {prediction['median_days']} 天"
                f"（范围 {prediction['range'][0]}–{max_days} 天）{elapsed_note}，叠加当前扩散条件"
                f"「{disp_level}」{region_note}，预计本次响应在 {end} 前后解除；"
                f"若届时未发布终止公告、扩散转差或区域仍未转好，影响时长需按上限顺延。"
            )
    elif prediction and prediction.get("applicable") is False:
        outlook = ("The response has been terminated — restrictions are lifted; watch the column for the next "
                   "start notice and keep the weekly check." if en else
                   "本次响应已终止，限产约束解除；继续关注栏目是否有新的启动公告，保持周度巡检。")
    else:
        outlook = (f"With dispersion at {disp_show}, measures are expected to continue; "
                   f"an upgrade would turn the affected processes into a full shutdown." if en else
                   f"若未来 48 小时扩散条件维持「{disp_level}」，管控措施预计持续；"
                   f"升级到更高一级预警时，受影响工序将转为全部停产。")

    if bj_outlook:
        outlook = f"{outlook} {bj_outlook}"

    return {"headline": headline, "summary_md": summary,
            "counter_hoarding": counter, "alerts": alerts, "outlook": outlook}


def baseline_from_rules(assessments: list[dict], notice: dict, aq: dict,
                        prediction: dict | None = None) -> dict:
    """无 AI key 时的规则版总结：结构与 AI 输出完全一致，中英双语。"""
    zh = _sections(assessments, notice, aq, prediction, "zh")
    en = _sections(assessments, notice, aq, prediction, "en")
    return {"engine": "rules", **zh, "i18n": {"en": en}}


def refresh_analysis(assessments: list[dict], notice: dict, air: dict,
                     prediction: dict | None, previous: dict | None = None) -> dict:
    """公告未更新但时间/气象推进时，用规则引擎重算文字：日期与空气质量跟得上。

    旧文案里写死的「预计解除日」和 AQI 会过期，与其留着自相矛盾，不如用可复现的
    规则文本重写；之前的引擎标识保留在 ai_engine 里供追溯。
    """
    fresh = baseline_from_rules(assessments, notice, air, prediction)
    prev = previous or {}
    old_engine = prev.get("engine") or "rules"
    if old_engine != "rules":
        fresh["ai_engine"] = old_engine
        fresh["ai_generated_at"] = prev.get("refreshed_at") or prev.get("generated_at")
    fresh["refreshed_at"] = now_cst().isoformat(timespec="seconds")
    return fresh



def rules_cfg_playbook_low() -> list[str]:
    return list((rules()["playbook"].get("partial") or {}).get("zh") or [])


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    return m.group(1).strip() if m else text


def call_ai(payload: dict, cfg: dict | None = None) -> dict | None:
    """调用 OpenAI 兼容接口；失败返回 None 由规则版兜底。"""
    cfg = cfg or settings()
    ai_cfg = cfg["ai"]
    key = env("AI_API_KEY") or env("OPENAI_API_KEY")
    if not key:
        log("未配置 AI_API_KEY，使用规则引擎生成总结")
        return None
    base = (env("AI_BASE_URL") or ai_cfg["base_url"]).rstrip("/")
    model = env("AI_MODEL") or ai_cfg["model"]
    body = {
        "model": model,
        "temperature": ai_cfg.get("temperature", 0.3),
        "max_tokens": ai_cfg.get("max_tokens", 2600),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_prompt(payload)},
        ],
    }
    try:
        log(f"调用大模型分析: {model} @ {base}")
        r = requests.post(f"{base}/chat/completions", json=body, timeout=ai_cfg.get("timeout", 90),
                          headers={"Authorization": f"Bearer {key}",
                                   "Content-Type": "application/json"})
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        data = json.loads(_strip_code_fence(content))
        # 模型若给了英文版，规整到与规则引擎一致的 i18n.en 结构
        if isinstance(data.get("en"), dict):
            data["i18n"] = {"en": data.pop("en")}
        data["engine"] = f"ai:{model}"
        return data
    except Exception as exc:  # noqa: BLE001
        log(f"大模型调用失败，回退规则引擎: {type(exc).__name__}: {exc}")
        return None


SYSTEM_PROMPT = """你是供应链政策风险分析师，只分析"这家供应商本身会受到什么影响"。
输入包含：德州市重污染天气应急响应公告摘要、空气/气象实况、
京津冀及周边城市的区域联动实况（region）、历史响应时长统计，
以及该企业在《固定源应急减排措施清单》中的管控措施（哪些工序、几条线、管控方式）。

硬性要求：
1. 只使用输入中给出的企业与数字。**不要分析或猜测采购方自己的库存、交期、替代供应商**，也不要估算断供天数——
   这些数据没有提供，编造即为错误。
2. 只回答三件事：哪些工序/产线受影响、减产多少（%）、影响多长时间（天）。
3. 严格区分"政府清单要求"与"供应商自己的说法"：清单限的是特定工序的部分生产线，不等于全厂停产。
   区域联动（region）是解除判断的一半：区域中位 AQI 仍高、或北京未转好时，不要给"提前解除"的结论。
   北京官方公告（beijing_official）比 AQI 更权威：北京已解除而德州未终止时，可判断为解除临近；
   北京仍在响应时，不要给出德州单独提前解除的结论。
4. 输出 JSON，键为 headline / summary_md / counter_hoarding / alerts / outlook，
   另加 "en" 对象，放同样五个键的英文版本（同一份事实，不要另行发挥）：
   - headline：一句话，含企业名、影响程度、时长，不超过 60 字。
   - summary_md：Markdown，三小节：「今日态势」「受影响工序与幅度」「影响时长判断」，不要用表格。
   - counter_hoarding：4-6 条反制供应商以限产为由囤货/涨价/拖延的动作，要具体到话术依据或合同条款。
   - alerts：0-3 条需立刻上报的风险点。
   - outlook：预计解除时间（依据历史时长统计）与升级情形下的变化。
5. 中文，克制、数字化，不夸张。"""


def build_prompt(payload: dict) -> str:
    notice = payload["notice"]
    aq = payload["air"]
    assessments = payload["suppliers"]
    region = aq.get("region") or {}
    region_brief = ({
        "level": region.get("level"), "median_aqi": region.get("median_aqi"),
        "hot_count": region.get("hot_count"), "city_count": region.get("city_count"),
        "beijing": region.get("beijing"), "trend": region.get("trend"),
    } if region.get("available") else None)
    bj = aq.get("beijing") or {}
    bj_brief = ({
        "state": bj.get("state"), "level": bj.get("level"),
        "started_at": bj.get("started_at"), "ended_at": bj.get("ended_at"),
        "days": bj.get("days"), "elapsed_days": bj.get("elapsed_days"),
        "signal": bj.get("signal"), "stale": bj.get("stale"),
        "beijing_estimated_end": bj.get("estimate"),
        "beijing_history": {
            "start_lag": (bj.get("history") or {}).get("start_lag"),
            "end_lag": (bj.get("history") or {}).get("end_lag"),
            "pairs": (bj.get("history") or {}).get("pairs"),
        },
        "link": bj.get("link"),
    } if bj.get("available") else None)
    lines = [
        "## 公告",
        f"标题：{notice.get('title')}",
        f"发布日期：{notice.get('publish_date')}　类型：{notice.get('kind_label')}",
        f"预警：{notice.get('warning_color') or '无'}　响应级别：{notice.get('level_label') or '无'}",
        f"生效时间：{notice.get('effective_time')}",
        f"正文节选：{(notice.get('attachment_text') or notice.get('body') or '')[:2200]}",
        "",
        "## 空气与气象",
        json.dumps({
            "aqi": aq.get("current"), "weather": aq.get("weather"),
            "dispersion": aq.get("dispersion"),
            "region": region_brief,
            "beijing_official": bj_brief,
            "next24h_pm25_avg": aq.get("forecast_pm25_avg_next24h"),
        }, ensure_ascii=False),
        "",
        "## 在监控企业（措施来自减排清单，事实依据）",
    ]
    for a in assessments:
        lines.append(json.dumps({
            "企业": a["name"], "区县": a["district"],
            "行业": f"{a['industry']}/{a['industry_branch']}",
            "绩效等级": a["performance"], "年产能": f"{a['capacity']}{a['capacity_unit'] or ''}",
            "本次预警": a["warning_color"],
            "影响程度": a["impact_label"],
            "受影响工序": [
                {"工序": l["process"], "总产线": l["total_lines"],
                 "停产/限产产线": l["stopped_lines"], "管控方式": l["way"], "措施原文": l["measure"]}
                for l in a["affected_lines"]
            ],
            "厂内运输管控": [l["way"] for l in a["mobile_lines"]],
            "影响时长_天": a["duration_days"],
            "企业日应急成本_元": a["daily_cost"],
        }, ensure_ascii=False))
    lines.append("")
    lines.append("## 历史响应时长统计（历次启动/终止公告配对得出）")
    lines.append(json.dumps(payload.get("prediction") or {"available": False}, ensure_ascii=False))
    lines.append("")
    lines.append("请按系统提示输出 JSON。")
    return "\n".join(lines)


def analyze(notice: dict, profiles: dict, suppliers_cfg: list[dict], air: dict,
            rules_cfg: dict | None = None, cfg: dict | None = None,
            prediction: dict | None = None) -> dict:
    rules_cfg = rules_cfg or rules()
    cfg = cfg or settings()
    assessments = []
    for s in suppliers_cfg:
        profile = profiles.get(s["name"])
        if not profile:
            log(f"清单中未找到供应商「{s['name']}」，跳过（请检查企业名称或 alias）")
            continue
        assessments.append(assess_supplier(s, profile, notice, rules_cfg, cfg, prediction))

    payload = {"notice": notice, "air": air, "suppliers": assessments, "prediction": prediction}
    result = call_ai(payload, cfg) or baseline_from_rules(assessments, notice, air, prediction)
    return {"assessments": assessments, "analysis": result}
