"""生成静态站点：把 web/ 复制到 docs/，并注入最新数据（JSON + 内联 JS）。"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from .common import ROOT, log, settings, write_json, write_text

WEB_DIR = ROOT / "web"


def build(data: dict, cfg: dict | None = None) -> Path:
    cfg = cfg or settings()
    docs = ROOT / cfg["output"]["docs_dir"]
    docs.mkdir(parents=True, exist_ok=True)

    for name in ("index.html", "style.css", "app-shell.css", "app.js", "favicon.svg"):
        src = WEB_DIR / name
        if src.exists():
            shutil.copyfile(src, docs / name)
        else:
            log(f"缺少前端文件 web/{name}")

    # 给静态资源加版本号，避免浏览器缓存旧样式/脚本
    version = str(int(time.time()))
    index = (docs / "index.html").read_text(encoding="utf-8")
    index = index.replace('href="./style.css"', f'href="./style.css?v={version}"')
    index = index.replace('src="./app.js"', f'src="./app.js?v={version}"')
    index = index.replace('src="./data/latest.js"', f'src="./data/latest.js?v={version}"')
    (docs / "index.html").write_text(index, encoding="utf-8")

    (docs / ".nojekyll").write_text("", encoding="utf-8")

    data_dir = docs / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    write_json(data_dir / "latest.json", data)
    write_text(data_dir / "latest.js",
               "window.__DATA__ = " + json.dumps(data, ensure_ascii=False) + ";\n")

    log(f"站点已生成: {docs}")
    return docs
