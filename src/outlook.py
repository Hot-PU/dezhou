"""近期复警概率：用 Open-Meteo 未来 72 小时的污染与气象预报，结合历史阈值估算。

思路（可在页面上讲清楚，不做黑盒）：
1. 取未来 72 小时逐时 AQI / PM2.5 / 风速 / 降水；
2. 四个可解释因子：
   - 污染峰值相对历史警戒线（城市 3 日 AQI 阈值）的偏离
   - 超过 PM2.5 75 μg/m³ 的小时数（持续累积）
   - 静风小时占比（<2 m/s，扩散差）
   - 累计降水（湿沉降会压住污染）
3. 加权成 0-100 的评分，直接作为概率参考值，并列出每个因子的贡献。
"""
from __future__ import annotations

from datetime import datetime

from .common import CST

WEIGHT = {"peak": 40, "persist": 25, "calm": 20, "dry": 15}


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _ts(row: dict) -> datetime | None:
    try:
        return datetime.fromisoformat(row["t"]).replace(tzinfo=CST)
    except (KeyError, TypeError, ValueError):
        return None


def compute(air: dict, threshold: dict | None = None, horizon: int = 72) -> dict:
    rows = []
    now = datetime.now(CST)
    for r in air.get("hourly") or []:
        t = _ts(r)
        if t and t >= now:
            rows.append(r)
    rows = rows[:horizon]

    if len(rows) < 12:
        return {"available": False, "reason": "预报数据不足"}

    aqi = [r["aqi"] for r in rows if r.get("aqi") is not None]
    pm = [r["pm25"] for r in rows if r.get("pm25") is not None]
    wind = [r["wind"] for r in rows if r.get("wind") is not None]
    rain = [r.get("rain") or 0 for r in rows]

    peak = max(aqi) if aqi else None
    hours_hot = sum(1 for v in pm if v >= 75)
    calm_hours = sum(1 for v in wind if v < 2)
    total_rain = sum(rain)

    # 历史阈值（城市 3 日 AQI），缺省用 135
    line = 135.0
    try:
        line = float(((threshold or {}).get("city_aqi") or {}).get("threshold") or 135)
    except (TypeError, ValueError):
        line = 135.0

    peak_ratio = (peak / line) if (peak and line) else 0.0
    f_peak = _clamp((peak_ratio - 0.75) / 0.6)          # 0.75 倍警戒线以下基本为 0
    f_persist = _clamp(hours_hot / 24)                  # 连续 24 小时超 75 记满
    f_calm = _clamp(calm_hours / max(1, len(wind)))     # 静风占比
    f_dry = _clamp(1 - total_rain / 5)                  # 5mm 以上降水视为明显湿沉降

    parts = {
        "peak": round(WEIGHT["peak"] * f_peak, 1),
        "persist": round(WEIGHT["persist"] * f_persist, 1),
        "calm": round(WEIGHT["calm"] * f_calm, 1),
        "dry": round(WEIGHT["dry"] * f_dry, 1),
    }
    score = _clamp(sum(parts.values()), 3, 95)

    level = "low"
    if score >= 75:
        level = "high"
    elif score >= 50:
        level = "elevated"
    elif score >= 25:
        level = "moderate"

    drivers = [
        {"key": "peak", "value": peak, "ratio": round(peak_ratio, 2), "points": parts["peak"]},
        {"key": "persist", "value": hours_hot, "points": parts["persist"]},
        {"key": "calm", "value": calm_hours, "points": parts["calm"]},
        {"key": "dry", "value": round(total_rain, 1), "points": parts["dry"]},
    ]

    return {
        "available": True,
        "probability": round(score),
        "level": level,
        "horizon_hours": horizon,
        "peak_aqi": round(peak) if peak else None,
        "hot_hours": hours_hot,
        "calm_hours": calm_hours,
        "calm_share": round(f_calm * 100),
        "rain_mm": round(total_rain, 1),
        "alert_line": round(line),
        "drivers": drivers,
        "generated_at": datetime.now(CST).isoformat(timespec="seconds"),
    }
