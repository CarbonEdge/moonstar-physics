# A working theory of how to train, model and scale

## 1. Core thesis
- Input data geometry correctness is the foundational prerequisite; before slice ordering, physical scale and laterality are fixed, label signal is largely wasted.  
- Scaling pseudo-label volume is associated with substantial public-AUC gains, but the experiments are confounded and the isolated magnitude is unknown.  
- Reliable measurement via a fixed, large gold-standard validation protocol is mandatory—without it, the public leaderboard progression cannot be trusted and may reflect overfitting.

## 2. The ordering rule: what to fix/scale first, second, third

| Order | Action | Evidence (round pair) | Effect size (public unless stated) | Caveat |
|-------|--------|------------------------|-----------------------------------|--------|
| **1st** | **Audit & enforce input geometry** (slice order, physical spacing, laterality) | r6 → r7 | +0.12 public | The leap is primarily attributed to geometry fixes, but undisclosed recipe changes may contribute; the isolated effect is therefore **downgraded** to “large but not precisely measured”. |
| **2nd** | **Maximise pseudo-label volume** from a low-cost source (e.g., LLM reports) | r8 → r12 | +0.05 public | The comparison confounds the addition of ≈22 k series with the removal of per-target confidence weighting and possible pipeline changes. **Direction** is credible, **magnitude** is not isolated. |
| **3rd** | **Invest in model capacity, resolution and fine-tuning** once label volume saturates | r14 (224 px) vs r16 (384 px) on CoAtNet-raptor; r18 frozen vs r16 fine-tuned | CV: resolution drop → −0.10; fine-tuning gain → +0.038 (single-model CV) | Both comparisons are confounded (resolution sweep uncontrolled; frozen vs fine-tuned used different hardware and backbones). No public confirmation exists. **Downgrade** to speculative until clean A/B tests are run. |

## 3. Scaling model

- **Data scale**  
  A log-linear slope of ≈0.033 AUC per 10× series was fitted from the two confounded points r8 and r12. **Not validated** – a pure scale effect cannot be extracted from these rounds.
- **Input resolution**  
  Dropping from 384 px to 224 px reduced CV by ≈0.10 (r14 vs r16). The comparison lacked matching hyper-parameters and therefore over-estimates the loss.
- **Model capacity & pretraining**  
  ResNet-18 → ResNet-50 gave +0.02 public (r5 → r6), but the change was bundled with RadImageNet pretraining and 3-fold CV. The true capacity-only contribution is unknown.
- **What is underdetermined**  
  All scaling curves (data, capacity, resolution, pretraining domain, fine-tuning recipe) are underdetermined because no clean, single-variable experiment has been performed.

## 4. Measurement protocol (how to decide between rounds reliably)

- **Gold-standard validation set**  
  Use ≥200 studies with confirmed labels. If impossible, supplement with stratified pseudo-labels but always monitor disagreement against the 58-gold list.
- **Fixed data splits**  
  Pre-define one stratified 5-fold split, identical for all experiments, with recorded seed and split files.
- **Reliable metric**  
  For each model train on all folds, report *mean AUC ± standard error*. Declare improvement only if the mean difference exceeds 2 × SE and is consistent across random restarts.
- **Leaderboard usage**  
  Submit a small fixed set of models periodically solely to detect drift in the CV-public gap; never select models based on public feedback.
- **Noise floor**  
  Measure training variance with repeated random seeds to calibrate the detection threshold.

## 5. Falsifiable predictions for the next rounds

1. **Resolution sweep (clean A/B, RadImageNet ResNet-50)**  
   Mean CV AUC will increase monotonically with pixel size (224 → 256 → 320 → 384 px), but the difference between 256 and 384 px will be **≤0.03** CV. (No quantitative justification beyond a plausible saturation guess.)
2. **Best single-model public AUC with current data**  
   A well-tuned CoAtNet-raptor fine-tuned at 384 px on 22.8 k series, with no leaderboard over-optimisation, will score **0.89–0.92** on Kaggle public. Basis: r16 CV ≈0.878 and historical CV-public gap ~+0.03; the wide range reflects uncertainty from overfitting risk and unknown public-set composition. (Not statistically justified.)
3. **Geometry-fixed frozen ensemble**  
   Running the r17 ensemble pipeline with input-geometry fixes correctly implemented will yield a public AUC ≥0.87, exceeding r17’s 0.856. (Direction predictable; exact number not justified.)

## 6. Ranked experiment plan (30 h GPU + 16 h TPU + free CPU per week)

| # | Experiment | Hardware | Approx. time | Purpose |
|---|------------|----------|--------------|---------|
| 1 | **Resolution sweep** — RadImageNet R-50 at 224, 256, 320, 384 px (same folds, epochs, augmentations) | GPU | 4 h | Clean resolution-AUC curve; unconfounds r14/r16 |
| 2 | **Capacity scaling** — RadImageNet R-18, R-34, R-50, R-101 all at 384 px | GPU | 4 h | Isolate model capacity, holding resolution and pretraining constant |
| 3 | **Data-scale ladder** — Train R-50@384 on 700, 1.4 k, 3.5 k, 10 k, 22.8 k series subsets | GPU | 5 h | Disentangle data scale from the r8↔r12 confounds; fit scaling law |
| 4 | **Fine-tuned vs frozen head** — CoAtNet-raptor fine-tuned vs frozen (both on GPU) | GPU | 3 h | Quantify fine-tuning premium without hardware confound |
| 5 | **Pretraining domain A/B** — ImageNet vs RadImageNet R-50 at 384 px | GPU | 2 h | Isolate value of medical-domain pretraining |
| 6 | **TPU vs GPU repeatability** — Re-run best R-50@384 config on TPU with identical hyper-parameters | TPU+GPU | 1.5 h TPU + 1 h GPU | Test for systematic bfloat16/batch-size benefits |
| 7 | **Large-fold CV for measurement** — 5-fold† of r16 protocol (CoAtNet-raptor fine-tuned) on TPU | TPU | ≈11.5 h | Obtain reliable mean ± SE to replace the 3-fold uncontrolled CV |

†5-fold chosen to fit 16 h TPU budget; if more time, 10-fold gives higher precision.

## 7. What this theory cannot yet explain

- The true functional form and saturation point of pseudo-label quantity (any log-linear slope is fitted from two confounded points).  
- The isolated effect of per-target confidence weighting versus simply adding more data.  
- The genuine contribution of domain-specific pretraining (still confounded with capacity and fold changes).  
- Whether the public leaderboard progression reflects real improvement or systematic overfitting to a small fixed test set.  
- The impact of fine-tuning compute budget (number of epochs, batch size) – not systematically swept.

---

## Appendix: reviewer corrections (human/Claude fact-check against `data-summary.md`)

Generated by `pipelines/ml_theory_synthesis.yaml` (3 theorists -> evidence critic -> synthesizer, cost $0.008). The model had only the summary, so these items need correcting:

- **r6 -> r7 is the cleanest pair, not a weak one.** r7's own submission note says the model is "unchanged from r6" apart from the geometry fixes, so +0.124 public (0.687 -> 0.811) is a near-isolated effect. The "undisclosed recipe changes" downgrade in section 2 is unwarranted.
- **Prediction 3 is invalid.** r17 already includes the r7 geometry fixes; there is no "geometry-fixed" variant to run.
- **Section 4 asks for >=200 gold studies; only 58 exist.** The realistic protocol is a held-out pseudo-label set (~500 studies) used alongside the 58 gold, plus fixed folds and seed repeats.
- **Prediction 2 (0.89-0.92)** leans on the CV->public gap (+0.02 to +0.03, unstable ordering) and r16's fold spread (0.848-0.909). Treat 0.87-0.91 as the honest range until r16 is submitted.
- **The "-0.10 resolution" and "+0.038 fine-tune" numbers** are CV deltas between rounds that differ in pipeline, folds and hardware (r14 vs r16; r18 vs r16). Directional only.
- **The log-linear data slope (~0.033 AUC per 10x)** comes from two confounded points (r8, r12). Do not extrapolate.
- **Section 6 cost check:** experiment 7 (5-fold r16 protocol) = 5 x 2.3 h ~ 11.5 h TPU, consistent with the 16 h budget but leaves ~4.5 h.
