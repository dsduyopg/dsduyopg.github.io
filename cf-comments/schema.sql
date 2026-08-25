-- D1 初始化脚本：在 Cloudflare 控制台或 wrangler 执行
CREATE TABLE IF NOT EXISTS comments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT NOT NULL,
  author TEXT NOT NULL,
  body TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_comments_slug ON comments(slug);
CREATE INDEX IF NOT EXISTS idx_comments_created ON comments(created_at);
