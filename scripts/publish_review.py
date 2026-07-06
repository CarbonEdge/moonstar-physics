"""One-shot CLI: publish a full review for one paper.

Runs the paper's PDF through map-reduce summarization, tests every curated
hypothesis in papers/<slug>.yaml against the physics_hypothesis pipeline,
and writes reviews/<slug>/review.md (+ review.pdf via pandoc, if installed),
reviews/<slug>/review_data.json (consumed by scripts/build_site.py), and
reviews/<slug>/scienceopen_metadata.json (a copy-paste sidecar for manually
submitting the review to ScienceOpen).

Usage:
    MOONSTAR_AUTH_TOKEN=<token> python scripts/publish_review.py geometric-unity

Env vars:
    MOONSTAR_GATEWAY_URL   default http://localhost:8000
    MOONSTAR_AUTH_TOKEN    required — get one via `python -m moonstar_gateway.cli seed-user`

Requires `pdftotext` (poppler-utils) on PATH. `pandoc` + the `typst` PDF
engine are optional — PDF export is skipped with a warning if either isn't
installed (`scoop install pandoc typst` on Windows).

Reads `scienceopen_author.json` (repo root) for the author/ORCID block in
the metadata sidecar — fill in your real ORCID iD there before first use.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))
from moonstar_physics.paper_review.chunking import ChunkingError, chunk_text
from moonstar_physics.paper_review.markdown_render import render_review_markdown
from moonstar_physics.paper_review.paper_spec import load_paper_spec
from moonstar_physics.paper_review.review_model import HypothesisResult, ReviewData
from moonstar_physics.paper_review.scienceopen import build_scienceopen_metadata

sys.path.insert(0, str(Path(__file__).parent))
from _pipeline_client import (  # noqa: E402
    PipelineRunError,
    extract_verdict,
    find_artifact,
    render_pipeline_yaml,
    strip_leading_verdict_line,
    submit_and_wait,
)

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

_ROOT_DIR = Path(__file__).parent.parent
_PIPELINES_DIR = _ROOT_DIR / "pipelines"
_PAPERS_DIR = _ROOT_DIR / "papers"
_REVIEWS_DIR = _ROOT_DIR / "reviews"
_MODELS_PATH = _PIPELINES_DIR / "models.json"
_AUTHOR_PATH = _ROOT_DIR / "scienceopen_author.json"

_WAVE1_TRANSFORM_NAMES = ["conservation_check", "qm_calculation", "reference_lookup", "dimension_check"]


def _extract_pdf_text(pdf_path: Path) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", "-enc", "UTF-8", str(pdf_path), "-"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"pdftotext failed on {pdf_path}: {result.stderr}")
    return result.stdout


async def _summarize_paper(
    client: httpx.AsyncClient, gateway_url: str, token: str, title: str, text: str
) -> str:
    chunks = chunk_text(text)
    if not chunks:
        raise RuntimeError(f"no text extracted from PDF for '{title}'")

    chunk_yaml = render_pipeline_yaml(_PIPELINES_DIR / "paper_chunk_summary.yaml", _MODELS_PATH)
    chunk_summaries: list[str] = []
    for i, chunk in enumerate(chunks, start=1):
        print(f"Summarizing chunk {i}/{len(chunks)} ...")
        chunk_input = {"title": title, "chunk_index": i, "total_chunks": len(chunks), "chunk_text": chunk}

        # First attempt
        status = None
        first_error = None
        try:
            status = await submit_and_wait(client, gateway_url, token, chunk_yaml, chunk_input)
        except (httpx.HTTPError, PipelineRunError) as exc:
            first_error = exc

        # Check if first attempt failed (by exception or non-completed status)
        if first_error is not None or (status is not None and status.get("status") != "completed"):
            print(f"Chunk {i}/{len(chunks)} summary failed, retrying once ...")
            # Retry attempt
            status = None
            try:
                status = await submit_and_wait(client, gateway_url, token, chunk_yaml, chunk_input)
            except (httpx.HTTPError, PipelineRunError) as exc:
                raise PipelineRunError(f"chunk {i}/{len(chunks)} summary failed twice: {exc}")

            # Check if retry succeeded
            if status.get("status") != "completed":
                raise PipelineRunError(
                    f"chunk {i}/{len(chunks)} summary failed twice: status={status.get('status')}"
                )

        artifact = find_artifact(status, "chunk_summarizer") or {}
        chunk_summaries.append(artifact.get("response", ""))

    reduce_yaml = render_pipeline_yaml(_PIPELINES_DIR / "paper_reduce_summary.yaml", _MODELS_PATH)
    print("Reducing chunk summaries into final paper summary ...")
    status = await submit_and_wait(
        client, gateway_url, token, reduce_yaml, {"title": title, "chunk_summaries": chunk_summaries}
    )
    if status.get("status") != "completed":
        raise PipelineRunError(f"reduce-summary step failed: status={status.get('status')}")
    artifact = find_artifact(status, "reduce_summarizer") or {}
    return artifact.get("response", "")


async def _test_hypothesis(
    client: httpx.AsyncClient, gateway_url: str, token: str, slug: str, hypothesis: str, index: int
) -> HypothesisResult:
    hypothesis_yaml = render_pipeline_yaml(_PIPELINES_DIR / "physics_hypothesis.yaml", _MODELS_PATH)
    print(f"Testing hypothesis {index}: {hypothesis[:70]}...")
    try:
        status = await submit_and_wait(client, gateway_url, token, hypothesis_yaml, {"hypothesis": hypothesis})
    except (httpx.HTTPError, PipelineRunError) as exc:
        return HypothesisResult(hypothesis=hypothesis, verdict="ERROR", writeup=str(exc), wave1_results={}, run_path=None)

    runs_dir = _REVIEWS_DIR / slug / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    session_id = status.get("session_id", f"unknown-{index}")
    (runs_dir / f"{session_id}.json").write_text(
        json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    run_path = f"runs/{session_id}.json"

    if status.get("status") != "completed":
        return HypothesisResult(
            hypothesis=hypothesis,
            verdict="ERROR",
            writeup=f"pipeline session {status.get('status')} — see raw run data",
            wave1_results={},
            run_path=run_path,
        )

    synthesizer = find_artifact(status, "synthesizer") or {}
    raw_writeup = synthesizer.get("response", "")
    wave1_results = {name: (find_artifact(status, name) or {}) for name in _WAVE1_TRANSFORM_NAMES}
    return HypothesisResult(
        hypothesis=hypothesis,
        verdict=extract_verdict(raw_writeup),
        writeup=strip_leading_verdict_line(raw_writeup),
        wave1_results=wave1_results,
        run_path=run_path,
    )


async def _publish(slug: str) -> int:
    gateway_url = os.environ.get("MOONSTAR_GATEWAY_URL", "http://localhost:8000")
    token = os.environ.get("MOONSTAR_AUTH_TOKEN")
    if not token:
        print("ERROR: MOONSTAR_AUTH_TOKEN is not set", file=sys.stderr)
        return 1

    spec = load_paper_spec(_PAPERS_DIR / f"{slug}.yaml")
    text = _extract_pdf_text(_ROOT_DIR / spec.pdf)

    review_dir = _REVIEWS_DIR / slug
    review_dir.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            summary = await _summarize_paper(client, gateway_url, token, spec.title, text)
        except (ChunkingError, PipelineRunError) as exc:
            print(f"ERROR: paper summarization failed: {exc}", file=sys.stderr)
            return 1

        hypothesis_results = [
            await _test_hypothesis(client, gateway_url, token, slug, hypothesis, i)
            for i, hypothesis in enumerate(spec.hypotheses, start=1)
        ]

    review = ReviewData(
        slug=slug,
        title=spec.title,
        authors=spec.authors,
        draft_date=spec.draft_date,
        pdf_path=spec.pdf,
        source_url=spec.source_url,
        summary=summary,
        hypothesis_results=hypothesis_results,
    )

    models = json.loads(_MODELS_PATH.read_text(encoding="utf-8"))
    author = json.loads(_AUTHOR_PATH.read_text(encoding="utf-8"))

    (review_dir / "review_data.json").write_text(
        json.dumps(review.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (review_dir / "review.md").write_text(render_review_markdown(review, models), encoding="utf-8")
    print(f"Wrote {review_dir / 'review.md'}")

    metadata = build_scienceopen_metadata(review, author, models)
    (review_dir / "scienceopen_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Wrote {review_dir / 'scienceopen_metadata.json'}")

    if shutil.which("pandoc"):
        pandoc_result = subprocess.run(
            [
                "pandoc",
                str(review_dir / "review.md"),
                "--pdf-engine=typst",
                "-o",
                str(review_dir / "review.pdf"),
            ],
            capture_output=True,
            text=True,
        )
        if pandoc_result.returncode == 0:
            print(f"Wrote {review_dir / 'review.pdf'}")
        else:
            print(f"WARNING: pandoc failed, skipping PDF export: {pandoc_result.stderr}", file=sys.stderr)
    else:
        print("WARNING: pandoc not found on PATH, skipping PDF export", file=sys.stderr)

    return 0


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/publish_review.py <paper-slug>", file=sys.stderr)
        sys.exit(1)
    sys.exit(asyncio.run(_publish(sys.argv[1])))


if __name__ == "__main__":
    main()
