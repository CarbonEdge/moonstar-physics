# Source: kaggle notebook `bend-the-knee-to-dinov3-ensembled`

## Narrative (markdown cells)
## ⚠️ WARNING: Read this before forking

**This notebook is now likely overfit to the public leaderboard:** after users repeatedly forked and republished it with one or two parameter tweaks, I also followed movements of only 0.001–0.003 and changed the notebook in response.

That user-driven fork-and-republish race is not meaningful model development. Changing one or two parameters and presenting the pipeline as a new solution is opportunistic reuse, not original work.

Use an earlier version as a baseline, or better, use the public DINOv3 member from `knee-mri-fold-weights` and validate it locally; it was selected on held-out labelled studies, while sub-resolution blend tweaks should be treated as noise.

---

# Bend the Knee Ensemble

A community pipeline, with one more model added.

## Thank you

This is built on work other people did first and shared:

- **pilkwang** — twenty trained models that are part of this ensemble, and a
  set of labels read from the reports.
- **stevenleehans** and **lixin73** — two more sets of labels read from the
  reports, so one reading could be checked against another.
- **tonylica** — four more trained models that join the ensemble.
- **marwanmath** — the official RadImageNet ResNet-50 weights.
- **prvsiyan** — the notebook this was forked from (Apache 2.0). Most of its
  later stages have been removed here.
- **cf696666** (*fishface*) — for the earliest verified E10/E11 RadImageNet
  machinery, including the four-slot E11 design, and for leaving two findings
  out of the E10 blend.
- **romantamrazov** — for the fold-rank aggregation idea, and for the
  adaptive second-pass weighting this version uses: the RadImageNet second
  pass is no longer blended in at one fixed weight for all twelve findings,
  but at a weight set per finding by how much the five folds agree and how
  far the second pass departs from the first. His design, from his public
  DINOsaur V3 notebook; the implementation here is our own.
- **ieshanmeghani** — for isolating the public v15/E10 RadImageNet delta.
- **sofiaanjenje** — for running and publishing the five-fold E11 and E13
  RadImageNet heads, including the E13 fat-sensitive crop arm used here.
- **saidmohamedomary** — for publishing V48, which surfaced the value of
  adding the E13 arm to the deployed RadImageNet block.
- **sakhawathossen** and **ranjithragavan07** — for publishing the
  no-extra-pass fold-balanced/smooth DINO aggregation tested here.
- **tonylica** — for publishing a run of this pipeline with the two per-finding
  specialists left out. That version scored higher than the one with them, which
  is what led to their removal here; the deployed recipe is otherwise unchanged.

### The added member

The submission this forks from is a rank mean of twenty **DINOv2** models. Added
here is one **DINOv3 ViT-S/16** — self-supervised and pretrained without labels,
then fine-tuned on this competition's knee MRI — rank-blended into that
family.

Above the encoder, each series carries a learned type embedding — plane crossed
with fat suppression — added to all of its tokens. The tokens of every series in
a study are then concatenated into one key/value sequence, and twelve learned
queries, one per finding, cross-attend over it with multi-head attention. A
finding therefore draws evidence from any series in the study at once, rather
than from per-series summaries combined afterwards. Each query's output is
concatenated with the mean and the max of the per-series CLS embeddings before
the classifier. Series a study does not contain are removed by the key-padding
mask, so nothing is imputed for them.

**RadImageNet** joins the vote in two pinned stages. The E13 heads are fused
into the pinned v15 reference family at 0.50 on ranks; that family then gets a
0.50 rank vote on ten findings, with Baker's and Fracture preserved. The same
E13 heads are then run a second time on the E11 slot layout — three
non-fat-suppressed planes at a 130 mm crop — and blended in at 0.15.

All twelve findings come from the image ensemble. Two earlier stages that
replaced individual findings with report and metadata models — Synovitis, and
Lateral Meniscus with Lateral OA — have been removed: they were unreachable in the deployed run, and
leaving those findings to the image models scored better.

## Key configuration lines from code
text = text.translate(_PRE).lower()
text = unicodedata.normalize('NFKD', text)
text = ''.join((ch for ch in text if not unicodedata.combining(ch)))
text = text.replace('\xad', '')
text = re.sub('[_\\-/\\\\]+', ' ', text)
text = re.sub('[ \\t]+', ' ', text)
out = []
norm = normalize(unwrap(text) if FEATURES['unwrap'] else text)
raw = [c.strip() for c in _SENT_SPLIT.split(norm) if c and c.strip()]
merged = []
FEATURES = {'unwrap': True, 'directional_negation': True, 'oa_inherit': True, 'graded_pathology': True, 'synovitis_backoff': True}
NEGATION = _rx(PRE_NEG.pattern, POST_NEG.pattern, '\\bunremarkable\\b')
NEG_WINDOW = 90
best = None
best = n
DECOY = {'Fracture': _rx('microfractur', '\\bfracture (risk|prophyla)'), "Baker's": _rx('meniscal cyst', 'quiste meniscal', 'parameniscal')}
PAIRED = {'ACL', 'MCL', 'Medial Meniscus', 'Lateral Meniscus'}
OA_TARGETS = ['Medial OA', 'Lateral OA', 'PF OA']
ANY_SIDE = _rx(SIDE_MEDIAL.pattern, SIDE_LATERAL.pattern)
STEM_MENISCUS = _rx('menisc\\w*', 'menisk\\w*', 'μηνισκ\\w*', 'мениск\\w*')
ANAT_MATCH = {t: _Matcher(ANAT[t], *STEM_RULES[t]) for t in PAIRED}
DIRECT_MATCH = {t: _Matcher(_rx(rx.pattern, STEM_FRACTURE.pattern) if t == 'Fracture' else rx) for t, rx in DIRECT.items()}
GRADE_HIGH = re.compile('grade?[ao]?\\s*(3|4|iii|iv)\\b|icrs grade (iii|iv|3|4)|stupnja iv|stupnja iii|\\bgrado (3|4)\\b|\\bgrad (3|4)\\b|\\bgrade (3|4)\\b')
high = SEV_HIGH.search(clause) is not None
low = SEV_LOW.search(clause) is not None
score = min(0.97, 0.5 + 0.45 * best + 0.015 * min(n_pos, 3))
conf = min(1.0, 0.55 + 0.15 * n_pos)
score = max(0.04, 0.2 - 0.04 * n_neg)
conf = min(0.9, 0.45 + 0.12 * n_neg)
tear = TEAR.search(clause) is not None
base = 1.0
base = 0.95 if g >= 3 else 0.3
base = 0.35
base = 0.45
base = 0.85 if g >= 2 else 0.3
base = 0.4
base = 0.55
base = min(1.0, base * 1.2)
anat_rx = ANAT_MATCH[tgt]
path_rx = _rx(TEAR.pattern, DEGEN.pattern, INJURY.pattern)
meniscus = 'Meniscus' in tgt
n_pos = n_neg = n_unc = 0
best = 0.0
hit = anat_rx.search(c)
hit = PLURAL_MENISCI.search(c)
span = (pm.start(), pm.end()) if pm is not None else None
pol = _polarity(c, span)
best = max(best, _paired_weight(c, meniscus))
best = max(best, 0.45 * _paired_weight(c, meniscus))
pol = _polarity(c, (m.start(), m.end()))
best = max(best, w)
best = max(best, 0.3)
acc = {t: {'pos': 0, 'neg': 0, 'unc': 0, 'best': 0.0} for t in OA_TARGETS}
sev = _severity(c)
tf_med = _near(c, TF_SITE, SIDE_MEDIAL, 45)
tf_lat = _near(c, TF_SITE, SIDE_LATERAL, 45)
hits = []
g_best = max(g_best, sev if GLOBAL_OA.search(c) else sev * 0.7)
out = {}
score = max(score, 0.35)
cls = clauses(report)
proxy = sum((1 for c in cls if SYNOVIAL_PROXY.search(c) and _polarity(c) == 'positive'))
eff = out['Effusion']
prior = 0.3 + 0.3 * max(0.0, (eff - 0.5) / 0.45) + 0.06 * min(proxy, 3)
dev = torch.device(f'cuda:{index}')
probe = nn.Conv2d(3, 4, kernel_size=3, padding=1).eval().to(dev)
out = probe(torch.zeros((1, 3, 16, 16), device=dev))
DEVS = []
DEVS = [torch.device(f'cuda:{i}') for i in range(torch.cuda.device_count()) if _cuda_execution_probe(i)]
DEVS = [torch.device('cpu')]
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
base = Path('/kaggle/input')
LABEL_COLS = TARGETS + [t + '__conf' for t in TARGETS]
cands = []
head = pd.read_csv(c, nrows=1)
lab = pd.DataFrame([extract(r) for r in train_df['Report'].fillna('')])
lab = lab.set_index('StudyInstanceUID')
src = find_label_table()
tab = pd.read_csv(src).set_index('StudyInstanceUID')
missing = [c for c in LABEL_COLS if c not in tab.columns]
hit = lab.index.intersection(tab.index)
ROOT = find_root()
IMG = CACHE_IMG
info = {k.strip(): v for k, v in (l.split(':', 1) for l in fh if ':' in l)}
avail = available_gb()
budget = min(avail * CACHE_FRACTION, CACHE_BUDGET_MAX_GB)
n_total = n_study + max(n_test, int(TEST_SHARE * n_study))
per_slice = n_total * N_SLOT * IMG * IMG
afford = int(budget * 1024 ** 3 // max(per_slice, 1))
groups = max(1, min(N_GROUP_MAX, afford
