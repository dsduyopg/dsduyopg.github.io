#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Obsidian 笔记 → R2 图片链接转换器
================================

专门适配你的 Obsidian 笔记结构：

    20260912_shell脚本三剑客之grep/
    ├── grep的相关问题以及解决手段.md      ← 笔记（slug 由它的文件名推导）
    └── pictures/                          ← 附件夹（自动探测）
        └── Pasted image 20260913080949.png

生成的 R2 链接规则：

    <base>/<prefix>/<slug>/<子目录>/<文件名>
    https://pub-xxxx.r2.dev/blog_images/grep的相关问题以及解决手段/pictures/Pasted%20image%2020260913080949.png
                                       └── 笔记名 ──┘  └附件夹┘  └── 原文件名 ──┘

与 replace_images_to_r2.py 的区别（三个都是实测踩过的坑）：
  1. 支持 Obsidian 双链语法 ![[图片.png]]（原脚本只认 ![](path)，对双链替换 0 处）
  2. 附件夹自动探测（pictures / images / assets… 都认，原脚本写死 images）
  3. 上传校验时**比对本地文件字节数**，能发现传错/传漏/传了一半的文件

用法：
  # 预览（不写文件）
  python obsidian_images_to_r2.py --file "笔记.md" --dry-run

  # 生成 -r2.md（默认输出到同目录，加 -r2 后缀）
  python obsidian_images_to_r2.py --file "笔记.md"

  # 原地替换 + 校验
  python obsidian_images_to_r2.py --file "笔记.md" --in-place --check

  # 手动指定 slug / 附件夹 / 保留图片尺寸
  python obsidian_images_to_r2.py --file "笔记.md" --slug "my-post" --subdir pictures --keep-size
"""

import argparse
import concurrent.futures
import hashlib
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

# ────────────────────────── 默认配置 ──────────────────────────
DEFAULT_BASE = "https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev"
DEFAULT_PREFIX = "blog_images"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".avif"}
# 附件夹候选名（按顺序探测，Obsidian 常见设置）
SUBDIR_CANDIDATES = ["pictures", "images", "assets", "attachments", "img", "image", "media"]

# Obsidian 双链：![[名字.png]]  ![[名字.png|300]]  ![[名字.png|说明文字]]
WIKI_RE = re.compile(r"!\[\[([^\]|]+?)(?:\|([^\]]*))?\]\]")
# 标准 Markdown：![alt](path)
MD_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def enc(seg):
    """URL 编码单个路径段（斜杠保留在段外，这里只编码段内字符）"""
    return urllib.parse.quote(seg, safe="")


def build_url(base, prefix, slug, subdir, name):
    return "{0}/{1}/{2}/{3}/{4}".format(
        base.rstrip("/"), enc(prefix), enc(slug), enc(subdir), enc(name)
    )


def is_image(name):
    return Path(name).suffix.lower() in IMAGE_EXTS


def is_remote(url):
    return url.startswith(("http://", "https://", "//", "data:"))


def detect_subdir(note_dir, image_names):
    """自动探测附件夹：哪个候选目录里能找到笔记引用的图片"""
    for cand in SUBDIR_CANDIDATES:
        d = note_dir / cand
        if not d.is_dir():
            continue
        # 命中任意一张引用的图，就认为它是附件夹
        for name in image_names:
            if (d / name).exists():
                return cand
    # 兜底：找第一个含图片的候选目录
    for cand in SUBDIR_CANDIDATES:
        d = note_dir / cand
        if d.is_dir() and any(p.suffix.lower() in IMAGE_EXTS for p in d.iterdir() if p.is_file()):
            return cand
    return None


def parse_wikilink_meta(raw):
    """
    解析双链里 | 后面的部分：
      纯数字        → 宽度（Obsidian 缩放）
      其它          → alt 文字
    返回 (width 或 None, alt 或 None)
    """
    if raw is None:
        return None, None
    raw = raw.strip()
    if not raw:
        return None, None
    if re.fullmatch(r"\d+(\.\d+)?", raw):
        return raw, None
    return None, raw


def convert_text(text, base, prefix, slug, subdir, keep_size=False):
    """返回 (新文本, 替换记录列表, 未解析的目标列表)"""
    records = []
    unresolved = []
    in_fence = False

    def repl_wiki(m):
        name = m.group(1).strip()
        width, alt = parse_wikilink_meta(m.group(2))
        if not is_image(name):
            unresolved.append(name)
            return m.group(0)
        url = build_url(base, prefix, slug, subdir, name)
        records.append({"name": name, "url": url, "width": width})
        if keep_size and width:
            return '<img src="{0}" width="{1}" alt="{2}">'.format(url, width, name)
        return "![{0}]({1})".format(alt or name, url)

    def repl_md(m):
        alt, target = m.group(1), m.group(2).strip()
        if is_remote(target):
            return m.group(0)
        name = Path(target.replace("\\", "/")).name
        if not is_image(name):
            return m.group(0)
        url = build_url(base, prefix, slug, subdir, name)
        records.append({"name": name, "url": url, "width": None})
        return "![{0}]({1})".format(alt or name, url)

    out_lines = []
    for line in text.splitlines(keepends=True):
        ending = "\n" if line.endswith("\n") else ""
        body = line[: -len(ending)] if ending else line
        stripped = body.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            out_lines.append(line)
            continue
        if in_fence or stripped.startswith("    "):  # 代码块/缩进代码不动
            out_lines.append(line)
            continue
        body = WIKI_RE.sub(repl_wiki, body)
        body = MD_RE.sub(repl_md, body)
        out_lines.append(body + ending)

    return "".join(out_lines), records, unresolved


def verify(urls_with_local):
    """并发 HEAD 校验；有本地文件时比对字节数"""
    def head(item):
        url, local = item
        try:
            req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
            resp = urllib.request.urlopen(req, timeout=20)
            remote_len = resp.headers.get("Content-Length")
            local_len = local.stat().st_size if local and local.exists() else None
            if resp.status == 200 and local_len is not None and remote_len is not None:
                if int(remote_len) == local_len:
                    return url, "OK", "字节数一致 ({0})".format(local_len)
                return url, "SIZE", "本地 {0} vs 远端 {1}".format(local_len, remote_len)
            return url, str(resp.status), (str(remote_len) + " 字节" if remote_len else "")
        except Exception as exc:
            return url, "ERR", str(exc)[:80]

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        for r in ex.map(head, urls_with_local):
            results.append(r)
    return results


def audit_attachment_dir(note_dir, subdir, referenced):
    """报告：没被引用的图片 + 内容重复的图片"""
    d = note_dir / subdir if subdir else None
    if not d or not d.is_dir():
        return [], []
    files = sorted(p for p in d.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS)
    unused = [p.name for p in files if p.name not in referenced]

    by_hash = {}
    for p in files:
        h = hashlib.md5(p.read_bytes()).hexdigest()
        by_hash.setdefault(h, []).append(p.name)
    dupes = [v for v in by_hash.values() if len(v) > 1]
    return unused, dupes


def main():
    ap = argparse.ArgumentParser(description="Obsidian 笔记图片 → Cloudflare R2 链接")
    ap.add_argument("--file", required=True, help="Obsidian 笔记 .md 文件")
    ap.add_argument("--base", default=DEFAULT_BASE, help="R2 桶公开域名")
    ap.add_argument("--prefix", default=DEFAULT_PREFIX, help="桶内顶层前缀，默认 blog_images")
    ap.add_argument("--slug", help="R2 路径里的项目名，默认取笔记文件名（去 .md）")
    ap.add_argument("--subdir", help="附件夹名，默认自动探测（pictures/images/…）")
    ap.add_argument("--output", help="输出文件路径，默认同目录加 -r2 后缀")
    ap.add_argument("--in-place", action="store_true", help="直接覆盖原笔记（危险，建议先备份）")
    ap.add_argument("--keep-size", action="store_true", help="双链里的 |300 用 <img width> 保留")
    ap.add_argument("--check", action="store_true", help="生成后逐条 HEAD 校验 URL")
    ap.add_argument("--dry-run", action="store_true", help="只预览，不写文件")
    args = ap.parse_args()

    note = Path(args.file)
    if not note.exists():
        sys.exit("找不到文件: {0}".format(note))
    note_dir = note.parent
    slug = args.slug or note.stem
    base, prefix = args.base.rstrip("/"), args.prefix

    text = note.read_text(encoding="utf-8-sig")

    # 先扫一遍引用了哪些图片名，用于自动探测附件夹
    names = []
    for m in WIKI_RE.finditer(text):
        n = m.group(1).strip()
        if is_image(n):
            names.append(n)
    for m in MD_RE.finditer(text):
        n = Path(m.group(2).strip().replace("\\", "/")).name
        if not is_remote(m.group(2)) and is_image(n):
            names.append(n)

    subdir = args.subdir or detect_subdir(note_dir, names)
    if not subdir:
        sys.exit("无法探测附件夹，请用 --subdir 手动指定（例如 --subdir pictures）")

    print("笔记    : {0}".format(note))
    print("slug    : {0}".format(slug))
    print("附件夹  : {0}/".format(subdir))
    print("base    : {0}/{1}/".format(base, enc(prefix)))
    print()

    new_text, records, unresolved = convert_text(
        text, base, prefix, slug, subdir, keep_size=args.keep_size
    )

    # ── 替换明细（去重展示）──
    seen = {}
    for r in records:
        seen.setdefault(r["name"], r["url"])
    print("替换了 {0} 处引用，涉及 {1} 张不同图片".format(len(records), len(seen)))
    if unresolved:
        print("⚠️  以下双链不是图片，已跳过：{0}".format(", ".join(unresolved[:5])))
    print()

    if args.dry_run:
        print("=== 预览（前 3 条）===")
        for name, url in list(seen.items())[:3]:
            print("  {0}\n    → {1}".format(name, url))
        print("\n[dry-run] 未写入任何文件。去掉 --dry-run 即可生成。")
        return

    # ── 写文件 ──
    if args.output and args.in_place:
        sys.exit("--output 与 --in-place 不能同时用")
    if args.in_place:
        target = note
    elif args.output:
        target = Path(args.output)
    else:
        target = note.with_name(note.stem + "-r2.md")
    target.write_text(new_text, encoding="utf-8")
    print("已写入: {0}".format(target))

    # ── 附件夹体检 ──
    used = set(seen.keys())
    unused, dupes = audit_attachment_dir(note_dir, subdir, used)
    if unused:
        print("\n⚠️  上传了但笔记没引用（{0} 张）：".format(len(unused)))
        for n in unused[:10]:
            print("    {0}".format(n))
    if dupes:
        print("\n⚠️  内容完全相同的重复图片：")
        for group in dupes:
            print("    {0}".format("  =  ".join(group)))

    # ── URL 校验 ──
    if args.check:
        print("\n=== URL 校验（{0} 条）===".format(len(seen)))
        items = [(url, note_dir / subdir / name) for name, url in seen.items()]
        bad = 0
        for url, status, extra in verify(items):
            if status != "OK":
                bad += 1
            mark = "✅" if status == "OK" else ("⚠️" if status == "SIZE" else "❌")
            print("  {0} {1:>4}  {2:<28} {3}".format(
                mark, status, Path(url).name[:26], extra))
        print()
        if bad == 0:
            print("全部通过 ✅")
        else:
            print("有 {0} 条异常，请检查上面的明细 ❌".format(bad))
            sys.exit(1)


if __name__ == "__main__":
    main()
