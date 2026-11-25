# 部署指南（Vercel + GitHub Actions）

站点是纯静态的：GitHub Actions 每天抓取、分析、把结果写进 `docs/` 并提交；
Vercel 直接托管 `docs/`，不需要在 Vercel 里跑 Python。

## 1. 建仓库

新建一个空仓库（不要勾选 README / .gitignore），然后在本目录执行：

```bash
git init
git add .
git commit -m "init: Dezhou supplier impact monitor"
git branch -M main
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

## 2. 配 Secrets（Settings → Secrets and variables → Actions）

以下都可选，不配也能运行：

| 名称 | 用途 |
| --- | --- |
| `WAQI_TOKEN` | 空气质量数据 token（不配用内置默认） |
| `AI_API_KEY` / `AI_BASE_URL` / `AI_MODEL` | 可选的大模型分析 |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_SECURITY` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM` / `SMTP_TO` | 邮件通知 |
| `SOURCE_RELAY` | 可覆盖 `config/settings.yaml` 里内置的中继地址（不配则用内置），见第 6 节 |
| `SOURCE_PROXY` | 国内出口的 HTTP/SOCKS 代理，见第 6 节 |

变量（Variables，非 Secrets）：`EMAIL_DRY_RUN=true` 可先只渲染不投递。

## 3. 部署到 Vercel

1. 打开 <https://vercel.com/new>，选择刚推送的仓库。
2. Framework Preset 选 **Other**，Root Directory 保持默认。
3. Build & Output Settings 不用改：仓库里的 `vercel.json` 已指定
   - Build Command：`echo "static site: docs/ is committed by GitHub Actions"`（不构建）
   - Output Directory：`docs`
4. 点 Deploy。之后每次 `main` 有新提交（包括 Actions 每天写入的数据提交）都会自动重新部署。

> 说明：工作流的提交信息去掉了 `[skip ci]`，否则 Vercel 会跳过这些数据更新；
> 由于工作流只监听 `src/` `config/` `web/` 等代码路径，数据提交不会反向触发 Actions，不会循环。

## 4. 首次运行 Action

Actions → 「每日重污染巡检」→ Run workflow：

- 勾选 `force`：公告未更新也重新分析
- 勾选 `notify_test`：先发一封测试邮件验证 SMTP

之后每天 07:30 / 13:30 / 19:30（北京时间）自动执行，抓取结果提交回 `main`，Vercel 自动更新站点。

## 5. 也可以继续用 GitHub Pages（可选）

Settings → Pages → Source 选 **GitHub Actions**，工作流里的 deploy job 会一并发布。

## 6. 数据源在境外访问不通（免费解决）

现象：Actions 日志里 `dzbee.dezhou.gov.cn` 报
`[Errno 101] Network is unreachable`，且每次重试卡满 40 秒。

实测（2026-11，境外 SSL Labs / AWS 节点）：

| 地址 | 境外连通性 |
| --- | --- |
| IPv4 `112.253.47.47:443` | 超时，连不上 |
| IPv6 `240e:644:6700::26:443` | 正常，返回 `HTTP 200` |

即：该站在境外**只有 IPv6 出口才通**，而 GitHub 托管 runner 没有 IPv6，
`requests` 只能走 IPv4，所以必然失败。国内网络直连正常。

### 方案 A：Cloudflare Worker 中继（已内置，0 成本）

Worker 跑在 Cloudflare 双栈网络上，由它去取页面、原样返回给 Actions。

**当前仓库已经直接内置了中继，推到 GitHub 就能用，不用配任何 Secret：**

```yaml
# config/settings.yaml
source:
  relay: https://dezhou.zhenyusun84.workers.dev/?token=dereksun
```

下面只在这种情况下才需要看：中继挂了 / 要换 token / 想重新建一个。

1. 注册 <https://dash.cloudflare.com>（免费额度 10 万次/天，本项目一天最多十几次请求）。
2. **Workers & Pages → Create → Worker**，命名如 `dz-relay`，把 `worker/relay.js`
   的内容整个粘进去 → **Deploy**。
3. Worker → **Settings → Variables and Secrets** 添加加密变量 `RELAY_TOKEN`，
   值随便填一串随机字符（不要公开）。
4. 自检：浏览器打开

   ```
   https://dz-relay.<你的>.workers.dev/?token=<TOKEN>&ping=1
   ```

   看到 `ok: true` 说明 Worker 已上线；再打开

   ```
   https://dz-relay.<你的>.workers.dev/?token=<TOKEN>&url=https%3A%2F%2Fdzbee.dezhou.gov.cn%2Fn23586430%2Findex.html
   ```

   能出 HTML（或至少不是超时）就说明这条出口能到源站。

5. 改 `config/settings.yaml` 里的 `source.relay`（或配环境变量 `SOURCE_RELAY` 覆盖，
   适合不想提交 token 的情况），然后 `python run.py --probe` 验证。

> 中继只转发 `*.dezhou.gov.cn`（`worker/relay.js` 里的白名单），配了 token 后别人拿到地址也刷不了别的站。
> 日志与站点数据里的 `token=...` 会自动脱敏（`src/common.redact`），所以即使抓取失败也不会把密钥写进页面。
> 若仓库以后要转为公开，建议把 token 改成 GitHub Secret（`SOURCE_RELAY`）并删掉 `settings.yaml` 里的值。
> 若 Worker 里 `fetch` 也报超时，把返回的 JSON 日志贴出来即可判断是 Cloudflare 出口被拒还是别的。

### 方案 B：Cloudflare WARP（免费、不用注册账号）

在 workflow 里给 runner 装 WARP，等于给 runner 一个 IPv6 出口，代码完全不用改：

```yaml
      - name: 启用 Cloudflare WARP
        run: |
          curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg \
            | sudo gpg --yes --dearmor -o /usr/share/keyrings/cloudflare-warp-keyring.gpg
          echo "deb [signed-by=/usr/share/keyrings/cloudflare-warp-keyring.gpg] \
            https://pkg.cloudflareclient.com/ $(lsb_release -cs) main" \
            | sudo tee /etc/apt/sources.list.d/cloudflare-client.list
          sudo apt-get update && sudo apt-get install -y cloudflare-warp
          warp-cli --accept-tos registration new
          warp-cli --accept-tos connect
          sleep 5 && warp-cli --accept-tos status
```

缺点是要在 CI 里跑一个常驻客户端，稳定性不如方案 A。

### 方案 C：公共 CORS 代理（应急，不推荐长期用）

`src/fetch.py` 的中继只要形如 `...?token=&url=<encoded>` 即可，所以也能直接填公共代理，
比如 `SOURCE_RELAY=https://api.allorigins.win/raw?`。它们免费但限速、随时会挂，只适合临时验证。

### 方案 D：自托管 runner 放国内

`runs-on: self-hosted`，家里/公司一台常开的机器（或国内云主机）即可，
完全不依赖境外出口，也没有第三方依赖。

### 没配代理会怎样

不会再把 Action 跑红：抓不到源站时 `run.py` 会沿用上次数据重建站点，
把 `meta.status` 标成 `unreachable`，页面顶部提示「今日未能访问……沿用 x 月 x 日 的分析结果」。
只有连历史数据都不存在时，才会以非零退出码结束。

## 7. 本地预览

```bash
pip install -r requirements.txt
python run.py --offline          # 用现有数据重建页面
cd docs && python -m http.server 8765
```
