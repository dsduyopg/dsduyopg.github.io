import json
import sys
from datetime import datetime
from pathlib import Path


def ensure_title(path):
    raw = path.read_text(encoding="utf-8")
    text = raw.lstrip("\ufeff")
    title = path.parent.name
    lines = text.splitlines(keepends=True)

    if text.startswith("---"):
        end = None
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end = i
                break
        if end is None:
            return False
        body = lines[1:end]
        if any(line.strip().startswith("title:") for line in body):
            return False
        new_lines = (
            lines[:1]
            + ['title: ' + json.dumps(title, ensure_ascii=False) + "\n"]
            + body
            + lines[end:]
        )
    else:
        date = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")
        front = (
            "---\n"
            + "title: " + json.dumps(title, ensure_ascii=False) + "\n"
            + "date: " + date + "\n"
            + "draft: false\n"
            + "---\n"
        )
        new_lines = [front] + lines

    path.write_text("".join(new_lines), encoding="utf-8")
    return True


def main():
    root = Path.cwd() / "content" / "posts"
    if not root.is_dir():
        print("Directory not found: " + str(root))
        return 1
    changed = 0
    skipped = 0
    for path in sorted(root.rglob("index.md")):
        if ensure_title(path):
            print("TITLE ADDED: " + str(path))
            changed += 1
        else:
            skipped += 1
    print("done: added={} skipped={}".format(changed, skipped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
