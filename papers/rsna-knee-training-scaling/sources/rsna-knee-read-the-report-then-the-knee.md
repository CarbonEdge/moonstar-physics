# Source: kaggle notebook `rsna-knee-read-the-report-then-the-knee`

## Narrative (markdown cells)
# Twelve findings, fifty-eight labels, four thousand reports

![Report-supervised knee MRI ensemble](attachment:rsna-knee-report-to-image-hero.jpg)

A knee MRI study here has to be given twelve probabilities — anterior cruciate and medial
collateral ligament injury, medial and lateral meniscal tear, osteoarthritis in each of
the three compartments, effusion, synovitis, Baker's cyst, bone contusion, fracture — and
the score is the unweighted mean of the twelve ROC AUCs.

The decisive fact about this dataset is not in the images. It is in `train.csv`:

| | studies | carry the twelve labels | carry a radiology report |
|---|---|---|---|
| train | 4 407 | **58** | 4 407 |
| test | — | — | **none — there is no `Report` column** |

Fifty-eight labelled studies cannot train an imaging model, and the reports that could
supply the missing four thousand are unavailable at prediction time. So the pipeline is
forced into one shape: **read the reports into targets, fit a pure imaging model against
them, and throw the text away.** Everything downstream — which slices to decode, how large
to make them, which encoder to adapt — is bounded by how well that first step is done.

This notebook is organised in the order the decisions constrain each other.

1. What the score rewards, and what that removes from the design.
2. Where the targets come from — a nine-language report reader, and the two ways to tell
   whether it works when only 58 studies can check it.
3. What the scanner recorded — recovering the acquisition protocol from DICOM headers.
4. Geometry — slice order, physical scale, and which knee was scanned.
5. Reading the pixels once.
6. Turning six views into twelve decisions.
7. Validating without fooling yourself.
8. Three arms, combined the only way the metric permits.

Every analytical number below is computed by the cell above it. Official Kaggle results in
the scorecard are explicitly labelled as external leaderboard evidence.

> **Highest verified public score for this notebook: 0.906.** Version 52 is the
> completed Kaggle row (submission 55399732) that establishes that result; its submitted
> artifact was bitwise matched to the audited 20% RadImageNet rank blend. Version 46
> established 0.899, and Version 49 independently tested the five-fold EfficientNet-B3
> contribution at 0.898. Later guarded candidates remain diagnostic until Kaggle returns
> a completed official score.

| reproducible public run | score | evidence or inference change |
|---|---:|---|
| Pilkwang V15 public anchor | 0.891 | original public 20-member ensemble |
| This notebook V14 | **0.894** | Fracture max + OOF-selected target-wise rank blend |
| This notebook V46 | **0.899** | exact audited specialist artifact; completed Kaggle row |
| This notebook V49 | **0.898** | guarded five-fold EfficientNet-B3 rank contribution |
| This notebook V52 | **0.906** | independent RadImageNet ResNet-50, 20% rank vote; completed Kaggle row 55399732 |
| external Yash Bishnoi reference | **0.903** | inspected five-fold B3 MIL recipe; not this notebook's score |

The scorecard separates completed official rows from local validation and from other
authors' public references. The cells below preserve that boundary: OOF diagnostics can
select or reject an arm, but only a completed Kaggle submission can change the verified
public score above.

If this evidence-first walkthrough saves you time, an upvote helps other competitors
find the reproducible result.

## 1. What the score rewards

$$\text{Score} \;=\; \frac{1}{12}\sum_{i=0}^{11} \mathrm{AUC}_i$$

Three consequences follow directly, and each one removes a design choice rather than
adding one.

**Only order matters.** $\mathrm{AUC}_i$ is invariant under any strictly increasing map of
the scores for label $i$. Calibration is worth nothing here, and so is any fixed
threshold. It also settles how to combine models: averaging raw probabilities lets
whichever arm happens to be most confident dominate, while averaging *ranks* combines the
only information the metric reads. Every combination in §8 is a rank mean.

**Every label costs the same.** Write $M$ for the mean AUC a good model reaches. A label
left at chance contributes $0.5$ instead of roughly $M$, forfeiting

$$\frac{M-0.5}{12}$$

no matter how well the other eleven do. At $M=0.85$ that is $0.029$ — larger than the gap
between neighbouring places on a mature leaderboard. So a rare finding deserves *more*
attention than a common one, because a rare finding is where a model most easily ends up
at chance. That is why §2 spends its effort on the findings the reports mention least,
not on the ones they mention most.

**Prevalence drift is survivable; thresholds are not.** AUC is, in expectation, invariant
to the positive rate, and the data description warns that prevalence need not match across
the training, public and private sets. That would be fatal for an accuracy-like metric. It
is not fatal here — but it does mean one cut has to be named and watched. The report-derived
targets below are graded, not binary; to compute an AUC against them at all they are
binarised at their midpoint for validation only. That cut chooses epochs and arms. It never
reaches a submitted score.

## 2. Where the targets come from

Every training study carries the radiology report written when it was read, and the data
description invites deriving labels from it. The structural fact that decides how is in the
schemas rather than in the prose: `train.csv` has a `Report` column and `test.csv` does
not. Text is available when fitting and absent when predicting. That rules out a fusion
model with a text branch — at inference it would have nothing to read — and leaves the
reports doing two jobs:

1. supplying the training targets, and
2. saying how confidently each one could be read, which becomes a per-finding sample
   weight.

Both matter. A study whose report never mentions synovitis should pull on the synovitis
head far more weakly than one that names it, and a loss that cannot express that trains
every silence as a confident negative.

### Nine languages, one lexicon

The corpus is written in nine languages across three scripts. The extractor is built here
in-line rather than attached as a file, for two reasons: it runs over the whole corpus in
seconds, so there is nothing to save by precomputing; and a notebook that ships its own
labels cannot quietly train against a stale copy of them.

**No language is identified.** Every cue list below carries all nine at once and each
clause is tested against the union. Routing first would mean committing to a guess before
any evidence is read, and the cheap guess fails badly here — `la` is as common in Spanish
as in French, and whichever substring test runs first swallows both. Pooling costs little
in exchange: Greek and Cyrillic cues cannot collide with Latin-script ones at all, and
among the Latin-script languages the vocabulary of interest is close enough that a shared
cue is usually right. The price is paid in coverage instead — a phrasing no listed language
contributes stays unmatched — and coverage is the thing §2.2 measures.

**Normalise, then unwrap, then segment, then scope.** Case, diacritics and separators are
folded first, which also repairs a real codepoint problem: many Greek reports spell mu with
the MICRO SIGN `U+00B5` rather than `U+03BC`, and NFKD maps one onto the other. Then the
lines are unwrapped — see below — then split into clauses, with a heading line attached to
the value beneath it, because a report that reads `Fractures :` and then `Aucune.` states
one thing across two lines.

**Assertion, negation, hedge.** Negation is not an edge case here. For several findings
*most* mentions are negative, because a report lists what was checked and found intact.
Explicit normality counts as absence — *ligamentos cruzados y colaterales dentro de límites
normales* is evidence of absence, not absence of evidence — except where a tear or a high
grade is named in the same breath.

**Grade, do not threshold.** §1 established that only order is read. So a mention is scored
by its emphasis — trace, unqualified, marked — and never binarised.

### 2.1 Four rules that are not obvious

Most of a lexicon is vocabulary, and vocabulary is dull work that pays. Four rules are not
vocabulary, and each of them fixes an error that a term list cannot reach. All four are
behind flags in `FEATURES`, and §2.2 turns them off one at a time and re-measures.

**Unwrap before splitting.** A large share of these reports arrive hard-wrapped at a fixed
column, so a sentence is broken across two lines with no punctuation at the break.
Splitting on newlines then severs a finding from its anatomy:

> `Rotura compleja degenerativa del cuerno anterior, cuerpo, cuerno posterior y parte de la raíz`
> `meniscal posterior del menisco lateral con extrusión asociada.`

The first line says *tear* and names no structure; the second names the lateral meniscus
and says nothing about a tear. Neither clause carries a finding on its own, and the study
comes out silent on a meniscus that the report describes as complexly torn. A line that
does not end in sentence punctuation is a continuation, not a statement.

**Scope negation by direction, and anchor it on the pathology word.** Read at clause scope,

> `Subchondral insufficiency fracture at the medial tibial plateau without articular surface collapse.`

is a denial: it contains *without*. It is in fact an assertion — *without* governs what
follows it, and the fracture precedes it. This is the house style of one of the larger
reporting sites in this corpus, so the error is systematic rather than occasional, and it
falls on `Fracture`, one of the rarest targets. Direction alone is not enough either. In

> `Medial meniscus is not torn.`

the negator stands *after* the noun and before the verb, so scoping the test from the
anatomy match reads the sentence as an assertion. The negator governs the finding, so the
test is anchored on the pathology word — *torn* — not on *meniscus*.

**Let an unlocalised cartilage statement reach all three compartments.** Osteoarthritis is
rarely written as "osteoarthritis". It is written as cartilage loss, chondrosis, a
chondromalacia grade, joint space narrowing, or osteophytes — and often without naming a
compartment at all. `Tricompartmental osteoarthritis`, `gonarthrose`, `Incipient OA of all
three compartmens` are the house styles, not `chondropathy of the medial femorotibial
compartment`. A rule that requires a compartment phrase before it will fire leaves three
quarters of the corpus silent on the three OA targets. So a cartilage statement is
attributed by what else its clause names — *medial* next to a tibiofemoral structure sends
it to the medial compartment, *patella* or *trochlea* to the patellofemoral one — and a
statement that localises to nothing counts for all three at a discount, unless that
compartment was separately and explicitly cleared.

**Read numeric grades on the right scale.** A grade is the most precise thing a knee report
says, and it means opposite things in different places. Grade 3 of a *meniscus* is signal
reaching the articular surface, which is a tear by definition; grades 1 and 2 are
intrasubstance change that is not. A *ligament* runs the other way — grade 1 is a stretch,
grade 2 a partial tear. Folding both into one pathology vocabulary scores a degenerate
meniscus like a torn one and throws away the ordering the metric is built on.

### 2.2 How an extractor like this is validated

This is the part that decides whether any of the above is worth trusting, and it is harder
than writing the rules, because the obvious measurement cannot carry the weight.

**The dangerous failure is silent.** A rule that never fires does not raise an error — it
emits a negative, indistinguishable from a confident one. A lexicon complete in English and
thin in Greek does not look broken; it looks like a corpus in which Greek patients have
fewer findings. And the error is not random: language tracks the reporting institution,
which tracks the scanner and the population, so a gap in one language is a bias aligned with
a site, not noise that averages out.

**Gauge one — agreement, on the 58 annotated studies.** For each target, compare the
extracted score against the annotation and read the AUC. This measures exactly the right
thing and is nearly useless for tuning, because the subset is tiny. The Hanley–McNeil
approximation for the standard error of an AUC $A$ with $n_p$ positives and $n_n$ negatives,

$$\mathrm{SE}(A)=\sqrt{\frac{A(1-A)+(n_p-1)(Q_1-A^{2})+(n_n-1)(Q_2-A^{2})}{n_p n_n}},\qquad
Q_1=\frac{A}{2-A},\quad Q_2=\frac{2A^{2}}{1+A},$$

at $A\approx0.85$ with nine positives among 58 studies lands near $0.083$, so a 95% interval
spans roughly $\pm0.16$. Competitions are decided by differences an order of magnitude
smaller. Choosing between two lexicons on a single one of these numbers is choosing by coin
flip, and it will feel like signal every time. The intervals are drawn below so that this
is visible rather than stated.

**Gauge two — coverage, on all 4 407 reports.** For each (study, target) pair, record
whether *any* rule fired — assertion, negation or hedge. The **silence rate** is the fraction
where none did. It needs no labels, so it runs on the whole corpus rather than on the
annotated handful, and it points straight at missing vocabulary.

| | measures | sample | can decide |
|---|---|---|---|
| agreement | is a fired rule *right* | 58 | whether a target's labels are usable at all |
| silence | does a rule *fire* | 4 407 | which finding to work on next |

Neither substitutes for the other, and the second is the one to steer by. A common finding
that is silent in one language and not another is a lexicon gap. A rare finding that is
silent nearly everywhere is simply rare, and silence there is correct.

**One limit worth naming.** The 58 annotations were read from the images; the reports were
w

## Key configuration lines from code
TARGETS = [
text = text.translate(_PRE).lower()
text = unicodedata.normalize("NFKD", text)
text = "".join(ch for ch in text if not unicodedata.combining(ch))
text = text.replace("­", "")
text = re.sub(r"[_\-/\\]+", " ", text)
text = re.sub(r"[ \t]+", " ", text)
out = []
norm = normalize(unwrap(text) if FEATURES["unwrap"] else text)
raw = [c.strip() for c in _SENT_SPLIT.split(norm) if c and c.strip()]
merged = []
FEATURES = {
PRE_NEG = _rx(
POST_NEG = _rx(
NEGATION = _rx(PRE_NEG.pattern, POST_NEG.pattern, r"\bunremarkable\b")
NEG_WINDOW = 90
NORMALITY = _rx(
NORMAL_PHRASE = _rx(
UNCERTAIN = _rx(
TEAR = _rx(
DEGEN = _rx(
INJURY = _rx(
best = None
best = n
ANAT = {
OA_EVIDENCE = _rx(
TF_SITE = _rx(
PF_SITE = _rx(
SIDE_MEDIAL = _rx(
SIDE_LATERAL = _rx(
SIDE_ANTERIOR = _rx(
GLOBAL_OA = _rx(
DIRECT = {
DECOY = {
PAIRED = {"ACL", "MCL", "Medial Meniscus", "Lateral Meniscus"}
OA_TARGETS = ["Medial OA", "Lateral OA", "PF OA"]
PLURAL_MENISCI = _rx(
ANY_SIDE = _rx(SIDE_MEDIAL.pattern, SIDE_LATERAL.pattern)
STEM_MENISCUS = _rx(r"menisc\w*", r"menisk\w*", r"μηνισκ\w*", r"мениск\w*")
STEM_CRUCIATE = _rx(r"cruciate", r"cruzado", r"croise", r"kruisband", r"kreuzband",
STEM_COLLATERAL = _rx(r"collateral\w*", r"colateral\w*", r"kollateral\w*",
STEM_FRACTURE = _rx(r"fractur\w*", r"fraktur\w*", r"fractuur\w*", r"\bfract\b",
POSTERIOR_ONLY = _rx(r"\bpcl\b", r"\blcp\b", r"\bhkb\b", r"\bacb\b",
LATERAL_COLL_ONLY = _rx(r"\blcl\b", r"\bfcl\b", r"lateral collateral",
STEM_RULES = {
ANAT_MATCH = {t: _Matcher(ANAT[t], *STEM_RULES[t]) for t in PAIRED}
DIRECT_MATCH = {
SEV_LOW = _rx(
SEV_HIGH = _rx(
GRADE_HIGH = re.compile(r"grade?[ao]?\s*(3|4|iii|iv)\b|icrs grade (iii|iv|3|4)|"
DEGENERATIVE_MARROW = _rx(
TRAUMA = _rx(
SYNOVIAL_PROXY = _rx(
high = SEV_HIGH.search(clause) is not None
low = SEV_LOW.search(clause) is not None
score = min(0.97, 0.50 + 0.45 * best + 0.015 * min(n_pos, 3))
conf = min(1.0, 0.55 + 0.15 * n_pos)
score = max(0.04, 0.20 - 0.04 * n_neg)
conf = min(0.9, 0.45 + 0.12 * n_neg)
tear = TEAR.search(clause) is not None
base = 1.0
base = 0.95 if g >= 3 else 0.30
base = 0.35
base = 0.45
base = 0.85 if g >= 2 else 0.30
base = 0.40
base = 0.55
base = min(1.0, base * 1.2)
anat_rx = ANAT_MATCH[tgt]
path_rx = _rx(TEAR.pattern, DEGEN.pattern, INJURY.pattern)
meniscus = "Meniscus" in tgt
n_pos = n_neg = n_unc = 0
best = 0.0
hit = anat_rx.search(c)
hit = PLURAL_MENISCI.search(c)
span = (pm.start(), pm.end()) if pm is not None else None
pol = _polarity(c, span)
best = max(best, _paired_weight(c, meniscus))
best = max(best, 0.45 * _paired_weight(c, meniscus))
context_bonus=None):
pol = _polarity(c, (m.start(), m.end()))
best = max(best, w)
best = max(best, 0.30)
acc = {t: {"pos": 0, "neg": 0, "unc": 0, "best": 0.0} for t in OA_TARGETS}
sev = _severity(c)
tf_med = _near(c, TF_SITE, SIDE_MEDIAL, 45)
tf_lat = _near(c, TF_SITE, SIDE_LATERAL, 45)
hits = []
g_best = max(g_best, sev if GLOBAL_OA.search(c) else sev * 0.7)
out = {}
score = max(score, 0.35)
cls = clauses(report)
context_penalty=DEGENERATIVE_MARROW, context_bonus=TRAUMA)
proxy = sum(1 for c in cls if SYNOVIAL_PROXY.search(c)
eff = out["Effusion"]
prior = 0.30 + 0.30 * max(0.0, (eff - 0.5) / 0.45) + 0.06 * min(proxy, 3)
base = Path("/kaggle/input")
ROOT = find_root()
STAGE_OK = {}
out = fn(*a, **k)
train_df = pd.read_csv(ROOT / "train.csv")
LAB = pd.DataFrame([extract(r) for r in train_df["Report"].fillna("")])
LAB = LAB.set_index("StudyInstanceUID")
GOLD = train_df.dropna(subset=TARGETS).set_index("StudyInstanceUID")[TARGETS]
pos = (LAB[TARGETS] > 0.5).mean()
sil = pd.Series({t_: float(((LAB[t_ + "__npos"] == 0) & (LAB[t_ + "__nneg"] == 0)).mean())
rng = np.random.default_rng(seed)
rows = []
AGREE = agreement(LAB).dropna(subset=["auc"])
gridspec_kw={"width_ratios": [1.25, 1]})
ax[0].hlines(y, o.lo, o.hi, color=ACC, lw=3, alpha=.35)
loc="left", fontsize=8)
ax[1].barh(np.arange(len(o2)), o2.values * 100, color=INK, alpha=.8, height=.65)
lab = pd.DataFrame([extract(r) for r in train_df["Report"].fillna("")])
lab = lab.set_index("StudyInstanceUID")
rows = [("all rules on", base_a, base_s, 0.0, 0.0)]
ABL = pd.DataFrame(rows, columns=["configuration", "macro AUC", "mean silence",
score = {k: len(rx.findall(n)) for k, rx in _STOP.items()}
best = max(score, key=score.get)
LANG = pd.Series([guess_language(r) for r in train_df["Report"].fillna("")],
index=train_df["StudyInstanceUID"])
SIL = pd.DataFrame({t: ((LAB[t + "__npos"] == 0) & (LAB[t + "__nneg"] == 0)).values
by_lang = SIL.groupby(LANG.reindex(SIL.index).values).mean() * 100
by_lang = by_lang.loc[LANG.value_counts().index.intersection(by_lang.index)]
gridspec_kw={"width_ratios": [1.7, 1]})
fontsize=7)
color="white" if v > 62 or v < 12 else INK)
CLAUSES = {u: clauses(r) for u, r in
sel = SIL[t_].values
named = np.array([names_it(u, t_) for u in SIL.index[sel]])
label="mentioned, missed")
fontsize=6.5)
dev = torch.device(f"cuda:{index}")
probe = nn.Conv2d(3, 4, kernel_size=3, padding=1).eval().to(dev)
out = probe(torch.zeros((1, 3, 
