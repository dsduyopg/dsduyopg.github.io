# CSDN 博客本地化工具

## 用途

CSDN 导出的 Markdown 文件通常只包含图床链接，例如：

```markdown
![图片](https://img-blog.csdnimg.cn/xxxx.png)
```

如果图床失效或文章被删除，图片就找不回来了。

这个工具会把 Markdown 里的远程图片全部下载到本地，并把链接改成相对路径：

```markdown
![图片](images/xxxx.png)
```

这样博客的正文和图片就能一起保存、迁移、备份。

## 使用方法

### 1. 准备

本机需要安装 Python 3.11 或更高版本。

检查：

```powershell
python --version
```

### 2. 下载图片

```powershell
python download_images.py "D:\博客\文章.md"
```

执行后会在文章同目录生成：

```text
D:\博客\
├─ 文章.md
└─ images\
   └─ xxxx.png
```

`文章.md` 里的图片链接会自动改写为：

```markdown
![图片](images/xxxx.png)
```

### 3. 可选参数

指定图片目录名：

```powershell
python download_images.py "D:\博客\文章.md" --out 图片
```

只预览，不实际下载：

```powershell
python download_images.py "D:\博客\文章.md" --dry-run
```

## 注意事项

- 脚本只处理 Markdown 的 `![alt](url)` 图片语法
- 下载失败时会保留原图床链接，并在结果里显示 `FAILED`
- 已存在且大小不为 0 的图片会自动跳过，不会重复下载
- 执行前会先把原 Markdown 备份为 `文章.md.bak`
- 下载的图片文件会按 URL 文件名保存，重名时自动加编号

## 建议

下载完成后，把整个博客文件夹放进 Teldrive 备份目录，这样正文和图片都会一起自动备份，不再依赖 CSDN 图床。
