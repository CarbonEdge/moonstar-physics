# Source: kaggle notebook `rsna-versia-5`

## Narrative (markdown cells)
# 🩺 RSNA Knee Abnormality Detection: A Diagnostic Quest

Welcome to the clinic of the future!  
You are a radiologist — but not an ordinary one. You are armed with neural networks.  
Your task is to make **12 key diagnoses** from knee MRI studies, using both images and, during training, the accompanying radiology reports.

---

## 🧩 The Core Challenge

Each study is a **puzzle** made of several MRI series — slices acquired in different planes and with different contrast weightings.  
You must assemble the full picture and answer 12 questions: Is there a ligament tear? Meniscal damage? Osteoarthritis? Inflammation? A cyst? A fracture?

**Metric:** macro-averaged ROC AUC across all 12 labels.  
**Key twist:** during training, you have access not only to the images but also to the **radiologists’ free-text reports**. At inference time, reports are absent — so you must learn to squeeze every bit of signal from them while training.

---

## 🧠 Analogy: “Training a Virtual Radiology Resident”

Imagine you are teaching a new resident:

- **DICOM series** — different examination tools: sagittal, coronal, and axial views.
- **Fluid-sensitive sequences** (T2, PD, STIR) — a flashlight that highlights fluid, edema, and tears.
- **train.csv** — patient charts with partially completed diagnoses.
- **train_series.csv** — a description of each scan: plane, fat suppression, fluid sensitivity.
- **Radiology reports** — notes from an experienced mentor who sometimes writes “ACL tear” and sometimes “intact menisci.”

Your resident (the model) must learn to make diagnoses even when the mentor is not there (at test time).

---

## 🏆 Difficulty Tiers of the Diagnoses

| Tier | Diagnoses | Why They Are Hard | What Helps |
|------|-----------|-------------------|------------|
| 🟢 **Easier** | Baker's cyst, Effusion | Clearly visible on fluid-sensitive sequences | A single sagittal series |
| 🟡 **Moderate** | MCL, Medial/Lateral Meniscus, PF OA | Need assessment across multiple planes | 2–3 series + attention |
| 🔴 **Hard** | ACL, Synovitis, Contusion, Fracture | May be subtle; require broader context | Multi-plane aggregation, 2.5D/3D inputs |
| 🟣 **Very Hard** | Medial OA, Lateral OA | Cartilage thickness assessment; need thin slices | Specialized models + post-processing |

---

## 💡 The Main Takeaway

**This competition is won by whoever does three things best:**

1. **Select the right series** — not all 500 GB of data is useful.
2. **Exploit the reports** to expand weak labels — they are free supervision.
3. **Aggregate carefully** across planes and slices.

No magic — only solid data engineering and thoughtful modeling.

---

**Let’s go!** 🚀  
We start with a simple diagnostic tool and gradually turn it into a radiology expert.

# 📊 Evolution of Public Solutions: 0.937 → 0.94 → 0.941 → 0.942 → 0.943

## 🥉 Work 1 — 0.937
**Head and Shoulders, Knees and Toes**

🔗 https://www.kaggle.com/code/prvsiyan/head-and-shoulders-knees-and-toes

- CoAtNet branch expanded to **4 arms**: v5, v10, v5-reverse, v8.
- Reverse-flip adds diversity without new training.
- Outer CoAtNet weight becomes **global 0.60** instead of per-target.

---

## 🥈 Work 2 — 0.94
**RSNA Knee Hybrid Raptor — Lateral Meniscus R100**

🔗 https://www.kaggle.com/code/renta0426/rsna-knee-hybrid-raptor-lateral-meniscus-r100

- Starts from the exact 0.939 parent (reproduced 1-to-1).
- Changes **only one label**: Lateral Meniscus.
- Outer routing for Lateral Meniscus: Transformer/Rad **0.00** / strengthened Raptor **1.00**.
- All other 11 labels remain **bit-for-bit equal** to the parent at 0.40 / 0.60.

> **Key idea:** isolate one problematic target and give it the full weight of the strongest branch.

---

## 🥇 Work 3 — 0.941
**Bend the Knee to the Dinosaurs (ALL PUBLIC)**

🔗 https://www.kaggle.com/code/mattiaangeli/bend-the-knee-to-the-dinosaurs

- Keeps the 4-arm Raptor from Work 1.
- Adds **residual-gated CoAtNet** (e4/e6/e8) inside the Raptor branch.
- Inner blend: public Raptor 0.60 / residual-CoAt 0.40.
- Adds a public **CoAtNet MRI reader**: 384 px adjacent-slice triplets → CoAtNet RMLP-2 backbone.
- Finding-specific gated spatial head + second attention stage pools windows across the study.
- Updated CoAtNet arm weights: maxspan-v5 = **0.60**, reverse = **0.10**.
- Per-target outer routing: ACL **0.75**, Medial Meniscus **0.80**, Lateral Meniscus **1.00**, Lateral OA **0.75**, Fracture **0.75**.

> **Key idea:** strengthen the Raptor arm with a genuinely different visual inductive bias and let each finding lean on whichever branch predicts it best.

---

## 🚀 Work 4 — 0.942
**rsna-knee-0942-restructured**

🔗 https://www.kaggle.com/code/maverickss26/rsna-knee-0942-restructured

### What changed vs 0.941

Three **hyperparameters** raised — no new models:

| Parameter | 0.941 | 0.942 |
|-----------|-------|-------|
| `a5_w` (A5 blend weight) | 0.45 | **0.52** |
| `rad_alpha` (RadImageNet) | 0.50 | **0.55** |
| `rad_second_alpha` (E13 second pass) | 0.15 | **0.20** |
| `raptor_k_eval` (windows per arm) | 62 / 42 | **94** |

### Why it helps

- **`raptor_k_eval=94`** — samples each stack more densely. This is an accuracy change that needed no new model, and it is only affordable because of the speed work: shared DINO prefixes, persistent T4×2 replicas, cached decoding. Full run takes **~4 minutes** on T4×2.
- **Reweighted A5 and RadImageNet** — both branches contribute more to the final blend.

### Added in this version

- **E9 RadImageNet Heads V15 dataset** — an alternative source of heads (`antoinegg1/rsna-knee-e9-radimagenet-heads-v15`).
- **Parallel execution** of residual-gated CoAtNet and D4 DepthZone SWA3 — 155s → 69s with zero change to predictions.
- **Routing diagnostics** — an agreement / tie-block table.
- **Presets:** `speedy`, `parent`, `halfway`, `sparse`.

---

## ⚡ Work 5 — 0.943
**rsna-knee-fast-2xt4-inference**

🔗 https://www.kaggle.com/code/jiweiliu/rsna-knee-fast-2xt4-inference

### What changed vs 0.942

The CoAt family **doubled** — from 2 members to 4 — and the way they are combined was changed.

| Component | 0.942 | 0.943 |
|-----------|-------|-------|
| CoAt family members | 2 (resgated, d4) | **4** (+ global96, + repairv1) |
| Global96 epochs | — | **16 / 23 / 18** |
| Repair-v1 epochs | — | **12 / 7 / 11** |
| Family reduction | mean of ranks | **rank of mean of probabilities** |
| Parallelism | pair | **two pairs in parallel** |
| Raptor header cache | — | **shared from DINOv2 ordering scan** |

### New models in this version

- **Global96 top-3** — same 96-slice stack as D4, but a full-width gated head instead of Rank8 finding-to-slot attention. Shares geometry, not the reader.
- **Repair-v1 top-3** — third independent CoAt checkpoint, adds another 3-checkpoint vote.

### Family reduction change

Previous: rank each member, average ranks, rank the average.
New: read each member's `probability_mean` from its `.npz`, average **probabilities**, then `rank(pct=True)`.
Fallback to the old rank-sum if any member's `.npz` is missing.

### Speed work

- Two CoAt readers run **in parallel pairs** — `(resgated, d4)` and `(global96, repairv1)`.
- **Raptor header cache** is seeded from the DINOv2 ordering pass, so Raptor never re-reads DICOM headers.

> **Key idea:** beyond picking the best single model per finding, the frontier now comes from combining **more, genuinely different CoAt readers** and **reducing them in probability space** rather than rank space.

---

## 🔑 Key Pattern

Each step isolates a single high-impact change:

1. **Diversity** — more CoAtNet arms + reverse-flip.
2. **Inner strengthening** — residual-gated CoAt.
3. **Target-specific routing** — full weight to the best model for a problematic label.
4. **Sampling density** — `k_eval=94` with no new models.
5. **Family depth + probability-space reduction** — 4 CoAt members, reduced in probability space.

This is how public solutions moved from **0.937 → 0.94 → 0.941 → 0.942 → 0.943**.

---

## 📚 Credits

All models, weights, and pipelines below are public work by other authors. We reproduced them one-to-one and packaged them into a single notebook. Full credit to their authors and contributors.

- **Work 1 (0.937)** — [prvsiyan](https://www.kaggle.com/code/prvsiyan/head-and-shoulders-knees-and-toes)
- **Work 2 (0.94)** — [renta0426](https://www.kaggle.com/code/renta0426/rsna-knee-hybrid-raptor-lateral-meniscus-r100)
- **Work 3 (0.941)** — [Mattia Angeli](https://www.kaggle.com/code/mattiaangeli/bend-the-knee-to-the-dinosaurs) + credits: Pilkwang, Sofia Anjenje, Antoine G., prvsiyan, Marwan Mahmoud, dreaddevelopment/Roman Tamrazov, renta.k, Anvith Pothula
- **Work 4 (0.942)** — [maverick_ss_26](https://www.kaggle.com/code/maverickss26/rsna-knee-0942-restructured/notebook)
- **Work 5 (0.943)** — [Jiwei Liu](https://www.kaggle.com/code/jiweiliu/rsna-knee-fast-2xt4-inference/notebook)

## 1. 🔧 Environment, D4 runtime checks, asset lookup

Пиннинг потоков (`OMP/OPENBLAS/MKL=4`, `CUDNN_CONV_WSCAP_DBG=1024`), проверка D4-контракта, и **кэшированный поиск ассетов**.

**Главное:**
- `ASSET_ROOTS` — **явный список** всех датасетов. Здесь уже добавлен **Global96** (`rsna-knee-coatnet-global96-top3`), которого не было в 0.942.
- `_asset_walk` и `_asset_find_asset` кэшируются через `_speed_asset_catalogue` — каталог обходится **один раз**, потом только сравнение по хешу.
- **D4 reference checks:** `coatnet_pairfilm_manifest.json` должен совпадать по SHA256, `N_MODELS==1`, чекпоинт `coatnet_d4_parent_rank8_swa2.pt`, версии `cv2==4.12.0` и `timm==1.0.22`, **ровно 2 T4**.
- **`_asset_half_rank_mix`** теперь принимает **varargs** (`*members`) — это под 4 члена CoAt-семейства в 0.943, а не под 2.
- `_d4_check_outputs` — жёсткая проверка receipt: `fallback_studies==0`, `preparation_warnings==0`, `peak_reserved_bytes < 15.5 GB`, и что CSV на диске совпадает с рангами в `.npz`.

## 2. 🎯 Dense depth allocation — capacity-aware sampling

Как D4-модель делит слоты на depth-зоны и распределяет бюджет срезов.

**Главное:**
- **`_dense_allocate`** — распределяет 94 окна по слотам **пропорционально их реальной capacity** (сколько уникальных срезов доступно), а не по фиксированной схеме. Это устраняет дубли и padding.
- **`_dense_coat_specs`** — считает capacity каждого слота через `sampler._candidate_centers`, потом зовёт `_dense_allocate` с пропорциями `(20, 12, 12, 8, 16, 8)` на 94 окна. Проверяет, что не осталось дублей центров.
- **`INFERRED96_WIDTHS = (27, 21, 18, 12, 18)`** — эталонная раскладка на 96 позиций.
- **`_dense_stack`** — пересобирает эталонный Global96-стек под конкретное исследование: фильтрует невалидные срезы, разворачивает reverse-стек, распределяет квоты, склеивает обратно в `FixedGlobalStack`.
- **Audit на каждый слот:** `original_width`, `allocated_width`, `additional`, `reason` (`missing_no_padding` / `short_slot_all_unique` / `uniform_native_centers`).

**Итог:** один и тот же набор моделей D4 и Global96 работает и на длинных, и на коротких сериях — просто перераспределяя окна туда, где реально есть данные.

## 3. 🚀 Startup: пути, девайсы, integrity harness

Старт пайплайна. Проверяет, что есть **ровно 2 GPU**, и что это **T4** — иначе падает (никакого CPU/1-GPU fallback).

**Главное — здесь же весь integrity harness:**

- **`rsna_finite` / `rsna_rank01` / `rsna_rankpct`** — проверка значений до ранжирования. Nonfinite или out-of-range → падение.
- **`rsna_frame`** — валидирует схему и порядок `StudyInstanceUID`, приводит к нужному порядку.
- **`rsna_save_predictions`** — сохраняет промежуточные предсказания в `diagnostics/*.npz` для аудита.
- **`rsna_strict_load`** — загрузка чекпоинта: **все** тензоры должны совпасть по имени и форме, nonfinite значения запрещены. Никакой случайной инициализации.
- **`rsna_deadline`** — если весь пайплайн перевалил за `TIME_BUDGET = 8 часов` — падение, а не частичный submission.
- **`rsna_array`** — большие массивы пикселей уходят в `memmap` (`/kaggle/temp` или `/tmp`), не в RAM.
- **`rsna_phase`** — пишет в `diagnostics/current_phase.json` и `phase_events.jsonl` отметки START/COMPLETE каждой стадии.
- **`_rsna_capture_cell_error`** — ловит uncaught ошибки через IPython hooks и логирует их в phase.

**Что нового vs 0.942:** по сути, тот же harness. Единственное — `SLOTS_RECOVERED` теперь включает `SAG_T1` (Sagittal T1), и добавлен `smart fat`/`water` в `_FATSAT_RX` (для GE Dixon).

## 4. 📁 Пути, кэш, A5 applicability

Находит корень соревнования и DINOv2 строго по списку (ровно один кандидат). Планирует размер кэша: 45% от доступной RAM, не больше 24 ГБ → 1 группа × 3 среза = 3 на слот.

Проверяет, у каких тестовых исследований есть нужные A5-слоты (`Sagittal/Coronal/Axial` × `Fat_Suppression` 0/1). Если слотов нет — A5 пропускается **только для этого исследования**, модель не падает.

## 5. 🦴 Чтение DICOM-заголовков

Три функции: `probe` (метаданные одной серии), `walk` (обход всех, с кэшем `_RSNA_HEADERS_MEMO`), `annotate` (восстановление T1/T2/PD/GRE и fat-suppression).

`lat_of` определяет сторону колена: сначала по тегу `Laterality`, если нет — по геометрии (медиана X-координаты). Логирует, сколько разрешилось каждым способом.

Отдельно ловит GE Dixon (`smart fat`, `water`) — раньше 37 исследований из 4407 не имели fat-sat серий.

## 6. 🗂️ Выбор серий для слотов

Для каждого исследования — по одной серии на слот (плоскость × контраст × fat-suppression).

Если точного совпадения нет и `slot_fallback=True` (только для не-FS слотов), берётся любая не-FS серия в этой плоскости. Среди кандидатов — самая длинная (`n_slices` max).

Результат: `{study: {slot_name: series_row}}`, из которого потом строится фиксированный тензор.

## 7. 📐 Геометрическая сортировка и чтение срезов

`order_slices` сортирует DICOM по физическому положению среза (dot IPP · cross(IOP)), fallback — `InstanceNumber`, потом natural sort.

Заодно **заполняет `RAPTOR_HEADER_CACHE`** — если все файлы серии имеют валидную геометрию и уникальный ключ, порядок и spacing сохраняются для Raptor-ветки (чтобы н

## Key configuration lines from code
root = Path(artifact_root)
manifest_path = root / 'coatnet_pairfilm_manifest.json'
digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
expected = json.loads(manifest_path.read_text())
if rt.GPU_BATCH_STUDIES != 2 or rt.BACKBONE_MICRO_IMAGES != 8:
names = [torch.cuda.get_device_name(i) for i in range(2)]
checkpoints = receipt['checkpoints']
need(checkpoints[0]['member_epochs'] == [15, 16], 'parent SWA member epochs')
processes = receipt['processes']
shards = receipt['shards']
output = Path(output)
prediction_path = output.parent / rt.PREDICTIONS_NAME
uids = payload['study_uids'].astype(str).tolist()
raw = np.asarray(payload['raw_probabilities'], dtype=np.float32)
mean = np.asarray(payload['probability_mean'], dtype=np.float32)
ranked = np.asarray(payload['submission_percentile_rank'], dtype=np.float64)
ids = pd.read_csv(Path(competition) / 'test.csv', dtype={'StudyInstanceUID': str}).StudyInstanceUID.tolist()
frame = pd.read_csv(output, dtype={'StudyInstanceUID': str}, float_precision='round_trip')
actual_hash = hashlib.sha256(output.read_bytes()).hexdigest()
remaining = TIME_BUDGET - (time.time() - T0)
path = Path(logfile)
process = subprocess.Popen(command, env=environment, stdout=log_handle, stderr=subprocess.STDOUT, start_new_session=True)
returncode = process.wait(timeout=remaining)
tail = handle.read().decode('utf-8', errors='replace')
seen = set()
root = Path(root).resolve()
level = [root]
following = []
children = sorted(directory.iterdir())
dirs = [p for p in children if p.is_dir() and p.name not in ('train_series', 'test_series', 'train_images', 'test_images')]
files = [p.name for p in children if p.is_file()]
level = following
hits = []
first = members[0]
units = members[0].rank(method='average')
units = units + other.rank(method='average')
source = Path(artifact) / 'coatnet_resgated_ep10_top3_inference.py'
text = source.read_text()
text = text.replace(old, new)
text = text.replace('"gold58_rank_ensemble_auc": manifest["selection"]', '"historical_parent_gold58_rank_ensemble_auc": manifest["selection"]')
marker = 'if __name__ == "__main__":'
patch = helper_source + ('\n_original_train_faithful_eval_specs = train_faithful_eval_specs\n'
text = text.replace(marker, patch + '\n' + marker)
audited = rt.parent.audited
original = audited.prepare_global96_bag
original_shard = rt._PARENT_INFER_SHARD
src = textwrap.dedent(inspect.getsource(original))
tree = ast.parse(src)
call = candidates[0]
keywords = {k.arg: k.value for k in call.value.keywords}
audit_dir = Path(os.environ['RSNA_D4_INPUT_AUDIT_DIR'])
arrays = ('global_indices', 'nominal_slots', 'canonical_depths', 'nominal_steps', 'source_series_rows', 'source_slot_ids')
digest = hashlib.sha256()
value = np.ascontiguousarray(getattr(stack, name))
injection = ast.parse('try:\n    stack, input_audit = _dense_stack(stack, study.offsets, study.valid, study.source_depth)\n'
where = fn.body.index(call)
patched = audited.prepare_global96_bag
files = {}
path = Path(module.__file__)
manifest = artifact / 'coatnet_pairfilm_manifest.json'
audit_dir = output.parent / 'study_input_receipts'
wrapper = output.parent / 'd4_worker_entry.py'
env = dict(os.environ)
receipt = json.loads(output.with_suffix('.receipt.json').read_text())
expected = pd.read_csv(Path(competition) / 'test.csv', dtype={'StudyInstanceUID': str}).StudyInstanceUID.tolist()
records = []
ids = [r['study_uid'] for r in records]
catalogue = _speed_asset_catalogue
key = (str(name), digest)
capacities = np.asarray(capacities, dtype=np.int64)
proportions = np.asarray(proportions, dtype=np.float64)
ideal = int(target) * proportions / proportions.sum()
initial = np.floor(ideal).astype(np.int64)
quotas = np.minimum(initial, capacities)
wanted = min(int(target), int(capacities.sum()))
deficit = np.zeros(len(quotas), dtype=np.float64)
donors = quotas < capacities
weights = np.where(donors, proportions, 0.0)
chosen = int(np.argmax(np.where(donors, deficit, -np.inf)))
result = np.linspace(0, capacity - 1, count).round().astype(np.int64)
capacities = []
quotas = _dense_allocate(capacities, (20, 12, 12, 8, 16, 8), 94)
keys = [(s.series_row, s.center_local) for s in specs]
start = int(study.offsets[s.series_row])
INFERRED96_WIDTHS = (27, 21, 18, 12, 18)
base = np.asarray(INFERRED96_WIDTHS, dtype=np.int64)
quotas = np.minimum(base, capacities)
target = min(96, int(capacities.sum()))
deficit = np.zeros(5, dtype=np.float64)
weights = np.where(donors, base, 0).astype(np.float64)
selected = int(np.argmax(np.where(donors, deficit, -np.inf)))
pools = []
audit = []
begin = 0
end = begin + width
old = reference.global_indices[begin:end]
row = int(reference.source_series_rows[begin])
info = {'slot': slot, 'original_width': width, 'source_row': row}
begin = end
depth = np.asarray(source_depth[start:stop], dtype=np.float32)
keep = np.asarray(valid[start:stop], dtype=bool) & np.isfinite(depth) & (depth >= 0.02) & (depth <= 0.98)
eligible = np.flatnonzero(keep).astype(np.int64) + start
reverse = bool(old[0] > old[-1] or
