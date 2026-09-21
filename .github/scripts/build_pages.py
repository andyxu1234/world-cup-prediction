#!/usr/bin/env python3
"""Build the GitHub Pages site from docs/demo.html.

Layout produced in <out_dir>:
    index.html              -> docs/demo.html (asset paths rewritten)
    demo.html               -> same file, for old links
    screenshot/*.jpg        -> docs/screenshot
    assets/aimodels/*.svg   -> client/src/assets/aimodels
    .nojekyll               -> skip Jekyll processing

Usage:
    python .github/scripts/build_pages.py [out_dir]   # default: site
"""

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

REWRITES = [
    # demo.html lives in docs/, so it points one level up into client/ and
    # double-prefixes docs/ in the lightbox handler. Both break on Pages.
    ("../client/src/assets/aimodels/", "assets/aimodels/"),
    ("docs/screenshot/", "screenshot/"),
]


def build(out_dir: Path) -> None:
    src_html = ROOT / "docs" / "demo.html"
    if not src_html.is_file():
        sys.exit(f"missing source file: {src_html}")

    html = src_html.read_text(encoding="utf-8")
    for old, new in REWRITES:
        html = html.replace(old, new)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    (out_dir / "index.html").write_text(html, encoding="utf-8")
    (out_dir / "demo.html").write_text(html, encoding="utf-8")
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")

    shutil.copytree(ROOT / "docs" / "screenshot", out_dir / "screenshot")
    shutil.copytree(
        ROOT / "client" / "src" / "assets" / "aimodels",
        out_dir / "assets" / "aimodels",
    )

    print(f"built {out_dir.relative_to(ROOT) if out_dir.is_relative_to(ROOT) else out_dir}")


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "site"
    build(target.resolve())
