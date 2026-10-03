# Source: kaggle notebook `rsna-knee-baseline-v1`

## Narrative (markdown cells)
# Twelve findings from one knee MRI

Each study is a set of MRI series acquired in one session, and the task is to give it
twelve probabilities: anterior cruciate and medial collateral ligament injury, medial and
lateral meniscal tear, osteoarthritis in each of the three compartments, joint effusion,
synovitis, Baker's cyst, bone contusion, and fracture.

The sections are ordered by how the decisions constrain each other: what the score rewards
decides how predictions are combined, where the targets come from decides what can be
trained, and what the scanner recorded decides what the encoder is shown.

> **On the two label sources.** §2 describes two readers for one job: a rule extractor,
> defined in full below, and a language model reading the same reports, whose output is a
> public table attached as a dataset. With the table mounted it supplies the targets,
> without it the extractor does, and every cell after that is unchanged.

## 1. What the score rewards

The score is the unweighted mean of twelve per-label ROC AUCs:

$$\text{Score} \;=\; \frac{1}{12}\sum_{i=0}^{11} \mathrm{AUC}_i .$$

Three consequences follow, and each removes a design choice.

**Only order matters.** $\mathrm{AUC}_i$ is invariant under any strictly increasing map of
the scores for label $i$, so calibration and thresholds are worth nothing. It also fixes
how to combine models: averaging raw probabilities lets whichever model is most confident
dominate, whereas averaging *ranks* combines the only information the metric reads.

**Every label costs the same.** Write $M$ for the mean AUC a good model could reach. A
label left at chance contributes $0.5$ instead of roughly $M$, forfeiting $(M-0.5)/12$ of
the final score however well the other eleven do — at $M = 0.85$, $0.029$. Rare findings
deserve *more* attention than common ones, because a rare finding is where a model most
easily ends up at chance.

**Prevalence drifts are survivable, thresholds are not.** AUC is in expectation invariant
to the positive rate, and the competition states prevalence is not guaranteed to match
across the training, public and final sets. One cutoff survives below — the graded targets
are binarised at their midpoint so that a held-out AUC can be computed at all — and it
decides which epoch and configuration are kept, never a submitted score.

## 2. Where the targets come from

Only a small subset of training studies carry the twelve per-condition labels. Every
training study carries the original radiology report, and the data description invites
deriving labels from it.

The decisive fact is in the schemas rather than the prose: `train.csv` has a `Report`
column and `test.csv` does not. Text is available when fitting and absent when predicting.
That rules out a fusion model with a text branch — at inference it would have nothing to
read — and leaves the reports usable only as training targets, as an auxiliary signal
dropped at inference, or as a weight on how confidently a study could be read. This
notebook takes the first and the third: a multilingual rule extractor reads each report
clause by clause, deciding for each finding whether the clause asserts, negates or hedges
it, and emits a score with a confidence. The confidence becomes a sample weight, so a study
whose report says nothing about synovitis pulls on that head far less than one that names it.

**Two readers.** A lexicon matches morphology, so its failure mode is silence rather than
error, and silence is measurable without ground truth: for each (report, finding) pair, ask
only whether anything matched at all. That rate needs no annotations, so it runs on every
study, and tagged by language it says *where* the vocabulary is thin. Here the misses are
concentrated — one language is covered far better than the other eight, and the gap falls on
findings a knee report almost always comments on. Enumerating morphology for nine languages
is the wrong instrument for that; reading the sentence is the right one, and a language model
reads it, asked for the same twelve findings in the same graded form. The annotated studies
decide between the readers, paired on the same studies, and the difference is large and
one-sided in the direction the coverage rate predicts. So the pipeline prefers a mounted
table of model-read labels when present and runs the lexicon when not; both emit the same
columns, and a partial table falls back per study rather than per run.

Two details matter more than either reader's internals.

**Reports are graded, annotations are thresholded.** The reporting radiologist and the
annotator do not share a threshold. A report saying *small joint effusion* may sit against
a negative annotation, because the annotator marked only effusions they judged significant.
A rule of the form *term present $\Rightarrow$ positive* is wrong by construction; grading
the mention — trace, unqualified, marked — is right and costs nothing, because §1
established that only order is read.

**Derived labels are not independent across studies.** A report shared verbatim by several
studies yields one target vector for all of them, which must be respected when splitting;
§7 does.

### Reading a report in nine languages

**No language is identified.** Every cue lexicon carries all nine languages at once and
each clause is tested against the union. Routing first means committing to a guess before
any evidence is read, and the cheap guess — substring tests, `'the '` for English, `'la '`
for French — fails badly, because `la` is as common in Spanish as in French and whichever
test runs first swallows both. Pooling costs little, since Greek and Cyrillic cues cannot
collide with Latin-script ones and the Latin-script vocabularies of interest are close
enough that a shared cue is usually right. The price is paid in coverage instead.

**Normalise, then segment, then scope.** Case, diacritics and separators are folded first,
which also repairs a codepoint problem: many Greek reports spell mu with MICRO SIGN U+00B5
rather than U+03BC, and NFKD maps one onto the other. Text is then split into clauses, with
a heading line attached to the value beneath it, because a report reading `Fractures :`
then `Aucune.` states one thing across two lines and any method that splits them reads a
negation as a positive.

**Assertion, negation, hedge.** Negation is not an edge case: for several findings most
mentions are negative, since a report lists what was checked and found intact. Explicit
normality counts as negation — *ligamentos cruzados y colaterales dentro de límites
normales* is evidence of absence, not absence of evidence — except where a tear or a high
grade is named in the same breath.

**Stems behind phrases.** Four targets need an anatomy word and a pathology word together.
A lexicon of complete phrases carries most matches but cannot survive morphology: Turkish
suffixes possessives onto the noun, Croatian and Greek decline it. Where the phrase fails,
a second pass matches a stem and requires a side qualifier within a *character* window,
which handles inflection without enumerating it, and handles word order — which puts the
side adjective before the noun in English and after it in Greek.

**Why coverage decides and agreement does not.** A rule that never fires raises no error;
in a binary extractor it emits a negative, indistinguishable from a confident one, and a
lexicon complete in English and thin in Greek looks like a corpus where Greek patients have
fewer findings. The obvious check — agreement with the per-condition annotations — measures
the right thing on far too few studies. The Hanley–McNeil standard error of an AUC $A$ with
$n_p$ positives and $n_n$ negatives,

$$
\mathrm{SE}(A)=\sqrt{\frac{A(1-A)+(n_p-1)(Q_1-A^{2})+(n_n-1)(Q_2-A^{2})}{n_p\,n_n}},
\qquad
Q_1=\frac{A}{2-A},\quad Q_2=\frac{2A^{2}}{1+A},
$$

at $A\approx0.8$ and a handful of positives among a few dozen studies lands near $0.09$ — a
95% interval of roughly $\pm0.17$ — far wider than the differences between two lexicons it would be asked to
separate. The silence rate has no such limit, so it is what points at the missing
vocabulary and what changes to the lexicon are judged on.

## 3. Reading the acquisition

`train_series.csv` describes each series with an anatomical plane and two binary flags,
`Fluid_Sensitive` and `Fat_Suppression`. The names denote two physically independent
properties — and that independence is what the delivered columns do not have: across the
training series the two agree on every row, so as given they carry one axis rather than
two. That is the first reason to recover both from the header.

*Fluid sensitivity* is a property of the **contrast weighting**, set by repetition time
$T_R$ and echo time $T_E$:

$$
\text{weighting} \;=\;
\begin{cases}
T_1 & T_R \lesssim 800\ \text{ms}\\
T_2 & T_R \gtrsim 800\ \text{ms},\ T_E \gtrsim 60\ \text{ms}\\
\text{PD} & T_R \gtrsim 800\ \text{ms},\ T_E \lesssim 60\ \text{ms}
\end{cases}
$$

Fluid is bright on $T_2$, intermediate on proton density, dark on $T_1$. Gradient echo
breaks the rule — its $T_R$ is short by design — so it is settled by `ScanningSequence`
first. *Fat suppression* is a **preparation** applied on top of any weighting, and is what
makes marrow oedema conspicuous. Both are read from `SeriesDescription`, `SequenceName` and
`ScanOptions` where the protocol names them, and from $T_R$ and $T_E$ where it does not.

### Which sequences to show the model

A knee is read in three planes because the structures run in different directions:
cruciate ligaments obliquely, best seen sagittally; collateral ligaments and the meniscal
body coronally; patellar cartilage and the retinacula axially. Crossing plane with the two
acquisition axes gives the slots below, chosen so each of the twelve findings has at least
one sequence that shows it well.

| slot | plane | weighting | fat sat | what it carries |
|---|---|---|---|---|
| `SAG_FLUID_FS` | sagittal | PD / T2 | yes | meniscal tears, marrow oedema, effusion |
| `COR_FLUID_FS` | coronal | PD / T2 | yes | collateral ligaments, meniscal body, oedema |
| `AX_FLUID_FS` | axial | PD / T2 | yes | patellofemoral joint, synovium, effusion |
| `SAG_FLUID_NOFS` | sagittal | PD / T2 | no | meniscal morphology at high contrast-to-noise |
| `COR_T1` | coronal | T1 | no | marrow architecture, cartilage and bone outline |
| `SAG_T1` | sagittal | T1 | no | anatomy, chronic change |

A study rarely has all six; a per-slot presence mask carries the absences into the head,
which §6 uses.

## 3b. What order the slices are in

A series is a directory of files, and the obvious way to walk it is to sort the file names.
That is wrong here, and wrong in a way that produces no error. The file name is the SOP
Instance UID, assigned to be unique rather than ordered, so sorting by it yields a sequence
uncorrelated with anatomy — measured on a series from this corpus, the rank correlation
between file-name order and physical position is $\rho \approx 0.01$. Three things
downstream depend on that order: three adjacent slices as three channels become three
unrelated cross-sections; the middle of the stack becomes a random subset; and reversing
the order to normalise laterality does nothing at all.

The true order is recoverable exactly from geometry every slice carries.
`ImageOrientationPatient` gives the in-plane axes $\hat{r}_x, \hat{r}_y$ and
`ImagePositionPatient` the position $p$ of the first voxel, so

$$\hat{n} \;=\; \hat{r}_x \times \hat{r}_y, \qquad k \;=\; p \cdot \hat{n},$$

and $k$ increases monotonically along the stack. Because $k$ is signed and expressed in
patient coordinates, the stack has a fixed direction along the body's left-right axis —
which is what the laterality normalisation of §5 reverses. `InstanceNumber` is the fallback
where the geometry tags are missing; it usually tracks $k$ up to sign, but interleaved and
multi-echo acquisitions number slices in an order that is not the order they occupy in
space, and it is not signed in patient coordinates.

## 4. Sampling: how many millimetres one pixel is allowed to be

A DICOM slice of $N \times N$ pixels with spacing $s$ mm/pixel covers $Ns$ millimetres of
anatomy. Both vary across this corpus, so a fixed-pixel resize hands the encoder images
whose physical scale differs by a factor of several. But scale normalisation is only half
of it; the other half is a hard limit.

**A feature narrower than two pixels does not survive the resize.** To represent a
structure of width $d$ millimetres the pixel pitch must satisfy $s_{\text{eff}} \le d/2$,
the Nyquist condition applied to the resampling grid. A meniscal tear is one to three
millimetres, so at $d = 1$ mm the pitch must be at most $0.5$ mm — and if it is not, no
capacity downstream recovers the signal, because it was destroyed before the first
convolution. This is a property of the resize, not of the network.

Cropping to a constant physical extent $L$ and resampling to $P$ pixels fixes the pitch:

$$n \;=\; \Big\lfloor \frac{L}{s} \Big\rceil \ \text{pixels}, \qquad
s_{\text{eff}} \;=\; \frac{L}{P}\ \ \text{mm/pixel}, \qquad
\text{token} \;=\; 14\,s_{\text{eff}}\ \ \text{mm}.$$

The crop must be smaller than the smallest field of view or it silently does nothing: if
$L/s$ exceeds the image width the crop cannot be taken and that series passes through
unnormalised, with no error. $L = 130$ mm is below the acquired field of view of almost
every series here while still containing the joint. The resize target then follows from the
tear width rather than convention — at $L = 130$ mm an input of $224$ gives $0.580$
mm/pixel, above the bound for a 1 mm feature, while $336$ gives $0.387$ mm/pixel and puts a
$14$-pixel patch token at $5.4$ mm.

**Intensity needs the same treatment**, MR having no absolute scale. Each series is
normalised to its own 1st and 99th percentile — over the sampled stack rather than per
slice, so slices keep their relative contrast, and percentiles rather than 

## Key configuration lines from code
base = Path("/kaggle/input")
hit = next(d.rglob(name), None)
TARGETS = [
text = text.translate(_PRE).lower()
text = unicodedata.normalize("NFKD", text)
text = "".join(ch for ch in text if not unicodedata.combining(ch))
text = text.replace("­", "")                    # soft hyphen
text = re.sub(r"[_\-/\\]+", " ", text)
text = re.sub(r"[ \t]+", " ", text)
norm = normalize(text)
raw = [c.strip() for c in _SENT_SPLIT.split(norm) if c and c.strip()]
merged = []
out = []
NEGATION = _rx(
NORMALITY = _rx(
UNCERTAIN = _rx(
TEAR = _rx(
DEGEN = _rx(
INJURY = _rx(
ANAT = {
OA_EVIDENCE = _rx(
COMPARTMENT = {
DIRECT = {
DECOY = {
PAIRED = {"ACL", "MCL", "Medial Meniscus", "Lateral Meniscus"}
OA_TARGETS = {"Medial OA", "Lateral OA", "PF OA"}
STEM_MENISCUS = _rx(r"menisc\w*", r"menisk\w*", r"μηνισκ\w*", r"мениск\w*")
STEM_CRUCIATE = _rx(r"cruciate", r"cruzado", r"croise", r"kruisband", r"kreuzband",
STEM_COLLATERAL = _rx(r"collateral\w*", r"colateral\w*", r"kollateral\w*",
SIDE_MEDIAL = _rx(r"\bmedial\w*", r"\bmedyal\w*", r"\bmedijaln\w*", r"\bmediaal\w*",
SIDE_LATERAL = _rx(r"\blateral\w*", r"\bextern[oa]\w*", r"\bexterne\w*", r"\bdis\b",
SIDE_ANTERIOR = _rx(r"\banterior\w*", r"\bant\b", r"\bon\b", r"\bprednj\w*",
SIDE_POSTERIOR = _rx(r"\bposterior\w*", r"\bpost[eé]rieur\w*", r"\bposteriore\w*",
STEM_FRACTURE = _rx(r"fractur\w*", r"fraktur\w*", r"fractuur\w*", r"\bfract\b",
STEM_OA_COMPARTMENT = _rx(r"compartment\w*", r"compartimento\w*", r"compartiment\w*",
best = None
best = d if best is None else min(best, d)
STEM_RULES = {
SEV_LOW = _rx(
SEV_HIGH = _rx(
GLOBAL_OA = _rx(
DEGENERATIVE_MARROW = _rx(
TRAUMA = _rx(
other = _distance(clause, self.stem, self.contrary, self.window)
own = _distance(clause, self.stem, self.side, self.window)
CONTRARY = {"ACL": SIDE_POSTERIOR, "MCL": SIDE_LATERAL}
ANAT_MATCH = {
COMPARTMENT_MATCH = {
DIRECT_MATCH = {
high = SEV_HIGH.search(clause) is not None
low = SEV_LOW.search(clause) is not None
context_bonus=None):
n_pos = n_neg = n_unc = 0
best = 0.0
pol = _polarity(c, m.end())
best = max(best, w)
best = max(best, 0.30)
score = min(0.95, 0.50 + 0.42 * best + 0.03 * min(n_pos, 3))
conf = min(1.0, 0.55 + 0.15 * n_pos)
score = max(0.04, 0.20 - 0.04 * n_neg)
conf = min(0.9, 0.45 + 0.12 * n_neg)
cls = clauses(report)
out = {}
path_paired = _rx(TEAR.pattern, DEGEN.pattern, INJURY.pattern)
context_penalty=DEGENERATIVE_MARROW,
context_bonus=TRAUMA)
g_hits = [c for c in cls if GLOBAL_OA.search(c) and _polarity(c, 0) == "positive"]
gscore = 0.50 + 0.42 * max(_severity(c) for c in g_hits)
SEED = 2026
TARGETS = ["ACL", "MCL", "Medial Meniscus", "Lateral Meniscus", "Medial OA",
CROP_MM = 130.0
CACHE_IMG = 336
GROUP = 3                  # slices per encoder input, stacked as the three channels
N_GROUP_MAX = 1
CACHE_FRACTION = 0.45      # share of free memory the pixel cache may take
CACHE_BUDGET_MAX_GB = 24.0 # hard ceiling regardless of what the machine reports
CACHE_BUDGET_GB = 12.0     # only the fallback, for a machine with no /proc/meminfo
TEST_SHARE = 0.30          # floor on the test corpus relative to the training one, since
HDR_THREADS = 16
PIX_THREADS = 12
ORDER_THREADS = 32         # slice-ordering is latency-bound on the mount, not CPU-bound
ORDER_BUDGET_S = 5400
RUNS = [
EPOCHS = 10
BATCH_STUDIES = 8          # a study is a bag of up to N_SLOT slot images
AUG_ROT_DEG = 8.0          # rigid jitter; see augment() for why neither flip is used
AUG_SCALE = 0.08
AUG_SHIFT = 0.05
AUG_INTENSITY = 0.10
LAT_MIN_OFFSET_MM = 20.0   # inside this the side is not readable from geometry; see
SLICE_BAND = (0.20, 0.80)  # fraction of the ordered stack read_slot samples across
RULES_NATIVE = {"order": "normal", "lat": "centre",
RULES_LEGACY = {"order": "dominant_axis", "lat": "corner_x",
RULES = dict(RULES_NATIVE)
LEGACY_LAT_OFFSET_MM = 5.0   # the dead zone the legacy laterality rule was fitted with
LR_HEAD = 1e-3
LR_BACKBONE = 8e-6         # the encoder is adapted, not retrained
UNFREEZE_LAST = 6          # trainable transformer blocks, from the output end
WEIGHT_DECAY = 0.02
EVAL_BATCH = 8
TIME_BUDGET = 8.0 * 3600
SLOTS_RECOVERED = [
SLOTS_PUBLIC = [
SLOT_SCHEME = os.environ.get("SLOT_SCHEME", "recovered")
SLOTS = SLOTS_PUBLIC if SLOT_SCHEME == "public" else SLOTS_RECOVERED
N_SLOT = len(SLOTS)
POOL_PARTS = {"cls_mean": 2, "cls_mean_focal": 3}
SLOT_PRIOR_TABLE = {
SLOT_PRIOR_STRENGTH = 0.55
FATSAT_OPTS = {"FS", "FATSAT", "FAT_SAT", "FSAT"}
hits = []
LABEL_COLS = TARGETS + [t + "__conf" for t in TARGETS]
cands = []
head = pd.read_csv(c, nrows=1)
lab = pd.DataFrame([extract(r) for r in train_df["Report"].fillna("")])
lab = lab.set_index("StudyInstanceUID")
src = find_label_table()
tab = pd.read_csv(src).set_index("StudyInstanceUID")
missing = [c for c in LABEL_COLS if c not in tab.columns]
hit = lab.index.intersection(tab.index)
ROOT = find_root()
IMG = CACHE_IMG            # kept as the name the pixel reader and cache use
info = {k.strip(): v for k, v in
avail = available_gb()
budget = min(avail * CACHE_FRA
