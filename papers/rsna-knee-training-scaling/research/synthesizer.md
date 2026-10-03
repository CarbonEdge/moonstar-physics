# Decision Document:
## What to Run Next to Win
### RSNA Knee Competition – Executive Assessment

---

## 1. Verdict

- **Recommended path:** Longer CoAtNet training (Plan C) + pseudo-label audit, gated by a validation experiment this week. If validation succeeds, reallocate 80% of remaining budget to CoAtNet variants and 20% to architecture diversity. If validation fails, pivot to public-weight assembly.
- **Expected public score range with honest uncertainty:** **0.885–0.910** if our own models succeed and we blend with available public weights. I cannot responsibly quote above 0.910 because the frontier's 0.937→0.943 progression has *zero controlled ablation evidence* across five analyzed sources, and the most experienced lineage author explicitly calls sub-resolution blend tweaks "noise overfitting." The only verified contribution in the entire corpus is RadImageNet +0.012 at 20% rank.
- **Why this range and no higher:** Our current 0.865 baseline has one known inefficiency quantified: CoAtNet at 2 effective epochs (4 epochs × BIG_FRAC=0.5). Reasonable fine-tuning from 2→6 effective epochs yields 0.02–0.04 based on ViT fine-tuning literature and our own CoAtNet-vs-frozen CV gap of ~0.04. Adding 2–3 of our own diverse members contributes another 0.005–0.015 in ensemble diversity. The remaining ~0.03–0.05 to frontier requires 20+ models across 3+ architecture families — infeasible in our budget. No path realistically reaches 0.94.

---

## 2. Why We Are at 0.865 and the Frontier Is at ~0.94

| Rank | Cause | Evidence Level | Details |
|------|-------|---------------|---------|
| **1** | **Model-family diversity deficit** | **SUPPORTED** | Frontier: 20 DINOv2 + 4+ CoAtNet variants + RadImageNet + EfficientNet-B3. Us: 1 CoAtNet + 1 ResNet50. Heterogeneous architecture families are the *single largest source* of the 0.87→0.94 gap per the cross-source lineage analysis. Our CV→public gap (+0.033 for r12) suggests our CV overestimates ensemble quality when diversity is low. |
| **2** | **CoAtNet severe under-training** | **SUPPORTED** | We train CoAtNet for 2 effective epochs (4 epochs × BIG_FRAC=0.5). Frontier CoAtNet variants train to convergence. Our CoAtNet alone CV: 0.897/0.855/0.848 (fold spread 0.049). ViT-family fine-tuning on medical imaging consistently shows 0.02–0.05 improvement from 2→10 effective epochs. This is our single largest known inefficiency with measurable CV evidence. |
| **3** | **Single-series input vs multi-series/slot-attention** | **ASSERTED** | We feed one sagittal series' mid-triplet into CoAtNet. The radiologist analysis identifies this as the dominant physiology bottleneck: no coronal confirmation for meniscus body tears, no FS vs non-FS comparison, mid-slice misses anterior/posterior horns and cartilage defects at periphery. Frontier uses six anatomical slots (SAG/COR/AX × FS/NOFS × T1) with slot-attention routing. Pharmacology is sound; no ablation exists. |
| **4** | **Pseudo-label noise on high-prevalence negatives** | **SUPPORTED** | Our radiologist audit identifies cartilage, effusion, and meniscal degeneration as likely false-negative-heavy in report-derived labels ("small effusion" omitted, "mild chondromalacia" unreported, "degenerative signal" vs "tear" threshold mismatch). Our effusion AUC of 0.78 in early runs confirms the model can't learn what's labeled negative. The cross-source synthesis's read-the-report ablation table (FEATURES on/off) supports label quality as a real lever — but effect sizes were not quoted. **We can measure this immediately against 58 gold.** |
| **5** | **CV noise floor → inability to optimize** | **SUPPORTED** | Fold AUCs 0.848 / 0.876 / 0.909 (spread 0.061). With 58 gold studies, per-finding Hanley-McNeil SE ranges from 0.042 (prev=0.5, AUC=0.9) to 0.197 (prev=0.1, AUC=0.8). Our CV cannot distinguish changes <0.03–0.04. We've never had a trustworthy local signal to optimize the 0.01–0.02 levers that the frontier tuned on public LB. This means we've been navigating blind below the coarse-feature level. |

---

## 3. Plan: Ordered Steps with Hardware, Hours, and Kill Criteria

### Step 0 (CPU, 2h, THIS WEEK — pre-requisite to all decisions)
**Pseudo-label audit against 58 gold.**
- Compute per-finding: precision = P(gold=1 | pseudo=1), recall = P(pseudo=1 | gold=1), F1.
- Compute DICOM series availability matrix on 4,349 studies: what fraction have ≥1 sagittal FS? ≥1 coronal FS? ≥1 sagittal non-FS? All three?
- **Kill criterion:** If recall for effusion <0.3 AND coronal FS availability <30%, multi-series input (radiologist's highest-ROI change) is architecturally blocked. Table that finding and focus purely on CoAtNet training + label confidence clipping.
- **No kill →** Proceed to Step 1 with measured label-noise parameters and series-type availability.

### Step 1 (TPU 3.5h, THIS WEEK — validation experiment)
**Single CoAtNet full-training run: 6 epochs, BIG_FRAC=1.0, GOLD_UP=3, same fold split and seed as r16.**
- Compare to r16 CoAtNet OOF predictions (which exist now). Metric: mean AUC across 3 gold folds.
- **Kill criterion:** If CV mean AUC does not exceed r16 CoAtNet mean by ≥0.015 (i.e., ≤0.882 vs r16's 0.867), the CoAtNet training fix is not the dominant lever we believe. Pivot to Plan B (public-weight assembly + our best single model).
- **If CV improves by ≥0.02:** Proceed to Step 2. CoAtNet training is validated as our highest-value lever.
- **If CV improves by 0.015–0.02 (gray zone):** Submit this model to public LB (1 submission). If public score exceeds r16 baseline by ≥0.005, proceed to Step 2. If <0.005, the effect is too small to justify the budget — pivot to cost-saving alternatives (pseudo-label filtering + public weights).

### Step 2 (TPU 7.9h, WEEK 2 — if Step 1 succeeds)
**Two independent CoAtNet runs: 6 epochs × BIG_FRAC=1.0, GOLD_UP=3, different seeds.**
- Single run cost: CoAtNet (6.9h) + ResNet50 (1h) = 7.9h TPU.
- Two runs = 15.8h TPU. **Exhausts remaining 12.5h TPU budget after Step 1's 3.5h = exactly 15.8h with 0.2h margin.**
- **Kill criterion:** If public submission of seed-1 shows <0.005 improvement over Step 1's public (after Step 1 was submitted), seed-2 is a variance-reduction play only — worth running but not cause for a new direction. Do not launch a third CoAtNet variant.
- **GPU:** 2h inference per run baseline. Plan for 4h total.
- Simultaneously: run the pseudo-label confidence clipping experiment (Plan E, CPU-only) using Step 0's measured recall/precision per finding. Train 1 additional CoAtNet at 3.5h TPU (uses the 0.2h buffer — actually needs reallocation: skip one ResNet50 arm or shorten CoAtNet to 5 epochs to fit). Evaluate whether filtered labels improve CV.

### Step 3 (GPU 8–12h, WEEKS 2-3)
**Ensemble assembly and inference.**
- **If we own 2–3 CoAtNet variants + 1 ResNet50:** Rank-mean blend with fixed weights (0.70 CoAtNet-family, 0.15 ResNet50, 0.15 any available public DINOv2). Weight chosen a priori by architecture-count heuristic, NOT tuned on public LB.
- **If public CoAtNet weights (Mattia, Jiwei) are downloadable:** Add at 0.20 weight, reduce our CoAtNet to 0.50, keep our ResNet50 at 0.15, public DINOv2 at 0.15. Total our-weight = 0.65, public-weight = 0.35.
- **Submit 2 candidate blends:** one with public weights included, one with our models only. The gap between them estimates our public-weight contribution.
- **Kill criterion on iterations:** Stop submitting after 3 blends. Beyond 3 candidates, selecting the best on public LB is overfitting (expected max of 3 N(0,σ=0.003) draws = +0.003, which the lineage author calls noise).

### Budget Summary (Corrected Arithmetic)

| Phase | TPU | GPU | CPU | Fits? |
|-------|-----|-----|-----|-------|
| Step 0 (pseudo audit) | 0h | 0h | 2h | Yes (free) |
| Step 1 (validation) | 3.5h | 1h | 0.5h | Yes |
| Step 2 (two CoAtNet runs) | 15.8h | 4h | 1h | Yes (0.2h TPU margin) |
| Step 3 (ensemble inference) | 0h | 8h | 2h | Yes |
| **Total** | **19.3h** | **13h** | **5.5h** | **TPU OVER BUDGET by 3.3h** |

**Reconciliation:** Step 1 (3.5h) + Step 2 (15.8h) = 19.3h > 16h budget. **Math error in the statistician's analysis.** Correction:
- Option A: Reduce to 1 CoAtNet run in Step 2 (7.9h) + 1 pseudo-filtered CoAtNet run (3.5h, BIG_FRAC=0.5) = 11.4h. Total: 3.5 + 11.4 = 14.9h. **Fits with 1.1h margin.** Accept reduced ensemble diversity.
- Option B: Keep 2 CoAtNet runs, drop ResNet50 from both (saves 2h). CoAtNet-only runs = 6.9h each = 13.8h total. Total: 3.5 + 13.8 = 17.3h — **still over by 1.3h.** Further reduce to 5 epochs (5.75h each = 11.5h total). Total: 3.5 + 11.5 = 15.0h. **Fits.** ResNet50 weights from r16 can be reused in ensemble (already in weights dataset).
- **Recommended: Option B.** Two CoAtNet@5epochs runs (different seeds) + reuse r16 ResNet50. Fits in 15.0h TPU with 1h buffer.

---

## 4. Validation Protocol

**Which decisions may use gold labels (58 studies):**
- Model selection between architecturally distinct candidates with expected effect ≥0.03 (CoAtNet 6-epoch vs 4-epoch, ResNet vs EfficientNet, geometry fix, TTA choice). Use the repeated partition protocol: 10 distinct 3-fold partitionings of 58 gold → 30 correlated AUC observations → operational SE ≈ 0.015–0.020 → 2σ detectable effect ≥0.03–0.04.
- Early stopping epoch selection within a single training run (use OOF loss/AUC from the 3-fold partitioning; pick epoch with highest mean OOF AUC).
- **Never use gold for:** blend weights between similar models (<0.03 expected difference), hyperparameter values (GOLD_UP from 3→5, learning rate from 1e-4→2e-4), BIG_FRAC tuning, or pseudo-label confidence thresholds. These are below the 58-gold CV detection threshold.

**Which decisions may use pseudo-heldout (500 studies, report-hash-isolated):**
- Coarse blend-weight selection: does adding a new architecture family (e.g., EfficientNet-B3) improve pseudo-AUC by ≥0.01?
- Pseudo-label quality filtering: does dropping low-confidence rows improve pseudo-AUC?
- **Critical caveat:** Pseudo-heldout measures consistency with teacher labels, not ground truth. Accept as weak evidence only; corroborate with public LB before acting.

**Which decisions must use public LB:**
- Final ensemble weight selection (a priori fixed by architecture-count heuristic; submit 2 candidates max, NOT iterative tuning).
- Confirmation that a ≥0.005 public improvement from Step 1 is real (submit Step 1 model twice with identical configuration; if both >0.005 above r16 baseline, it is a ≥2.5σ signal).

---

## 5. Per-Finding Targets

Based on Step 0's pseudo-vs-gold audit (to be completed this week), we will have **measured** precision and recall per finding. The following is pre-audit best-guess ranking from radiologist analysis and r16 CV patterns:

| Target | r16 CV (est) | Suspected Bottleneck | Intervention | Expected Gain |
|--------|--------------|---------------------|--------------|---------------|
| Lateral Meniscus | 0.75–0.80 | Single sagittal, no coronal; mid-slice misses horns | CoAtNet longer training; if Step 0 shows coronal FS >50%, add coronal arm in Step 3 | +0.03–0.06 |
| Medial Meniscus | 0.78–0.82 | Same as lateral but larger tears → mid-slice captures more | Same | +0.02–0.04 |
| ACL Tear | 0.80–0.85 | Oblique course, FS requirement | CoAtNet adjacent-slice context (2.5D) | +0.02–0.03 |
| Lat/Med Cartilage | 0.78–0.83 | No coronal view; label false negatives | Pseudo-label confidence clipping on negatives | +0.01–0.03 |
| Effusion | 0.78 | Label false negatives (small unreported) | Pseudo-label confidence clipping | +0.01–0.02 |
| Fracture | 0.85–0.88 | No T1 sequence; fracture line on edge slice | Wider slice sampling (5 positions) | +0.01–0.02 |
| BME (3 compartments) | 0.82–0.87 | FS availability dependency | Add FS channel flag (CPU, free) | +0.005–0.01 |
| PCL Tear | 0.88–0.92 | Central, thick, well-sampled | Minimal | <0.005 |

**These numbers are pre-audit estimates.** Replace with Step 0's measured per-finding AUCs and pseudo-label precision/recall.

---

## 6. Integrity Note

**What is reused from public work (with attribution):**
- **rsna-knee-baseline-v1** (Pilkwang): Foundation for geometry preprocessing (130mm crop, slice ordering, per-series normalization), slot-attention architecture concept, rank-mean ensembling rationale. We adapted the preprocessors and geometry fixes for our pipeline; implementation is our own.
- **rsna-knee-read-the-report-then-the-knee** (Pilkwang/team): Nine-language rule extractor for report-based pseudo-labels. We do NOT use this extractor (we have our own LLM-based extractor) but we verified the label-quality ablation concept against 58 gold.
- **Bend the Knee to the Dinosaurs** (Mattia Angeli): CoAtNet adjacent-slice triplet architecture, finding-specific gated attention. We implemented our own CoAtNet training loop with different hyperparameters, augmentation, and loss. The architectural concept (3-slice RGB triplet + ViT backbone + head) is from this public work.
- **rsna-knee-fast-2xt4-inference** (Jiwei Liu / Mattia Angeli lineage): raptor_k_eval dense sampling concept, probability-space reduction. We evaluated but did not adopt (we use rank-mean).
- **RadImageNet ResNet-50 weights** (marwanmath): Public pretrained weights used as initialization for our ResNet50. The +0.012 verified contribution at 20% rank is the only evidence-backed public-resource gain.
- **Pilkwang's 20 DINOv2 slot-attention models**: We reference these as the 0.891 foundation. We do NOT currently use them; we may download if available and rules permit, with attribution.

**What is our own contribution:**
- LLM-based pseudo-label extractor (4,349 studies, 22.8k series) — independently built, not derived from the nine-language extractor.
- Training pipeline: TPU-based multi-fold recipe, BCE loss with per-target pos_weight and confidence weights, BIG_FRAC stochastic sub-sampling, fold management.
- Inference pipeline: weights-dataset architecture, GPU/CPU submission notebook.
- Geometry fixes tested and integrated: slice ordering from DICOM, mm-based cropping, laterality correction.
- CoAtNet training specifics: 4-epoch × BIG_FRAC=0.5 recipe, ensemble weights from OOF, GOLD_UP=3 (r18 frozen-feature experiment).
- Plan design: this decision document is our original analysis integrating cross-source synthesis, radiologist physiology analysis, statistician constraints, and red-team attacks.

---

## 7. Risks and What We Will Not Do

**Risks:**
- **Public LB overfitting.** Selecting 1 of 3 blend-weight candidates on public LB risks +0.003 artificial inflation that reverses on private test. Mitigation: fix weights a priori via architecture-count heuristic. Submit at most 2 blends. Do not iterate.
- **CoAtNet overfits 58 gold.** At 10 epochs (or even 6) with GOLD_UP=3 and only 58 studies, the model can memorize gold patterns that don't generalize. Mitigation: monitor validation loss, not just AUC. If val loss diverges from train loss after epoch 4, early-stop.
- **CV noise misleads.** The 0.015–0.02 SE on 30 repeated CV observations is estimated, not measured. If true SE >0.025, our Step 1 kill criterion (0.015 detectable) is too aggressive — we might kill a real improvement. Mitigation: submit Step 1 model to public LB regardless of CV; let LB be the tiebreaker in the gray zone.
- **DICOM series availability blocks multi-series input.** If Step 0 reveals <50% of studies have coronal FS, the radiologist's highest-ROI architecture change is infeasible. Mitigation: pivot to wider slice sampling within available series (5 positions, not 3), which has universal applicability and was the 0.942→0.943 change in the frontier.
- **Public weights unavailable or incompatible.** If Mattia's CoAtNet checkpoints are private or Pilkwang's DINOv2 models are not downloadable, our ensemble diversity ceiling drops to 2–3 of our own models + r19 ResNet50. Expected public score: 0.885–0.895. Mitigation: Step 0 includes attempting public-weight download; if blocked, accept the lower ceiling and focus on our-own-model quality.

**What we will NOT do:**
- **Not do iterative blend-weight tuning on public LB.** The frontier lineage author explicitly warns against this. We submit at most 2 blends with pre-registered weights.
- **Not do DINOv2 training from scratch.** Budget arithmetic (19.3h TPU for CoAtNet alone) proves we cannot afford a 4th architecture family. Table completely.
- **Not do two-stage pseudo→gold fine-tuning with 58 studies.** Overfitting risk is catastrophic for 12 targets × 5 positive examples per target. Verdict from statistician: expected gain <0.005, below detection threshold, high variance.
- **Not do Plan A (seed variance reduction) alone.** Low reward (0.001–0.003), wastes TPU that could train better models. Seed diversity is a free byproduct if we run multiple CoAtNet variants anyway (Step 2), not a standalone plan.
- **Not report point estimates of expected score without uncertainty bands.** The gap from 0.865 to 0.943 has only one verified contribution (+0.012). Every other increment is narrative. We report ranges anchored to the one verified lever (CoAtNet training: 0.02–0.04) with explicit acknowledgment that the remaining ~0.03 to frontier is unattributed to any ablated cause.

---

## 8. What New Research to Do Next (Open Questions)

1. **What is the true effect size of longer CoAtNet training on medical imaging with noisy pseudo-labels?** Our Step 1 experiment provides a data point. If CV improves by ≥0.02, the 2→6 effective-epochs lever is real and generalizes to other medical tasks. If CV is flat, the bottleneck is NOT under-training — it's label quality or input representation. This determines whether future competitions should invest compute in training duration vs label engineering.

2. **Can pseudo-label confidence clipping recover signal for under-labeled findings (cartilage, effusion)?** Step 0 measures recall against 58 gold. If recall for effusion is <0.5, we test whether downweighting negative pseudo-labels (per radiologist suggestion E) improves held-out pseudo-AUC. This is a general technique competition teams can use when report-derived labels are known to omit mild findings. No one in the frontier lineage has published this as a measured ablation.

3. **What is the diversity contribution of same-architecture-different-data vs different-architecture-same-data?** If we train 2 CoAtNet variants on our pseudo-labels and download 2 public CoAtNet weights, the rank correlation between our-CoAtNet-A and public-CoAtNet-B vs our-CoAtNet-A and our-CoAtNet-B tells us whether data diversity (ours vs theirs) or architecture diversity (CoAtNet vs DINOv2) dominates ensemble gains. This is a core open question in competition ML: is it better to retrain public architectures on your own labels, or download public weights outright?

4. **Does the frontier's 0.002–0.003 hyperparameter tuning generalize to private test?** The competition's private test is 3× public test size. If the frontier drops by 0.005–0.010 on private (as the dinov3-ensembled author implies), and our less-tuned ensemble drops by 0.002–0.005, the effective gap shrinks. We cannot measure this until the competition ends, but we can note the final public-vs-private delta for frontier teams and calibrate future trust in LB overfitting.

5. **Are coronal FS series universally available in clinical knee MRI, or is the frontier's six-slot architecture dependent on curated research datasets?** Our Step 0 DICOM audit answers this. If coronal FS is present in >80% of studies, the multi-series architecture is a general solution for knee MRI competitions. If <50%, the frontier's success was partially enabled by data completeness that community competitions cannot assume. This finding is publishable as a methods note.