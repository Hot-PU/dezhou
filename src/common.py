"""公共工具：路径、配置、HTTP、JSON、日志、中文终端输出。"""
from __future__ import annotations

import io
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"

CST = timezone(timedelta(hours=8))

# 减排清单（随仓库内置，作为脚本规则的事实依据）
REDUCTION_LIST_DIR = ROOT / "2025年12月调整版重污染天气应急减排清单"


def force_utf8_stdout() -> None:
    """Windows 控制台默认 GBK，统一成 UTF-8 避免中文报错。"""
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def log(msg: str) -> None:
    stamp = datetime.now(CST).strftime("%H:%M:%S")
    print(f"[{stamp}] {msg}", flush=True)


def load_yaml(name: str) -> dict:
    with open(CONFIG_DIR / name, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def settings() -> dict:
    return load_yaml("settings.yaml")


def suppliers() -> list[dict]:
    return load_yaml("suppliers.yaml")["suppliers"]


def rules() -> dict:
    return load_yaml("analysis_rules.yaml")


def read_json(path: Path, default: Any = None) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def now_cst() -> datetime:
    return datetime.now(CST)


def source_proxy(cfg: dict | None = None) -> str | None:
    """源站专用代理：环境变量 SOURCE_PROXY 优先，其次 settings.yaml 的 source.proxy。

    政府站点在境外通常不可直连（IPv4 被墙、IPv6 才通），CI 里配一个国内出口的
    HTTP 代理即可：SOURCE_PROXY=http://user:pass@1.2.3.4:3128
    """
    cfg = cfg or settings()
    return env("SOURCE_PROXY") or (cfg.get("source") or {}).get("proxy") or None


def source_relay(cfg: dict | None = None) -> str | None:
    """源站中继地址（免费方案：Cloudflare Worker），用于绕过境外直连限制。

    形如 https://xxx.workers.dev/?token=abc，抓取时会再拼上 &url=<原始地址>。
    优先环境变量 SOURCE_RELAY，其次 settings.yaml 的 source.relay。
    """
    cfg = cfg or settings()
    return env("SOURCE_RELAY") or (cfg.get("source") or {}).get("relay") or None


def http_session(cfg: dict | None = None, proxy: str | None = None) -> requests.Session:
    cfg = cfg or settings()
    s = requests.Session()
    s.headers.update(cfg["source"]["headers"])
    if proxy:
        s.proxies.update({"http": proxy, "https": proxy})
    return s


_SECRET_QS_RE = re.compile(r"([?&](?:token|key|secret|password|pwd)=)[^&\s]+", re.I)


def redact(url: str) -> str:
    """日志/站点数据里隐去 token、密码等查询参数，避免密钥泄漏到公开页面。"""
    return _SECRET_QS_RE.sub(r"\1***", str(url))


def get_with_retry(session: requests.Session, url: str, *, timeout: int = 40,
                   tries: int = 3, **kw) -> requests.Response:
    last: Exception | None = None
    for i in range(tries):
        try:
            r = session.get(url, timeout=timeout, **kw)
            r.raise_for_status()
            return r
        except requests.HTTPError as exc:
            # 4xx 是明确的"不存在"，重试没有意义
            if exc.response is not None and 400 <= exc.response.status_code < 500:
                raise
            last = exc
            log(f"  请求失败({i + 1}/{tries}) {redact(url)} -> {type(exc).__name__}: {redact(exc)}")
        except Exception as exc:  # noqa: BLE001 - 网络波动统一重试
            last = exc
            log(f"  请求失败({i + 1}/{tries}) {redact(url)} -> {type(exc).__name__}: {redact(exc)}")
    raise RuntimeError(f"无法获取 {redact(url)}: {redact(last)}")


def decode_html(resp: requests.Response) -> str:
    """政府站点多为 UTF-8，个别老页面是 GBK，按内容自适应。"""
    if resp.encoding and resp.encoding.lower() not in ("iso-8859-1", "ascii"):
        text = resp.text
    else:
        resp.encoding = resp.apparent_encoding or "utf-8"
        text = resp.text
    if "\ufffd" in text[:2000]:
        try:
            text = resp.content.decode("gb18030", errors="replace")
        except Exception:  # noqa: BLE001
            pass
    return text


def env(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)
