# Analysis of `rsna-versia-5`

## Headline claim and reported scores
- Claims "Evolution of Public Solutions: 0.937 → 0.94 → 0.941 → 0.942 → 0.943" — but these are **scores of other authors' public notebooks**, not this notebook's own results. No score is reported as this notebook's own original contribution.
- The notebook describes itself as a reproduction/package: "All models, weights, and pipelines below are public work by other authors. We reproduced them one-to-one and packaged them into a single notebook."
- Scores referenced: Work 1 = 0.937, Work 2 = 0.94, Work 3 = 0.941, Work 4 = 0.942, Work 5 = 0.943. No evidence that this notebook itself achieved any of these.

## Concrete techniques (with numbers)
**Work 1 (0.937) — CoAtNet branch**
- Expanded to 4 arms: v5, v10, v5-reverse, v8
- Reverse-flip adds diversity "without new training"
- Outer CoAtNet weight becomes "global 0.60 instead of per-target"

**Work 2 (0.94) — Hybrid Raptor, Lateral Meniscus R100**
- Starts from "exact 0.939 parent"
- Changes only one label: Lateral Meniscus
- Outer routing for Lateral Meniscus: Transformer/Rad = 0.00, Raptor = 1.00
- All other 11 labels remain "bit-for-bit equal" to parent at 0.40/0.60

**Work 3 (0.941) — Bend the Knee to the Dinosaurs**
- Keeps 4-arm Raptor
- Adds residual-gated CoAtNet (e4/e6/e8) inside Raptor branch
- Inner blend: public Raptor 0.60 / residual-CoAt 0.40
- Public CoAtNet MRI reader: 384 px adjacent-slice triplets → CoAtNet RMLP-2 backbone
- Finding-specific gated spatial head + second attention stage pools windows across study
- CoAtNet arm weights: maxspan-v5 = 0.60, reverse = 0.10
- Per-target outer routing: ACL 0.75, Medial Meniscus 0.80, Lateral Meniscus 1.00, Lateral OA 0.75, Fracture 0.75

**Work 4 (0.942) — rsna-knee-0942-restructured**
- Three hyperparameters raised: `a5_w` 0.45→0.52, `rad_alpha` 0.50→0.55, `rad_second_alpha` 0.15→0.20, `raptor_k_eval` 62/42→94
- "Full run takes ~4 minutes on T4×2"
- Added E9 RadImageNet Heads V15 dataset
- Parallel execution of residual-gated CoAtNet and D4 DepthZone SWA3: "155s → 69s with zero change to predictions"
- `INFERRED96_WIDTHS = (27, 21, 18, 12, 18)`
- `_dense_allocate` with proportions `(20, 12, 12, 8, 16, 8)` for 94 windows
- "SLOTS_RECOVERED now includes SAG_T1", adds "smart fat"/"water" to `_FATSAT_RX` for GE Dixon

**Work 5 (0.943) — rsna-knee-fast-2xt4-inference**
- CoAt family doubled from 2 to 4 members (+ global96, + repairv1)
- Global96 epochs: 16/23/18; Repair-v1 epochs: 12/7/11
- Family reduction changed from "mean of ranks" to "rank of mean of probabilities"
- Two pairs in parallel: (resgated, d4) and (global96, repairv1)
- Raptor header cache seeded from DINOv2 ordering scan
- Global96: "same 96-slice stack as D4, but a full-width gated head instead of Rank8 finding-to-slot attention"

**Environment / infrastructure**
- Requires "ровно 2 GPU", "ровно 2 T4" (exactly 2 T4 GPUs) — fails otherwise, no CPU/1-GPU fallback
- `TIME_BUDGET = 8 часов` (8 hours)
- D4 contract checks: `coatnet_pairfilm_manifest.json` SHA256 match, `N_MODELS==1`, checkpoint `coatnet_d4_parent_rank8_swa2.pt`, `cv2==4.12.0`, `timm==1.0.22`
- "peak_reserved_bytes < 15.5 GB"
- Cache: 45% of RAM, max 24 GB → 1 group × 3 slices
- Thread pinning: OMP/OPENBLAS/MKL=4, `CUDNN_CONV_WSCAP_DBG=1024`
- Diffusion of "37 исследований из 4407 не имели fat-sat серий" (37 of 4407 studies lacked fat-sat series) — fixed via GE Dixon detection

## Ablations / measured effect sizes
- **None.** No ablation is reported anywhere in this notebook. The notebook presents the 0.937→0.943 progression as a sequence of other people's changes, not as experiments this notebook ran.
- The only measured comparisons cited are performance/time: "155s → 69s with zero change to predictions" (speed, not score).

## Resources and reproducibility
- Mounts public datasets authored by others (e.g., `rsna-knee-coatnet-global96-top3`)
- All models/weights are public: "All models, weights, and pipelines below are public work by other authors"
- Requires exact T4×2 hardware, specific package versions, specific checkpoints with SHA256-verified manifests
- Links to: prvsiyan (Work 1), renta0426 (Work 2), Mattia Angeli (Work 3), maverick_ss_26 (Work 4), Jiwei Liu (Work 5)

## Warnings / caveats
- The notebook is a **reproduction/package** of others' work, not original; it takes no credit
- D4 runtime checks are hard: "падает" (crashes) if any asset is missing or mismatched
- Explicit "никакого CPU/1-GPU fallback" (no CPU/1-GPU fallback)
- Failure is preferable to silent partial submission: if `TIME_BUDGET` exceeded, crash rather than partial submission

## Confidence in techniques as causes of score
- **Work 1 CoAtNet 4-arm expansion, global 0.60 weight** — ASSERTED (claimed 0.937, no ablation shown in this source)
- **Work 2 Lateral Meniscus routing 0.00/1.00** — ASSERTED (claimed 0.94; described as changing only one label, but no ablation in this source)
- **Work 3 residual-gated CoAtNet 0.40 inner, per-target routing (ACL 0.75, Med Meniscus 0.80, Lat Meniscus 1.00, Lat OA 0.75, Fracture 0.75)** — ASSERTED (claimed 0.941)
- **Work 4 hyperparameter raises (a5_w 0.52, rad_alpha 0.55, rad_second 0.20, raptor_k 94)** — ASSERTED (claimed 0.942; described as "three hyperparameters raised — no new models," implying causality but with no ablation shown here)
- **Work 5 4-member CoAt family, probability-space reduction, Global96/Repair-v1 additions** — ASSERTED (claimed 0.943)
- **Dense capacity-aware depth allocation (94 windows, proportions)** — ASSERTED as an engineering improvement ("устраняет дубли и padding"), but no score attribution
- **GE Dixon fat/water detection** — ASSERTED as fixing "37/4407 studies," no score impact claimed

Overall: **Everything is ASSERTED**. No ablation, no error bars, no per-change score deltas are reported in this source; the notebook is a review/reproduction of others' scored work, with the scores attributed to the original authors.