# Knee MRI Physiology → Deep Learning Bottleneck Analysis

## 1. Finding-by-Finding Physiology Requirements

Let me reason from tissue physics and imaging principles for each of the 12 RSNA findings:

### Meniscal Tears (Medial Meniscus, Lateral Meniscus)
- **Tissue**: Fibrocartilage; tears appear as linear high signal within normally dark triangle.
- **Critical plane**: Sagittal (in-plane visualization of anterior/posterior horns). Coronal supplements body tears.
- **Critical sequence**: PD with fat suppression OR T2 FS. Meniscus is dark on all sequences; tear signal requires fluid (bright on T2/PD FS).
- **Resolution limit**: 1 mm tear requires ≤0.5 mm in-plane pitch (Nyquist). At our 384 px / 130 mm crop: 0.339 mm — *theoretically sufficient*. But slice thickness matters more: most acquisitions have 3–4 mm slice thickness, meaning partial volume averages small tears. **The slice plane, not in-plane resolution, is the bottleneck.**
- **Cross-slice context needed**: Tears propagate vertically or horizontally; adjacent slices show continuity. **2.5D (3+ slices) is physiologically necessary.**

### ACL / PCL Tears
- **Tissue**: Collagenous bundles; discontinuous fibers, abnormal orientation, edema.
- **Critical plane**: Sagittal for ACL (oblique sagittal ideal but clinical sagittal sufficient). Both sagittal and coronal for PCL.
- **Critical sequence**: T2 FS shows edema best; PD FS shows fiber detail. ACL is dark on T1; edema bright on T2.
- **Resolution**: ACL is ~4-5 mm thick. Individual fiber disruption visible at 0.3-0.5 mm. **In-plane adequate; slice thickness + oblique course are the bottlenecks.**
- **Cross-slice**: ACL traverses 3-5 slices. **Single mid-slice misses oblique fibers.**

### Cartilage Abnormalities (Patellofemoral, Medial/Lateral Compartment)
- **Tissue**: Hyaline cartilage, ~2-4 mm thick. Defects appear as contour irregularities, signal change.
- **Critical plane**: Dependent on compartment. PF: axial ideal, sagittal secondary. Medial/lateral: coronal for weightbearing surface, sagittal for posterior condyles.
- **Critical sequence**: PD FS or fat-suppressed T2/GRE. Cartilage is intermediate signal; fluid in defects bright on FS sequences. **FS is essential.**
- **Resolution**: Grade 2 lesions (partial thickness ~1 mm) require ≤0.5 mm. 3 mm slices can miss focal defects entirely. **Slice thickness is critical.**
- **Cross-slice**: Defects span 1-3 slices. **Adjacent context essential.**

### Bone Marrow Edema-like Signal (all three compartments)
- **Tissue**: Subchondral bone; increased water content, low T1 signal, high T2/STIR signal.
- **Critical plane**: Coronal + sagittal complement. BME is geographic.
- **Critical sequence**: **Fat suppression mandatory.** T2 FS or STIR. Without FS, marrow edema is invisible against bright fatty marrow.
- **Resolution**: Lesions often >5 mm, so 0.5 mm in-plane is more than sufficient. **Not resolution-limited.**
- **Cross-slice**: Lesions span many slices. **Single mid-slice can still capture large confluent edema, but small foci near joint line could be missed.**

### Fracture
- **Tissue**: Linear low signal on T1, high T2 signal line, surrounding edema.
- **Critical plane**: Variable; cortical disruption best on axial/coronal.
- **Critical sequence**: T1 for fracture line; T2 FS for edema. Without T1, subtle non-displaced fractures can be occult.
- **Resolution**: Fracture lines are <1 mm. **Slice thickness is more limiting than in-plane.**
- **Cross-slice**: Fracture line may appear on only 1-2 slices. **Mid-slice alone misses ~30% of fracture planes.**

### Joint Effusion / Synovitis
- **Tissue**: Fluid in joint space (effusion) or thickened synovium (synovitis).
- **Critical plane**: Axial best for suprapatellar pouch; sagittal for overall volume.
- **Critical sequence**: T2 FS shows fluid brilliantly. **FS required.**
- **Resolution**: Effusion >10 mL is macroscopic; not resolution-limited.
- **Cross-slice**: Effusion spans entire joint. **Single mid-slice may capture presence, but volume estimation suffers.**

---

## 2. Sequence/Plane/FS Requirement Matrix

| Finding | Optimal Plane(s) | FS Required? | T1 Needed? | Min Slice Context | Resolution Sensitivity |
|---|---|---|---|---|---|
| Medial Meniscus Tear | SAG >> COR | Yes (PD FS) | No (dark on all) | HIGH (3+ slices) | HIGH (1mm features) |
| Lateral Meniscus Tear | SAG > COR | Yes (PD FS) | No | HIGH (3+ slices) | HIGH (1mm features) |
| ACL Tear | SAG | Yes (T2 FS best) | T1 helpful | MOD (3 slices) | MOD (fiber disruption) |
| PCL Tear | SAG + COR | Yes (T2 FS) | T1 helpful | MOD (3 slices) | MOD |
| PF Cartilage | AX >> SAG | Yes (PD/T2 FS) | No | HIGH (2-3 slices) | HIGH (defect depth) |
| Medial Cartilage | COR > SAG | Yes (PD/T2 FS) | No | HIGH (2-3 slices) | HIGH |
| Lateral Cartilage | COR > SAG | Yes (PD/T2 FS) | No | HIGH (2-3 slices) | HIGH |
| PF Edema | AX + SAG | **Mandatory** | No (T2 FS) | LOW-MOD | LOW |
| Medial Edema | COR + SAG | **Mandatory** | No | LOW-MOD | LOW |
| Lateral Edema | COR + SAG | **Mandatory** | No | LOW-MOD | LOW |
| Fracture | Variable | Yes (T2 FS) | **Strongly helpful** | MOD (2-3 slices) | HIGH (line <1mm) |
| Effusion/Synovitis | AX > SAG | Yes | No | LOW | LOW |

---

## 3. What Our Current Design Does (and Misses)

**Current**: Single mid-triplet (mid ± 1 slice), RGB-stacked from *one series per study* (first sagittal in pool), 384 px CoAtNet, series-then-pool aggregation.

### What we lose by finding:

| Finding | Loss Mechanism | Expected Magnitude |
|---|---|---|
| **Meniscal tears** | ① Single sagittal series only — no coronal confirmation for body tears. ② Mid-slice doesn't sample anterior/posterior horns optimally (tear may be at horn, not body). ③ No fat-suppressed vs non-FS comparison (tears visible on both but *only* if fluid signal is present — early/degenerative tears without effusion may be isointense on non-FS). ④ Single triplet = 1.0 mm slice coverage (3 slices × 3-4 mm = ~10-12 mm), meniscus is ~15-20 mm anteroposterior — we sample only the middle 50%. | **HIGHEST LOSS** |
| **ACL/PCL** | ① Single sagittal from single series. If FS is absent, edema in torn ligament is invisible. ② Mid-slice may capture mid-substance but miss femoral/tibial avulsion tears. ③ ACL course is oblique — single orthogonal sagittal plane partially captures fibers. | **HIGH LOSS** |
| **Cartilage** | ① Cartilage assessment requires fat suppression — if our single sagittal is non-FS, cartilage signal contrast drops. ② No coronal view for medial/lateral weightbearing surface (most common OA location). No axial for PF cartilage. ③ Single triplet covers ~10 mm; focal defect may be outside this window. | **HIGH LOSS** |
| **Bone Marrow Edema** | ① If single sagittal lacks FS, **edema is invisible** (bright fat masks bright edema on non-FS sequences). ② Large confluent edema may still be sampled by mid-slice; small subchondral foci at joint line edges could be missed. | **MODERATE-HIGH LOSS** (conditional on FS status of selected series) |
| **Fracture** | ① No T1 sequence: fracture line signal void is most specific finding; without T1, only surrounding edema (which may be absent in chronic fractures) is visible. ② Fracture line may be on peripheral slice, not midpoint. | **MODERATE LOSS** |
| **Effusion/Synovitis** | ① Large effusions span whole joint — mid-slice captures them. But volume estimation (critical for severity) degrades. ② Synovitis is more focal (suprapatellar, posterior recess) and may be outside mid-window. | **LOW-MODERATE LOSS** |

---

## 4. Report-Derived Labels vs Annotation Thresholds

**Critical divergence**: Our pseudo-labels come from *radiologist reports*, not from imaging annotations. The report writes:

> "Small horizontal tear of the posterior horn of the medial meniscus. Moderate joint effusion. No fracture."

**The model must infer**:
1. Does "small horizontal tear" meet the annotation threshold for "Meniscal Tear = Yes"? (Probably yes — any tear counts.)
2. Does "moderate effusion" meet the threshold for "Joint Effusion = Yes"? (Yes, but what about "trace effusion"?)
3. "No fracture" = negative (high confidence).
4. What about *incidental* findings the radiologist *didn't mention*? Are they absent, or not reported?

**Label noise by finding**:

| Finding | Report Sensitivity | Report Specificity | Noise Source |
|---|---|---|---|
| Meniscal tears | High (radiologists describe if present) | Moderate (degenerative signal not always called "tear") | Degenerative intrasubstance signal (grade 1-2) may be reported as "degeneration" not "tear"; annotation may call it negative. **False positives in pseudo-labels for grade 1-2 signal.** |
| ACL/PCL | Very high | High | Partial tears: report may say "sprain" not "tear" → false negative in pseudo-labels. |
| Cartilage | Low-moderate (only described if severe or focal defect) | High | **False negatives**: "mild chondromalacia" may be omitted from report. Annotation threshold is uniform; report threshold is clinical relevance. |
| BME | Moderate (mentioned when striking) | High | **False negatives**: subtle subchondral edema may be unreported. Miss rate proportional to subtlety. |
| Fracture | Very high | Very high | Near-zero noise — radiologists never miss fractures in reports. |
| Effusion | Low (described only if clinically relevant) | High | **False negatives**: "small/trace effusion" often omitted. Report mentions only when moderate or large. |

**The labeling gap is largest for cartilage and effusion** — our pseudo-labels are *missing positive cases* that the image shows. This biases the model toward false negatives for these findings. Effusion = 0.78 AUC in early runs confirms this (we can't learn what we label negative).

---

## 5. Current Design Loss Ranking vs Theoretical Frontier

Given: single-series, single-triplet, series-then-pool, no FS awareness, report-label noise.

**Ranked expected loss (gap to frontier) by finding**:

| Rank | Finding | Expected AUC Loss | Dominant Mechanism |
|---|---|---|---|
| **1 (WORST)** | **Lateral Meniscus Tear** | **0.08-0.12** | ① No coronal confirmation (body tears). ② Mid-slice misses horns. ③ Label noise (degenerative vs tear). ④ No FS comparison. |
| **2** | **Medial Meniscus Tear** | **0.06-0.10** | Same as lateral but medial tears are larger/more central → mid-slice captures more. Still suffers all four mechanisms. |
| **3** | **Lateral Cartilage** | **0.06-0.09** | ① No coronal view. ② FS requirement. ③ Label false negatives (mild unreported). |
| **4** | **Medial Cartilage** | **0.05-0.08** | Same. |
| **5** | **ACL Tear** | **0.05-0.08** | ① Oblique course not orthogonal to single sagittal. ② Partial tear label noise. ③ FS requirement for edema. |
| **6** | **PF Cartilage** | **0.04-0.07** | ① No axial view (most critical). ② Sagittal alone misses PF surface detail. |
| **7** | **Fracture** | **0.04-0.06** | ① No T1 sequence. ② Fracture line on peripheral slice. ③ Label quality is good (mitigates some loss). |
| **8** | **Lateral Edema** | **0.03-0.05** | ① FS dependence. ② If selected series has FS, large edema captured. If not, invisible. |
| **9** | **Medial Edema** | **0.03-0.05** | Same. |
| **10** | **PF Edema** | **0.03-0.05** | Same. |
| **11** | **PCL Tear** | **0.03-0.05** | PCL is central, thick, orthogonal to sagittal — mid-slice captures most. Main loss is FS requirement. |
| **12 (BEST)** | **Effusion/Synovitis** | **0.02-0.04** | ① Macroscopic — mid-slice captures presence. ② Volume estimation loss. ③ Label false negatives (small unreported) actually reduce our measured AUC but model might still *see* it. |

---

## 6. Concrete Input-Design Changes (Prioritized by Physiology)

### **Immediate (within current codebase, 1-2 days):**

**A. Multi-series input (HIGHEST ROI)**
- **Current**: Single sagittal series per study (first encountered).
- **Change**: Select *three* series with explicit type routing:
  - **Sagittal FS** (PD FS or T2 FS): Primary for menisci, cruciates, cartilage, edema.
  - **Sagittal non-FS** (T1 or PD): Secondary confirmation; tears still visible if no fluid artifact.
  - **Coronal FS** (PD FS or T2 FS): Critical for body tears, cartilage, weightbearing surface.
  - If study lacks all three, fall back to available sagittal > coronal > axial.
- **Why**: Easiest implementation; directly addresses meniscus (ranked #1-2 loss) and cartilage (#3-6). Multiple series are *already in the DICOM pool* — we're just discarding them.
- **Architecture**: Independent CoAtNet triplet per series → concatenate features → shared head. Or: three-channel input where each channel = different series' mid-slice (simpler, test first).
- **TPU cost**: Same per-series compute, 3× series count → ~3× training time (but we crop to max 6 series already; extend to max 3 *types* × 2 slices each still fits).

**B. Wider slice sampling per series (2nd priority)**
- **Current**: Mid ± 1 slice (total span ~10 mm at 3.5 mm slice thickness).
- **Change**: Sample *five* equally spaced positions along the series (like raptor_k_eval=94 in frontier code, but we use exactly 5 positions: 10%, 30%, 50%, 70%, 90%).
- **Why**: Meniscus anterior/posterior horns at periphery, cartilage defects not at midpoint, fracture lines on edge slices. Directly addresses #1-4 losses. This was a 0.942→0.943 change in the frontier lineage.
- **Architecture**: Each position = a triplet → mean pool across positions → per-series embedding. Or: 3D CNN on stacked positions (expensive).

**C. Explicit FS channel flag (3rd priority)**
- **Current**: Model must *learn* whether FS is present from pixel statistics.
- **Change**: Add a 2-channel input per slice: (pixel data, binary FS mask). FS mask = 1 if DICOM header indicates fat suppression (ScanningSequence, SequenceVariant, or ImageType tags).
- **Why**: Edema and cartilage findings are FS-dependent. Model currently must guess FS status and re-learn per study. Directly aids #3-10 losses. Essentially zero cost — just DICOM tag extraction.

### **Medium-term (2-3 runs):**

**D. Coronal + axial arms with finding-routing**
- Mirror frontier design: separate CoAtNet backbones for SAG/COR/AX planes, each with its own per-finding attention.
- Finding-specific gating: Meniscus tears = SAG + COR gates; Cartilage = COR + AX/SAG; Edema = FS-series across all planes; Fracture = T1 + FS combination.
- **Cost**: 3× model parameters → TPU time increase. But each arm is smaller (maybe keep r50-CoAtNet @224 for arms, r50 @384 for main SAG).

**E. Report-label calibration**
- For findings with known false negatives (cartilage, effusion): apply *label confidence downweighting* on negative pseudo-labels, not just positive confidence weighting.
- Example: Cartilage negative in pseudo-label → weight = 0.5 (model may "override" with image evidence). Fracture negative → weight = 0.95 (report is gold).
- Implement via per-sample BCE weight matrix: `weight[pos] = confidence; weight[neg] = (1 - false_negative_rate_finding)`.

### **Not recommended (low physiology ROI):**
- Higher in-plane resolution (384→512): We're already at 0.34 mm — below the 0.