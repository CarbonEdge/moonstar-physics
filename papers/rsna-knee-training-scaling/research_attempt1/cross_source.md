**Research Synthesis: RSNA Knee MRI Competition – From ~0.87 Single-Model to ~0.94 Heterogeneous Ensemble**

This synthesis integrates the per‑source extractions to map the evolution of solutions, identify key techniques, assess evidence quality, and rank the factors most likely responsible for the ~0.07 AUC gap.

---

### 1) Lineage Graph

All solutions descend from a common **baseline** (`rsna-knee-baseline-v1`).  
The lineage is best understood as a chain of forks and augmentations:

- **`rsna-knee-baseline-v1`** – Initial training recipe: DINOv2‑style transformer, 6‑slot anatomy, 130 mm crop, 336 px images, 3‑slice input, rule‑based report extractor. No public score reported.
- **`rsna-knee-read-the-report-then-the-knee`** – Fork that adds an **independent RadImageNet ResNet‑50 at 20% rank vote** and enhances the report extractor with `FEATURES` flags. Reached **0.906** public AUC (V52).
- **`bend-the-knee-to-dinov3-ensembled`** – Further fork: adds a **DINOv3 ViT‑S/16**, increases RadImageNet rank vote to **0.50 (first pass) and 0.15 (second pass)**, and introduces adaptive per‑finding second‑pass weights. No score claimed, but author warns of overfit to public LB.
- **`bend-the-knee-to-the-dinosaurs`** – Adds a **CoAtNet RMLP‑2** reader (384 px triplets, gated spatial head). Described as “inference‑only”; references Mattia Angeli’s **0.943 v34** as the upstream recipe. The notebook itself does not report a score.
- **`rsna-knee-fast-2xt4-inference`** – Documents the **full 5‑stage stack** that achieves 0.943: 20 DINO members, 5 A5 attention‑pooling folds (45% update), RadImageNet E10/E13/E11 heads, 4 Raptor views, and a CoAt family of 4 readers. Contains the hyper‑parameters of the final ensemble.
- **`rsna-versia-5`** – Reproduces five public solutions that form the final **score ladder: 0.937 → 0.94 → 0.941 → 0.942 → 0.943**, each corresponding to a specific change in the Raptor/CoAtNet ensemble.

Thus the overall progression is:  
`baseline` ⟶ `report+RadImageNet 20% (0.906)` ⟶ `DINOv3 + heavier RadImageNet (no score)` ⟶ `CoAtNet added (no score)` ⟶ `5‑stage ensemble (0.937–0.943)`.

---

### 2) Techniques – Cross‑Source Occurrence

Techniques appearing **independently in multiple sources** (i.e., not just a single fork):

- **6‑slot anatomical input** (SAG_FLUID_FS, COR_FLUID_FS, etc.) and **130 mm physical crop → 336 px**.
- **3 adjacent slices stacked as 3 channels**; intensity normalisation per series using 1st/99th percentile.
- **Multilingual rule‑based report extract