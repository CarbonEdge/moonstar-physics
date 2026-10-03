# Analysis of `bend-the-knee-to-dinov3-ensembled`

## 1. Headline claim and score
- **No explicit score is reported in this notebook.** The narrative describes architecture and blending but does not state a public or private LB AUC. (Compare: related notebooks in other sources cite 0.941–0.943 for derivative pipelines, but this source itself is silent on its own score.)
- **Explicit warning:** "This notebook is now likely overfit to the public leaderboard" — author states they changed the notebook in response to 0.001–0.003 leaderboard movements after user forks. "Use an earlier version as a baseline, or better, use the public DINOv3 member from `knee-mri-fold-weights` and validate it locally."
- Author asserts the DINOv3 member was "selected on held-out labelled studies, while sub-resolution blend tweaks should be treated as noise."

## 2. Concrete techniques (with exact numbers)
**Base ensemble:**
- Rank-mean of **twenty DINOv2 models** (from pilkwang), plus **one DINOv3 ViT-S/16** added and rank-blended into the family.
- DINOv3 described as "self-supervised and pretrained without labels, then fine-tuned on this competition's knee MRI."

**Architecture:**
- Per-series learned type embedding (plane × fat suppression) added to all tokens of that series.
- Tokens of every series in a study concatenated into one key/value sequence; **twelve learned queries** (one per finding) cross-attend with multi-head attention.
- Each query's output concatenated with mean and max of per-series CLS embeddings before classifier.
- Missing series removed by key-padding mask (nothing imputed).

**RadImageNet blending (two pinned stages):**
- E13 heads fused into "pinned v15 reference family" at **0.50 on ranks**; that family then gets a **0.50 rank vote on ten findings**, with Baker's and Fracture preserved (i.e., those two not replaced by RadImageNet).
- Same E13 heads run a **second time** on the E11 slot layout (three non-fat-suppressed planes at a **130 mm crop**), blended in at **0.15**.

**Removed components:**
- Two earlier stages that replaced individual findings with report/metadata models (Synovitis; Lateral Meniscus with Lateral OA) were removed — "leaving those findings to the image models scored better" (this is an ablation from a user's fork, attributed to tonylica).

**Training/inference config (from code lines):**
- `SEED = 2026`
- `CROP_MM = 130.0`
- `CACHE_IMG = 336`
- `GROUP = 3`, `N_GROUP_MAX = 1`
- `CACHE_FRACTION = 0.45`, `CACHE_BUDGET_MAX_GB = 24.0`, `CACHE_BUDGET_GB = 12.0`
- `TEST_SHARE = 0.3`
- `RUNS = [{'name': 'r224', 'img': 224}, {'name': 'r336', 'img': 336}]`
- `EPOCHS = 10`
- `BATCH_STUDIES = 8`
- `AUG_ROT_DEG = 8.0`, `AUG_SCALE = 0.08`, `AUG_SHIFT = 0.05`, `AUG_INTENSITY = 0.1`
- `LAT_MIN_OFFSET_MM = 20.0`
- `SLICE_BAND = (0.2, 0.8)`
- `LR_HEAD = 0.001`, `LR_BACKBONE = 8e-06`
- `UNFREEZE_LAST = 6`
- `WEIGHT_DECAY = 0.02`
- `EVAL_BATCH = 8`
- `TIME_BUDGET = 8.0 * 3600`
- `SLOT_PRIOR_STRENGTH = 0.55`
- `POOL_PARTS = {'cls_mean': 2, 'cls_mean_focal': 3}`
- `SLOT_SCHEME` defaults to `'recovered'` (uses `SLOTS_RECOVERED` unless env var `public`)
- `ORDER_TAGS = [(32, 50), (32, 55), (32, 19)]`
- `NEG_WINDOW = 90`, `FEATURES` flags: `unwrap=True`, `directional_negation=True`, `oa_inherit=True`, `graded_pathology=True`, `synovitis_backoff=True`

**Report-extractor formulas (label generation):**
- Positive score: `min(0.97, 0.5 + 0.45*best + 0.015*min(n_pos,3))`, conf `min(1.0, 0.55 + 0.15*n_pos)`
- Negative score: `max(0.04, 0.2 - 0.04*n_neg)`, conf `min(0.9, 0.45 + 0.12*n_neg)`
- Synovitis prior: `0.3 + 0.3*max(0.0, (eff - 0.5)/0.45) + 0.06*min(proxy,3)`
- OA scoring with `GRADE_HIGH` regex and severity handling.

## 3. Ablations / measured effects
- **Supporting evidence cited from a fork (tonylica):** running the pipeline with the two per-finding specialists (Synovitis; Lateral Meniscus+OA) left out "scored higher than the one with them, which is what led to their removal here." No numeric delta given; this is a qualitative directional claim attributed to a fork, not the author's own ablation.
- **No other numeric ablations** are reported in this notebook.
- The author explicitly cautions that sub-resolution blend tweaks (0.001–0.003 movements) "should be treated as noise" — implying the 0.50/0.50/0.15 blend weights and similar are NOT validated by meaningful ablations, only by noisy LB movements.

## 4. Resources / reproducibility requirements
- **Attached/required datasets:** pilkwang's twenty trained models; three label tables (pilkwang, stevenleehans+lixin73, tonylica); tonylica's four trained models; RadImageNet ResNet-50 official weights (marwanmath); the public DINOv3 member from `knee-mri-fold-weights` (recommended as baseline).
- **Upstream notebooks:** forked from prvsiyan's notebook (Apache 2.0) but with "most of its later stages removed"; builds on cf696666's E10/E11 RadImageNet machinery (four-slot E11, E10 blend with two findings left out), romantamrazov's fold-rank aggregation and adaptive second-pass weighting (his public DINOsaur V3 notebook; implementation here is original), ieshanmeghani's v15/E10 RadImageNet delta, sofiaanjenje's five-fold E11 and E13 heads (including E13 fat-sensitive crop arm), saidmohamedomary's V48, and sakhawathossen/ranjithragavan07's no-extra-pass fold-balanced/smooth DINO aggregation.
- **Reproduction requires:** a Kaggle environment with the competition data, the listed public datasets, and likely multiple GPUs (`DEVS` probing for `cuda:{index}`).

## 5. Author's warnings/caveats
- **"This notebook is now likely overfit to the public leaderboard."** Explicitly states the notebook was tuned in response to 0.001–0.003 LB movements from user forks, and calls that "not meaningful model development."
- **"Changing one or two parameters and presenting the pipeline as a new solution is opportunistic reuse, not original work."**
- **Recommendation:** "Use an earlier version as a baseline, or better, use the public DINOv3 member from `knee-mri-fold-weights` and validate it locally; it was selected on held-out labelled studies, while sub-resolution blend tweaks should be treated as noise."
- No other explicit performance caveats.

## 6. Confidence that each technique causes score (SUPPORTED / ASSERTED / UNCLEAR)

| Technique | Confidence | Rationale |
|---|---|---|
| DINOv3 ViT-S/16 addition (rank-blended into 20 DINOv2) | **ASSERTED** | Claimed as "the added member," but no ablation isolating its contribution to score is shown in this source. Author recommends it as the validated component (selected on held-out labelled studies, per narrative) but presents no numbers. |
| Removing Synovitis and Lateral Meniscus+OA report/metadata specialists | **SUPPORTED (weakly, via fork)** | Author states tonylica's fork without those specialists "scored higher than the one with them" — but this is qualitative, no delta, and from a user fork rather than the author's own controlled ablation. |
| RadImageNet E13/E11 two-stage blending (0.50 rank / 0.50 rank on 10 findings / 0.15 second pass) | **ASSERTED / UNCLEAR** | Blend weights are described as pinned, but author warns sub-resolution blend tweaks are "noise" and the notebook is "overfit to the public leaderboard." No ablation isolating these weights is presented. |
| Cross-attention over concatenated study tokens with twelve queries | **ASSERTED** | Architectural description only; no ablation vs. per-series-summary aggregation. |
| Per-series type embedding (plane × fat suppression) | **ASSERTED** | Described but not ablated. |
| Key-padding mask (no imputation of missing series) | **ASSERTED** | Described; no ablation. |
| Report-extractor label generation rules with the given scores/confs | **ASSERTED** | Formulas given, but no evaluation against gold labels is shown in this source (other sources in the family discuss silence rate/agreement; this one does not). |
| 130 mm crop, 336 cache image, 224/336 dual runs | **ASSERTED** | Config values given; the 336 resolution's necessity is argued in other sources but not ablated here. |
| Augmentation (rot 8°, scale 0.08, shift 0.05, intensity 0.1) | **ASSERTED** | No ablation. |
| LR head 0.001 / backbone 8e-06, unfreeze last 6 blocks, WD 0.02 | **ASSERTED** | No ablation. |
| `SLOT_SCHEME = 'recovered'` default | **ASSERTED** | No comparison vs. `public` scheme shown here. |

**Overall:** This notebook provides almost no self-contained evidence for what drives its score. Nearly every claim is asserted, the one ablation cited is from another user's fork (qualitative), and the author's own dominant caveat is that the pipeline is overfit to the public leaderboard through noise-level tweaks. The DINOv3 member is the only component the author recommends trusting, on grounds of a held-out selection procedure, but no score or effect size is given even for that.