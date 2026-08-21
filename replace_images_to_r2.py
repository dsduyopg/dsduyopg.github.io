#!/usr/bin/env python3
"""Replace local markdown image links with Cloudflare R2 URLs."""

import argparse
import re
import sys
import urllib.request
from pathlib import Path

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".avif"}
IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def is_remote(url):
    return url.startswith(("http://", "https://", "//", "data:"))


def local_image_path(url):
    url = url.strip().strip("\"'")
    if is_remote(url) or "://" in url:
        return None
    path = Path(url.replace("\\", "/"))
    if path.suffix.lower() not in IMAGE_EXTS:
        return None
    return path


def replace_line(line, base, prefix, slug):
    def repl(match):
        alt, target = match.group(1), match.group(2)
        path = local_image_path(target)
        if path is None:
            return match.group(0)
        url = "{0}/{1}/{2}/images/{3}".format(base, prefix, slug, path.name)
        return "![{0}]({1})".format(alt, url)

    return IMG_RE.sub(repl, line)


def process_markdown(text, base, prefix, slug):
    out_lines = []
    in_fence = False
    changed = 0
    for line in text.splitlines(keepends=True):
        ending = "\n" if line.endswith("\n") else ""
        body = line[:-len(ending)] if ending else line
        if body.strip().startswith("```"):
            in_fence = not in_fence
            out_lines.append(line)
            continue
        if in_fence:
            out_lines.append(line)
            continue
        new_body = replace_line(body, base, prefix, slug)
        if new_body != body:
            changed += 1
        out_lines.append(new_body + ending)
    return "".join(out_lines), changed


def check_r2_urls(text, base, prefix):
    prefix_url = "{0}/{1}".format(base, prefix)
    urls = sorted(set(url for _, url in IMG_RE.findall(text) if url.startswith(prefix_url)))
    bad = []
    for url in urls:
        try:
            req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
            resp = urllib.request.urlopen(req, timeout=15)
            if resp.status != 200:
                bad.append((url, resp.status))
        except Exception as exc:
            bad.append((url, str(exc)[:120]))
    return urls, bad


def main():
    parser = argparse.ArgumentParser(description="Replace local image links with R2 URLs.")
    parser.add_argument("--file", required=True, help="Markdown file to process")
    parser.add_argument("--slug", required=True, help="R2 project slug, e.g. telegram_rsyc_twoway")
    parser.add_argument("--base", default="https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev")
    parser.add_argument("--prefix", default="blog_images")
    parser.add_argument("--output", help="Output markdown path")
    parser.add_argument("--in-place", action="store_true", help="Overwrite the source file")
    parser.add_argument("--check", action="store_true", help="Verify R2 image URLs after replacement")
    args = parser.parse_args()

    source = Path(args.file)
    if not source.exists():
        sys.exit("File not found: {0}".format(source))

    text = source.read_text(encoding="utf-8-sig")
    output_text, changed = process_markdown(text, args.base, args.prefix, args.slug)

    if args.output and args.in_place:
        sys.exit("Use either --output or --in-place, not both")
    if args.output:
        target = Path(args.output)
    elif args.in_place:
        target = source
    else:
        target = source.with_name(source.stem + "-r2.md")

    target.write_text(output_text, encoding="utf-8")
    print("Replaced {0} local image link(s) with R2 URLs".format(changed))
    print("Output: {0}".format(target))

    if args.check:
        urls, bad = check_r2_urls(output_text, args.base, args.prefix)
        print("R2 URLs checked: {0}, bad: {1}".format(len(urls), len(bad)))
        for url, reason in bad[:10]:
            print("BAD {0}: {1}".format(url, reason))
        if bad:
            sys.exit(1)


if __name__ == "__main__":
    main()
