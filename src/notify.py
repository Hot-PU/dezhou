"""邮件通知：把每日研判结果按模板发到采购/供应链负责人邮箱（英文正文）。

- SMTP 参数在 config/notifications.yaml，密码走环境变量（GitHub Secrets）
- 支持 ssl / starttls / 明文三种连接方式
- 只在「启动/升级」与「终止」两类公告时发信；同一条公告只发一次
  （去重记录 data/notify_log.json，随仓库提交，CI 多次运行不会重复打扰）
- 模板：startup（启动/升级）、terminate（终止）、test（连通性测试）
"""
from __future__ import annotations

import html
import os
import smtplib
import ssl
from datetime import datetime
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import format_datetime, formataddr, make_msgid

from .common import CST, ROOT, load_yaml, log, read_json, write_json
from .translate import translate as translate_title

LOG_PATH = ROOT / "data" / "notify_log.json"
CFG_NAME = "notifications.yaml"

# 这些域名的 SPF/DMARC 都是“谁都不许发”（example.com 是 v=spf1 -all + p=reject），
# 当真发件人用会被收件方直接拒收/隔离，所以自动换成 SMTP 账号地址。
PLACEHOLDER_DOMAINS = {"example.com", "example.org", "example.net", "localhost",
                      "localhost.localdomain", "test.com"}


def config() -> dict:
    """读取配置；允许用环境变量覆盖（GitHub Actions Secrets 里配完就能用）。"""
    try:
        cfg = (load_yaml(CFG_NAME).get("email") or {})
    except FileNotFoundError:
        cfg = {}
    env = os.environ
    if env.get("SMTP_HOST"):
        cfg["smtp_host"] = env["SMTP_HOST"]
    if env.get("SMTP_PORT"):
        cfg["smtp_port"] = int(env["SMTP_PORT"])
    if env.get("SMTP_SECURITY"):
        cfg["smtp_security"] = env["SMTP_SECURITY"]
    if env.get("SMTP_USER"):
        cfg["username"] = env["SMTP_USER"]
    if env.get("SMTP_FROM"):
        cfg["from"] = env["SMTP_FROM"]
    if env.get("SMTP_TO"):
        cfg["to"] = [x.strip() for x in env["SMTP_TO"].replace(";", ",").split(",") if x.strip()]
    if env.get("EMAIL_ENABLED"):
        cfg["enabled"] = env["EMAIL_ENABLED"].lower() in ("1", "true", "yes", "on")
    if env.get("EMAIL_DRY_RUN"):
        cfg["dry_run"] = env["EMAIL_DRY_RUN"].lower() in ("1", "true", "yes", "on")
    return cfg


def _now() -> str:
    return datetime.now(CST).isoformat(timespec="seconds")


def _fmt(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        return datetime.fromisoformat(iso).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return str(iso)[:16].replace("T", " ")


def _should_send(cfg: dict, kind: str, status: str) -> bool:
    """只对「启动/升级」和「终止」发信；其余（含未更新）一律静默。"""
    if not cfg.get("enabled"):
        return False
    if status == "unchanged":
        return bool((cfg.get("send_on") or {}).get("unchanged"))
    if kind == "terminate":
        return bool((cfg.get("send_on") or {}).get("terminate"))
    if kind in ("startup", "adjust"):
        return bool((cfg.get("send_on") or {}).get("startup"))
    return False


AQI_EN = {"优": "Good", "良": "Moderate", "轻度污染": "Light pollution",
          "中度污染": "Heavy pollution", "重度污染": "Severe pollution", "严重污染": "Hazardous"}


def _context(data: dict) -> dict:
    """从站点数据里抽取邮件需要的字段，避免模板里堆逻辑。"""
    notice = data.get("notice") or {}
    meta = data.get("meta") or {}
    suppliers = data.get("suppliers") or []
    pred = data.get("prediction") or {}
    thr = data.get("threshold") or {}
    air = (data.get("air") or {}).get("current") or {}
    sources = data.get("sources") or {}
    # 邮件统一用英文版分析（页面默认语言之外单独取）
    analysis = data.get("analysis") or {}
    analysis = {**analysis, **((analysis.get("i18n") or {}).get("en") or {})}

    affected = [s for s in suppliers if s.get("impact") and s["impact"] != "none"]
    rows = []
    for s in affected:
        process = " / ".join(
            l.get("process", "") + (f" ({l.get('way')})" if l.get("way") else "")
            for l in (s.get("affected_lines") or [])
        ) or "—"
        rows.append({
            "name": s.get("name", ""),
            "district": s.get("district") or "",
            "impact": s.get("impact_label") or "",
            "reduction": s.get("reduction_pct") or 0,
            "process": process,
            "duration": s.get("duration_days"),
            "window": f"{_fmt(s.get('window_start'))} → {_fmt(s.get('window_end'))}",
            "cost": s.get("daily_cost") or 0,
        })

    kind = notice.get("kind")
    label = {
        "terminate": "Response terminated",
        "adjust": "Response escalated",
        "startup": "Response started",
    }.get(kind, "Notice")

    title_zh = notice.get("title") or ""
    ctx = {
        "kind": kind,
        "label": label,
        "title": notice.get("title_en") or translate_title(title_zh) or title_zh,
        "title_zh": title_zh,
        "publish_date": notice.get("publish_date") or "",
        "effective": _fmt(notice.get("effective_time")),
        "color": (notice.get("warning_color") or "—").replace("预警", " alert")
                 .replace("红色", "Red").replace("橙色", "Orange").replace("黄色", "Yellow"),
        "level": notice.get("level_label") or "—",
        "notice_url": notice.get("url") or "",
        "list_url": sources.get("list_url") or "",
        "analysis_date": meta.get("analysis_date") or "",
        "generated_at": _fmt(meta.get("generated_at")),
        "headline": analysis.get("headline") or "",
        "actions": analysis.get("counter_hoarding") or [],
        "affected": rows,
        "affected_count": len(rows),
        "supplier_count": meta.get("supplier_count") or len(suppliers),
        "max_reduction": meta.get("max_reduction") or 0,
        "duration": meta.get("duration_days"),
        "predicted_end": _fmt(pred.get("predicted_end")) if pred.get("applicable") is not False else "—",
        "threshold": {
            "current": (thr.get("current") or {}).get("hot_count"),
            "line": (thr.get("hot_count") or {}).get("threshold"),
            "max": (thr.get("hot_count") or {}).get("max"),
            "status": (thr.get("current") or {}).get("status"),
        },
        "aqi": air.get("aqi"),
        "aqi_level": AQI_EN.get(air.get("level") or "", air.get("level") or ""),
        "pm25": air.get("pm25"),
    }
    ctx["duration_text"] = f"{ctx['duration']} days" if ctx["duration"] not in (None, 0) else "—"
    ctx["reduction_text"] = f"{ctx['max_reduction']}%" if rows else "—"
    ctx["thr_current"] = ctx["threshold"]["current"] if ctx["threshold"]["current"] is not None else "—"
    ctx["thr_max"] = ctx["threshold"]["max"] or 9
    ctx["thr_line"] = ctx["threshold"]["line"] if ctx["threshold"]["line"] is not None else "—"
    return ctx


def _subject(ctx: dict, cfg: dict) -> str:
    prefix = (cfg.get("subject_prefix") or "[Supplier Watch]").strip()
    if ctx["kind"] == "terminate":
        core = f"{ctx['color']} lifted — response terminated in Dezhou"
    elif ctx["kind"] == "adjust":
        core = f"{ctx['color']} escalated — {ctx['level']} response in Dezhou"
    else:
        names = ", ".join(r["name"] for r in ctx["affected"]) or "no affected supplier"
        core = f"{ctx['color']} {ctx['level']} response started — {names} cut {ctx['reduction_text']}"
    return f"{prefix} {core}".strip()


TEXT_TMPL = """Dezhou heavy-pollution supplier monitoring

{label}: {title}
Official title (zh): {title_zh}
Alert level: {color} ({level})
Published: {publish_date}   Effective: {effective}
Affected suppliers: {affected_count} / {supplier_count}   Largest cut: {reduction_text}   Duration: {duration_text}

ASSESSMENT
{headline}

AFFECTED SUPPLIERS
{rows_block}

RECOMMENDED ACTIONS
{actions_block}

AIR QUALITY
AQI {aqi} ({aqi_level}), PM2.5 {pm25} ug/m3
Threshold: {thr_current}/{thr_max} grid points above AQI 150 (alert line {thr_line})

{links_block}
--
Automated message. Production restrictions follow the official notice and the fixed-source reduction list.
Generated {generated_at}
"""


def _links_text(ctx: dict, cfg: dict) -> str:
    """纯文本部分的链接段；include_links: false 时只留来源说明，不给 URL。"""
    if cfg.get("include_links", True):
        return f"LINKS\nNotice: {ctx['notice_url']}\nNotice column (for the termination notice): {ctx['list_url']}\n"
    return 'SOURCE\nDezhou EPB "Heavy pollution weather" column (link removed to pass mail gateways).\n'


def _links_html(ctx: dict, cfg: dict) -> str:
    """HTML 部分的链接按钮；关闭时换成一行纯文字来源。"""
    if cfg.get("include_links", True):
        return (
            f'<a href="{ctx["notice_url"]}" style="display:inline-block;background:#0066cc;color:#fff;'
            'text-decoration:none;font-size:13px;padding:9px 16px;border-radius:9px;">Read the notice</a>'
            f'<a href="{ctx["list_url"]}" style="display:inline-block;margin-left:8px;color:#0066cc;'
            'text-decoration:none;font-size:13px;padding:9px 6px;">Watch for termination &rarr;</a>'
        )
    return ('<div style="font-size:12px;color:#6e6e73;">Source: Dezhou EPB '
            '&ldquo;Heavy pollution weather&rdquo; column (link removed to pass mail gateways).</div>')


def _text(ctx: dict, cfg: dict) -> str:
    rows = "\n".join(
        f"- {r['name']} ({r['district']}): {r['impact']}, cut {r['reduction']}%; "
        f"{r['process']}; window {r['window']}; listed cost {r['cost']:,} CNY/day"
        for r in ctx["affected"]
    ) or "- none"
    actions = "\n".join(f"{i + 1}. {a}" for i, a in enumerate(ctx["actions"][:5])) or "1. Keep monitoring the notice column."
    return TEXT_TMPL.format(**ctx, rows_block=rows, actions_block=actions,
                            links_block=_links_text(ctx, cfg))


HTML_TMPL = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8" /></head>
<body style="margin:0;padding:0;background:#fafafa;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#fafafa;padding:24px 12px;">
<tr><td align="center">
<table role="presentation" width="640" cellpadding="0" cellspacing="0"
       style="max-width:640px;background:#fff;border:1px solid #e8e8ed;border-radius:16px;
              font-family:-apple-system,'Segoe UI','Helvetica Neue',Arial,sans-serif;color:#111114;">
  <tr><td style="padding:22px 26px 0;">
    <div style="font-size:11px;letter-spacing:2px;color:#8e8e93;">DEZHOU · SUPPLIER IMPACT ALERT</div>
    <div style="font-size:20px;font-weight:600;margin-top:6px;line-height:1.45;">{title}</div>
    <div style="font-size:11.5px;color:#8e8e93;margin-top:4px;">{title_zh}</div>
    <div style="margin-top:10px;font-size:12.5px;color:#6e6e73;">
      {color} ({level}) · {label} · published {publish_date} · effective {effective}
    </div>
  </td></tr>

  <tr><td style="padding:18px 26px 0;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td style="width:25%;padding:10px 0;border-top:1px solid #f1f1f4;">
          <div style="font-size:11px;color:#8e8e93;">Affected suppliers</div>
          <div style="font-size:19px;font-weight:600;">{affected_count}<span style="font-size:12px;color:#8e8e93;"> / {supplier_count}</span></div>
        </td>
        <td style="width:25%;padding:10px 0;border-top:1px solid #f1f1f4;">
          <div style="font-size:11px;color:#8e8e93;">Largest cut</div>
          <div style="font-size:19px;font-weight:600;">{reduction_text}</div>
        </td>
        <td style="width:25%;padding:10px 0;border-top:1px solid #f1f1f4;">
          <div style="font-size:11px;color:#8e8e93;">Duration</div>
          <div style="font-size:19px;font-weight:600;">{duration_text}</div>
        </td>
        <td style="width:25%;padding:10px 0;border-top:1px solid #f1f1f4;">
          <div style="font-size:11px;color:#8e8e93;">Expected end</div>
          <div style="font-size:19px;font-weight:600;">{predicted_end}</div>
        </td>
      </tr>
    </table>
  </td></tr>

  <tr><td style="padding:18px 26px 0;">
    <div style="font-size:11px;letter-spacing:1px;color:#8e8e93;">ASSESSMENT</div>
    <p style="margin:8px 0 0;font-size:14px;line-height:1.7;color:#3a3a3c;">{headline}</p>
  </td></tr>

  <tr><td style="padding:18px 26px 0;">
    <div style="font-size:11px;letter-spacing:1px;color:#8e8e93;">AFFECTED SUPPLIERS</div>
    {rows_html}
  </td></tr>

  <tr><td style="padding:18px 26px 0;">
    <div style="font-size:11px;letter-spacing:1px;color:#8e8e93;">RECOMMENDED ACTIONS</div>
    {actions_html}
  </td></tr>

  <tr><td style="padding:18px 26px 0;">
    <div style="font-size:12.5px;color:#3a3a3c;line-height:1.9;
                background:#f7f7f9;border-radius:10px;padding:12px 14px;">
      Air quality: AQI {aqi} ({aqi_level}), PM2.5 {pm25} ug/m3<br/>
      Threshold: {thr_current}/{thr_max} grid points above AQI 150 (alert line {thr_line})
    </div>
  </td></tr>

  <tr><td style="padding:18px 26px 26px;">
    {links_html}
    <div style="margin-top:16px;font-size:11px;color:#8e8e93;line-height:1.8;">
      Automated message. Restrictions follow the official notice and the fixed-source reduction list.<br/>
      Generated {generated_at}
    </div>
  </td></tr>
</table>
</td></tr></table>
</body></html>
"""


def _html(ctx: dict, cfg: dict) -> str:
    rows_html = "".join(
        f"""<div style="padding:12px 0;border-top:1px solid #f1f1f4;">
              <div style="font-size:13.5px;font-weight:600;">{html.escape(r['name'])}
                <span style="font-weight:400;color:#8e8e93;font-size:11.5px;">{html.escape(r['district'])}</span></div>
              <div style="font-size:12.5px;color:#3a3a3c;margin-top:4px;">
                {html.escape(r['impact'])} · cut {r['reduction']}% · {html.escape(r['process'])}
              </div>
              <div style="font-size:11.5px;color:#8e8e93;margin-top:2px;">
                window {r['window']} · listed cost {r['cost']:,} CNY/day
              </div>
            </div>"""
        for r in ctx["affected"]
    ) or '<p style="margin:8px 0 0;font-size:13px;color:#8e8e93;">No monitored supplier is affected; production continues as normal.</p>'

    actions_html = "".join(
        f"""<div style="padding:9px 0;border-top:1px solid #f1f1f4;font-size:12.5px;color:#3a3a3c;">
              <span style="color:#8e8e93;margin-right:8px;">{i + 1}</span>{html.escape(a)}</div>"""
        for i, a in enumerate(ctx["actions"][:5])
    ) or '<p style="margin:8px 0 0;font-size:13px;color:#8e8e93;">Keep monitoring the notice column.</p>'

    return HTML_TMPL.format(**ctx, rows_html=rows_html, actions_html=actions_html,
                             links_html=_links_html(ctx, cfg))


def _smtp_send(cfg: dict, subject: str, text: str, html_body: str) -> None:
    host = cfg.get("smtp_host") or ""
    port = int(cfg.get("smtp_port") or 465)
    security = (cfg.get("smtp_security") or "ssl").lower()
    username = cfg.get("username") or ""
    password = os.environ.get(cfg.get("password_env") or "SMTP_PASSWORD", "")

    if not host or not cfg.get("to"):
        raise RuntimeError("SMTP is not configured: set smtp_host / to in config/notifications.yaml")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(subject, "utf-8")
    from_name, from_addr = _effective_from(cfg)
    msg["From"] = formataddr((from_name, from_addr))
    msg["To"] = ", ".join(cfg["to"])
    msg["Reply-To"] = from_addr
    msg["Message-ID"] = make_msgid(domain=from_addr.split("@")[-1] or None)
    msg["Date"] = format_datetime(datetime.now(CST))
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    log(f"发信参数: 发件人 {formataddr((from_name, from_addr))} -> 收件人 {', '.join(cfg['to'])}"
        f"，SMTP {host}:{port} ({security})，账号 {username or '无'}")

    if security == "ssl":
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as s:
            if username:
                s.login(username, password)
            s.sendmail(from_addr, cfg["to"], msg.as_string())
    else:
        with smtplib.SMTP(host, port, timeout=30) as s:
            if security == "starttls":
                s.starttls(context=ssl.create_default_context())
            if username:
                s.login(username, password)
            s.sendmail(from_addr, cfg["to"], msg.as_string())


def _parse_addr(value: str) -> tuple[str, str]:
    value = value or ""
    if "<" in value and ">" in value:
        name = value.split("<")[0].strip().strip('"')
        addr = value.split("<")[1].split(">")[0].strip()
        return name, addr
    return "", value.strip()


def _effective_from(cfg: dict) -> tuple[str, str]:
    """确定发件人：占位地址自动回退到 SMTP 账号，否则 SPF/DMARC 会把邮件吃掉。"""
    name, addr = _parse_addr(cfg.get("from") or "")
    username = (cfg.get("username") or "").strip()
    addr_domain = addr.split("@")[-1].lower() if "@" in addr else ""
    user_domain = username.split("@")[-1].lower() if "@" in username else ""

    if username and (not addr or addr_domain in PLACEHOLDER_DOMAINS):
        log(f"发件人 {(addr or '(空)')} 不可用（占位地址会被 SPF/DMARC 拒收），改用 {username}")
        return name, username
    if username and user_domain and addr_domain != user_domain:
        log(f"提示：发件人域 {addr_domain} 与 SMTP 账号域 {user_domain} 不同，"
            "若发件域没授权这台服务器，邮件可能被判为伪造")
    return name, addr


def _already_sent(notice_id: str | None) -> bool:
    record = read_json(LOG_PATH, {}) or {}
    sent = record.get("sent") or {}
    if notice_id and notice_id in sent:
        return True
    # 兼容旧格式
    return bool(notice_id and record.get("last_notice_id") == notice_id)


def _mark_sent(notice_id: str | None, kind: str, subject: str, cfg: dict) -> None:
    record = read_json(LOG_PATH, {}) or {}
    sent = record.get("sent") or {}
    if notice_id:
        sent[notice_id] = {"kind": kind, "sent_at": _now(), "subject": subject}
    write_json(LOG_PATH, {
        "sent": dict(list(sent.items())[-200:]),
        "last_notice_id": notice_id,
        "last_kind": kind,
        "sent_at": _now(),
        "subject": subject,
        "to": cfg.get("to"),
    })


def send_if_needed(data: dict, cfg: dict | None = None) -> dict:
    """按配置决定是否发信；同一公告只发一次。返回结果字典（写进日志与站点数据）。"""
    cfg = cfg or config()
    if not cfg:
        return {"sent": False, "reason": "notifications.yaml not found"}

    status = (data.get("meta") or {}).get("status") or "new"
    kind = (data.get("notice") or {}).get("kind") or "other"
    notice_id = (data.get("notice") or {}).get("id")

    if not _should_send(cfg, kind, status):
        return {"sent": False, "reason": f"skipped by policy (kind={kind}, status={status})"}
    if _already_sent(notice_id):
        return {"sent": False, "reason": "already sent for this notice"}

    ctx = _context(data)
    subject = _subject(ctx, cfg)
    text = _text(ctx, cfg)
    html_body = _html(ctx, cfg)

    if cfg.get("dry_run"):
        log(f"[dry-run] email not sent: {subject}")
        return {"sent": False, "dry_run": True, "subject": subject}

    try:
        _smtp_send(cfg, subject, text, html_body)
    except Exception as exc:  # noqa: BLE001 - 发信失败不阻断主流程
        log(f"email failed: {type(exc).__name__}: {exc}")
        return {"sent": False, "error": f"{type(exc).__name__}: {exc}", "subject": subject}

    _mark_sent(notice_id, kind, subject, cfg)
    log(f"email sent to {', '.join(cfg.get('to') or [])}: {subject}")
    return {"sent": True, "subject": subject, "to": cfg.get("to"), "sent_at": _now()}


def send_test(data: dict | None = None, cfg: dict | None = None) -> dict:
    """发一封测试邮件，用最近一次数据渲染，便于上线前验证 SMTP。"""
    cfg = cfg or config()
    if not cfg:
        return {"sent": False, "reason": "notifications.yaml not found"}
    if not data:
        data = read_json(ROOT / "docs" / "data" / "latest.json", {}) or {}
    ctx = _context(data)
    ctx["title"] = f"[TEST] {ctx['title']}"
    subject = f"{(cfg.get('subject_prefix') or '[Supplier Watch]').strip()} [TEST] SMTP connectivity check"
    text = _text(ctx, cfg)
    html_body = _html(ctx, cfg)

    preview = ROOT / "data" / "email_preview.html"
    preview.parent.mkdir(parents=True, exist_ok=True)
    preview.write_text(html_body, encoding="utf-8")
    log(f"email preview written: {preview}")

    if cfg.get("dry_run"):
        log(f"[dry-run] test email not sent: {subject}")
        return {"sent": False, "dry_run": True, "subject": subject, "preview": str(preview)}
    try:
        _smtp_send(cfg, subject, text, html_body)
    except Exception as exc:  # noqa: BLE001
        log(f"test email failed: {type(exc).__name__}: {exc}")
        return {"sent": False, "error": f"{type(exc).__name__}: {exc}"}
    log(f"test email sent to {', '.join(cfg.get('to') or [])}")
    return {"sent": True, "subject": subject, "to": cfg.get("to")}
