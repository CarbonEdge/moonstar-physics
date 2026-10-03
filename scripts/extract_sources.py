"""Distil pulled Kaggle notebooks into compact research digests (markdown narrative + key config lines).

Usage: python scripts/extract_sources.py <dir-with-pulled-notebooks> <out-dir>
Each <dir>/<slug>/<slug>.ipynb -> <out-dir>/<slug>.md  (provenance for the research pipeline).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_MD_CAP = 14000
_CODE_CAP = 5000
_KEY = re.compile(
    r"^\s*(?:[A-Z][A-Z0-9_]{2,}\s*=|.*(?:weight|alpha|blend|rank|fold|epoch|lr|img_size|image_size|"
    r"n_slices|k_eval|crop|backbone|timm\.create_model|pooling).*=)", re.I)


def digest(nb_path: Path) -> str:
    nb = json.loads(nb_path.read_text(encoding="utf-8"))
    md = "\n\n".join("".join(c["source"]).strip() for c in nb["cells"] if c["cell_type"] == "markdown")
    code_lines: list[str] = []
    for c in nb["cells"]:
        if c["cell_type"] != "code":
            continue
        for line in "".join(c["source"]).splitlines():
            if len(line) < 160 and _KEY.match(line) and not line.lstrip().startswith(("#", "print")):
                code_lines.append(line.strip())
    seen, uniq = set(), []
    for l in code_lines:
        if l not in seen:
            seen.add(l)
            uniq.append(l)
    code = "\n".join(uniq)
    return f"## Narrative (markdown cells)\n{md[:_MD_CAP]}\n\n## Key configuration lines from code\n{code[:_CODE_CAP]}\n"


def main(src: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for nb in sorted(src.glob("*/*.ipynb")):
        slug = nb.parent.name
        (out / f"{slug}.md").write_text(f"# Source: kaggle notebook `{slug}`\n\n" + digest(nb), encoding="utf-8")
        print("wrote", out / f"{slug}.md")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
