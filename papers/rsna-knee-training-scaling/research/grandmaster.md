# Plan: From 0.865 to Frontier Under Constraints

## I. Honest Score Expectations

### Path (a): Attach and Ensemble Public Weights
**What we'd do:** Download DINOv2 slot-attention models (Pilkwang's 20-models at 0.891 base), CoAtNet raptor family (prvsiyan/renta/Mattia/maverick/Jiwei lineage, 0.937→0.943), RadImageNet ResNet-50 heads (verified +0.012 at 20% early), and DINOv3 ViT-S/16 (held-out selected). Blend via rank-mean with our r19 (r16-repro) member at 0.10-0.15 weight.

**Expected public score range:** **0.915–0.925**

**Why not higher:** The public 0.943 is an ensemble of 4+ CoAtNet variants + 20 DINOv2 + RadImageNet heads, each tuned to the public LB. Our single r19 member (one CoAtNet, one ResNet50, 58-gold tuned) cannot carry weight above ~0.15 without dragging the mean down. At 0.10 weight, our contribution adds ~0.001-0.003 if we're lucky. The gap to frontier closes mostly by riding public weights, not by our model quality.

**Failure modes:**
1. **Weights unavailable or incompatible.** Pilkwang's 20 DINOv2 models may not be downloadable; CoAtNet checkpoints may be private. You get partial ensemble → 0.900–0.910.
2. **Inference time blowup.** 20 DINOv2 + 4 CoAtNet + heads → potentially 30+ model passes. GPU 30h may not suffice for full test set. Need to profile one study latency first.
3. **Overfit to public LB.** The dinov3-ensembled author explicitly warns that sub-resolution blend tweaks are noise overfitting. A 0.002-0.003 LB gain may reverse on private. Private test is 3x public size → gap could be -0.01 to -0.02.
4. **No learning.** This path teaches us nothing about the task. Rank depends entirely on others' work. If private test distribution differs (different scanners, populations), our ensemble has no robustness beyond what public weights captured.

### Path (b): Retrain Our Own Members with Upgrades
**What we'd do:** With 4 TPU runs (16h budget):
- Run 1: CoAtNet@384, 10 epochs, BIG_FRAC=1.0, GOLD_UP=3, 5 views (mid ± 2 adjacent slices as 3-channel triplets per view, per Mattia's architecture)
- Run 2: CoAtNet@384, different seed/fold split, same upgrades
- Run 3: RadImageNet ResNet50@256 (pitch=0.508mm, meets 0.5mm Nyquist for 1mm tears), 10 epochs, 5 views, GOLD_UP=3
- Run 4: EfficientNet-B3@300 (pitch=0.433mm), 10 epochs, 5 views, GOLD_UP=3 — new architecture family for diversity

Ensemble via OOF-chosen weights on 58 gold.

**Expected public score range:** **0.885–0.905**

**Why:** The CoAtNet architecture is the single largest post-0.906 contributor per the research synthesis. Full training (10 epochs × BIG_FRAC=1.0 = 10 effective epochs vs our current 2 effective epochs) should recover most of the 0.04 CV gain we saw from CoAtNet vs frozen features. GOLD_UP=3 (proven in r18) ensures the 58 gold aren't drowned by 22.8k pseudo. 5 views capture more contextual slices. The EfficientNet-B3 adds a new architecture family — the dominant mechanism for ensemble gain per the lineage analysis.

**The gap from 0.905 to 0.943 is ~0.038. This is almost entirely the public ensemble's diversity (20+ models across 3+ architecture families). We cannot close this with 4 models.**

**Failure modes:**
1. **CV noise misleads.** With 19-val-studies per fold, even a 0.02 CV gain may be noise. We could spend all 4 runs and get 0.875 public.
2. **CoAtNet overfits gold.** 10 epochs × 58 gold studies studied 10 times each. If pseudo labels are noisy, the model may memorize gold patterns that don't generalize.
3. **5-view input breaks geometry.** Middle-slice selection logic may fail on edge cases (series with <5 slices).
4. **TPU OOM.** 5 views × CoAtNet@384 × batch 16 may not fit. Need to reduce batch to 8 → longer training → may not finish in 3.5h.

### Path (c): Hybrid Rank-Blend — Our Diverse Members + Public Weights
**What we'd do:**
1. Train 2 CoAtNet variants (runs 1-2 from path b, different seeds) → our best CoAtNet family
2. Train 1 RadImageNet ResNet50@256 (run 3 from path b) → our RadImageNet family
3. Train 1 DINOv2 slot-attention model at 336px (from scratch, using the rsna-knee-baseline-v1 recipe adapted to our data) → new architecture family we own
4. Download: Pilkwang's 20 DINOv2 (if available), Mattia's CoAtNet (if available), RadImageNet heads (if available)
5. Rank-mean blend with our-own weight = 0.25-0.35, public weight = 0.65-0.75

**Expected public score range:** **0.920–0.932**

**Why:** Our models contribute more meaningfully (0.25-0.35 weight vs 0.10 in path a) because we have 4 diverse members across 3 architectures (CoAtNet, ResNet, DINOv2). Our DINOv2 trained on our data should be more complementary to our CoAtNet than public DINOv2 trained on unknown data. The public ensemble provides the bulk of the score; our members add genuine diversity rather than just riding along.

**Failure modes:**
1. **Our DINOv2 training fails.** DINOv2 slot-attention from scratch requires careful implementation. If buggy → worse than no member.
2. **Blend weight overfitting.** Choosing our-weight=0.30 on 58 gold is 1 degree of freedom over 58 samples. Easy to overfit.
3. **Same as path (a) failures 1-3.**

---

## II. Blending Design That Avoids Overfitting to 58 Gold

**Rule:** Any parameter learned on 58 gold studies with more degrees of freedom than sqrt(58) ≈ 8 risks overfitting. We have ~12 findings × ensemble weights = many DOF.

**Design:**
1. **Single blend weight per model family, not per finding.** 4 model families (our CoAtNet family, our ResNet, our DINOv2, public ensemble) → 3 degrees of freedom (weights sum to 1) → safe.
2. **Use public LB as the blend weight selector, not 58-gold CV.** Submit 3-4 candidate blends (different our-weight values: 0.20, 0.25, 0.30, 0.35). Pick the highest public score. This uses the 58-gold only for within-family member weighting (which we do anyway) and delegates the critical between-family blend to the larger public test set.
3. **If public submissions are limited:** Pre-register blend weights. Use rank-mean (not probability-mean) to make blend weights less sensitive — rank-mean is invariant to probability calibration differences between families.
4. **Constrain our-weight ≤ 0.35.** Based on the verified RadImageNet contribution (+0.012 at 0.20 weight early in the lineage), a single new family adds diminishing returns above ~0.25 weight.

---

## III. What Our Own Assets Add as Diversity

**Our pseudo-label pool (22.8k series from 4,349 studies):**
- Different from public pools (unknown what public used, but likely similar report-extraction methods).
- If our pseudo-labels have different systematic errors than public pseudo-labels, our models learn different "wrong" patterns → ensemble cancels some errors.
- Our geometry pipeline (slice order, mm crop, laterality) is independently implemented. Even if logically equivalent, numerical differences (interpolation, rounding) create slightly different inputs → diversity.

**Our CoAtNet trained on our data:**
- Different data order, different augmentation seeds, different fold splits.
- Same architecture trained on different data → higher ensemble diversity than same data + different architectures (per standard ensemble theory: data diversity > architecture diversity when architectures are similar).

**Our RadImageNet ResNet50:**
- We use 224px (0.58mm pitch) vs public's likely 336px. Different resolutions → different features learned.
- Our 3-view mid-slice triplet vs public's likely 5-view or slot-attention → different input representation.

**Our DINOv2 (if built):**
- Trained on our data with our labels → encodes our pseudo-label biases.
- Complementary to public DINOv2 trained on unknown labels.

**Quantified diversity expectation:** If our single best model is 0.88-0.89 and public ensemble is 0.93-0.94, the correlation between our errors and public errors is likely 0.6-0.8 (they're solving the same task on the same images). At correlation 0.7, optimal our-weight ≈ (1-0.7)/(2-2×0.7) = 0.25, and the blended score ≈ 0.5×(0.89+0.935) + diversity bonus ≈ 0.912 + 0.005-0.010 = **0.917-0.922**. This matches the path (c) range above.

---

## IV. Weighing Learning-the-Task vs Raw Rank

**Paths (a) and (c): Raw rank focus.**
- Rely on public weights for score.
- Risk: if private test differs (e.g., different prevalence, different scanners, different label quality), public-overfit ensembles degrade. The dinov3-ensembled author's warning is serious: 0.002-0.003 LB gains from hyperparameter tuning may reverse to -0.005 on private.
- Benefit: high public score now, which is the only signal that matters for competition standing.

**Path (b): Learning-the-task focus.**
- Build understanding of what works on this specific medical task.
- Failures teach us about MRI knee diagnosis, pseudo-label quality, and CoAtNet behavior.
- If we stay in this domain (medical imaging competitions), lessons transfer.
- Risk: lower public score → lower competition rank.

**Recommendation: Path (c) with learning-the-task emphasis.**
The hybrid approach gives us both: we learn from building our own diverse members, and we capture public-rank via the blend. If our members are genuinely good (0.89+), we contribute meaningfully. If they're mediocre (0.87), we still get 0.918+ from public weights. The key is that **we train models that would be useful even without public weights** — this forces us to solve the actual problem, not just ensemble.

---

## V. Smallest First Experiment to Validate the Choice

### Experiment: Single CoAtNet Full-Training Validation

**Purpose:** Test whether longer CoAtNet training (+5 views, +GOLD_UP) actually improves over r16, and whether the 58-gold CV can detect it.

**Design:**
- **One TPU run (3.5h):** CoAtNet@384, 10 epochs, BIG_FRAC=1.0, 5 views (mid ± 2 slices as 3-channel triplets, 3 such triplets = 3 views per series), GOLD_UP=3, batch 8 (if OOM), seed = r16 seed for comparability.
- **Compare to r16 CoAtNet:** Same fold split, same data, same seed. Only differences: epochs (10 vs 4), BIG_FRAC (1.0 vs 0.5), views (5 vs 3), GOLD_UP (3 vs 1).
- **Metric:** Per-fold AUC on the 3 gold validation folds (same folds as r16). Also: loss curves, per-finding AUCs.

**Decision rule:**
| Outcome | Interpretation | Action |
|---|---|---|
| CV improves by ≥0.02 (e.g., 0.898 vs 0.878) | CoAtNet upgrades are real | Proceed with path (c), run all 4 TPU runs |
| CV improves by 0.005-0.02 | Possible improvement, noise band | Run a second CoAtNet variant (different seed) to confirm; if both show same direction, proceed |
| CV unchanged or worse (≤0.005) | CoAtNet upgrades don't help on our data | Abort path (b); pivot to path (a) — download public weights and blend with r19 only |
| CV worse by >0.01 | CoAtNet overfits or 5-view breaks something | Debug 5-view logic, revert to 3-view, try only GOLD_UP+epochs as next experiment |

**Why this experiment is minimal:**
- Uses 1 of 4 TPU runs (3.5h of 16h budget).
- Answers the critical unknown: "Does longer CoAtNet training on our data help, or is our pseudo-label pool too noisy to benefit?"
- The r16 baseline CoAtNet alone had CV 0.897/0.855/0.848 (mean 0.867). If this experiment reaches 0.885+ CV, the CoAtNet path is validated.
- If it fails, we've only spent one run and can immediately pivot to public-weight assembly, saving 3 TPU runs for other experiments.

**Secondary validation (free, CPU):**
While TPU trains, compute rank correlation between our OOF predictions and public ensemble predictions (if any public weights are downloadable). If correlation >0.8, our models are largely redundant with public ones → path (a) is better. If correlation <0.7, our models add genuine diversity → path (c) has strong justification.

---

## VI. Budget Allocation

| Phase | TPU | GPU | CPU | Purpose |
|---|---|---|---|---|
| **Validation experiment** | 3.5h | 1h | 2h | Single CoAtNet full training; profile public model inference speed |
| **If GO:** Remaining 3 TPU runs | 10.5h | 0h | 0h | CoAtNet-seed2, ResNet50@256, DINOv2@336 |
| Ensemble inference | 0h | 8h | 0h | Blend 4 of our models + available public weights |
| Submission iteration | 0h | 0h | 2h | 3-4 blend weight candidates → public LB |
| **If NO-GO:** Public weight assembly | 0h | 12h | 2h | Download, validate, ensemble public weights + r19 |
| **Buffer** | 2h | 9h | free | Debugging, OOM fixes, re-runs |
| **Total used** | 16h | ≤21h | free | Within budgets |

---

## VII. Summary Recommendation

**Highest-value path: (c) Hybrid rank-blend, gated by the validation experiment.**

- **Expected public score: 0.920–0.932** if all 4 of our models train successfully and public CoAtNet weights are available.
- **Fallback (validation fails): Path (a) for 0.915–0.925.**
- **Not recommended: Path (b) alone.** Building 4 of our own models without public ensemble caps us at ~0.905 — we'd need 20+ diverse models to reach 0.93+, which requires more compute than we have.

**Why hybrid beats pure-attach:**
1. Our own diverse members at 0.25-0.35 weight contribute real diversity, not just noise.
2. Training our own models builds task understanding, which pays off if the competition has a second phase or private test surprises.
3. The validation experiment costs only 1 TPU run and prevents us from wasting 3 runs on a dead end.

**The unspoken truth:** No path realistically reaches 0.94 under our constraints. The frontier (0.943) required 20+ DINOv2 models + 4+ CoAtNet variants + RadImageNet + EfficientNet + months of LB tuning by a coordinated team. Our 4 TPU runs and 30 GPU hours cannot replicate that compute. The best we can do is **0.92-0.93 by intelligently blending our 4 diverse members with available public weights**, and hope that LB overfitting penalizes the frontier more than it penalizes our cleaner, less-tuned ensemble on the private test.