### Physiological reasoning: which findings suffer most under our current design?

Our pipeline treats each series as a **single mid‑volume triplet (3 adjacent slices → RGB channels)**, then pools that representation **across all available series** with per‑target mean/max.  
The frontier systematically removes limitations that harm specific knee pathologies:

- **Plane/sequence specificity** – many findings are only visible on **one or two optimal sequences** (e.g., a radial meniscal tear needs coronal PD FS). Feeding every series into one global pool dilutes the signal for findings that require a **dedicated reader** on the correct anatomical slot.
- **Off‑centre anatomy** – peripheral structures (meniscal roots, MCL, patellar attachments) are often **not in the middle slice** of a volume. A single triplet can completely miss a small tear.
- **Spatial resolution** – meniscal tears and full‑thickness cartilage defects can be **1 mm or less**; ResNet50 at 224 px (0.58 mm pitch) cannot reliably resolve them. CoAtNet at 384 px (0.34 mm) is adequate, but the ResNet branch dominates some members of our ensemble.
- **Pseudo‑label noise** – findings where the radiologist’s report diverges from the annotation threshold (e.g., “bone marrow oedema” not meeting size criteria, “joint fluid” vs. “effusion”) are learned from noisy targets, amplifying the input‑design gap.  

---

### Ranked findings by expected loss vs. the frontier

| Rank | Finding                         | Why our design loses most                                                                                                                                                                                                                                                                                         |
|------|---------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1    | **Lateral meniscus tear**       | Often **peripheral** (mid‑slice may miss root or posterior horn), demands **high resolution** (small width), and benefits from a **dedicated coronal+ sagittal slot**. Pseudo‑labels are moderately good, but the morphological subtlety dominates.                                                                |
| 2    | **Medial meniscus tear**        | Same vulnerabilities; slightly larger anatomy reduces loss fractionally.                                                                                                                                                                                                                                           |
| 3    | **Cartilage (medial compartment)** | Full‑thickness defect requires **exact slice through weight‑bearing zone** and **<0.5 mm resolution** to confirm no residual cartilage. Mid‑triplet often misses the steepest defect. Pseudo‑labels confound “partial” with “full” thickness.                                                                  |
| 4    | **Cartilage (lateral compartment)**| Identical to #3, with similar prevalence.                                                                                                                                                                                                                                                                          |
| 5    | **ACL tear**                     | Large structure, but **mid‑sagittal slice usually shows the ACL**. Loss is driven by **partial‑tear subtlety**, need for **oblique plane** in some variants, and the **ResNet resolution limitation**.                                                                                                             |
| 6    | **MCL / soft‑tissue injury**     | **Peripheral, multi‑slice extent**. A coronal mid‑slice may catch the MCL if the plane is central, but **off‑centre oedema** is easily missed. Pseudo‑labels are noisy for “sprain” vs. “tear”.                                                                                                                    |
| 7    | **PCL tear**                     | Central‑enough on sagittal, but **rare** (our small gold set has few positives) and often subtle.                                                                                                                                                                                                                  |
| 8    | **Bone marrow lesion (BME)**     | Large, high signal on all fat‑suppressed series — **easy for the triplet to see**. However, **pseudo‑label noise is severe** (report mentions “oedema” vs. annotation‑size threshold). Frontier gains come from refined report extractors and gold‑finetuning, not input geometry.                                |
| 9    | **Patellar tendon tear**         | Needs high resolution for **small intrasubstance tears**. Sagittal mid‑slice usually contains the tendon, but **fine detail** suffers at 224 px.                                                                                                                                                                   |
| 10   | **Quadriceps tendon tear**       | Same as patellar tendon, but **even rarer**.                                                                                                                                                                                                                                                                       |
| 11   | **Effusion**                     | Trivial to detect: **any fluid‑sensitive mid‑slice** shows it. Low‑resolution harmless. Loss is entirely from **pseudo‑label threshold mismatch** (small effusion vs. annotation size).                                                                                                                            |
| 12   | **Lateral patellar plica**       | Requires **axial plane** and is **very rare**. Our pool‑of‑all‑series design likely ignores the few sequences that show it; no dedicated slot means it is the hardest to learn from.

*(If the exact 12‑target list differs, re‑order the same principles: small, off‑centre, slot‑dependent targets first; large, central, or omnipresent targets last.)*

---

### Concrete input‑design changes to close the gap

#### 1. Adopt the 6‑slot anatomical backbone
Map every series to one of the six predefined anatomical views (e.g., SAG_FLUID_FS, COR_PD_FS) and **apply a separate head or attention per slot**. This forces the model to use the correct physiology, eliminating the dilution from irrelevant series.

#### 2. Widen the slice stack per series
Replace the mid‑only triplet with **5‑ or 7‑slice stacks** centred on the anatomically relevant midpoint (or learned centre). This reduces the “off‑slice” miss rate for peripheral tears and MCL lesions. For CoAtNet, treat them as multi‑channel input or as a small 2.5D volume via pooling across slices before the head.

#### 3. Upscale ResNet input to ≥336 px
Even with bilinear resizing, bringing the RadImageNet ResNet50 to **336 px (pitch 0.39 mm)** during fine‑tuning will give it a chance to resolve 1 mm structures. The TPU budget permits this; a single 336‑px run fits within one r16‑recipe slot.

#### 4. Target‑specific gold‑upweighting
For findings with **high pseudo‑label noise** (BME, effusion), apply **GOLD_UP = 5‑10** during training, or add a **second fine‑tuning stage on gold‑only**. A two‑stage pipeline (pseudo‑pretraining → gold‑finetuning) was a key frontier technique and directly addresses the ranking of #8 and #11.

#### 5. Pseudo‑label refinement
Blend the **tsuyu122** pseudo‑label source (high‑recall, rule‑based) and **drop series **where both sources disagree** or confidence is low**. This targets the label‑noise‑dominant findings without hurting the geometry‑driven ones.

#### 6. Multi‑slice ensembling
For each series, extract **three non‑overlapping 3‑slice views** (e.g., anterior‑third, middle, posterior‑third) and pool their predictions before the per‑series aggregation. This mimics r13b style and costs only a small GPU overhead during inference.

**Expected score uplift**: combining slots + wider stacks + 336‑px ResNet should push beyond 0.89 (public) by fixing the geometry‑dependent losses. Pseudo‑label refinement and gold‑finetuning then address the label‑noise gap, targeting 0.92+ before large‑scale ensembling.