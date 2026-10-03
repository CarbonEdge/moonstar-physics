# Analysis of `rsna-versia-5`

## Headline claim / score
- The notebook is a **repackaging/reproduction** of five public solutions, not a new method: quote — *“All models, weights, and pipelines below are public work by other authors. We reproduced them one-to-one and packaged them into a single notebook.”*
- It lists the public leaderboard progression: **“0.937 → 0.94 → 0.941 → 0.942 → 0.943”**, attributed to five external notebooks. It does **not** state its own submitted score.
- Task framing: macro-averaged ROC AUC over 12 labels; reports are available only at training time.

## Concrete techniques and numbers (by source work)

### Work 1 — 0.937
- CoAtNet branch expanded to **4 arms: v5, v10, v5-reverse, v8**.
- Reverse-flip is used as **diversity without new training** (a form of TTA).
- Outer CoAtNet weight becomes **global 0.60** instead of per-target.
- Confidence: **ASSERTED** for score contribution; no isolated ablation.

### Work 2 — 0.94
- Starts “from the exact 0.939 parent (reproduced 1-to-1)”.
- Only **Lateral Meniscus** rerouted: **Transformer/Rad 0.00 / strengthened Raptor 1.00**.
- Other 11 labels remain at **0.40 / 0.60**.
- Confidence: **ASSERTED**; no ablation in this source.

### Work 3 — 0.941
- Keeps 4-arm Raptor; adds **residual-gated CoAtNet (e4/e6/e8)** inside the Raptor branch.
- Inner blend: **public Raptor 0.60 / residual-CoAt 0.40**.
- New CoAtNet MRI reader: **384 px adjacent-slice triplets → CoAtNet RMLP-2 backbone**; finding-specific gated spatial head + second attention stage pooling windows.
- CoAtNet arm weights: **