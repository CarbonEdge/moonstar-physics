"""Research pipeline: read many sources -> cross-source synthesis -> expert panel -> red team -> decision doc.

Usage: MOONSTAR_AUTH_TOKEN=<token> python scripts/run_research.py papers/rsna-knee-training-scaling

Inputs (in <dir>):  variant-planning-context.md (our facts/constraints), sources/*.md (digests of public work)
Outputs (in <dir>/research/): <stage>.md for every stage, run.json, computed_facts.json, decision.md

The pipeline YAML is generated per run: one `reader_<slug>` LlmTransform per source (source text embedded
in its prompt), then fixed downstream stages. Computed facts (real arithmetic, not LLM output) are embedded
in the downstream prompts so the experts argue from numbers.
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
import _pipeline_client as pc  # noqa: E402

ROOT = Path(__file__).parent.parent
SKIP = {"rsna-knee-abnormalities-efficiency-lb"}  # leaderboard-only page, no method content


def hanley_mcneil_se(auc: float, n_pos: int, n_neg: int) -> float:
    q1, q2 = auc / (2 - auc), 2 * auc * auc / (1 + auc)
    var = (auc * (1 - auc) + (n_pos - 1) * (q1 - auc * auc) + (n_neg - 1) * (q2 - auc * auc)) / (n_pos * n_neg)
    return math.sqrt(max(var, 0.0))


def computed_facts() -> dict:
    se = {}
    for n in (19, 58):
        for prev in (0.1, 0.3, 0.5):
            n_pos = max(2, round(n * prev))
            for auc in (0.80, 0.90):
                se[f"n={n},prev={prev},auc={auc}"] = round(hanley_mcneil_se(auc, n_pos, n - n_pos), 3)
    pitch = {px: round(130.0 / px, 3) for px in (224, 256, 336, 384)}
    gaps = {"r12": round(0.865 - 0.832, 3), "r13b": round(0.862 - 0.841, 3), "r17": round(0.856 - 0.825, 3)}
    return {
        "AUC_standard_error_Hanley_McNeil (single finding)": se,
        "note_on_SE": "mean over 12 findings shrinks noise by ~sqrt(12) only if findings are independent; they are not.",
        "pixel_pitch_mm_at_130mm_crop": pitch,
        "tear_width_1mm_needs_pitch_leq_mm": 0.5,
        "cv_to_public_gap": gaps,
        "tpu_budget": {"hours_available": 16, "r16_recipe_hours_per_run": 3.5, "full_runs_that_fit": int(16 // 3.5)},
        "gpu_budget": {"hours_available": 30},
        "public_frontier": {"0.937": "prvsiyan", "0.940": "renta0426", "0.941": "mattiaangeli", "0.942": "maverickss26", "0.943": "jiweiliu"},
        "our_best_public": 0.865,
        "gap_to_frontier": round(0.943 - 0.865, 3),
    }


def block(text: str, indent: int = 8) -> str:
    pad = " " * indent
    return "\n".join((pad + line if line.strip() else "") for line in text.splitlines())


def slug_id(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:40]


def build_yaml(models: dict, ctx: str, facts: dict, sources: dict[str, str]) -> str:
    def m(k): return models[k]
    grounding = (
        "OUR SITUATION AND CONSTRAINTS:\n" + ctx + "\n\nCOMPUTED FACTS (arithmetic done in code, treat as ground truth):\n"
        + json.dumps(facts, indent=1)
    )
    out = ["pipeline:", "  name: ml-research", '  version: "1.0"',
           "  description: Read public sources, synthesize cross-source evidence, expert panel, red team, decision.",
           "", "transforms:"]
    reader_names = []
    for slug, text in sources.items():
        name = "reader_" + slug_id(slug)
        reader_names.append(name)
        out += [
            f"  - name: {name}", "    type: LlmTransform", "    config:", f'      model: "{m("MODEL_SUMMARIZER")}"',
            "      max_tokens: 2500", "      system: |",
            block(
                "You are a research analyst reading ONE source: a public Kaggle notebook from a competition on "
                "knee-MRI abnormality detection (12 findings, mean AUC). Extract, faithfully and without "
                "inventing anything: (1) the headline claim and any score it reports, with the version/evidence; "
                "(2) every concrete technique (architecture, input design, slice counts, resolution, "
                "preprocessing, label handling, loss, aggregation, blending/routing weights, TTA) with the "
                "numbers given; (3) any ablation or measured effect size, quoted; (4) what resources it attaches "
                "(datasets/weights) and what it requires to reproduce; (5) the author's own warnings or "
                "caveats; (6) your confidence that each technique is a real cause of score (SUPPORTED by an "
                "ablation / ASSERTED / UNCLEAR). Use compact bullets. Quote numbers exactly.\n\n"
                f"Your input JSON has a key \"sources\" mapping source names to their text. Analyse ONLY the "
                f"source named `{slug}` and ignore the others.", 8),
        ]
    out += [
        "  - name: cross_source", "    type: LlmTransform", f"    input: [{', '.join(reader_names)}]", "    config:",
        f'      model: "{m("MODEL_DECISION_MAKER")}"', "      max_tokens: 6000", "      system: |",
        block(
            "You receive per-source analyses of public solutions to one competition. Do the research "
            "synthesis: (1) the lineage graph: which solution builds on which, so you do not double count "
            "evidence; (2) techniques that appear across independent sources vs only once; (3) which "
            "techniques have measured ablations (with numbers) vs are only asserted; (4) the score ladder "
            "and which step explains each increment; (5) contradictions between sources; (6) which resources "
            "(weights/datasets) are attached and what each contributes; (7) a ranked list of the techniques "
            "most likely responsible for the gap between ~0.87 (single-model, mid-triplet, series-pooled) "
            "and ~0.94 (large heterogeneous ensemble). Separate evidence from inference explicitly.", 8),
    ]
    experts = {
        "radiologist": (
            "You are a musculoskeletal radiologist who understands deep learning. Using the cross-source "
            "research and our situation, reason from knee MRI physiology: which sequences/planes/fat "
            "suppression show which of the 12 findings, what resolution/slice coverage each needs, where "
            "report-derived labels diverge from annotation thresholds, and which findings our current "
            "single-mid-triplet, series-then-pool design must lose most on. Rank the findings by expected "
            "loss vs the frontier and recommend concrete input-design changes."),
        "grandmaster": (
            "You are a Kaggle grandmaster in medical-imaging code competitions. Design the best plan to move "
            "from 0.865 toward the frontier under our constraints. Compare (a) attaching and ensembling "
            "public trained weights in a GPU inference notebook, (b) retraining our own members with "
            "slot/2.5D/dense-slice upgrades, (c) a hybrid rank-blending our own diverse members with public "
            "ones. Give honest expected public-score ranges and failure modes, the blending design that avoids "
            "overfitting to 58 gold studies, and the smallest first experiment that validates the choice."),
        "statistician": (
            "You are a statistician and compute planner. Using the computed facts (they are correct), state "
            "what 58 gold studies can and cannot resolve, design the validation protocol (report-hash grouped "
            "splits, repeated partitions, nested blend weights; which decisions may use gold), do the "
            "TPU/GPU/CPU budget arithmetic for each candidate plan showing your work, and say which public-LB "
            "signals are trustworthy given the daily submission limit."),
    }
    for nm, prompt in experts.items():
        out += [
            f"  - name: {nm}", "    type: LlmTransform", "    input: [cross_source]", "    config:",
            f'      model: "{m("MODEL_GENERATOR")}"', "      max_tokens: 4000", "      system: |",
            block(prompt + "\n\n" + grounding, 8),
        ]
    out += [
        "  - name: red_team", "    type: LlmTransform", "    input: [cross_source, radiologist, grandmaster, statistician]",
        "    config:", f'      model: "{m("MODEL_CRITIC")}"', "      max_tokens: 3500", "      system: |",
        block(
            "Attack the three expert drafts using the cross-source research as the evidence base: "
            "unsupported claims, budget arithmetic errors (recompute them), plans that rely on gold-label "
            "post-selection, contradictions, public-LB overfitting risk, and integrity/compliance concerns "
            "about reusing public work. Quote the claim, say why it fails, say what repairs it. End with the "
            "single biggest blind spot.\n\n" + grounding, 8),
        "  - name: synthesizer", "    type: LlmTransform",
        "    input: [cross_source, radiologist, grandmaster, statistician, red_team]", "    config:",
        f'      model: "{m("MODEL_DECISION_MAKER")}"', "      max_tokens: 14000", "      system: |",
        block(
            "Write the decision document \"What to run next to win\" in markdown, executive style (bullets, "
            "tables, no walls of text). Use only what survived the red team. Sections: 1. Verdict (3 bullets: "
            "recommended path, expected public score range with honest uncertainty). 2. Why we are at 0.865 "
            "and the frontier is at ~0.94 (4-5 real causes, ranked, each marked SUPPORTED/ASSERTED). 3. Plan: "
            "ordered steps with hardware, hours, and a kill criterion each; step 1 runnable this week. "
            "4. Validation protocol; which decisions may use gold labels. 5. Per-finding targets. 6. Integrity "
            "note: what is reused from public work (attribute authors) and what is our own contribution. "
            "7. Risks and what we will not do. 8. What new research to do next (open questions). Every "
            "quantitative claim names its source or shows arithmetic.\n\n" + grounding, 8),
        "", "budget:", "  max_usd: 4.00", "  max_wallclock_seconds: 2400", "",
    ]
    text = "\n".join(out)
    # Reasoning models spend max_tokens on hidden thinking and return empty/truncated text (runs 1-2:
    # every stage hit its cap; statistician returned nothing). Same fix as construct.yaml.
    return re.sub(r"(      max_tokens: \d+\n)", r"\1      timeout_seconds: 600\n      reasoning: {enabled: false}\n", text)


async def main(d: Path) -> int:
    models = json.loads((ROOT / "pipelines" / "models.json").read_text(encoding="utf-8"))
    ctx = (d / "variant-planning-context.md").read_text(encoding="utf-8")
    ctx += ("\n\nQUESTIONS THE PLAN MUST ANSWER: highest-value path to >0.90 and toward 0.94 (attach public weights / "
            "retrain own members / hybrid) with honest expected scores; what our own assets add as diversity; how "
            "to validate with 58 gold; how to weigh learning-the-task against raw rank (reusing public work).\n")
    sources = {p.stem: p.read_text(encoding="utf-8") for p in sorted((d / "sources").glob("*.md")) if p.stem not in SKIP}
    facts = computed_facts()
    out = d / "research"
    out.mkdir(exist_ok=True)
    (out / "computed_facts.json").write_text(json.dumps(facts, indent=2), encoding="utf-8")
    spec = build_yaml(models, ctx, facts, sources)
    (out / "pipeline_rendered.yaml").write_text(spec, encoding="utf-8")
    print(f"sources: {list(sources)}  yaml chars: {len(spec)}", flush=True)
    pc._MAX_POLLS = 1200
    async with httpx.AsyncClient(timeout=120) as client:
        res = await pc.submit_and_wait(client, os.environ.get("MOONSTAR_GATEWAY_URL", "http://localhost:8000"),
                                       os.environ["MOONSTAR_AUTH_TOKEN"], spec, {"sources": sources})
    (out / "run.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print("status:", res.get("status"), "spend:", res.get("spend_usd"))
    for a in res.get("artifacts", []):
        data = a.get("data") or {}
        text = data.get("response") if isinstance(data, dict) else None
        if text:
            (out / f"{a['transform_name']}.md").write_text(text, encoding="utf-8")
    if (out / "synthesizer.md").exists():
        (out / "decision.md").write_text((out / "synthesizer.md").read_text(encoding="utf-8"), encoding="utf-8")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main(Path(sys.argv[1]))))
