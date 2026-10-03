## Extraction from `rsna-knee-baseline-v1`

### 1. Headline claim & reported score
- **No score reported.** The notebook describes a baseline methodology but does not state a public or private leaderboard score. The metric is defined as the unweighted mean of 12 per-label ROC AUCs, but no achieved value is given.

### 2. Concrete techniques (with exact numbers)

**Architecture**
- **Backbone:** Transformer encoder (not named); only the last **6** blocks are trainable (`UNFREEZE_LAST = 6`).
- **Input design:** 6 predefined anatomical *slots* – `SAG_FLUID_FS`, `COR_FLUID_FS`, `AX_FLUID_FS`, `SAG_FLUID_NOFS`, `COR_T1`, `SAG_T1` (defined in `SLOTS_RECOVERED`/`SLOTS_PUBLIC`).
- **Slice stack:** **3** adjacent slices stacked as the three channels of the encoder input (`GROUP = 3`). Only **1** group per slot (`N_GROUP_MAX = 1`).
- **Resolution:** Crop to constant physical extent **130.0 mm** (`CROP_MM = 130.0`), then resize to **336 px** (`CACHE_IMG = 336`). Effective pixel pitch = 130/336 = 0.387 mm/px. A second run to 224 px is also planned (`RUNS = [{'name': 'r224', 'img': 224}, {'name': 'r336', 'img': 336}]`).

**Preprocessing**
- **Intensity normalisation:** Per series, using the **1st and 99th percentile** over the *sampled stack* (not per slice), then clipped and rescaled. (Code not shown, described in narrative.)
- **Label handling:**
  - Two sources: a multilingual rule-based extractor (lexicon with assertion/negation/hedge, grading, per-finding confidence) and a mounted table from a language model.
  - Confidence becomes a per-finding sample weight.
  - Targets are graded (not binary); binarised at their **midpoint** for validation only.
- **Loss:** Not specified.
- **Aggregation:** Not specified (sections 6–8 referenced but not included in this notebook).
- **Blending/routing weights:** Not