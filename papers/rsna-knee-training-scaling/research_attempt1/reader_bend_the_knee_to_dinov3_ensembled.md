**Source: `bend-the-knee-to-dinov3-ensembled`**

**(1) Headline claim and score**
- **No final public score is reported in this source.** The notebook does not claim any leaderboard number. It describes itself as "now likely overfit to the public leaderboard" and states that "users repeatedly forked and republished it with one or two parameter tweaks" which the author also followed for "movements of only 0.001–0.003". The specific score these movements refer to is never stated.

**(2) Concrete techniques with numbers**

**Architecture — DINOv3 added member:**
- DINOv2 model ensemble. Added one "DINOv3 ViT-S/16 — self-supervised and pretrained without labels, then fine-tuned on this competition's knee MRI".
- Rank-blended into the DINOv2 family.

**Architecture — per-series token design:**
- "Each series carries a learned type embedding — plane crossed with fat suppression — added to all of its tokens."
- "The tokens of every series in a study are then concatenated into one key/value sequence, and twelve learned queries, one per finding, cross-attend over it with multi-head attention."
- "Each query's output is concatenated with the mean and the max of the per-series CLS embeddings before the classifier."
- "Series a study does not contain are removed by the key-padding mask, so nothing is imputed for them."

**Architecture — RadImageNet blending (the main contribution of this notebook):**
- "The E13 heads are fused into the pinned v15 reference family at **0.50** on ranks; that family then gets a **0.50** rank vote on ten findings, with Baker's and Fracture preserved."
- "The same E13 heads are then run a second time on the E11 slot layout — three non-fat-suppressed planes at a 130 mm crop — and blended in at **0.15**."
- The weights for the second pass (RadImageNet) are set "per finding by how much the five folds agree and how far the second pass departs from the first" (adaptive second-pass weighting, credited to romantamrazov's ideas).

**Removed components:**
- "Two earlier stages that replaced individual findings with report and metadata models — Synovitis, and Lateral Meniscus with Lateral OA — have been removed: they were unreachable in the deployed run, and leaving those findings to the image models scored better."

**Key configuration lines from code (no further narrative context):**
- `CROP_MM = 130.0`
- `CACHE_IMG = 336`
- `GROUP = 3`
- `N_GROUP_MAX = 1`
- `CACHE_FRACTION = 0.45`
- `CACHE_BUDGET_MAX_GB = 24.0`
- `CACHE_BUDGET_GB = 12.0`
- `TEST_SHARE = 0.3`
- `HDR_THREADS = 16`, `PIX_THREADS = 12`, `ORDER_THREADS = 32`, `ORDER_BUDGET_S = 5400`
- `RUNS = [{'name': 'r224', 'img': 224}, {'name': 'r336', 'img': 336}]`
- `EPOCHS = 10`
- `BATCH_STUDIES = 8`
- `AUG_ROT_DEG = 8.0`, `AUG_SCALE = 0.08`, `AUG_SHIFT = 0.05`, `AUG_INTENSITY = 0.1`
- `LAT_MIN_OFFSET_MM = 20.0`
- `SLICE_BAND = (0.2, 0.8)`
- `RULES_NATIVE = {'order': 'normal', 'lat': 'centre', 'slot_fallback': False, 'decode_fill': 'nearest'}`
- `RULES_LEGACY = {'order': 'dominant_axis', 'lat': 'corner_x', 'slot_fallback': True, 'decode_fill': 'zero'}`
- `LEGACY_LAT_OFFSET_MM = 5.0`
- `LR_HEAD = 0.001`, `LR_BACKBONE = 8e-06`
- `UNFREEZE_LAST = 6`
- `WEIGHT_DECAY = 0.02`
- `EVAL_BATCH = 8`
- `TIME_BUDGET = 8.0 * 3600`
- `SLOT_SCHEME = 'recovered'` (default)
- `N_SLOT = len(SLOTS)` (SLOTS defined as either SLOTS_PUBLIC or SLOTS_RECOVERED)
- `SLOT_PRIOR_STRENGTH = 0.55`
- `SEED = 2026`

**Label processing:**
- `FEATURES = {'unwrap': True, 'directional_negation': True, 'oa_inherit': True, 'graded_pathology': True, 'synovitis_backoff': True}`
- `NEGATION = _rx(PRE_NEG.pattern, POST_NEG.pattern, '\\bunremarkable\\b')`
- `NEG_WINDOW = 90`
- `DECOY = {'Fracture': _rx('microfractur', '\\bfracture (risk|prophyla)'), "Baker's": _rx('meniscal cyst', 'quiste meniscal', 'parameniscal')}`
- Tear/grade weighting formulas: `score = min(0.97, 0.5 + 0.45 * best + 0.015 * min(n_pos, 3))`; `conf = min(1.0, 0.55 + 0.15 * n_pos)`; negative scores: `score = max(0.04, 0.2 - 0.04 * n_neg)`, `conf = min(0.9, 0.45 + 0.12 * n_neg)`.
- Severity grades: base 1.0 for tear; `base = 0.95 if g >= 3 else 0.3`; OA high grade: `base = 0.85 if g >= 2 else 0.3`.
- Effusion prior: `prior = 0.3 + 0.3 * max(0.0, (eff - 0.5) / 0.45) + 0.06 * min(proxy, 3)`.

**(3) Ablations or measured effect sizes**
- **Supported (two item-specific removals):** "two per-finding specialists left out. That version scored higher than the one with them, which is what led to their removal here". The effect size is not quoted numerically, only that it was higher.
- **Asserted (DINOv3 quality):** "the public DINOv3 member from `knee-mri-fold-weights` ... was selected on held-out labelled studies, while sub-resolution blend tweaks should be treated as noise."
- **Asserted (fork degradation):** "This notebook is now likely overfit to the public leaderboard" due to the fork-and-republish race.

**(4) Resources and reproducibility**
- **Datasets credited (checkpoints and labels published by others):**
    - "pilkwang — twenty trained models"
    - "tonylica — four more trained models that join the ensemble"
    - "sofiaanjenje — five-fold E11 and E13 RadImageNet heads"
    - "marwanmath — the official RadImageNet ResNet-50 weights"
    - "prvsiyan — the notebook this was forked from"
- **Requires to reproduce:** Fork from the original source notebook, mount the above datasets, run inference on Kaggle. The author warns against using this version as a baseline without validation: "Use an earlier version as a baseline, or better, use the public DINOv3 member from `knee-mri-fold-weights` and validate it locally."

**(5) Author's own warnings or caveats**
- **"⚠️ WARNING: Read this before forking. This notebook is now likely overfit to the public leaderboard."**
- **"Changing one or two parameters and presenting the pipeline as a new solution is opportunistic reuse, not original work."**
- **The per-finding adaptive RadImageNet weights and the sub-resolution blend tweaks "should be treated as noise"** — the DINOv3 member itself was selected on held-out labelled studies.
- **Two specialist arms were removed** because they "were unreachable in the deployed run" (they did not produce outputs) and "leaving those findings to the image models scored better."

**(6) Confidence that each technique is a real cause of score**

- **Rank blending (rather than probability blending):** ASSERTED. The text says "the submission this forks from is a rank mean of twenty DINOv2 models" and the RadImageNet fusion is described as "0.50 on ranks". The rationale ("averaging ranks combines the only information the metric reads") appears in the supporting `rsna-knee-baseline-v1` text but not in this source itself.
- **RadImageNet E13 at 0.50 weight (first pass):** ASSUMED (no ablation shown in this source).
- **RadImageNet E13 second pass at 0.15 weight on E11 slots:** ASSUMED (no ablation).
- **Adaptive per-finding second-pass weight:** ASSERTED. Credited to romantamrazov's idea; implementation is the author's own. No effect size is given.
- **Removing the two specialist report/metadata models:** SUPPORTED (the author states the version without them scored higher, and that is why they were removed).
- **Learned type embeddings for plane×fatsat:** ASSERTED. No ablation shown.
- **Cross-attention query design (12 queries, concatenated with CLS mean/max):** ASSERTED. No ablation shown.
- **Crop to 130 mm, resize to 336 pixels:** ASSERTED. The reasoning (Nyquist sampling for 1 mm features, token size of 5.4 mm) appears in the baseline version. No ablation.
- **DINOv3 ViT-S/16 addition:** UNCLEAR. The author states the member was "selected on held-out labelled studies" but presents no comparative score.