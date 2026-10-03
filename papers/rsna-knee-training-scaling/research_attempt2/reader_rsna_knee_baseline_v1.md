# Analysis of `rsna-knee-baseline-v1`

## (1) Headline claim and score
- **No official leaderboard score reported anywhere in this notebook.** The narrative repeatedly states the metric (mean of 12 per-label AUCs) but never claims a specific achieved score.
- Score definition is stated: `Score = (1/12) Σ AUC_i` — unweighted mean of twelve per-label ROC AUCs.
- No version/evidence of any reported score exists; the notebook describes architecture and rationale but no outcome.

## (2) Concrete techniques (exact numbers quoted)

### Input / preprocessing
- `CROP_MM = 130.0` (mm crop, "below the acquired field of view of almost every series here")
- `CACHE_IMG = 336`; resize target 336 px → `0.387 mm/pixel`; also mentions 224 px → `0.580 mm/pixel` (with 130mm crop, a 14-pixel patch token at 336 = `5.4 mm`)
- `GROUP = 3` (slices per encoder input, "stacked as the three channels")
- `SLICE_BAND = (0.20, 0.80)` (fraction of ordered stack sampled)
- 1st/99th percentile intensity normalization "over the sampled stack rather than per slice"
- `LAT_MIN_OFFSET_MM = 20.0` (inside this the side is not readable from geometry)
- `RULES_NATIVE = {"order": "normal", "lat": "centre", ...}`; `RULES_LEGACY = {"order": "dominant_axis", "lat": "corner_x", "slot_fallback": True, "decode_fill": "zero"}`; default `RULES = dict(RULES_NATIVE)`
- `LEGACY_LAT_OFFSET_MM = 5.0`
- Slice ordering recovered from geometry: `n = r_x × r_y; k = p · n` (signed patient-coordinate position); fallback `InstanceNumber`.
- `ORDER_BUDGET_S = 5400`; `HDR_THREADS = 16`, `PIX_THREADS = 12`, `ORDER_THREADS = 32`
- `CACHE_FRACTION = 0.45`, `CACHE_BUDGET_MAX_GB = 24.0`, `CACHE_BUDGET_GB = 12.0`, `TEST_SHARE = 0.30`
- Measured: file-name order vs physical position rank correlation `ρ ≈ 0.01` on a series from this corpus.

### Slots (series selection)
Six anatomical slots: `SAG_FLUID_FS`, `COR_FLUID_FS`, `AX_FLUID_FS`, `SAG_FLUID_NOFS`, `COR_T1`, `SAG_T1`; per-slot presence mask; `SLOTS_PUBLIC` vs `SLOTS_RECOVERED` (`SLOT_SCHEME = os.environ.get("SLOT_SCHEME", "recovered")`), `N_SLOT = len(SLOTS)`.
- Weighting determined from TR/TE thresholds: T1 `TR ≲ 800 ms`; T2 `TR ≳ 800 ms, TE ≳ 60 ms`; PD `TR ≳ 800 ms, TE ≲ 60 ms`; GRE settled by `ScanningSequence` first.
- `FATSAT_OPTS = {"FS", "FATSAT", "FAT_SAT", "FSAT"}`

### Model / training
- `RUNS = [{'name': 'r224', 'img': 224}, {'name': 'r336', 'img': 336}]`
- `EPOCHS = 10`; `BATCH_STUDIES = 8` ("a study is a bag of up to N_SLOT slot images")
- `LR_HEAD = 1e-3`; `LR_BACKBONE = 8e-6` ("encoder is adapted, not retrained")
- `UNFREEZE_LAST = 6` (trainable transformer blocks from output end)
- `WEIGHT_DECAY = 0.02`; `EVAL_BATCH = 8`; `TIME_BUDGET = 8.0 * 3600`
- `SEED = 2026`
- `POOL_PARTS = {"cls_mean": 2, "cls_mean_focal": 3}`; `SLOT_PRIOR_STRENGTH = 0.55`
- Augmentation: `AUG_ROT_DEG = 8.0`, `AUG_SCALE = 0.08`, `AUG_SHIFT = 0.05`, `AUG_INTENSITY = 0.10`; "neither flip is used."

### Label handling / report extractor
- Two readers: a multilingual rule extractor (defined in full) and an LM-read public table; mounted table preferred, extractor as fallback; partial table falls back "per study rather than per run."
- Confidence from extractor becomes sample weight (`conf = min(1.0, 0.55 + 0.15*n_pos)`; `conf = min(0.9, 0.45 + 0.12*n_neg)`).
- Graded (not binary) targets; binarized at midpoint only for held-out AUC computation.
- `NEG_WINDOW = 90` (character window); `PAIRED = {"ACL", "MCL", "Medial Meniscus", "Lateral Meniscus"}`; `OA_TARGETS = {"Medial OA", "Lateral OA", "PF OA"}`
- Lexicon scoring: e.g., `score = min(0.95, 0.50 + 0.42*best + 0.03*min(n_pos,3))`; `score = max(0.04, 0.20 - 0.04*n_neg)`
- `FEATURES` flags include `unwrap`, `directional_negation`, `oa_inherit`, `graded_pathology`, `synovitis_backoff` (in companion source; baseline mentions four non-obvious rules but does not list flags here).

### Aggregation / combination
- Rank averaging chosen (not probability averaging) because "AUC is invariant under any strictly increasing map" — "averaging *ranks* combines the only information the metric reads."
- No explicit final blend weights given in this notebook.

### Data split
- Derived labels not independent across studies (shared verbatim reports); §7 respects this when splitting.

## (3) Ablations / measured effect sizes
- **None reported in this notebook.** No ablation tables, no effect sizes, no score comparisons.
- The only measured quantity: `ρ ≈ 0.01` (file-name vs physical slice order).
- Hanley–McNeil SE example stated analytically (not as an ablation): at `A≈0.8`, handful of positives among few dozen studies, `SE ≈ 0.09`, 95% interval `±0.17`.

## (4) Resources attached / required to reproduce
- Attaches: a public table of LM-read labels ("attached as a dataset" — mounted, with fallback to extractor if absent).
- Requires: `train.csv` `Report` column (for extractor), DICOM series with geometry tags (`ImageOrientationPatient`, `ImagePositionPatient`), T4-type GPU implied by config.
- No trained weights attached in this notebook itself.
- `ROOT = find_root()` locates competition data.

## (5) Author's warnings / caveats
- "A lexicon of complete phrases carries most matches but cannot survive morphology" — hence stem+window fallback.
- "The crop must be smaller than the smallest field of view or it silently does nothing… with no error."
- "A rule that never fires raises no error; in a binary extractor it emits a negative, indistinguishable from a confident one." Silence rate is the measured gauge, not agreement, because agreement "measures the right thing on far too few studies" (58 annotated).
- Language coverage gap: "one language is covered far better than the other eight."
- "Reports are graded, annotations are thresholded" — mismatch is by construction.
- Sorting by filename yields order "uncorrelated with anatomy" with no error.
- AUC invariance argument: "calibration and thresholds are worth nothing" — thresholds only used internally for held-out AUC.

## (6) Confidence that each technique causes score

| Technique | Confidence | Basis |
|---|---|---|
| Rank averaging (vs probability) | ASSERTED | Argument from AUC invariance; no ablation |
| 130 mm crop / 336 px (0.387 mm/px) | ASSERTED | Nyquist argument (tear 1–3 mm needs ≤0.5 mm/px); no measured ablation |
| Slice reordering from geometry (vs filename) | ASSERTED | ρ≈0.01 measured but no downstream AUC effect shown |
| 1st/99th percentile stack normalization | ASSERTED | No ablation |
| Per-slot presence mask | ASSERTED | No ablation |
| Six-slot design (plane × weighting × fat-sat) | ASSERTED | Rationale by anatomy; no ablation |
| Graded targets + confidence sample weighting | ASSERTED | Rationale only; no ablation |
| Multilingual union lexicon (no language routing) | ASSERTED | Argument against routing failure; no measured effect |
| LM-read labels preferred over lexicon | ASSERTED | "difference is large and one-sided" — stated but **no numbers given** |
| Unfreeze last 6 blocks, LR 8e-6 backbone | ASSERTED | No ablation |
| 3-slice channel stacking (GROUP=3) | ASSERTED | No ablation |
| Binarize at midpoint for validation only | ASSERTED | Necessary for AUC computation; no effect claimed |
| Per-study split (shared reports) | ASSERTED | Correctness argument; no effect measured |

**Overall:** This notebook is a design-rationale document with essentially no experimental evidence attached — no reported score, no ablations, no measured effect sizes beyond the slice-order correlation. Every technique is ASSERTED (justified by first-principles arguments about AUC, Nyquist, DICOM geometry) rather than SUPPORTED by any ablation. The one measured quantity (ρ≈0.01) supports the claim that filename ordering is wrong but does not quantify its impact on the final score.