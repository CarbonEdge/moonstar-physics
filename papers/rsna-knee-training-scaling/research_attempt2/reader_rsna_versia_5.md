## Analysis of `rsna-versia-5`

### 1. Headline claim and score
- **Claim:** The notebook reproduces and packages public solutions that evolved from **0.937 → 0.940 → 0.941 → 0.942 → 0.943** (macro-averaged ROC AUC over 12 findings). No independent score is reported for this specific notebook.
- **Highest reported score:** **0.943** (Work 5, `rsna-knee-fast-2xt4-inference`).

### 2. Every concrete technique (with numbers quoted exactly)

| Technique | Detail | Source (narrative / code) |
|---|---|---|
| **Architecture – CoAtNet arms** | Work 1: 4 arms (`v5`, `v10`, `v5‑reverse`, `v8`). Work 3: **residual‑g