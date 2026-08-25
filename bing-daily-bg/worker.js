// Cloudflare Worker: 每日 Bing 壁纸代理
// 用途：前端请求本 Worker，返回当天 Bing 风景图 1920x1080 直链。
// 缓存：用 Cache API 缓存 24 小时，每天只去 Bing 抓 1 次（不占 D1/KV/你的存储）。
export default {
  async fetch(request, env, ctx) {
    const cache = caches.default;
    const cacheKey = new Request("https://bing-daily-bg/cache/today", request);
    // 先查缓存
    let cached = await cache.match(cacheKey);
    if (cached) return cached;

    // 抓 Bing 每日壁纸接口
    const api = "https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1&mkt=zh-cn";
    let imgUrl;
    try {
      const resp = await fetch(api, { cf: { cacheTtl: 3600 } });
      const data = await resp.json();
      const urlbase = data.images && data.images[0] && data.images[0].urlbase;
      if (!urlbase) throw new Error("no urlbase");
      imgUrl = "https://www.bing.com" + urlbase + "_1920x1080.jpg";
    } catch (e) {
      // 兜底：用一张固定 Bing 图，避免背景空白
      imgUrl = "https://www.bing.com/th?id=OHR.RedwoodPark_ZH-CN9513051062_1920x1080.jpg";
    }

    // 返回 JSON 给前端
    const out = new Response(JSON.stringify({ url: imgUrl }), {
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "public, max-age=86400",
        "Access-Control-Allow-Origin": "*",
      },
    });
    // 写入 Cache API（24h）
    ctx.waitUntil(cache.put(cacheKey, out.clone()));
    return out;
  },
};
