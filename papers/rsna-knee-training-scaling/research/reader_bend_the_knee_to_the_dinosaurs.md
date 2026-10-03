Based on the provided source material, here is the analysis of the notebook `bend-the-knee-to-the-dinosaurs`.

## 1. Headline claim and reported scores
- The notebook reports a public leaderboard score of **0.943**, achieved by a previous work (`rsna-knee-fast-2xt4-inference`), which this notebook builds upon. The narrative states the progression: "This is how public solutions moved from **0.937 → 0.94 → 0.941 → 0.942 → 0.943**."
- This notebook ("Bend the Knee to the Dinosaurs (ALL PUBLIC)") is an **inference-only submission** that adds a CoAtNet MRI reader to an existing ensemble. It does not explicitly report its own final score in the provided text.

## 2. Concrete techniques with exact numbers
**Architecture / Models:**
- **CoAtNet MRI reader**: Each 384 px adjacent-slice triplet passes through a CoAtNet RMLP-2 backbone. A "finding-specific gated spatial head blends localized evidence with a protected global-average residual; a second finding-specific attention stage pools windows across the study."
- **New models added**: Global96 top-3 (96-slice stack, full-width gated head) and Repair-v1 top-3 (third independent CoAt checkpoint).
- **Existing ensemble members**: References 20 DINOv2 models (from pilkwang) and 4 more from tonylica; adds one DINOv3 ViT-S/16.
- **RadImageNet stages**: E13 heads fused at 0.50 on ranks into a pinned v15 family; that family gets 0.50 rank vote on ten findings (preserving Baker's and Fracture); E13 heads re-run on E11 slot layout and blended in at 0.15.

**Input / Preprocessing:**
- Image resolutions: `RUNS = [{'name': 'r224', 'img': 224}, {'name': 'r336', 'img': 336}]`
- `CROP_MM = 130.0`, `CACHE_IMG = 336`, `SLICE_BAND = (0.2, 0.8)`, `LAT_MIN_OFFSET_MM = 20.0`
- Slice schemes: `SLOTS_PUBLIC` vs `SLOTS_RECOVERED` with `SLOT_SCHEME` env var.
- Geometry rules: two variants `RULES_NATIVE` and `RULES_LEGACY` with different ordering/fallback settings.

**Training / Optimization:**
- `EPOCHS = 10`, `BATCH_STUDIES = 8`, `LR_HEAD = 0.001`, `LR_BACKBONE = 8e-06`, `UNFREEZE_LAST = 6`, `WEIGHT_DECAY = 0.02`
- Augmentation: `AUG_ROT_DEG = 8.0`, `AUG_SCALE = 0.08`, `AUG_SHIFT = 0.05`, `AUG_INTENSITY = 0.1`

**Ensembling / Aggregation:**
- **Probability-space reduction** (changed from rank-space): "read each member's `probability_mean` from its `.npz`, average **probabilities**, then `rank(pct=True)`" — fallback to rank-sum if `.npz` missing.
- Three CoAt checkpoints combined by "per-finding rank averaging" before joining the ensemble.
- Parallel execution: "residual-gated CoAtNet and D4 DepthZone SWA3 — 155s → 69s with zero change to predictions."

**Inference / Hardware:**
- Runtime: "~4 minutes on T4×2" (shared DINO prefixes, persistent T4×2 replicas, cached decoding).
- D4 reference checks: `cv2==4.12.0`, `timm==1.0.22`, exactly 2 T4 GPUs, `N_MODELS==1`.
- Cache: `CACHE_BUDGET_GB = 12.0`, `CACHE_FRACTION = 0.45`, `GROUP = 3`, `N_GROUP_MAX = 1`.

## 3. Ablations / measured effect sizes
- The narrative reports for the 0.943 version (vs 0.942):
  - CoAt family members doubled: 2 → 4 (adding global96, repairv1).
  - Global96 epochs: **16 / 23 / 18**; Repair-v1 epochs: **12 / 7 / 11**.
  - Family reduction changed from "mean of ranks" to "rank of mean of probabilities".
  - Parallelism changed to "two pairs in parallel".
- It states that removing two per-finding specialists (from tonylica's run) "scored higher than the one with them, which is what led to their removal here."
- The D4 allocation section describes `_dense_allocate` distributing 94 windows proportionally to capacity with proportions `(20, 12, 12, 8, 16, 8)`, `INFERRED96_WIDTHS = (27, 21, 18, 12, 18)`.

## 4. Resources / Reproduction requirements
- **External weights/datasets**:
  - CoAtNet MRI model: `https://www.kaggle.com/datasets/mattiaangeli/rsna-knee-coat-resgated-ep10-top3`
  - Credits to public works: prvsiyan (0.937), renta0426 (0.94), Mattia Angeli (0.941), maverick_ss_26 (0.942), Jiwei Liu (0.943).
  - References to pilkwang's 20 models, tonylica's 4 models, RadImageNet ResNet-50 weights (marwanmath), E9 RadImageNet Heads V15 dataset (`antoinegg1/rsna-knee-e9-radimagenet-heads-v15`).
- **Integrity harness**: Requires exactly 2 T4 GPUs, falls over if not (no CPU/1-GPU fallback); checks receipt digests, model checkpoints must match exactly (all tensors by name/shape, no random init); `TIME_BUDGET = 8.0 * 3600` seconds (8 hours) with deadline enforcement; uses memmap for large arrays; writes phase events to `diagnostics/`.
- **Runtime**: ~4 minutes on T4×2 for the full pipeline.

## 5. Author warnings / caveats
- ⚠️ **Overfitting warning** (in the first source, `bend-the-knee-to-dinov3-ensembled`): "This notebook is now likely overfit to the public leaderboard" due to repeated forking/republishing with parameter tweaks; "Changing one or two parameters and presenting the pipeline as a new solution is opportunistic reuse, not original work." Recommends using earlier versions as baselines.
- The narrative notes "sub-resolution blend tweaks should be treated as noise."
- D4 runtime checks: fails if GPU count != 2 or not T4; strict SHA256 matching for manifests; budget caps at 24 GB cache.

## 6. Confidence in causality (SUPPORTED by ablation / ASSERTED / UNCLEAR)
- **CoAtNet reader addition**: ASSERTED — described as the "new addition," but no standalone score improvement is measured in this text.
- **Probability-space reduction (rank of mean of probabilities)**: ASSERTED — described as a change from 0.942 → 0.943, but the text attributes the overall gain to multiple simultaneous changes (CoAt members doubling + reduction change), so the individual contribution is UNCLEAR.
- **Parallel execution (155s → 69s)**: SUPPORTED — explicitly states "zero change to predictions," so it's a pure speedup, not a score improvement.
- **Removal of per-finding specialists**: SUPPORTED — explicitly states tonylica's run "scored higher than the one with them, which is what led to their removal here."
- **Dense slot allocation (proportional to capacity)**: ASSERTED — described in the Russian section as "distributes 94 windows by slots proportionally to their real capacity," but no ablation score is given.
- **RadImageNet blending weights (0.50/0.15)**: ASSERTED — described in text, but no ablations.
- **Global96/Repair-v1 addition**: ASSERTED — described as "new models," with epoch counts given, but no individual contribution to score is measured.

The notebook does not provide a rigorous ablation for most techniques; only the specialist removal and the parallel-speedup (with zero prediction change) have explicit evidence. The rest are described as part of a combined change.