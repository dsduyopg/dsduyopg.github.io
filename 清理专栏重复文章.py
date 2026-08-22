#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理 posts 与专栏重复文章脚本
================================
作用:
  1. 统计 content/posts 与 content/专栏/ 下所有专栏里的重复文章(按目录名/文件名比对)
  2. 预览重复清单,或在确认后删除 posts 里的重复副本(专栏里的版本保留)

用法:
  python 清理专栏重复文章.py             # 只统计 + 预览,不删除
  python 清理专栏重复文章.py --yes       # 统计并直接删除 posts 里的重复副本
  python 清理专栏重复文章.py --backup    # 统计 + 预览,并说明会先备份再删(需配合 --yes)
  python 清理专栏重复文章.py --yes --backup   # 删除前先把副本移动(备份)到 .专栏清理备份_<时间戳>/

说明:
  - 重复判定:文章所在目录名(或 .md 文件名)在专栏与 posts 中同时存在
  - 只删除 posts 一侧,专栏内容一律不动
  - 项目已接入 git auto-sync,删除后可用 git 恢复;使用 --backup 则另有本地备份
"""
import argparse
import os
import shutil
import sys
import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
POSTS_DIR = os.path.join(ROOT, "content", "posts")
COLUMNS_DIR = os.path.join(ROOT, "content", "专栏")


def list_posts_articles():
    """返回 {文章名: 目录/文件绝对路径},扫描 posts 顶层下的文章(目录内含 md,或直接是 md 文件)"""
    result = {}
    if not os.path.isdir(POSTS_DIR):
        return result
    for name in os.listdir(POSTS_DIR):
        full = os.path.join(POSTS_DIR, name)
        if os.path.isdir(full):
            # 目录型文章:目录内直接存在 .md 文件才算文章
            if any(f.lower().endswith(".md") for f in os.listdir(full)):
                result[name] = full
        elif full.lower().endswith(".md"):
            # 文件型文章
            result[name] = full
    return result


def list_column_articles():
    """返回 {文章名: 绝对路径},扫描 content/专栏/<专栏名>/ 下的所有文章"""
    result = {}
    if not os.path.isdir(COLUMNS_DIR):
        return result
    for col_name in os.listdir(COLUMNS_DIR):
        col_path = os.path.join(COLUMNS_DIR, col_name)
        if not os.path.isdir(col_path):
            continue  # 跳过直接放在 专栏/ 下的散文件(如总览说明)
        for item in os.listdir(col_path):
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
    parser.add_argument("--yes", action="store_true", help="确认后直接删除 posts 里的重复副本(默认只预览)")
    parser.add_argument("--backup", action="store_true", help="删除前先把副本移动到 .专栏清理备份_<时间戳>/ 而非直接删除")
    args = parser.parse_args()

    posts = list_posts_articles()
    columns = list_column_articles()

    print("=" * 60)
    print(f"posts 文章数    : {len(posts)}")
    print(f"专栏文章数      : {len(columns)}")

    # 找出重复:posts 文章名 出现在专栏中
    dup_names = sorted(set(posts) & set(columns))
    print("=" * 60)
    if not dup_names:
        print("✅ 没有发现重复文章,无需处理。")
        return 0

    print(f"⚠️  发现 {len(dup_names)} 篇重复文章(posts 与专栏各有一份):\n")
    total_size = 0
    for name in dup_names:
        p_size = dir_size(posts[name])
        total_size += p_size
        print(f"  - {name}")
        print(f"      posts 副本 : {os.path.relpath(posts[name], ROOT)}  ({fmt_size(p_size)})")
        print(f"      专栏版本   : {os.path.relpath(columns[name], ROOT)}")

    print("-" * 60)
    print(f"预计删除 posts 副本合计占用: {fmt_size(total_size)}")

    if not args.yes:
        print("\n(预览模式,未删除任何文件。确认删除请加 --yes,如:")
        print('  python "清理专栏重复文章.py" --yes  或  --yes --backup)')
        return 0

    # 备份目录
    backup_dir = None
    if args.backup:
        backup_dir = os.path.join(ROOT, ".专栏清理备份_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
        os.makedirs(backup_dir, exist_ok=True)

    deleted = 0
    for name in dup_names:
        src = posts[name]
        if backup_dir:
            dst = os.path.join(backup_dir, name)
            shutil.move(src, dst)
            print(f"  [备份] {name} -> {os.path.relpath(dst, ROOT)}")
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
        print(f"   备份位置: {os.path.relpath(backup_dir, ROOT)}(确认无误后可手动删除该备份目录)")
    print("   提示:删除操作已由 git auto-sync 记录,如需恢复可执行 git revert / git checkout。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
