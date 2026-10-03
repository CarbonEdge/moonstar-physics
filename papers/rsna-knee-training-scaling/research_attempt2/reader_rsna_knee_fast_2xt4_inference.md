**Source:** `rsna-knee-fast-2xt4-inference` (v11)  

### (1) Headline claim and score  
- **Claim:** Implements Mattia Angeli’s Speedy Raptors v34 recipe, which **scored 0.943 publicly** (upstream score, not a guarantee for this version).  
- **Evidence:** Changelog v9 – “adopts Mattia Angeli’s scored **0.943 v34**”.  

### (2) Concrete techniques with numbers  

| Component | Details (as stated) |
|-----------|---------------------|
| **Architecture stages** | 1. 20 DINO slot‑attention members (shared frozen 6‑block prefix)<br>2. 5‑fold A5 attention‑pooling folds (45% update to base)<br>3. RadImageNet E10/E13/E11 heads<br>4. Four Raptor views (MaxSpan forward/reverse, Native384 Dense/Native384)<br>5. Four CoAtNet readers: residual‑gated top‑3, D4 SWA3, Global96 top‑3, Repair‑v1 top‑3 |
| **Input design** | MRI series mapped to anatomical slots; no explicit resolution/input size in text |
| **Slice counts** | D4: 94 windows per stack, allocation quotas `(20,12,12,8,16,8)`<br>Global96: 96 positions, inferred widths `(27,21,18,12,18)` |
| **Preprocessing** | Shared frozen DINO prefix; CPU preparation overlapped with GPU; DINO header scan seeds Raptor ordering cache; capacity‑aware unique windows; bounded pixel cache |
| **Label handling** | Not described |
| **Loss** | Not described |
| **Aggregation / blend weights** | • RadImageNet: main alpha **0.55**, second E13 pass alpha **0.20** (v7)<br>• Raptor inner (v3): forward **0.60**, reverse **0.10**, Native384 Dense **0.10**, Native384 **0.20** (superseded by later blends?)<br>• Outer: CoAt family total **0.40**, Raptor **0.60** (v7, v9)<br>• CoAt inner: each of 4 members **0.25** (v9)<br>• CoAt reduction: **rank of mean of probabilities** (v9)<br>• A5 fold influence: “45% update to the base” (model‑stack table) |
| **TTA** | Not mentioned |
| **Runtime** | Full run ~4 minutes on 2×T4 (v7 changelog) |

### (3) Ablation / measured effect  
- **None reported.** Version history lists weight changes but no effect sizes or ablations.  

### (4) Resources & reproduction requirements  
- **Attached datasets/weights:**  
  - `coatnet_pairfilm_manifest.json`, `coatnet_resgated_ep10_top3_inference.py` (part of artifact)  
  - All checkpoints from upstream (pinned by SHA256)  
- **Hardware:** Exactly 2× GPU (must be T4; fails otherwise)  
- **Software:** `cv2==4.12.0`, `timm==1.0.22`  
- **Time budget:** 8 h (but actual inference ~4 min)  
- **Data:** Mounted competition/test DICOM directories; no report column needed  

### (5) Author’s warnings / caveats  
- “That is the upstream score, not a guarantee for this version.”  
- Reader fallback: if a CoAt arm fails, remaining arms share the 0.40 weight equally; if none survive, keep Raptor only.  
- Missing raw probabilities use v34’s rank‑mix fallback.  
- Large cohorts (>48 studies) run CoAt readers sequentially to limit memory.  
- All outputs are validated for finite values, correct schema, and checkpoint integrity before submission.  

### (6) Confidence in each technique’s score impact  

| Technique | Confidence | Reason |
|-----------|------------|--------|
| Architecture (20 DINO, A5, RadImageNet, Raptor, 4 CoAt readers) | ASSERTED | Part of the scored upstream recipe; no ablation within this notebook. |
| Blend weights (alpha values, outer ratio) | ASSERTED | Tuned upstream; changes between versions are recorded but not ablated here. |
| Slice‑count allocation (94, 96) | ASSERTED | From upstream D4/Global96 designs. |
| Preprocessing / caching optimisations | UNCLEAR | Speed measures, not demonstrated to improve score. |
| Rank‑of‑mean‑probabilities fusion | ASSERTED | Upstream v34 change; no ablation. |
| TTA | — | Not present. |