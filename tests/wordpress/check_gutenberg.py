"""Opens every page and theme pattern in the real block editor and reports what Gutenberg calls invalid."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from wp_browser import Browser


def main(base: str, ids: list[int], slug: str) -> int:
    browser = Browser(base)
    browser.login()
    failures = 0
    for post in ids:
        ready = browser.open_editor(post)
        if not ready:
            print(f"post {post}: the editor did not become ready")
            failures += 1
            continue
        browser.wait(1500)
        total, bad = browser.invalid_in_editor()
        print(f"post {post}: {total} blocks, {len(bad)} invalid")
        failures += len(bad)
        for item in bad[:4]:
            print(json.dumps(item)[:1800])
    for pattern in browser.patterns():
        if not pattern["name"].startswith(f"{slug}/"):
            continue
        total, bad = browser.parse_report(pattern["content"])
        print(f"pattern {pattern['name']}: {total} blocks, {len(bad)} invalid")
        failures += len(bad)
        for item in bad[:3]:
            print(json.dumps(item)[:1800])
    print("TOTAL INVALID:", failures)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], [int(v) for v in sys.argv[2].split(",")], sys.argv[3]))
