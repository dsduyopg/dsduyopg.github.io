#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Clean up duplicate articles between content/posts and content/专栏 (columns).
用法 / Usage:
  python cleanup_dup_articles.py                 # 统计 + 预览,不删除 (preview only)
  python cleanup_dup_articles.py --yes           # 统计并删除 posts 里的重复副本 (delete)
  python cleanup_dup_articles.py --yes --backup  # 删除前先备份到 .专栏清理备份_<时间戳>/
  python cleanup_dup_articles.py --blog D:/my-blog --yes   # 指定博客目录
逻辑 / Logic:
  - 对比 content/posts 与 content/专栏/<专栏名>/ 下的文章(按目录名或 .md 文件名)
  - 只删除 posts 一侧的副本,专栏内容一律不动
  - 项目已接入 git auto-sync,删除后可用 git 恢复
"""
import argparse
import datetime
import os
import shutil
import sys

# Windows cmd 下保证中文输出不乱码(配合 bat 中的 chcp 65001)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass


def find_blog_dir(args_dir):
    """优先用 --blog 参数;否则用脚本所在目录;否则报错"""
    if args_dir:
        d = os.path.abspath(args_dir)
    else:
        d = os.path.dirname(os.path.abspath(__file__))
    if not os.path.isdir(os.path.join(d, "content", "posts")):
        print(f"[错误] 在 {d} 下没有找到 content/posts 目录。")
        print("        请用 --blog 参数指定博客目录,例如:")
        print('        python cleanup_dup_articles.py --blog D:\\my-blog --yes')
        sys.exit(2)
    return d


def list_posts_articles(root):
    """返回 {文章名: 目录/文件绝对路径},扫描 posts 顶层下的文章(排除 _index.md)"""
    result = {}
    posts_dir = os.path.join(root, "content", "posts")
    for name in os.listdir(posts_dir):
        if name == "_index.md":
            continue
        full = os.path.join(posts_dir, name)
        if os.path.isdir(full):
            if any(f.lower().endswith(".md") for f in os.listdir(full)):
                result[name] = full
        elif full.lower().endswith(".md"):
            result[name] = full
    return result


def list_column_articles(root):
    """返回 {文章名: 绝对路径},扫描 content/专栏/<专栏名>/ 下的所有文章(排除 _index.md)"""
    result = {}
    cols_dir = os.path.join(root, "content", "专栏")
    if not os.path.isdir(cols_dir):
        return result
    for col_name in os.listdir(cols_dir):
        col_path = os.path.join(cols_dir, col_name)
        if not os.path.isdir(col_path):
            continue
        for item in os.listdir(col_path):
            if item == "_index.md":
                continue
            full = os.path.join(col_path, item)
            if os.path.isdir(full):
                if any(f.lower().endswith(".md") for f in os.listdir(full)):
                    result[item] = full
            elif full.lower().endswith(".md"):
                result[item] = full
    return result


def dir_size(path):
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, f))
            except OSError:
                pass
    return total


def fmt_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n} B"


def main():
    parser = argparse.ArgumentParser(description="统计并清理 posts 与专栏的重复文章")
    parser.add_argument("--blog", default="", help="博客根目录(含 content/posts),默认取脚本所在目录")
    parser.add_argument("--yes", action="store_true", help="确认后直接删除 posts 里的重复副本(默认只预览)")
    parser.add_argument("--backup", action="store_true", help="删除前先把副本移动到 .专栏清理备份_<时间戳>/ 而非直接删除")
    args = parser.parse_args()

    root = find_blog_dir(args.blog)
    posts = list_posts_articles(root)
    columns = list_column_articles(root)

    line = "=" * 60
    print(line)
    print(f"博客目录        : {root}")
    print(f"posts 文章数    : {len(posts)}")
    print(f"专栏文章数      : {len(columns)}")

    dup_names = sorted(set(posts) & set(columns))
    print(line)
    if not dup_names:
        print("✅ 没有发现重复文章,无需处理。")
        return 0

    print(f"⚠️  发现 {len(dup_names)} 篇重复文章(posts 与专栏各有一份):\n")
    total_size = 0
    for name in dup_names:
        p_size = dir_size(posts[name])
        total_size += p_size
        print(f"  - {name}")
        print(f"      posts 副本 : {os.path.relpath(posts[name], root)}  ({fmt_size(p_size)})")
        print(f"      专栏版本   : {os.path.relpath(columns[name], root)}")

    print("-" * 60)
    print(f"预计删除 posts 副本合计占用: {fmt_size(total_size)}")

    if not args.yes:
        print("\n(预览模式,未删除任何文件。确认删除请加 --yes)")
        return 0

    backup_dir = None
    if args.backup:
        backup_dir = os.path.join(root, ".专栏清理备份_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
        os.makedirs(backup_dir, exist_ok=True)

    deleted = 0
    for name in dup_names:
        src = posts[name]
        if backup_dir:
            dst = os.path.join(backup_dir, name)
            shutil.move(src, dst)
            print(f"  [备份] {name} -> {os.path.relpath(dst, root)}")
        else:
            if os.path.isdir(src):
                shutil.rmtree(src)
            else:
                os.remove(src)
            print(f"  [删除] posts/{name}")
        deleted += 1

    print("-" * 60)
    print(f"✅ 已处理 {deleted} 篇重复文章,posts 里与专栏重复的副本已清理,专栏内容不受影响。")
    if backup_dir:
        print(f"   备份位置: {os.path.relpath(backup_dir, root)}(确认无误后可手动删除该备份目录)")
    print("   提示:删除操作已由 git auto-sync 记录,如需恢复可执行 git revert / git checkout。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
