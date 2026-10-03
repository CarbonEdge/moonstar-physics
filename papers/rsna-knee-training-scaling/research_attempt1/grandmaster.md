## Path Evaluation & Expected Scores

**Honest public-score ranges (given constraints)**  
- **(a) Attach/ensemble public weights (0.94 frontier):** 0.930–0.945.  
  * If a well-documented top enssemble (e.g., the 5‑stage stack in `rsna‑knee‑fast‑2xt4‑inference`) runs correctly on GPU → >0.940. Minor preprocessing mismatches → 0.930, still a huge jump over 0.865.  
- **(b) Retract our own members with slot/2.5D/dense-slice upgrades:** 0.880–0.905.  
  * r16 CV 0.878 maps to ~0.85‑0.87 public (historical gap +0.02‑0.03). Improving CoAtNet (fuller training, slot‑specific heads, 3→5 slice input) might lift +0.03‑0.05 → public 0.89‑0.91. A 4‑model ensemble (2 ResNet + 2 CoAtNet variants) could reach 0.90‑0.91. Not enough to close the 0.078 gap alone.  
- **(c) Hybrid rank‑blending:** 0.942–0.947.  
  * The public ensemble already at 0.943; adding 1‑3 carefully chosen (but genomically different) own members can yield +0..002‑0.005 if diversity is real and blending does not overfit the 58 gold studies. Maximum plausible gain ~0.005.

---

## Why (a) is the Bedrock – Rapid Validation under Budget

We have only 30 h GPU and limited submissions. The fastest path to the frontier is to **run a known top‑performing public ensemble** end‑to‑end in our inference notebook, confirm it scores ≥0.94, and then **safely layer modest diversity on top**.

**First experiement (validates (a) & fits time budget):**  
- Take the publishhed 5‑stage 0.943 notebook (`rsna‑knee‑fast‑2xt4‑inference`).  
- Adapt it to our environment (same 130 mm crop, 6‑slot formatting, series selection).  
- Retrieve the required weights (CoAtNet, DINO, RadImageNet series heads, Raptor views) – likely available as public datasets.  
- Run inference on GPU (predicted ~2‑3 h for the full inference on test).  
- Submit once → public score.  
- *Expected outcome:* 0.940–0.943. This single run confirms that the public weights work on our GPU infrastructure and that our preprocessing is consistent. Failure modes: missing weights, version conflicts, time‑out due to large DINO ViT‑L → use ViT‑S fallback; we can first test on a small subset. Within 3 h GPU we can validate.

---

## Hybrid‑Blending Design that Avoids Overfitting to 58 Gold Studies

### Core problem
Any weighting coefficients learned on 58 studies (or 3×19 OOF) will overfit heavily. The local CV noise is ~0.09 per per‑fold AUC (Hanley‑McNeil SE for n = 19 is 0.1‑0.15), so even OOF‑based stacking will not generalize.

### Solution: Pseudo‑Validation Set Blending
- **Hold out 500–1,000 psuedo‑labelled studies** from the Llama‑based pseudo pool **before any training**. These studies come from unique patients (not overlapping with the 58 gold) and provide weak‑label targets.  
- Train all our own members (e.g., an improved CoAtNet with slot+5‑slice input, a RadImageNet ResNet50‑256 withd 6‑slot) on the remaining pool + all gold.  
- Run inference for **every member (public + own)** on the held‑out pseudo‑validation set.  
- Compute the psuedo‑validation multi‑label**bce Score** per‑model. This large‑sample (500 × 12 findings) estimate of model quality is far more stable than 58 gold.  
- Optimise blending weights (a single softmax layer per finding) on the pseudo‑validation scores using a **constrained regression** (naïve stacking with 5‑fold cross‑validation over the 500 studies to avoid overfitting to weak labels). The constraint: **rank‑based weights** – assign weights proportional to the model’s historical pubic LB rank (e.g., 0.943 → weight 1.5, 0.940 → 1.0, our 0.89 model → 0.5) and only small perturbations allowed : \Delta w \in [-0.1, 0.1] with L1 regularisation. This hierarchical prior ties tying performance