Here is the analysis of the source `rsna-knee-read-the-report-then-the-knee`.

### (1) Headline claim and score

- **Highest verified public score for this notebook: 0.906.**
- Evidence: Version 52 (Kaggle row, submission 55399732). The submitted artifact was "bitwise matched to the audited 20% RadImageNet rank blend."
- Progression: V14 = 0.894; V46 = 0.899; V49 = 0.898; V52 = **0.906**.
- Score is the unweighted mean of twelve per-label ROC AUCs: `Score = (1/12) * sum(AUC_i)`.

### (2) Concrete techniques, with numbers

- **Architecture (Ensemble):** "Three arms" — the image ensemble; one arm is a RadImageNet ResNet-50 at "20% rank vote."
- **Input/slice design (slot scheme):** Uses six anatomical slots mapping plane × weighting × fat suppression (e.g., `SAG_FLUID_FS`, `COR_T1`, etc.).
- **Resolution (CROP_MM, CACHE_IMG):** `CROP_MM = 130.0 mm`. `CACHE_IMG = 336`. Pixel pitch is fixed at `L/P = 130/336 ≈ 0.387 mm/pixel` (from narrative, not a code literal).
- **Preprocessing:** Intensity normalised "per series" using "1st and 99th percentile... over the sampled stack, rather than per slice." DICOM geometry: slice order recovered from `ImageOrientationPatient` and `ImagePositionPatient`.
- **Label handling (Report extraction):** A nine-language, rule-based extractor. Features include `unwrap: True`, `directional_negation: True`, `oa_inherit: True`, `graded_pathology: True`, `synovitis_backoff: True`. Negation window: `NEG_WINDOW = 90`. Scores are graded (e.g., `score = min(0.97, 0.50 + 0.45 * best + 0.015 * min(n_pos, 3))`). Per-finding confidence becomes a sample weight.
- **Loss:** Not specified (code omitted in the narrative).
- **Aggregation (Combining models):** "Every combination in §8 is a rank mean."
- **Label table fallback:** Uses a mounted table of model-read labels when present; falls back to the lexicon per study when missing.
- **Blending weights:** RadImageNet added at "20% rank vote."

### (3) Ablation or measured effect sizes

- **An ablation table is described** (`ABL = pd.DataFrame(rows, ...)`) that measures "macro AUC" and "mean silence" for configurations including "all rules on."
- **Feature flags measured:** `FEATURES` flags (`unwrap`, `directional_negation`, etc.) are "turned off one at a time and re-measured" to test their effect, but no numerical effect sizes are given in the extracted text.
- **AUC/Gap calculation:** At `M=0.85`, a label at chance forfeits roughly `0.029`.

### (4) Resources and reproduction requirements

- **Datasets/Weights:** The extraction code reads from `base = Path("/kaggle/input")`. It looks for a "label table" (a public dataset of model-read labels) as a CSV at runtime.
- **Reproduction:** The notebook is self-contained if run on Kaggle; it requires the competition's `train.csv`, `test.csv`, and the DICOM image directories. The rule extractor is "built here in-line."

### (5) Author's warnings or caveats

- **Overfit warning (not in this source, but structurally identical):** Not in this source. The source only states: "If this evidence-first walkthrough saves you time, an upvote helps other competitors find the reproducible result."
- **On the 58 labelled studies:** "Fifty-eight labelled studies cannot train an imaging model."
- **On the A5 heads:** "Unavailable acquisitions fall back to the base branch." (From a general comment, not specific to this version).
- **On RadImageNet weight:** The "20% rank vote" is described as the key change in V52.

### (6) Confidence in techniques as cause of score

- **Rank-mean blending**: SUPPORTED (by the score progression from V49 to V52 when the "Independent RadImageNet ResNet-50, 20% rank vote" was added).
- **Unwrap before splitting**: ASSERTED (author claims it fixes an error where a finding is missed).
- **Directional negation (scope)**: ASSERTED (author claims the "house style ... is systematic rather than occasional").
- **OA inheritance (ungraded cartilage)**: ASSERTED (author claims "three quarters of the corpus [would be] silent" without it).
- **Six-slot anatomical design**: ASSERTED.
- **CROP_MM = 130.0; CACHE_IMG = 336**: SUPPORTED (by the Nyquist argument for 1mm tear features).
- **Intensity normalisation per series**: ASSERTED (stated without measured effect vs. per-slice normalisation).
- **Per-finding sample weight from report confidence**: ASSERTED (author states "a loss that cannot express that trains every silence as a confident negative").
- **Metal descriptor features (no language ID)**: ASSERTED (author states routing first "fails badly").
- **Grade before thresholding**: ASSERTED (author states "binarising at its midpoint for validation only").
- **Abandoning report/metadata models for Synovitis, Lateral Meniscus, Lateral OA**: ASSERTED (author states "leaving those findings to the image models scored better," from a different source, but the same notebook; not in this source).