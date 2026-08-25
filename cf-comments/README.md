# CF 自建评论系统（CFW + D1 + Turnstile）

博客评论后端：Cloudflare Worker 处理 API，D1 存评论，Turnstile 防机器人，KV 做频率限制。
前端集成在 Hugo 的 `layouts/partials/comments.html`（giscus 下方），支持匿名提交 + GitHub 轻量登录。

## 一、准备资源（都在 Cloudflare 控制台）

1. **D1 数据库**
   - Workers & Pages → D1 → Create → 名称 `blog-comments-db`
   - 复制数据库 ID，填进 `wrangler.toml` 的 `database_id`
   - 执行建表：`wrangler d1 execute blog-comments-db --file=./schema.sql --remote`

2. **KV 命名空间**（频率限制）
   - Workers & Pages → KV → Create namespace → 名称 `blog-comments-kv`
   - 复制命名空间 ID，填进 `wrangler.toml` 的 `kv_namespaces.id`

3. **Turnstile**
   - 控制台 → Turnstile → Add widget → 域名填 `dsduyopg-github-io.pages.dev`（或你的自定义域）
   - 拿到 **Site Key** 和 **Secret Key**
   - Site Key 填前端 `comments.html` 里的 `TURNSTILE_SITE_KEY`
   - Secret Key 填 `wrangler.toml` 里的 `TURNSTALL_SECRET`（建议用 `wrangler secret put TURNSTALL_SECRET` 更安全）

4. **GitHub OAuth App**（仅轻量登录需要）
   - GitHub → Settings → Developer settings → OAuth Apps → New
   - Homepage URL：`https://dsduyopg-github-io.pages.dev`
   - Authorization callback URL：`https://dsduyopg-github-io.pages.dev/gh-callback.html`（见 gh-callback.html）
   - 拿到 **Client ID**（填前端 `GH_CLIENT_ID`）；Client Secret 在前端不需要

## 二、部署 Worker

```bash
cd cf-comments
# 本地预览（需 wrangler + 已登录：wrangler login）
wrangler dev

# 部署到生产
wrangler deploy
```

部署后 Worker 地址形如 `https://blog-comments.<你的子域>.workers.dev`，
把它填进前端 `comments.html` 的 `API` 变量（替换 `629017960` 为你的子域）。

## 三、前端集成

`comments.html` 已包含 CF 评论区代码，需替换占位符：
- `YOUR_TURNSTILE_SITE_KEY` → 真实 Turnstile Site Key
- `YOUR_GITHUB_CLIENT_ID` → 真实 GitHub Client ID
- `https://blog-comments.629017960.workers.dev` → 你的 Worker 真实地址

把 `gh-callback.html` 放到 Hugo 的 `static/` 目录（构建后作为 `/gh-callback.html` 可访问）。

然后 hugo 构建 + push（Git 自动构建会重新部署 Pages）。

## 四、注意

- Worker 用 `629017960` 子域是示例，换成你自己的 CF 账号子域。
- Turnstile Secret 通过 `wrangler secret` 设置比写进 wrangler.toml 更安全。
- giscus 原样保留，未删除。
