# Situation Assessment

You have 58 gold-labeled studies. To distinguish two variants that differ by 0.02 AUC, you need at least 2-sigma separation, which requires ~86 studies per arm (or ~172 total) at moderate prevalence and AUC. You have 58 total. This means **local CV cannot resolve the 0.01–0.03 increments that separate LB positions**, exactly as observed: your own fold AUCs span 0.061 (0.848–0.909), and your gap to frontier (0.078) is nearly triple any single known lever effect. Feature work (geometry) produced detectable +0.12 changes; architecture changes (0.03–0.04) produced borderline detectable changes; everything else is noise-level at N=58.

The frontier lineage 0.906→0.943 has exactly one verified ablation: RadImageNet +0.012 at 20% rank. The 0.937→0.943 progression is entirely narrative, with 0.002–0.003 increments that the most experienced lineage author explicitly calls noise.

**What 58-gold CV can resolve:** changes ≥0.04 (e.g., adding a new architecture family like CoAtNet, fixing a data pipeline bug, switching from frozen to fine-tuned features).

**What 58-gold CV cannot resolve:** blend weight changes, epoch counts from 4→10, BIG_FRAC from 0.5→1.0, gold upweighting strategies below ~4x, pseudo-label clipping, individual ensemble member contributions <0.03.

# Validation Protocol Design

## Stratified Report-Hash Grouped Splits (Repeated)

- Group by `report_hash` so all series from one pseudo-report assignment stay together; no leakage.
- Stratify on earliest available report Y/N vector to preserve label prevalence.
- Create 10 distinct 3-fold partitionings of the 58 gold studies (each fold = 19–20 studies).
- For each partitioning, the 39–40 gold studies join all pseudo studies as training; the 19–20 gold are validation.
- This gives 30 “repeated CV” observations per configuration (10 partitionings × 3 folds).
- Operational SE on 30 correlated observations ≈ 0.015–0.02 for AUC, meaning a 2-sigma detectable effect is ~0.03–0.04.
- **Which decisions may use gold:** model selection between architecturally distinct candidates (CoAtNet vs ResNet), stopping-epoch selection, TTA choice, hardware/resolution decisions. No blend weight or hyperparameter tuning may use gold except via this repeated partition framework, and even then only >0.03 effects are reportable.

## Nested Blend-Weight Validation (Pseudo-Heldout)

- Reserve ~500 studies from the pseudo pool (report-hash selected, not overlapping the 58 gold) before any training.
- This held-out pseudo set gives ~500 observations for 12 targets × prevalence ~0.1–0.4, providing SE ~0.015–0.025 per target, mean ~0.004–0.007 across targets (assuming moderate correlation).
- Evaluate ensemble blend weights, pseudo-label quality filters, and inference-time aggregations against these held-out pseudo labels.
- **Critical caveat:** pseudo labels are teacher predictions, so this measures consistency with teacher, not true accuracy. Trust only coarse directional checks: does a large change (adding 0.5-weight CoAtNet) move pseudo-AUC? Fine-tuning (0.45→0.55) is not measurable here—the SE on the difference of two rankings is ~0.01, which matches the effect size.

## Trustworthy Public LB Signals (Daily Limit)

With ~5 submissions/day and public LB noise estimated at σ ≈ 0.002–0.003:

- A single submission score change < 0.003 is **noise**.
- A single submission score change 0.003–0.006 is **suggestive**, requires 2+ repeated submissions with same configuration and consistent >0.003 gap to prior best.
- A single submission score change > 0.006 is **trustworthy signal** (3-sigma against noise).
- Ensemble member changes: if adding member X gives +0.004–0.006 in two independent submissions (different seeds/pseudorandom components), it is real.
- **Do not trust:** single submissions improving by 0.001–0.002 after tuning a weight. These are within-noise and the frontier lineage author explicitly warns against them.
- **Trust after 3+ corroborating submissions at consistent magnitude:** architectural changes, major member additions, label-quality changes.

# Candidate Plan Evaluations

## Plan A: Seed/Fold Variance Reduction (TPU-heavy)

**Design:** Run r16 recipe 4 times with different seeds (fold splits fixed). Inference averages all 4×3 = 12 models.

**Budget arithmetic:**
- 4 runs × 3.5 h = **14.0 h TPU** (fits in 16 h with 2 h margin)
- GPU: weights-dataset build + inference overhead ≈ **4 h** (loading 12 checkpoints, predicting)
- Total: 14 h TPU, 4 h GPU. **Fits budget.**

**Expected gain and evidence basis:**
- Your fold AUCs show σ_fold ≈ 0.025. Averaging 4 seeds reduces fold variance by √4 = 2×, but most of this variance is gold-N noise, not model instability. True model variance across seeds with same hyperparameters on fixed architecture is typically σ_seed ≈ 0.002–0.005 (from LB chaos literature). Expected LB improvement: 0.001–0.003.
- Can 58-gold CV detect? No: σ_CV(fold) ≈ 0.02 dominates.
- Can public LB detect? Marginally: need 3–4 submissions to confirm a 0.002–0.003 mean shift against σ=0.003 noise.
- **Verdict:** Low risk, low reward. Fits budget. Do only if it's free alongside other plans (takes zero cognitive cost beyond the runs).

## Plan B: Train on All 58 Gold + Pseudo (No Holdout)

**Design:** Use full 58 gold + all pseudo in training; no OOF CV. Evaluate solely via public LB and pseudo-heldout.

**Budget arithmetic:**
- 1 run × 3.5 h TPU = **3.5 h TPU** with identical recipe but n_gold=58 instead of ~39.
- Inference: standard ~2 h GPU.
- Total: 3.5 h TPU, 2 h GPU. **Fits budget with massive slack.**

**Expected gain and evidence basis:**
- Training on 58 vs 39 gold adds ~19 positive examples spread across ~12 targets (prevalence-dependent). For a target with prevalence 0.3, n_gold goes from ~12 to ~18. Gold-upweighted contribution to loss: negligible at current gold/pseudo ratio (~58/4300 = 1.3%). Even with GOLD_UP=3 (r18 style), the additional gold studies contribute ~0.013 of the total loss mass.
- Expected LB improvement: 0.000–0.003. Not distinguishable from Plan A.
- **Can CV detect:** N/A (CV is abandoned).
- **Public LB:** Same noise floor; need same 3–4 submissions to confirm.
- **Verdict:** Low cost, marginal gain. Do alongside Plan C as the "final" model after architecture/epoch decisions are made with Plan C's CV results. Not a standalone high-value path.

## Plan C: Longer/Fuller CoAtNet Training (GPU-bottleneck not TPU?)

**Design:** Increase CoAtNet from 4 epochs × BIG_FRAC=0.5 (= 2 effective epochs) to 6 epochs × BIG_FRAC=1.0 (= 6 effective epochs). Keep ResNet50 fixed. Potential LR warm-restart at epoch 4 (cosine cycle 6 epochs, lr 1e-4→1e-6).

**Budget arithmetic:**
- Current r16 CoAtNet: ~2.3 h for 3 folds, 4 epochs each, BIG_FRAC=0.5 → total CoAtNet compute ≈ 2.3 h.
- With BIG_FRAC=1.0, per-epoch compute doubles (2× rows). At 6 epochs: 2.3 × (6/4) × (1.0/0.5) = 2.3 × 1.5 × 2 = **6.9 h** for CoAtNet alone.
- Total run: ResNet50 (1 h) + CoAtNet (6.9 h) = **7.9 h TPU**.
- Fits in 16 h with room for exactly 2 runs (15.8 h) or 1 long run + Plan A corner cases.
- GPU inference: standard **2 h**.
- **Fits budget** for 1–2 runs.

**Expected gain and evidence basis:**
- CoAtNet is severely under-trained (2 effective epochs). Standard fine-tuning of ViT-family models on medical imaging shows 0.02–0.05 improvement from 2→10 effective epochs, especially with larger LR warmup.
- Your own data: CoAtNet alone fold AUCs 0.897/0.855/0.848 (mean 0.867) vs ResNet 0.797/0.874/0.818 (mean 0.830)—a 0.037 gap. If longer training lifts CoAtNet by even 0.015, the ensemble benefit multiplies (CoAtNet weight is 0.75 in r16).
- **Can 58-gold CV detect?** If the true gain is 0.03+, yes—30 repeated partition observations at SE ~0.015 give 2σ separation. If gain is 0.01–0.02, no.
- **Public LB trustworthy?** A 0.005–0.010 jump from one recipe change, confirmed in two independent runs with different seeds, would be >2σ evidence.
- **Verdict:** **Highest expected value.** The CoAtNet under-training is the single largest known inefficiency in your pipeline. The gain is likely in the detectable range (0.02–0.04), and if it materializes, it closes 25–50% of the frontier gap. Run 2 seeds at 6-epochs × BIG_FRAC=1.0; if seed-1 public submission exceeds r16 baseline by >0.005, seed-2 confirms.

## Plan D: Gold Upweighting / Two-Stage Training

**Design:** (D1) Add GOLD_UP=5 to current joint training; (D2) two-stage: train on pseudo-only 4 epochs, then fine-tune on 58 gold 2 epochs with frozen backbone; (D3) GOLD_UP=3 + pseudo-label confidence clipping (drop <0.15 confidence rows).

**Budget arithmetic:**
- D1: 1 run × 3.5 h = **3.5 h TPU** (no architecture changes).
- D2: 4 epochs pseudo + 2 epochs gold; pseudo phase = ~current CoAtNet cost × (4/4) × (1.0/0.5 assuming BIG_FRAC=1 for pseudo) = ~4.6 h. Gold phase: tiny (58 studies, <50 series) = negligible. Total: ~4.6 h + 1 h ResNet = **5.6 h TPU**.
- D3: same as D1 + label processing (CPU, free). **3.5 h TPU**.
- All fit within 16 h if D2+D3 prioritized.

**Expected gain and evidence basis:**
- Gold upweighting in a 58/4300 study regime: the ratio is 1:74. At GOLD_UP=5, gold gets 5/79 ≈ 6.3% of loss mass (vs 1.3% at GOLD_UP=1). For the ~12 positive examples per target, this is ~0.6 positive samples of influence. Meaningful only for targets with severe class imbalance or label noise.
- Two-stage: pseudo pretraining + gold fine-tuning is standard for few-shot medical. At 58 gold with 12 targets, you're fine-tuning ~4–5 positive examples per target per fold. This is extremely aggressive and prone to catastrophic overfitting.
- **Can 58-gold CV detect?** Two-stage has 19 gold for validation; the change is distributional (different loss weights), and the gain, if any, is likely 0.005–0.015 for a few targets (those with noisy pseudo-labels). Below the 0.03 detection threshold of repeated CV.
- **Public LB trustworthy?** Marginal. Need 3+ submissions showing consistent >0.003 gain.
- **Verdict:** Low priority. Two-stage overfitting risk is high with N=58; gold-upweight is a 1-line change but expected gain <0.005. Worth trying D3 (confidence clipping) as it costs CPU only, and noisy pseudo-labels could degrade CoAtNet training. Run D3 *after* Plan C if Plan C's longer training exposes label-noise artifacts (e.g., CoAtNet validation loss plateaus).

## Plan E: Additional Pseudo-Label Source Blending

**Design:** Merge tsuyu122 pseudo-labels with current LLM labels; evaluate agreement; keep studies where both sources agree; drop or downweight disagreements.

**Budget arithmetic:**
- Label processing, alignment, agreement scoring: **CPU only, ~2 h (free)**.
- Rerun training with filtered pseudo pool: depends on pool size reduction. If 20% dropped, training time drops proportionally: CoAtNet ~2.3 h → ~1.8 h (TPU). Total: **~2.8 h TPU**.
- **Fits budget** as a secondary experiment.

**Expected gain and evidence basis:**
- Label noise reduction can improve a model already at 2× over-parameterization (CoAtNet) by 0.01–0.03 for affected targets. The key insight: if tsuyu122 labels disagree with your labels on ~10% of studies, and those disagreements correlate with model errors, filtering recovers signal.
- **Can 58-gold CV detect?** No—the gain is target-specific and average <0.02.
- **Public LB trustworthy?** Yes if the effect is >0.005 and replicated. Label quality improvements tend to be robust (they reduce noise floor, not shift rank context). Two submissions with filtered labels >0.004 above baseline is believable.
- **Verdict:** Medium priority. CPU-only evaluation first: check agreement with your labels; measure prevalence shifts. If >8% rate difference on ≥3 targets, proceed to training run. Execute in parallel with Plan C decision-making (doesn't compete for TPU during evaluation).

## Plan F: More/Wider Views for CoAtNet (2.5D)

**Design:** For CoAtNet, use 5 slices instead of 3 (mid ± 1 → mid, ±1, ±2); or use 3 views per series as r13b did for ResNet (mid-sagittal, mid-coronal, mid-axial reconstructed).

**Budget arithmetic:**
- 5 slices = 5/3 × input volume size. CoAtNet ViT at 384 processes 5×224×224×3 → proportional compute increase ≈ 1.5–1.7×. Training time: 2.3 h → ~3.7 h (big_frac=0.5) or ~7.4 h (big_frac=1.0). With BIG_FRAC=1.0 and 6 epochs from Plan C: **~11 h for CoAtNet alone**.
- Total run: 11 h CoAtNet + 1 h ResNet = **12 h TPU**. Only one such run fits in 16 h.
- **Tight fit; precludes Plan C multi-seed.**

**Expected gain and evidence basis:**
- Pixel pitch at 384 is 0.339 mm, already Nyquist-resolving 1 mm tears (0.5 mm pitch required). Adding ±2 slices gives 1.7 mm context per side—useful for grading cartilage defects but marginal for acute meniscal tears.
- r13b’s 2-views@256 for ResNet: CV +0.009, public -0.003 vs 1-view@224. The delta was noise.
- Literature: 2.5D (5 slices) adds 0.01–0.02 for tasks requiring 3D context (e.g., ACL tear grading, where femoral/tibial attachment context matters).
- **Can 58-gold CV detect?** Likely not (0.01–0.02 < 0.03 threshold).
- **Public LB:** Would need 0.005+ to be credible; uncertain.
- **Verdict:** Do not pursue now. High compute cost, low expected gain relative to Plan C, and precludes Plan C's multi-seed confirmation. Revisit only if Plan C saturates and CoAtNet's under-training is resolved.

## Plan G: CoAtNet Frozen-Feature Heads (CPU Ensemble)

**Design:** Extract CoAtNet features from Plan C's best checkpoint; train lightweight MLP heads on CPU (r18-style); use as cheap extra ensemble members.

**Budget arithmetic:**
- Feature extraction (GPU): single forward pass on all series, ~30 min.
- Head training on CPU: 12 targets × 3 folds × ~1000 series features (dim ~1536) with 3-layer MLP, ~10 min total. **GPU: 0.5 h, CPU: free.**
- Inference: heads are tiny; add negligible time.
- **Trivially fits budget; near-zero cost.**

**Expected gain and evidence basis:**
- r18 frozen heads (ResNet features): r17 public 0.856 vs r12 public 0.865—the frozen-head addition was worth ≤0. Marginal diversity gain when base ensemble is already heterogeneous (CoAtNet + ResNet). Adding frozen CoAtNet heads to fine-tuned CoAtNet + ResNet adds near-zero diversity because features are identical to what the fine-tuned model already uses.
- You already fine-tune the CoAtNet; frozen heads on the same backbone are redundant. Literature: gains only when frozen model differs from fine-tuned (e.g., CNN features + ViT classifier).
- **Verd