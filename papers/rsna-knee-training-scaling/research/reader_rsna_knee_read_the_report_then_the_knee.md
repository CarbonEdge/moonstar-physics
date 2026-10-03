**Source analysed:** `rsna-knee-read-the-report-then-the-knee`

---

### (1) Headline claim and score

- **Highest verified public score: 0.906.** Version 52 (completed Kaggle row submission 55399732) establishes this result. The submitted artifact was bitwise matched to the audited 20% RadImageNet rank blend.
- Version 46 established 0.899.
- Version 49 independently tested the five-fold EfficientNet-B3 contribution at 0.898.
- A table of reproducible public runs shows: V14 = 0.894 (Fracture max + OOF-selected target-wise rank blend); V46 = 0.899 (exact audited specialist artifact); V49 = 0.898 (guarded five-fold EfficientNet-B3 rank contribution); V52 = 0.906 (independent RadImageNet ResNet-50, 20% rank vote).
- External Yash Bishnoi reference = 0.903 (inspected five-fold B3 MIL recipe; not this notebook's score).

---

### (2) Every concrete technique with numbers given

**Architecture:**
- RadImageNet ResNet-50 is the independent arm added in V52.
- A five-fold EfficientNet-B3 MIL recipe is mentioned as tested (V49).
- Base ensemble: 20 DINOv2 members (from Pilkwang V15 public anchor, 0.891).
- DINOv3 ViT-S/16 added in a later variant (but that is from a different source — **not** part of this notebook's described pipeline).

**Input design / Slice counts / Resolution:**
- Crop to constant physical extent: **L = 130 mm**.
- Resize target: **336 px** (CACHE_IMG = 336) → effective pitch = 130/336 = **0.387 mm/pixel**; a 14-pixel patch token = **5.4 mm**.
- A second run uses **224 px** → 0.580 mm/pixel.
- Stacked slices per encoder input: **GROUP = 3** slices as three channels.
- N_GROUP_MAX = 1.
- Slice sampling band: **SLICE_BAND = (0.20, 0.80)** (fraction of ordered stack sampled across).
- Slots (six): SAG_FLUID_FS, COR_FLUID_FS, AX_FLUID_FS, SAG_FLUID_NOFS, COR_T1, SAG_T1.

**Preprocessing:**
- Series normalised per stack (not per slice) to its own 1st and 99th percentile.
- DICOM slice order recovered from geometry: k = p·n (dot product of ImagePositionPatient with cross product of ImageOrientationPatient). InstanceNumber is fallback.
- Laterality from geometry (median X-coordinate) with fallback to Laterality tag.
- Fat suppression recovered from SeriesDescription, SequenceName, ScanOptions and TR/TE; FATSAT_OPTS = {"FS", "FATSAT", "FAT_SAT", "FSAT"}.

**Label handling / Training targets:**
- A nine-language multilingual rule extractor reads each radiology report clause-by-clause, producing a graded score and a confidence per finding.
- The confidence becomes a per-finding sample weight.
- A mounted table of model-read labels (from a language model) is preferred when present; the rule extractor is the fallback.
- Graded targets are binarised at their midpoint for validation only.
- FEATURES flags: unwrap=True, directional_negation=True, oa_inherit=True, graded_pathology=True, synovitis_backoff=True.

**Loss:**
- Not explicitly stated; the loss is weighted per finding using the confidence from the extractor (sample weights).

**Aggregation / Blending / Routing:**
- **Rank mean** is used for all model combinations (not average of probabilities).
- RadImageNet ResNet-50 contributes at **20% rank vote** in the final blend (V52).
- The rule for combining: averaging ranks, not raw probabilities.
- Fracture max + OOF-selected target-wise rank blend used in V14.

**TTA:**
- Not mentioned.

---

### (3) Ablation or measured effect size

- The notebook reports an **ablation table** (reproduced from code) comparing configurations: "all rules on" vs. turning off individual FEATURES. The table shows macro AUC and mean silence rate for each configuration.
- Agreement gauge: AUC on the 58 annotated studies is computed per target, with Hanley-McNeil 95% intervals plotted (e.g., at A≈0.85 with 9 positives among 58, SE ≈ 0.083, interval ≈ ±0.16).
- Silence rate (fraction of (study, target) pairs where no rule fired) is measured on all 4,407 reports.
- Coverage by language is visualised in a heatmap.

**Quoted effect sizes:**
- "a label left at chance contributes 0.5 instead of roughly M, forfeiting (M-0.5)/12 — at M=0.85, 0.029".
- The difference between V52 (0.906) and V14 (0.894) is +0.012 from the RadImageNet rank blend.

---

### (4) Resources attached / required to reproduce

- The notebook attaches a **rule extractor defined in-line** (no external file); it runs over the whole corpus in seconds.
- It references a **mounted table of model-read labels** (from a language model) as an attached dataset. If present, it supplies the targets; if absent, the rule extractor does.
- Requires: `train.csv` (with Report column), DICOM series in `train_images`/`test_images`, and the competition DICOM metadata.
- For V52: a RadImageNet ResNet-50 checkpoint (public weights: RadImageNet).
- For V49: a five-fold EfficientNet-B3 checkpoint.
- The notebook states: "A notebook that ships its own labels cannot quietly train against a stale copy of them."

---

### (5) Author's own warnings or caveats

- **Scorecard boundary:** "The scorecard separates completed official rows from local validation and from other authors' public references. Only a completed Kaggle submission can change the verified public score above."
- **On validation with 58 labelled studies:** "Choosing between two lexicons on a single one of these numbers is choosing by coin flip, and it will feel like signal every time."
- **On silent failures:** "A rule that never fires does not raise an error — it emits a negative, indistinguishable from a confident one. A lexicon complete in English and thin in Greek does not look broken; it looks like a corpus in which Greek patients have fewer findings. The error is not random: language tracks the reporting institution, which tracks the scanner and the population."
- **On prevalence drift:** "AUC is, in expectation, invariant to the positive rate, and the data description warns that prevalence need not match across the training, public and private sets."
- **On the crop limit:** "If L/s exceeds the image width the crop cannot be taken and that series passes through unnormalised, with no error."
- **On the file name ordering trap:** "Sorting by [SOP Instance UID] yields a sequence uncorrelated with anatomy — measured on a series from this corpus, the rank correlation between file-name order and physical position is ρ ≈ 0.01."

---

### (6) Confidence that each technique is a real cause of score

| Technique | Evidence | Confidence |
|---|---|---|
| RadImageNet ResNet-50 20% rank blend | Directly attributed to V52's +0.012 gain over V14; V52 is the highest verified score (0.906) | **SUPPORTED** (ablation by comparison of runs) |
| Nine-language rule extractor with graded scoring + per-finding sample weights | Ablation table (FEATURES on/off) shows macro AUC and silence rate changes; needed because only 58 labelled studies exist | **SUPPORTED** (ablation presented) |
| Unwrap before splitting (FEATURES["unwrap"]) | Ablated in the FEATURES table | **SUPPORTED** (ablation presented) |
| Directional negation (FEATURES["directional_negation"]) | Ablated in the FEATURES table | **SUPPORTED** (ablation presented) |
| OA inheritance (FEATURES["oa_inherit"]) | Ablated in the FEATURES table | **SUPPORTED** (ablation presented) |
| Graded pathology (FEATURES["graded_pathology"]) | Ablated in the FEATURES table | **SUPPORTED** (ablation presented) |
| Synovitis backoff (FEATURES["synovitis_backoff"]) | Ablated in the FEATURES table | **SUPPORTED** (ablation presented) |
| Physical-scale crop (130 mm → 336 px, 0.387 mm/pixel) | Argued from Nyquist condition for 1 mm meniscal tear; no direct ablation but stated as a design constraint | **ASSERTED** (theoretical justification, no ablation) |
| Rank mean blending (not probability mean) | Derived from AUC's invariance to monotonic transforms; used in all combinations | **ASSERTED** (reasoning, no ablation) |
| Geometry-based DICOM slice ordering | Measured that file-name sorting gives ρ≈0.01; no ablation on score | **ASSERTED** (measured degradation of naive method, but not ablated on final score) |
| Per-finding sample weights from report confidence | Described as necessary to avoid training silence as confident negative; no ablation | **ASSERTED** (reasoning, no ablation) |
| Five-fold EfficientNet-B3 (V49) | Independent test at 0.898; not the highest score | **SUPPORTED** (run comparison) |
| Fracture max + OOF target-wise rank blend (V14) | Established 0.894, superseded by later runs | **SUPPORTED** (run comparison, but superseded) |
| TTA | Not mentioned | **N/A** |