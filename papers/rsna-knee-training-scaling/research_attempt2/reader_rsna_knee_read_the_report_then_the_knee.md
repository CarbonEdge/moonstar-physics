**Headline claim and score**  

- **Headline claim:** "Highest verified public score for this notebook: **0.906**."  
- **Version/evidence:** Version 52, Kaggle submission 55399732; artifact "bitwise matched to the audited 20% RadImageNet rank blend."  
- Earlier verified runs: V14 → 0.894, V46 → 0.899, V49 → 0.898 (five‑fold EfficientNet‑B3), external Yash Bishnoi reference → 0.903.  

---

**Every concrete technique with numbers given**  

**Input design**  
- 6 anatomical slots: `SAG_FLUID_FS, COR_FLUID_FS, AX_FLUID_FS, SAG_FLUID_NOFS, COR_T1, SAG_T1`.  
- Per‑slot presence mask carries absences into head.  

**Slice count & resolution**  
- `GROUP = 3` (three adjacent slices stacked as three channels).  
- `CACHE_IMG = 336` (image size for the cache; RUNS also list r224 with `img` 224).  
- `CROP_MM = 130.0` (fixed physical crop, resampled to `P` pixels → effective pixel pitch = 130/P).  
- `SLICE_BAND = (0.20, 0.80)` (fraction of ordered stack sampled).  

**Preprocessing**  
- DICOM geometric sorting: order by `k = p · n̂` where `n̂ = r̂x × r̂y`; fallback `InstanceNumber`.  
- Laterality: from `Laterality` tag or from geometry (median X‑coordinate).  
- Intensity: normalised to 1st–99th percentile over the sampled stack (per series, not per slice).  
- Report text: NFKD normalisation, unwrap (if `FEATURES['unwrap']`), clause splitting, negation window `NEG_WINDOW = 90`.  

**Label handling (report reader)**  
- Nine‑language rule extractor; no language identification, all cues pooled.  
- Graded (not binary): score formulas e.g. `min(0.97, 0.50 + 0.45 * best + 0.015 * min(n_pos, 3))`, confidence `min(1.0, 0.55 + 0.15 * n_pos)` for positives; for negatives `score = max(0.04, 0.20 - 0.04 * n_neg)`, `conf = min(0.9, 0.45 + 0.12 * n_neg)`.  
- Binary targets (for validation only): binarised at midpoint (>0.5).  
- Sample weight from `conf` (confidence per finding).  
- `FEATURES = {'unwrap': True, 'directional_negation': True, 'oa_inherit': True, 'graded_pathology': True, 'synovitis_backoff': True}`.  
- Decoy patterns for Fracture and Baker's cyst; paired anatomy targets: ACL, MCL, Medial/Lateral Meniscus; OA targets: Medial OA, Lateral OA, PF OA.  

**Loss** – not explicitly stated in narrative; code shows no loss definition.  

**Architecture**  
- “Pure imaging model” with RadImageNet ResNet‑50 encoder. (V49 also tested five‑fold EfficientNet‑B3.)  
- Three “arms” combined via rank averaging.  

**Aggregation / blending**  
- **Rank averaging** (not probability averaging) used for all combinations.  
- V52: “independent RadImageNet ResNet‑50, **20% rank vote**” – the RadImageNet arm contributes 20% weight in the rank blend.  
- V49: five‑fold EfficientNet‑B3 “rank contribution” (no weight given).  
- Earlier versions (V14, V46) used “OOF‑selected target‑wise rank blend” and “exact audited specialist artifact”.  

**Training hyperparameters** (from code)  
- `SEED = 2026`  
- `EPOCHS = 10`  
- `BATCH_STUDIES = 8`  
- `LR_HEAD = 1e-3`, `LR_BACKBONE = 8e-6`  
- `UNFREEZE_LAST = 6` (trainable transformer blocks from output end)  
- `WEIGHT_DECAY = 0.02`  
- `AUG_ROT_DEG = 8.0`, `AUG_SCALE = 0.08`, `AUG_SHIFT = 0.05`, `AUG_INTENSITY = 0.10`  
- `SLOT_PRIOR_STRENGTH = 0.55`  
- `TIME_BUDGET = 8.0 * 3600` seconds  

**Test‑time augmentation (TTA)** – none mentioned.  

---

**Any ablation or measured effect size, quoted**  

- **V49 score 0.898** *“independently tested the five‑fold EfficientNet‑B3 contribution at 0.898.”* → the EfficientNet‑B3 arm produced that score.  
- **Agreement on 58 annotated studies**: *“at A ≈ 0.85 with nine positives among 58 studies [SE] ≈ 0.083, so a 95% interval spans roughly ±0.16.”* (used to show that agreement cannot steer tuning).  
- **Silence rate** (fraction of studies where no rule fires) measured on all 4 407 reports. Narrative states ablation of FEATURES one at a time, but **no numeric effect sizes** are quoted for individual FEATURE toggles.  

---

**Resources attached and what is required to reproduce**  

- **Attached:** the notebook itself is self‑contained; the report reader code is built in‑line. No external weights file is explicitly listed (though “RadImageNet ResNet‑50” is used – these are presumably pretrained RadImageNet weights, but the author does not link a dataset).  
- **Required:** Kaggle competition dataset (`train.csv`, `test.csv`, DICOM images). Must mount “`find_root()`” (presumably `/kaggle/input`). Optionally mount a pre‑computed label table (public dataset of model‑read labels); falls back to the inline lexicon per study.  
- **Reproduction:** run the notebook with Kaggle GPU (2×T4 recommended? Not stated; code uses `torch.device(f'cuda:{index}')` and probes available devices).  

---

**Author’s own warnings or caveats**  

- *“Only fifty‑eight labelled studies cannot train an imaging model, and the reports that could supply the missing four thousand are unavailable at prediction time. So the pipeline is forced into one shape: read the reports into targets, fit a pure imaging model against them, and throw the text away.”*  
- *“Fifty‑eight annotated studies … agreement intervals are wide (±0.16), too wide to steer tuning; the silence rate is more reliable.”*  
- *“The scorecard separates completed official rows from local validation … OOF diagnostics can select or reject an arm, but only a completed Kaggle submission can change the verified public score above.”*  
- *“Prevalence drift is survivable; thresholds are not.”* (AUC invariance to prevalence).  

---

**Confidence that each technique is a real cause of score**  

| Technique | Confidence | Reason |
|-----------|------------|--------|
| **Report reader (multilingual rule extractor)** | ASSERTED | Justified by silence rate and agreement on 58 studies, but no ablation with numeric effect on score quoted. |
| **Unwrap / directional negation / oa_inherit / graded_pathology / synovitis_backoff** | ASSERTED | Author claims they fix specific errors; no numeric effect size quoted. |
| **Rank averaging** | ASSERTED | Argument based on AUC invariance to monotonic transforms; no ablation comparing to probability averaging. |
| **Crop 130 mm, 336 px, 3‑slice stacking** | ASSERTED | Nyquist argument for meniscal tear resolution; no ablation shown. |
| **RadImageNet ResNet‑50 at 20% rank vote** (V52) | **SUPPORTED** | Official Kaggle score 0.906 produced by this configuration. |
| **Five‑fold EfficientNet‑B3** (V49) | **SUPPORTED** | Produced 0.898 in a guarded run. |
| **Training hyperparameters (SEED, EPOCHS=10, LR, aug, etc.)** | ASSERTED | No ablation reported. |
| **Sample weights from confidence** | ASSERTED | Author states it prevents training every silence as confident negative; no ablation. |