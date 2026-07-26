# AI-Assisted Hypothesis Verification for Speculative Physics Papers: A Case Study with the Moonstar Harness

**Author:** Melvin Chotu (ORCID: [0009-0007-1617-4856](https://orcid.org/0009-0007-1617-4856))

**Date:** 2026-07-26

## Abstract

We report on moonstar-physics, a small deterministic-transform package plugged into the Moonstar multi-agent pipeline orchestration engine, used to test natural-language physics hypotheses against exact conservation-law arithmetic, four closed-form quantum-mechanical systems, a curated particle reference dataset, and fiber-bundle/spinor dimension counting — each check cross-examined by an LLM theory critic and a devil's-advocate LLM before a synthesizer produces a verdict. We evaluate the system on two published case studies — Eric Weinstein's *Geometric Unity* (2021) and Stephen Wolfram's *Finally We May Have a Path to the Fundamental Theory of Physics* (2020) — nine curated hypotheses in total, and report the actual costs, verdict distribution, and reliability data from those runs rather than projected or hypothetical figures. The marginal cost per hypothesis was on the order of $0.001, with a full paper review completing in minutes. But only 4 of 36 individual deterministic checks (11%) actually engaged with the hypothesis content; the remainder returned `not_applicable` because the papers' central claims fall outside the checker's narrow scope. We also encountered and fixed a genuine infrastructure reliability issue (an 18% session-level failure rate from an undersized HTTP client timeout) during the course of this work. We argue the system is best understood as a cheap, fast, auditable triage and adversarial-scrutiny scaffold for a narrow class of checkable claims — not a general-purpose automated peer reviewer — and we quantify exactly how narrow that class is in practice.

## 1. Introduction

The volume of speculative and foundational-physics writing — preprints, blog-length "theory of everything" announcements, long-form technical notes released outside conventional peer review — has grown to the point where no single human reviewer can give each one serious, structured scrutiny. Large language models are increasingly proposed as a partial answer: read the paper, extract its claims, and judge them. The appeal is obvious (near-zero marginal cost, no scheduling, no reviewer fatigue) and so are the risks (confident-sounding hallucination, no verifiable chain of reasoning, no way to distinguish a correct verdict from a fluent one).

moonstar-physics takes a narrower, more defensible position: instead of asking an LLM to *judge* a hypothesis, it asks an LLM only to *extract* a hypothesis into structured form, routes that structure through four independent deterministic checkers (exact arithmetic via `sympy`, not LLM inference), and only then brings LLMs back in — as a critic and a devil's advocate arguing over what the deterministic checks did or didn't establish. The idea is that wherever a claim is reducible to arithmetic, the system should never hallucinate about it; and wherever it isn't, the system should say so explicitly (`not_applicable`) rather than paper over the gap with confident prose.

This paper is a report on what actually happened when we pointed that system at two real, published, non-mainstream physics papers. We did not simulate or estimate the results — every number below is pulled directly from the pipeline's own run logs and cost-tracking database. We think the honest accounting matters more than the pitch: the system is genuinely useful, but not for the reason one might initially assume, and it broke in real, instructive ways before it worked.

## 2. Related Work

LLM-as-judge is now a standard evaluation pattern (Zheng et al., 2023, *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena*), and multi-agent debate has been shown to improve factual reliability over single-model judgment (Du et al., 2023, *Improving Factuality and Reasoning in Language Models through Multiagent Debate*). Self-critique loops (Madaan et al., 2023, *Self-Refine: Iterative Refinement with Self-Feedback*) and AI-feedback-driven correction (Bai et al., 2022, *Constitutional AI*) establish that having a model argue with itself, or with another model, measurably changes output quality. Separately, there is direct empirical work on LLMs reviewing real papers: Liang et al. (2024) found that large language models can produce feedback on scientific manuscripts that overlaps substantially with human reviewer comments, particularly for surface-level and methodological issues, while noting they miss deeper conceptual problems.

moonstar-physics sits at the intersection of these threads but diverges in one respect that we think is under-explored in the literature: it does not ask the LLM ensemble to be the source of truth about anything checkable. The deterministic layer is intentionally small, exact, and inspectable — closer in spirit to a property-based test suite than to a judge model. The debate pattern (critic vs. devil's advocate) is applied only on top of that layer, to interpret what it found rather than to replace it. This paper is, to our knowledge, one of the few reports that measures how much of a real paper's argument actually falls within such a deterministic layer's scope, as opposed to assuming broad coverage.

## 3. System Architecture

### 3.1 Moonstar: the orchestration substrate

Moonstar is a durable, multi-agent pipeline execution engine. Every step of a pipeline (a "transform") is a row in a PostgreSQL table; a worker loop claims work with `SELECT ... FOR UPDATE SKIP LOCKED`, executes it, and records cost, latency, and output as durable state. This matters for a paper-review workload specifically because it means a transient failure in one hypothesis's pipeline does not corrupt or block the others — each of the 5–8 pipeline sessions per paper review is independent, resumable, and separately budgeted (`max_usd`, `max_wallclock_seconds` per session).

### 3.2 moonstar-physics: the domain package

moonstar-physics contributes four deterministic transform types, discovered by Moonstar's worker at startup via Python entry points:

| Transform | What it checks |
|---|---|
| `ConservationLawCheckTransform` | Charge, baryon number, and per-flavor lepton number, computed exactly via `sympy.Rational` — plus a rest-mass-energy threshold check for proposed decays |
| `QMCalculationTransform` | Closed-form solutions for four systems: infinite square well, harmonic oscillator, hydrogen-like energy levels, and Heisenberg uncertainty bounds |
| `ReferenceDataLookupTransform` | Looks up mass, charge, spin, and lifetime for ~16 known particles from a bundled dataset |
| `DimensionConsistencyTransform` | Checks fiber-bundle total-space dimension arithmetic (base + fiber) and Spin(n) spinor representation dimensions against closed-form formulas |

Every one of these is pure, exact computation. None of them call an LLM, and none of them can be "convinced" by argument — a claimed Weyl spinor dimension is either arithmetically consistent with Spin(n) representation theory or it is not.

### 3.3 The physics_hypothesis pipeline

A single natural-language hypothesis moves through the following stages:

1. **Extractor** (LLM, flash-tier model): converts free text into a structured JSON schema — particle names, initial/final states for a proposed reaction, a QM system type and parameters if applicable, and any explicit fiber-bundle or spinor dimension claims. The extractor is instructed to leave fields null rather than guess, and to populate `dimension_claims` *only* when the hypothesis explicitly states a fiber-bundle or Spin(n) construction — it is explicitly forbidden from force-fitting unrelated claims into the schema.
2. **Wave 1 — four parallel deterministic checks** run against the extracted structure: `conservation_check`, `qm_calculation`, `reference_lookup`, `dimension_check`. Each returns one of a small set of verdicts (`consistent`, `violated`, `unknown_particle`, or `not_applicable`) — never a confidence score, never prose.
3. **theory_critic** (LLM, pro-tier model), run in parallel with the deterministic checks, gives a free-text assessment of theoretical soundness.
4. **devils_advocate** (LLM, pro-tier model): challenges the emerging consensus, explicitly weighing deterministic results against the critic's LLM reasoning, and is instructed to treat a deterministic `violated` as authoritative over an LLM's contrary intuition.
5. **synthesizer** (LLM, pro-tier model): produces the final conversational verdict (`CONSISTENT` / `INCONSISTENT` / `INCONCLUSIVE`) and writeup published in the review.

### 3.4 The paper-review workflow

A human curator reads the paper and hand-writes a small YAML spec (`papers/<slug>.yaml`) containing the paper's metadata and a short list of specific, testable claims drawn from the text. `scripts/publish_review.py` then: extracts the paper's PDF text (`pdftotext`), map-reduces it into a 2–3 paragraph summary via two further LLM pipelines (`paper_chunk_summary.yaml`, `paper_reduce_summary.yaml`), runs every curated hypothesis through `physics_hypothesis.yaml` sequentially, and writes a Markdown/PDF review plus a ScienceOpen submission-metadata sidecar. No step in this workflow discovers hypotheses on its own — every claim tested was chosen by a human, a design decision we return to in Section 7.

## 4. Method: Two Case Studies

We selected two published, non-peer-reviewed physics papers that each propose foundational reinterpretations of physics, differing in how mathematically explicit their claims are:

- **Geometric Unity** (Eric Weinstein, 2021): proposes a specific higher-dimensional fiber-bundle construction (the "Chimeric Bundle," an "Observerse" of stated dimension) and makes explicit claims about Spin(14) spinor representation dimensions and how the Standard Model gauge group should embed in it. We curated 4 hypotheses directly from these explicit dimensional claims.
- **Finally We May Have a Path to the Fundamental Theory of Physics** (Stephen Wolfram, 2020): proposes that spacetime, relativity, and quantum mechanics emerge from hypergraph rewriting rules. Its claims are almost entirely about emergent fractal/graph dimension estimates, qualitative unification arguments, and speculative particle candidates ("oligons") — not fiber-bundle geometry or specific particle decays. We curated 5 hypotheses spanning its most concrete numerical claims (an effective dimension of ≈2.7 from one rewrite rule, a Sierpiński-matching fractal dimension of log(3)/log(2) from another, an electron-radius conjecture derived from a proposed elementary length, the oligon dark-matter candidate, and its central claim that general relativity and quantum mechanics are the same phenomenon viewed in different "slices" of a multiway causal graph).

We deliberately chose the Wolfram paper *after* completing the Geometric Unity review and *knowing* it was a worse fit for the tool's checkable categories, specifically to measure how the system behaves outside its comfort zone rather than only reporting a favorable case.

### 4.1 Results

| Paper | Hypotheses | INCONSISTENT | INCONCLUSIVE | Deterministic checks that fired (of 4×N) |
|---|---|---|---|---|
| Geometric Unity | 4 | 1 | 3 | 2 / 16 (12.5%) |
| Wolfram Physics Project | 5 | 1 | 4 | 2 / 20 (10%) |
| **Combined** | **9** | **2** | **7** | **4 / 36 (11%)** |

Zero hypotheses across either paper received a `CONSISTENT` verdict. The two cases where a deterministic check *did* engage meaningfully are worth examining directly, because they illustrate the system doing exactly what it is designed to do:

- **Geometric Unity, hypothesis 3** ("The Weyl half-spinor representation of Spin(14) has complex dimension 64"): `dimension_check` returned `violated` — the correct dimension is 128, not 64. The theory critic (an LLM) had judged the claim "mathematically correct." The devil's advocate correctly overrode the LLM's intuition in favor of the deterministic result, and the synthesizer's final verdict was `INCONSISTENT`. This is the single cleanest demonstration of the architecture's value in our data: an LLM's confident, plausible-sounding, and *wrong* factual claim, caught by exact arithmetic that the LLM's own critique layer would not have caught alone.
- **Wolfram Physics Project, hypothesis 3** (electron radius derived from an "elementary length" conjecture): `reference_lookup` confirmed the electron is a real, correctly-named particle, but the deterministic layer has no notion of "radius" in its schema, so it could not evaluate the numerical claim itself. The `INCONSISTENT` verdict here rested entirely on the LLM critic's argument (electron treated as point-like in established QFT) — the deterministic check contributed context, not the verdict.

The remaining 7 of 9 hypotheses produced `INCONCLUSIVE` because every deterministic check returned `not_applicable`: no initial/final decay states were given, no closed-form QM system was implied, no fiber-bundle or Spin(n) dimension claim was explicit, and no particle name appeared to look up. In every one of these cases the published verdict rests entirely on two LLMs arguing with each other, with the deterministic layer contributing nothing beyond confirming there was nothing for it to check.

## 5. Cost Analysis

All figures below are drawn directly from the `spend_usd` field recorded by Moonstar's budget-tracking database for the actual runs referenced in each published review (i.e., excluding failed retries, which are reported separately in Section 7).

| Metric | Geometric Unity | Wolfram Physics Project |
|---|---|---|
| Hypotheses tested | 4 | 5 |
| Total LLM spend (hypothesis testing only) | $0.00475 | $0.00538 |
| Spend per hypothesis | ~$0.0012 | ~$0.0011 |
| Total input + output tokens | 24,837 | 28,702 |
| Wall-clock time per hypothesis (healthy run) | — | 48s–97s (median ~64s) |

Paper summarization (map-reduce over 8 chunks of the Wolfram paper, plus a reduce step) added a further handful of LLM calls at roughly $0.0004 per chunk based on directly measured single-call costs, bringing the estimated all-in cost of a full paper review to well under $0.01 in raw model spend. Across the entire body of work reported in this paper — both reviews, all failed retries, and our own diagnostic test calls — total recorded spend across 72 sessions was $0.0305.

This number is, on its own, the strongest quantitative argument for the approach: getting adversarial, structured scrutiny on a physics claim for roughly a tenth of a cent is not comparable to any human-reviewer economics. But we want to be explicit that this is *not* the dominant cost of the exercise, a point we return to in Section 7.4.

## 6. Benefits

**Cost.** As shown above, the marginal cost of testing one hypothesis is negligible — three orders of magnitude below what it costs to get a domain expert's attention for even a few minutes.

**Speed.** A full 5-hypothesis review, including paper summarization, completed in minutes end-to-end in a healthy run, versus the weeks-to-months timeline of conventional peer review or informal expert outreach.

**Auditability.** Every verdict in the published review links to the full raw pipeline JSON (`runs/<session_id>.json`) — the exact extracted hypothesis structure, every deterministic check's exact output, and every LLM message. Nothing is summarized away before it can be independently inspected. This stands in contrast to a bare "ask an LLM to grade this paper" approach, which produces a verdict with no decomposable trail.

**Epistemic honesty by construction.** The `not_applicable` verdict is a first-class, explicitly documented outcome, not an error state to be hidden. When 7 of 9 hypotheses in our case studies resolved this way, the system said so plainly in the published review rather than manufacturing a confident-sounding verdict to fill the gap. We consider this the single most valuable design property of the architecture, independent of how narrow the checkable scope turned out to be.

**Catching exact, checkable errors that LLM judgment alone missed.** The Geometric Unity Weyl-spinor case (Section 4.1) is a direct demonstration: an LLM critic judged a false claim "correct," and only the deterministic layer caught the error. This is precisely the failure mode — confident LLM hallucination on a checkable fact — that motivates having a deterministic layer at all.

**Democratized adversarial scrutiny.** A single researcher, with no institutional access to domain experts, can get a structured critic-versus-devil's-advocate exchange on demand. Even where the deterministic layer contributes nothing, the multi-agent debate pattern surfaces objections (missing derivations, undefined terms, absent falsifiability) that a first read might not.

## 7. Downsides and Limitations

### 7.1 Scope coverage is the central limitation, and it is severe

Only 11% of individual deterministic checks across our two case studies actually engaged with hypothesis content; 89% returned `not_applicable`. This is not a minor caveat — it means that for the large majority of claims in both papers, the system's core value proposition (exact, hallucination-proof checking) simply did not apply, and the published verdict rested on unaudited LLM argument alone, indistinguishable in kind from a bare LLM-as-judge approach. The four checkable categories — particle-decay conservation laws, four specific closed-form QM systems, a 16-particle lookup table, and fiber-bundle/spinor dimension arithmetic — are a genuinely narrow slice of what foundational and speculative physics papers actually argue about. Widening this scope (more QM systems, more geometric structures, gauge-anomaly arithmetic) is possible in principle, but the deeper problem is structural: most interesting theoretical physics claims are not reducible to closed-form arithmetic at all, and no realistic checklist closes that gap completely.

### 7.2 INCONCLUSIVE risks becoming an uninformative default

Precisely because it is the honest answer whenever the deterministic layer has nothing to check, `INCONCLUSIVE` was 7 of 9 verdicts across our case studies. A reader skimming verdict labels across many published reviews could reasonably come away thinking the tool has an opinion when in fact it is reporting an absence of one. The honesty is real, but its information value degrades as it becomes the dominant outcome — a distribution this skewed suggests the tool is, in its current form, better described as "occasionally catches an exact error, otherwise summarizes two LLMs' unaudited opinions" than as "verifies hypotheses."

### 7.3 Human hypothesis curation is a hidden, unaudited variable

Nothing in the pipeline discovers what to test — a human reads the paper and decides which claims are "specific" and "testable" enough to submit. This means: (a) the system can never surface a problem the curator didn't think to frame as a hypothesis, so its coverage of a paper's actual argument is bounded by curator judgment, not by the paper's content; (b) how a claim is phrased measurably changes what the Extractor populates and therefore which deterministic checks fire — a differently-worded version of the same underlying claim could produce a different verdict; and (c) a curator selecting only claims likely to trigger deterministic engagement (consciously or not) would make the tool look more capable than it is on genuinely novel material. We did not attempt to quantify phrasing sensitivity in this study, but flag it as a concrete threat to reproducibility that future work should measure directly.

### 7.4 Infrastructure reliability was a real, non-trivial cost

During the course of this work we measured, from Moonstar's own session-tracking database: **13 of 72 sessions failed outright (18%)**, and per-transform failure rates ranged from 4.8% (`chunk_summarizer`) to 16% (`Extractor`) before we diagnosed and fixed the root cause — an `httpcore.ReadTimeout` on the shared OpenRouter HTTP client, whose 90-second timeout was occasionally too short for pro-tier model calls under load, even though isolated single-request tests against the same endpoint reliably completed in under 5 seconds. Getting one paper to a clean, fully-populated review took as many as five full re-runs of the publish script. We raised the shared client timeout to 180 seconds as a direct result, a fix that will affect every pipeline running on this Moonstar instance, not just physics reviews. We report this not as an indictment of the specific fix but as a general observation: a system built from several chained LLM API calls per hypothesis has a compounding failure surface, and the operational cost of debugging *that* — as opposed to the cost of the LLM calls themselves — was, in our experience, larger in wall-clock human time than every dollar spent on inference in this entire study combined.

### 7.5 The LLM layers are themselves unverified

Nothing in the architecture checks whether the theory critic's or devil's advocate's physics reasoning is *correct* — only whether it is internally consistent with the deterministic layer's output when one exists. In the 89% of checks that returned `not_applicable`, the published verdict is pure LLM argument, and a wrong-but-fluent critique is, by construction, indistinguishable in the output from a correct one unless a human reviewer independently re-derives the physics. The devil's-advocate pattern raises the bar for internal consistency; it does not raise the bar for truth.

### 7.6 Cost framing can mislead

The headline number — a few tenths of a cent per hypothesis — is real, but it measures only inference spend. It excludes: the engineering time to build and maintain the pipeline; the time to convert a source (often HTML, as in the Wolfram case, requiring manual `pdftotext`/`pandoc` conversion to satisfy the workflow's PDF-only ingestion path); the human time to read the paper and curate defensible hypotheses; and, per Section 7.4, real debugging time when the infrastructure itself fails. "AI review costs a tenth of a cent" is true and also a significantly incomplete accounting of what it actually costs to produce one review.

## 8. Discussion

We think the honest framing for moonstar-physics, given the data above, is: a cheap, fast, fully-auditable scaffold that (a) is very good at catching a narrow, exactly-checkable class of factual errors an LLM would otherwise assert with unwarranted confidence, and (b) otherwise functions as an unusually structured, adversarially-debated LLM opinion generator whose verdicts should be weighted accordingly. It is not, in its current form, a general-purpose automated peer reviewer, and the 11% deterministic-engagement rate we measured on two real papers should discourage treating its `INCONSISTENT`/`INCONCLUSIVE` labels as more authoritative than "two language models disagreed about this and one of them wasn't obviously wrong."

Where we think this is genuinely valuable is high-volume, low-stakes triage: screening a large corpus of preprints for a small number of exactly-checkable red flags (a spinor dimension that doesn't work out, a proposed decay that violates lepton-flavor conservation) before any human time is spent, cheaply enough that running it is never the bottleneck. It is a poor substitute for expert judgment on any single paper's deepest claims, and we would caution strongly against citing an `INCONCLUSIVE` or even `INCONSISTENT` verdict from this system as if it settled anything — the correct reading of `INCONCLUSIVE`, per Section 7.2, is "we didn't check this," not "this might be true."

Widening the deterministic layer's scope is a natural next step, but Section 7.1 argues this has diminishing returns: the gap between "checkable by closed-form arithmetic" and "the actual content of a foundational physics paper" is not primarily a coverage gap that more checkers close, but a structural feature of what these papers are trying to claim in the first place. A more promising direction, in our view, is making the *human curation* step (Section 7.3) itself more transparent and auditable — publishing not just the tested hypotheses but the curator's rationale for selecting them, so readers can independently judge whether the tested claims are representative of the paper's actual argument or a convenient subset.

## 9. Future Work

The cost and latency figures in Section 5 are, we think, the strongest argument for continuing to invest in this direction rather than treating the two case studies here as a finished result. At roughly a tenth of a cent and under two minutes per hypothesis, the binding constraint on this approach was never inference cost or wall-clock time — it was the narrowness of what the deterministic layer could check (Section 7.1) and the engineering cost of infrastructure reliability (Section 7.4), both of which are addressable with continued work rather than fundamental limits of the approach. We intend to keep running and refining the existing transforms, and to build out the deterministic-checker library — for physics and beyond — on that basis.

Liang et al. (2023) found that GPT-4-generated feedback on real manuscripts overlapped substantially with human reviewer comments on surface-level and methodological issues, while missing deeper conceptual problems — comment-for-comment, LLM feedback looked most like a competent human reviewer exactly where a claim reduced to something checkable, and least like one where it required domain judgment. That is precisely the split moonstar-physics's architecture is built around: route the checkable slice to exact, non-hallucinating arithmetic, and reserve the LLM layer for the judgment calls that arithmetic can't make. Our 11% deterministic-engagement figure (Section 4.1) is a direct measurement of how small that checkable slice currently is for foundational-physics papers specifically — and the most concrete way to grow it is the same way moonstar-physics itself was built: add another narrow, exact, domain-specific transform package (a `moonstar-<domain>` sibling repo, following the same pattern as `moonstar-physics`) for each additional class of checkable claim, whether that is a different area of physics, a different scientific domain entirely, or a different *kind* of artifact — a software paper's complexity or benchmark claims, a statistics paper's reported significance tests, a proof's individual inference steps. Moonstar's orchestration layer (durable execution, per-session budgets, entry-point transform discovery) does not care what domain a transform checks; every result in this paper suggests that the marginal cost of running such a pipeline is low enough to make trying this broadly worthwhile, even where most individual checks will, as here, come back `not_applicable`.

A second, more speculative direction goes beyond checking a hand-curated hypothesis list at all: using Moonstar to generate runnable code directly from a paper — an implementation of a claimed algorithm, or a simulation reproducing a claimed numerical result — and testing the paper's claims by executing that code rather than by routing a paraphrase of the claim through a fixed checker schema. This would remove the human-curation bottleneck identified in Section 7.3 (the tool could attempt to test *every* concrete, implementable claim in a paper, not just the ones a curator selected) at the cost of introducing a new one: the correctness of LLM-generated implementation code is itself unverified, and a plausible-but-wrong implementation could produce a confidently wrong verdict about the paper it was meant to test — the same failure mode this paper has spent Sections 7 and 8 arguing against, one level further removed from the source claim. We think this is worth pursuing precisely because the underlying harness has already been shown, in this paper, to be cheap and reliable enough to support it — but any such system would need its own honest accounting of scope and failure modes before its verdicts should be trusted any further than the ones reported here.

## 10. Conclusion

We built and ran an AI-assisted hypothesis-verification pipeline against two real, published, non-mainstream physics papers, and report the actual — not projected — costs, verdicts, and failure modes. The system is remarkably cheap (~$0.001 per hypothesis) and fast (minutes per paper), and it demonstrably caught at least one confident, wrong LLM claim via exact deterministic arithmetic that the LLM layer alone would have missed. But its deterministic core engaged with only 11% of the claims we tested; the rest of its output — the majority — was unaudited multi-agent LLM debate wearing the presentation of a verification system. We think both facts are true simultaneously, and that reporting only one of them — either "AI review is nearly free" or "AI review mostly doesn't check anything" — would misrepresent what we actually observed.

## References

- Bai, Y. et al. (2022). *Constitutional AI: Harmlessness from AI Feedback.* Anthropic. [arXiv:2212.08073](https://arxiv.org/abs/2212.08073)
- Du, Y., Li, S., Torralba, A., Tenenbaum, J. B., & Mordatch, I. (2023). *Improving Factuality and Reasoning in Language Models through Multiagent Debate.* [arXiv:2305.14325](https://arxiv.org/abs/2305.14325)
- Liang, W. et al. (2023). *Can large language models provide useful feedback on research papers? A large-scale empirical analysis.* [arXiv:2310.01783](https://arxiv.org/abs/2310.01783)
- Madaan, A. et al. (2023). *Self-Refine: Iterative Refinement with Self-Feedback.* [arXiv:2303.17651](https://arxiv.org/abs/2303.17651)
- Weinstein, E. (2021). *Geometric Unity: Author's Working Draft, v 1.0.* [geometricunity.org](https://geometricunity.org/) — draft PDF: [geometricunity.nyc3.digitaloceanspaces.com](https://geometricunity.nyc3.digitaloceanspaces.com/Geometric_Unity-Draft-April-1st-2021.pdf)
- Wolfram, S. (2020). *Finally We May Have a Path to the Fundamental Theory of Physics… and It's Beautiful.* [writings.stephenwolfram.com](https://writings.stephenwolfram.com/2020/04/finally-we-may-have-a-path-to-the-fundamental-theory-of-physics-and-its-beautiful/)
- Zheng, L. et al. (2023). *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena.* [arXiv:2306.05685](https://arxiv.org/abs/2306.05685)

## Appendix: Data Availability

All raw pipeline session data underlying the figures in Sections 4 and 5 are committed in this repository at `reviews/geometric-unity/runs/*.json` and `reviews/wolfram-fundamental-theory/runs/*.json`, including the failed-retry sessions referenced in Section 7.4. The full published reviews are at `reviews/geometric-unity/review.md` and `reviews/wolfram-fundamental-theory/review.md`.
