// Cloudflare Worker: 每日 Bing 壁纸代理 + 博主覆盖
// 缓存：Cache API 缓存 24h，每天只去 Bing 抓 1 次（不占 D1/KV 你的存储计数压力）
// KV：仅存 1 条覆盖图 URL（约 200 字节），博主可手动覆盖/恢复

const ADMIN_KEY = "AbCdEfGhIjKlMnOpQrSt";

async function getBingUrl() {
  try {
    const api = "https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1&mkt=zh-cn";
    const resp = await fetch(api, { cf: { cacheTtl: 3600 } });
    const data = await resp.json();
    const urlbase = data.images && data.images[0] && data.images[0].urlbase;
    if (!urlbase) throw new Error("no urlbase");
    return "https://www.bing.com" + urlbase + "_1920x1080.jpg";
  } catch (e) {
    return "https://www.bing.com/th?id=OHR.RedwoodPark_ZH-CN9513051062_1920x1080.jpg";
  }
}

function json(body, status) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
      "Cache-Control": "no-store",
    },
  });
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // POST /set  —— 博主设置固定背景图
    if (request.method === "POST" && url.pathname === "/set") {
      const payload = await request.json().catch(() => ({}));
      if (payload.key !== ADMIN_KEY) return json({ error: "密钥错误" }, 403);
      const img = (payload.url || "").trim();
      if (!/^https?:\/\/.+/i.test(img)) return json({ error: "图片地址无效" }, 400);
      await env.KV.put("bg_override", img, { expirationTtl: 60 * 60 * 24 * 365 });
      return json({ ok: true, url: img });
    }

    // POST /reset —— 博主恢复每日自动
    if (request.method === "POST" && url.pathname === "/reset") {
      const payload = await request.json().catch(() => ({}));
      if (payload.key !== ADMIN_KEY) return json({ error: "密钥错误" }, 403);
      await env.KV.delete("bg_override");
      return json({ ok: true });
    }

    // GET / —— 返回当前生效背景
    const cache = caches.default;
    const cacheKey = new Request("https://bing-daily-bg/cache/serve", request);

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET,POST,OPTIONS" } });
    }

    // 优先返回覆盖图
    let override = null;
    try { override = await env.KV.get("bg_override"); } catch (e) {}
    if (override) {
      return json({ url: override, mode: "override" });
    }

    // 否则返回当天 Bing 图（缓存 24h）
    let cached = await cache.match(cacheKey);
    if (cached) return cached;
    const imgUrl = await getBingUrl();
    const out = json({ url: imgUrl, mode: "auto" }, 200);
    out.headers.set("Cache-Control", "public, max-age=86400");
    ctx.waitUntil(cache.put(cacheKey, out.clone()));
    return out;
  },
};
