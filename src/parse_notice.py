"""公告规则解析：识别公告类型、预警颜色、响应级别、生效时间与强制性措施段落。"""
from __future__ import annotations

import re
from datetime import datetime

from .common import CST

COLOR_BY_LEVEL = {"Ⅰ": "红色预警", "Ⅱ": "橙色预警", "Ⅲ": "黄色预警", "Ⅳ": "蓝色预警"}
LEVEL_BY_COLOR = {v: k for k, v in COLOR_BY_LEVEL.items()}
CN_NUM = {"一": "Ⅰ", "二": "Ⅱ", "三": "Ⅲ", "四": "Ⅳ", "1": "Ⅰ", "2": "Ⅱ", "3": "Ⅲ", "4": "Ⅳ"}

DATETIME_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2})[时点]")
PUBLISH_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2})[时点]\s*发布")


def _dt(m: re.Match) -> str:
    y, mo, d, h = (int(x) for x in m.groups())
    return datetime(y, mo, d, h, tzinfo=CST).isoformat()


def parse_notice(notice: dict, attachment_text: str = "") -> dict:
    title = notice.get("title", "")
    text = f"{title}\n{notice.get('body','')}\n{attachment_text}"

    # 公告类型
    if "终止" in title or "解除" in title:
        kind = "terminate"
    elif "启动" in title:
        kind = "startup"
    elif "调整" in title or "升级" in title:
        kind = "adjust"
    else:
        kind = "other"

    # 预警颜色 / 响应级别
    color = ""
    for c in COLOR_BY_LEVEL.values():
        if c in title:
            color = c
            break
    if not color:
        m = re.search(r"(红色|橙色|黄色|蓝色)预警", text)
        if m:
            color = m.group(1) + "预警"

    level = ""
    m = re.search(r"([ⅠⅡⅢⅣ])\s*级", title) or re.search(r"([ⅠⅡⅢⅣ])\s*级", text)
    if m:
        level = m.group(1)
    elif color:
        level = LEVEL_BY_COLOR.get(color, "")
    if level and not color and level in COLOR_BY_LEVEL:
        color = COLOR_BY_LEVEL[level]

    # 生效时间：优先「X年X月X日X时启动…」，其次「…发布…」，最后取正文首个时间
    # 公告里常见「2026年11月2日12时发布…，11月3日12时启动…」，启动时间可能省略年份
    effective = ""
    default_year = None
    ym = re.search(r"(\d{4})年", text)
    if ym:
        default_year = int(ym.group(1))
    loose = re.compile(r"(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日\s*(\d{1,2})[时点]\s*(启动|发布)")
    for cand in loose.finditer(text):
        if cand.group(5) != "启动":
            continue
        year = int(cand.group(1)) if cand.group(1) else default_year
        if not year:
            continue
        effective = datetime(year, int(cand.group(2)), int(cand.group(3)),
                             int(cand.group(4)), tzinfo=CST).isoformat()
        break
    if not effective:
        m = PUBLISH_RE.search(text) or DATETIME_RE.search(text)
        if m:
            effective = _dt(m)
    if not effective and notice.get("publish_date"):
        effective = datetime.fromisoformat(notice["publish_date"]).replace(
            hour=0, tzinfo=CST).isoformat()

    # 强制性措施原文（截取"强制性减排措施"到"其他减排措施"/末尾）
    measures: dict[str, str] = {}
    seg = ""
    m = re.search(r"强制性(?:污染)?减排措施(.+?)(?=四、|其他减排措施|$)", text, re.S)
    if m:
        seg = m.group(1)
    for key, pat in (("工业企业", r"[（(]一[）)][^\n]*?工业(.+?)(?=[（(]二[）)]|$)"),
                     ("扬尘源", r"[（(]二[）)][^\n]*?扬尘(.+?)(?=[（(]三[）)]|$)"),
                     ("移动源", r"[（(]三[）)][^\n]*?移动源(.+?)(?=[（(]四[）)]|$)")):
        mm = re.search(pat, seg, re.S) if seg else None
        if mm:
            measures[key] = re.sub(r"\s+", " ", mm.group(1)).strip()

    if kind == "terminate" and not color:
        # 终止公告正文常写「解除橙色预警并终止Ⅱ级应急响应」，保留它解除的是哪一级
        color, level = "", ""

    return {
        **notice,
        "kind": kind,
        "kind_label": {"startup": "启动响应", "terminate": "终止响应",
                       "adjust": "调整响应", "other": "通知"}.get(kind, "通知"),
        "warning_color": color,
        "warning_level": level,
        "level_label": f"{level}级" if level else "",
        "effective_time": effective,
        "level_text": (f"{color}（{level}级应急响应）" if color and level
                       else (color or (f"{level}级应急响应" if level else "未识别级别"))),
        "measures": measures,
        "attachment_text": attachment_text,
    }
