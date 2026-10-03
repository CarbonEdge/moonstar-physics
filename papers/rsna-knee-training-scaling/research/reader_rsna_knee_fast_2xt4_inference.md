Here is the analysis of the source `rsna-knee-fast-2xt4-inference`.

### (1) Headline Claim and Score

- **Headline score:** The notebook "comes directly from [Mattia Angeli's Speedy Raptors v34](...), which scored **0.943 publicly**."
- **Version/Evidence:** The 0.943 is the *upstream* score of a specific version (v34) of a parent notebook. The author explicitly states: "That is the upstream score, not a guarantee for this version."
- **Internal version history notes the following weighted blends as scoring achievements:** v5 matched a "public 0.941 recipe", v7 adopts a "current public **0.942** recipe", and v9 adopts a "scored **0.943 v34**" from Mattia Angeli. The score is an external reference, not a measurement made in this notebook.

### (2) Concrete Techniques with Numbers

**Architecture / Model Stack (5-stage fusion)**

- **Stage 1:** DINO ensemble: "20 DINO slot-attention members."
- **Stage 2:** A5 attention-pooling: "five A5 attention-pooling folds."
- **Stage 3:** RadImageNet: "E10/E13/E11 heads."
- **Stage 4:** Raptor: "four Raptor views." Public CoAtNet branch.
- **Stage 5:** CoAtNet family: "residual top-3 + D4 SWA3 + Global96 top-3 + Repair-v1 top-3."

**Blending / Routing Weights**

- **Final blend (v7, 0.942 recipe):** "residual-gated CoAtNet and D4 DepthZone SWA3 ranks are mixed **0.50/0.50**; that private family remains **0.40** against public Raptor **0.60**, with no inner rerank. RadImageNet's main/second-pass weights change **0.50→0.55** and **0.15→0.20**."
- **Final blend (v9, 0.943 v34 recipe):** "residual/D4 weights **0.50/0.50→0.25/0.25**, plus Global96/Repair-v1 **0/0→0.25/0.25**." The family is blended as "**0.40 CoAt / 0.60 Raptor**."
- **v3 Raptor blend:** "Raptor MaxSpan forward/reverse weights from **0.55/0.15** to **0.60/0.10**; Native384 Dense/Native384 stayed **0.10/0.20**."
- **Fallback (v10/v11):** "the 0.40 CoAt weight" is shared equally among available arms; "if none survives, keep Raptor."
- **CoAt family reduction (v9):** Changed "from **rank-of-mean-ranks** to **rank-of-mean-probabilities**."

**Slice Counts and Resolution**

- **Raptor windows per arm:** v7 (0.942 recipe): `raptor_k_eval=94`.
- **D4 / Global96 allocation target:** `target = min(96, int(capacities.sum()))`. Proportion allocation: `(20, 12, 12, 8, 16, 8)` for 94 windows. `INFERRED96_WIDTHS = (27, 21, 18, 12, 18)`.
- **CoAtNet MRI reader (Stage 4/5):** 384 px adjacent-slice triplets (implicit from the upstream architecture referenced in the model stack description).

**Preprocessing / Decoding**

- **Header Cache:** "Raptor header cache is seeded from the DINOv2 ordering pass" (v9 changelog).
- **MaxSpan decoding:** "MaxSpan forward/reverse views share one decode and checkpoint load."

**Label Handling / Loss**

- Not specified in this inference-only notebook.

**Aggregation**

- **CoAtNet family:** v9 change: "CoAt family fusion changes from rank-of-mean-ranks to **rank-of-mean-probabilities**."
- **Fallback:** "Missing raw probabilities use v34's rank-mix fallback."

**TTA**

- Not explicitly mentioned.

### (3) Ablations / Measured Effect Sizes

- **Runtime improvement:** v8: "Parallel execution of residual-gated CoAtNet and D4 DepthZone SWA3 — 155s → 69s with zero change to predictions."

### (4) Resources Required for Reproduction

- **Attached datasets:** The notebook relies on public datasets from other authors (Pilkwang Kim, Sofia Anjenje, Antoine G., Marwan Mahmoud, etc.) as part of the model stack. Specific datasets mentioned include `rsna-knee-coatnet-global96-top3` and `coatnet_pairfilm_manifest.json`.
- **Hardware:** **2× T4 GPUs**, 29 GB machine. The harness explicitly checks for 2 T4s (v3 changelog, startup checks). `TIME_BUDGET = 8 hours` (likely a cap, actual runtime ~4 minutes on T4×2 per v7 note).
- **Software:** `cv2==4.12.0`, `timm==1.0.22`.
- **Checkpoints:** Requires specific checkpoints: `coatnet_d4_parent_rank8_swa2.pt`, and checkpoints from the four CoAtNet members (residual top-3, D4 SWA3, Global96 top-3, Repair-v1 top-3).
- **Memory Limits:** `CACHE_BUDGET_MAX_GB = 24.0`; `CACHE_FRACTION = 0.45`.

### (5) Author's Warnings/Caveats

- **Upstream score:** "That is the upstream score, not a guarantee for this version." (Explicit disclaimer that the 0.943 score is not from this notebook's run).
- **Overfitting warning (in a different source, not this one):** The author warns that the notebook is "likely overfit to the public leaderboard" and that forking with minor tweaks is "not meaningful model development." (This is from `bend-the-knee-to-dinov3-ensembled`, but it is the same user, so the caveat likely applies to this notebook family).
- **Fallback handling:** "Reader failures and per-study fallbacks are logged, and the scored upstream blend handles missing readers or probabilities without aborting."

### (6) Confidence in Techniques as Score Causes

- **DINO + A5 + RadImageNet + Raptor + CoAtNet ensemble:** **SUPPORTED** (by the upstream score progression on the public leaderboard). The progression from 0.937 → 0.94 → 0.941 → 0.942 → 0.943 is documented as a series of incremental changes to this family of models (adding Raptor, adding CoAt, increasing weights).
- **Raptor `k_eval=94`:** **SUPPORTED** (by the "Why it helps" comment: "samples each stack more densely. This is an accuracy change that needed no new model").
- **Re-weighted blends (A5, RadImageNet):** **SUPPORTED** (by the "Why it helps" comment: "both branches contribute more to the final blend"). The v7 changelog shows they move from 0.50→0.55 and 0.15→0.20.
- **CoAt family expansion to 4 members:** **SUPPORTED** (by the "Key idea" in the narrative: "the frontier now comes from combining **more, genuinely different CoAt readers** and **reducing them in probability space** rather than rank space").
- **CoAt family reduction change (rank-of-mean-probabilities):** **ASSERTED** (v9 changelog states this change was made, but no ablation is given to compare rank-of-mean-ranks vs. rank-of-mean-probabilities).
- **Parallel execution of CoAt readers:** **SUPPORTED** (by the measured 155s → 69s speedup, and explicitly stated as "with zero change to predictions"). This is a latency improvement, not a score improvement.
- **Shared DINO prefix / Raptor header cache:** **ASSERTED** (for speed). No ablation is given.
- **Capacity-aware slice allocation (/`_dense_allocate`)** : **ASSERTED** (for handling variable-length series gracefully). No score impact is quoted.