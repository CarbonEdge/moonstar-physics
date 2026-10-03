# Research Synthesis: RSNA Knee Competition Public Solution Lineage (0.906 → 0.943)

## Classification of Sources

**Primary sources analyzed (5 notebooks):**
1. `bend-the-knee-to-dinov3-ensembled` — architecture narrative, no own score
2. `bend-the-knee-to-the-dinosaurs` — inference-only CoAtNet addition, reports upstream 0.943
3. `rsna-knee-baseline-v1` — foundation design, no score reported
4. `rsna-knee-fast-2xt4-inference` — packaged reproduction of 0.943 lineage
5. `rsna-knee-read-the-report-then-the-knee` — report-extractor foundation, verified 0.906
6. `rsna-versia-5` — external summary of the 0.937→0.943 progression

---

## 1. Lineage Graph

```
                    rsna-knee-baseline-v1 (foundation, no score)
                              │
                              ├──→ rsna-knee-read-the-report-then-the-knee (0.906 verified)
                              │         │
                              │         └──→ [report-extractor label machinery reused downstream]
                              │
                              └──→ prvsiyan 0.937 (CoAtNet 4-arm Raptor)
                                        │
                                        └──→ renta0426 0.940 (Lateral Meniscus routing)
                                                  │
                                                  └──→ Mattia Angeli 0.941 ("Bend the Knee to the Dinosaurs")
                                                            │
                                                            └──→ maverick_ss_26 0.942 (three hyperparameters)
                                                                      │
                                                                      └──→ Jiwei Liu 0.943 ("fast-2xt4-inference")
                                                                                │
                                                                                └──→ bend-the-knee-to-dinov3-ensembled
                                                                                      (overfit warning; no own score)
```

**Counting rule for evidence:** the incremental deltas 0.937→0.940→0.941→0.942→0.943 are each attributed to a *single* notebook's changes by the downstream authors, but no source provides a controlled ablation isolating any single change. `rsna-versia-5` is a secondary compilation and cannot be counted as independent confirmation.

---

## 2. Techniques by Frequency Across Sources

### Appear in 2+ independent sources:

| Technique | Occurrence | Independent? |
|---|---|---|
| Rank-mean ensembling (not probability mean) | baseline-v1, read-the-report, dinov3-ensembled | Yes — argued from AUC invariance |
| 130 mm constant crop / 336 px cache image | baseline-v1, read-the-report, knee-to-dinosaurs | Yes |
| Six anatomical slots (SAG/COR/AX × FS/NOFS × T1) | baseline-v1, read-the-report | Same author lineage |
| 224 px + 336 px dual resolution runs | baseline-v1, knee-to-dinosaurs, fast-2xt4 | Yes |
| 20 DINOv2 slot-attention models as base | read-the-report, knee-to-dinosaurs, dinov3-ensembled, versia-5 | Yes (same public weights, different authors) |
| Geometry-based slice ordering (k = p·n̂) | baseline-v1, read-the-report | Same author |
| Per-series percentile normalization (not per-slice) | baseline-v1, read-the-report | Same author |
| RadImageNet ResNet-50 heads | read-the-report, knee-to-dinosaurs, dinov3-ensembled, versia-5 | Yes (weights from marwanmath, heads from multiple authors) |
| CoAtNet adjacent-slice triplet (384 px) reader | knee-to-dinosaurs, fast-2xt4, versia-5 | Same model lineage |
| `raptor_k_eval=94` dense slice sampling | fast-2xt4, versia-5 | Same lineage |
| Grouped 3-slice stacks (GROUP=3, N_GROUP_MAX=1) | baseline-v1, knee-to-dinosaurs, fast-2xt4 | Yes |
| Augmentation: rot 8°, scale 0.08, shift 0.05, intensity 0.10 | baseline-v1, knee-to-dinosaurs, fast-2xt4 | Same author lineage |
| LR head 1e-3 / backbone 8e-6, unfreeze last 6 | baseline-v1, knee-to-dinosaurs | Same author |
| Epochs = 10, batch = 8 studies | baseline-v1, knee-to-dinosaurs | Same author |

### Appear in only one source:

| Technique | Source |
|---|---|
| DINOv3 ViT-S/16 added to 20 DINOv2 | dinov3-ensembled only |
| Nine-language rule extractor with graded scoring | read-the-report only |
| Per-finding confidence → sample weight | read-the-report only |
| OA inheritance / directional negation / synovitis backoff / unwrap | read-the-report only |
| Per-series type embedding (plane × fatsat) added to all tokens | dinov3-ensembled only |
| Twelve learned queries cross-attending over study tokens | dinov3-ensembled only |
| Key-padding mask (no imputation) | dinov3-ensembled only |
| Removing Synovitis/Lateral Meniscus report specialists | dinov3-ensembled only (via tonylica fork) |
| E13 heads fused at 0.50 rank into pinned v15 family | dinov3-ensembled only |
| E13 re-run on E11 slots at 0.15 second-pass blend | dinov3-ensembled only |
| Probability-space reduction (rank-of-mean-probabilities) | fast-2xt4, versia-5 (single change lineage) |
| Global96 top-3 / Repair-v1 top-3 | fast-2xt4, versia-5 (single change lineage) |
| Lateral Meniscus outer routing 0.00/1.00 Raptor-only | versia-5 only |
| `_dense_allocate` capacity-aware 94-window distribution | versia-5 only |
| GE Dixon fat/water detection fixing 37/4407 studies | versia-5 only |

---

## 3. Measured Ablations vs Assertions

### Ablations WITH numbers:

| Technique | Effect size | Source | Quality |
|---|---|---|---|
| RadImageNet ResNet-50 at 20% rank vote | +0.012 (0.894 → 0.906) | read-the-report | Direct run comparison, verified submission |
| Five-fold EfficientNet-B3 standalone | 0.898 (did not surpass) | read-the-report | Direct run comparison |
| FEATURES on/off table (unwrap, directional_negation, oa_inherit, graded_pathology, synovitis_backoff) | Changes in macro AUC + silence rate (numbers not quoted in summary) | read-the-report | Ablation table exists, but effect sizes not transcribed |
| Filename sorting vs geometry ordering | ρ ≈ 0.01 correlation | baseline-v1 | Measured degradation of naive approach |
| Parallel execution of CoAt readers | 155s → 69s, zero prediction change | fast-2xt4 | Speed only, not score |
| Removing Synovitis + Lateral Meniscus report specialists | "scored higher" — no delta | dinov3-ensembled (via tonylica fork) | Qualitative only, not author's own ablation |

### Assertions without ANY ablation in any source:

- CoAtNet 4-arm expansion (0.937) — no ablation
- Lateral Meniscus routing 0.00/1.00 (0.940) — no ablation
- Residual-gated CoAtNet at 0.40 inner blend (0.941) — no ablation
- Per-target routing ACL 0.75 / MedMen 0.80 / LatMen 1.00 / LatOA 0.75 / Fracture 0.75 — no ablation
- a5_w 0.45→0.52, rad_alpha 0.50→0.55, rad_second 0.15→0.20, raptor_k_eval 62→94 (0.942) — described as "three hyperparameters raised — no new models" implying causality, zero ablation in source
- 4-member CoAt family (Global96, Repair-v1 added) + probability-space reduction (0.943) — no ablation
- DINOv3 ViT-S/16 addition — no ablation, no score claimed
- All RadImageNet blend weights (0.50/0.50/0.15/0.20) — no ablation
- All augmentation values — no ablation
- All hyperparameter values (LRs, weight decay, unfreeze depth) — no ablation
- All slot design choices — no ablation

**Critical observation:** The score progression 0.937→0.940→0.941→0.942→0.943 is a *narrative*, not a controlled experiment. Each downstream notebook attributes the increment to its change, but:
- No notebook reports a fair A/B test (same seed, same data, one variable changed).
- Public LB noise is ~0.001–0.003 per the dinov3-ensembled author's own warning.
- The 0.002–0.003 increments (e.g., 0.941→0.942→0.943) are *within* what the most experienced author in this lineage calls "noise."
- The author of dinov3-ensembled explicitly states: "This notebook is now likely overfit to the public leaderboard" and "sub-resolution blend tweaks should be treated as noise."

---

## 4. Score Ladder and Step Attribution

| Score | Step | Attributed Change | Evidence Quality |
|---|---|---|---|
| 0.891 | Pilkwang V15 public anchor (20 DINOv2) | Base ensemble | External reference |
| 0.894 | V14: Fracture max + OOF target-wise rank blend | Report-extractor pipeline | Direct run comparison |
| 0.899 | V46: audited specialist artifact | Refinement of pipeline | Direct run comparison |
| 0.898 | V49: five-fold EfficientNet-B3 | Independent arm test | Direct run comparison |
| 0.906 | V52: + RadImageNet ResNet-50 at 20% | First independent model family added | **Verified submission** |
| 0.937 | prvsiyan: CoAtNet 4-arm expansion, global 0.60 | New architecture family | Narrative only |
| 0.940 | renta0426: Lat Meniscus routing 0/1 | Single-label routing | Narrative only |
| 0.941 | Mattia Angeli: residual-gated CoAtNet at 0.40, per-target routing | Another CoAtNet variant | Narrative only |
| 0.942 | maverick_ss_26: three hyperparameters raised | **No new models** — pure tuning | Narrative only, author of compiled lineage explicitly says "three hyperparameters raised — no new models" |
| 0.943 | Jiwei Liu: 4-member CoAt family, probability reduction | More CoAtNet variants | Narrative only |

**Key inference:** The jumps from 0.906 to 0.937 (+0.031) involve *new architectures* (CoAtNet family). The jumps from 0.941 to 0.943 (+0.002) involve *hyperparameter tuning and ensemble member addition within an already-saturated architecture family*. The 0.937→0.941 range additions are all CoAtNet-based, suggesting the CoAtNet reader itself (384px adjacent-slice triplets, finding-specific gated spatial head, study-level attention window pooling) is the single most important post-0.906 contribution.

---

## 5. Contradictions Between Sources

1. **Rank-space vs probability-space reduction:**
   - `baseline-v1` argues rank-mean is correct because "averaging ranks combines the only information the metric reads."
   - The 0.942→0.943 change explicitly switches CoAt family fusion from rank-of-mean-ranks to rank-of-mean-probabilities.
   - These are potentially contradictory; no source reconciles them.

2. **Overfitting assessment:**
   - `dinov3-ensembled` (same author family, most self-aware source): "This notebook is now likely overfit to the public leaderboard." "Sub-resolution blend tweaks should be treated as noise."
   - `rsna-versia-5` presents the 0.937→0.943 progression as a clean increasing sequence of "solutions."
   - These are directly contradictory framings of the same data.

3. **RadImageNet contribution:**
   - `read-the-report` shows RadImageNet ResNet-50 at 20% gives +0.012 over a 0.894 base (verified).
   - Downstream, RadImageNet is weighted at 0.50 rank into the pinned family, then 0.55, then 20% second-pass.
   - No source shows a controlled increase from 0.20 to 0.55, so whether the higher weight helped is unknown.

4. **The author identity:** `bend-the-knee-to-dinov3-ensembled` and `rsna-knee-fast-2xt4-inference` appear to be by the same user (rsna-knee-fast-2xt4-inference says "comes directly from Mattia Angeli's Speedy Raptors v34"). This means the strongest caveat about overfitting comes from the *same lineage* that produced the 0.943 score.

---

## 6. Attached Resources and Their Contributions

| Resource | Type | Contribution |
|---|---|---|
| Pilkwang's 20 DINOv2 slot-attention models | Public weights | Foundation: alone achieves 0.891. Contributes the base diversity to later ensembles. |
| tonylica's 4 DINOv2 models | Public weights | Adds diversity. Their specialists were *removed* (scored higher without them). |
| RadImageNet ResNet-50 weights (marwanmath) | Public pretrained | The only **verified** measurable contribution (+0.012 at 20% rank in early pipeline). |
| E9 RadImageNet Heads V15 (antoinegg1) | Public heads | Contribution unquantified; weights "pin" family structure. |
| CoAtNet MRI model (mattiaangeli) | Public weights | The 0.891→0.937 jump. Architecture described in detail; no ablation of its contribution vs DINO-only. |
| `rsna-knee-coatnet-global96-top3` | Public weights | Addition claimed for 0.943; no ablation. |
| `coatnet_pairfilm_manifest.json` | Manifest | SHA256 integrity check, not score. |
| Nine-language rule extractor | Inline code | Foundation for labels in read-the-report lineage. Ablation table exists (FEATURES on/off). |
| LM-model read labels table | Public dataset | Preferred when present over rule extractor. No independent evaluation. |
| `knee-mri-fold-weights` (DINOv3 member) | Public weights | Recommended by dinov3-ensembled as the only trustworthy addition (selected on held-out studies); no score or delta given. |

---

## 7. Ranked List: Techniques Most Likely Responsible for the 0.87→0.94 Gap

**The gap decomposition (inference, clearly separated from evidence):**

Given the sources, the gap from ~0.87 to ~0.94 decomposes roughly as:
- 0.87 → 0.891: base 20-model DINOv2 ensemble (evidence: stated as base; no ablation)
- 0.891 → 0.906: RadImageNet + report-extractor labels (evidence: verified +0.012 from RadImageNet at 20%; label machinery has ablation table)
- 0.906 → 0.937: CoAtNet architecture + diversity (evidence: narrative only)
- 0.937 → 0.943: ensembling/saturation/hyperparameter tuning (evidence: narrative only, author warning about overfit)

**Ranked techniques (inference from convergence of sources):**

1. **Heterogeneous model families** (DINOv2 + CoAtNet + RadImageNet + EfficientNet) — the single largest source of the gap. Each new architecture family added the largest increments. Rank-mean across genuinely different architectures is the dominant mechanism. *Supported by score progression structure, not ablation.*

2. **CoAtNet adjacent-slice-triplet reader with finding-specific gated spatial attention** — enabled the 0.906→0.937 jump, and every subsequent increment involved adding more CoAtNet variants. *Asserted in all sources, zero controlled ablation.*

3. **Label quality from nine-language rule extractor with graded scoring + per-finding confidence weights** — the early pipeline's ability to reach 0.906 depended on this. Has the strongest local ablation evidence (FEATURES on/off table), though raw effect sizes are not quoted in the synthesis sources. *Supported by ablation table existence.*

4. **RadImageNet ResNet-50 heads** — verified +0.012 at 20% blend early; its downstream weight inflation to 0.55 is unverified. *Partially supported.*

5. **Geometry-based preprocessing** (slice ordering from DICOM geometry, constant physical crop 130mm, per-series percentile normalization, 336px resolution) — consistently present across all sources, theoretically justified by Nyquist argument (1mm meniscal tears require ≤0.5mm pitch), and the naive alternative (filename sorting) is measured as ρ≈0.01. *Supported by measurement of the failure mode it fixes, not by score ablation.*

6. **Hyperparameter tuning within architecture families** (a5_w, rad_alpha, raptor_k_eval, per-target routing weights) — the 0.941→0.943 region. The most experienced author in the lineage explicitly labels this as noise overfitting. *Asserted only; actively warned against by one source.*

7. **DINOv3 addition** — recommended as trustworthy (held-out selection), but no score or delta provided in any source. *Unquantifiable from available evidence.*

8. **Removal of report/metadata specialists** — weakly supported (fork result, qualitative, no delta). *Directional only.*

---

## 8. Overall Evidence Quality Assessment

| Claim type | Number of techniques | Evidence level |
|---|---|---|
| Verified (measured, controlled) | 1 (RadImageNet at 20% early) | +0.012 |
| Supported (measured, but uncontrolled or single-source) | 2 (label extractor ablations, geometry vs filename) | Directional |
| Narrative-only (score ladder attribution) | 8+ (all CoAtNet additions, all blend weights, all hyperparameters) | None |
| Actively warned against by source author | 2 (sub-resolution blend tweaks, specialist removal) | Negative |

The most striking finding: **the score progression 0.937→0.943 has zero controlled ablation evidence across five analyzed sources.** It is a lineage of incremental ensemble additions and weight changes where the 0.002–0.003 increments are within the public leaderboard noise band acknowledged by the most experienced author in the lineage. The only large, verified contribution in the entire corpus is the RadImageNet ResNet-50 at 20% rank (+0.012), measured in a controlled run comparison. Every other technique is asserted by narrative attribution.