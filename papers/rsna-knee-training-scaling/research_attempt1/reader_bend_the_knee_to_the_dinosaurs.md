```json
{
  "source_used": "bend-the-knee-to-the-dinosaurs",
  "analysis": {
    "headline_claim": {
      "claim": "Notebook adds a CoAtNet MRI reader, forming an ensemble. No single final score is reported; the notebook is presented as an inference-only submission. The upstream context mentions a 0.943 leaderboard, but this is stated as Mattia Angeli's score from a different notebook version (v34), not this notebook's own score.",
      "version_evidence": "No explicit score for this notebook. The narrative states: \"Inference-only submission.\" The only score mentioned is from an external reference: \"adopts Mattia Angeli's scored **0.943 v34**\" (this appears in the `rsna-knee-fast-2xt4-inference` source, not in `bend-the-knee-to-the-dinosaurs`). For the source itself, no score is claimed."
    },
    "concrete_techniques": {
      "new_member_addition": {
        "description": "Adds a CoAtNet MRI reader (public CoAtNet RMLP-2 backbone) to an existing ensemble of 20 DINOv2 models (rank mean).",
        "input_design": "Each 384 px adjacent-slice triplet passes through the backbone.",
        "backbone": "CoAtNet RMLP-2.",
        "head": "Finding-specific gated spatial head blends localized evidence with a protected global-average residual; a second finding-specific attention stage pools windows across the study.",
        "checkpoints": "Three checkpoints are combined by per-finding rank averaging before joining the existing ensemble.",
        "numbers": {
          "input_resolution": "384 px",
          "triplet_slices": "3 slices (GROUP = 3, N_GROUP_MAX = 1)",
          "crop_mm": 130.0,
          "cache_img": 336,
          "aug_rot_deg": 8.0,
          "aug_scale": 0.08,
          "aug_shift": 0.05,
          "aug_intensity": 0.1,
          "epochs": 10,
          "batch_studies": 8,
          "lr_head": 0.001,
          "lr_backbone": 8e-06,
          "weight_decay": 0.02,
          "unfreeze_last": 6,
          "slot_prior_strength": 0.55
        }
      },
      "existing_ensemble_architecture": {
        "description": "Original 20 DINOv2 members are rank-blended. Then a DINOv3 ViT-S/16 is fine-tuned on the competition data and rank-blended into that family. Above the encoder, each series carries a learned type embedding (plane crossed with fat suppression) added to all its tokens. Tokens from all series are concatenated into one key/value sequence, and twelve learned queries (one per finding) cross-attend over it with multi-head attention. Each query's output is concatenated with the mean/max of per-series CLS embeddings before the classifier. Series a study does not contain are removed by key-padding mask.",
        "numbers": {}
      },
      "RadImageNet_fusion": {
        "description": "RadImageNet joins in two pinned stages: E13 heads fused into pinned v15 reference family at 0.50 on ranks; that family then gets 0.50 rank vote on ten findings (Baker's and Fracture preserved). Same E13 heads run second time on E11 slot layout (three non-fat-suppressed planes at 130 mm crop) and blended in at 0.15.",
        "numbers": {
          "first_stage_weight": 0.50,
          "second_stage_weight": 0.15,
          "E11_crop_mm": 130.0
        }
      },
      "report_reading_pipeline": {
        "description": "Extensive rule-based NLP extractor for 12 findings from radiology reports. Includes unwrap, normalization (NFKD), clause splitting, negation/hedge detection, grade reading, OA compartment attribution, language-agnostic matching (9 languages), and a confidence/sample-weight output.",
        "FEATURES_flags": "{'unwrap': True, 'directional_negation': True, 'oa_inherit': True, 'graded_pathology': True, 'synovitis_backoff': True}",
        "numbers": {
          "NEG_WINDOW": 90,
          "GRADE_HIGH_patterns": "grade?[ao]?\\s*(3|4|iii|iv)\\b|icrs grade (iii|iv|3|4)|stupnja iv|stupnja iii|\\bgrado (3|4)\\b|\\bgrad (3|4)\\b|\\bgrade (3|4)\\b",
          "SYNOVIAL_PROXY_prior_formula": "prior = 0.30 + 0.30 * max(0.0, (eff - 0.5) / 0.45) + 0.06 * min(proxy, 3)"
        }
      },
      "dicom_handling": {
        "description": "Geometry-based slice ordering (dot IPP·cross(IOP)), laterality from geometry or Laterality tag, physical crop to 130 mm, resampling to fixed pixels, per-series intensity normalization (1st/99th percentile over sampled stack).",
        "numbers": {
          "lat_min_offset_mm": 20.0,
          "legacy_lat_offset_mm": 5.0,
          "slice_band": "(0.2, 0.8)"
        }
      },
      "slot_selection": {
        "description": "Six anatomical slots: SAG_FLUID_FS, COR_FLUID_FS, AX_FLUID_FS, SAG_FLUID_NOFS, COR_T1, SAG_T1. Series chosen by plane × weighting × fat suppression, fallback allowed for non-FS slots. Longest series selected. N_SLOT = len(SLOTS) (6).",
        "SLOTS_RECOVERED": "['SAG_FLUID_FS', 'COR_FLUID_FS', 'AX_FLUID_FS', 'SAG_FLUID_NOFS', 'COR_T1', 'SAG_T1']",
        "SLOTS_PUBLIC": "specified in notebook (not fully listed in extracted code)",
        "SLOT_SCHEME": "os.environ.get('SLOT_SCHEME', 'recovered')",
        "numbers": {
          "groups": 3,
          "n_group_max": 1,
          "cache_fraction": 0.45,
          "cache_budget_max_gb": 24.0,
          "cache_budget_gb": 12.0
        }
      },
      "test_time_augmentation_tta": "Not mentioned in this source. TTA is not used in the inference-only submission."
    },
    "ablation_or_measured_effect_size": {
      "tonylica_ablation": "The notebook states: 'tonylica — for publishing a run of this pipeline with the two per-finding specialists left out. That version scored higher than the one with them, which is what led to their removal here; the deployed recipe is otherwise unchanged.' This is an ablation (removing two specialists) reported to improve score, but the specific score delta is not given.",
      "per_finding_specialist_removal": "Removed two stages that replaced individual findings (Synovitis, Lateral Meniscus with Lateral OA) with report and metadata models. Narrative says: 'they were unreachable in the deployed run, and leaving those findings to the image models scored better.' No score numbers provided."
    },
    "resources_and_reproduction": {
      "datasets_attached": [
        "pilkwang — twenty trained models",
        "stevenleehans and lixin73 — label reading tables",
        "tonylica — four more trained models",
        "marwanmath — official RadImageNet ResNet-50 weights",
        "cf696666 (fishface) — E10/E11 RadImageNet machinery",
        "sofiaanjenje — five-fold E11 and E13 RadImageNet heads",
        "saidmohamedomary — V48 notebook",
        "sakhawathossen and ranjithragavan07 — DINO aggregation notebook",
        "public DINOv2 models (20 members)",
        "public DINOv3 ViT-S/16 fine-tuned model",
        "CoAtNet RMLP-2 model (Mattia Angeli's weight: https://www.kaggle.com/datasets/mattiaangeli/rsna-knee-coat-resgated-ep10-top3)",
        "RadImageNet E10/E11/E13 head weights"
      ],
      "reproduction_requirements": [
        "Kaggle environment with at least one GPU (CUDA)",
        "Mount all attached datasets under /kaggle/input",
        "DICOM files from competition test set",
        "8 hours TIME_BUDGET (8.0 * 3600)",
        "Minimum 12 GB cache budget, max 24 GB",
        "16 HDR threads, 12 PIX threads, 32 ORDER threads"
      ],
      "artifacts_produced": "submission.csv with 12 probability columns"
    },
    "warnings_or_caveats": [
      "The notebook states it is 'Inference-only submission' — no training code is run.",
      "The narrative explicitly states this version adds one model (CoAtNetMRI) to the previous ensemble; it does not claim to retrain the base models.",
      "The slot scheme depends on environment variable SLOT_SCHEME (default 'recovered'); different slot definitions may affect reproducibility.",
      "The cache budget is adaptive (CACHE_FRACTION = 0.45 of available memory, capped at 24 GB), so reproducibility may vary by machine memory.",
      "The legacy vs native DICOM rules (RULES) are configurable; native is default but legacy may be needed for some public versions.",
      "The report extractor depends on a mounted label table (find_label_table()) — if the table is missing, the extractor falls back to the lexicon but only per study, not per run."
    ],
    "technique_confidence": {
      "CoAtNet_RMLP-2_backbone_added": "SUPPORTED — the notebook adds this as the headline new member, and the effect is measured by the upstream score (0.943) attributed to the parent notebook. However, no ablation of just this addition is reported.",
      "DINOv2_to_DINOv3_added": "SUPPORTED — described as a new addition to the 20 DINOv2 family, but no separate score for this change alone.",
      "per_finding_specialist_removal": "SUPPORTED — directly stated: tonylica's run without them scored higher, causing their removal.",
      "cross-attention_queries_12": "SUPPORTED — explicitly described as the architecture above the encoder.",
      "RadImageNet_0.50_0.15_weights": "SUPPORTED — explicitly stated as the blend weights.",
      "adjacent_slice_triplet_384px": "SUPPORTED — explicitly stated for CoAtNet input.",
      "report_reading_pipeline": "SUPPORTED — extensive code and configuration lines are present; the pipeline is used to generate training targets.",
      "slice