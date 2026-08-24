// Cloudflare Workers + KV 匿名点赞服务
// 部署后提供两个接口（自动处理 CORS 预检）:
//   GET  /api/like?path=/xxx/        -> {"path":"/xxx/","count":N,"liked":true|false}
//   POST /api/like  body {"path":"/xxx/"} -> {"path":"/xxx/","count":N,"liked":true,"already":false}
// 说明: 同一 IP 对同一 path 只能点赞一次(防刷); 计数与"是否点过"都存 KV。
// KV namespace 绑定名必须是 LIKE_KV(见 wrangler.toml)。

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Access-Control-Max-Age': '86400',
};

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json', ...CORS_HEADERS },
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const kv = env.LIKE_KV;

    // 只服务 /api/like
    if (url.pathname !== '/api/like') {
      return json({ error: 'not found' }, 404);
    }

    // CORS 预检
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    // 访客真实 IP(Cloudflare 注入)
    const ip = request.headers.get('CF-Connecting-IP') || 'unknown';

    if (request.method === 'GET') {
      const path = url.searchParams.get('path') || '';
      if (!path) return json({ error: 'missing path' }, 400);
      const count = parseInt((await kv.get(`like:${path}`)) || '0', 10);
      const liked = (await kv.get(`liked:${path}:${ip}`)) === '1';
      return json({ path, count, liked });
    }

    if (request.method === 'POST') {
      let body;
      try {
        body = await request.json();
      } catch {
        return json({ error: 'bad json' }, 400);
      }
      const path = String(body.path || '').trim();
      if (!path) return json({ error: 'missing path' }, 400);

      const key = `like:${path}`;
      const likedKey = `liked:${path}:${ip}`;

      // 该 IP 已经点过
      if ((await kv.get(likedKey)) === '1') {
        const count = parseInt((await kv.get(key)) || '0', 10);
        return json({ path, count, liked: true, already: true });
      }

      // 正常 +1
      const prev = parseInt((await kv.get(key)) || '0', 10);
      const next = prev + 1;
      await kv.put(key, String(next));
      await kv.put(likedKey, '1', { expirationTtl: 31536000 }); // 记录一年

      return json({ path, count: next, liked: true, already: false });
    }

    return json({ error: 'method not allowed' }, 405);
  },
};
