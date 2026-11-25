"""抓取德州市生态环境局「重污染天气信息发布」栏目：列表 → 详情 → 附件原文。"""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

from .common import (ROOT, decode_html, get_with_retry, http_session, log,
                     redact, settings, source_proxy, source_relay)


class SourceUnavailable(RuntimeError):
    """源站不可达，或列表页没有可解析的公告（境外出口访问政府站点时常见）。"""


def relay_url(url: str, cfg: dict) -> str:
    """配了 SOURCE_RELAY（如 Cloudflare Worker）时，把请求地址改写为中继地址。"""
    base = source_relay(cfg)
    if not base:
        return url
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}url={quote(url, safe='')}"


def source_session(cfg: dict):
    """访问源站用会话：优先走中继，其次走 SOURCE_PROXY / source.proxy 代理。"""
    proxy = None if source_relay(cfg) else source_proxy(cfg)
    return http_session(cfg, proxy=proxy)


def source_get(session, url: str, cfg: dict, **kw):
    """按当前配置（中继/代理）请求源站地址。"""
    return get_with_retry(session, relay_url(url, cfg), **kw)


CONTENT_RE = re.compile(
    r'<a\s+href=(?P<href>[^\s>]+?/content\.html)[^>]*?\btitle=(?P<title>[^>]+?)>',
    re.I,
)
DATE_AFTER_RE = re.compile(r'align=right>\s*(\d{4}-\d{2}-\d{2})\s*<', re.I)
DATE_NEAR_RE = re.compile(r'(\d{4}-\d{2}-\d{2})')


def _clean(title: str) -> str:
    title = re.sub(r"<[^>]+>", "", title)
    return re.sub(r"\s+", " ", title).strip().strip('"\'')


def parse_list(html: str, page_url: str) -> list[dict]:
    """从栏目列表页提取公告（标题 / 链接 / 发布日期）。"""
    items: list[dict] = []
    seen: set[str] = set()
    for m in CONTENT_RE.finditer(html):
        href = m.group("href").strip().strip('"\'')
        url = urljoin(page_url, href)
        if url in seen:
            continue
        seen.add(url)
        title = _clean(m.group("title"))
        # 日期取锚点之后最近的 YYYY-MM-DD
        tail = html[m.end(): m.end() + 800]
        dm = DATE_NEAR_RE.search(tail)
        date = dm.group(1) if dm else ""
        doc_id = Path(urlparse(url).path).parent.name
        items.append({"id": doc_id, "title": title, "url": url, "publish_date": date})
    return items


def fetch_notice_list(cfg: dict | None = None) -> list[dict]:
    cfg = cfg or settings()
    src = cfg["source"]
    session = source_session(cfg)
    all_items: list[dict] = []
    seen: set[str] = set()
    for page in range(0, max(1, int(src.get("max_pages", 1)))):
        url = src["list_url"] if page == 0 else src["list_url"].replace(
            "index.html", f"index_{page}.html")
        try:
            html = decode_html(source_get(session, url, cfg, timeout=src.get("timeout", 40)))
        except Exception as exc:  # noqa: BLE001
            log(f"列表页第 {page + 1} 页抓取失败，停止翻页: {exc}")
            if page == 0:
                raise SourceUnavailable(f"无法获取列表页 {url}: {redact(exc)}") from exc
            break
        items = parse_list(html, url)
        fresh = [i for i in items if i["url"] not in seen]
        if not fresh:
            break
        seen.update(i["url"] for i in fresh)
        all_items.extend(fresh)
        log(f"列表第 {page + 1} 页: {len(fresh)} 条")
    all_items.sort(key=lambda i: (i["publish_date"], i["id"]), reverse=True)
    return all_items


ATTACH_RE = re.compile(
    r'<a[^>]+href="(?P<href>[^"]+?\.(?:docx?|pdf|wps))"[^>]*>(?P<name>[^<]*)</a>', re.I)
TITLE_RE = re.compile(r'id="con_t"[^>]*>(?P<t>.*?)</div>', re.S | re.I)
TIME_RE = re.compile(r'id="con_time"[^>]*>(?P<t>.*?)</span>', re.S | re.I)
BODY_RE = re.compile(r'id="con_con"[^>]*>(?P<b>.*?)</div>', re.S | re.I)


def _strip_tags(html: str) -> str:
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    html = re.sub(r"</p>", "\n", html, flags=re.I)
    html = re.sub(r"<[^>]+>", "", html)
    html = html.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return re.sub(r"\n{3,}", "\n\n", html).strip()


def fetch_notice_detail(item: dict, cfg: dict | None = None) -> dict:
    """抓取公告详情页，返回标题、发布时间、正文、附件地址。"""
    cfg = cfg or settings()
    session = source_session(cfg)
    html = decode_html(source_get(session, item["url"], cfg,
                                  timeout=cfg["source"].get("timeout", 40)))

    title = item["title"]
    m = TITLE_RE.search(html)
    if m:
        title = _clean(_strip_tags(m.group("t"))) or title

    publish = item.get("publish_date", "")
    m = TIME_RE.search(html)
    if m:
        dm = DATE_NEAR_RE.search(_strip_tags(m.group("t")))
        publish = dm.group(1) if dm else publish

    body = ""
    m = BODY_RE.search(html)
    if m:
        body = _strip_tags(m.group("b"))

    attachments = []
    for a in ATTACH_RE.finditer(html):
        href = a.group("href").strip()
        url = urljoin(item["url"], href)
        name = _clean(a.group("name")) or Path(urlparse(url).path).name
        attachments.append({"name": name, "url": url})

    return {
        "id": item["id"],
        "title": title,
        "url": item["url"],
        "publish_date": publish,
        "body": body,
        "attachments": attachments,
    }


def download_attachment(notice: dict, att: dict, raw_dir: Path | None = None,
                        cfg: dict | None = None) -> Path:
    cfg = cfg or settings()
    raw_dir = raw_dir or (ROOT / "data" / "raw" / notice["id"])
    raw_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(urlparse(att["url"]).path).suffix.lower() or ".bin"
    # 文件名里带 content_id，避免不同公告同名附件互相覆盖
    safe = re.sub(r"[\\/:*?\"<>|\s]+", "_", att["name"])
    if not safe.lower().endswith(suffix):
        safe += suffix
    dest = raw_dir / safe
    if dest.exists() and dest.stat().st_size > 1024:
        log(f"  附件已存在，跳过下载: {dest.name}")
        return dest
    session = source_session(cfg)
    resp = source_get(session, att["url"], cfg, timeout=90)
    dest.write_bytes(resp.content)
    log(f"  附件已下载: {dest.name} ({len(resp.content) / 1024:.0f} KB)")
    return dest


def extract_docx_text(path: Path) -> str:
    """提取 .docx 正文（段落 + 表格），供 AI 与规则引擎共用。"""
    if path.suffix.lower() == ".docx":
        try:
            import docx  # python-docx
        except ImportError:
            log("未安装 python-docx，无法解析附件正文")
            return ""
        doc = docx.Document(str(path))
        parts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells]
                if any(cells):
                    parts.append(" | ".join(cells))
        return "\n".join(parts)
    if path.suffix.lower() == ".doc":
        # 老式 .doc（OLE 复合文档）：python-docx 打不开，正文以 UTF-16LE 存放，
        # 这里做一次启发式抽取，只保留像公文句子的片段，够用于识别终止时间/级别。
        raw = path.read_bytes()
        text = raw.decode("utf-16-le", errors="ignore")
        runs = re.findall(r"[\u4e00-\u9fa5][\u4e00-\u9fa5A-Za-z0-9，。、；：（）《》〔〕%\-年月日时]{3,}", text)
        keep = [r for r in runs if re.search(r"(重污染|应急|预警|通知|响应|解除|终止|启动|德州市|\d{4}年)", r)]
        seen, out = set(), []
        for r in keep:
            if r not in seen:
                seen.add(r)
                out.append(r)
        return "\n".join(out)
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            return ""
        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages).strip()
    return ""
