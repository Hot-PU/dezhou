/**
 * 免费源站中继：Cloudflare Worker（免费额度 10 万次/天，无需信用卡）。
 *
 * 背景：德州市生态环境局站点在境外只有 IPv6 出口可访问，GitHub 托管 runner
 * 没有 IPv6，抓取必然超时。Worker 跑在 Cloudflare 的网络上（IPv4/IPv6 双栈），
 * 由它去取页面，再把内容原样返回给 Actions。
 *
 * 部署：
 *   1. 注册 https://dash.cloudflare.com （免费）
 *   2. Workers & Pages → Create → Worker → 粘贴本文件 → Deploy
 *   3. Settings → Variables 添加加密变量 RELAY_TOKEN（随便一串随机字符）
 *   4. 用法： https://<你的>.workers.dev/?token=<RELAY_TOKEN>&url=<urlencoded 目标地址>
 *   5. 在 GitHub 仓库 Secrets 里加 SOURCE_RELAY，值为
 *      https://<你的>.workers.dev/?token=<RELAY_TOKEN>
 *
 * 自检：浏览器打开 https://<你的>.workers.dev/?token=...&ping=1 会返回代理出口信息。
 */

const ALLOWED_HOSTS = [
  "dezhou.gov.cn", // 列表/详情/附件都在这个域下
];

function hostAllowed(target) {
  const host = (target.hostname || "").toLowerCase();
  return ALLOWED_HOSTS.some((h) => host === h || host.endsWith("." + h));
}

export default {
  async fetch(request, env) {
    const reqUrl = new URL(request.url);
    const token = reqUrl.searchParams.get("token") || "";

    if (env.RELAY_TOKEN && token !== env.RELAY_TOKEN) {
      return new Response("forbidden: bad token", { status: 403 });
    }

    if (reqUrl.searchParams.get("ping")) {
      const ip = request.headers.get("cf-connecting-ip") || "";
      return Response.json({
        ok: true,
        colo: request.cf && request.cf.colo,
        client_ip: ip,
        allowed_hosts: ALLOWED_HOSTS,
      });
    }

    const raw = reqUrl.searchParams.get("url");
    if (!raw) {
      return new Response("usage: ?token=<t>&url=<encoded target url>", { status: 400 });
    }

    let target;
    try {
      target = new URL(raw);
    } catch {
      return new Response("bad url", { status: 400 });
    }
    if (!hostAllowed(target)) {
      return new Response(`host not allowed: ${target.hostname}`, { status: 403 });
    }

    const headers = new Headers({
      "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
        "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36 Edg/156.0.0.0",
      Accept: "*/*",
      "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
      Referer: `${target.protocol}//${target.host}/`,
    });

    let upstream;
    try {
      upstream = await fetch(target.toString(), { headers, redirect: "follow" });
    } catch (err) {
      return Response.json(
        { ok: false, error: String(err), target: target.toString() },
        { status: 502 },
      );
    }

    const body = await upstream.arrayBuffer();
    return new Response(body, {
      status: upstream.status,
      headers: {
        "content-type": upstream.headers.get("content-type") || "application/octet-stream",
        "cache-control": "no-store",
        "access-control-allow-origin": "*",
      },
    });
  },
};
