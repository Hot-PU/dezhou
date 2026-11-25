"""公告标题英译（规则法，无外部依赖）。

德州市生态环境局的公告标题高度模板化，例如：
  关于启动重污染天气Ⅱ级应急响应的通知-重污染应急〔2026〕23号
  关于终止重污染天气应急响应的通知
  关于升级重污染天气预警并启动Ⅲ级应急响应的通知
用关键词组合即可得到可用的英文标题；无法识别时返回空串，由调用方回退中文。
"""
from __future__ import annotations

import re

CN_NUM = {"Ⅰ": "I", "Ⅱ": "II", "Ⅲ": "III", "Ⅳ": "IV",
          "一": "I", "二": "II", "三": "III", "四": "IV"}
COLOR = {"红色": "Red", "橙色": "Orange", "黄色": "Yellow", "蓝色": "Blue"}
ACTION = {"启动": "Launching", "终止": "Terminating", "解除": "Lifting",
          "升级": "Upgrading", "调整": "Adjusting", "印发": "Issuing", "发布": "Publishing"}


def _clean(title: str) -> str:
    """去掉文件号与副标题，只保留正文标题。"""
    t = re.sub(r"\s*[-—]\s*重污染应急〔\d{4}〕\d+号.*$", "", title or "")
    t = re.sub(r"[-\s]*重污染应急〔\d{4}〕\d+号.*$", "", t)
    return t.strip()


def translate(title: str) -> str:
    t = _clean(title)
    if not t:
        return ""

    level = ""
    m = re.search(r"([ⅠⅡⅢⅣ一二三四])\s*级", t)
    if m:
        level = "Level " + CN_NUM.get(m.group(1), "")

    color = ""
    for cn, en in COLOR.items():
        if cn + "预警" in t:
            color = en + " Alert"
            break

    actions = [v for k, v in ACTION.items() if k in t]
    if not actions:
        return ""

    # 终止/解除类公告不谈级别
    terminating = any(k in t for k in ("终止", "解除"))
    if terminating:
        if "终止" in t:
            return "Notice on Terminating the Heavy-Pollution Emergency Response"
        return "Notice on Lifting the Heavy-Pollution Alert"

    if "升级" in t:
        parts = ["Notice on Upgrading the Alert"]
        if level:
            parts.append("and Launching the " + level + " Emergency Response")
        return " ".join(parts)

    subject = "Heavy-Pollution Emergency Response"
    if "预警" in t and "应急响应" not in t:
        subject = "Heavy-Pollution Alert"

    core = " ".join(x for x in [level, subject] if x)
    if color and color.replace(" Alert", "") not in core:
        core = f"{core} ({color})" if core else color
    return f"Notice on {actions[-1]} the {core}"


def title_en(notice: dict) -> str:
    return translate(notice.get("title") or "")
