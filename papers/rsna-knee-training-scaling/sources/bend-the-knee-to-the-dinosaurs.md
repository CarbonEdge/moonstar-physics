# Source: kaggle notebook `bend-the-knee-to-the-dinosaurs`

## Narrative (markdown cells)
# Bend the Knee to the Dinosaurs (ALL PUBLIC)

## New addition: CoAtNet MRI reader

Inspired by [dreaddevelopment's discussion](https://www.kaggle.com/competitions/rsna-knee-abnormality-detection/discussion/737696), this version adds my public [CoAtNet MRI model](https://www.kaggle.com/datasets/mattiaangeli/rsna-knee-coat-resgated-ep10-top3).

Each 384 px adjacent-slice triplet passes through a CoAtNet RMLP-2 backbone. A finding-specific gated spatial head blends localized evidence with a protected global-average residual; a second finding-specific attention stage pools windows across the study. Three checkpoints are combined by per-finding rank averaging before joining the existing ensemble.

Inference-only submission.

## Credits

[Pilkwang](https://www.kaggle.com/datasets/pilkwang/rsna-knee-weights) · Sofia Anjenje · Antoine G. · prvsiyan · Marwan Mahmoud · dreaddevelopment / Roman Tamrazov · [renta.k](https://www.kaggle.com/code/renta0426/rsna-knee-hybrid-raptor-lateral-meniscus-r100) · [Anvith Pothula](https://www.kaggle.com/code/anvithpothula/rsna-base) · [Evgen Dvorkin](https://www.kaggle.com/evgendvorkin)

## Key configuration lines from code
dev = torch.device(f'cuda:{index}')
probe = nn.Conv2d(3, 4, kernel_size=3, padding=1).eval().to(dev)
out = probe(torch.zeros((1, 3, 16, 16), device=dev))
DEVS = []
DEVS = [torch.device(f'cuda:{i}') for i in range(torch.cuda.device_count()) if _cuda_execution_probe(i)]
SEED = 2026
CROP_MM = 130.0
CACHE_IMG = 336
GROUP = 3
N_GROUP_MAX = 1
CACHE_FRACTION = 0.45
CACHE_BUDGET_MAX_GB = 24.0
CACHE_BUDGET_GB = 12.0
TEST_SHARE = 0.3
HDR_THREADS = 16
PIX_THREADS = 12
ORDER_THREADS = 32
ORDER_BUDGET_S = 5400
RUNS = [{'name': 'r224', 'img': 224}, {'name': 'r336', 'img': 336}]
EPOCHS = 10
BATCH_STUDIES = 8
AUG_ROT_DEG = 8.0
AUG_SCALE = 0.08
AUG_SHIFT = 0.05
AUG_INTENSITY = 0.1
LAT_MIN_OFFSET_MM = 20.0
SLICE_BAND = (0.2, 0.8)
RULES_NATIVE = {'order': 'normal', 'lat': 'centre', 'slot_fallback': False, 'decode_fill': 'nearest'}
RULES_LEGACY = {'order': 'dominant_axis', 'lat': 'corner_x', 'slot_fallback': True, 'decode_fill': 'zero'}
RULES = dict(RULES_NATIVE)
LEGACY_LAT_OFFSET_MM = 5.0
LR_HEAD = 0.001
LR_BACKBONE = 8e-06
UNFREEZE_LAST = 6
WEIGHT_DECAY = 0.02
EVAL_BATCH = 8
TIME_BUDGET = 8.0 * 3600
SLOT_SCHEME = os.environ.get('SLOT_SCHEME', 'recovered')
SLOTS = SLOTS_PUBLIC if SLOT_SCHEME == 'public' else SLOTS_RECOVERED
N_SLOT = len(SLOTS)
POOL_PARTS = {'cls_mean': 2, 'cls_mean_focal': 3}
SLOT_PRIOR_STRENGTH = 0.55
FATSAT_OPTS = {'FS', 'FATSAT', 'FAT_SAT', 'FSAT'}
matches = []
unique = []
ROOT = find_root()
DINOV2_SOURCE = find_dinov2('small')
IMG = CACHE_IMG
info = {k.strip(): v for k, v in (l.split(':', 1) for l in fh if ':' in l)}
avail = available_gb()
budget = min(avail * CACHE_FRACTION, CACHE_BUDGET_MAX_GB)
n_total = n_study + max(n_test, int(TEST_SHARE * n_study))
per_slice = n_total * N_SLOT * IMG * IMG
afford = int(budget * 1024 ** 3 // max(per_slice, 1))
groups = max(1, min(N_GROUP_MAX, afford // GROUP))
N_GROUP = plan_cache(len(pd.read_csv(ROOT / 'train.csv')), len(pd.read_csv(ROOT / 'test.csv')))
CACHE_SLICES = GROUP * N_GROUP
ipp = _hdr_vec(getattr(r, 'ImagePositionPatient', None), 3)
iop = _hdr_vec(getattr(r, 'ImageOrientationPatient', None), 6)
out = {}
geo = side_from_corner_x(h) if RULES['lat'] == 'corner_x' else side_from_geometry(h)
side = v[0] if v else None
side = geo.get(st)
row = {'split': split, 'StudyInstanceUID': study, 'SeriesInstanceUID': series, 'dir': path}
files = sorted((e.name for e in os.scandir(path) if e.name.endswith('.dcm')))
row['n_slices'] = len(files)
base = ROOT / split
items = []
rows = list(pool.map(probe, items))
desc = df['SeriesDescription'].fillna('') + ' ' + df['SequenceName'].fillna('')
desc = desc.str.lower().str.replace(_SEP, ' ', regex=True)
opts = df['ScanOptions'].fillna('').str.upper().str.split('|')
opts_fs = opts.apply(lambda ts: any((t.strip() in FATSAT_OPTS for t in ts)))
gre = df['ScanningSequence'].fillna('').str.upper().str.contains('GR')
series_df = series_df.copy()
chosen = {}
sel = (g['plane'] == plane) & (g['fatsat'] == fs)
cand = g[sel]
cand = g[(g['plane'] == plane) & ~g['fatsat']]
chosen[name] = cand.sort_values('n_slices', ascending=False).iloc[0]
ORDER_TAGS = [(32, 50), (32, 55), (32, 19)]
DECODE_FAILED = []
rows = []
ipp = inst = None
raw = getattr(ds, 'ImagePositionPatient', None)
ipp = c
inst = float(n)
placed = [r for r in rows if r[1] is not None]
need = max(2, int(0.8 * len(rows)))
xyz = np.stack([r[1] for r in placed])
axis = int(np.argmax(np.ptp(xyz, axis=0)))
spare = float(np.nanmedian(xyz[:, axis]))
keyed = []
iop = np.asarray(ds.ImageOrientationPatient, dtype=float)
ipp = np.asarray(ds.ImagePositionPatient, dtype=float)
n_slice = GROUP if n_slice is None else n_slice
out_size = IMG if out_size is None else out_size
idx = np.unique(np.linspace(lo, hi, n_slice).astype(int)) if hi > lo else np.array([n // 2])
idx = np.append(idx, idx[-1])
planes = []
got = [k for k, p in enumerate(planes) if p is not None]
planes = [np.zeros((out_size, out_size), np.float32) if p is None else p for p in planes]
got = list(range(len(planes)))
shp = planes[0].shape
planes = [p if p.shape == shp else np.zeros(shp, np.float32) for p in planes]
vol = np.stack(planes)
want = int(round(CROP_MM / px))
half = want // 2
vol = vol[:, max(0, cy - half):cy + half, max(0, cx - half):cx + half]
vol = np.clip((vol - lo_v) / max(hi_v - lo_v, 1e-06), 0, 1)
ORDER_CACHE = os.environ.get('RSNA_ORDER_CACHE') or None
studies = sorted(slot_map)
sidx = {s: i for i, s in enumerate(studies)}
cache = np.zeros((len(studies), N_SLOT, CACHE_SLICES, IMG, IMG), np.uint8)
mask = np.zeros((len(studies), N_SLOT), np.float32)
jobs = [(st, k, plane, slot_map[st][name]) for st in studies for k, (name, plane, _, _) in enumerate(SLOTS) if name in slot_map[st]]
n_job = len(jobs)
t_ord = time.time()
n_slice_total = sum((len(j[3]['files']) for j in jobs))
CHUNK_O = 1024
seen = {}
seen = _json.loads(Path(ORDER_CACHE).read_text())
hit = 0
jobs = [j for j in jobs if 'ordered' not in j[3]]
block = jobs[c0:c0 + CHUNK_O]
budget = min(ORDER_BUDGET_S, max(60.0, (TIME_BUDGET - (time.time() - T0)) * 0.35))
n_fail
