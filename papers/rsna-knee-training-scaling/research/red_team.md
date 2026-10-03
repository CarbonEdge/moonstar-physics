# Attack on the Three Expert Drafts (Cross-Source Synthesis as Evidence Base)

---

## ATTACK ON GRANDMASTER'S PLAN

### Claim 1 (Expected Score Ranges)

> **"Path (b): Retrain Our Own Members... Expected public score range: 0.885–0.905"**
> **"Path (c): Hybrid Rank-Blend... Expected public score range: 0.920–0.932"**

**Why it fails:** These expected ranges are fabricated. The cross-source research synthesis explicitly states the frontier progression 0.937→0.943 has *zero controlled ablation evidence* across five analyzed sources, and the lineage author calls sub-resolution blend tweaks "noise." If we cannot trust the frontier's 0.002–0.003 increments, we certainly cannot project our own scores to ±0.005 precision from a baseline of 0.865. The only verified contribution in the entire corpus is RadImageNet +0.012 at 20% rank. Extrapolating from one verified data point to predict multi-component ensemble scores is speculation dressed as computation.

**Repair:** Replace point estimates with probability ranges anchored to the one verified ablation: "If our best model reaches 0.89 (CoAtNet fully trained, +0.02–0.04 from under-training fix), and we obtain public weights at 0.93–0.94, the rank-mean of N models with correlation ~0.7 gives blended score approximately 0.91–0.93, with uncertainty ±0.02." Acknowledge that the 0.865→0.920 gap decomposes into known (~0.03–0.04 from CoAtNet training) and unknown (public weight availability, ensemble diversity bonus, LB overfitting penalty) components.

---

### Claim 2 (Blend Weight Selection)

> **"Use public LB as the blend weight selector, not 58-gold CV. Submit 3-4 candidate blends... Pick the highest public score."**

**Why it fails:** This is public-LB overfitting risk in its purest form. The cross-source synthesis identifies the same pattern in the 0.942→0.943 progression: "three hyperparameters raised — no new models," which the experienced lineage author calls "noise." The grandmaster's proposal selects 1 of 4 candidates based on one submission each against σ≈0.003 LB noise. At 4 candidates, the expected maximum of 4 independent N(0, 0.003) draws is ~+0.003 above truth—exactly the overfitting mechanism warned against. On a private test 3× larger, this gain reverses to expected -0.003 to -0.005.

**Repair:** Fix the blend weight a priori using only architecture-count heuristics: (our distinct families) / (total distinct families). If we contribute 2 genuinely distinct models (CoAtNet + ResNet/EfficientNet) and download 3 families (DINOv2, CoAtNet, RadImageNet), our weight = 2/5 = 0.40, capped at 0.35 for conservatism. Do not tune this number. If public LB selection is used, require Bonferroni correction: to select 1 of 4 candidates with 95% confidence against σ=0.003, need a gap ≥ 0.003 × z(0.05/4) ≈ 0.008 between best and second-best. Any selection below this threshold is a random draw from the noise distribution.

---

### Claim 3 (Budget Allocation Table)

> *Phase validation: TPU 3.5h, GPU 1h; If GO: TPU 10.5h; Ensemble inference: GPU 8h; If NO-GO: GPU 12h; Buffer: TPU 2h, GPU 9h*

**Why it fails:** Budget arithmetic error. The grandmaster claims 16h TPU total: 3.5 + 10.5 + 2 = 16h. But 3.5 + 10.5 = 14h, leaving 2h buffer → correct. However, the "If NO-GO" path specifies *no additional TPU runs* (0h), yet the total table claims 16h TPU used. This is an accounting contradiction: either the budget is exhausted or it isn't. More critically, the GPU budget says "≤21h" but the NO-GO path says GPU 12h while the GO path says GPU 8h + 1h validation = 9h. The table's own numbers sum to ≤21h against a 30h budget—9h slack—but the grandmaster doesn't allocate this slack to anything useful (e.g., additional inference diversity experiments, public-weight validation on pseudo-heldout, or submission iteration overhead).

**Recomputation:**
- GO path: validation 3.5h TPU + remaining 3 runs @3.5h = 14h TPU total. GPU: 1h (validation) + 8h (inference) = 9h.
- NO-GO path: validation 3.5h TPU + 0h additional TPU = 3.5h TPU total. GPU: 1h + 12h = 13h.
- The NO-GO path leaves 12.5h TPU idle. This slack should be explicitly allocated to fallback experiments (e.g., Plan C with different seeds, or GOLD_UP/confidence clipping experiments).

**Repair:** Specify what happens with unused TPU hours in each branch. If validation fails → pivot immediately, use remaining 12.5h TPU for controlled ablations of the single most promising remaining lever (pseudo-label quality filtering, Plan E). If validation succeeds → the 2h TPU buffer is genuine slack for OOM/debugging.

---

### Claim 4 (DINOv2 Training from Scratch)

> **"Train 1 DINOv2 slot-attention model at 336px (from scratch, using the rsna-knee-baseline-v1 recipe adapted to our data) → new architecture family we own"**

**Why it fails:** Integrity/compliance concern: reusing public work without attribution. The "rsna-knee-baseline-v1" recipe + 20-model DINOv2 ensemble is Pilkwang's creation (the 0.891 base). "Adapting" this to our data and calling it "new architecture family we own" is derivative work. The cross-source synthesis identifies Pilkwang's 20 DINOv2 models as the foundation of the entire lineage. Reproducing their exact architecture and training pipeline on our pseudo-labels produces a model that is architecturally identical to public weights but trained on different labels—this is not a "new architecture family," it's a data-variant of an existing public family. True architectural novelty would require a different backbone (e.g., DINOv2-registers, ViT with different patch size, Swin Transformer), different slot design, or different attention mechanism.

**Repair:** Be explicit: "We retrain Pilkwang-style DINOv2 slot-attention on our pseudo-labels. This gives us the same architecture as public DINOv2 but with different label-induced biases, providing correlation <1.0 with public DINOv2 predictions." Do not claim architectural novelty; claim data-diversity novelty. If compliance/rules permit using others' architectures with attribution, proceed. If not, substitute EfficientNet-B3 (verified as standalone arm in read-the-report lineage) or a ViT-B/16 from scratch without slot-attention.

---

## ATTACK ON RADIOLOGIST'S ANALYSIS

### Claim 1 (Finding-by-Finding Loss Ranking)

> **"Ranked expected loss (gap to frontier) by finding: Lateral Meniscus Tear 0.08-0.12, Medial Meniscus Tear 0.06-0.10, Lateral Cartilage 0.06-0.09..."**

**Why it fails:** These loss estimates are unsupported by any measurement. The cross-source synthesis contains exactly zero per-finding AUC breakdowns from the frontier lineage. We don't know the frontier's per-finding performance. Our own per-finding AUCs (from r16 CV) are confounded by 58-gold noise (per-finding SE ~0.10–0.20) and pseudo-label quality variance. The radiologist's reasoning from physiology is sound directionally, but quantifying gaps to 0.01 precision without a single data point is physiologically-informed guesswork, not evidence.

**Repair:** Replace numerical loss estimates with ordinal rankings anchored to measurable proxies: (1) CV per-finding AUC vs ensemble mean (available from r16 OOF predictions), (2) inter-fold variance per finding (high variance = model confused = likely physiology-limited), (3) pseudo-label confidence distributions per finding (low confidence on negatives for cartilage/effusion → label noise). Report: "Lateral Meniscus has lowest CV AUC and highest fold variance → likely highest true loss. Cartilage and Effusion have lowest pseudo-label confidence on negatives → likely under-labeled → models trained to be false-negative-biased." No numbers without measurements.

---

### Claim 2 (Multi-Series Input as Highest ROI)

> **"A. Multi-series input (HIGHEST ROI)... Select three series with explicit type routing: Sagittal FS, Sagittal non-FS, Coronal FS."**

**Why it fails:** Contradiction with their own Loss Ranking table. The table says meniscal tears (ranked #1-2 loss) require coronal confirmation, cartilage (#3-4) requires coronal, and ACL (#5) requires sagittal FS. But the proposed change selects *three series* from *potentially the same study that currently has only one sagittal series in the pool*. Our pseudo-labeled studies have variable DICOM completeness. The radiologist assumes all planes and FS combinations are present. The cross-source synthesis notes that the frontier lineage uses "six anatomical slots (SAG/COR/AX × FS/NOFS × T1)" and a complex slot-allocation architecture. We don't have that infrastructure. Proposing "select three series with explicit type routing" without first auditing how many studies actually have sagittal FS + sagittal non-FS + coronal FS is architecturally valid but operationally unvalidated.

**Repair:** Before implementing multi-series, audit our 4,349-study pseudo pool for DICOM series availability: what fraction of studies have ≥1 sagittal FS? ≥1 coronal FS? ≥1 sagittal non-FS? All three? If <50% of studies have all three, the routing logic degrades to "use what's available" and the physiological benefit is diluted. This audit is CPU-only and takes ~30 minutes parsing DICOM headers. Report the availability matrix, then decide whether multi-series is highest ROI or whether fixing single-series sampling (wider slice coverage, Plan F variant) is more universally applicable.

---

### Claim 3 (Label Noise by Finding)

> **"Effusion: Report Sensitivity Low (described only if clinically relevant), Report Specificity High. False negatives: 'small/trace effusion' often omitted."**

**Why it fails:** Unsupported claim about report content. The cross-source synthesis's read-the-report notebook uses a "nine-language rule extractor with graded scoring" and has "FEATURES on/off" ablation tables. It does not report per-finding sensitivity/specificity vs ground truth. The radiologist's claim that radiologists "never miss fractures" (sensitivity very high) and "often omit trace effusion" (sensitivity low) is plausible clinical knowledge but not grounded in our actual label extractor's behavior or the RSNA annotation protocol. The RSNA task may define "effusion = yes" at a different threshold than clinical reporting.

**Repair:** Audit our pseudo-labels against the 58 gold labels, per finding. Compute: precision = P(gold=1 | pseudo=1), recall = P(pseudo=1 | gold=1), F1 per finding. This is exactly 58 samples × 12 findings = 696 binary comparisons, CPU-only, immediate. The recall for effusion/cartilage will be low if the "radiologists omit mild findings" claim is true. If recall <0.5 for effusion, the label-noise mechanism is confirmed and label confidence downweighting on negatives (their suggestion E) becomes actionable with measured parameters, not assumed ones.

---

## ATTACK ON STATISTICIAN'S ANALYSIS

### Claim 1 (Repeated CV Detectability Threshold)

> **"10 distinct 3-fold partitionings... 30 observations per configuration... Operational SE on 30 correlated observations ≈ 0.015–0.02 for AUC, meaning a 2-sigma detectable effect is ~0.03–0.04."**

**Why it fails:** The operational SE estimate is unsupported. Correlated CV folds violate independence assumptions. The statistician states "30 correlated observations" but does not estimate the intra-cluster correlation (ICC) that determines the effective sample size. If 10 partitionings of the same 58 studies produce folds with high overlap (each study appears in validation ~10/3 ≈ 3.3 times across partitionings), ICC could be 0.3–0.5, making effective N = 30 / (1 + (3.3–1)×ICC) ≈ 12–18. The SE on 12–18 correlated observations could be 0.025–0.035, pushing 2σ detectability to 0.05–0.07. The statistician's 0.03–0.04 threshold is optimistic and not derived from our data.

**Repair:** Run a simulation: take the r16 OOF predictions (which exist now), resample 10 partitionings with replacement, compute the standard deviation of the mean AUC across partitionings. This gives an empirical estimate of σ_partitioning. Multiply by 2 for the 2σ threshold. This takes 5 lines of Python on CPU, uses existing data, and replaces assumption with measurement.

---

### Claim 2 (Plan C Budget Arithmetic)

> **"Current r16 CoAtNet: ~2.3 h for 3 folds, 4 epochs each, BIG_FRAC=0.5 → total CoAtNet compute ≈ 2.3 h. With BIG_FRAC=1.0, per-epoch compute doubles (2× rows). At 6 epochs: 2.3 × (6/4) × (1.0/0.5) = 2.3 × 1.5 × 2 = 6.9 h for CoAtNet alone. Total run: ResNet50 (1 h) + CoAtNet (6.9 h) = 7.9 h TPU."**

**Why it fails:** Budget arithmetic error: double-counting the BIG_FRAC factor. The r16 CoAtNet at 2.3h for 3 folds × 4 epochs at BIG_FRAC=0.5 means per-epoch per-fold time = 2.3 / (3 × 4) = 0.192h at BIG_FRAC=0.5. At BIG_FRAC=1.0, per-epoch per-fold = 0.192 × 2 = 0.383h. For 6 epochs over 3 folds: 3 × 6 × 0.383 = 6.9h. This arithmetic is correct. BUT: the TPU budget is 16h, and the statistician says "Fits in 16h with room for exactly 2 runs (15.8h)." 2 × 7.9 = 15.8h, leaving 0.2h for ResNet50 × 2 = 2h → total 17.8h, NOT 15.8h. The ResNet50 component (1h per run) was omitted from the 2-run calculation.

**Recomputation:**
- One full run: ResNet50 1h + CoAtNet 6.9h = 7.9h
- Two runs: 2 × 7.9 = 15.8h
- **Total TPU: 15.8h, fits in 16h with 0.2h margin (not 2h).**
- Three runs: 23.7h — impossible.

**Repair:** Plan C allows exactly 2 runs at 6 epochs × BIG_FRAC=1.0,