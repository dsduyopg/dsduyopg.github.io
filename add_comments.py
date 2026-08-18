from pathlib import Path


def main():
    root = Path.cwd() / "content" / "posts"
    changed = 0
    for path in sorted(root.rglob("index.md")):
        text = path.read_text(encoding="utf-8").lstrip("\ufeff")
        lines = text.splitlines(keepends=True)
        if not text.startswith("---"):
            continue
        end = None
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end = i
                break
        if end is None:
            continue
        if any(line.strip().startswith("comments:") for line in lines[1:end]):
            continue
        lines.insert(1, "comments: true\n")
        path.write_text("".join(lines), encoding="utf-8")
        changed += 1
    print("done: comments_added={}".format(changed))


if __name__ == "__main__":
    main()
