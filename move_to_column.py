#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 posts 里的文章移动到专栏
================================
用法 / Usage:
  交互模式(推荐,双击 bat 等同):
    python move_to_column.py --blog D:\my-blog

  非交互模式:
    python move_to_column.py --blog D:\my-blog --post "文章名" --column "专栏名" --yes

功能:
  - 列出 posts 里的文章和现有专栏,交互选择
  - 目标专栏不存在时自动创建(并生成 _index.md)
  - 移动前检测文件是否被占用(被其他程序打开会提示,不移动)
  - 移动后自动验证
"""
import argparse
import os
import shutil
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass


def find_blog_dir(args_dir):
    if args_dir:
        d = os.path.abspath(args_dir)
    else:
        d = os.path.dirname(os.path.abspath(__file__))
    if not os.path.isdir(os.path.join(d, "content", "posts")):
        print(f"[错误] 在 {d} 下没有找到 content/posts 目录,请用 --blog 指定博客目录")
        sys.exit(2)
    return d


def list_posts(root):
    """返回 {文章名: 绝对路径}"""
    result = {}
    posts_dir = os.path.join(root, "content", "posts")
    for name in os.listdir(posts_dir):
        full = os.path.join(posts_dir, name)
        if os.path.isdir(full) and any(f.lower().endswith(".md") for f in os.listdir(full)):
            result[name] = full
        elif full.lower().endswith(".md"):
            result[name] = full
    return result


def list_columns(root):
    """返回现有专栏名列表(content/专栏/ 下有 _index.md 或含文章的目录)"""
    cols_dir = os.path.join(root, "content", "专栏")
    result = []
    if os.path.isdir(cols_dir):
        for name in os.listdir(cols_dir):
            if os.path.isdir(os.path.join(cols_dir, name)):
                result.append(name)
    return sorted(result)


def ensure_column(root, name):
    """专栏不存在则创建目录 + _index.md,返回专栏目录路径"""
    col_path = os.path.join(root, "content", "专栏", name)
    os.makedirs(col_path, exist_ok=True)
    idx = os.path.join(col_path, "_index.md")
    if not os.path.exists(idx):
        with open(idx, "w", encoding="utf-8") as f:
            f.write('---\n')
            f.write(f'title: "{name}"\n')
            f.write('description: ""\n')
            f.write('draft: false\n')
            f.write('---\n')
            f.write('\n')
    return col_path


def check_lock(path):
    """返回被占用的文件列表:通过"重命名探测"判断(重命名需要删除权限,
    文件被其他程序以非删除共享方式打开时会失败)"""
    locked = []
    targets = []
    if os.path.isdir(path):
        for root, _, files in os.walk(path):
            for f in files:
                targets.append(os.path.join(root, f))
    else:
        targets.append(path)
    for p in targets:
        probe = p + ".__lockprobe__"
        try:
            os.rename(p, probe)
            os.rename(probe, p)  # 改名成功说明没被锁,立刻改回
        except OSError:
            locked.append(p)
    return locked


def main():
    parser = argparse.ArgumentParser(description="把 posts 里的文章移动到专栏")
    parser.add_argument("--blog", default="", help="博客根目录(含 content/posts),默认取脚本所在目录")
    parser.add_argument("--post", default="", help="要移动的文章名(posts 下的目录名),省略则进入交互模式")
    parser.add_argument("--column", default="", help="目标专栏名,不存在会自动创建")
    parser.add_argument("--yes", action="store_true", help="跳过确认")
    args = parser.parse_args()

    root = find_blog_dir(args.blog)
    posts = list_posts(root)
    columns = list_columns(root)

    line = "=" * 60
    print(line)
    print(f"博客目录: {root}")
    print(f"posts 文章数: {len(posts)}   现有专栏: {len(columns)}")
    print(line)

    # ---------- 选择文章 ----------
    post_name = args.post
    if not post_name:
        print("\n选择要移动的文章:")
        names = sorted(posts)
        for i, n in enumerate(names, 1):
            print(f"  [{i}] {n}")
        try:
            sel = input("请输入编号: ").strip()
            post_name = names[int(sel) - 1]
        except (ValueError, IndexError):
            print("[错误] 无效编号")
            sys.exit(1)
    if post_name not in posts:
        print(f"[错误] posts 里没有这篇文章: {post_name}")
        sys.exit(1)
    src = posts[post_name]

    # ---------- 选择/输入专栏 ----------
    column_name = args.column
    if not column_name:
        print("\n选择目标专栏(或输入新专栏名):")
        for i, c in enumerate(columns, 1):
            print(f"  [{i}] {c}")
        try:
            sel = input("请输入编号,或直接输入新专栏名: ").strip()
            if sel.isdigit():
                column_name = columns[int(sel) - 1]
            elif sel:
                column_name = sel
            else:
                print("[错误] 未输入专栏")
                sys.exit(1)
        except (ValueError, IndexError):
            print("[错误] 无效编号")
            sys.exit(1)

    col_path = ensure_column(root, column_name)
    dest = os.path.join(col_path, post_name)

    if os.path.exists(dest):
        print(f"[提示] 专栏里已存在同名文章: {post_name},跳过(如需要请先手动处理)。")
        return 0

    # ---------- 检测占用 ----------
    locked = check_lock(src)
    if locked:
        print("\n[提示] 以下文件正被其他程序占用,无法移动:")
        for p in locked[:10]:
            print(f"   - {os.path.relpath(p, root)}")
        print("       请关闭打开它们的程序(如 WPS、图片查看器、资源管理器)后重试。")
        return 1

    # ---------- 确认 ----------
    print(line)
    print(f"将移动: {os.path.relpath(src, root)}")
    print(f"    到: {os.path.relpath(dest, root)}")
    if not args.yes:
        confirm = input("确认移动? (y/N): ").strip().lower()
        if confirm not in ("y", "yes"):
            print("已取消。")
            return 0

    # ---------- 执行 ----------
    try:
        shutil.move(src, dest)
    except (PermissionError, OSError) as e:
        print("\n[错误] 移动失败,可能有文件正被其他程序占用:")
        locked = check_lock(src)
        if locked:
            for p in locked[:10]:
                print(f"   - {os.path.relpath(p, root)}")
            print("       请关闭打开它们的程序(如 WPS、图片查看器、资源管理器、Typora 等)后重试。")
        else:
            print(f"       详情: {e}")
        return 1
    ok_src = not os.path.exists(src)
    ok_dst = os.path.isdir(dest) if os.path.isdir(dest) else os.path.exists(dest)
    if ok_src and ok_dst:
        print(f"✅ 移动成功: {post_name} -> 专栏/{column_name}/")
        print("   文章已可在「专栏 → " + column_name + "」中查看,主页也会正常显示。")
        print("   提示:git auto-sync 会自动提交本次移动,如需回退可 git revert。")
        return 0
    else:
        print("[错误] 移动后验证失败,请检查文件状态。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
