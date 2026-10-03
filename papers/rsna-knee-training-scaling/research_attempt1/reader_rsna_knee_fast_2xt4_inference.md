## Extraction from `rsna-knee-fast-2xt4-inference`

### (1) Headline claim and score  
- **Headline:** "This inference-only notebook is derived from … and the current model recipe comes directly from **Mattia Angeli's Speedy Raptors v34**, which scored **0.943 publicly**."  
- **Version:** v11 (final changelog entry). The notebook itself does not report its own score; the cited score is the upstream 0.943.  
- **Evidence:** "0.943 v34" is referenced as the anchor; v7 adopted "the current public 0.942 recipe". No ablation or cross‑validation within this notebook.

### (2) Concrete techniques with numbers  

#### Architecture & ensemble  
- **5‑stage model stack:**  
  1. 20 DINO slot‑attention members (transformer base)  
  2. 5 A5 attention‑pooling folds — **45% update** to the base  
  3. RadImageNet **E10/E13/E11** heads  
  4. Four **Raptor** views (CoAtNet branch)  
  5. **CoAt family = 4 readers**: residual‑gated CoAtNet (top‑3), D4 DepthZone SWA3, Global96 (top‑3), Repair‑v1 (top‑3)  

- **CoAt family fusion:** **rank‑of‑mean‑probabilities** (changed from rank‑of‑mean‑ranks in v9).  
  - Each CoAt reader contributes **25%** probability average; then rank.  
  - Outer routing: **CoAt family 0.40 / Raptor 0.60** (unchanged from v7).  

- **RadImageNet blend:**  
  - Main alpha **0.55** (was 0.50 in v6, changed to 0.55 in v7).  
  - Second E13 pass alpha **0.20** (was 0.15 in v6).  

- **Raptor inner weights** (from v3 changelog):  
  - MaxSpan forward/reverse = **0.60 / 0.10**  
  - Native384 Dense / Native384 = **0.10 / 0.20**  

- **Raptor windows (`raptor_k_eval`):** **94** (adopted from 0.942 recipe).  

- **Dense depth allocation proportions:** (20, 12, 12, 8, 16, 8) for 94 windows.  
- **Global96 reference widths:** INFERRED96_WIDTHS = (27, 21, 18, 12, 18).  

#### Input design & preprocessing  
- **Crop physical extent:** CROP_MM = **130.0**  
- **Cache image size:** CACHE_IMG = **336**  
- **Slice grouping:** GROUP = **3** (stacked as 3 channels), N_GROUP_MAX = **1**  
- **Slice sampling band:** SLICE_BAND = (0.2, 0.8)  
- **Lat min offset:** LAT_MIN_OFFSET_MM = **20.0**  
- **Augmentation (training):**  
  - AUG_ROT_DEG = **8.0**  
  - AUG_SCALE = **0.08**  
  - AUG_SHIFT = **0.05**  
  - AUG_INTENSITY = **0.10**  

#### Decoding & ordering  
- **DICOM ordering rules:** RULES_NATIVE = {order: 'normal', lat: 'centre', slot_fallback: False, decode_fill: 'nearest'}  
- **Legacy rules:** RULES_LEGACY = {order: 'dominant_axis', lat: 'corner_x', slot_fallback: True, decode_fill: 'zero'}  
- **Order threads:** ORDER_THREADS = **32**  
- **Pixel threads:** PIX_THREADS = **12**  
- **Header threads:** HDR_THREADS = **16**  

#### Training hyperparameters (from code lines, though notebook is inference‑only)  
- EPOCHS = **10**  
- BATCH_STUDIES = **8**  
- LR_HEAD = **0.001**  
- LR_BACKBONE = **8e-06**  
-