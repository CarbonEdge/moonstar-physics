"""Run pipelines/ml_theory_synthesis.yaml on a data summary and save the result.

Usage: MOONSTAR_AUTH_TOKEN=<token> python scripts/run_ml_theory.py papers/rsna-knee-training-scaling
Reads <dir>/data-summary.md; writes <dir>/theory.md and <dir>/theory_run.json.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
import _pipeline_client as pc  # noqa: E402

ROOT = Path(__file__).parent.parent


async def main(d: Path) -> int:
    spec = pc.render_pipeline_yaml(ROOT / "pipelines" / "ml_theory_synthesis.yaml", ROOT / "pipelines" / "models.json")
    summary = (d / "data-summary.md").read_text(encoding="utf-8")
    pc._MAX_POLLS = 300
    async with httpx.AsyncClient(timeout=60) as client:
        res = await pc.submit_and_wait(
            client, os.environ.get("MOONSTAR_GATEWAY_URL", "http://localhost:8000"),
            os.environ["MOONSTAR_AUTH_TOKEN"], spec, {"data_summary": summary},
        )
    (d / "theory_run.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print("status:", res.get("status"))
    syn = pc.find_artifact(res, "synthesizer")
    if syn is None:
        print("no synthesizer artifact"); return 1
    text = syn.get("text") or syn.get("content") or json.dumps(syn, ensure_ascii=False)
    (d / "theory.md").write_text(text, encoding="utf-8")
    print(text[:300])
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(Path(sys.argv[1]))))
