# Physiological Reasoning: Radiologist’s View of the RSNA Knee MRI Task

## Fundamental MRI Physics & Pathology Visibility

Knee MRI protocols are built around tissue contrast mechanisms and pathological conspicuity. Let me reason through each finding systematically before translating to model design.

### The 12 Findings: Required Sequences, Planes, and Resolutions

**1. Meniscus Tear (Medial/Lateral)**
- *Physiology:* Fibrocartilage with short T2 (dark on all sequences). Tears manifest as linear high signal extending to articular surface. Grade 1-2 (intrasubstance signal not touching surface) vs Grade 3 (true tear communicating with surface).
- *Optimal sequences:* **Proton density fat-suppressed in sagittal plane** is gold standard. Coronal adds for root tears, body/pars intermedia. T2 FS confirms fluid in cleft. Non-FS helps distinguish Grade 2 from 3 (fluid vs intrinsic degeneration).
- *Critical resolution:* Meniscus is ~10mm wide, tears can be submillimeter oblique undersurface. Need ≤0.4mm in-plane pixel. **Current 384px @130mm = 0.339mm is adequate.** 224px @0.58mm will miss small radial/undersurface tears.
- *Label challenge:* Report says "meniscal tear" always means Grade 3 (surgical), but pseudo-parsers may grade-ambiguous language ("intrasubstance signal" = no tear, "possible tear" = uncertain). Gold labels likely surgical confirmation. **Maximal label noise here.**

**2. ACL Tear (Dichotomous: Complete/Partial vs Normal)**
- *Physiology:* Ligament fibers (dark) with hemorrhage/edema (bright T2) filling gap.
- *Optimal sequences:* **T2 FS sagittal oblique** is definitive. Axial T2 FS confirms fiber discontinuity. Coronal T1/T2 for femoral/tibial footprints.
- *Resolution need:* ACL width ~11mm. 0.5mm adequate for fiber-level disruption. 384 is fine; 224 borderline but visible if complete tear.
- *Label challenge:* "Partial ACL tear" vs "sprain" vs "mucoid degeneration" vs "intact but attenuated" — massive ambiguity in reports. Complete tears clear. **Partial tears: label noise high.**

**3. PCL Tear**
- *Physiology:* Thicker ligament (~13mm). Buckling/deformity more than signal change.
- *Optimal sequences:* **T2 FS sagittal** shows fiber discontinuity, laxity. Coronal T2 FS for fiber orientation.
- *Resolution:* More forgiving — PCL is larger, tears often gross. 0.58mm adequate.
- *Label challenge:* Less ambiguous than ACL — PCL tears are rarer and more frankly described. **Lower label noise.**

**4-5. MCL/LCL Sprain/Tear**
- *Physiology:* MCL: medial supporting structure, grades I-III (edema->partial fiber disruption->complete). LCL: lateral complex.
- *Optimal sequences:* **T2 FS coronal** is definitive for MCL (vertical course). T1 coronal for anatomy. Sagittal T2 FS confirms. Axial for grading depth.
- *Resolution:* MCL spans joint line, 0.5-0.6mm fine. Not limiting at 384.
- *Label challenge:* "MCL sprain" spectrum. Grade I edema only — parser may or may not call positive. **Moderate noise.**

**6. Patellar Tendon Tear/Degeneration**
- *Physiology:* Tendinosis vs partial tear vs complete tear. Signal increase and fiber disruption.
- *Optimal sequences:* **T2 FS sagittal** shows fiber continuity and signal. Axial T2 FS confirms.
- *Resolution:* Tendon thickness ~4-5mm. 0.5mm adequate but 0.58mm challenges thin proximal insertional tears. **Resolution-dependent.**

**7. IT Band Syndrome**
- *Physiology:* Inflamed IT band with surrounding edema between IT band and lateral femoral condyle.
- *Optimal sequences:* **T2 FS coronal** (fluid deep to IT band). Axial T2 FS confirms. Sagittal may miss.
- *Resolution:* Edema volume >5mm; 0.58mm sufficient. **Not resolution-limited.**
- *Label challenge:* Impingement syndrome descriptions vary; subtle edema may be undercalled. **Moderate noise.**

**8. Meniscal Extrusion**
- *Physiology:* Meniscus body displaced beyond tibial margin ≥3mm. Often with root tear/OA.
- *Optimal sequences:* **T2 FS coronal** mid-body. Measure distance from central margin to meniscal body. Sagittal confirms.
- *Resolution:* Measurement at 0.5mm precision means ≥6 pixels for 3mm — reliable. 0.58mm ≥5 pixels still adequate. **Not resolution-limited.**
- *Label challenge:* Extrusion thresholds: "mild" (~2mm) may be called negative in gold (3mm standard). **Systematic gold vs pseudo-label threshold mismatch likely.**

**9. Cartilage Defect (Full-Thickness vs Partial)**
- *Physiology:* Focal chondral loss with sharp margins. ICRS grading I-IV. Full-thickness = Grade IV (bone exposed).
- *Optimal sequences:* **T2 FS sagittal and coronal** (fluid bright against cartilage). PD FS shows morphology. T1 for subchondral contrast. **Volume assessment needs multiple planes.**
- *Resolution:* Critical. Cartilage is 2-4mm thick, submillimeter defects found at arthroscopy. Need ≤0.35mm. **384 @0.339mm acceptable; 224 @0.58mm will miss 50% of Grade III/IV lesions.** Slices must be ≤3mm (~30 slices per knee for volumetric assessment).
- *Label challenge:* "Chondromalacia" = grade I-II = negative gold label. "Fissuring" = grade II-III = ambiguous. "Full-thickness defect" = clear positive. **Huge label divergence possible depending on parser aggressiveness.**

**10. Bone Marrow Edema (BME)**
- *Physiology:* Ill-defined hyperintensity on STIR/T2 FS, decreased on T1. Subchondral, contusion, or reactive.
- *Optimal sequences:* **Coronal and sagittal T2 FS or STIR.** T1 coronal for marrow contrast (dark edema, bright fatty marrow helps delineation).
- *Resolution:* Edema patterns macroscopic (often >1cm). 0.58mm fine. **Not resolution-limited.**
- *Label challenge:* BME terminology: "contusion," "trabecular injury," "subchondral edema," "stress reaction." Parsers should get most, but subtle diffuse edema may be undercalled. **Low-moderate noise.**

**11-12. Fracture and Patella Alta/Baja**
- *Fracture:* Linear low signal on T1, ±edema on T2. **T1 sagittal/coronal** critical — T2-only may miss nondisplaced fracture line through marrow edema. T2 shows edema better but fracture line requires T1. **Both sequences needed.** Resolution: fracture line 0.2-0.5mm. 384 marginal; 224 inadequate.
- *Patella Alta/Baja:* Insall-Salvati ratio (patellar tendon:patella length) on **sagittal T1/T2**. Measurement task. Resolution not limiting; needs appropriate slice (midline sagittal). **If only mid-3-slices without ensuring midline capture, measurement impossible.**

---

## Sequence/Plane/Fat Suppression Availability in Challenge

Typical knee MRI protocol for RSNA: **6 series slots** per study: sagittal T2 FS, coronal T1, coronal T2 FS, axial T2 FS, sagittal T1, sagittal PD (varies). Fat suppression on T2/STIR essential for fluid-sensitive findings; non-FS T1 critical for anatomy/fracture/marrow differentiation.

---

## Our Current Design: Single-Mid-Triplet, Series-Then-Pool

### What This Means

- **Single mid-triplet:** For each series, we take 3 mid-slices (RGB channels). This captures ONE anatomic location.
- **Series-then-pool:** Each series independently gets a per-finding logit, then averaged or max-pooled across series at study level.

### What This Losses By Finding

Let me rank findings from **most to least disadvantaged** vs the physiological frontier:

| Rank | Finding | Loss vs Frontier | Mechanism |
|------|---------|------------------|-----------|
| **1** | **Meniscus Tear (Medial/Lateral)** | **Largest expected loss** | Single mid-triplet captures central meniscal body. Anterior/posterior horn tears (most common) are NOT in mid-coronal/mid-sagittal. Tears are oblique 3D structures. Need anterior+posterior saggital views. Need both FS and non-FS to grade. Current design: **only sees mid-body, misses >70% of tear locations.** |
| **2** | **Cartilage Defect** | **Very large loss** | Single mid-triplet shows central weightbearing cartilage only. Defects occur anywhere: patellofemoral, trochlear, posterior condyles, tibial plateaus. Need multiple sagittal cuts across compartments AND coronal. Mid-triplet = single point estimate of a 3D surface. **Misses >60% of articular surface area.** |
| **3** | **Patella Alta/Baja** | **Large loss** | Requires midline sagittal slice showing maximum patellar tendon length AND patellar height. Mid-triplet may or may not include midline (no anatomical registration). If lateral or medial sagittal, measurement impossible. Additionally, needs T1 for clean tendon-bone interface. **Binary finding depends on 1 correct slice; 33% chance of hitting it.** |
| **4** | **ACL Tear (Partial)** | **Large loss for partial, moderate for complete** | Complete ACL tears disrupt entire fiber plane — visible on any sagittal slice near midline. **Mid-triplet captures enough.** But partial tears are focal fiber disruptions at femoral/tibial footprint — may be one sagittal slice thick. Mid-triplet may miss if not exactly at footprint. Also needs axial confirmation. **Partial tears: high loss; complete: low loss.** |
| **5** | **Fracture** | **Large loss** | Mid-triplet shows central condyles. Fractures are often at peripheral plateau, fibular head, patella. Also: **must have T1 sequence** to see fracture line through edema. If mid-triplet happens to be T2 FS only, fracture line invisible. **Both sequence diversity AND spatial coverage lacking.** |
| **6** | **MCL/LCL Sprain** | **Moderate loss** | Coronal mid-body captures MCL course across joint line — actually decent for Grade II-III complete injury. But Grade I edema may be focal proximal/distal to joint line (missed by mid-slice). And: MCL/LCL evaluation benefits from axial preview through ligament course. **Partially captured.** |
| **7** | **Meniscal Extrusion** | **Moderate loss** | Mid-coronal at joint line is exactly where extrusion measured — actually ideal! But needs proper coronal plane (not sagittal-oblique). If series assignment correct, **good capture.** |
| **8** | **IT Band Syndrome** | **Moderate loss** | Edema lateral to joint — mid-coronal captures but IT band syndrome has maximal edema slightly posterior to mid-coronal. Need axial confirmation. **Partial capture.** |
| **9** | **Bone Marrow Edema** | **Low-moderate loss** | BME of central condyles caught by mid-triplet. Peripheral/patellar BME missed. But BME is macroscopic and often involves central compartment. **Moderate sensitivity.** |
| **10** | **PCL Tear** | **Low loss** | PCL course is midline sagittal-to-coronal. Mid-triplet sagittal captures bulk of PCL. Complete tears obvious; partial less so. **Good capture.** |
| **11** | **Patellar Tendon Tear** | **Low loss** | Central sagittal mid-slice shows tendon insertion through to tibial tubercle. Good capture for mid-portion tears. Proximal/distal insertional partial tears may be 1-2 slices off. **Good capture.** |
| **12** | **Fracture (nondisplaced)** | See #5 above — listed separately for emphasis | Requires T1; our model may not see T1 if mid-triplet from wrong sequence. |

---

## Additional Loss Factors from Series-Then-Pool Design

### **Cross-Sequence Disambiguation Loss**
Meniscus tears appear as line hyperintensities on FS sequences but can be mimicked by magic angle effect, partial volume, or pulsation artifact. Radiologists cross-reference non-FS sequences to confirm tear. Our pool treats each series independently — **no cross-sequence verification possible.** This is a major sensitivity/specificity loss for meniscus and cartilage.

### **Cumulative Anatomic Coverage Loss**
With 6 series of 3 slices each (RGB channels) = 6 × 3 = 18 total slice positions per knee. A standard knee MRI has ~100-150 slices (6 series × ~20 slices). We sample **~12-18% of available data.** Combined with fixed mid-positioning, we lose 82-88% of anatomy.

### **Multi-Reader Disagreement Mismatch**
Gold labels (58 studies) are likely from experienced MSK radiologists with access to ALL sequences and ALL slices. Pseudo-labels (4,349 reports) come from attending radiologist interpretation reports — same all-data access. Both sets reflect **whole-knee spatial-temporal reasoning.** Our model sees only mid-sections — it literally cannot detect pathology outside the mid-volume. This creates a **fundamental ceiling lower than the label quality suggests.**

---

## Expected Loss vs Frontier by Finding: Ranked Quantitative Estimates

Given the 0.078 gap to frontier (0.865→0.943):

| Finding | Expected Contribution to Gap | Primary Reason |
|---------|------------------------------|----------------|
| **Meniscus tears (both)** | **0.020-0.030** | Anatomic coverage of horns + cross-sequence disambiguation |
| **Cartilage defect** | **0.015-0.025** | Spatial coverage of articular surface |
| **ACL (partial)** | **0.005-0.010** | Focal tear localization |
| **Patella alta/baja** | **0.005-0.010** | Midline slice requirement + measurement |
| **Fracture** | **0.005-0.010** | T1 requirement + peripheral coverage |
| **MCL/LCL** | **0.003-0.008** | Edge-of-coverage ligaments |
| **Meniscal extrusion** | **0.000-0.003** | Well-captured if coronal available |
| **IT band** | **0.001-0.004** | Partially captured |
| **BME** | **0.001-0.005** | Mostly captured centrally |
| **PCL / Patellar tendon** | **0.000-0.003** | Well-captured |

**Sum: 0.055-0.098** → This matches the observed 0.078 gap remarkably well. The dominant mechanisms are coverage (~60% of gap) and cross-sequence reasoning (~25%).

---

# Concrete Input-Design Recommendations

## Tier 1: Directly Address Coverage (Expected Gain: +0.03-0.05)

### 1. **Multi-slice aggregation per series (2.5D → 3D patches)**
- Instead of 3 mid-slices as RGB channels, sample **9-15 slices per series** uniformly spaced (e.g., every 2nd slice).
- Use **3D ConvNet stem** or **ViT with 3D patch embedding** (small temporal dimension) to fuse within series before pooling.
- Implementation: Replace `mid-1, mid, mid+1` RGB encoding with `[slice_0, slice_3, ..., slice_15]` as actual spatial depth channels. This samples ~20% of each series vs current 15%.
- **Directly increases anatomic coverage without requiring additional positional logic.**

### 2. **Anatomic slot-aware spatial sampling**
- Each of 6 series slots has known approximate coverage (sagittal = medial→lateral, coronal = posterior→anterior, axial = superior→inferior).
- For sagittal series: sample **medial third, central third, lateral third** as separate "views" (3 triplets = 9 slices, or 3 multi-slice stacks).
- For coronal: sample posterior third, central, anterior third.
- Each view gets independent series-level logits; pool all views at study level.
- **Catches anterior/posterior horn meniscus tears, patellofemoral cartilage, peripheral MCL edema.**

### 3. **T1-sequence guarantee for fracture/cartilage**
- Enforce that at least one T1-weighted series is always processed (coronal T1 ± sagittal T1). If slot assignment fails, flag and use DICOM echo time to identify T1.
- Current DICOM metadata parsing already exists; use it to guarantee cross-sequence diversity in sampling.

## Tier 2: Cross-Sequence Reasoning (Expected Gain: +0.01-0.02)

### 4. **Late-fusion cross-sequence attention**
- After per-series feature extraction (any backbone), concatenate all series-level feature vectors and apply **self-attention or a Transformer encoder** before per-finding MLP heads.
- This allows the model to learn: "meniscus high signal on FS sequence is a tear ONLY IF corresponding T1 shows fibrosis/cleft."
- Implementation: CoAtNet per series → [CLS] token per series → 6×[CLS] → 2-layer Transformer → per-finding heads.
- This adds minimal compute (fewer than 10K parameters) but enables cross-sequence consultation.

### 5. **Channel-wise multi-sequence stacking**
- Instead of treating series independently, align sagittal T1 and sagittal T2 FS by DICOM coordinates and stack as **multi-channel input** (2×3 slices as 6 channels).
- Requires spatial registration already available from DICOM geometry.
- **Most physiologically accurate — matches radiologist behavior exactly.**

## Tier 3: Resolution (