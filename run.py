"""巡检入口：抓最新公告 → 解析附件 → 规则/AI 分析 → 生成站点。

用法：
    python run.py              # 每日巡检（CI 用）
    python run.py --force      # 忽略"公告未更新"，强制重新分析
    python run.py --offline    # 不联网，用上次抓取的数据重建页面（调试前端）
    python run.py --snapshot   # 从 Excel 重建 data/suppliers_snapshot.json（内置企业数据）
"""
from __future__ import annotations

import argparse
import copy
import json
import socket
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from src import (analyze, aqi, beijing, build_site, fetch, history as hist,
                 notify, outlook, parse_notice, reduction_list, region,
                 thresholds, translate)
from src.common import (CST, ROOT, decode_html, force_utf8_stdout,
                        load_yaml, log, now_cst, read_json, redact, rules,
                        settings, source_proxy, suppliers, write_json, write_text)

STATE = ROOT / "data" / "state.json"
LATEST = ROOT / "data" / "latest.json"
HISTORY = ROOT / "data" / "history.json"
RAW = ROOT / "data" / "raw"


def pick_target(items: list[dict]) -> dict | None:
    """只关心最新一条公告（用户要求：仅抓取并显示最新信息）。"""
    return items[0] if items else None


def load_profile(supplier: dict, cache: dict) -> dict | None:
    key = supplier["name"]
    if key not in cache:
        cache[key] = reduction_list.profile(
            supplier["name"], supplier.get("alias"), rules())
    return cache[key]


def collect_notice(notice_item: dict, cfg: dict) -> dict:
    detail = fetch.fetch_notice_detail(notice_item, cfg)
    text = ""
    attachment_meta = []
    for att in detail.get("attachments", []):
        try:
            path = fetch.download_attachment(detail, att, RAW / detail["id"], cfg)
            attachment_meta.append({"name": att["name"], "url": att["url"],
                                    "saved": str(path.relative_to(ROOT))})
            if not text and path.suffix.lower() in (".docx", ".doc", ".pdf"):
                text = fetch.extract_docx_text(path)
        except Exception as exc:  # noqa: BLE001 - 单个附件失败不阻断主流程
            log(f"  附件处理失败 {att['name']}: {exc}")
    detail["attachment_files"] = attachment_meta
    detail["attachment_text"] = text
    write_json(RAW / detail["id"] / "notice.json", detail)
    write_text(RAW / detail["id"] / "notice.txt", detail.get("body", "") + "\n\n" + text)
    log(f"公告正文 {len(detail.get('body', ''))} 字 / 附件原文 {len(text)} 字")
    return detail


def beijing_source(air: dict) -> dict:
    """数据来源卡片里的北京官方栏目条目（公告未更新时也要刷新）。"""
    bj = air.get("beijing") or {}
    return {
        "provider": "北京市应急管理局 · 预警信息栏目",
        "url": bj.get("url") or beijing.COLUMN_URL,
        "state": bj.get("state"),
        "count": bj.get("total"),
        "note": "空气重污染预警的发布/启动/解除公告，与德州本次响应做时间重叠比对",
    }


def build_payload(notice: dict, assessments: list[dict], analysis: dict,
                  air: dict, history: list[dict], status: str,
                  analysis_date: str, analysis_generated_at: str,
                  cfg: dict, prediction: dict | None = None,
                  threshold: dict | None = None, re_alert: dict | None = None) -> dict:
    affected = [a for a in assessments if a["impact"] != "none"]
    stopped = [a for a in assessments if a["impact"] == "stop"]
    max_reduction = max([a["reduction_pct"] for a in assessments] or [0])
    duration = affected[0]["duration_days"] if affected else None
    return {
        "meta": {
            "site_name": cfg["site"]["name"],
            "generated_at": now_cst().isoformat(timespec="seconds"),
            "analysis_date": analysis_date,
            "analysis_generated_at": analysis_generated_at,
            "status": status,
            "status_label": "今日已更新" if status == "new" else "公告未更新，沿用上次分析",
            "source_url": cfg["source"]["list_url"],
            "timezone": cfg["site"]["timezone"],
            "supplier_count": len(assessments),
            "affected_count": len(affected),
            "stopped_count": len(stopped),
            "max_reduction": max_reduction,
            "duration_days": duration,
            "warning_color": notice.get("warning_color"),
            "warning_level": notice.get("warning_level"),
            "prediction": prediction or {},
        },
        "notice": notice,
        "air": air,
        "suppliers": assessments,
        "analysis": analysis,
        "prediction": prediction or {},
        "threshold": threshold or {},
        "re_alert": re_alert or {},
        "sources": {
            "notice": {
                "title": notice.get("title"),
                "publish_date": notice.get("publish_date"),
                "url": notice.get("url"),
                "attachments": notice.get("attachment_files") or [],
            },
            "list_url": cfg["source"]["list_url"],
            "emission_list": {
                "file": reduction_list.FIXED_SOURCE,
                "sheet": "固定源",
                "dir": "2025年12月调整版重污染天气应急减排清单",
                "scope": "企业绩效等级、各预警级别下的工序措施与应急成本",
                "snapshot": reduction_list.snapshot_info(),
            },
            "aqi": {
                "provider": "WAQI (aqicn.org)",
                "station": (air.get("current") or {}).get("station"),
                "time": (air.get("current") or {}).get("time"),
                "url": (air.get("current") or {}).get("url"),
                "note": "分指数(IAQI)按 HJ633-2012 折算为浓度",
            },
            "meteo": {
                "provider": "Open-Meteo",
                "url": "https://open-meteo.com/",
                "variables": "PM2.5 / PM10 / O₃ / NO₂ / SO₂ / CO / 沙尘 / US AQI + 气温、湿度、风速、降水",
                "generated_at": air.get("generated_at"),
            },
            "history": {
                "list_url": cfg["source"]["list_url"],
                "samples": (prediction or {}).get("sample_size"),
                "note": "由栏目历次「启动/终止」公告配对统计，非官方公布的时长",
            },
            "map": {"tiles": "OpenStreetMap", "stations": "WAQI map/bounds"},
            "beijing": beijing_source(air),
        },
        "history": history,
    }


def merge_history(history: list[dict], notice: dict, analysis: dict,
                  analysis_date: str) -> list[dict]:
    entry = {
        "id": notice.get("id"),
        "title": notice.get("title"),
        "url": notice.get("url"),
        "publish_date": notice.get("publish_date"),
        "color": notice.get("warning_color"),
        "level": notice.get("warning_level"),
        "kind_label": notice.get("kind_label"),
        "headline": analysis.get("headline"),
        "analysis_date": analysis_date,
    }
    history = [h for h in history if h.get("id") != entry["id"]]
    history.insert(0, entry)
    return history[:60]


def build_prediction(notice: dict, items: list[dict], air: dict) -> dict:
    """当前这次响应的预计解除时间：历史时长 + 扩散条件 + 已持续天数。"""
    start_dt = None
    if notice.get("effective_time"):
        try:
            start_dt = datetime.fromisoformat(notice["effective_time"])
        except ValueError:
            start_dt = None
    prediction = hist.predict(
        items, start_dt,
        (air.get("dispersion") or {}).get("level"),
        notice.get("warning_level"),
        regional_level=(air.get("region") or {}).get("level"),
        beijing=air.get("beijing"),
    )
    if notice.get("kind") == "terminate":
        # 终止公告：历史样本仍然有效，只是"本次预测"不适用
        prediction["applicable"] = False
        prediction["reason"] = "本次公告为终止响应，无需预测解除时间"
        prediction["predicted_end"] = None
    else:
        prediction["applicable"] = True
    return prediction


def refresh_live(data: dict, items: list[dict], air: dict, cfg: dict) -> bool:
    """公告未变也要重算「预计解除」，否则页面会一直停在启动日 + 固定天数那一天。

    返回 True 表示预测结果变了（文字总结需要一起重写）。
    """
    notice = data.get("notice") or {}
    if (air.get("beijing") or {}).get("available"):
        # 北京官方状态也要随本次公告重算重叠关系（公告未变时只是日期滚动）
        bj_status = beijing.attach_history(air["beijing"], items)
        air = {**air, "beijing": beijing.link(bj_status, notice)}
        data["air"] = air
    old = data.get("prediction") or {}
    prediction = build_prediction(notice, items, air)
    meta = data.setdefault("meta", {})
    suppliers = data.get("suppliers") or []
    moved = ((prediction.get("predicted_end"), prediction.get("predicted_days"))
             != (old.get("predicted_end"), old.get("predicted_days")))
    for key in ("elapsed_days", "overdue", "conditional", "regional_level", "adjust",
                "beijing_bound"):
        if prediction.get(key) != old.get(key):
            moved = True
    if ((prediction.get("beijing_estimate") or {}).get("predicted_end")
            != (old.get("beijing_estimate") or {}).get("predicted_end")):
        moved = True
    data["prediction"] = prediction
    meta["prediction"] = prediction
    meta["prediction_refreshed_at"] = now_cst().isoformat(timespec="seconds")
    changed = [analyze.refresh_duration(a, notice, prediction, cfg) for a in suppliers]
    affected = [a for a in suppliers if a.get("impact") != "none"]
    meta["duration_days"] = affected[0].get("duration_days") if affected else None
    # 规则引擎的总结是确定性的、零成本：每次巡检都重写，保证日期/AQI 不跟卡片矛盾；
    # AI 文案只在预测真的变了（日期、已持续天数、区域/扩散状态）时才换成规则文本。
    engine = (data.get("analysis") or {}).get("engine") or "rules"
    if moved or not engine.startswith("ai:"):
        data["analysis"] = analyze.refresh_analysis(suppliers, notice, air, prediction,
                                                    data.get("analysis"))
        meta["analysis_refreshed_at"] = meta["prediction_refreshed_at"]
    return moved or any(changed)


def fallback_stale(cfg: dict, previous: dict | None, air: dict, reason: str) -> dict:
    """源站不可达时不把巡检算作失败：沿用上次数据重建站点，并标注原因。"""
    if not previous:
        raise SystemExit(f"未抓到任何公告且没有历史数据: {reason}")
    data = copy.deepcopy(previous)
    stamp = now_cst().isoformat(timespec="seconds")
    meta = data.setdefault("meta", {})
    meta["generated_at"] = stamp
    meta["status"] = "unreachable"
    meta["status_label"] = "数据源暂时无法访问，沿用上次分析"
    meta["source_error"] = redact(reason)[:300]
    meta["source_checked_at"] = stamp
    if air:
        prev_bj = ((previous or {}).get("air") or {}).get("beijing") or {}
        bj_status = air.get("beijing") or {}
        if (bj_status.get("available")
                and not (bj_status.get("history") or {}).get("available")
                and (prev_bj.get("history") or {}).get("available")):
            bj_status["history"] = prev_bj["history"]  # 列表没抓到：沿用上次的历史配对
        if bj_status.get("available") and data.get("notice"):
            air["beijing"] = beijing.link(bj_status, data["notice"])
        data["air"] = air
    write_json(LATEST, data)
    build_site.build(data, cfg)
    log(f"沿用 {meta.get('analysis_date')} 的分析结果重建站点（巡检不中断，也不会让 Action 失败）")
    return data


def run(force: bool = False, offline: bool = False) -> dict:
    cfg = settings()
    suppliers_cfg = suppliers()
    state = read_json(STATE, {}) or {}
    history = read_json(HISTORY, []) or []
    previous = read_json(LATEST)
    profiles: dict = {}

    air = {}
    if not offline:
        log("抓取空气质量、气象与监测站（WAQI + Open-Meteo）")
        air = aqi.summarize(aqi.fetch_waqi(cfg), aqi.fetch_open_meteo(cfg),
                            aqi.fetch_waqi_stations(cfg))
        air["region"] = region.summarize(cfg)
        bj = beijing.summarize(cfg)
        if not bj.get("available"):
            # 北京站偶尔不可达：沿用上次状态，总比页面突然空白好
            cached = ((previous or {}).get("air") or {}).get("beijing") or {}
            if cached.get("available"):
                bj = cached
                log("北京官方栏目本次未取到，沿用上次状态")
        air["beijing"] = bj
    elif previous:
        air = previous.get("air", {})

    if offline:
        if not previous:
            raise SystemExit("没有历史数据，--offline 无法运行")
        log("离线模式：使用上次数据重建页面")
        data = copy.deepcopy(previous)
        data["meta"]["generated_at"] = now_cst().isoformat(timespec="seconds")
        data["air"] = air or data.get("air")
        build_site.build(data, cfg)
        return data

    log("抓取「重污染天气信息发布」列表")
    try:
        items = fetch.fetch_notice_list(cfg)
    except fetch.SourceUnavailable as exc:
        log(f"数据源不可达：{exc}")
        return fallback_stale(cfg, previous, air, str(exc))

    target = pick_target(items)
    if not target:
        reason = "列表页没有解析到任何公告"
        log(reason)
        return fallback_stale(cfg, previous, air, reason)

    log(f"最新公告：{target['publish_date']} {target['title']}")

    # 阈值：历史空气质量 + 历次发文日，估计「几个网格点暴雷会触发文件」
    threshold = {}
    if not offline:
        threshold = thresholds.analyze(items, air, cfg)
        if threshold.get("available"):
            log(f"阈值：{threshold['grid_points']} 个网格点中 "
                f"≥{threshold['hot_count']['threshold']} 个日均 AQI≥{threshold['hot_theta']} 时进入警戒"
                f"（召回 {threshold['hot_count']['recall']}）；当前 {threshold['current']['hot_count']} 个，"
                f"状态 {threshold['current']['status']}")

    # 复警概率：未来 72h 污染/气象预报 + 历史阈值
    re_alert = {}
    if not offline:
        re_alert = outlook.compute(air, threshold)
        if re_alert.get("available"):
            log(f"复警概率（72h）：{re_alert['probability']}%（{re_alert['level']}）")

    unchanged = (not force
                 and state.get("last_notice_id") == target["id"]
                 and previous is not None)

    if unchanged and cfg["analysis"].get("reuse_when_unchanged", True):
        log("公告未更新：不重新总结，沿用上一次分析，仅刷新污染数据")
        data = copy.deepcopy(previous)
        data["meta"]["generated_at"] = now_cst().isoformat(timespec="seconds")
        data["meta"]["status"] = "unchanged"
        data["meta"]["status_label"] = "公告未更新，沿用上次分析"
        data["air"] = air or data.get("air")
        if threshold:
            data["threshold"] = threshold
        if re_alert:
            data["re_alert"] = re_alert
        refreshed = refresh_live(data, items, air, cfg)
        if refreshed:
            data["meta"]["status_label"] = "公告未更新，已按最新气象刷新预计解除时间"
            log(f"预计解除已重算：{((data.get('prediction') or {}).get('predicted_end') or '—')[:10]}")
        sources = dict(data.get("sources") or {})
        emission = dict(sources.get("emission_list") or {})
        emission["snapshot"] = reduction_list.snapshot_info()
        sources["emission_list"] = emission
        sources["beijing"] = beijing_source(air)
        data["sources"] = sources
        write_json(LATEST, data)
        build_site.build(data, cfg)
        log(f"沿用分析日期 {data['meta'].get('analysis_date')} 的总结")
        return data

    log("抓取公告详情与附件")
    try:
        detail = collect_notice(target, cfg)
    except Exception as exc:  # noqa: BLE001 - 详情页失败也降级到上次数据
        log(f"公告详情抓取失败：{exc}")
        return fallback_stale(cfg, previous, air, f"公告详情抓取失败：{exc}")
    parsed = parse_notice.parse_notice(detail, detail.get("attachment_text", ""))
    parsed["title_en"] = translate.title_en(parsed)
    log(f"解析结果：{parsed['kind_label']} / {parsed['warning_color']} / {parsed['level_label']} / 生效 {parsed['effective_time']}")

    if (air.get("beijing") or {}).get("available"):
        air["beijing"] = beijing.attach_history(air["beijing"], items)
        air["beijing"] = beijing.link(air["beijing"], parsed)
        if air["beijing"].get("note"):
            log(f"北京官方联动：{air['beijing']['note']}")

    # 历史规律：历次「启动 → 终止」的持续时长 → 本次预计解除时间
    prediction = build_prediction(parsed, items, air)
    if prediction.get("available") and prediction.get("applicable"):
        log(f"预计解除：{prediction['predicted_end'][:10]}（历史中位 {prediction['median_days']} 天，"
            f"样本 {prediction['sample_size']} 次）")

    assessments = []
    profile_map = {}
    for s in suppliers_cfg:
        profile = load_profile(s, profiles)
        if not profile:
            log(f"清单中未找到：{s['name']}")
            continue
        profile_map[s["name"]] = profile

    result = analyze.analyze(parsed, profile_map,
                             [s for s in suppliers_cfg if s["name"] in profile_map],
                             air, rules(), cfg, prediction)
    assessments = result["assessments"]
    for a in assessments:
        profile = profile_map[a["name"]]
        exempt = reduction_list.is_exempt(a["name"], [s for s in suppliers_cfg
                                                     if s["name"] == a["name"]][0].get("alias"))
        a["exempt"] = bool(exempt)
        if exempt:
            a["impact_summary"] += "（注意：该企业同时出现在固定源应急豁免清单中，实际可能豁免）"
            a["exempt_note"] = True

    analysis_date = now_cst().strftime("%Y-%m-%d")
    analysis_generated_at = now_cst().isoformat(timespec="seconds")
    history = merge_history(history, parsed, result["analysis"], analysis_date)

    data = build_payload(parsed, assessments, result["analysis"], air, history,
                         "new", analysis_date, analysis_generated_at, cfg, prediction,
                         threshold, re_alert)

    log("检查邮件通知")
    data["meta"]["notification"] = notify.send_if_needed(data, notify.config())

    write_json(LATEST, data)
    write_json(HISTORY, history)
    write_json(STATE, {
        "last_notice_id": parsed["id"],
        "last_notice_date": parsed.get("publish_date"),
        "last_run_at": now_cst().isoformat(timespec="seconds"),
        "analysis_date": analysis_date,
    })
    build_site.build(data, cfg)
    log("完成 ✅")
    return data


def probe() -> int:
    """检查源站可达性（DNS / 代理 / HTTP），用于排查 CI 抓取失败。

    境外出口访问该站通常只走 IPv6 才通，而 GitHub 托管 runner 没有 IPv6，
    所以建议先配 SOURCE_RELAY（免费 Cloudflare Worker 中继）或 SOURCE_PROXY，
    再用 `python run.py --probe` 验证。
    """
    cfg = settings()
    url = cfg["source"]["list_url"]
    host = urlparse(url).hostname or ""
    proxy = source_proxy(cfg)
    relay = fetch.source_relay(cfg)
    print(f"目标: {url}")
    print(f"中继: {relay or '未配'}")
    print(f"代理: {proxy or '直连'}")
    relayed = fetch.relay_url(url, cfg)
    if relayed != url:
        print(f"请求: {relayed}")
    try:
        infos = socket.getaddrinfo(host, 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
        addrs = sorted({info[4][0] for info in infos})
        print(f"DNS : {', '.join(addrs) or '无记录'}")
    except OSError as exc:
        print(f"DNS : 解析失败 {exc}")
    started = time.time()
    try:
        session = fetch.source_session(cfg)
        html = decode_html(fetch.source_get(
            session, url, cfg, timeout=cfg["source"].get("timeout", 40), tries=1))
        print(f"结果: 成功，{len(html)} 字符，耗时 {time.time() - started:.1f}s")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"结果: 失败 {type(exc).__name__}: {exc}（耗时 {time.time() - started:.1f}s）")
        print("提示: 境外出口访问该站通常不通，建议配 SOURCE_RELAY（免费 Worker 中继）或 SOURCE_PROXY，见 DEPLOY.md")
        return 1


def main() -> None:
    force_utf8_stdout()
    ap = argparse.ArgumentParser(description="德州市重污染天气供应商减产监督台")
    ap.add_argument("--force", action="store_true", help="公告未更新也重新分析")
    ap.add_argument("--offline", action="store_true", help="不联网，仅用上次数据重建页面")
    ap.add_argument("--snapshot", action="store_true",
                    help="从 Excel 重建 data/suppliers_snapshot.json（内置企业数据）")
    ap.add_argument("--notify-test", action="store_true",
                    help="按当前数据发一封测试邮件，验证 SMTP 配置")
    ap.add_argument("--probe", action="store_true",
                    help="检查源站可达性（DNS/代理/HTTP），排查抓取失败")
    args = ap.parse_args()
    if args.snapshot:
        reduction_list.build_snapshot(suppliers(), rules())
        log("快照已重建，可以不再提交 Excel 清单")
        return
    if args.notify_test:
        result = notify.send_test()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.probe:
        raise SystemExit(probe())
    run(force=args.force, offline=args.offline)


if __name__ == "__main__":
    main()
