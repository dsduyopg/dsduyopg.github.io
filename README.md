# 我的博客

基于 Hugo + PaperMod 的个人博客，可以部署到 GitHub Pages 或 Cloudflare Pages。

## 本地运行

```powershell
hugo server
```

浏览器打开 <http://localhost:1313>。

## 新建文章

```powershell
hugo new posts/文章标题/index.md
```

文章写在 `content/posts/文章标题/index.md`，图片放在同目录的 `images/` 下。

## 部署到 GitHub Pages

1. 在 GitHub 新建仓库 `你的用户名.github.io`
2. 把本目录推送到仓库 main 分支
3. 仓库 Settings -> Pages -> Source 选择 `GitHub Actions`
4. 仓库里已经包含 `.github/workflows/hugo.yml`，推送后自动构建部署

## 部署到 Cloudflare Pages

1. 把本目录推送到任意 GitHub 仓库
2. Cloudflare 控制台：Workers & Pages -> Create -> Pages -> Connect to Git，选择该仓库
3. 构建配置：

```text
Build command: hugo --baseURL https://你的项目名.pages.dev/ --minify
Build output directory: public
```

可选环境变量：

```text
HUGO_VERSION = 0.164.0
```

4. 把 `你的项目名` 换成你实际的 Cloudflare Pages 项目名
5. 部署完成后，访问 `https://你的项目名.pages.dev`

注意：这个构建命令只对 Cloudflare 生效，不会影响 GitHub Pages 的 `baseURL`。

## 注意

- 文章图片必须和 `index.md` 放在同一个目录，Hugo 才会自动发布
- 不要提交 `csdn_cookie.txt`、Token、密码等敏感信息
- 部分文章由 AI 辅助创作，发布时保留文首声明
