"""污染与气象数据：WAQI（现况空气质量）+ Open-Meteo（逐时污染与气象预报，免密钥）。"""
from __future__ import annotations

import re
from datetime import datetime

import requests

from .common import CST, env, get_with_retry, http_session, log, settings

OPEN_METEO_AQ = "https://air-quality-api.open-meteo.com/v1/air-quality"
OPEN_METEO_WEATHER = "https://api.open-meteo.com/v1/forecast"


def aqi_level(aqi: float | int | None) -> str:
    if aqi is None:
        return "未知"
    aqi = float(aqi)
    if aqi <= 50:
        return "优"
    if aqi <= 100:
        return "良"
    if aqi <= 150:
        return "轻度污染"
    if aqi <= 200:
        return "中度污染"
    if aqi <= 300:
        return "重度污染"
    return "严重污染"


# WAQI 的 iaqi 是「分指数」，不是浓度。按《环境空气质量指数(AQI)技术规定HJ633-2012》反推浓度。
BREAKPOINTS: dict[str, tuple[list[float], list[float]]] = {
    "pm25": ([0, 50, 100, 150, 200, 300, 400, 500], [0, 35, 75, 115, 150, 250, 350, 500]),
    "pm10": ([0, 50, 100, 150, 200, 300, 400, 500], [0, 50, 150, 250, 350, 420, 500, 600]),
    "o3": ([0, 50, 100, 150, 200, 300, 400, 500], [0, 100, 160, 215, 265, 800, 1000, 1200]),
    "no2": ([0, 50, 100, 150, 200, 300, 400, 500], [0, 40, 80, 180, 280, 565, 750, 940]),
    "so2": ([0, 50, 100, 150, 200, 300, 400, 500], [0, 50, 150, 475, 800, 1600, 2100, 2620]),
    "co": ([0, 50, 100, 150, 200, 300, 400, 500], [0, 2, 4, 14, 24, 36, 48, 60]),
}
POLLUTANT_LABEL = {"pm25": "PM2.5", "pm10": "PM10", "o3": "O₃", "no2": "NO₂",
                   "so2": "SO₂", "co": "CO"}


def iaqi_to_conc(pollutant: str, iaqi: float | int | None) -> float | None:
    if iaqi is None or pollutant not in BREAKPOINTS:
        return None
    iaqi = float(iaqi)
    i_pts, c_pts = BREAKPOINTS[pollutant]
    if iaqi <= 0:
        return 0.0
    if iaqi > i_pts[-1]:
        return None
    for i in range(1, len(i_pts)):
        if iaqi <= i_pts[i]:
            lo_i, hi_i = i_pts[i - 1], i_pts[i]
            lo_c, hi_c = c_pts[i - 1], c_pts[i]
            return round(lo_c + (hi_c - lo_c) * (iaqi - lo_i) / (hi_i - lo_i), 1)
    return None


def _f(value, nd: int = 1):
    try:
        return round(float(value), nd)
    except (TypeError, ValueError):
        return None


def fetch_waqi(cfg: dict | None = None) -> dict:
    cfg = cfg or settings()
    token = env("WAQI_TOKEN") or cfg["aqi"]["waqi_token"]
    city = cfg["aqi"].get("waqi_city", "dezhou")
    out = {"ok": False, "source": "WAQI (aqicn.org)", "city": city}
    try:
        session = http_session(cfg)
        r = get_with_retry(session, f"https://api.waqi.info/feed/{city}/?token={token}", timeout=30)
        payload = r.json()
        if payload.get("status") != "ok":
            out["error"] = str(payload.get("data"))[:200]
            return out
        d = payload["data"]
        iaqi = d.get("iaqi", {})
        raw = {k: _f((iaqi.get(k) or {}).get("v")) for k in
               ("pm25", "pm10", "o3", "no2", "so2", "co")}
        dominant = d.get("dominentpol") or ""
        out.update({
            "ok": True,
            "aqi": _f(d.get("aqi"), 0),
            "aqi_level": aqi_level(d.get("aqi")),
            "station": (d.get("city") or {}).get("name"),
            "dominant": POLLUTANT_LABEL.get(dominant, dominant or None),
            "time": (d.get("time") or {}).get("s"),
            "iaqi": raw,
            # 单位统一为 μg/m³（CO 为 mg/m³），由分指数反推
            "pm25": iaqi_to_conc("pm25", raw["pm25"]),
            "pm10": iaqi_to_conc("pm10", raw["pm10"]),
            "o3": iaqi_to_conc("o3", raw["o3"]),
            "no2": iaqi_to_conc("no2", raw["no2"]),
            "so2": iaqi_to_conc("so2", raw["so2"]),
            "co": iaqi_to_conc("co", raw["co"]),
        })
        log(f"WAQI: AQI={out['aqi']} ({out['aqi_level']}) PM2.5={out['pm25']}")
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"{type(exc).__name__}: {exc}"
        log(f"WAQI 获取失败: {out['error']}")
    return out


def fetch_open_meteo(cfg: dict | None = None) -> dict:
    cfg = cfg or settings()
    lat, lon = cfg["city"]["lat"], cfg["city"]["lon"]
    session = http_session(cfg)
    out = {"ok": False, "source": "Open-Meteo (open-meteo.com)"}

    try:
        r = get_with_retry(session, OPEN_METEO_AQ, timeout=40, params={
            "latitude": lat, "longitude": lon,
            "hourly": ("pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,"
                       "sulphur_dioxide,ozone,dust,us_aqi"),
            "past_days": 1, "forecast_days": 2,
            "timezone": "Asia/Shanghai",
        })
        d = r.json()
        h = d.get("hourly", {})
        out["ok"] = True
        out["hourly"] = {
            "time": h.get("time", []),
            "pm25": h.get("pm2_5", []),
            "pm10": h.get("pm10", []),
            "o3": h.get("ozone", []),
            "no2": h.get("nitrogen_dioxide", []),
            "so2": h.get("sulphur_dioxide", []),
            "co": h.get("carbon_monoxide", []),
            "dust": h.get("dust", []),
            "aqi": h.get("us_aqi", []),
        }
        out["units"] = d.get("hourly_units", {})
        log(f"Open-Meteo 空气质量: {len(out['hourly']['time'])} 个逐时点 × {len(out['hourly']) - 1} 项污染物")
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"{type(exc).__name__}: {exc}"
        log(f"Open-Meteo 空气质量获取失败: {out['error']}")

    try:
        r = get_with_retry(session, OPEN_METEO_WEATHER, timeout=40, params={
            "latitude": lat, "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,weather_code,precipitation",
            "hourly": "wind_speed_10m,wind_direction_10m,precipitation,relative_humidity_2m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max",
            "forecast_days": 7, "timezone": "Asia/Shanghai",
        })
        d = r.json()
        cur = d.get("current", {})
        out["weather"] = {
            "time": cur.get("time"),
            "temperature": _f(cur.get("temperature_2m")),
            "humidity": _f(cur.get("relative_humidity_2m"), 0),
            "wind_speed": _f(cur.get("wind_speed_10m")),
            "wind_dir": _f(cur.get("wind_direction_10m"), 0),
            "precipitation": _f(cur.get("precipitation")),
            "weather_code": cur.get("weather_code"),
        }
        out["daily"] = d.get("daily", {})
        out["hourly_weather"] = d.get("hourly", {})
        out["ok"] = True
        log(f"Open-Meteo 气象: {out['weather']['temperature']}℃ 风速 {out['weather']['wind_speed']} m/s")
    except Exception as exc:  # noqa: BLE001
        out["weather_error"] = f"{type(exc).__name__}: {exc}"
        log(f"Open-Meteo 气象获取失败: {out['weather_error']}")

    ws = (out.get("weather") or {}).get("wind_speed")
    out["dispersion"] = None
    if ws is not None:
        if ws < 2:
            out["dispersion"] = {"level": "差", "note": "风速 <2m/s，污染物易累积，预警大概率维持或升级"}
        elif ws < 4:
            out["dispersion"] = {"level": "一般", "note": "风速 2-4m/s，扩散条件中等"}
        else:
            out["dispersion"] = {"level": "好", "note": "风速 >4m/s，扩散条件转好，应急响应可能提前解除"}
    return out


def fetch_waqi_stations(cfg: dict | None = None) -> list[dict]:
    """WAQI 监测站：取德州市域范围内的站点，用于地图打点。"""
    cfg = cfg or settings()
    token = env("WAQI_TOKEN") or cfg["aqi"]["waqi_token"]
    lat, lon = cfg["city"]["lat"], cfg["city"]["lon"]
    bbox = f"{lat - 0.9:.3f},{lon - 1.2:.3f},{lat + 0.9:.3f},{lon + 1.2:.3f}"
    stations: list[dict] = []
    try:
        session = http_session(cfg)
        r = get_with_retry(session,
                           f"https://api.waqi.info/map/bounds/?latlng={bbox}&token={token}",
                           timeout=30)
        payload = r.json()
        for s in payload.get("data") or []:
            try:
                aqi = int(float(s.get("aqi")))
            except (TypeError, ValueError):
                continue
            full = (s.get("station") or {}).get("name") or ""
            cn = None
            m = re.search(r"[（(]([^）)]+)[）)]", full)
            if m:
                cn = m.group(1)
            stations.append({
                "name": cn or full.split(",")[0],
                "full_name": full,
                "lat": s.get("lat"),
                "lon": s.get("lon"),
                "aqi": aqi,
                "level": aqi_level(aqi),
                "uid": s.get("uid"),
                "time": (s.get("station") or {}).get("time"),
            })
        stations.sort(key=lambda x: x["aqi"], reverse=True)
        log(f"WAQI 监测站: {len(stations)} 个（德州市域及周边）")
    except Exception as exc:  # noqa: BLE001
        log(f"WAQI 监测站获取失败: {type(exc).__name__}: {exc}")
    return stations


def summarize(aqi: dict, meteo: dict, stations: list[dict] | None = None) -> dict:
    """给前端与 AI 用的精简气象/污染摘要。"""
    weather = meteo.get("weather") or {}
    hourly = meteo.get("hourly") or {}
    times = hourly.get("time") or []

    def series(key: str) -> list:
        values = hourly.get(key) or []
        return values + [None] * (len(times) - len(values))

    # 把逐时风速/降水并到同一时间轴上，供复警模型使用
    hw = meteo.get("hourly_weather") or {}
    hw_time = hw.get("time") or []
    wind_map = {t: v for t, v in zip(hw_time, hw.get("wind_speed_10m") or [])}
    rain_map = {t: v for t, v in zip(hw_time, hw.get("precipitation") or [])}
    hum_map = {t: v for t, v in zip(hw_time, hw.get("relative_humidity_2m") or [])}

    rows = []
    for i, t in enumerate(times):
        rows.append({
            "t": t,
            "pm25": series("pm25")[i],
            "pm10": series("pm10")[i],
            "o3": series("o3")[i],
            "no2": series("no2")[i],
            "so2": series("so2")[i],
            "co": series("co")[i],
            "dust": series("dust")[i],
            "aqi": series("aqi")[i],
            "wind": wind_map.get(t),
            "rain": rain_map.get(t),
            "humidity": hum_map.get(t),
        })
    tomorrow = [s["pm25"] for s in rows[-24:] if s["pm25"] is not None]
    return {
        "current": {
            "aqi": aqi.get("aqi"),
            "level": aqi.get("aqi_level"),
            "station": aqi.get("station"),
            "pm25": aqi.get("pm25"),
            "pm10": aqi.get("pm10"),
            "o3": aqi.get("o3"),
            "no2": aqi.get("no2"),
            "so2": aqi.get("so2"),
            "co": aqi.get("co"),
            "dominant": aqi.get("dominant"),
            "time": aqi.get("time"),
            "url": "https://aqicn.org/city/dezhou",
        },
        "weather": weather,
        "dispersion": meteo.get("dispersion"),
        "forecast_pm25_avg_next24h": round(sum(tomorrow) / len(tomorrow)) if tomorrow else None,
        "hourly": rows,
        "daily": meteo.get("daily") or {},
        "stations": stations or [],
        "generated_at": datetime.now(CST).isoformat(timespec="seconds"),
    }
