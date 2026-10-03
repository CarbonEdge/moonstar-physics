# Source: kaggle notebook `rsna-knee-fast-2xt4-inference`

## Narrative (markdown cells)
# RSNA Knee — fast 2xT4 inference

## Mini changelog

- **v2:** reorganized inference for two T4s: shared the frozen DINO prefix,
  overlapped CPU preparation, shared MaxSpan decoding, and bounded cuDNN memory.
- **v3:** changed Raptor MaxSpan forward/reverse weights from **0.55/0.15** to
  **0.60/0.10**; Native384 Dense/Native384 stayed **0.10/0.20**.
- **v4:** cached immutable DICOM slice order and spacing across Raptor views.
- **v5:** removed a redundant Raptor rerank, matching the public 0.941 recipe.
- **v6:** passed DINO's verified slice order and spacing into Raptor, avoiding a
  second header scan while retaining the original fallback for ambiguous series.
- **v7:** adopts the current public **0.942** recipe: residual-gated CoAtNet and
  D4 DepthZone SWA3 ranks are mixed **0.50/0.50**; that private family remains
  **0.40** against public Raptor **0.60**, with no inner rerank. RadImageNet's
  main/second-pass weights change **0.50→0.55** and **0.15→0.20**.
- **v8:** runs the independent residual-gated and D4 readers concurrently on
  both T4s; checkpoints, windows, precision, and weights are unchanged.
- **v9:** adopts Mattia Angeli's scored **0.943 v34**: residual/D4 weights
  **0.50/0.50→0.25/0.25**, plus Global96/Repair-v1 **0/0→0.25/0.25**.
  CoAt family fusion changes from rank-of-mean-ranks to **rank-of-mean-probabilities**.
  CoAt/Raptor stays **0.40/0.60**. Runs the four CoAt readers in two parallel
  pairs, retaining every checkpoint and the scored precision/window settings.
- **v10:** for cohorts above 48 studies, serves the four CoAt readers one at a
  time to limit concurrent RAM and GPU use on 2×T4. Restores v34's per-study
  fallback handling; the four-model probability blend and all weights remain
  **0.25/0.25/0.25/0.25**, then **0.40 CoAt / 0.60 Raptor**.
- **v11:** restores v34's reader-level fallback: if a CoAt arm fails, the
  available arms share the 0.40 CoAt weight equally; if none survives, keep
  Raptor. Missing raw probabilities use v34's rank-mix fallback.

This inference-only notebook is derived from
[maverickss26's public solution](https://www.kaggle.com/code/maverickss26/rsna-knee-0941-restructured)
and the current model recipe comes directly from
[Mattia Angeli's Speedy Raptors v34](https://www.kaggle.com/code/mattiaangeli/bend-the-knee-to-speedy-raptors-the-original?scriptVersionId=351665011),
which scored 0.943 publicly. That is the upstream score, not a guarantee for
this version. The earlier v7 recipe was cross-checked against
[Berat Erol Celik's v5](https://www.kaggle.com/code/beraterolelk/rsna-knee-speedy-raptors-coatnet-d4-sota?scriptVersionId=351068470).
Thanks also to Dread Development, Pilkwang Kim,
Sofia Anjenje, Antoine G., prvsiyan, Marwan Mahmoud, renta.k, and Anvith Pothula
for the released models and upstream work.

## Model stack

| Stage | Inference family | Fusion role |
|---|---|---|
| 1 | 20 DINO slot-attention members | transformer base |
| 2 | five A5 attention-pooling folds | 45% update to the base |
| 3 | RadImageNet E10/E13/E11 heads | calibrated transformer branch |
| 4 | four Raptor views | public CoAtNet branch |
| 5 | residual top-3 + D4 SWA3 + Global96 top-3 + Repair-v1 top-3 | 25% each, probability mean then rank |

## Why it is fast

- DINO members share their identical frozen six-block prefix.
- CPU preparation overlaps GPU inference for A5 and RadImageNet.
- MaxSpan forward/reverse views share one decode and checkpoint load.
- Raptor uses two balanced GPU workers, a bounded pixel cache, and capacity-aware
  unique windows. DINO's existing header scan also seeds Raptor's ordering cache.
- The four CoAtNet readers use parallel pairs for small cohorts. Large cohorts
  run them sequentially to limit peak RAM and contention on Kaggle's 2×T4/29 GB
  machine. Raptor finishes first to bound memory.
- Artifact lookup uses explicit mounted datasets and never walks the test DICOM tree.

All score-sensitive checkpoints, views, ranks, and normal-path blend coefficients
match the scored 0.943 anchor. Header reuse retains the anchor's ambiguity
checks. Reader failures and per-study fallbacks are logged, and the scored
upstream blend handles missing readers or probabilities without aborting.

## Runtime contract and artifact checks

The first cells pin checkpoint hashes, dependency versions, memory limits, and
the D4 serving contract before expensive inference begins. Any missing or
changed required asset stops the run instead of silently changing predictions.

## Stage 1 — DINO ensemble

Each MRI study is mapped into anatomical slots. Twenty member-specific tails
share the verified frozen DINO prefix, preserving all members while avoiding
the largest repeated transformer computation.

## Stage 2 — A5 attention pooling

Five folds pool variable-length slice features. Host preparation stays bounded
and overlaps the active GPU pass; unavailable acquisitions fall back to the
base branch, while model failures remain fatal.

## Stage 3 — RadImageNet heads

One RadImageNet encoder feeds the E10/E13/E11 layouts. Version 7 uses the scored
0.942 routing: main alpha 0.55 and second E13 pass alpha 0.20.

## Stages 4–5 — Raptor and complementary CoAtNet readers

Four Raptor views run first. Small cohorts overlap residual + D4 and
Global96 + Repair-v1; large cohorts run the readers one at a time. When all
four CoAt readers succeed, their probability arrays are averaged 25% each and
ranked, then blended 40% into Raptor. Missing arms use the scored upstream
fallback; outer routing is unchanged.

## Final checks

The notebook publishes `submission.csv` only after schema, study order, finite
values, checkpoint identities, model counts, and fallback counts are recorded.

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
