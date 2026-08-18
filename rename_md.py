import sys
from pathlib import Path


def main():
    if len(sys.argv) > 1:
        root = Path(sys.argv[1]).resolve()
    else:
        root = Path.cwd().resolve()
        if (root / "content").is_dir():
            root = root / "content"
    if not root.is_dir():
        print("Directory not found: " + str(root))
        return 1

    files = sorted(root.rglob("article.md"))
    renamed = 0
    skipped = 0
    for old in files:
        new = old.with_name("index.md")
        if new.exists():
            print("SKIP (index.md exists): " + str(old))
            skipped += 1
            continue
        old.rename(new)
        print("RENAMED: " + str(old) + " -> " + str(new))
        renamed += 1

    print("done: renamed={} skipped={}".format(renamed, skipped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
