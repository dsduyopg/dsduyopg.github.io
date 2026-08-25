// Cloudflare Worker: 每日 Bing 壁纸 + 博主覆盖
// 缓存：Cache API，每天只抓 Bing 有限次（不占 D1/KV 你的存储）
// KV：仅存 1 条覆盖图 URL（约 200 字节）

const ADMIN_KEY = "AbCdEfGhIjKlMnOpQrSt";

async function bingList(n) {
  try {
    const api = "https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=" + n + "&mkt=zh-cn";
    const resp = await fetch(api, { cf: { cacheTtl: 3600 } });
    const data = await resp.json();
    if (!data.images) return [];
    return data.images.map(function (it) {
      return {
        url: "https://www.bing.com" + it.urlbase + "_1920x1080.jpg",
        title: it.title || "",
        date: it.startdate || "",
      };
    });
  } catch (e) { return []; }
}

function json(body, status) {
  return new Response(JSON.stringify(body), {
    status: status || 200,
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
    const cache = caches.default;

    if (request.method === "OPTIONS") {
      return new Response(null, {
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type",
        },
      });
    }

    // POST /set —— 博主设置固定背景
    if (request.method === "POST" && url.pathname === "/set") {
      const p = await request.json().catch(() => ({}));
      if (p.key !== ADMIN_KEY) return json({ error: "密钥错误" }, 403);
      const img = (p.url || "").trim();
      if (!/^https?:\/\/.+/i.test(img)) return json({ error: "图片地址无效" }, 400);
      await env.KV.put("bg_override", img, { expirationTtl: 60 * 60 * 24 * 365 });
      return json({ ok: true, url: img });
    }

    // POST /save —— 把当前生效背景保存为「原始风景图」存档
    if (request.method === "POST" && url.pathname === "/save") {
      const p = await request.json().catch(() => ({}));
      if (p.key !== ADMIN_KEY) return json({ error: "密钥错误" }, 403);
      let current = null;
      try { current = await env.KV.get("bg_override"); } catch (e) {}
      if (!current) {
        const list = await bingList(1);
        current = (list[0] && list[0].url) || "";
      }
      if (!current) return json({ error: "获取当前背景失败" }, 500);
      await env.KV.put("bg_saved", current, { expirationTtl: 60 * 60 * 24 * 365 });
      return json({ ok: true, url: current });
    }

    // POST /restore —— 恢复到「原始风景图」存档
    if (request.method === "POST" && url.pathname === "/restore") {
      const p = await request.json().catch(() => ({}));
      if (p.key !== ADMIN_KEY) return json({ error: "密钥错误" }, 403);
      const saved = await env.KV.get("bg_saved");
      if (!saved) return json({ error: "还没有保存过原始风景图，请先保存" }, 404);
      await env.KV.put("bg_override", saved, { expirationTtl: 60 * 60 * 24 * 365 });
      return json({ ok: true, url: saved });
    }

    // GET /saved —— 返回原始风景图存档（公开只读，只有图片 URL）
    if (url.pathname === "/saved") {
      const saved = await env.KV.get("bg_saved");
      return json({ saved: saved || null });
    }

    // POST /reset —— 恢复自动
    if (request.method === "POST" && url.pathname === "/reset") {
      const p = await request.json().catch(() => ({}));
      if (p.key !== ADMIN_KEY) return json({ error: "密钥错误" }, 403);
      await env.KV.delete("bg_override");
      return json({ ok: true });
    }

    // GET /list?n=8 —— 返回最近 n 天 Bing 图（供页面翻历史）
    if (url.pathname === "/list") {
      const n = Math.min(parseInt(url.searchParams.get("n") || "8", 10), 20);
      const list = await bingList(n);
      return json({ images: list });
    }

    // GET / —— 当前生效背景（覆盖优先，否则当天 Bing）
    let override = null;
    try { override = await env.KV.get("bg_override"); } catch (e) {}
    if (override) return json({ url: override, mode: "override" });

    const cacheKey = new Request("https://bing-daily-bg/cache/serve", request);
    let cached = await cache.match(cacheKey);
    if (cached) return cached;
    const list = await bingList(1);
    const imgUrl = (list[0] && list[0].url) || "https://www.bing.com/th?id=OHR.RedwoodPark_ZH-CN9513051062_1920x1080.jpg";
    const out = json({ url: imgUrl, mode: "auto" });
    out.headers.set("Cache-Control", "public, max-age=86400");
    ctx.waitUntil(cache.put(cacheKey, out.clone()));
    return out;
  },
};
