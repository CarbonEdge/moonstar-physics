(1) **Headline claim & score**
- Title: "Bend the Knee to the Dinosaurs (ALL PUBLIC)"; adds a new CoAtNet MRI reader to an existing ensemble. Describes itself simply as "Inference-only submission."
- **No score is reported anywhere in this source.** (The 0.941 figure appears in other sources, which I am excluding.) No leaderboard number, no local validation number, no ablation table.

(2) **Concrete techniques (numbers as given)**
- **New member:** "384 px adjacent-slice triplet" → "CoAtNet RMLP-2 backbone".
- **Head design:** "a finding-specific gated spatial head blends localized evidence with a protected global-average residual; a second finding-specific attention stage pools windows across the study."
- **Combination within the member:** "Three checkpoints are combined by per-finding rank averaging before joining the existing ensemble" (no reduction weights given).
- **Ensemble context:** joins "the existing ensemble" (the notebook's credits imply a prior DINO/RadImageNet pipeline; no routing weights given here).
- **Input/preprocessing constants in code:** `CROP_MM = 130.0`; `CACHE_IMG = 336`; `GROUP = 3` (three slices stacked as channels); `N_GROUP_MAX = 1`; `CACHE_FRACTION = 0.45`; `CACHE_BUDGET_MAX_GB = 24.0`; `CACHE_BUDGET_GB = 12.0`; `TEST_SHARE = 0.3`; `HDR_THREADS = 16`; `PIX_THREADS = 12`; `ORDER_THREADS = 32`; `ORDER_BUDGET_S = 5400`; `SEED = 2026`.
- **Training hyperparameters present in config (shared from parent pipeline, not claimed as new):** `LR_HEAD = 0.001`; `LR_BACKBONE = 8e-06`; `UNFREEZE_LAST = 6`; `WEIGHT_DECAY = 0.02`; `EPOCHS = 10`; `BATCH_STUDIES = 8`; `EVAL_BATCH = 8`; `AUG_ROT_DEG = 8.0`; `AUG_SCALE = 0.08`; `AUG_SHIFT = 0.05`; `AUG_INTENSITY = 0.1`; `TIME_BUDGET = 8.0 * 3600`; `RUNS = [{'name': 'r224', 'img': 224}, {'name': 'r336', 'img': 336}]`.
- **Slot handling:** `SLOT_SCHEME = os.environ.get('SLOT_SCHEME', 'recovered')`; `SLOTS = SLOTS_PUBLIC if SLOT_SCHEME == 'public' else SLOTS_RECOVERED`; `POOL_PARTS = {'cls_mean': 2, 'cls_mean_focal': 3}`; `SLOT_PRIOR_STRENGTH = 0.55`; `FATSAT_OPTS = {'FS', 'FATSAT', 'FAT_SAT', 'FSAT'}`; series selection rules `RULES_NATIVE = {'order': 'normal', 'lat': 'centre', 'slot_fallback': False, 'decode_fill': 'nearest'}`.
- **Geometry ordering code fragments:** slice order via `ImageOrientationPatient`/`ImagePositionPatient`; `LAT_MIN_OFFSET_MM = 20.0`; `SLICE_BAND = (0.2, 0.8)`; `LEGACY_LAT_OFFSET_MM = 5.0`.
- **GPU selection:** `DEVS` built only from CUDA devices that pass a 1×3×16×16 conv `_cuda_execution_probe`.
- No TTA parameters are given in this source.

(3) **Ablations / measured effect sizes**
- None reported. The only comparative statement is "Inspired by dreaddevelopment's discussion". No "version X scored Y" claims inside this source.

(4) **Resources & reproduction requirements**
- Attached dataset: "my public CoAtNet MRI model" — https://www.kaggle.com/datasets/mattiaangeli/rsna-knee-coat-resgated-ep10-top3 (three checkpoints, "ep10 top3").
- Credits/artifacts relied on: Pilkwang's weights, Sofia Anjenje, Antoine G., prvsiyan, Marwan Mahmoud, dreaddevelopment/Roman Tamrazov, renta.k, Anvith Pothula, Evgen Dvorkin (datasets/notebooks).
- Repro needs: the mounted CoAtNet model weights, the competition DICOM data, multi-GPU CUDA devices passing the probe, and the parent ensemble's predictions to blend into.

(5) **Author's warnings / caveats**
- "Inference-only submission." (i.e., no training here; assumes upstream checkpoints and ensemble outputs are mounted.)
- No explicit overfitting or caution statements in this source.

(6) **Confidence that each technique causes the score**
- CoAtNet RMLP-2 backbone at 384 px input: ASSERTED (no ablation in this source).
- Gated spatial head + protected global-average residual: ASSERTED (no ablation).
-