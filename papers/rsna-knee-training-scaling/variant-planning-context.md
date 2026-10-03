# Decision problem: which variants to run next on the RSNA knee task

## Hard constraints (facts)
- Code competition: the SCORING rerun cannot use TPU ("Your Notebook cannot use TPU in this competition"). TPU works for ordinary training runs.
- Pipeline now: train on TPU (saves per-fold weights) -> weights dataset -> inference notebook on GPU/CPU loads weights, predicts hidden test. Inference averages any set of saved models.
- Budgets this week: TPU 16 h, GPU 30 h, CPU free. One r16-recipe training run on TPU = ~3.5 h (decode ~21 min, CoAtNet@384 ~2.3 h for 3 folds, ResNet50@224 ~1 h).
- Gold labels: only 58 studies. Pseudo-labels (LLM from reports): ~4,349 studies, ~22.8k-series pool. Local CV = 3 folds over the 58 gold studies (~19 val studies per fold); ALL pseudo studies are always in the training set. So CV noise is large (fold AUCs 0.848 / 0.876 / 0.909).
- Public score is the only trusted signal; submission count is limited per day. Local CV ranked past rounds wrongly vs public (CV->public gap +0.02..+0.03, unstable).

## r16 recipe (the baseline being reproduced as r19, which saves weights)
- Members: RadImageNet ResNet50 @224 (6 epochs, lr 2e-4, 3 views=mid+-1 slices as RGB, max 6 series/pseudo study, 8/gold), raptor CoAtNet (`coatnet_rmlp_2_rw_384.sw_in12k_ft_in1k`) @384 (4 epochs, lr 1e-4 cosine, each epoch sees a random 50% of rows via BIG_FRAC=0.5, batch 16).
- Loss: per-element BCE with per-target pos_weight (cap 15) and per-target label-confidence weights (floor 0.15); gold and pseudo concatenated (no explicit gold upweight in the train notebook; the frozen-feature r18 used GOLD_UP=3).
- Study-level aggregation: per-target mean or max pooling across series, chosen on gold OOF. Flip TTA. Ensemble weights chosen on gold OOF (r16: 0.75 CoAtNet / 0.25 ResNet).
- Augmentation: random h-flip + ±10° rotation. Geometry fixes (slice order, mm crop, laterality) already in.
- r16 result: CV 0.878 (folds 0.909/0.876/0.848); CoAtNet alone 0.897/0.855/0.848; ResNet alone 0.797/0.874/0.818. Public unknown yet (not submitted).

## Prior public results (for calibration)
r12 0.865 (CV 0.832, ResNet r50 @224, full pseudo pool), r13b 0.862 (CV 0.841, 2 views@256, 10 epochs), r17 0.856 (CV 0.825, frozen features heads, CPU), r8 0.815, r7 0.811 (geometry fix, +0.124 vs r6).

## Known evidence on levers
- Geometry/input correctness: huge (+0.12). Pseudo-label volume 700 -> full pool: ~+0.05 (confounded). Recipe tweaks on ResNet (views, res 224->256, epochs 6->10): CV +0.009 / public -0.003 = noise. Weight averaging of last epochs: -0.01. Flip TTA ~0.
- Native-resolution fine-tuned CoAtNet vs frozen CoAtNet features: ~+0.04 CV. CoAtNet at wrong res (224): member AUC 0.61-0.77.
- CoAtNet is currently under-trained by design (4 epochs x 50% of rows = 2 effective epochs).
- Fold spread and the 58-gold CV mean we cannot distinguish rounds that differ by <0.02.

## Candidate variant families (to be evaluated, not pre-decided)
A. Same recipe, different seeds / different fold splits; average in inference (variance reduction).
B. Train on ALL 58 gold + pseudo (no holdout) for the final models; use fold-run CV only for diagnostics.
C. Longer / fuller CoAtNet training (more epochs, BIG_FRAC=1.0), possibly larger LR schedule.
D. Gold upweighting (GOLD_UP) or two-stage: pretrain on pseudo, fine-tune on gold.
E. Label-quality: blend additional pseudo-label source (tsuyu122) after checking vs gold; drop low-confidence pseudo rows.
F. More/wider views per series (r13b style) for the CoAtNet; more slices (2.5D).
G. Use the CoAtNet frozen-feature heads (r18-style, CPU) as extra cheap ensemble members.
H. Build a ~500-study held-out pseudo-label validation set to make decisions measurable.
