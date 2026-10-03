# Source: `rsna-knee-baseline-v1`

## (1) Headline claim and score
- **No headline score reported in this notebook.**  
  The notebook describes design decisions and does not claim a final leaderboard score.  
  The text explains the metric structure and constraints, but no version-specific public or private score is given.

## (2) Concrete techniques with numbers

### Architecture
- **Encoder:** unspecified transformer-based encoder (referred to as "the encoder" throughout).  
  - `UNFREEZE_LAST = 6` — last 6 transformer blocks are trainable from the output end.  
  - `LR_BACKBONE = 8e-06` for the encoder backbone.  
  - `LR_HEAD = 1e-3` for the classification head.  
- Input: a study is a bag of up to `N_SLOT` slot images.

### Input design / Slots
- **6 anatomical slots** defined:
  - `SAG_FLUID_FS` — sagittal, PD/T2, fat-sat
  - `COR_FLUID_FS` — coronal, PD/T2, fat-sat
  - `AX_FLUID_FS` — axial, PD/T2, fat-sat
  - `SAG_FLUID_NOFS` — sagittal, PD/T2, no fat-sat
  - `COR_T1` — coronal, T1, no fat-sat
  - `SAG_T1` — sagittal, T1, no fat-sat
- **Two slot definitions:** `SLOTS_RECOVERED` (default) and `SLOTS_PUBLIC`, selected via env var `SLOT_SCHEME` with default `"recovered"`.
- Each slot has a per-study presence mask (carries absences into the head).

### Slice counts / Grouping
- `GROUP = 3` — slices per encoder input, stacked as three channels.
- `N_GROUP_MAX = 1` — maximum groups per study (since `CACHE_SLICES = GROUP * N_GROUP`).
- Slice sampling: fractions are sampled across band `SLICE_BAND = (0.20, 0.80)` of the ordered stack.
- `CACHE_IMG = 336` — image size used by pixel cache.

### Resolution / Physical scale
- `CROP_MM = 130.0` — constant physical crop extent in mm.
- Two resolution runs: `RUNS = [{'name': 'r224', 'img': 224}, {'name': 'r336', 'img': 336}]`.
- At 130 mm: 224 px → 0.580 mm/pixel; 336 px → 0.387 mm/pixel.
- A 14-pixel patch token at 336 px corresponds to 5.4 mm.
- Crop is applied only if the field of view is large enough; otherwise the series passes through unnormalised.

### Preprocessing / DICOM
- **Slice ordering:** recovered from geometry: `k = p · n̂` where `n̂ = r̂_x × r̂_y`; `InstanceNumber` is fallback.
- **Laterality:** two rules:  
  `RULES_NATIVE = {"order": "normal", "lat": "centre", "slot_fallback": False, "decode_fill": "nearest"}`  
  `RULES_LEGACY = {"order": "dominant_axis", "lat": "corner_x", "slot_fallback": True, "decode_fill": "zero"}`  
  Default is `RULES_NATIVE`.
- `LAT_MIN_OFFSET_MM = 20.0` — inside this distance the side is not readable from geometry.
- `LEGACY_LAT_OFFSET_MM = 5.0` — dead zone the legacy laterality rule was fitted with.
- **Intensity:** per-series normalisation to 1st and 99th percentiles over the sampled stack (not per slice).
- **Fat suppression detection:** `FATSAT_OPTS = {"FS", "FATSAT", "FAT_SAT", "FSAT"}` and also recovered from `ScanningSequence` for gradient echo.

### Label handling
- **Two label sources:**  
  1. A multilingual rule extractor (lexicon-based, 9 languages, grade scoring).  
  2. A language model table (mounted dataset), preferred when present.  
- Per-finding confidences become sample weights.
- Targets are graded (not binary); binarised at midpoint **only for validation** (thresholding chooses epochs/arms, never submitted scores).
- Report-derived labels: if a report never mentions a finding, its head pulls weakly.
- **Report details:**
  - Normalised via `unicodedata.normalize("NFKD", text)`, lowercased, diacritics removed, soft hyphen removed.
  - Unwrap step (`FEATURES["unwrap"] = True`): lines not ending in sentence punctuation are continuations.
  - Clause splitting with heading line attachment.
  - Negation window: `NEG_WINDOW = 90`.
  - Features flags: `{'unwrap': True, 'directional_negation': True, 'oa_inherit': True, 'graded_pathology': True, 'synovitis_backoff': True}`.

### Loss / Training
- **Epochs:** `EPOCHS = 10`.
- **Batch:** `BATCH_STUDIES = 8` — a study is a bag of up to N_SLOT slot images.
- **Augmentation:**  
  - `AUG_ROT_DEG = 8.0` — rotation jitter  
  - `AUG_SCALE = 0.08` — scaling jitter  
  - `AUG_SHIFT = 0.05` — shift jitter  
  - `AUG_INTENSITY = 0.10` — intensity jitter  
  - No flips used (stated explicitly).
- **Optimiser:** `WEIGHT_DECAY = 0.02`.
- **Evaluation batch:** `EVAL_BATCH = 8`.

### Aggregation / Blending
- **Rank averaging** for model combination (since AUC reads only order).
- **Slot-prior table:** `SLOT_PRIOR_TABLE` exists; `SLOT_PRIOR_STRENGTH = 0.55`.
- **Pooling parts:** `POOL_PARTS = {"cls_mean": 2, "cls_mean_focal": 3}`.

### TTA
- **No explicit TTA mentioned.**

### Cache / Memory
- `CACHE_FRACTION = 0.45` — share of free memory for pixel cache.
- `CACHE_BUDGET_MAX_GB = 24.0` — hard ceiling.
- `CACHE_BUDGET_GB = 12.0` — fallback.
- `TEST_SHARE = 0.30` — floor on test corpus relative to training.
- Time budget: `TIME_BUDGET = 8.0 * 3600` seconds.

### Threads
- `HDR_THREADS = 16`  
- `PIX_THREADS = 12`  
- `ORDER_THREADS = 32`  
- `ORDER_BUDGET_S = 5400`

## (3) Ablation or measured effect size
- **None reported.** The notebook describes constraints and design logic but does not present ablation studies or quantified effects of individual techniques.

## (4) Resources and reproduction requirements

### Datasets attached
- The notebook expects competition data mounted at `/kaggle/input`.
- A mounted table of model-read labels is used when present (path discovered via `find_label_table()`). The notebook falls back to the lexicon when this table is missing.
- No custom model weights are distributed by this notebook.

### Reproduction requirements
- Kaggle environment with competition data mounted.
- The notebook is self-contained: the lexicon is defined in-line, not from a file.
- Env var `SLOT_SCHEME` (optional, defaults to `"recovered"`) selects between public and recovered slot definitions.

## (5) Warnings or caveats
- **On slicing order:** "The file name is the SOP Instance UID… sorting by it yields a sequence uncorrelated with anatomy — measured on a series from this corpus, the rank correlation between file-name order and physical position is ρ ≈ 0.01."
- **On scale:** "A feature narrower than two pixels does not survive the resize… a meniscal tear is one to three millimetres, so at d=1 mm the pitch must be at most 0.5 mm."
- **On crop limits:** "The crop must be smaller than the smallest field of view or it silently does nothing: if L/s exceeds the image width the crop cannot be taken and that series passes through unnormalised, with no error."
- **On label source coverage:** The lexicon has a language-dependent silence gap; coverage (not agreement) is the metric to steer by because the annotated set is too small for reliable AUC-based tuning.
- **On report-derived labels:** "A report shared verbatim by several studies yields one target vector for all of them, which must be respected when splitting."
- **On the label columns:** `train.csv` has a `Report` column; `test.csv` does not. "That rules out a fusion model with a text branch."
- **On graded targets:** Graded targets are binarised at midpoint only for validation; "that cutoff decides which epoch and configuration are kept, never a submitted score."

## (6) Confidence in technique effect

| Technique | Confidence | Evidence |
|-----------|-----------|----------|
| Rank averaging for model combination (not probability averaging) | **SUPPORTED** (by metric analysis) | Notebook argues: "averaging raw probabilities lets whichever model is most confident dominate, whereas averaging ranks combines the only information the metric reads." This is a logical deduction from AUC invariance, not an empirical ablation. |
| Per-finding confidences as sample weights | **ASSERTED** | Stated but no ablation comparing weighted vs unweighted training. |
| 6-slot anatomical design | **ASSERTED** | Described as "chosen so each of the twelve findings has at least one sequence that shows it well." No comparison to fewer/more slots. |
| 130 mm crop + 336 px resolution | **ASSERTED** | Physical reasoning about Nyquist for 1 mm features motivates the resolution choice. No ablation comparing resolutions. |
| Geometry-based slice ordering vs filename sorting | **SUPPORTED** (by measurement) | Measured rank correlation "ρ ≈ 0.01" between filename order and physical position. |
| Per-series (not per-slice) intensity normalisation | **ASSERTED** | Stated: "so slices keep their relative contrast." No ablation. |
| Rule-based report reader | **ASSERTED** | Coverage analysis is described qualitatively (language gaps) but no quantitative comparison to an alternative label source. |
| Unwrap before clause splitting | **ASSERTED** | Illustrated with a Spanish example. No ablation. |
| Directional negation anchored on pathology word | **ASSERTED** | Illustrated with English examples. No ablation. |
| OA inheritance for unlocalised cartilage statements | **ASSERTED** | Described as preventing 3/4 of the corpus being silent on OA targets. No ablation. |
| No flips in augmentation | **ASSERTED** | Stated: "see augment() for why neither flip is used." The reasoning is not reproduced. |