"""减排清单规则：把企业名映射到「绩效等级 + 各预警下的管控措施」。

两种数据来源，优先级从高到低：
1. data/suppliers_snapshot.json —— 从 Excel 抽出的企业快照（随仓库内置，部署时不需要上传 Excel）
2. 2025年12月调整版重污染天气应急减排清单/*.xlsx —— 原始清单，存在时可用 `python run.py --snapshot` 重建快照
"""
from __future__ import annotations

import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from .common import CST, REDUCTION_LIST_DIR, ROOT, log, read_json, rules, write_json

FIXED_SOURCE = "2-固定源应急减排措施清单.xlsx"
EXEMPT = "6-固定源应急豁免清单.xlsx"
VEHICLE = "5-重点用车单位清单12.29.xlsx"
WHITELIST = "8-货车白名单12.29.xlsx"
SNAPSHOT = ROOT / "data" / "suppliers_snapshot.json"

COLORS = ("红色预警", "橙色预警", "黄色预警")
LINE_RE = re.compile(r"(\d+)\s*条生产线")


@lru_cache(maxsize=1)
def _snapshot() -> dict:
    data = read_json(SNAPSHOT, None) or {}
    return data.get("companies") or {}


def snapshot_info() -> dict:
    data = read_json(SNAPSHOT, None) or {}
    return {"path": str(SNAPSHOT.relative_to(ROOT)),
            "generated_at": data.get("generated_at"),
            "source": data.get("source"),
            "count": len(data.get("companies") or {})}



@lru_cache(maxsize=4)
def _load_rows(path_str: str) -> tuple[list[dict], dict]:
    import openpyxl

    path = Path(path_str)
    if not path.exists():
        log(f"清单文件不存在: {path.name}")
        return [], {}
    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    ws = wb.worksheets[0]
    it = ws.iter_rows(values_only=True)
    header = [str(h).strip() if h is not None else "" for h in next(it)]
    idx = {h: i for i, h in enumerate(header)}
    rows = []
    for i, r in enumerate(it, start=2):  # 第 1 行是表头
        if not r or all(v is None for v in r):
            continue
        row = {h: r[idx_] for h, idx_ in idx.items() if idx_ < len(r)}
        row["_row"] = i
        rows.append(row)
    wb.close()
    return rows, idx


def _norm(s: str) -> str:
    return re.sub(r"[\s（）()·\-_—]", "", str(s or ""))


def find_company(name: str, aliases: list[str] | None = None,
                 path: Path | None = None) -> list[dict]:
    """返回该企业在固定源清单中的所有行（一条生产线/工序一行）。"""
    path = path or (REDUCTION_LIST_DIR / FIXED_SOURCE)
    rows, _ = _load_rows(str(path))
    keys = [_norm(name)] + [_norm(a) for a in (aliases or [])]
    out = []
    for row in rows:
        company = _norm(row.get("企业名称*", ""))
        if not company:
            continue
        if any(k and (k == company or k in company) for k in keys):
            out.append(row)
    return out


def _num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def profile(name: str, aliases: list[str] | None = None,
            rules_cfg: dict | None = None, path: Path | None = None,
            use_snapshot: bool = True) -> dict | None:
    """企业画像：基础信息 + 三个预警级别下的管控措施与产能压降。

    优先读内置快照（部署无需 Excel）；快照没有或显式 use_snapshot=False 时读 Excel。
    """
    rules_cfg = rules_cfg or rules()
    keys = [_norm(name)] + [_norm(a) for a in (aliases or [])]
    if use_snapshot:
        snap = _snapshot()
        for key, entry in snap.items():
            nk = _norm(key)
            if any(k and (k == nk or k in nk or nk in k) for k in keys):
                return entry

    rows = find_company(name, aliases, path)
    if not rows:
        return None
    head = rows[0]
    factor_map = rules_cfg["measure_factor"]

    performance = str(head.get("绩效等级*") or "其他").strip()
    base = {
        "name": head.get("企业名称*"),
        "credit_code": head.get("统一社会信用代码*"),
        "district": head.get("所属区县*"),
        "town": head.get("所属乡、镇、街道*"),
        "address": head.get("详细地址*"),
        "lon": _num(head.get("经度（°）*")),
        "lat": _num(head.get("纬度（°）*")),
        "industry": head.get("重点行业类型*"),
        "industry_branch": head.get("重点行业分支*"),
        "performance": performance,
        "is_small": head.get("是否为小微涉气企业*"),
        "product": head.get("主要产品*"),
        "capacity": _num(head.get("产能*")),
        "capacity_unit": head.get("产能单位（_/年）*"),
        "zone": head.get("所属工业园区名称*"),
    }

    by_color: dict[str, dict] = {}
    for color in COLORS:
        lines = []
        for row in rows:
            measure = str(row.get(f"{color}_减排措施*") or "").strip()
            way = str(row.get(f"{color}_管控方式*") or "").strip()
            process = str(row.get("生产线、工序*") or "").strip()
            if not measure and not way:
                continue
            lines.append({
                "process": process,
                "measure": measure,
                "way": way,
                "cost_per_day": _num(row.get(f"{color}_应急成本（元/天）")),
                "row": row.get("_row"),
            })
        factors = [factor_map.get(l["way"], 0.0) for l in lines]
        # 企业整体减产：按「各工序产线条数」加权，而不是直接取最大比例。
        # 例：4 条线停产 + 2 条线限产50% → (4×1.0 + 2×0.5) / 6 ≈ 83%，而非 100%。
        weights = []
        for l in lines:
            m = LINE_RE.search(l["process"] or "")
            if m:
                weights.append((int(m.group(1)), factor_map.get(l["way"], 0.0)))
        if weights and sum(w for w, _ in weights) > 0:
            reduction = sum(w * f for w, f in weights) / sum(w for w, _ in weights)
            method = f"按产线加权（{sum(w for w, _ in weights)} 条生产线）"
        else:
            reduction = max(factors) if factors else 0.0
            method = "无可解析产线条数，取最大压降比例"
        by_color[color] = {
            "lines": lines,
            "reduction_pct": round(reduction * 100),
            "reduction_method": method,
            "stopped_processes": sum(1 for l in lines if l["way"] == "停产"),
            "daily_cost": round(sum(l["cost_per_day"] for l in lines)),
            "summary": "；".join(
                f"{l['process']}→{l['way']}" for l in lines if l["way"] not in ("", "正常生产")
            ) or "正常生产",
        }

    base["by_color"] = by_color
    base["row"] = head.get("_row")
    base["source_file"] = FIXED_SOURCE
    return base


@lru_cache(maxsize=2)
def _sheet_text(path_str: str) -> str:
    import openpyxl

    path = Path(path_str)
    if not path.exists():
        return ""
    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    chunks = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            chunks.append(" ".join(str(v) for v in row if v is not None))
    wb.close()
    return "\n".join(chunks)


def is_exempt(name: str, aliases: list[str] | None = None,
              path: Path | None = None) -> bool | None:
    """是否在固定源应急豁免清单中。None 表示清单不可用。"""
    path = path or (REDUCTION_LIST_DIR / EXEMPT)
    if not path.exists():
        return None
    text = _norm(_sheet_text(str(path)))
    keys = [_norm(name)] + [_norm(a) for a in (aliases or [])]
    return any(k and k in text for k in keys)


def list_stats(path: Path | None = None) -> dict:
    path = path or (REDUCTION_LIST_DIR / FIXED_SOURCE)
    rows, _ = _load_rows(str(path))
    return {"rows": len(rows), "file": path.name}


def build_snapshot(suppliers_cfg: list[dict], rules_cfg: dict | None = None) -> dict:
    """从 Excel 抽取在监控企业的画像，写成内置快照；之后部署不再需要 Excel。"""
    rules_cfg = rules_cfg or rules()
    companies = {}
    for s in suppliers_cfg:
        p = profile(s["name"], s.get("alias"), rules_cfg, use_snapshot=False)
        if not p:
            log(f"快照跳过（Excel 中未找到）: {s['name']}")
            continue
        companies[s["name"]] = p
        log(f"快照收录: {s['name']}（清单第 {p.get('row')} 行）")
    data = {
        "generated_at": datetime.now(CST).isoformat(timespec="seconds"),
        "source": FIXED_SOURCE,
        "sheet": "固定源",
        "note": "由 python run.py --snapshot 从官方减排清单生成；可直接提交到仓库，部署时无需 Excel。",
        "companies": companies,
    }
    write_json(SNAPSHOT, data)
    _snapshot.cache_clear()
    log(f"已写入内置快照: {SNAPSHOT}（{len(companies)} 家企业）")
    return data
