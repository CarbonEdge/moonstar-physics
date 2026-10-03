# Research Synthesis

## (1) Lineage Graph (No Double Counting)

All solutions descend from a common **baseline pipeline** defined in `rsna-knee-baseline-v1`. That notebook formalised:
- anatomical slot mapping (6 series types),
- DICOM geometric slice ordering,
- fixed 130 mm crop → 336 px, 3‑slice channel stacking,
- percentile intensity normalisation,
- a multilingual rule‑based report reader with graded targets, and
- rank‑averaging as the primary fusion method.

**Downstream lineage:**
- `rsna-knee-read-the-report-then-the-knee` extends the baseline by adding a specific imaging model (RadImageNet ResNet‑50) and refined report‑reader flags, producing **0.906** (V52).
- `bend-the-knee-to-the-dinosaurs` adds a CoAtNet reader (from a public dataset) to an existing ensemble that likely already contained the RadImageNet/DINO family. It is a precursor contribution later absorbed into the final Speedy Raptors ensemble.
- `bend-the-knee-to-dinov3-ensembled` adds a DINOv3 ViT‑S/16 to a rank‑mean of twenty DINOv2 models; this, too, is an ancestor of the full ensemble.
- `rsna-knee-fast-2xt4-inference` packages the **final Speedy Raptors v34** recipe, assembling all prior members: 20 DINO slot‑attention heads, 5‑fold A5 attention‑pooling, RadImageNet heads, four Raptor views, and four CoAtNet readers. This version scores **0.943**.
- `rsna-versia-5` documents the step‑wise assembly that matches the above: scores rise **0.937 → 0.940 → 0.941 → 0.942 → 0.943** as arms are added.

*Inference: the 0.943 ensemble of `fast-2xt4-inference` already subsumes the CoAtNet and DINOv3 contributions; therefore those are not independent “new” techniques but components of the final ensemble.*

---

## (2) Techniques That Appear Across Independent Sources vs. Only Once

### Techniques appearing in **multiple independent sources**  
(likely essential, not idiosyncratic):
- **Slot‑based series selection** – baseline, read‑the‑report, and is implicitly required by all ensemble members (they all read “slots”).
- **Geometric slice ordering** (using `ImageOrientationPatient`/`ImagePositionPatient`) – baseline, read‑the‑report.
- **130 mm crop, 336 px resize, 3‑slice stacking** – baseline, read‑the‑report.
- **Rank averaging** (instead of probability averaging) – baseline, read‑the‑report, and is the stated aggregation method in the ensemble (fast‑2xt4‑inference uses “rank of mean of probabilities” for CoAtNet reduction).
- **Multilingual rule‑based report reader** (with graded scores & confidence) – baseline, read‑the‑report; the pseudo‑labels it produced were used by all later imaging models.
- **RadImageNet pretraining** – used in read‑the‑report and in the RadImageNet arm of the final ensemble.
- **CoAtNet architecture** – appears in `dinosaurs` and in the four CoAtNet readers of the final ensemble.
- **DINO‑family models** – DINOv2 in the 20‑DINO pool, DINOv3 added in `dinov3-ensembled` and presumably kept in the final recipe.

### Techniques appearing **only once** (may be incremental or specific to the final score):
- **Raptor views** (MaxSpan forward/reverse, Native384 Dense, Native384) – only in `fast-2xt4-inference`.
- **A5 attention‑pooling folds** (45% update to the base) – only in `fast-2xt4-inference`.
- **DINOv3 ViT‑S/16** – only in `dinov3-ensembled` (but note it is part of the 0.943 ensemble; it’s a *model addition*, not a generic technique).
- **LM‑read label table** (as supplement to lexicon) – only mentioned in `baseline-v1` and `read-the-report`; not described as part of the final ensemble notebook.

---

## (3) Ablations: Measured (with numbers) vs. Asserted

### Techniques with **measured ablations** (numeric effect sizes):
- **Read‑the‑report notebook (V52)**  
  - Five‑fold EfficientNet‑B3 alone: **