var __defProp = Object.defineProperty;
var __name = (target, value) => __defProp(target, "name", { value, configurable: true });

// worker.js
var CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Access-Control-Max-Age": "86400"
};
function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store", ...CORS_HEADERS }
  });
}
__name(json, "json");
var worker_default = {
  async fetch(request, env) {
    const url = new URL(request.url);
    const kv = env.LIKE_KV;
    if (url.pathname !== "/api/like") {
      return json({ error: "not found" }, 404);
    }
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }
    const ip = request.headers.get("CF-Connecting-IP") || "unknown";
    if (request.method === "GET") {
      const path = url.searchParams.get("path") || "";
      if (!path) return json({ error: "missing path" }, 400);
      const count = parseInt(await kv.get(`like:${path}`) || "0", 10);
      const liked = await kv.get(`liked:${path}:${ip}`) === "1";
      return json({ path, count, liked });
    }
    if (request.method === "POST") {
      let body;
      try {
        body = await request.json();
      } catch {
        return json({ error: "bad json" }, 400);
      }
      const path = String(body.path || "").trim();
      if (!path) return json({ error: "missing path" }, 400);
      const key = `like:${path}`;
      const likedKey = `liked:${path}:${ip}`;
      if (await kv.get(likedKey) === "1") {
        const count = parseInt(await kv.get(key) || "0", 10);
        return json({ path, count, liked: true, already: true });
      }
      const prev = parseInt(await kv.get(key) || "0", 10);
      const next = prev + 1;
      await kv.put(key, String(next));
      await kv.put(likedKey, "1", { expirationTtl: 31536e3 });
      return json({ path, count: next, liked: true, already: false });
    }
    return json({ error: "method not allowed" }, 405);
  }
};
export {
  worker_default as default
};
//# sourceMappingURL=worker.js.map
