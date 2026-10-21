# Week 5 Stress Matrix v2b Report (Corrected Scoring)

> **Generated strictly from:** `data/results/stress_summary_v2b.csv`
> **Amendment Note:** This report applies the Task C2 scoring corrections formulated after reviewing v2 results. All frozen modules remain completely untouched.

## Rule Amendments Applied in v2b
1. **Anomaly Ground Truth Distinction:** In v1/v2, False Alarm Rate (`pred != 'H'`) was erroneously evaluated against non-healthy scenarios (S4-S7, S9, S10, S12), incorrectly penalizing true positive detections as 'false alarms'. In v2b:
   - **Healthy Truth (S1, S2, S3, S8, S11, S13):** Evaluated by FAR; cell FAILS if FAR $> 15.0\%$.
   - **Non-Healthy Truth (S4-S7 wrong physics, S9 jitter, S10 bias, S12 out-of-range):** Evaluated by Detection Rate (`pred != 'H'`); cell PASSES if Detection Rate $\ge 80.0\%$, and checks expected class assignment (S10 expected Class F; S12 expected Class A; S4-S7 physical anomaly).
2. **S1 Matching Clean Baseline:** Error ratio compares against the clean reference at matching true $\sigma$ ($\sigma=0.01, 0.03, 0.05$). Coverage ($< 80.0\%$) remains the primary failure criterion.
3. **S8 and S11 Reduced Sensor Degradation:** Observed errors are benchmarked against the Cramér-Rao Bound for reduced sensor arrays. Cells where observed median error $\le 1.5\times$ CRB-predicted error are labeled **'degradation as predicted'** and PASS.
4. **S12 Clarification & Boundary Analysis:** Renamed $\alpha=5.0$ to 'high-alpha, information-limited' (inside grid $[0.001, 10.0]$). Added `estimate_at_bound_pct` tracking boundary pinning.

---

## 1. Executive Summary Table per Module and Category

| Module | Robustness Pass Rate (Scenarios 1–3, 8–13) | Declared-Scope Violation Pass Rate (Scenarios 4–7) | Total Pass Rate (All 39 Cells) |
| :--- | :---: | :---: | :---: |
| **Mode 2** | 18 / 27 (66.7%) | 0 / 12 (0.0%) | **18 / 39 (46.2%)** |
| **Mode 3** | 18 / 27 (66.7%) | 0 / 12 (0.0%) | **18 / 39 (46.2%)** |
| **Mode 3+** | 18 / 27 (66.7%) | 0 / 12 (0.0%) | **18 / 39 (46.2%)** |
| **Two-Stage Placement** | 24 / 27 (88.9%) | 1 / 12 (8.3%) | **25 / 39 (64.1%)** |
| **Anomaly Cascade** | 18 / 27 (66.7%) | 11 / 12 (91.7%) | **29 / 39 (74.4%)** |

**Overall Portfolio Performance:** **108 / 195 Cells Passed** (`55.4%` Pass Rate; `87 / 195` Failed, `44.6%` Failure Rate).

---

## 2. Anomaly Ground Truth Rescoring Breakdown

| Scen | Ground Truth State | Severity Level | Healthy FAR % [95% CI] | Detection Rate % [95% CI] | Class Assigned Distribution | Status | Rule Assessment |
| :---: | :--- | :--- | :---: | :---: | :--- | :---: | :--- |
| S1 | Healthy | Assumed 0.05, true 0.01 | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | `H:100.0%, A:0.0%, F:0.0%, C:0.0%` | **PASS** | Within specification |
| S1 | Healthy | Assumed 0.01, true 0.05 | `100.0%` [96.3, 100.0] | `nan%` [nan, nan] | `H:0.0%, A:0.0%, F:88.0%, C:12.0%` | <span style='color:red;'>**FAIL**</span> | Healthy FAR 100.0% > 15.0% |
| S1 | Healthy | Assumed 0.01, true 0.03 | `99.0%` [94.55, 99.82] | `nan%` [nan, nan] | `H:1.0%, A:0.0%, F:82.0%, C:17.0%` | <span style='color:red;'>**FAIL**</span> | Healthy FAR 99.0% > 15.0% |
| S2 | Healthy | Student-t df=3 (moderate tail) | `17.0%` [10.89, 25.55] | `nan%` [nan, nan] | `H:83.0%, A:0.0%, F:16.0%, C:1.0%` | <span style='color:red;'>**FAIL**</span> | Healthy FAR 17.0% > 15.0% |
| S2 | Healthy | Student-t df=2.5 with 2% 5-sigma outliers | `25.0%` [17.55, 34.3] | `nan%` [nan, nan] | `H:75.0%, A:0.0%, F:23.0%, C:2.0%` | <span style='color:red;'>**FAIL**</span> | Healthy FAR 25.0% > 15.0% |
| S2 | Healthy | Student-t df=2.1 with 5% 5-sigma outliers | `45.0%` [35.61, 54.76] | `nan%` [nan, nan] | `H:55.0%, A:0.0%, F:42.0%, C:3.0%` | <span style='color:red;'>**FAIL**</span> | Healthy FAR 45.0% > 15.0% |
| S3 | Healthy | AR(1) rho = 0.50 | `5.0%` [2.15, 11.18] | `nan%` [nan, nan] | `H:95.0%, A:0.0%, F:0.0%, C:5.0%` | **PASS** | Within specification |
| S3 | Healthy | AR(1) rho = 0.80 | `20.0%` [13.34, 28.88] | `nan%` [nan, nan] | `H:80.0%, A:0.0%, F:0.0%, C:20.0%` | <span style='color:red;'>**FAIL**</span> | Healthy FAR 20.0% > 15.0% |
| S3 | Healthy | AR(1) rho = 0.95 | `13.0%` [7.76, 20.98] | `nan%` [nan, nan] | `H:87.0%, A:0.0%, F:0.0%, C:13.0%` | **PASS** | Within specification |
| S4 | Non-Healthy | Harmonic double mode sin(2 pi x) | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | `H:0.0%, A:0.0%, F:100.0%, C:0.0%` | **PASS** | Detected as physical anomaly (A:0.0%, F:100.0%, C:0.0%) |
| S4 | Non-Healthy | Two-mode sum sin(pi x) + 0.5 sin(3 pi x) | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | `H:0.0%, A:0.0%, F:100.0%, C:0.0%` | **PASS** | Detected as physical anomaly (A:0.0%, F:100.0%, C:0.0%) |
| S4 | Non-Healthy | Gaussian bump exp(-(x-0.5)^2 / (2*0.08^2)) | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | `H:0.0%, A:0.0%, F:94.0%, C:6.0%` | **PASS** | Detected as physical anomaly (A:0.0%, F:94.0%, C:6.0%) |
| S5 | Non-Healthy | Small constant offset u_bc = 0.05 | `nan%` [nan, nan] | `87.0%` [79.02, 92.24] | `H:13.0%, A:0.0%, F:4.0%, C:83.0%` | **PASS** | Detected as physical anomaly (A:0.0%, F:4.0%, C:83.0%) |
| S5 | Non-Healthy | Moderate constant offset u_bc = 0.15 | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | `H:0.0%, A:0.0%, F:14.0%, C:86.0%` | **PASS** | Detected as physical anomaly (A:0.0%, F:14.0%, C:86.0%) |
| S5 | Non-Healthy | Linearly drifting boundary u_bc(t) = 0.20 * t | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | `H:0.0%, A:0.0%, F:9.0%, C:91.0%` | **PASS** | Detected as physical anomaly (A:0.0%, F:9.0%, C:91.0%) |
| S6 | Non-Healthy | Small constant source s = 0.1 | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | `H:0.0%, A:0.0%, F:3.0%, C:97.0%` | **PASS** | Detected as physical anomaly (A:0.0%, F:3.0%, C:97.0%) |
| S6 | Non-Healthy | Moderate constant source s = 0.5 | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | `H:0.0%, A:0.0%, F:14.0%, C:86.0%` | **PASS** | Detected as physical anomaly (A:0.0%, F:14.0%, C:86.0%) |
| S6 | Non-Healthy | Strong constant source s = 2.0 | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | `H:0.0%, A:0.0%, F:100.0%, C:0.0%` | **PASS** | Detected as physical anomaly (A:0.0%, F:100.0%, C:0.0%) |
| S7 | Non-Healthy | Mild linear ramp alpha(x) = alpha0*(1 + 0.5*(x-0.5)) | `nan%` [nan, nan] | `75.0%` [65.7, 82.45] | `H:25.0%, A:0.0%, F:54.0%, C:21.0%` | <span style='color:red;'>**FAIL**</span> | Detection rate 75.0% < 80.0% |
| S7 | Non-Healthy | Steep linear ramp alpha(x) = alpha0*(1 + 1.5*(x-0.5)) | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | `H:0.0%, A:0.0%, F:89.0%, C:11.0%` | **PASS** | Detected as physical anomaly (A:0.0%, F:89.0%, C:11.0%) |
| S7 | Non-Healthy | Step discontinuity alpha(x) = 2*alpha0 for x > 0.5 | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | `H:0.0%, A:0.0%, F:75.0%, C:25.0%` | **PASS** | Detected as physical anomaly (A:0.0%, F:75.0%, C:25.0%) |
| S8 | Healthy | 10% readings missing (1 sensor dropped) | `9.0%` [4.81, 16.23] | `nan%` [nan, nan] | `H:91.0%, A:0.0%, F:4.0%, C:5.0%` | **PASS** | Within specification |
| S8 | Healthy | 30% readings missing (3 sensors dropped) | `3.0%` [1.03, 8.45] | `nan%` [nan, nan] | `H:97.0%, A:0.0%, F:2.0%, C:1.0%` | **PASS** | Within specification |
| S8 | Healthy | 50% readings missing (5 sensors dropped) | `5.0%` [2.15, 11.18] | `nan%` [nan, nan] | `H:95.0%, A:0.0%, F:3.0%, C:2.0%` | **PASS** | Within specification |
| S9 | Non-Healthy | Small jitter sigma_jitter = 0.01 | `nan%` [nan, nan] | `59.0%` [49.2, 68.13] | `H:41.0%, A:0.0%, F:54.0%, C:5.0%` | <span style='color:red;'>**FAIL**</span> | Detection rate 59.0% < 80.0% |
| S9 | Non-Healthy | Moderate jitter sigma_jitter = 0.03 | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | `H:0.0%, A:0.0%, F:94.0%, C:6.0%` | **PASS** | Detected as physical anomaly (A:0.0%, F:94.0%, C:6.0%) |
| S9 | Non-Healthy | Large jitter sigma_jitter = 0.06 | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | `H:0.0%, A:0.0%, F:93.0%, C:7.0%` | **PASS** | Detected as physical anomaly (A:0.0%, F:93.0%, C:7.0%) |
| S10 | Non-Healthy | Small sensor bias b = 3 sigma (0.03) | `nan%` [nan, nan] | `51.0%` [41.35, 60.58] | `H:49.0%, A:0.0%, F:50.0%, C:1.0%` | <span style='color:red;'>**FAIL**</span> | Detection rate 51.0% < 80.0% |
| S10 | Non-Healthy | Medium sensor bias b = 6 sigma (0.06) | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | `H:0.0%, A:0.0%, F:100.0%, C:0.0%` | **PASS** | Detected as expected Class F (100.0%) |
| S10 | Non-Healthy | Strong sensor bias b = 15 sigma (0.15) | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | `H:0.0%, A:0.0%, F:100.0%, C:0.0%` | **PASS** | Detected as expected Class F (100.0%) |
| S11 | Healthy | Sparse array N = 5 sensors | `1.0%` [0.18, 5.45] | `nan%` [nan, nan] | `H:99.0%, A:0.0%, F:1.0%, C:0.0%` | **PASS** | Within specification |
| S11 | Healthy | Very sparse array N = 3 sensors | `5.0%` [2.15, 11.18] | `nan%` [nan, nan] | `H:95.0%, A:0.0%, F:0.0%, C:5.0%` | **PASS** | Within specification |
| S11 | Healthy | Minimal array N = 2 sensors | `6.0%` [2.78, 12.48] | `nan%` [nan, nan] | `H:94.0%, A:0.0%, F:0.0%, C:6.0%` | **PASS** | Within specification |
| S12 | Non-Healthy | Sub-grid low diffusivity alpha = 5e-4 | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | `H:0.0%, A:96.0%, F:2.0%, C:2.0%` | **PASS** | Detected as expected Class A (96.0%) |
| S12 | Non-Healthy | high-alpha, information-limited | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | `H:0.0%, A:98.0%, F:0.0%, C:2.0%` | **PASS** | Detected as expected Class A (98.0%) |
| S12 | Non-Healthy | Super-grid extreme diffusivity alpha = 20.0 | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | `H:0.0%, A:0.0%, F:100.0%, C:0.0%` | **PASS** | Detected (100.0%); Class A recall 0.0% < 80% (expected A; assigned F:100.0%) |
| S13 | Healthy | Slow drift delta = 2% | `7.0%` [3.43, 13.75] | `nan%` [nan, nan] | `H:93.0%, A:0.0%, F:2.0%, C:5.0%` | **PASS** | Within specification |
| S13 | Healthy | Moderate drift delta = 5% | `7.0%` [3.43, 13.75] | `nan%` [nan, nan] | `H:93.0%, A:0.0%, F:2.0%, C:5.0%` | **PASS** | Within specification |
| S13 | Healthy | Severe drift delta = 10% | `29.0%` [21.01, 38.54] | `nan%` [nan, nan] | `H:71.0%, A:0.0%, F:1.0%, C:28.0%` | <span style='color:red;'>**FAIL**</span> | Healthy FAR 29.0% > 15.0% |

---

## 3. S8 & S11 Degradation vs Cramér-Rao Bound

| Scen | Module | Severity Level | Observed Med Rel Err | CRB Predicted Rel Err | Ratio (Obs/CRB) | Status | Assessment |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| S8 | Mode 2 | 10% readings missing (1 sensor dropped) | `0.0155` | `0.0202` | `0.77x` | **PASS** | degradation as predicted (err 0.0155 <= 1.5x CRB 0.0202) |
| S8 | Mode 3 | 10% readings missing (1 sensor dropped) | `0.0132` | `0.0202` | `0.65x` | **PASS** | degradation as predicted (err 0.0132 <= 1.5x CRB 0.0202) |
| S8 | Mode 3+ | 10% readings missing (1 sensor dropped) | `0.0155` | `0.0202` | `0.77x` | **PASS** | degradation as predicted (err 0.0155 <= 1.5x CRB 0.0202) |
| S8 | Two-Stage Placement | 10% readings missing (1 sensor dropped) | `0.0092` | `0.0202` | `0.46x` | **PASS** | degradation as predicted (err 0.0092 <= 1.5x CRB 0.0202) |
| S8 | Mode 2 | 30% readings missing (3 sensors dropped) | `0.0185` | `0.0226` | `0.82x` | **PASS** | degradation as predicted (err 0.0185 <= 1.5x CRB 0.0226) |
| S8 | Mode 3 | 30% readings missing (3 sensors dropped) | `0.0184` | `0.0226` | `0.81x` | **PASS** | degradation as predicted (err 0.0184 <= 1.5x CRB 0.0226) |
| S8 | Mode 3+ | 30% readings missing (3 sensors dropped) | `0.0185` | `0.0226` | `0.82x` | **PASS** | degradation as predicted (err 0.0185 <= 1.5x CRB 0.0226) |
| S8 | Two-Stage Placement | 30% readings missing (3 sensors dropped) | `0.0090` | `0.0226` | `0.40x` | **PASS** | degradation as predicted (err 0.0090 <= 1.5x CRB 0.0226) |
| S8 | Mode 2 | 50% readings missing (5 sensors dropped) | `0.0248` | `0.0278` | `0.89x` | **PASS** | degradation as predicted (err 0.0248 <= 1.5x CRB 0.0278) |
| S8 | Mode 3 | 50% readings missing (5 sensors dropped) | `0.0258` | `0.0278` | `0.93x` | **PASS** | degradation as predicted (err 0.0258 <= 1.5x CRB 0.0278) |
| S8 | Mode 3+ | 50% readings missing (5 sensors dropped) | `0.0248` | `0.0278` | `0.89x` | **PASS** | degradation as predicted (err 0.0248 <= 1.5x CRB 0.0278) |
| S8 | Two-Stage Placement | 50% readings missing (5 sensors dropped) | `0.0081` | `0.0278` | `0.29x` | **PASS** | degradation as predicted (err 0.0081 <= 1.5x CRB 0.0278) |
| S11 | Mode 2 | Sparse array N = 5 sensors | `0.0166` | `0.0260` | `0.64x` | **PASS** | degradation as predicted (err 0.0166 <= 1.5x CRB 0.0260) |
| S11 | Mode 3 | Sparse array N = 5 sensors | `0.0182` | `0.0260` | `0.70x` | **PASS** | degradation as predicted (err 0.0182 <= 1.5x CRB 0.0260) |
| S11 | Mode 3+ | Sparse array N = 5 sensors | `0.0166` | `0.0260` | `0.64x` | **PASS** | degradation as predicted (err 0.0166 <= 1.5x CRB 0.0260) |
| S11 | Two-Stage Placement | Sparse array N = 5 sensors | `0.0083` | `0.0260` | `0.32x` | **PASS** | degradation as predicted (err 0.0083 <= 1.5x CRB 0.0260) |
| S11 | Mode 2 | Very sparse array N = 3 sensors | `0.0216` | `0.0291` | `0.74x` | **PASS** | degradation as predicted (err 0.0216 <= 1.5x CRB 0.0291) |
| S11 | Mode 3 | Very sparse array N = 3 sensors | `0.0247` | `0.0291` | `0.85x` | **PASS** | degradation as predicted (err 0.0247 <= 1.5x CRB 0.0291) |
| S11 | Mode 3+ | Very sparse array N = 3 sensors | `0.0216` | `0.0291` | `0.74x` | **PASS** | degradation as predicted (err 0.0216 <= 1.5x CRB 0.0291) |
| S11 | Two-Stage Placement | Very sparse array N = 3 sensors | `0.0156` | `0.0291` | `0.54x` | **PASS** | degradation as predicted (err 0.0156 <= 1.5x CRB 0.0291) |
| S11 | Mode 2 | Minimal array N = 2 sensors | `0.0205` | `0.0311` | `0.66x` | **PASS** | degradation as predicted (err 0.0205 <= 1.5x CRB 0.0311) |
| S11 | Mode 3 | Minimal array N = 2 sensors | `0.0245` | `0.0311` | `0.79x` | **PASS** | degradation as predicted (err 0.0245 <= 1.5x CRB 0.0311) |
| S11 | Mode 3+ | Minimal array N = 2 sensors | `0.0205` | `0.0311` | `0.66x` | **PASS** | degradation as predicted (err 0.0205 <= 1.5x CRB 0.0311) |
| S11 | Two-Stage Placement | Minimal array N = 2 sensors | `0.0204` | `0.0311` | `0.65x` | **PASS** | degradation as predicted (err 0.0204 <= 1.5x CRB 0.0311) |

---

## 4. S12 Boundary Pinning Analysis

| Scen | Module | Severity Level | Abs Med Rel Err | Ratio vs Clean | Coverage % [95% CI] | At Bound % (<=0.001 or >=9.9) | Status |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| S12 | Mode 2 | Sub-grid low diffusivity alpha = 5e-4 | `1.0000` | `86.56x` | `88.0%` [80.19, 93.0] | `72.0%` | <span style='color:red;'>**FAIL**</span> |
| S12 | Mode 3 | Sub-grid low diffusivity alpha = 5e-4 | `0.9690` | `77.15x` | `80.0%` [71.12, 86.66] | `51.0%` | <span style='color:red;'>**FAIL**</span> |
| S12 | Mode 3+ | Sub-grid low diffusivity alpha = 5e-4 | `1.0002` | `86.55x` | `88.0%` [80.19, 93.0] | `72.0%` | <span style='color:red;'>**FAIL**</span> |
| S12 | Two-Stage Placement | Sub-grid low diffusivity alpha = 5e-4 | `1.0000` | `125.96x` | `90.0%` [82.56, 94.48] | `84.0%` | <span style='color:red;'>**FAIL**</span> |
| S12 | Mode 2 | high-alpha, information-limited | `0.1075` | `9.30x` | `0.0%` [0.0, 3.7] | `0.0%` | <span style='color:red;'>**FAIL**</span> |
| S12 | Mode 3 | high-alpha, information-limited | `0.1031` | `8.21x` | `22.0%` [15.0, 31.07] | `0.0%` | <span style='color:red;'>**FAIL**</span> |
| S12 | Mode 3+ | high-alpha, information-limited | `0.1075` | `9.30x` | `0.0%` [0.0, 3.7] | `0.0%` | <span style='color:red;'>**FAIL**</span> |
| S12 | Two-Stage Placement | high-alpha, information-limited | `0.0101` | `1.28x` | `94.0%` [87.52, 97.22] | `0.0%` | **PASS** |
| S12 | Mode 2 | Super-grid extreme diffusivity alpha = 20.0 | `0.5000` | `43.28x` | `0.0%` [0.0, 3.7] | `100.0%` | <span style='color:red;'>**FAIL**</span> |
| S12 | Mode 3 | Super-grid extreme diffusivity alpha = 20.0 | `0.5000` | `39.81x` | `0.0%` [0.0, 3.7] | `100.0%` | <span style='color:red;'>**FAIL**</span> |
| S12 | Mode 3+ | Super-grid extreme diffusivity alpha = 20.0 | `0.5001` | `43.27x` | `0.0%` [0.0, 3.7] | `100.0%` | <span style='color:red;'>**FAIL**</span> |
| S12 | Two-Stage Placement | Super-grid extreme diffusivity alpha = 20.0 | `0.5000` | `62.98x` | `0.0%` [0.0, 3.7] | `100.0%` | <span style='color:red;'>**FAIL**</span> |

---

## 5. All FAILED Cells in v2b with Absolute Errors and 95% CIs

| Scen | Category | Module | Severity Level | Abs Med Rel Err | Clean Err | Ratio | Coverage % [95% CI] | Healthy FAR % / Det % [95% CI] | Failure Reason |
| :---: | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| S1 | robustness | **Two-Stage Placement** | Assumed 0.05, true 0.01 | `0.0402` | `0.0079` | `5.06x` | `99.0%` [94.55, 99.82] | FAR `nan%` [nan, nan] | Error 5.06x > 2.0x matching clean (0.0079) |
| S1 | robustness | **Anomaly Cascade** | Assumed 0.01, true 0.05 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `100.0%` [96.3, 100.0] | Healthy FAR 100.0% > 15.0% |
| S1 | robustness | **Mode 2** | Assumed 0.01, true 0.05 | `0.0656` | `0.0550` | `1.19x` | `29.0%` [21.01, 38.54] | FAR `nan%` [nan, nan] | Coverage 29.0% < 80.0% |
| S1 | robustness | **Mode 3** | Assumed 0.01, true 0.05 | `0.0646` | `0.0572` | `1.13x` | `30.0%` [21.89, 39.58] | FAR `nan%` [nan, nan] | Coverage 30.0% < 80.0% |
| S1 | robustness | **Mode 3+** | Assumed 0.01, true 0.05 | `0.0656` | `0.0550` | `1.19x` | `29.0%` [21.01, 38.54] | FAR `nan%` [nan, nan] | Coverage 29.0% < 80.0% |
| S1 | robustness | **Anomaly Cascade** | Assumed 0.01, true 0.03 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `99.0%` [94.55, 99.82] | Healthy FAR 99.0% > 15.0% |
| S1 | robustness | **Mode 2** | Assumed 0.01, true 0.03 | `0.0394` | `0.0345` | `1.14x` | `47.0%` [37.51, 56.71] | FAR `nan%` [nan, nan] | Coverage 47.0% < 80.0% |
| S1 | robustness | **Mode 3** | Assumed 0.01, true 0.03 | `0.0408` | `0.0345` | `1.18x` | `45.0%` [35.61, 54.76] | FAR `nan%` [nan, nan] | Coverage 45.0% < 80.0% |
| S1 | robustness | **Mode 3+** | Assumed 0.01, true 0.03 | `0.0394` | `0.0345` | `1.14x` | `47.0%` [37.51, 56.71] | FAR `nan%` [nan, nan] | Coverage 47.0% < 80.0% |
| S2 | robustness | **Anomaly Cascade** | Student-t df=3 (moderate tail) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `17.0%` [10.89, 25.55] | Healthy FAR 17.0% > 15.0% |
| S2 | robustness | **Anomaly Cascade** | Student-t df=2.5 with 2% 5-sigma outliers | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `25.0%` [17.55, 34.3] | Healthy FAR 25.0% > 15.0% |
| S2 | robustness | **Anomaly Cascade** | Student-t df=2.1 with 5% 5-sigma outliers | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `45.0%` [35.61, 54.76] | Healthy FAR 45.0% > 15.0% |
| S3 | robustness | **Anomaly Cascade** | AR(1) rho = 0.80 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `20.0%` [13.34, 28.88] | Healthy FAR 20.0% > 15.0% |
| S3 | robustness | **Mode 2** | AR(1) rho = 0.80 | `0.0288` | `0.0116` | `2.50x` | `61.0%` [51.2, 69.98] | FAR `nan%` [nan, nan] | Error 2.50x > 2.0x clean; Coverage 61.0% < 80.0% |
| S3 | robustness | **Mode 3** | AR(1) rho = 0.80 | `0.0266` | `0.0126` | `2.12x` | `63.0%` [53.22, 71.82] | FAR `nan%` [nan, nan] | Error 2.12x > 2.0x clean; Coverage 63.0% < 80.0% |
| S3 | robustness | **Mode 3+** | AR(1) rho = 0.80 | `0.0288` | `0.0116` | `2.50x` | `61.0%` [51.2, 69.98] | FAR `nan%` [nan, nan] | Error 2.50x > 2.0x clean; Coverage 61.0% < 80.0% |
| S3 | robustness | **Mode 2** | AR(1) rho = 0.95 | `0.0238` | `0.0116` | `2.06x` | `69.0%` [59.37, 77.22] | FAR `nan%` [nan, nan] | Error 2.06x > 2.0x clean; Coverage 69.0% < 80.0% |
| S3 | robustness | **Mode 3** | AR(1) rho = 0.95 | `0.0241` | `0.0126` | `1.92x` | `69.0%` [59.37, 77.22] | FAR `nan%` [nan, nan] | Coverage 69.0% < 80.0% |
| S3 | robustness | **Mode 3+** | AR(1) rho = 0.95 | `0.0239` | `0.0116` | `2.06x` | `69.0%` [59.37, 77.22] | FAR `nan%` [nan, nan] | Error 2.06x > 2.0x clean; Coverage 69.0% < 80.0% |
| S4 | declared-scope violation | **Mode 2** | Harmonic double mode sin(2 pi x) | `98.9987` | `0.0116` | `8569.09x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 8569.09x > 2.0x clean; Coverage 0.0% < 80.0% |
| S4 | declared-scope violation | **Mode 3** | Harmonic double mode sin(2 pi x) | `98.9979` | `0.0126` | `7882.62x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 7882.62x > 2.0x clean; Coverage 0.0% < 80.0% |
| S4 | declared-scope violation | **Mode 3+** | Harmonic double mode sin(2 pi x) | `98.9883` | `0.0116` | `8565.23x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 8565.23x > 2.0x clean; Coverage 0.0% < 80.0% |
| S4 | declared-scope violation | **Two-Stage Placement** | Harmonic double mode sin(2 pi x) | `98.9987` | `0.0079` | `12469.92x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 12469.92x > 2.0x clean; Coverage 0.0% < 80.0% |
| S4 | declared-scope violation | **Mode 2** | Two-mode sum sin(pi x) + 0.5 sin(3 pi x) | `0.0563` | `0.0116` | `4.87x` | `35.0%` [26.36, 44.75] | FAR `nan%` [nan, nan] | Error 4.87x > 2.0x clean; Coverage 35.0% < 80.0% |
| S4 | declared-scope violation | **Mode 3** | Two-mode sum sin(pi x) + 0.5 sin(3 pi x) | `0.0558` | `0.0126` | `4.44x` | `36.0%` [27.27, 45.76] | FAR `nan%` [nan, nan] | Error 4.44x > 2.0x clean; Coverage 36.0% < 80.0% |
| S4 | declared-scope violation | **Mode 3+** | Two-mode sum sin(pi x) + 0.5 sin(3 pi x) | `0.0562` | `0.0116` | `4.87x` | `35.0%` [26.36, 44.75] | FAR `nan%` [nan, nan] | Error 4.87x > 2.0x clean; Coverage 35.0% < 80.0% |
| S4 | declared-scope violation | **Two-Stage Placement** | Two-mode sum sin(pi x) + 0.5 sin(3 pi x) | `0.0762` | `0.0079` | `9.59x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 9.59x > 2.0x clean; Coverage 0.0% < 80.0% |
| S4 | declared-scope violation | **Mode 2** | Gaussian bump exp(-(x-0.5)^2 / (2*0.08^2)) | `26.1431` | `0.0116` | `2262.88x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 2262.88x > 2.0x clean; Coverage 0.0% < 80.0% |
| S4 | declared-scope violation | **Mode 3** | Gaussian bump exp(-(x-0.5)^2 / (2*0.08^2)) | `28.9774` | `0.0126` | `2307.30x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 2307.30x > 2.0x clean; Coverage 0.0% < 80.0% |
| S4 | declared-scope violation | **Mode 3+** | Gaussian bump exp(-(x-0.5)^2 / (2*0.08^2)) | `26.1430` | `0.0116` | `2262.09x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 2262.09x > 2.0x clean; Coverage 0.0% < 80.0% |
| S4 | declared-scope violation | **Two-Stage Placement** | Gaussian bump exp(-(x-0.5)^2 / (2*0.08^2)) | `3.9861` | `0.0079` | `502.10x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 502.10x > 2.0x clean; Coverage 0.0% < 80.0% |
| S5 | declared-scope violation | **Mode 2** | Small constant offset u_bc = 0.05 | `0.0692` | `0.0116` | `5.99x` | `12.0%` [7.0, 19.81] | FAR `nan%` [nan, nan] | Error 5.99x > 2.0x clean; Coverage 12.0% < 80.0% |
| S5 | declared-scope violation | **Mode 3** | Small constant offset u_bc = 0.05 | `0.0733` | `0.0126` | `5.84x` | `11.0%` [6.25, 18.63] | FAR `nan%` [nan, nan] | Error 5.84x > 2.0x clean; Coverage 11.0% < 80.0% |
| S5 | declared-scope violation | **Mode 3+** | Small constant offset u_bc = 0.05 | `0.0692` | `0.0116` | `5.99x` | `12.0%` [7.0, 19.81] | FAR `nan%` [nan, nan] | Error 5.99x > 2.0x clean; Coverage 12.0% < 80.0% |
| S5 | declared-scope violation | **Two-Stage Placement** | Small constant offset u_bc = 0.05 | `0.0542` | `0.0079` | `6.83x` | `1.0%` [0.18, 5.45] | FAR `nan%` [nan, nan] | Error 6.83x > 2.0x clean; Coverage 1.0% < 80.0% |
| S5 | declared-scope violation | **Mode 2** | Moderate constant offset u_bc = 0.15 | `0.1886` | `0.0116` | `16.32x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 16.32x > 2.0x clean; Coverage 0.0% < 80.0% |
| S5 | declared-scope violation | **Mode 3** | Moderate constant offset u_bc = 0.15 | `0.1911` | `0.0126` | `15.21x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 15.21x > 2.0x clean; Coverage 0.0% < 80.0% |
| S5 | declared-scope violation | **Mode 3+** | Moderate constant offset u_bc = 0.15 | `0.1885` | `0.0116` | `16.32x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 16.32x > 2.0x clean; Coverage 0.0% < 80.0% |
| S5 | declared-scope violation | **Two-Stage Placement** | Moderate constant offset u_bc = 0.15 | `0.1549` | `0.0079` | `19.51x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 19.51x > 2.0x clean; Coverage 0.0% < 80.0% |
| S5 | declared-scope violation | **Mode 2** | Linearly drifting boundary u_bc(t) = 0.20 * t | `0.1007` | `0.0116` | `8.72x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 8.72x > 2.0x clean; Coverage 0.0% < 80.0% |
| S5 | declared-scope violation | **Mode 3** | Linearly drifting boundary u_bc(t) = 0.20 * t | `0.1034` | `0.0126` | `8.24x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 8.24x > 2.0x clean; Coverage 0.0% < 80.0% |
| S5 | declared-scope violation | **Mode 3+** | Linearly drifting boundary u_bc(t) = 0.20 * t | `0.1007` | `0.0116` | `8.71x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 8.71x > 2.0x clean; Coverage 0.0% < 80.0% |
| S5 | declared-scope violation | **Two-Stage Placement** | Linearly drifting boundary u_bc(t) = 0.20 * t | `0.0742` | `0.0079` | `9.35x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 9.35x > 2.0x clean; Coverage 0.0% < 80.0% |
| S6 | declared-scope violation | **Mode 2** | Small constant source s = 0.1 | `0.1694` | `0.0116` | `14.67x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 14.67x > 2.0x clean; Coverage 0.0% < 80.0% |
| S6 | declared-scope violation | **Mode 3** | Small constant source s = 0.1 | `0.1714` | `0.0126` | `13.65x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 13.65x > 2.0x clean; Coverage 0.0% < 80.0% |
| S6 | declared-scope violation | **Mode 3+** | Small constant source s = 0.1 | `0.1694` | `0.0116` | `14.66x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 14.66x > 2.0x clean; Coverage 0.0% < 80.0% |
| S6 | declared-scope violation | **Two-Stage Placement** | Small constant source s = 0.1 | `0.1711` | `0.0079` | `21.55x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 21.55x > 2.0x clean; Coverage 0.0% < 80.0% |
| S6 | declared-scope violation | **Mode 2** | Moderate constant source s = 0.5 | `0.7144` | `0.0116` | `61.83x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 61.83x > 2.0x clean; Coverage 0.0% < 80.0% |
| S6 | declared-scope violation | **Mode 3** | Moderate constant source s = 0.5 | `0.7162` | `0.0126` | `57.03x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 57.03x > 2.0x clean; Coverage 0.0% < 80.0% |
| S6 | declared-scope violation | **Mode 3+** | Moderate constant source s = 0.5 | `0.7144` | `0.0116` | `61.81x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 61.81x > 2.0x clean; Coverage 0.0% < 80.0% |
| S6 | declared-scope violation | **Two-Stage Placement** | Moderate constant source s = 0.5 | `0.6965` | `0.0079` | `87.74x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 87.74x > 2.0x clean; Coverage 0.0% < 80.0% |
| S6 | declared-scope violation | **Mode 2** | Strong constant source s = 2.0 | `0.9900` | `0.0116` | `85.69x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 85.69x > 2.0x clean; Coverage 0.0% < 80.0% |
| S6 | declared-scope violation | **Mode 3** | Strong constant source s = 2.0 | `0.9953` | `0.0126` | `79.25x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 79.25x > 2.0x clean; Coverage 0.0% < 80.0% |
| S6 | declared-scope violation | **Mode 3+** | Strong constant source s = 2.0 | `0.9900` | `0.0116` | `85.66x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 85.66x > 2.0x clean; Coverage 0.0% < 80.0% |
| S6 | declared-scope violation | **Two-Stage Placement** | Strong constant source s = 2.0 | `0.9900` | `0.0079` | `124.70x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 124.70x > 2.0x clean; Coverage 0.0% < 80.0% |
| S7 | declared-scope violation | **Anomaly Cascade** | Mild linear ramp alpha(x) = alpha0*(1 + 0.5*(x-0.5)) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `nan%` [nan, nan] | Detection rate 75.0% < 80.0% |
| S7 | declared-scope violation | **Mode 2** | Mild linear ramp alpha(x) = alpha0*(1 + 0.5*(x-0.5)) | `0.0326` | `0.0116` | `2.82x` | `61.0%` [51.2, 69.98] | FAR `nan%` [nan, nan] | Error 2.82x > 2.0x clean; Coverage 61.0% < 80.0% |
| S7 | declared-scope violation | **Mode 3** | Mild linear ramp alpha(x) = alpha0*(1 + 0.5*(x-0.5)) | `0.0310` | `0.0126` | `2.47x` | `63.0%` [53.22, 71.82] | FAR `nan%` [nan, nan] | Error 2.47x > 2.0x clean; Coverage 63.0% < 80.0% |
| S7 | declared-scope violation | **Mode 3+** | Mild linear ramp alpha(x) = alpha0*(1 + 0.5*(x-0.5)) | `0.0326` | `0.0116` | `2.82x` | `61.0%` [51.2, 69.98] | FAR `nan%` [nan, nan] | Error 2.82x > 2.0x clean; Coverage 61.0% < 80.0% |
| S7 | declared-scope violation | **Mode 2** | Steep linear ramp alpha(x) = alpha0*(1 + 1.5*(x-0.5)) | `0.0849` | `0.0116` | `7.35x` | `19.0%` [12.51, 27.78] | FAR `nan%` [nan, nan] | Error 7.35x > 2.0x clean; Coverage 19.0% < 80.0% |
| S7 | declared-scope violation | **Mode 3** | Steep linear ramp alpha(x) = alpha0*(1 + 1.5*(x-0.5)) | `0.0873` | `0.0126` | `6.95x` | `22.0%` [15.0, 31.07] | FAR `nan%` [nan, nan] | Error 6.95x > 2.0x clean; Coverage 22.0% < 80.0% |
| S7 | declared-scope violation | **Mode 3+** | Steep linear ramp alpha(x) = alpha0*(1 + 1.5*(x-0.5)) | `0.0849` | `0.0116` | `7.35x` | `19.0%` [12.51, 27.78] | FAR `nan%` [nan, nan] | Error 7.35x > 2.0x clean; Coverage 19.0% < 80.0% |
| S7 | declared-scope violation | **Two-Stage Placement** | Steep linear ramp alpha(x) = alpha0*(1 + 1.5*(x-0.5)) | `0.0305` | `0.0079` | `3.85x` | `24.0%` [16.69, 33.23] | FAR `nan%` [nan, nan] | Error 3.85x > 2.0x clean; Coverage 24.0% < 80.0% |
| S7 | declared-scope violation | **Mode 2** | Step discontinuity alpha(x) = 2*alpha0 for x > 0.5 | `0.4882` | `0.0116` | `42.26x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 42.26x > 2.0x clean; Coverage 0.0% < 80.0% |
| S7 | declared-scope violation | **Mode 3** | Step discontinuity alpha(x) = 2*alpha0 for x > 0.5 | `0.4839` | `0.0126` | `38.53x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 38.53x > 2.0x clean; Coverage 0.0% < 80.0% |
| S7 | declared-scope violation | **Mode 3+** | Step discontinuity alpha(x) = 2*alpha0 for x > 0.5 | `0.4882` | `0.0116` | `42.24x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 42.24x > 2.0x clean; Coverage 0.0% < 80.0% |
| S7 | declared-scope violation | **Two-Stage Placement** | Step discontinuity alpha(x) = 2*alpha0 for x > 0.5 | `0.5170` | `0.0079` | `65.12x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 65.12x > 2.0x clean; Coverage 0.0% < 80.0% |
| S9 | robustness | **Anomaly Cascade** | Small jitter sigma_jitter = 0.01 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `nan%` [nan, nan] | Detection rate 59.0% < 80.0% |
| S9 | robustness | **Mode 2** | Moderate jitter sigma_jitter = 0.03 | `0.0377` | `0.0116` | `3.26x` | `50.0%` [40.38, 59.62] | FAR `nan%` [nan, nan] | Error 3.26x > 2.0x clean; Coverage 50.0% < 80.0% |
| S9 | robustness | **Mode 3** | Moderate jitter sigma_jitter = 0.03 | `0.0407` | `0.0126` | `3.24x` | `48.0%` [38.46, 57.68] | FAR `nan%` [nan, nan] | Error 3.24x > 2.0x clean; Coverage 48.0% < 80.0% |
| S9 | robustness | **Mode 3+** | Moderate jitter sigma_jitter = 0.03 | `0.0377` | `0.0116` | `3.26x` | `50.0%` [40.38, 59.62] | FAR `nan%` [nan, nan] | Error 3.26x > 2.0x clean; Coverage 50.0% < 80.0% |
| S9 | robustness | **Mode 2** | Large jitter sigma_jitter = 0.06 | `0.0918` | `0.0116` | `7.94x` | `17.0%` [10.89, 25.55] | FAR `nan%` [nan, nan] | Error 7.94x > 2.0x clean; Coverage 17.0% < 80.0% |
| S9 | robustness | **Mode 3** | Large jitter sigma_jitter = 0.06 | `0.0900` | `0.0126` | `7.17x` | `15.0%` [9.31, 23.28] | FAR `nan%` [nan, nan] | Error 7.17x > 2.0x clean; Coverage 15.0% < 80.0% |
| S9 | robustness | **Mode 3+** | Large jitter sigma_jitter = 0.06 | `0.0918` | `0.0116` | `7.94x` | `17.0%` [10.89, 25.55] | FAR `nan%` [nan, nan] | Error 7.94x > 2.0x clean; Coverage 17.0% < 80.0% |
| S10 | robustness | **Anomaly Cascade** | Small sensor bias b = 3 sigma (0.03) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `nan%` [nan, nan] | Detection rate 51.0% < 80.0% |
| S12 | robustness | **Mode 2** | Sub-grid low diffusivity alpha = 5e-4 | `1.0000` | `0.0116` | `86.56x` | `88.0%` [80.19, 93.0] | FAR `nan%` [nan, nan] | Error 86.56x > 2.0x clean |
| S12 | robustness | **Mode 3** | Sub-grid low diffusivity alpha = 5e-4 | `0.9690` | `0.0126` | `77.15x` | `80.0%` [71.12, 86.66] | FAR `nan%` [nan, nan] | Error 77.15x > 2.0x clean |
| S12 | robustness | **Mode 3+** | Sub-grid low diffusivity alpha = 5e-4 | `1.0002` | `0.0116` | `86.55x` | `88.0%` [80.19, 93.0] | FAR `nan%` [nan, nan] | Error 86.55x > 2.0x clean |
| S12 | robustness | **Two-Stage Placement** | Sub-grid low diffusivity alpha = 5e-4 | `1.0000` | `0.0079` | `125.96x` | `90.0%` [82.56, 94.48] | FAR `nan%` [nan, nan] | Error 125.96x > 2.0x clean |
| S12 | robustness | **Mode 2** | high-alpha, information-limited | `0.1075` | `0.0116` | `9.30x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 9.30x > 2.0x clean; Coverage 0.0% < 80.0% |
| S12 | robustness | **Mode 3** | high-alpha, information-limited | `0.1031` | `0.0126` | `8.21x` | `22.0%` [15.0, 31.07] | FAR `nan%` [nan, nan] | Error 8.21x > 2.0x clean; Coverage 22.0% < 80.0% |
| S12 | robustness | **Mode 3+** | high-alpha, information-limited | `0.1075` | `0.0116` | `9.30x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 9.30x > 2.0x clean; Coverage 0.0% < 80.0% |
| S12 | robustness | **Mode 2** | Super-grid extreme diffusivity alpha = 20.0 | `0.5000` | `0.0116` | `43.28x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 43.28x > 2.0x clean; Coverage 0.0% < 80.0% |
| S12 | robustness | **Mode 3** | Super-grid extreme diffusivity alpha = 20.0 | `0.5000` | `0.0126` | `39.81x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 39.81x > 2.0x clean; Coverage 0.0% < 80.0% |
| S12 | robustness | **Mode 3+** | Super-grid extreme diffusivity alpha = 20.0 | `0.5001` | `0.0116` | `43.27x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 43.27x > 2.0x clean; Coverage 0.0% < 80.0% |
| S12 | robustness | **Two-Stage Placement** | Super-grid extreme diffusivity alpha = 20.0 | `0.5000` | `0.0079` | `62.98x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | Error 62.98x > 2.0x clean; Coverage 0.0% < 80.0% |
| S13 | robustness | **Anomaly Cascade** | Severe drift delta = 10% | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `29.0%` [21.01, 38.54] | Healthy FAR 29.0% > 15.0% |

---

## 6. Complete Table of All 195 Cells in v2b

| Scen | Category | Module | Severity Level | Abs Med Rel Err | Clean Err | Ratio | Coverage % [95% CI] | FAR / Det % [95% CI] | Status |
| :---: | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| S1 | robustness | Anomaly Cascade | Assumed 0.05, true 0.01 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `0.0%` [0.0, 3.7] | **PASS** |
| S1 | robustness | Mode 2 | Assumed 0.05, true 0.01 | `0.0171` | `0.0116` | `1.48x` | `100.0%` [96.3, 100.0] | FAR `nan%` [nan, nan] | **PASS** |
| S1 | robustness | Mode 3 | Assumed 0.05, true 0.01 | `0.0176` | `0.0126` | `1.40x` | `100.0%` [96.3, 100.0] | FAR `nan%` [nan, nan] | **PASS** |
| S1 | robustness | Mode 3+ | Assumed 0.05, true 0.01 | `0.0171` | `0.0116` | `1.48x` | `100.0%` [96.3, 100.0] | FAR `nan%` [nan, nan] | **PASS** |
| S1 | robustness | Two-Stage Placement | Assumed 0.05, true 0.01 | `0.0402` | `0.0079` | `5.06x` | `99.0%` [94.55, 99.82] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S1 | robustness | Anomaly Cascade | Assumed 0.01, true 0.05 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `100.0%` [96.3, 100.0] | <span style='color:red;'>**FAIL**</span> |
| S1 | robustness | Mode 2 | Assumed 0.01, true 0.05 | `0.0656` | `0.0550` | `1.19x` | `29.0%` [21.01, 38.54] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S1 | robustness | Mode 3 | Assumed 0.01, true 0.05 | `0.0646` | `0.0572` | `1.13x` | `30.0%` [21.89, 39.58] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S1 | robustness | Mode 3+ | Assumed 0.01, true 0.05 | `0.0656` | `0.0550` | `1.19x` | `29.0%` [21.01, 38.54] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S1 | robustness | Two-Stage Placement | Assumed 0.01, true 0.05 | `0.0065` | `0.0454` | `0.14x` | `96.0%` [90.16, 98.43] | FAR `nan%` [nan, nan] | **PASS** |
| S1 | robustness | Anomaly Cascade | Assumed 0.01, true 0.03 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `99.0%` [94.55, 99.82] | <span style='color:red;'>**FAIL**</span> |
| S1 | robustness | Mode 2 | Assumed 0.01, true 0.03 | `0.0394` | `0.0345` | `1.14x` | `47.0%` [37.51, 56.71] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S1 | robustness | Mode 3 | Assumed 0.01, true 0.03 | `0.0408` | `0.0345` | `1.18x` | `45.0%` [35.61, 54.76] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S1 | robustness | Mode 3+ | Assumed 0.01, true 0.03 | `0.0394` | `0.0345` | `1.14x` | `47.0%` [37.51, 56.71] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S1 | robustness | Two-Stage Placement | Assumed 0.01, true 0.03 | `0.0086` | `0.0216` | `0.40x` | `96.0%` [90.16, 98.43] | FAR `nan%` [nan, nan] | **PASS** |
| S2 | robustness | Anomaly Cascade | Student-t df=3 (moderate tail) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `17.0%` [10.89, 25.55] | <span style='color:red;'>**FAIL**</span> |
| S2 | robustness | Mode 2 | Student-t df=3 (moderate tail) | `0.0111` | `0.0116` | `0.96x` | `95.0%` [88.82, 97.85] | FAR `nan%` [nan, nan] | **PASS** |
| S2 | robustness | Mode 3 | Student-t df=3 (moderate tail) | `0.0114` | `0.0126` | `0.91x` | `95.0%` [88.82, 97.85] | FAR `nan%` [nan, nan] | **PASS** |
| S2 | robustness | Mode 3+ | Student-t df=3 (moderate tail) | `0.0111` | `0.0116` | `0.96x` | `95.0%` [88.82, 97.85] | FAR `nan%` [nan, nan] | **PASS** |
| S2 | robustness | Two-Stage Placement | Student-t df=3 (moderate tail) | `0.0056` | `0.0079` | `0.70x` | `96.0%` [90.16, 98.43] | FAR `nan%` [nan, nan] | **PASS** |
| S2 | robustness | Anomaly Cascade | Student-t df=2.5 with 2% 5-sigma outliers | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `25.0%` [17.55, 34.3] | <span style='color:red;'>**FAIL**</span> |
| S2 | robustness | Mode 2 | Student-t df=2.5 with 2% 5-sigma outliers | `0.0093` | `0.0116` | `0.81x` | `88.0%` [80.19, 93.0] | FAR `nan%` [nan, nan] | **PASS** |
| S2 | robustness | Mode 3 | Student-t df=2.5 with 2% 5-sigma outliers | `0.0089` | `0.0126` | `0.71x` | `88.0%` [80.19, 93.0] | FAR `nan%` [nan, nan] | **PASS** |
| S2 | robustness | Mode 3+ | Student-t df=2.5 with 2% 5-sigma outliers | `0.0093` | `0.0116` | `0.81x` | `88.0%` [80.19, 93.0] | FAR `nan%` [nan, nan] | **PASS** |
| S2 | robustness | Two-Stage Placement | Student-t df=2.5 with 2% 5-sigma outliers | `0.0072` | `0.0079` | `0.91x` | `98.0%` [93.0, 99.45] | FAR `nan%` [nan, nan] | **PASS** |
| S2 | robustness | Anomaly Cascade | Student-t df=2.1 with 5% 5-sigma outliers | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `45.0%` [35.61, 54.76] | <span style='color:red;'>**FAIL**</span> |
| S2 | robustness | Mode 2 | Student-t df=2.1 with 5% 5-sigma outliers | `0.0116` | `0.0116` | `1.00x` | `87.0%` [79.02, 92.24] | FAR `nan%` [nan, nan] | **PASS** |
| S2 | robustness | Mode 3 | Student-t df=2.1 with 5% 5-sigma outliers | `0.0130` | `0.0126` | `1.04x` | `86.0%` [77.86, 91.47] | FAR `nan%` [nan, nan] | **PASS** |
| S2 | robustness | Mode 3+ | Student-t df=2.1 with 5% 5-sigma outliers | `0.0116` | `0.0116` | `1.00x` | `87.0%` [79.02, 92.24] | FAR `nan%` [nan, nan] | **PASS** |
| S2 | robustness | Two-Stage Placement | Student-t df=2.1 with 5% 5-sigma outliers | `0.0066` | `0.0079` | `0.83x` | `95.0%` [88.82, 97.85] | FAR `nan%` [nan, nan] | **PASS** |
| S3 | robustness | Anomaly Cascade | AR(1) rho = 0.50 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `5.0%` [2.15, 11.18] | **PASS** |
| S3 | robustness | Mode 2 | AR(1) rho = 0.50 | `0.0199` | `0.0116` | `1.72x` | `83.0%` [74.45, 89.11] | FAR `nan%` [nan, nan] | **PASS** |
| S3 | robustness | Mode 3 | AR(1) rho = 0.50 | `0.0222` | `0.0126` | `1.76x` | `83.0%` [74.45, 89.11] | FAR `nan%` [nan, nan] | **PASS** |
| S3 | robustness | Mode 3+ | AR(1) rho = 0.50 | `0.0198` | `0.0116` | `1.72x` | `83.0%` [74.45, 89.11] | FAR `nan%` [nan, nan] | **PASS** |
| S3 | robustness | Two-Stage Placement | AR(1) rho = 0.50 | `0.0078` | `0.0079` | `0.98x` | `97.0%` [91.55, 98.97] | FAR `nan%` [nan, nan] | **PASS** |
| S3 | robustness | Anomaly Cascade | AR(1) rho = 0.80 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `20.0%` [13.34, 28.88] | <span style='color:red;'>**FAIL**</span> |
| S3 | robustness | Mode 2 | AR(1) rho = 0.80 | `0.0288` | `0.0116` | `2.50x` | `61.0%` [51.2, 69.98] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S3 | robustness | Mode 3 | AR(1) rho = 0.80 | `0.0266` | `0.0126` | `2.12x` | `63.0%` [53.22, 71.82] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S3 | robustness | Mode 3+ | AR(1) rho = 0.80 | `0.0288` | `0.0116` | `2.50x` | `61.0%` [51.2, 69.98] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S3 | robustness | Two-Stage Placement | AR(1) rho = 0.80 | `0.0083` | `0.0079` | `1.04x` | `94.0%` [87.52, 97.22] | FAR `nan%` [nan, nan] | **PASS** |
| S3 | robustness | Anomaly Cascade | AR(1) rho = 0.95 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `13.0%` [7.76, 20.98] | **PASS** |
| S3 | robustness | Mode 2 | AR(1) rho = 0.95 | `0.0238` | `0.0116` | `2.06x` | `69.0%` [59.37, 77.22] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S3 | robustness | Mode 3 | AR(1) rho = 0.95 | `0.0241` | `0.0126` | `1.92x` | `69.0%` [59.37, 77.22] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S3 | robustness | Mode 3+ | AR(1) rho = 0.95 | `0.0239` | `0.0116` | `2.06x` | `69.0%` [59.37, 77.22] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S3 | robustness | Two-Stage Placement | AR(1) rho = 0.95 | `0.0086` | `0.0079` | `1.08x` | `94.0%` [87.52, 97.22] | FAR `nan%` [nan, nan] | **PASS** |
| S4 | declared-scope violation | Anomaly Cascade | Harmonic double mode sin(2 pi x) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `nan%` [nan, nan] | **PASS** |
| S4 | declared-scope violation | Mode 2 | Harmonic double mode sin(2 pi x) | `98.9987` | `0.0116` | `8569.09x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S4 | declared-scope violation | Mode 3 | Harmonic double mode sin(2 pi x) | `98.9979` | `0.0126` | `7882.62x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S4 | declared-scope violation | Mode 3+ | Harmonic double mode sin(2 pi x) | `98.9883` | `0.0116` | `8565.23x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S4 | declared-scope violation | Two-Stage Placement | Harmonic double mode sin(2 pi x) | `98.9987` | `0.0079` | `12469.92x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S4 | declared-scope violation | Anomaly Cascade | Two-mode sum sin(pi x) + 0.5 sin(3 pi x) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `nan%` [nan, nan] | **PASS** |
| S4 | declared-scope violation | Mode 2 | Two-mode sum sin(pi x) + 0.5 sin(3 pi x) | `0.0563` | `0.0116` | `4.87x` | `35.0%` [26.36, 44.75] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S4 | declared-scope violation | Mode 3 | Two-mode sum sin(pi x) + 0.5 sin(3 pi x) | `0.0558` | `0.0126` | `4.44x` | `36.0%` [27.27, 45.76] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S4 | declared-scope violation | Mode 3+ | Two-mode sum sin(pi x) + 0.5 sin(3 pi x) | `0.0562` | `0.0116` | `4.87x` | `35.0%` [26.36, 44.75] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S4 | declared-scope violation | Two-Stage Placement | Two-mode sum sin(pi x) + 0.5 sin(3 pi x) | `0.0762` | `0.0079` | `9.59x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S4 | declared-scope violation | Anomaly Cascade | Gaussian bump exp(-(x-0.5)^2 / (2*0.08^2)) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `nan%` [nan, nan] | **PASS** |
| S4 | declared-scope violation | Mode 2 | Gaussian bump exp(-(x-0.5)^2 / (2*0.08^2)) | `26.1431` | `0.0116` | `2262.88x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S4 | declared-scope violation | Mode 3 | Gaussian bump exp(-(x-0.5)^2 / (2*0.08^2)) | `28.9774` | `0.0126` | `2307.30x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S4 | declared-scope violation | Mode 3+ | Gaussian bump exp(-(x-0.5)^2 / (2*0.08^2)) | `26.1430` | `0.0116` | `2262.09x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S4 | declared-scope violation | Two-Stage Placement | Gaussian bump exp(-(x-0.5)^2 / (2*0.08^2)) | `3.9861` | `0.0079` | `502.10x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S5 | declared-scope violation | Anomaly Cascade | Small constant offset u_bc = 0.05 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `nan%` [nan, nan] | **PASS** |
| S5 | declared-scope violation | Mode 2 | Small constant offset u_bc = 0.05 | `0.0692` | `0.0116` | `5.99x` | `12.0%` [7.0, 19.81] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S5 | declared-scope violation | Mode 3 | Small constant offset u_bc = 0.05 | `0.0733` | `0.0126` | `5.84x` | `11.0%` [6.25, 18.63] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S5 | declared-scope violation | Mode 3+ | Small constant offset u_bc = 0.05 | `0.0692` | `0.0116` | `5.99x` | `12.0%` [7.0, 19.81] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S5 | declared-scope violation | Two-Stage Placement | Small constant offset u_bc = 0.05 | `0.0542` | `0.0079` | `6.83x` | `1.0%` [0.18, 5.45] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S5 | declared-scope violation | Anomaly Cascade | Moderate constant offset u_bc = 0.15 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `nan%` [nan, nan] | **PASS** |
| S5 | declared-scope violation | Mode 2 | Moderate constant offset u_bc = 0.15 | `0.1886` | `0.0116` | `16.32x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S5 | declared-scope violation | Mode 3 | Moderate constant offset u_bc = 0.15 | `0.1911` | `0.0126` | `15.21x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S5 | declared-scope violation | Mode 3+ | Moderate constant offset u_bc = 0.15 | `0.1885` | `0.0116` | `16.32x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S5 | declared-scope violation | Two-Stage Placement | Moderate constant offset u_bc = 0.15 | `0.1549` | `0.0079` | `19.51x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S5 | declared-scope violation | Anomaly Cascade | Linearly drifting boundary u_bc(t) = 0.20 * t | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `nan%` [nan, nan] | **PASS** |
| S5 | declared-scope violation | Mode 2 | Linearly drifting boundary u_bc(t) = 0.20 * t | `0.1007` | `0.0116` | `8.72x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S5 | declared-scope violation | Mode 3 | Linearly drifting boundary u_bc(t) = 0.20 * t | `0.1034` | `0.0126` | `8.24x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S5 | declared-scope violation | Mode 3+ | Linearly drifting boundary u_bc(t) = 0.20 * t | `0.1007` | `0.0116` | `8.71x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S5 | declared-scope violation | Two-Stage Placement | Linearly drifting boundary u_bc(t) = 0.20 * t | `0.0742` | `0.0079` | `9.35x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S6 | declared-scope violation | Anomaly Cascade | Small constant source s = 0.1 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `nan%` [nan, nan] | **PASS** |
| S6 | declared-scope violation | Mode 2 | Small constant source s = 0.1 | `0.1694` | `0.0116` | `14.67x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S6 | declared-scope violation | Mode 3 | Small constant source s = 0.1 | `0.1714` | `0.0126` | `13.65x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S6 | declared-scope violation | Mode 3+ | Small constant source s = 0.1 | `0.1694` | `0.0116` | `14.66x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S6 | declared-scope violation | Two-Stage Placement | Small constant source s = 0.1 | `0.1711` | `0.0079` | `21.55x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S6 | declared-scope violation | Anomaly Cascade | Moderate constant source s = 0.5 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `nan%` [nan, nan] | **PASS** |
| S6 | declared-scope violation | Mode 2 | Moderate constant source s = 0.5 | `0.7144` | `0.0116` | `61.83x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S6 | declared-scope violation | Mode 3 | Moderate constant source s = 0.5 | `0.7162` | `0.0126` | `57.03x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S6 | declared-scope violation | Mode 3+ | Moderate constant source s = 0.5 | `0.7144` | `0.0116` | `61.81x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S6 | declared-scope violation | Two-Stage Placement | Moderate constant source s = 0.5 | `0.6965` | `0.0079` | `87.74x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S6 | declared-scope violation | Anomaly Cascade | Strong constant source s = 2.0 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `nan%` [nan, nan] | **PASS** |
| S6 | declared-scope violation | Mode 2 | Strong constant source s = 2.0 | `0.9900` | `0.0116` | `85.69x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S6 | declared-scope violation | Mode 3 | Strong constant source s = 2.0 | `0.9953` | `0.0126` | `79.25x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S6 | declared-scope violation | Mode 3+ | Strong constant source s = 2.0 | `0.9900` | `0.0116` | `85.66x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S6 | declared-scope violation | Two-Stage Placement | Strong constant source s = 2.0 | `0.9900` | `0.0079` | `124.70x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S7 | declared-scope violation | Anomaly Cascade | Mild linear ramp alpha(x) = alpha0*(1 + 0.5*(x-0.5)) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S7 | declared-scope violation | Mode 2 | Mild linear ramp alpha(x) = alpha0*(1 + 0.5*(x-0.5)) | `0.0326` | `0.0116` | `2.82x` | `61.0%` [51.2, 69.98] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S7 | declared-scope violation | Mode 3 | Mild linear ramp alpha(x) = alpha0*(1 + 0.5*(x-0.5)) | `0.0310` | `0.0126` | `2.47x` | `63.0%` [53.22, 71.82] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S7 | declared-scope violation | Mode 3+ | Mild linear ramp alpha(x) = alpha0*(1 + 0.5*(x-0.5)) | `0.0326` | `0.0116` | `2.82x` | `61.0%` [51.2, 69.98] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S7 | declared-scope violation | Two-Stage Placement | Mild linear ramp alpha(x) = alpha0*(1 + 0.5*(x-0.5)) | `0.0089` | `0.0079` | `1.11x` | `96.0%` [90.16, 98.43] | FAR `nan%` [nan, nan] | **PASS** |
| S7 | declared-scope violation | Anomaly Cascade | Steep linear ramp alpha(x) = alpha0*(1 + 1.5*(x-0.5)) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `nan%` [nan, nan] | **PASS** |
| S7 | declared-scope violation | Mode 2 | Steep linear ramp alpha(x) = alpha0*(1 + 1.5*(x-0.5)) | `0.0849` | `0.0116` | `7.35x` | `19.0%` [12.51, 27.78] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S7 | declared-scope violation | Mode 3 | Steep linear ramp alpha(x) = alpha0*(1 + 1.5*(x-0.5)) | `0.0873` | `0.0126` | `6.95x` | `22.0%` [15.0, 31.07] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S7 | declared-scope violation | Mode 3+ | Steep linear ramp alpha(x) = alpha0*(1 + 1.5*(x-0.5)) | `0.0849` | `0.0116` | `7.35x` | `19.0%` [12.51, 27.78] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S7 | declared-scope violation | Two-Stage Placement | Steep linear ramp alpha(x) = alpha0*(1 + 1.5*(x-0.5)) | `0.0305` | `0.0079` | `3.85x` | `24.0%` [16.69, 33.23] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S7 | declared-scope violation | Anomaly Cascade | Step discontinuity alpha(x) = 2*alpha0 for x > 0.5 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `nan%` [nan, nan] | **PASS** |
| S7 | declared-scope violation | Mode 2 | Step discontinuity alpha(x) = 2*alpha0 for x > 0.5 | `0.4882` | `0.0116` | `42.26x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S7 | declared-scope violation | Mode 3 | Step discontinuity alpha(x) = 2*alpha0 for x > 0.5 | `0.4839` | `0.0126` | `38.53x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S7 | declared-scope violation | Mode 3+ | Step discontinuity alpha(x) = 2*alpha0 for x > 0.5 | `0.4882` | `0.0116` | `42.24x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S7 | declared-scope violation | Two-Stage Placement | Step discontinuity alpha(x) = 2*alpha0 for x > 0.5 | `0.5170` | `0.0079` | `65.12x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S8 | robustness | Anomaly Cascade | 10% readings missing (1 sensor dropped) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `9.0%` [4.81, 16.23] | **PASS** |
| S8 | robustness | Mode 2 | 10% readings missing (1 sensor dropped) | `0.0155` | `0.0116` | `1.34x` | `87.0%` [79.02, 92.24] | FAR `nan%` [nan, nan] | **PASS** |
| S8 | robustness | Mode 3 | 10% readings missing (1 sensor dropped) | `0.0132` | `0.0126` | `1.05x` | `86.0%` [77.86, 91.47] | FAR `nan%` [nan, nan] | **PASS** |
| S8 | robustness | Mode 3+ | 10% readings missing (1 sensor dropped) | `0.0155` | `0.0116` | `1.34x` | `87.0%` [79.02, 92.24] | FAR `nan%` [nan, nan] | **PASS** |
| S8 | robustness | Two-Stage Placement | 10% readings missing (1 sensor dropped) | `0.0092` | `0.0079` | `1.16x` | `92.0%` [85.0, 95.89] | FAR `nan%` [nan, nan] | **PASS** |
| S8 | robustness | Anomaly Cascade | 30% readings missing (3 sensors dropped) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `3.0%` [1.03, 8.45] | **PASS** |
| S8 | robustness | Mode 2 | 30% readings missing (3 sensors dropped) | `0.0185` | `0.0116` | `1.60x` | `95.0%` [88.82, 97.85] | FAR `nan%` [nan, nan] | **PASS** |
| S8 | robustness | Mode 3 | 30% readings missing (3 sensors dropped) | `0.0184` | `0.0126` | `1.46x` | `94.0%` [87.52, 97.22] | FAR `nan%` [nan, nan] | **PASS** |
| S8 | robustness | Mode 3+ | 30% readings missing (3 sensors dropped) | `0.0185` | `0.0116` | `1.60x` | `95.0%` [88.82, 97.85] | FAR `nan%` [nan, nan] | **PASS** |
| S8 | robustness | Two-Stage Placement | 30% readings missing (3 sensors dropped) | `0.0090` | `0.0079` | `1.13x` | `94.0%` [87.52, 97.22] | FAR `nan%` [nan, nan] | **PASS** |
| S8 | robustness | Anomaly Cascade | 50% readings missing (5 sensors dropped) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `5.0%` [2.15, 11.18] | **PASS** |
| S8 | robustness | Mode 2 | 50% readings missing (5 sensors dropped) | `0.0248` | `0.0116` | `2.15x` | `92.0%` [85.0, 95.89] | FAR `nan%` [nan, nan] | **PASS** |
| S8 | robustness | Mode 3 | 50% readings missing (5 sensors dropped) | `0.0258` | `0.0126` | `2.05x` | `91.0%` [83.77, 95.19] | FAR `nan%` [nan, nan] | **PASS** |
| S8 | robustness | Mode 3+ | 50% readings missing (5 sensors dropped) | `0.0248` | `0.0116` | `2.15x` | `92.0%` [85.0, 95.89] | FAR `nan%` [nan, nan] | **PASS** |
| S8 | robustness | Two-Stage Placement | 50% readings missing (5 sensors dropped) | `0.0081` | `0.0079` | `1.02x` | `97.0%` [91.55, 98.97] | FAR `nan%` [nan, nan] | **PASS** |
| S9 | robustness | Anomaly Cascade | Small jitter sigma_jitter = 0.01 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S9 | robustness | Mode 2 | Small jitter sigma_jitter = 0.01 | `0.0184` | `0.0116` | `1.59x` | `82.0%` [73.33, 88.3] | FAR `nan%` [nan, nan] | **PASS** |
| S9 | robustness | Mode 3 | Small jitter sigma_jitter = 0.01 | `0.0174` | `0.0126` | `1.38x` | `82.0%` [73.33, 88.3] | FAR `nan%` [nan, nan] | **PASS** |
| S9 | robustness | Mode 3+ | Small jitter sigma_jitter = 0.01 | `0.0184` | `0.0116` | `1.59x` | `82.0%` [73.33, 88.3] | FAR `nan%` [nan, nan] | **PASS** |
| S9 | robustness | Two-Stage Placement | Small jitter sigma_jitter = 0.01 | `0.0086` | `0.0079` | `1.08x` | `95.0%` [88.82, 97.85] | FAR `nan%` [nan, nan] | **PASS** |
| S9 | robustness | Anomaly Cascade | Moderate jitter sigma_jitter = 0.03 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `nan%` [nan, nan] | **PASS** |
| S9 | robustness | Mode 2 | Moderate jitter sigma_jitter = 0.03 | `0.0377` | `0.0116` | `3.26x` | `50.0%` [40.38, 59.62] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S9 | robustness | Mode 3 | Moderate jitter sigma_jitter = 0.03 | `0.0407` | `0.0126` | `3.24x` | `48.0%` [38.46, 57.68] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S9 | robustness | Mode 3+ | Moderate jitter sigma_jitter = 0.03 | `0.0377` | `0.0116` | `3.26x` | `50.0%` [40.38, 59.62] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S9 | robustness | Two-Stage Placement | Moderate jitter sigma_jitter = 0.03 | `0.0079` | `0.0079` | `0.99x` | `95.0%` [88.82, 97.85] | FAR `nan%` [nan, nan] | **PASS** |
| S9 | robustness | Anomaly Cascade | Large jitter sigma_jitter = 0.06 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `nan%` [nan, nan] | **PASS** |
| S9 | robustness | Mode 2 | Large jitter sigma_jitter = 0.06 | `0.0918` | `0.0116` | `7.94x` | `17.0%` [10.89, 25.55] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S9 | robustness | Mode 3 | Large jitter sigma_jitter = 0.06 | `0.0900` | `0.0126` | `7.17x` | `15.0%` [9.31, 23.28] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S9 | robustness | Mode 3+ | Large jitter sigma_jitter = 0.06 | `0.0918` | `0.0116` | `7.94x` | `17.0%` [10.89, 25.55] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S9 | robustness | Two-Stage Placement | Large jitter sigma_jitter = 0.06 | `0.0080` | `0.0079` | `1.01x` | `96.0%` [90.16, 98.43] | FAR `nan%` [nan, nan] | **PASS** |
| S10 | robustness | Anomaly Cascade | Small sensor bias b = 3 sigma (0.03) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S10 | robustness | Mode 2 | Small sensor bias b = 3 sigma (0.03) | `0.0155` | `0.0116` | `1.34x` | `93.0%` [86.25, 96.57] | FAR `nan%` [nan, nan] | **PASS** |
| S10 | robustness | Mode 3 | Small sensor bias b = 3 sigma (0.03) | `0.0163` | `0.0126` | `1.29x` | `93.0%` [86.25, 96.57] | FAR `nan%` [nan, nan] | **PASS** |
| S10 | robustness | Mode 3+ | Small sensor bias b = 3 sigma (0.03) | `0.0155` | `0.0116` | `1.34x` | `93.0%` [86.25, 96.57] | FAR `nan%` [nan, nan] | **PASS** |
| S10 | robustness | Two-Stage Placement | Small sensor bias b = 3 sigma (0.03) | `0.0079` | `0.0079` | `1.00x` | `94.0%` [87.52, 97.22] | FAR `nan%` [nan, nan] | **PASS** |
| S10 | robustness | Anomaly Cascade | Medium sensor bias b = 6 sigma (0.06) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `nan%` [nan, nan] | **PASS** |
| S10 | robustness | Mode 2 | Medium sensor bias b = 6 sigma (0.06) | `0.0133` | `0.0116` | `1.15x` | `89.0%` [81.37, 93.75] | FAR `nan%` [nan, nan] | **PASS** |
| S10 | robustness | Mode 3 | Medium sensor bias b = 6 sigma (0.06) | `0.0146` | `0.0126` | `1.17x` | `89.0%` [81.37, 93.75] | FAR `nan%` [nan, nan] | **PASS** |
| S10 | robustness | Mode 3+ | Medium sensor bias b = 6 sigma (0.06) | `0.0133` | `0.0116` | `1.15x` | `89.0%` [81.37, 93.75] | FAR `nan%` [nan, nan] | **PASS** |
| S10 | robustness | Two-Stage Placement | Medium sensor bias b = 6 sigma (0.06) | `0.0059` | `0.0079` | `0.74x` | `94.0%` [87.52, 97.22] | FAR `nan%` [nan, nan] | **PASS** |
| S10 | robustness | Anomaly Cascade | Strong sensor bias b = 15 sigma (0.15) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `nan%` [nan, nan] | **PASS** |
| S10 | robustness | Mode 2 | Strong sensor bias b = 15 sigma (0.15) | `0.0153` | `0.0116` | `1.33x` | `96.0%` [90.16, 98.43] | FAR `nan%` [nan, nan] | **PASS** |
| S10 | robustness | Mode 3 | Strong sensor bias b = 15 sigma (0.15) | `0.0165` | `0.0126` | `1.31x` | `93.0%` [86.25, 96.57] | FAR `nan%` [nan, nan] | **PASS** |
| S10 | robustness | Mode 3+ | Strong sensor bias b = 15 sigma (0.15) | `0.0153` | `0.0116` | `1.33x` | `96.0%` [90.16, 98.43] | FAR `nan%` [nan, nan] | **PASS** |
| S10 | robustness | Two-Stage Placement | Strong sensor bias b = 15 sigma (0.15) | `0.0079` | `0.0079` | `0.99x` | `98.0%` [93.0, 99.45] | FAR `nan%` [nan, nan] | **PASS** |
| S11 | robustness | Anomaly Cascade | Sparse array N = 5 sensors | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `1.0%` [0.18, 5.45] | **PASS** |
| S11 | robustness | Mode 2 | Sparse array N = 5 sensors | `0.0166` | `0.0116` | `1.44x` | `95.0%` [88.82, 97.85] | FAR `nan%` [nan, nan] | **PASS** |
| S11 | robustness | Mode 3 | Sparse array N = 5 sensors | `0.0182` | `0.0126` | `1.45x` | `95.0%` [88.82, 97.85] | FAR `nan%` [nan, nan] | **PASS** |
| S11 | robustness | Mode 3+ | Sparse array N = 5 sensors | `0.0166` | `0.0116` | `1.44x` | `95.0%` [88.82, 97.85] | FAR `nan%` [nan, nan] | **PASS** |
| S11 | robustness | Two-Stage Placement | Sparse array N = 5 sensors | `0.0083` | `0.0079` | `1.04x` | `97.0%` [91.55, 98.97] | FAR `nan%` [nan, nan] | **PASS** |
| S11 | robustness | Anomaly Cascade | Very sparse array N = 3 sensors | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `5.0%` [2.15, 11.18] | **PASS** |
| S11 | robustness | Mode 2 | Very sparse array N = 3 sensors | `0.0216` | `0.0116` | `1.86x` | `91.0%` [83.77, 95.19] | FAR `nan%` [nan, nan] | **PASS** |
| S11 | robustness | Mode 3 | Very sparse array N = 3 sensors | `0.0247` | `0.0126` | `1.97x` | `89.0%` [81.37, 93.75] | FAR `nan%` [nan, nan] | **PASS** |
| S11 | robustness | Mode 3+ | Very sparse array N = 3 sensors | `0.0216` | `0.0116` | `1.87x` | `91.0%` [83.77, 95.19] | FAR `nan%` [nan, nan] | **PASS** |
| S11 | robustness | Two-Stage Placement | Very sparse array N = 3 sensors | `0.0156` | `0.0079` | `1.97x` | `96.0%` [90.16, 98.43] | FAR `nan%` [nan, nan] | **PASS** |
| S11 | robustness | Anomaly Cascade | Minimal array N = 2 sensors | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `6.0%` [2.78, 12.48] | **PASS** |
| S11 | robustness | Mode 2 | Minimal array N = 2 sensors | `0.0205` | `0.0116` | `1.77x` | `94.0%` [87.52, 97.22] | FAR `nan%` [nan, nan] | **PASS** |
| S11 | robustness | Mode 3 | Minimal array N = 2 sensors | `0.0245` | `0.0126` | `1.95x` | `95.0%` [88.82, 97.85] | FAR `nan%` [nan, nan] | **PASS** |
| S11 | robustness | Mode 3+ | Minimal array N = 2 sensors | `0.0205` | `0.0116` | `1.77x` | `94.0%` [87.52, 97.22] | FAR `nan%` [nan, nan] | **PASS** |
| S11 | robustness | Two-Stage Placement | Minimal array N = 2 sensors | `0.0204` | `0.0079` | `2.57x` | `95.0%` [88.82, 97.85] | FAR `nan%` [nan, nan] | **PASS** |
| S12 | robustness | Anomaly Cascade | Sub-grid low diffusivity alpha = 5e-4 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `nan%` [nan, nan] | **PASS** |
| S12 | robustness | Mode 2 | Sub-grid low diffusivity alpha = 5e-4 | `1.0000` | `0.0116` | `86.56x` | `88.0%` [80.19, 93.0] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S12 | robustness | Mode 3 | Sub-grid low diffusivity alpha = 5e-4 | `0.9690` | `0.0126` | `77.15x` | `80.0%` [71.12, 86.66] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S12 | robustness | Mode 3+ | Sub-grid low diffusivity alpha = 5e-4 | `1.0002` | `0.0116` | `86.55x` | `88.0%` [80.19, 93.0] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S12 | robustness | Two-Stage Placement | Sub-grid low diffusivity alpha = 5e-4 | `1.0000` | `0.0079` | `125.96x` | `90.0%` [82.56, 94.48] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S12 | robustness | Anomaly Cascade | high-alpha, information-limited | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `nan%` [nan, nan] | **PASS** |
| S12 | robustness | Mode 2 | high-alpha, information-limited | `0.1075` | `0.0116` | `9.30x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S12 | robustness | Mode 3 | high-alpha, information-limited | `0.1031` | `0.0126` | `8.21x` | `22.0%` [15.0, 31.07] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S12 | robustness | Mode 3+ | high-alpha, information-limited | `0.1075` | `0.0116` | `9.30x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S12 | robustness | Two-Stage Placement | high-alpha, information-limited | `0.0101` | `0.0079` | `1.28x` | `94.0%` [87.52, 97.22] | FAR `nan%` [nan, nan] | **PASS** |
| S12 | robustness | Anomaly Cascade | Super-grid extreme diffusivity alpha = 20.0 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `nan%` [nan, nan] | **PASS** |
| S12 | robustness | Mode 2 | Super-grid extreme diffusivity alpha = 20.0 | `0.5000` | `0.0116` | `43.28x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S12 | robustness | Mode 3 | Super-grid extreme diffusivity alpha = 20.0 | `0.5000` | `0.0126` | `39.81x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S12 | robustness | Mode 3+ | Super-grid extreme diffusivity alpha = 20.0 | `0.5001` | `0.0116` | `43.27x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S12 | robustness | Two-Stage Placement | Super-grid extreme diffusivity alpha = 20.0 | `0.5000` | `0.0079` | `62.98x` | `0.0%` [0.0, 3.7] | FAR `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S13 | robustness | Anomaly Cascade | Slow drift delta = 2% | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `7.0%` [3.43, 13.75] | **PASS** |
| S13 | robustness | Mode 2 | Slow drift delta = 2% | `0.0144` | `0.0116` | `1.24x` | `92.0%` [85.0, 95.89] | FAR `nan%` [nan, nan] | **PASS** |
| S13 | robustness | Mode 3 | Slow drift delta = 2% | `0.0132` | `0.0126` | `1.05x` | `91.0%` [83.77, 95.19] | FAR `nan%` [nan, nan] | **PASS** |
| S13 | robustness | Mode 3+ | Slow drift delta = 2% | `0.0144` | `0.0116` | `1.24x` | `92.0%` [85.0, 95.89] | FAR `nan%` [nan, nan] | **PASS** |
| S13 | robustness | Two-Stage Placement | Slow drift delta = 2% | `0.0075` | `0.0079` | `0.94x` | `96.0%` [90.16, 98.43] | FAR `nan%` [nan, nan] | **PASS** |
| S13 | robustness | Anomaly Cascade | Moderate drift delta = 5% | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `7.0%` [3.43, 13.75] | **PASS** |
| S13 | robustness | Mode 2 | Moderate drift delta = 5% | `0.0172` | `0.0116` | `1.49x` | `89.0%` [81.37, 93.75] | FAR `nan%` [nan, nan] | **PASS** |
| S13 | robustness | Mode 3 | Moderate drift delta = 5% | `0.0169` | `0.0126` | `1.35x` | `90.0%` [82.56, 94.48] | FAR `nan%` [nan, nan] | **PASS** |
| S13 | robustness | Mode 3+ | Moderate drift delta = 5% | `0.0172` | `0.0116` | `1.49x` | `89.0%` [81.37, 93.75] | FAR `nan%` [nan, nan] | **PASS** |
| S13 | robustness | Two-Stage Placement | Moderate drift delta = 5% | `0.0080` | `0.0079` | `1.01x` | `94.0%` [87.52, 97.22] | FAR `nan%` [nan, nan] | **PASS** |
| S13 | robustness | Anomaly Cascade | Severe drift delta = 10% | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | FAR `29.0%` [21.01, 38.54] | <span style='color:red;'>**FAIL**</span> |
| S13 | robustness | Mode 2 | Severe drift delta = 10% | `0.0158` | `0.0116` | `1.37x` | `94.0%` [87.52, 97.22] | FAR `nan%` [nan, nan] | **PASS** |
| S13 | robustness | Mode 3 | Severe drift delta = 10% | `0.0157` | `0.0126` | `1.25x` | `95.0%` [88.82, 97.85] | FAR `nan%` [nan, nan] | **PASS** |
| S13 | robustness | Mode 3+ | Severe drift delta = 10% | `0.0158` | `0.0116` | `1.37x` | `94.0%` [87.52, 97.22] | FAR `nan%` [nan, nan] | **PASS** |
| S13 | robustness | Two-Stage Placement | Severe drift delta = 10% | `0.0079` | `0.0079` | `0.99x` | `95.0%` [88.82, 97.85] | FAR `nan%` [nan, nan] | **PASS** |
