## 1. Honest expected scores and core failure modes

### (a) Attach and ensemble public trained weights  
**Expected public score:** **0.940–0.943** – i.e. the top‑of‑the‑leaderboard public ensembles (Speedy Raptors v34, jiweiliu’s 0.943, etc.) are known to score between 0.937 and 0.943, and their inference notebooks have been shared on Kaggle datasets.  
**Failure modes:**  
- The public weights may be partitioned across multiple datasets, some of which exceed the inference notebook’s internet‑download time or storage limit.  
- Pre‑processing mismatches (e.g. `pydicom` versions, pixel‑array rescaling) can silently break predictions.  
- The top ensemble (`rsna-knee-fast-2xt4-inference`) uses 2 × T4 GPU; while it fits within 30 h, the notebook must be debugged to run in our environment.  
- If only partial public weights are available (e.g. a single CoAtNet at 0.91), the gain will be much smaller.  

### (b) Retrain own members with slot/2.5D/dense‑slice upgrades  
**Expected public score:** **0.895–0.915** (single models 0.890–0.905, ensemble ~0.91).  
- Our current best public is 0.865. Adding 2.5D (9‑slice dense stack) and slot‑based series selection can lift a strong backbone (CoAtNet‑384) to ~0.90–0.91 on this task, based on known competition dynamics.  
- With only 4 TPU runs (16 h), we can train 2–3 diverse members (different views, seeds, pooling). Their ensemble might reach ~0.91–0.915.  
**Failure modes:**  
- The 58‑gold local CV is extremely noisy (SE ~0.05–0.10 per finding), so we cannot reliably steer architecture choices; we risk training a model that looks good locally but drops on public.  
- Slot mapping mistakes could degrade performance; it requires careful DICOM‑header parsing that may not be robust.  
- Upgraded models may still be under‑trained (our CoAtNet currently sees only ~2 effective epochs).  

### (c) Hybrid rank‑blending our own diverse members with public ones  
**Expected public score:** **0.943–0.945** (if public ensemble is 0.943, a diverse ensemble can add 0.001–0.002; occasionally there is a 0.003–0.005 jump from de‑correlated models).  
**Failure modes:**  
- Our own models may be so correlated with the public ensemble that the blend adds no value, or even dilutes the score (unlikely because our training recipe, pseudo‑labels, and backbones differ significantly).  
- Over‑optimising the blending weights on the 58 gold studies would produce a blend that generalises poorly to the hidden test set.  

---

## 2. What our own assets add as diversity and why they can lift the frontier

Our pipeline differs from the public ensembles in several fundamental ways, creating **orthogonal signal**:

| Aspect | Public top ensemble | Our current / planned |
|-------|-------------------|----------------------|
| **Pseudo‑labels** | Report‑reader rules (multilingual) + additional LLM labels | LLM pseudo‑labels from ~4,349 studies, not shared with public ensemble |
| **Backbones** | DINOv2‑ViT, DINOv3‑ViT‑S, Raptor, CoAtNet readers | RadImageNet ResNet‑50, CoAtNet‑rmlp‑384 fine‑tuned from scratch on our pseudo‑data |
| **Pre‑training** | Self‑supervised on natural images / in‑house data | RadImageNet (medical imaging specific), ImageNet‑21k for CoAtNet |
| **Input resolution & slice stack** | Varied (336 px, 3‑slice) | 384 px native for CoAtNet, mid±1 slice RGB (ResNet) |
| **Fusion** | Rich slot‑attention, A5 attention pooling, rank averaging | Simple max/mean pooling + weighted average |

This diversity means **rank‑blending** (averaging the rank‑transformed probabilities) almost always yields a small but reliable gain when the base ensemble is already near saturation. Even 0.001‑0.002 improvement is valuable at the top.

---

## 3. Blending design that avoids overfitting to the 58 gold studies

**Problem:** With only 58 gold studies, any weight search (grid, Bayesian) on local CV will drastically overfit the gold set, leading to a blend that performs *worse* on the public/hidden test than a simple average.

**Safe design – “Rank‑mean with LB‑guided weight selection”:**

1. **Always rank‑transform** each member’s raw probabilities (per finding, over the test set) before averaging. This cancels out scale differences and reduces sensitivity to outlier models.  
2. **Start with equal weight blending** (e.g., 0.5 × public_ensemble_rank + 0.5 × our_ensemble_rank). Submit this as a baseline hybrid.  
3. **If the LB improves**, we can try a second submission with weights shifted by ±0.1 (e.g., 0.6/0.4 and 0.4/0.6). Choose the best combination *solely from the public LB*, not from local gold CV.  
4. **Never search weights on the gold set** – use only on‑leaderboard feedback. With 2–3 submissions per day, we can probe a few blends after the public ensemble alone is established.  

**Why this works:**  
- The public LB is a noisy but unbiased signal (≈1000 studies). Tuning 1‑2 blending parameters on it has negligible overfitting risk compared to tuning on 58 gold studies.  
- The rank‑mean transform makes the blend insensitive to the exact weight choice, so a few coarse steps suffice.

---

## 4. The smallest‑cost experiment that validates the direction

**Step‑0 experiment (cost: ~2 h GPU, 0 TPU):**  
- Locate the most recent public inference dataset (e.g. `rsna-knee-fast-2xt4-inference` or the dataset linked by jiweiliu’s 0.943 submission).  
- Download a minimal subset (e.g. 100 studies) and run the public inference code in a GPU notebook **exactly as‑is**, verifying it produces non‑trivial predictions and runs under the runtime limit.  
- *Do not submit yet* – first confirm technical feasibility and rough inference time for the full test set.  

**Success criterion:** The public model produces predictions with reasonable probabilities (not all 0.5) and all components (DINO slots, CoAtNet readers, etc.) load without errors.  

**If this works**, we then submit the untouched public ensemble to the public LB. Expected score **0.940–0.943** – instantly placing us among the leaders.  

**If public weights are unavailable or fail**, we fall back to option (b) but with a tight focus: a single, maximal CoAtNet‑384 run using slot‑selection, 9‑slice dense stacking, and 8 full epochs (cost: ~5 h TPU). This is the safest single‑model upgrade that could reach ~0.90+.

---

## 5. Recommended overall plan (how to allocate TPU/GPU hours this week)

**Phase 1 – Immediate (hours 0–6):**  
- GPU: Execute the validation experiment above; prepare the full inference notebook.  
- GPU: Run inference with the best **public ensemble only** → submit. Expected LB: **0.942**.  

**Phase 2 – While waiting for LB feedback (hours 6–18):**  
- TPU: Train **two upgraded own members** using remaining TPU budget (8 h left after one full run).  
  - Run 1: CoAtNet‑384 with **9‑slice dense stack** (slot‑based selection), full BIG_FRAC=1.0, 8 epochs, lr 2e‑4 cosine.  
  - Run 2: RadImageNet ResNet‑50 with **5‑view 2.5D** (slot‑based) and longer training (10 epochs).  
-