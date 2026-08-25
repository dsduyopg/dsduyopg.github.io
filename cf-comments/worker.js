// Cloudflare Worker: 评论 API (CFW)
// 后端：D1 存评论 + KV 频率限制 + Turnstile 防机器人
// 支持：匿名提交（昵称+内容，过 Turnstile）、GitHub 轻量登录（前端拿用户名填昵称）

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // CORS（允许你的站点调用）
    const ALLOWED_ORIGINS = [
      "https://dsduyopg-github-io.pages.dev",
      "https://duyulin.dpdns.org",
    ];
    const origin = request.headers.get("Origin") || "";
    const corsHeaders = {
      "Access-Control-Allow-Origin": ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0],
      "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
      "Vary": "Origin",
    };

    // 预检
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders });
    }

    // GET /api/comments?slug=xxx
    if (request.method === "GET" && url.pathname === "/api/comments") {
      const slug = url.searchParams.get("slug") || "";
      if (!slug) {
        return json({ error: "missing slug" }, 400, corsHeaders);
      }
      const { results } = await env.DB.prepare(
        "SELECT id, author, body, created_at FROM comments WHERE slug = ? ORDER BY created_at ASC"
      ).bind(slug).all();
      return json({ comments: results }, 200, corsHeaders);
    }

    // POST /api/comments  { slug, author, body, "cf-turnstile-response" }
    if (request.method === "POST" && url.pathname === "/api/comments") {
      let payload;
      try {
        payload = await request.json();
      } catch {
        return json({ error: "invalid json" }, 400, corsHeaders);
      }

      const slug = (payload.slug || "").toString().slice(0, 255);
      const author = (payload.author || "匿名").toString().trim().slice(0, 40) || "匿名";
      const body = (payload.body || "").toString().trim();
      const token = payload["cf-turnstile-response"] || "";

      if (!slug) return json({ error: "missing slug" }, 400, corsHeaders);
      if (body.length < 1) return json({ error: "评论内容不能为空" }, 400, corsHeaders);
      if (body.length > 2000) return json({ error: "评论内容过长（≤2000字）" }, 400, corsHeaders);

      // ---- Turnstile 校验 ----
      const ip = request.headers.get("CF-Connecting-IP") || "";
      const ok = await verifyTurnstile(token, env.TURNSTALL_SECRET, ip);
      if (!ok) {
        return json({ error: "人机验证失败，请重试" }, 403, corsHeaders);
      }

      // ---- 频率限制（同一 IP 60 秒内最多 5 条）----
      const kvKey = "rate:" + ip;
      let count = parseInt(await env.KV.get(kvKey) || "0", 10);
      if (count >= 5) {
        return json({ error: "提交过于频繁，请稍后再试" }, 429, corsHeaders);
      }
      await env.KV.put(kvKey, String(count + 1), { expirationTtl: 60 });

      // ---- 写入 D1 ----
      await env.DB.prepare(
        "INSERT INTO comments (slug, author, body, created_at) VALUES (?, ?, ?, ?)"
      ).bind(slug, author, body, Date.now()).run();

      return json({ ok: true }, 201, corsHeaders);
    }

    // DELETE /api/comments  { id, adminToken }  —— 博主删除
    if (request.method === "DELETE" && url.pathname === "/api/comments") {
      if (!env.ADMIN_KEY) {
        return json({ error: "服务端未配置管理员密码" }, 500, corsHeaders);
      }
      let payload;
      try {
        payload = await request.json();
      } catch {
        return json({ error: "invalid json" }, 400, corsHeaders);
      }
      const id = parseInt(payload.id, 10);
      const token = payload.adminToken || "";
      if (!Number.isInteger(id)) {
        return json({ error: "invalid id" }, 400, corsHeaders);
      }
      if (token !== env.ADMIN_KEY) {
        return json({ error: "密码错误，无权删除" }, 403, corsHeaders);
      }
      const info = await env.DB.prepare("DELETE FROM comments WHERE id = ?").bind(id).run();
      if (info.success) {
        return json({ ok: true }, 200, corsHeaders);
      }
      return json({ error: "删除失败" }, 500, corsHeaders);
    }

    return json({ error: "not found" }, 404, corsHeaders);
  },
};

async function verifyTurnstile(token, secret, ip) {
  if (!secret) return false;            // 没配 secret 则拒绝（强制开启验证）
  if (!token) return false;
  const fd = new FormData();
  fd.append("secret", secret);
  fd.append("response", token);
  if (ip) fd.append("remoteip", ip);
  try {
    const r = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", {
      method: "POST",
      body: fd,
    });
    const data = await r.json();
    return data.success === true;
  } catch {
    return false;
  }
}

function json(obj, status, headers) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...headers },
  });
}
