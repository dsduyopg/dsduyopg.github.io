#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 posts 里的文章移动到专栏(支持批量)
================================
用法 / Usage:
  交互模式(推荐,双击 bat 等同):
    python move_to_column.py --blog D:\my-blog

  非交互模式(批量,文章名用逗号分隔):
    python move_to_column.py --blog D:\my-blog --post "文章A,文章B" --column "专栏名" --yes

功能:
  - 交互模式输入编号支持批量:空格或逗号分隔,如 "2 3 5" 或 "2,3,5"
  - 目标专栏不存在时自动创建(并生成 _index.md)
  - 移动前检测占用,被占用的文章跳过并提示
  - 专栏里已存在同名文章的自动跳过
  - 结束后汇总:成功 / 跳过 / 占用
"""
import argparse
import os
import re
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
        if name == "_index.md":
            continue
        full = os.path.join(posts_dir, name)
        if os.path.isdir(full) and any(f.lower().endswith(".md") for f in os.listdir(full)):
            result[name] = full
        elif full.lower().endswith(".md"):
            result[name] = full
    return result


def list_columns(root):
    """返回现有专栏名列表"""
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
    """返回被占用的文件列表(重命名探测法)"""
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
            os.rename(probe, p)
        except OSError:
            locked.append(p)
    return locked


def ask(prompt):
    """带 EOF 保护的输入"""
    try:
        return input(prompt)
    except EOFError:
        print("\n已取消。")
        sys.exit(0)


def parse_multi(raw, names):
    """解析批量编号输入(空格/逗号分隔),返回选中的文章名列表(去重保序)"""
    selected = []
    seen = set()
    for token in re.split(r"[,，\s]+", raw.strip()):
        if not token:
            continue
        if token.isdigit():
            i = int(token)
            if 1 <= i <= len(names):
                name = names[i - 1]
                if name not in seen:
                    selected.append(name)
                    seen.add(name)
            else:
                print(f"  [忽略] 无效编号 {token}(范围 1~{len(names)})")
        else:
            print(f"  [忽略] 无法识别: {token}")
    return selected


def main():
    parser = argparse.ArgumentParser(description="把 posts 里的文章移动到专栏(支持批量)")
    parser.add_argument("--blog", default="", help="博客根目录(含 content/posts),默认取脚本所在目录")
    parser.add_argument("--post", default="", help="要移动的文章名,多个用逗号分隔,如 \"文章A,文章B\"")
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

    # ---------- 选择文章(支持批量) ----------
    names = sorted(posts)
    post_names = []
    if args.post:
        for p in args.post.split(","):
            p = p.strip()
            if p in posts:
                post_names.append(p)
            else:
                print(f"[忽略] posts 里没有这篇文章: {p}")
    else:
        print("\n选择要移动的文章(可输入多个编号,用空格或逗号分隔,如: 2 3 5):")
        for i, n in enumerate(names, 1):
            print(f"  [{i}] {n}")
        raw = ask("请输入编号: ")
        post_names = parse_multi(raw, names)

    if not post_names:
        print("[错误] 未选择任何文章。")
        sys.exit(1)

    # ---------- 选择/输入专栏 ----------
    column_name = args.column
    if not column_name:
        print("\n选择目标专栏(或输入新专栏名):")
        for i, c in enumerate(columns, 1):
            print(f"  [{i}] {c}")
        try:
            sel = ask("请输入编号,或直接输入新专栏名: ").strip()
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

    # ---------- 预检:已存在 / 被占用 ----------
    to_move = []
    exists_list = []
    locked_list = {}
    for name in post_names:
        src = posts[name]
        dest = os.path.join(col_path, name)
        if os.path.exists(dest):
            exists_list.append(name)
            continue
        locked = check_lock(src)
        if locked:
            locked_list[name] = locked
            continue
        to_move.append((name, src, dest))

    print(line)
    if to_move:
        print(f"将移动 {len(to_move)} 篇文章到专栏「{column_name}」:")
        for name, _, _ in to_move:
            print(f"  - {name}")
    if exists_list:
        print(f"\n[跳过] 专栏里已存在同名文章({len(exists_list)} 篇): {', '.join(exists_list)}")
    if locked_list:
        print(f"\n[占用] 以下文章正被其他程序占用({len(locked_list)} 篇),本次不移动:")
        for name, locked in locked_list.items():
            print(f"  - {name}: {os.path.relpath(locked[0], root)}")

    if not to_move:
        print("\n没有可移动的文章(全部被跳过)。")
        return 0

    if not args.yes:
        confirm = ask("\n确认移动以上文章? (y/N): ").strip().lower()
        if confirm not in ("y", "yes"):
            print("已取消。")
            return 0

    # ---------- 批量执行 ----------
    ok_count = 0
    fail_list = []
    for name, src, dest in to_move:
        try:
            shutil.move(src, dest)
            ok_count += 1
            print(f"  ✅ {name} -> 专栏/{column_name}/")
        except (PermissionError, OSError) as e:
            fail_list.append((name, e))

    print(line)
    print(f"✅ 完成:成功移动 {ok_count} 篇")
    if exists_list:
        print(f"   已存在跳过: {len(exists_list)} 篇")
    if locked_list:
        print(f"   被占用跳过: {len(locked_list)} 篇(关闭占用程序后可重试)")
    if fail_list:
        print(f"   ❌ 移动失败: {len(fail_list)} 篇")
        for name, e in fail_list:
            print(f"      - {name}: {e}")
    print("   提示:git auto-sync 会自动提交本次移动,如需回退可 git revert。")
    return 0 if not fail_list else 1


if __name__ == "__main__":
    sys.exit(main())
