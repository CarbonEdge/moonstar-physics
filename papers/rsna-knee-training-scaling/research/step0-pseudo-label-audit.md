# Step 0: pseudo-label audit against the 58 gold studies (2026-10-03, CPU)

Teacher = the label tables used as training targets, scored against gold (>=0.5 binarisation, 58 studies).
Caveat: the v4 blend was selected using these same 58 gold studies, so its AUC is slightly optimistic.

| Finding | pos/58 | v4 blend AUC | prec@.5 | rec@.5 |
|---|---|---|---|---|
| ACL | 24 | 0.987 | 0.79 | 0.96 |
| MCL | 9 | 0.968 | 0.56 | 1.00 |
| Medial Meniscus | 26 | 0.948 | 0.82 | 0.88 |
| Lateral Meniscus | 23 | 0.879 | 0.82 | 0.78 |
| Medial OA | 15 | 0.932 | 0.67 | 0.93 |
| Lateral OA | 11 | 0.833 | 0.53 | 0.82 |
| PF OA | 21 | 0.902 | 0.68 | 0.81 |
| Effusion | 35 | 0.877 | 0.69 | 1.00 |
| Synovitis | 27 | 0.790 | 0.76 | 0.48 |
| Baker's | 12 | 0.944 | 0.69 | 0.92 |
| Contusion | 19 | 0.860 | 0.57 | 0.84 |
| Fracture | 18 | 0.793 | 0.67 | 0.78 |
| **mean** | | **0.893** | | |

Other tables on the same studies: llm_labels_full 0.878, report_labels_v2 0.870.

## Findings
1. **The label teacher's own AUC on gold (0.893) is about equal to our best student (r16 CV 0.878).** A student trained on a noisy teacher is bounded near the teacher unless it sees images the teacher didn't (it does, hence not far below) -- label quality is a ceiling for our own members.
2. **Weakest findings:** Synovitis (0.79, recall 0.48), Fracture (0.79), Lateral OA (0.83), Contusion (0.86), Effusion (0.88).
3. **The decision-doc hypothesis "effusion labels are false-negative heavy" is FALSE:** effusion recall is 1.00; its problem is precision 0.69 (false positives). Synovitis is the one with a recall problem (0.48).
4. Gold-vs-pseudo agreement is high enough that more own-model epochs help less than ensembling with differently-supervised public models (their labels/images differ), supporting the hybrid plan.
