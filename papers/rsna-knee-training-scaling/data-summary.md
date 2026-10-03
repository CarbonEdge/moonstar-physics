# RSNA Knee Abnormality Detection — empirical data summary (rounds 5–21, updated 2026-10-03)

Source: `moonstar-kaggle/runs/rsna-knee-abnormality-detection/` + Kaggle submissions API (pulled 2026-10-03).
Gold labels: **58 studies**. Pseudo-labels (LLM-derived from reports): **4,349 studies** (+ 22.8k-series pool from r12).
Metric: mean AUC over 12 targets. CV = local, on the 58-gold set (noise ≈ ±0.01).

## 1. Results table

| Round | Date | Change vs previous | Local CV | Public | Compute |
|---|---|---|---|---|---|
| r1 | 08-16 | baseline | – | 0.517 | – |
| r5 | 09-26 | offline resnet18 + 4349 LLM pseudo-labels | 0.60 (15 gold) | 0.667 | – |
| r6 | 09-26 | RadImageNet r50 + 3-fold + 2 label sources | 0.657 | 0.687 | – |
| r7 | 09-27 | **DICOM geometry fixes** (slice order, physical crop, laterality) | 0.759 | 0.811 | – |
| r8 | 09-27 | per-target confidence-weighted BCE, 700 studies | – | 0.815 | – |
| r12 | 09-30 | decode-once RAM cache, **full pseudo pool** | 0.832 | **0.865** | GPU, ~21 min decode + 104 s/epoch |
| r13b | 09-30 | 2 views/series, 256 px, 10 epochs | 0.841 | 0.862 | GPU |
| r14 | 09-30 | CoAtNet at 224 px (wrong res) | 0.769 | not submitted | GPU ~4 h |
| r17 | 10-01 | frozen-feature heads: raptor+concat+resnet | 0.825 | 0.856 | CPU |
| r18 | 10-02 | same, 6 folds, 4 series/pseudo study | 0.828 | not submitted | CPU ~5.3 h |
| **r16 TPU** | 10-02 | **raptor CoAtNet @384 fine-tuned + r50 @224, 3-fold** | **0.878** | **not yet submitted** | TPU v-8 (torch_xla 2.8), 2.3 h/CoAtNet member |

## 2. Per-member evidence

- r16 TPU folds: ensemble 0.909 / 0.876 / 0.848. CoAtNet-raptor 0.897 / 0.855 / 0.848; ResNet50-RadImageNet 0.797 / 0.874 / 0.818. Learned weights 0.75 / 0.25.
- r18 (frozen features + trained heads): resnet 0.661, raptor 0.829, concat 0.812; blend weights 0.11 / 0.47 / 0.42.
- raptor checkpoint = `coatnet_rmlp_2_rw_384.sw_in12k_ft_in1k`, native 384 px, gold AUC 0.917 on its original task. At 224 px: 0.61–0.77 (r14).
- Frozen raptor features (r18, 0.829) < fine-tuned raptor (r16, ~0.867 mean) — fine-tuning at native res adds ≈ +0.04.

## 3. Observed effects (what moved the number)

| Intervention | Effect | Evidence |
|---|---|---|
| Fix input geometry (slice order, mm-scale crop, laterality) | **+0.12 public** | r6→r7 |
| Pretraining domain (ImageNet r18 → RadImageNet r50) | ≈ +0.02 | r5→r6 (confounded with 3-fold) |
| Label count 700 → ~4.3k+ → 22.8k-series pool | +0.05 public | r8→r12 |
| Per-target confidence weighting | small | r8 |
| Views 1→2, 224→256 px, 6→10 epochs | CV +0.009, public −0.003 | r12→r13b (within noise) |
| Weight-averaging last epochs | −0.010 CV | r12 ablation |
| Flip TTA | ≈ 0 | |
| Strong pretrained backbone at **native** res | ≈ +0.04 CV over frozen raptor, ≈ +0.035 over r12 (different folds) | r16 vs r18/r12 |
| Same backbone at wrong res (224 vs 384) | member AUC 0.61–0.77 vs 0.917 on the checkpoint's own task | r14 |
| Frozen-feature heads (cheap) vs full fine-tune | −0.01 public, ~free compute | r17 vs r12 |
| Silent data-path fallback (58 gold only) | training on 58 studies | r10 |

## 4. Systematic biases

- Local CV under-predicts public: 0.832→0.865 (+0.033), 0.841→0.862 (+0.021), 0.825→0.856 (+0.031). Ratio unstable; ordering of CV across r12/r13b/r17 does **not** match public ordering.
- CV set (58 gold) is ≈ 1/75 of the pseudo pool; fold AUC spread inside one run is 0.06 (r16) to 0.26 (r14).
- Pseudo-label noise is unmeasured beyond the 58-gold check.

## 5. Compute facts

- GPU quota 30 h/week; TPU 16–20 h/week; CPU free (≈ 5 h per frozen-feature round).
- Decode (DICOM → RAM) is the fixed cost: ~21 min once, shared across epochs/folds.
- TPU: 8 devices visible, XLA world size 1 (single-process); CoAtNet@384 first epoch 693 s; r50@224 206 s.
- GPU CoAtNet@224 ≈ 4 h but wrong resolution — wasted.

## 6. Open questions (data cannot yet answer)

1. Is the 0.878 CV of r16 real or fold luck (spread 0.848–0.909)? Public score pending a submit.
2. Scaling exponent in label count: only two points (≈4.3k vs ≈22.8k series) with other changes mixed in.
3. Whether the gain is from model capacity, resolution, or domain-matched pretraining (r16 changes all three vs r12).
4. Ceiling set by pseudo-label noise vs by model.


---
# UPDATE 2026-10-03 (later in the day): what happened after the first summary

## 7. Leaderboard and the frontier
- Leaderboard top now **0.961** (ranks 1-15 span 0.958-0.961). Our best public: **0.865** (r12). Top public notebooks in the shared pool: 0.937-0.943.
- Frontier recipe (6 public notebooks read by the moonstar research pipeline): rank-averaged ensembles of many public members (20 DINOv2 + DINOv3, 4 CoAtNet arms, RadImageNet heads, A5 attention pooling), slot-based study-level inputs, dense slice sampling, per-finding routing weights. Only one step has a quoted ablation (RadImageNet 20% rank vote ~ +0.012); the 0.937 -> 0.943 ladder steps are documented, but authors call sub-0.003 changes noise.

## 8. Scoring constraint discovered
- The scoring rerun **cannot use TPU** ("Your Notebook cannot use TPU in this competition"). r16 TPU (CV 0.878) saved no weights, so it cannot be submitted as is.
- Fix: train on TPU, save weights, score on GPU from a weights dataset (r19 train / r19 infer, `make_r19.py`).
- Kaggle allows only **1 TPU batch session** at a time. r19 has been QUEUED for many hours and blocks r20.

## 9. Runs and submissions since the first summary
| Item | What | Status / result |
|---|---|---|
| **pub943** | unmodified reproduction of jiweiliu/rsna-knee-fast-2xt4-inference (0.943 public), GPU | ran OK; **submitted, ref 56797053, PENDING** (no score yet) |
| r19 train | r16 recipe + saves per-fold weights (TPU) | QUEUED |
| r19 infer | loads weights on GPU, test-only | built, untested |
| r20 train | r19 + 28 auxiliary concept heads (AUX_W=0.15, ~31% of total loss weight) from LLM-extracted report attributes | built, local data dry-run passed; **push blocked** (TPU session limit) |
| r20 infer | as r19 infer with aux-head slicing | built, untested |
| r21 | public DINO-V5 + meniscus-specialist notebook (0.943 base + public0033 Medial Meniscus at 10%), demo-study swap removed, empty overlay stage for our own members | pushed to GPU, RUNNING; not submitted |

## 10. Pseudo-label audit vs 58 gold (Step 0)
Teacher AUC on gold (v4 blend): mean **0.893**; ACL .99, MCL .97, Medial Meniscus .95, Baker's .94, Medial OA .93, PF OA .90, Lateral Meniscus .88, Effusion .88, Contusion .86, Lateral OA .83, Fracture .79, Synovitis .79 (recall 0.48). Other tables: llm_labels_full .878, report_labels_v2 .870. The v4 blend was chosen using the same gold, so it is slightly optimistic.
- Our best student (r16 CV 0.878) is about the teacher: **labels cap our own models**.
- Effusion's problem is precision (0.69), not recall (1.00); synovitis is the recall problem.

## 11. LLM attribute extraction (report text only, never images)
- 4,404 of 4,407 reports turned into structured attributes (fracture type/location, contusion severity/location, synovitis extent, effusion size, lateral-OA grade, lateral-meniscus tear type/location) with deepseek-v4-flash via OpenRouter; ~3.6M input / 0.9M output tokens (~$1). Dataset `joe1dataset/rsna-knee-attrs` (private, CC0), 28 aux targets.
- **Pilot result (58 gold): the extracted attributes do NOT beat the existing labels as labels** (AUC vs gold: Fracture .806 vs .793; Contusion .67-.70 vs .86; Synovitis .70 vs .79; Effusion .83 vs .88; Lateral OA .82 vs .83; Lateral Meniscus .82-.84 vs .88). Within noise at best. Their only value is as auxiliary training targets in r20 (untested).

## 12. Moonstar research outputs (this repo)
`research/decision.md` (+ reviewer corrections), `research/step0-pseudo-label-audit.md`, `theory.md`, `sources/` (digests of public notebooks), `variant-planning-context.md`. Pipeline lessons: reasoning models burn max_tokens on hidden thinking -> use `reasoning: {enabled: false}`; gateway spec limit is 64 KB (pass bulk text as initial_input).
The decision doc's verdict (own-model path, 0.885-0.91) was overridden: the frontier is reachable by attaching public weights (14 free datasets). The user chose the hybrid.

## 13. Statistics that govern decisions
Hanley-McNeil SE of one finding's AUC on 58 studies: 0.042 (prev .5, AUC .9) to 0.197 (n=19, prev .1, AUC .8). CV differences below ~0.03 are not resolvable; the CV -> public gap is +0.02 to +0.033 with unstable ordering. Do not tune blends on gold or on the public LB (an author reports 0.906 -> 0.887 after label-wise selection).

## 14. External assets reviewed (see `moonstar-kaggle/runs/rsna-knee-abnormality-detection/PROVENANCE.md`)
Used (CC0 unless noted): pilkwang/stevenleehans labels, dreaddevelopment raptor, mattiaangeli weights. **Non-commercial:** RadImageNet weights/heads (CC-BY-NC-SA-4.0); our ResNet50 member derives from them. Reviewed, not applicable: CT/PET datasets, LegSegNet (CT, CC BY-NC), kneeseg (RF cartilage), MRNet (ACL/meniscus only; terms unchecked).
