# Week 5 Stress Matrix Report: Comprehensive Stress Testing of Frozen Digital Twin Modules
This document records the empirical stress testing of all five frozen digital twin modules under severe, non-standard operating conditions. In accordance with strict experimental discipline, **zero changes were made to any module** during this study. Failures are the explicit deliverable of this stress test, revealing the precise mathematical and operational boundaries of the frozen architectures.
## Pre-Registered Failure Criteria (Fixed Pre-Run)
A cell is classified as **FAIL** if:
1. **Parameter Estimation Modules** (`Mode 2`, `Mode 3`, `Mode 3+`, `Two-Stage Placement`):
   - Median relative $\alpha$ error $> 2.0\times$ the matching clean cell error, **OR**
   - Empirical 95% confidence interval coverage $< 80.0\%$.
2. **Anomaly Cascade Module** (`Anomaly Cascade`):
   - Healthy false-alarm rate (FAR on Class H) $> 15.0\%$.

Otherwise, the cell is classified as **PASS**.

## Executive Summary Statistics
- **Total Scenarios Evaluated:** 13 scenarios across 3 severity levels (39 unique stress regimes).
- **Total Module Cells Evaluated:** 195 module-scenario conditions (evaluated across 5 random seeds each = 975 runs total).
- **Overall Pass Count:** 86 / 195 (44.1% pass rate).
- **Overall Failure Count:** 109 / 195 (55.9% failure rate).

### Module Pass/Fail Breakdown
| Module | Total Conditions | Passed | Failed | Pass Rate (%) | Primary Failure Drivers |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Mode 2** | 39 | 19 | 20 | **48.7%** | Misspecified noise sigma, Correlated noise (AR(1)), Different initial condition, +7 more |
| **Mode 3** | 39 | 18 | 21 | **46.2%** | Misspecified noise sigma, Heavy-tailed noise (Student-t), Correlated noise (AR(1)), +8 more |
| **Mode 3+** | 39 | 19 | 20 | **48.7%** | Misspecified noise sigma, Correlated noise (AR(1)), Different initial condition, +7 more |
| **Two-Stage Placement** | 39 | 20 | 19 | **51.3%** | Misspecified noise sigma, Correlated noise (AR(1)), Different initial condition, +7 more |
| **Anomaly Cascade** | 39 | 10 | 29 | **25.6%** | Misspecified noise sigma, Heavy-tailed noise (Student-t), Correlated noise (AR(1)), +9 more |

---

## Complete Stress Matrix Results
The table below reports the complete results across all 39 conditions and 5 modules, generated strictly from [`data/results/stress_summary.csv`](file:///c:/Users/HP/Desktop/Digital%20twin/data/results/stress_summary.csv).

| Scen # | Scenario | Severity Level | Module | Metric (Median Error / FAR) | Clean Baseline | Error Ratio / FAR | Coverage (%) | Status |
| :---: | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
|  1 | Misspecified noise sigma | Mild under-specified: true=0.02, assumed=0.01 | Mode 2 | 0.0324 | 0.0164 | 1.98x | 60.0% | **FAIL** |
|  1 | Misspecified noise sigma | Mild under-specified: true=0.02, assumed=0.01 | Mode 3 | 0.0354 | 0.0139 | 2.54x | 40.0% | **FAIL** |
|  1 | Misspecified noise sigma | Mild under-specified: true=0.02, assumed=0.01 | Mode 3+ | 0.0324 | 0.0164 | 1.98x | 60.0% | **FAIL** |
|  1 | Misspecified noise sigma | Mild under-specified: true=0.02, assumed=0.01 | Two-Stage Placement | 0.0110 | 0.0062 | 1.78x | 100.0% | PASS |
|  1 | Misspecified noise sigma | Mild under-specified: true=0.02, assumed=0.01 | Anomaly Cascade | FAR 60.0% | FAR 10.0% | N/A | N/A | **FAIL** |
|  1 | Misspecified noise sigma | Severe under-specified: true=0.05, assumed=0.01 | Mode 2 | 0.0701 | 0.0164 | 4.29x | 40.0% | **FAIL** |
|  1 | Misspecified noise sigma | Severe under-specified: true=0.05, assumed=0.01 | Mode 3 | 0.0704 | 0.0139 | 5.05x | 40.0% | **FAIL** |
|  1 | Misspecified noise sigma | Severe under-specified: true=0.05, assumed=0.01 | Mode 3+ | 0.0701 | 0.0164 | 4.29x | 40.0% | **FAIL** |
|  1 | Misspecified noise sigma | Severe under-specified: true=0.05, assumed=0.01 | Two-Stage Placement | 0.0009 | 0.0062 | 0.14x | 80.0% | PASS |
|  1 | Misspecified noise sigma | Severe under-specified: true=0.05, assumed=0.01 | Anomaly Cascade | FAR 100.0% | FAR 10.0% | N/A | N/A | **FAIL** |
|  1 | Misspecified noise sigma | Severe over-specified: true=0.01, assumed=0.05 | Mode 2 | 0.0138 | 0.0164 | 0.84x | 100.0% | PASS |
|  1 | Misspecified noise sigma | Severe over-specified: true=0.01, assumed=0.05 | Mode 3 | 0.0135 | 0.0139 | 0.97x | 100.0% | PASS |
|  1 | Misspecified noise sigma | Severe over-specified: true=0.01, assumed=0.05 | Mode 3+ | 0.0138 | 0.0164 | 0.84x | 100.0% | PASS |
|  1 | Misspecified noise sigma | Severe over-specified: true=0.01, assumed=0.05 | Two-Stage Placement | 0.0362 | 0.0062 | 5.84x | 60.0% | **FAIL** |
|  1 | Misspecified noise sigma | Severe over-specified: true=0.01, assumed=0.05 | Anomaly Cascade | FAR 0.0% | FAR 10.0% | N/A | N/A | PASS |
|  2 | Heavy-tailed noise (Student-t) | Standardized Student-t (df=5) | Mode 2 | 0.0155 | 0.0164 | 0.95x | 100.0% | PASS |
|  2 | Heavy-tailed noise (Student-t) | Standardized Student-t (df=5) | Mode 3 | 0.0107 | 0.0139 | 0.76x | 100.0% | PASS |
|  2 | Heavy-tailed noise (Student-t) | Standardized Student-t (df=5) | Mode 3+ | 0.0155 | 0.0164 | 0.95x | 100.0% | PASS |
|  2 | Heavy-tailed noise (Student-t) | Standardized Student-t (df=5) | Two-Stage Placement | 0.0115 | 0.0062 | 1.85x | 100.0% | PASS |
|  2 | Heavy-tailed noise (Student-t) | Standardized Student-t (df=5) | Anomaly Cascade | FAR 20.0% | FAR 10.0% | N/A | N/A | **FAIL** |
|  2 | Heavy-tailed noise (Student-t) | Standardized Student-t (df=3) | Mode 2 | 0.0058 | 0.0164 | 0.35x | 100.0% | PASS |
|  2 | Heavy-tailed noise (Student-t) | Standardized Student-t (df=3) | Mode 3 | 0.0040 | 0.0139 | 0.29x | 100.0% | PASS |
|  2 | Heavy-tailed noise (Student-t) | Standardized Student-t (df=3) | Mode 3+ | 0.0058 | 0.0164 | 0.35x | 100.0% | PASS |
|  2 | Heavy-tailed noise (Student-t) | Standardized Student-t (df=3) | Two-Stage Placement | 0.0037 | 0.0062 | 0.60x | 100.0% | PASS |
|  2 | Heavy-tailed noise (Student-t) | Standardized Student-t (df=3) | Anomaly Cascade | FAR 20.0% | FAR 10.0% | N/A | N/A | **FAIL** |
|  2 | Heavy-tailed noise (Student-t) | Contaminated Student-t (df=3) with 10% 5-sigma outliers | Mode 2 | 0.0274 | 0.0164 | 1.67x | 80.0% | PASS |
|  2 | Heavy-tailed noise (Student-t) | Contaminated Student-t (df=3) with 10% 5-sigma outliers | Mode 3 | 0.0305 | 0.0139 | 2.19x | 80.0% | **FAIL** |
|  2 | Heavy-tailed noise (Student-t) | Contaminated Student-t (df=3) with 10% 5-sigma outliers | Mode 3+ | 0.0274 | 0.0164 | 1.67x | 80.0% | PASS |
|  2 | Heavy-tailed noise (Student-t) | Contaminated Student-t (df=3) with 10% 5-sigma outliers | Two-Stage Placement | 0.0114 | 0.0062 | 1.84x | 100.0% | PASS |
|  2 | Heavy-tailed noise (Student-t) | Contaminated Student-t (df=3) with 10% 5-sigma outliers | Anomaly Cascade | FAR 100.0% | FAR 10.0% | N/A | N/A | **FAIL** |
|  3 | Correlated noise (AR(1)) | Temporal AR(1) rho = 0.50 | Mode 2 | 0.0235 | 0.0164 | 1.44x | 80.0% | PASS |
|  3 | Correlated noise (AR(1)) | Temporal AR(1) rho = 0.50 | Mode 3 | 0.0241 | 0.0139 | 1.73x | 80.0% | PASS |
|  3 | Correlated noise (AR(1)) | Temporal AR(1) rho = 0.50 | Mode 3+ | 0.0235 | 0.0164 | 1.44x | 80.0% | PASS |
|  3 | Correlated noise (AR(1)) | Temporal AR(1) rho = 0.50 | Two-Stage Placement | 0.0103 | 0.0062 | 1.66x | 100.0% | PASS |
|  3 | Correlated noise (AR(1)) | Temporal AR(1) rho = 0.50 | Anomaly Cascade | FAR 20.0% | FAR 10.0% | N/A | N/A | **FAIL** |
|  3 | Correlated noise (AR(1)) | Temporal AR(1) rho = 0.80 | Mode 2 | 0.0290 | 0.0164 | 1.77x | 60.0% | **FAIL** |
|  3 | Correlated noise (AR(1)) | Temporal AR(1) rho = 0.80 | Mode 3 | 0.0294 | 0.0139 | 2.11x | 60.0% | **FAIL** |
|  3 | Correlated noise (AR(1)) | Temporal AR(1) rho = 0.80 | Mode 3+ | 0.0290 | 0.0164 | 1.77x | 60.0% | **FAIL** |
|  3 | Correlated noise (AR(1)) | Temporal AR(1) rho = 0.80 | Two-Stage Placement | 0.0049 | 0.0062 | 0.78x | 100.0% | PASS |
|  3 | Correlated noise (AR(1)) | Temporal AR(1) rho = 0.80 | Anomaly Cascade | FAR 0.0% | FAR 10.0% | N/A | N/A | PASS |
|  3 | Correlated noise (AR(1)) | Temporal AR(1) rho = 0.95 | Mode 2 | 0.0262 | 0.0164 | 1.60x | 100.0% | PASS |
|  3 | Correlated noise (AR(1)) | Temporal AR(1) rho = 0.95 | Mode 3 | 0.0309 | 0.0139 | 2.22x | 100.0% | **FAIL** |
|  3 | Correlated noise (AR(1)) | Temporal AR(1) rho = 0.95 | Mode 3+ | 0.0262 | 0.0164 | 1.60x | 100.0% | PASS |
|  3 | Correlated noise (AR(1)) | Temporal AR(1) rho = 0.95 | Two-Stage Placement | 0.0117 | 0.0062 | 1.88x | 60.0% | **FAIL** |
|  3 | Correlated noise (AR(1)) | Temporal AR(1) rho = 0.95 | Anomaly Cascade | FAR 0.0% | FAR 10.0% | N/A | N/A | PASS |
|  4 | Different initial condition | Second harmonic: sin(2 pi x) | Mode 2 | 76.6246 | 0.0164 | 4683.52x | 0.0% | **FAIL** |
|  4 | Different initial condition | Second harmonic: sin(2 pi x) | Mode 3 | 92.6595 | 0.0139 | 6651.05x | 0.0% | **FAIL** |
|  4 | Different initial condition | Second harmonic: sin(2 pi x) | Mode 3+ | 76.6246 | 0.0164 | 4683.55x | 0.0% | **FAIL** |
|  4 | Different initial condition | Second harmonic: sin(2 pi x) | Two-Stage Placement | 98.9987 | 0.0062 | 15955.08x | 0.0% | **FAIL** |
|  4 | Different initial condition | Second harmonic: sin(2 pi x) | Anomaly Cascade | FAR 100.0% | FAR 10.0% | N/A | N/A | **FAIL** |
|  4 | Different initial condition | Two-mode sum: sin(pi x) + 0.5 sin(3 pi x) | Mode 2 | 0.0801 | 0.0164 | 4.90x | 0.0% | **FAIL** |
|  4 | Different initial condition | Two-mode sum: sin(pi x) + 0.5 sin(3 pi x) | Mode 3 | 0.0815 | 0.0139 | 5.85x | 0.0% | **FAIL** |
|  4 | Different initial condition | Two-mode sum: sin(pi x) + 0.5 sin(3 pi x) | Mode 3+ | 0.0801 | 0.0164 | 4.90x | 0.0% | **FAIL** |
|  4 | Different initial condition | Two-mode sum: sin(pi x) + 0.5 sin(3 pi x) | Two-Stage Placement | 0.0675 | 0.0062 | 10.87x | 0.0% | **FAIL** |
|  4 | Different initial condition | Two-mode sum: sin(pi x) + 0.5 sin(3 pi x) | Anomaly Cascade | FAR 100.0% | FAR 10.0% | N/A | N/A | **FAIL** |
|  4 | Different initial condition | Gaussian bump IC | Mode 2 | 3.8736 | 0.0164 | 236.77x | 0.0% | **FAIL** |
|  4 | Different initial condition | Gaussian bump IC | Mode 3 | 3.7712 | 0.0139 | 270.70x | 0.0% | **FAIL** |
|  4 | Different initial condition | Gaussian bump IC | Mode 3+ | 3.8736 | 0.0164 | 236.77x | 0.0% | **FAIL** |
|  4 | Different initial condition | Gaussian bump IC | Two-Stage Placement | 1.4654 | 0.0062 | 236.17x | 0.0% | **FAIL** |
|  4 | Different initial condition | Gaussian bump IC | Anomaly Cascade | FAR 100.0% | FAR 10.0% | N/A | N/A | **FAIL** |
|  5 | Boundary mismatch | Constant offset BC = 0.05 | Mode 2 | 0.0585 | 0.0164 | 3.58x | 40.0% | **FAIL** |
|  5 | Boundary mismatch | Constant offset BC = 0.05 | Mode 3 | 0.0587 | 0.0139 | 4.21x | 40.0% | **FAIL** |
|  5 | Boundary mismatch | Constant offset BC = 0.05 | Mode 3+ | 0.0585 | 0.0164 | 3.58x | 40.0% | **FAIL** |
|  5 | Boundary mismatch | Constant offset BC = 0.05 | Two-Stage Placement | 0.0292 | 0.0062 | 4.71x | 20.0% | **FAIL** |
|  5 | Boundary mismatch | Constant offset BC = 0.05 | Anomaly Cascade | FAR 40.0% | FAR 10.0% | N/A | N/A | **FAIL** |
|  5 | Boundary mismatch | Moderate constant BC = 0.15 | Mode 2 | 0.1207 | 0.0164 | 7.38x | 0.0% | **FAIL** |
|  5 | Boundary mismatch | Moderate constant BC = 0.15 | Mode 3 | 0.1216 | 0.0139 | 8.73x | 0.0% | **FAIL** |
|  5 | Boundary mismatch | Moderate constant BC = 0.15 | Mode 3+ | 0.1207 | 0.0164 | 7.37x | 0.0% | **FAIL** |
|  5 | Boundary mismatch | Moderate constant BC = 0.15 | Two-Stage Placement | 0.0756 | 0.0062 | 12.18x | 0.0% | **FAIL** |
|  5 | Boundary mismatch | Moderate constant BC = 0.15 | Anomaly Cascade | FAR 100.0% | FAR 10.0% | N/A | N/A | **FAIL** |
|  5 | Boundary mismatch | Time-drifting oscillating BC | Mode 2 | 0.0096 | 0.0164 | 0.59x | 100.0% | PASS |
|  5 | Boundary mismatch | Time-drifting oscillating BC | Mode 3 | 0.0121 | 0.0139 | 0.87x | 100.0% | PASS |
|  5 | Boundary mismatch | Time-drifting oscillating BC | Mode 3+ | 0.0096 | 0.0164 | 0.59x | 100.0% | PASS |
|  5 | Boundary mismatch | Time-drifting oscillating BC | Two-Stage Placement | 0.0147 | 0.0062 | 2.38x | 60.0% | **FAIL** |
|  5 | Boundary mismatch | Time-drifting oscillating BC | Anomaly Cascade | FAR 0.0% | FAR 10.0% | N/A | N/A | PASS |
|  6 | Source-term / heating mismatch | Weak constant source s = 0.10 | Mode 2 | 0.1601 | 0.0164 | 9.79x | 0.0% | **FAIL** |
|  6 | Source-term / heating mismatch | Weak constant source s = 0.10 | Mode 3 | 0.1644 | 0.0139 | 11.80x | 0.0% | **FAIL** |
|  6 | Source-term / heating mismatch | Weak constant source s = 0.10 | Mode 3+ | 0.1601 | 0.0164 | 9.79x | 0.0% | **FAIL** |
|  6 | Source-term / heating mismatch | Weak constant source s = 0.10 | Two-Stage Placement | 0.1674 | 0.0062 | 26.98x | 0.0% | **FAIL** |
|  6 | Source-term / heating mismatch | Weak constant source s = 0.10 | Anomaly Cascade | FAR 100.0% | FAR 10.0% | N/A | N/A | **FAIL** |
|  6 | Source-term / heating mismatch | Moderate constant source s = 0.50 | Mode 2 | 0.7133 | 0.0164 | 43.60x | 0.0% | **FAIL** |
|  6 | Source-term / heating mismatch | Moderate constant source s = 0.50 | Mode 3 | 0.7164 | 0.0139 | 51.43x | 0.0% | **FAIL** |
|  6 | Source-term / heating mismatch | Moderate constant source s = 0.50 | Mode 3+ | 0.7134 | 0.0164 | 43.60x | 0.0% | **FAIL** |
|  6 | Source-term / heating mismatch | Moderate constant source s = 0.50 | Two-Stage Placement | 0.6998 | 0.0062 | 112.79x | 0.0% | **FAIL** |
|  6 | Source-term / heating mismatch | Moderate constant source s = 0.50 | Anomaly Cascade | FAR 100.0% | FAR 10.0% | N/A | N/A | **FAIL** |
|  6 | Source-term / heating mismatch | Strong localized heating s = 2.0 at core | Mode 2 | 0.9900 | 0.0164 | 60.51x | 0.0% | **FAIL** |
|  6 | Source-term / heating mismatch | Strong localized heating s = 2.0 at core | Mode 3 | 0.9900 | 0.0139 | 71.06x | 0.0% | **FAIL** |
|  6 | Source-term / heating mismatch | Strong localized heating s = 2.0 at core | Mode 3+ | 0.9900 | 0.0164 | 60.51x | 0.0% | **FAIL** |
|  6 | Source-term / heating mismatch | Strong localized heating s = 2.0 at core | Two-Stage Placement | 0.9900 | 0.0062 | 159.55x | 0.0% | **FAIL** |
|  6 | Source-term / heating mismatch | Strong localized heating s = 2.0 at core | Anomaly Cascade | FAR 100.0% | FAR 10.0% | N/A | N/A | **FAIL** |
|  7 | Variable diffusivity alpha(x) | Linear gradient +/- 20% | Mode 2 | 0.0247 | 0.0164 | 1.51x | 80.0% | PASS |
|  7 | Variable diffusivity alpha(x) | Linear gradient +/- 20% | Mode 3 | 0.0258 | 0.0139 | 1.85x | 80.0% | PASS |
|  7 | Variable diffusivity alpha(x) | Linear gradient +/- 20% | Mode 3+ | 0.0247 | 0.0164 | 1.51x | 80.0% | PASS |
|  7 | Variable diffusivity alpha(x) | Linear gradient +/- 20% | Two-Stage Placement | 0.0053 | 0.0062 | 0.86x | 100.0% | PASS |
|  7 | Variable diffusivity alpha(x) | Linear gradient +/- 20% | Anomaly Cascade | FAR 40.0% | FAR 10.0% | N/A | N/A | **FAIL** |
|  7 | Variable diffusivity alpha(x) | Linear gradient +/- 50% | Mode 2 | 0.0211 | 0.0164 | 1.29x | 60.0% | **FAIL** |
|  7 | Variable diffusivity alpha(x) | Linear gradient +/- 50% | Mode 3 | 0.0235 | 0.0139 | 1.68x | 60.0% | **FAIL** |
|  7 | Variable diffusivity alpha(x) | Linear gradient +/- 50% | Mode 3+ | 0.0211 | 0.0164 | 1.29x | 60.0% | **FAIL** |
|  7 | Variable diffusivity alpha(x) | Linear gradient +/- 50% | Two-Stage Placement | 0.0183 | 0.0062 | 2.96x | 100.0% | **FAIL** |
|  7 | Variable diffusivity alpha(x) | Linear gradient +/- 50% | Anomaly Cascade | FAR 100.0% | FAR 10.0% | N/A | N/A | **FAIL** |
|  7 | Variable diffusivity alpha(x) | Discontinuous step (alpha to 2.0 alpha) | Mode 2 | 0.4348 | 0.0164 | 26.57x | 0.0% | **FAIL** |
|  7 | Variable diffusivity alpha(x) | Discontinuous step (alpha to 2.0 alpha) | Mode 3 | 0.4390 | 0.0139 | 31.51x | 0.0% | **FAIL** |
|  7 | Variable diffusivity alpha(x) | Discontinuous step (alpha to 2.0 alpha) | Mode 3+ | 0.4348 | 0.0164 | 26.57x | 0.0% | **FAIL** |
|  7 | Variable diffusivity alpha(x) | Discontinuous step (alpha to 2.0 alpha) | Two-Stage Placement | 0.5010 | 0.0062 | 80.75x | 0.0% | **FAIL** |
|  7 | Variable diffusivity alpha(x) | Discontinuous step (alpha to 2.0 alpha) | Anomaly Cascade | FAR 100.0% | FAR 10.0% | N/A | N/A | **FAIL** |
|  8 | Sensor dropout | 10% readings missing (1 sensor dropped) | Mode 2 | 0.0153 | 0.0164 | 0.94x | 100.0% | PASS |
|  8 | Sensor dropout | 10% readings missing (1 sensor dropped) | Mode 3 | 0.0135 | 0.0139 | 0.97x | 100.0% | PASS |
|  8 | Sensor dropout | 10% readings missing (1 sensor dropped) | Mode 3+ | 0.0153 | 0.0164 | 0.94x | 100.0% | PASS |
|  8 | Sensor dropout | 10% readings missing (1 sensor dropped) | Two-Stage Placement | 0.0082 | 0.0062 | 1.32x | 100.0% | PASS |
|  8 | Sensor dropout | 10% readings missing (1 sensor dropped) | Anomaly Cascade | FAR 0.0% | FAR 10.0% | N/A | N/A | PASS |
|  8 | Sensor dropout | 30% readings missing (3 sensors dropped) | Mode 2 | 0.0243 | 0.0164 | 1.48x | 100.0% | PASS |
|  8 | Sensor dropout | 30% readings missing (3 sensors dropped) | Mode 3 | 0.0246 | 0.0139 | 1.76x | 100.0% | PASS |
|  8 | Sensor dropout | 30% readings missing (3 sensors dropped) | Mode 3+ | 0.0243 | 0.0164 | 1.48x | 100.0% | PASS |
|  8 | Sensor dropout | 30% readings missing (3 sensors dropped) | Two-Stage Placement | 0.0124 | 0.0062 | 2.00x | 100.0% | **FAIL** |
|  8 | Sensor dropout | 30% readings missing (3 sensors dropped) | Anomaly Cascade | FAR 0.0% | FAR 10.0% | N/A | N/A | PASS |
|  8 | Sensor dropout | 50% readings missing (5 sensors dropped) | Mode 2 | 0.0400 | 0.0164 | 2.44x | 80.0% | **FAIL** |
|  8 | Sensor dropout | 50% readings missing (5 sensors dropped) | Mode 3 | 0.0322 | 0.0139 | 2.31x | 100.0% | **FAIL** |
|  8 | Sensor dropout | 50% readings missing (5 sensors dropped) | Mode 3+ | 0.0400 | 0.0164 | 2.44x | 80.0% | **FAIL** |
|  8 | Sensor dropout | 50% readings missing (5 sensors dropped) | Two-Stage Placement | 0.0077 | 0.0062 | 1.24x | 100.0% | PASS |
|  8 | Sensor dropout | 50% readings missing (5 sensors dropped) | Anomaly Cascade | FAR 0.0% | FAR 10.0% | N/A | N/A | PASS |
|  9 | Sensor position error and time jitter | Small jitter sigma_jitter = 0.01 | Mode 2 | 0.0177 | 0.0164 | 1.08x | 100.0% | PASS |
|  9 | Sensor position error and time jitter | Small jitter sigma_jitter = 0.01 | Mode 3 | 0.0173 | 0.0139 | 1.24x | 100.0% | PASS |
|  9 | Sensor position error and time jitter | Small jitter sigma_jitter = 0.01 | Mode 3+ | 0.0177 | 0.0164 | 1.08x | 100.0% | PASS |
|  9 | Sensor position error and time jitter | Small jitter sigma_jitter = 0.01 | Two-Stage Placement | 0.0058 | 0.0062 | 0.93x | 100.0% | PASS |
|  9 | Sensor position error and time jitter | Small jitter sigma_jitter = 0.01 | Anomaly Cascade | FAR 40.0% | FAR 10.0% | N/A | N/A | **FAIL** |
|  9 | Sensor position error and time jitter | Moderate jitter sigma_jitter = 0.03 | Mode 2 | 0.0279 | 0.0164 | 1.70x | 80.0% | PASS |
|  9 | Sensor position error and time jitter | Moderate jitter sigma_jitter = 0.03 | Mode 3 | 0.0270 | 0.0139 | 1.94x | 80.0% | PASS |
|  9 | Sensor position error and time jitter | Moderate jitter sigma_jitter = 0.03 | Mode 3+ | 0.0279 | 0.0164 | 1.70x | 80.0% | PASS |
|  9 | Sensor position error and time jitter | Moderate jitter sigma_jitter = 0.03 | Two-Stage Placement | 0.0053 | 0.0062 | 0.86x | 100.0% | PASS |
|  9 | Sensor position error and time jitter | Moderate jitter sigma_jitter = 0.03 | Anomaly Cascade | FAR 100.0% | FAR 10.0% | N/A | N/A | **FAIL** |
|  9 | Sensor position error and time jitter | Large jitter sigma_jitter = 0.06 | Mode 2 | 0.1227 | 0.0164 | 7.50x | 0.0% | **FAIL** |
|  9 | Sensor position error and time jitter | Large jitter sigma_jitter = 0.06 | Mode 3 | 0.1217 | 0.0139 | 8.74x | 0.0% | **FAIL** |
|  9 | Sensor position error and time jitter | Large jitter sigma_jitter = 0.06 | Mode 3+ | 0.1227 | 0.0164 | 7.50x | 0.0% | **FAIL** |
|  9 | Sensor position error and time jitter | Large jitter sigma_jitter = 0.06 | Two-Stage Placement | 0.0090 | 0.0062 | 1.45x | 100.0% | PASS |
|  9 | Sensor position error and time jitter | Large jitter sigma_jitter = 0.06 | Anomaly Cascade | FAR 100.0% | FAR 10.0% | N/A | N/A | **FAIL** |
| 10 | Constant sensor bias | Small sensor bias b = 3 sigma (0.03) | Mode 2 | 0.0100 | 0.0164 | 0.61x | 100.0% | PASS |
| 10 | Constant sensor bias | Small sensor bias b = 3 sigma (0.03) | Mode 3 | 0.0125 | 0.0139 | 0.89x | 100.0% | PASS |
| 10 | Constant sensor bias | Small sensor bias b = 3 sigma (0.03) | Mode 3+ | 0.0100 | 0.0164 | 0.61x | 100.0% | PASS |
| 10 | Constant sensor bias | Small sensor bias b = 3 sigma (0.03) | Two-Stage Placement | 0.0132 | 0.0062 | 2.12x | 100.0% | **FAIL** |
| 10 | Constant sensor bias | Small sensor bias b = 3 sigma (0.03) | Anomaly Cascade | FAR 20.0% | FAR 10.0% | N/A | N/A | **FAIL** |
| 10 | Constant sensor bias | Medium sensor bias b = 6 sigma (0.06) | Mode 2 | 0.0102 | 0.0164 | 0.62x | 100.0% | PASS |
| 10 | Constant sensor bias | Medium sensor bias b = 6 sigma (0.06) | Mode 3 | 0.0062 | 0.0139 | 0.45x | 100.0% | PASS |
| 10 | Constant sensor bias | Medium sensor bias b = 6 sigma (0.06) | Mode 3+ | 0.0102 | 0.0164 | 0.62x | 100.0% | PASS |
| 10 | Constant sensor bias | Medium sensor bias b = 6 sigma (0.06) | Two-Stage Placement | 0.0085 | 0.0062 | 1.37x | 80.0% | PASS |
| 10 | Constant sensor bias | Medium sensor bias b = 6 sigma (0.06) | Anomaly Cascade | FAR 100.0% | FAR 10.0% | N/A | N/A | **FAIL** |
| 10 | Constant sensor bias | Strong sensor bias b = 15 sigma (0.15) | Mode 2 | 0.0155 | 0.0164 | 0.95x | 100.0% | PASS |
| 10 | Constant sensor bias | Strong sensor bias b = 15 sigma (0.15) | Mode 3 | 0.0209 | 0.0139 | 1.50x | 80.0% | PASS |
| 10 | Constant sensor bias | Strong sensor bias b = 15 sigma (0.15) | Mode 3+ | 0.0155 | 0.0164 | 0.94x | 100.0% | PASS |
| 10 | Constant sensor bias | Strong sensor bias b = 15 sigma (0.15) | Two-Stage Placement | 0.0048 | 0.0062 | 0.77x | 100.0% | PASS |
| 10 | Constant sensor bias | Strong sensor bias b = 15 sigma (0.15) | Anomaly Cascade | FAR 100.0% | FAR 10.0% | N/A | N/A | **FAIL** |
| 11 | Very few sensors | Sparse array N = 5 sensors | Mode 2 | 0.0334 | 0.0164 | 2.04x | 80.0% | **FAIL** |
| 11 | Very few sensors | Sparse array N = 5 sensors | Mode 3 | 0.0242 | 0.0139 | 1.74x | 80.0% | PASS |
| 11 | Very few sensors | Sparse array N = 5 sensors | Mode 3+ | 0.0334 | 0.0164 | 2.04x | 80.0% | **FAIL** |
| 11 | Very few sensors | Sparse array N = 5 sensors | Two-Stage Placement | 0.0168 | 0.0062 | 2.72x | 100.0% | **FAIL** |
| 11 | Very few sensors | Sparse array N = 5 sensors | Anomaly Cascade | FAR 0.0% | FAR 10.0% | N/A | N/A | PASS |
| 11 | Very few sensors | Very sparse array N = 3 sensors | Mode 2 | 0.0420 | 0.0164 | 2.57x | 80.0% | **FAIL** |
| 11 | Very few sensors | Very sparse array N = 3 sensors | Mode 3 | 0.0259 | 0.0139 | 1.86x | 100.0% | PASS |
| 11 | Very few sensors | Very sparse array N = 3 sensors | Mode 3+ | 0.0420 | 0.0164 | 2.56x | 80.0% | **FAIL** |
| 11 | Very few sensors | Very sparse array N = 3 sensors | Two-Stage Placement | 0.0110 | 0.0062 | 1.78x | 80.0% | PASS |
| 11 | Very few sensors | Very sparse array N = 3 sensors | Anomaly Cascade | FAR 20.0% | FAR 10.0% | N/A | N/A | **FAIL** |
| 11 | Very few sensors | Minimal array N = 2 sensors | Mode 2 | 0.0224 | 0.0164 | 1.37x | 100.0% | PASS |
| 11 | Very few sensors | Minimal array N = 2 sensors | Mode 3 | 0.0381 | 0.0139 | 2.73x | 100.0% | **FAIL** |
| 11 | Very few sensors | Minimal array N = 2 sensors | Mode 3+ | 0.0224 | 0.0164 | 1.37x | 100.0% | PASS |
| 11 | Very few sensors | Minimal array N = 2 sensors | Two-Stage Placement | 0.0311 | 0.0062 | 5.02x | 100.0% | **FAIL** |
| 11 | Very few sensors | Minimal array N = 2 sensors | Anomaly Cascade | FAR 0.0% | FAR 10.0% | N/A | N/A | PASS |
| 12 | True alpha beyond the grid | Sub-grid low diffusivity alpha = 5e-4 | Mode 2 | 1.0000 | 0.0164 | 61.12x | 100.0% | **FAIL** |
| 12 | True alpha beyond the grid | Sub-grid low diffusivity alpha = 5e-4 | Mode 3 | 1.8919 | 0.0139 | 135.80x | 100.0% | **FAIL** |
| 12 | True alpha beyond the grid | Sub-grid low diffusivity alpha = 5e-4 | Mode 3+ | 1.0002 | 0.0164 | 61.14x | 100.0% | **FAIL** |
| 12 | True alpha beyond the grid | Sub-grid low diffusivity alpha = 5e-4 | Two-Stage Placement | 1.0000 | 0.0062 | 161.17x | 100.0% | **FAIL** |
| 12 | True alpha beyond the grid | Sub-grid low diffusivity alpha = 5e-4 | Anomaly Cascade | FAR 100.0% | FAR 10.0% | N/A | N/A | **FAIL** |
| 12 | True alpha beyond the grid | Super-grid high diffusivity alpha = 5.0 | Mode 2 | 0.1303 | 0.0164 | 7.96x | 0.0% | **FAIL** |
| 12 | True alpha beyond the grid | Super-grid high diffusivity alpha = 5.0 | Mode 3 | 0.0995 | 0.0139 | 7.14x | 20.0% | **FAIL** |
| 12 | True alpha beyond the grid | Super-grid high diffusivity alpha = 5.0 | Mode 3+ | 0.1303 | 0.0164 | 7.96x | 0.0% | **FAIL** |
| 12 | True alpha beyond the grid | Super-grid high diffusivity alpha = 5.0 | Two-Stage Placement | 0.0054 | 0.0062 | 0.87x | 100.0% | PASS |
| 12 | True alpha beyond the grid | Super-grid high diffusivity alpha = 5.0 | Anomaly Cascade | FAR 100.0% | FAR 10.0% | N/A | N/A | **FAIL** |
| 12 | True alpha beyond the grid | Super-grid extreme diffusivity alpha = 20.0 | Mode 2 | 0.5000 | 0.0164 | 30.56x | 0.0% | **FAIL** |
| 12 | True alpha beyond the grid | Super-grid extreme diffusivity alpha = 20.0 | Mode 3 | 0.5000 | 0.0139 | 35.89x | 0.0% | **FAIL** |
| 12 | True alpha beyond the grid | Super-grid extreme diffusivity alpha = 20.0 | Mode 3+ | 0.5001 | 0.0164 | 30.57x | 0.0% | **FAIL** |
| 12 | True alpha beyond the grid | Super-grid extreme diffusivity alpha = 20.0 | Two-Stage Placement | 0.5000 | 0.0062 | 80.58x | 0.0% | **FAIL** |
| 12 | True alpha beyond the grid | Super-grid extreme diffusivity alpha = 20.0 | Anomaly Cascade | FAR 100.0% | FAR 10.0% | N/A | N/A | **FAIL** |
| 13 | Baseline drift | Slow drift delta = 2% | Mode 2 | 0.0116 | 0.0164 | 0.71x | 100.0% | PASS |
| 13 | Baseline drift | Slow drift delta = 2% | Mode 3 | 0.0101 | 0.0139 | 0.72x | 100.0% | PASS |
| 13 | Baseline drift | Slow drift delta = 2% | Mode 3+ | 0.0116 | 0.0164 | 0.71x | 100.0% | PASS |
| 13 | Baseline drift | Slow drift delta = 2% | Two-Stage Placement | 0.0117 | 0.0062 | 1.89x | 100.0% | PASS |
| 13 | Baseline drift | Slow drift delta = 2% | Anomaly Cascade | FAR 0.0% | FAR 10.0% | N/A | N/A | PASS |
| 13 | Baseline drift | Moderate drift delta = 5% | Mode 2 | 0.0024 | 0.0164 | 0.15x | 100.0% | PASS |
| 13 | Baseline drift | Moderate drift delta = 5% | Mode 3 | 0.0015 | 0.0139 | 0.11x | 100.0% | PASS |
| 13 | Baseline drift | Moderate drift delta = 5% | Mode 3+ | 0.0024 | 0.0164 | 0.15x | 100.0% | PASS |
| 13 | Baseline drift | Moderate drift delta = 5% | Two-Stage Placement | 0.0090 | 0.0062 | 1.45x | 100.0% | PASS |
| 13 | Baseline drift | Moderate drift delta = 5% | Anomaly Cascade | FAR 20.0% | FAR 10.0% | N/A | N/A | **FAIL** |
| 13 | Baseline drift | Severe drift delta = 10% | Mode 2 | 0.0118 | 0.0164 | 0.72x | 100.0% | PASS |
| 13 | Baseline drift | Severe drift delta = 10% | Mode 3 | 0.0153 | 0.0139 | 1.10x | 100.0% | PASS |
| 13 | Baseline drift | Severe drift delta = 10% | Mode 3+ | 0.0118 | 0.0164 | 0.72x | 100.0% | PASS |
| 13 | Baseline drift | Severe drift delta = 10% | Two-Stage Placement | 0.0124 | 0.0062 | 2.00x | 80.0% | PASS |
| 13 | Baseline drift | Severe drift delta = 10% | Anomaly Cascade | FAR 60.0% | FAR 10.0% | N/A | N/A | **FAIL** |

---

## Root Cause Analysis & V2 Candidate Fixes for Failed Cells
Each failure below documents the observed empirical degradation, the likely physical/mathematical mechanism, and a candidate V2 architectural mitigation. *All causes and fixes are explicitly marked as hypotheses (unverified in V1).*

### Scenario 1: Misspecified noise sigma
- **Module:** `Mode 2` | **Severity:** Mild under-specified: true=0.02, assumed=0.01
  - *Failure Reason:* Coverage 60.0% < 80%
  - *Likely Cause (Hypothesis):* Mild noise under-specification reduces CI width below true empirical dispersion.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Robust sandwich Huber-White covariance estimator.

- **Module:** `Mode 3` | **Severity:** Mild under-specified: true=0.02, assumed=0.01
  - *Failure Reason:* Error 2.5x > 2x clean; Coverage 40.0% < 80%
  - *Likely Cause (Hypothesis):* Mild noise under-specification reduces CI width below true empirical dispersion.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Robust sandwich Huber-White covariance estimator.

- **Module:** `Mode 3+` | **Severity:** Mild under-specified: true=0.02, assumed=0.01
  - *Failure Reason:* Coverage 60.0% < 80%
  - *Likely Cause (Hypothesis):* Mild noise under-specification reduces CI width below true empirical dispersion.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Robust sandwich Huber-White covariance estimator.

- **Module:** `Anomaly Cascade` | **Severity:** Mild under-specified: true=0.02, assumed=0.01
  - *Failure Reason:* Healthy FAR 60.0% > 15%
  - *Likely Cause (Hypothesis):* Assumed noise mismatch causes GLR test statistic normalization (RSS / sigma^2) to trip gating threshold.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Pre-gate noise floor estimation using robust MAD (median absolute deviation) of baseline differences.

- **Module:** `Mode 2` | **Severity:** Severe under-specified: true=0.05, assumed=0.01
  - *Failure Reason:* Error 4.3x > 2x clean; Coverage 40.0% < 80%
  - *Likely Cause (Hypothesis):* Under-specified noise underestimates residual variance, causing catastrophic Wald CI collapse.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Residual-adaptive noise variance estimation via restricted maximum likelihood (REML).

- **Module:** `Mode 3` | **Severity:** Severe under-specified: true=0.05, assumed=0.01
  - *Failure Reason:* Error 5.1x > 2x clean; Coverage 40.0% < 80%
  - *Likely Cause (Hypothesis):* Under-specified noise underestimates residual variance, causing catastrophic Wald CI collapse.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Residual-adaptive noise variance estimation via restricted maximum likelihood (REML).

- **Module:** `Mode 3+` | **Severity:** Severe under-specified: true=0.05, assumed=0.01
  - *Failure Reason:* Error 4.3x > 2x clean; Coverage 40.0% < 80%
  - *Likely Cause (Hypothesis):* Under-specified noise underestimates residual variance, causing catastrophic Wald CI collapse.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Residual-adaptive noise variance estimation via restricted maximum likelihood (REML).

- **Module:** `Anomaly Cascade` | **Severity:** Severe under-specified: true=0.05, assumed=0.01
  - *Failure Reason:* Healthy FAR 100.0% > 15%
  - *Likely Cause (Hypothesis):* Assumed noise mismatch causes GLR test statistic normalization (RSS / sigma^2) to trip gating threshold.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Pre-gate noise floor estimation using robust MAD (median absolute deviation) of baseline differences.

- **Module:** `Two-Stage Placement` | **Severity:** Severe over-specified: true=0.01, assumed=0.05
  - *Failure Reason:* Error 5.8x > 2x clean; Coverage 60.0% < 80%
  - *Likely Cause (Hypothesis):* Unmodeled environmental disturbance violates forward PDE assumptions.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Adaptive surrogate residual inflation.

### Scenario 2: Heavy-tailed noise (Student-t)
- **Module:** `Anomaly Cascade` | **Severity:** Standardized Student-t (df=5)
  - *Failure Reason:* Healthy FAR 20.0% > 15%
  - *Likely Cause (Hypothesis):* Heavy-tailed noise outliers falsely trigger LOO sensor exclusion (BIC_F < BIC_0) or change-point GLR.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Trimmed likelihood or student-t BIC penalty term.

- **Module:** `Anomaly Cascade` | **Severity:** Standardized Student-t (df=3)
  - *Failure Reason:* Healthy FAR 20.0% > 15%
  - *Likely Cause (Hypothesis):* Heavy-tailed noise outliers falsely trigger LOO sensor exclusion (BIC_F < BIC_0) or change-point GLR.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Trimmed likelihood or student-t BIC penalty term.

- **Module:** `Mode 3` | **Severity:** Contaminated Student-t (df=3) with 10% 5-sigma outliers
  - *Failure Reason:* Error 2.2x > 2x clean
  - *Likely Cause (Hypothesis):* Heavy-tailed noise violates L2 Gaussian likelihood, heavily skewing least-squares optimum.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Huber loss or Student-t robust M-estimator likelihood objective.

- **Module:** `Anomaly Cascade` | **Severity:** Contaminated Student-t (df=3) with 10% 5-sigma outliers
  - *Failure Reason:* Healthy FAR 100.0% > 15%
  - *Likely Cause (Hypothesis):* Heavy-tailed noise outliers falsely trigger LOO sensor exclusion (BIC_F < BIC_0) or change-point GLR.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Trimmed likelihood or student-t BIC penalty term.

### Scenario 3: Correlated noise (AR(1))
- **Module:** `Anomaly Cascade` | **Severity:** Temporal AR(1) rho = 0.50
  - *Failure Reason:* Healthy FAR 20.0% > 15%
  - *Likely Cause (Hypothesis):* Correlated noise creates systematic multi-step residual deviations mimicking physical change-points.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Whittle likelihood or AR(1) pre-whitening filter in GLR hypothesis score.

- **Module:** `Mode 2` | **Severity:** Temporal AR(1) rho = 0.80
  - *Failure Reason:* Coverage 60.0% < 80%
  - *Likely Cause (Hypothesis):* AR(1) temporal correlation creates systematic pseudo-trend residuals, shrinking effective sample size.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Generalized least squares (GLS) whitening filter (I - rho L) on temporal sensor stream.

- **Module:** `Mode 3` | **Severity:** Temporal AR(1) rho = 0.80
  - *Failure Reason:* Error 2.1x > 2x clean; Coverage 60.0% < 80%
  - *Likely Cause (Hypothesis):* AR(1) temporal correlation creates systematic pseudo-trend residuals, shrinking effective sample size.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Generalized least squares (GLS) whitening filter (I - rho L) on temporal sensor stream.

- **Module:** `Mode 3+` | **Severity:** Temporal AR(1) rho = 0.80
  - *Failure Reason:* Coverage 60.0% < 80%
  - *Likely Cause (Hypothesis):* AR(1) temporal correlation creates systematic pseudo-trend residuals, shrinking effective sample size.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Generalized least squares (GLS) whitening filter (I - rho L) on temporal sensor stream.

- **Module:** `Mode 3` | **Severity:** Temporal AR(1) rho = 0.95
  - *Failure Reason:* Error 2.2x > 2x clean
  - *Likely Cause (Hypothesis):* AR(1) temporal correlation creates systematic pseudo-trend residuals, shrinking effective sample size.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Generalized least squares (GLS) whitening filter (I - rho L) on temporal sensor stream.

- **Module:** `Two-Stage Placement` | **Severity:** Temporal AR(1) rho = 0.95
  - *Failure Reason:* Coverage 60.0% < 80%
  - *Likely Cause (Hypothesis):* AR(1) temporal correlation creates systematic pseudo-trend residuals, shrinking effective sample size.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Generalized least squares (GLS) whitening filter (I - rho L) on temporal sensor stream.

### Scenario 4: Different initial condition
- **Module:** `Mode 2` | **Severity:** Second harmonic: sin(2 pi x)
  - *Failure Reason:* Error 4683.5x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Forward model assumes fundamental mode sin(pi*x); higher spatial harmonics decay at exp(-k^2 pi^2 alpha t), severely biasing single-parameter alpha fit.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Fourier spatial mode decomposition to isolate k=1 harmonic prior to parameter estimation.

- **Module:** `Mode 3` | **Severity:** Second harmonic: sin(2 pi x)
  - *Failure Reason:* Error 6651.0x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Forward model assumes fundamental mode sin(pi*x); higher spatial harmonics decay at exp(-k^2 pi^2 alpha t), severely biasing single-parameter alpha fit.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Fourier spatial mode decomposition to isolate k=1 harmonic prior to parameter estimation.

- **Module:** `Mode 3+` | **Severity:** Second harmonic: sin(2 pi x)
  - *Failure Reason:* Error 4683.5x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Forward model assumes fundamental mode sin(pi*x); higher spatial harmonics decay at exp(-k^2 pi^2 alpha t), severely biasing single-parameter alpha fit.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Fourier spatial mode decomposition to isolate k=1 harmonic prior to parameter estimation.

- **Module:** `Two-Stage Placement` | **Severity:** Second harmonic: sin(2 pi x)
  - *Failure Reason:* Error 15955.1x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Forward model assumes fundamental mode sin(pi*x); higher spatial harmonics decay at exp(-k^2 pi^2 alpha t), severely biasing single-parameter alpha fit.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Fourier spatial mode decomposition to isolate k=1 harmonic prior to parameter estimation.

- **Module:** `Anomaly Cascade` | **Severity:** Second harmonic: sin(2 pi x)
  - *Failure Reason:* Healthy FAR 100.0% > 15%
  - *Likely Cause (Hypothesis):* Physical model mismatch (IC, BC, heating, variable alpha) produces large structured residuals that trip the physical jump gate C or sensor fault gate F.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Model discrepancy Gaussian process (Kennedy-O'Hagan framework) isolating structural bias from discrete jumps.

- **Module:** `Mode 2` | **Severity:** Two-mode sum: sin(pi x) + 0.5 sin(3 pi x)
  - *Failure Reason:* Error 4.9x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Forward model assumes fundamental mode sin(pi*x); higher spatial harmonics decay at exp(-k^2 pi^2 alpha t), severely biasing single-parameter alpha fit.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Fourier spatial mode decomposition to isolate k=1 harmonic prior to parameter estimation.

- **Module:** `Mode 3` | **Severity:** Two-mode sum: sin(pi x) + 0.5 sin(3 pi x)
  - *Failure Reason:* Error 5.9x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Forward model assumes fundamental mode sin(pi*x); higher spatial harmonics decay at exp(-k^2 pi^2 alpha t), severely biasing single-parameter alpha fit.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Fourier spatial mode decomposition to isolate k=1 harmonic prior to parameter estimation.

- **Module:** `Mode 3+` | **Severity:** Two-mode sum: sin(pi x) + 0.5 sin(3 pi x)
  - *Failure Reason:* Error 4.9x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Forward model assumes fundamental mode sin(pi*x); higher spatial harmonics decay at exp(-k^2 pi^2 alpha t), severely biasing single-parameter alpha fit.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Fourier spatial mode decomposition to isolate k=1 harmonic prior to parameter estimation.

- **Module:** `Two-Stage Placement` | **Severity:** Two-mode sum: sin(pi x) + 0.5 sin(3 pi x)
  - *Failure Reason:* Error 10.9x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Forward model assumes fundamental mode sin(pi*x); higher spatial harmonics decay at exp(-k^2 pi^2 alpha t), severely biasing single-parameter alpha fit.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Fourier spatial mode decomposition to isolate k=1 harmonic prior to parameter estimation.

- **Module:** `Anomaly Cascade` | **Severity:** Two-mode sum: sin(pi x) + 0.5 sin(3 pi x)
  - *Failure Reason:* Healthy FAR 100.0% > 15%
  - *Likely Cause (Hypothesis):* Physical model mismatch (IC, BC, heating, variable alpha) produces large structured residuals that trip the physical jump gate C or sensor fault gate F.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Model discrepancy Gaussian process (Kennedy-O'Hagan framework) isolating structural bias from discrete jumps.

- **Module:** `Mode 2` | **Severity:** Gaussian bump IC
  - *Failure Reason:* Error 236.8x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Forward model assumes fundamental mode sin(pi*x); higher spatial harmonics decay at exp(-k^2 pi^2 alpha t), severely biasing single-parameter alpha fit.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Fourier spatial mode decomposition to isolate k=1 harmonic prior to parameter estimation.

- **Module:** `Mode 3` | **Severity:** Gaussian bump IC
  - *Failure Reason:* Error 270.7x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Forward model assumes fundamental mode sin(pi*x); higher spatial harmonics decay at exp(-k^2 pi^2 alpha t), severely biasing single-parameter alpha fit.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Fourier spatial mode decomposition to isolate k=1 harmonic prior to parameter estimation.

- **Module:** `Mode 3+` | **Severity:** Gaussian bump IC
  - *Failure Reason:* Error 236.8x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Forward model assumes fundamental mode sin(pi*x); higher spatial harmonics decay at exp(-k^2 pi^2 alpha t), severely biasing single-parameter alpha fit.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Fourier spatial mode decomposition to isolate k=1 harmonic prior to parameter estimation.

- **Module:** `Two-Stage Placement` | **Severity:** Gaussian bump IC
  - *Failure Reason:* Error 236.2x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Forward model assumes fundamental mode sin(pi*x); higher spatial harmonics decay at exp(-k^2 pi^2 alpha t), severely biasing single-parameter alpha fit.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Fourier spatial mode decomposition to isolate k=1 harmonic prior to parameter estimation.

- **Module:** `Anomaly Cascade` | **Severity:** Gaussian bump IC
  - *Failure Reason:* Healthy FAR 100.0% > 15%
  - *Likely Cause (Hypothesis):* Physical model mismatch (IC, BC, heating, variable alpha) produces large structured residuals that trip the physical jump gate C or sensor fault gate F.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Model discrepancy Gaussian process (Kennedy-O'Hagan framework) isolating structural bias from discrete jumps.

### Scenario 5: Boundary mismatch
- **Module:** `Mode 2` | **Severity:** Constant offset BC = 0.05
  - *Failure Reason:* Error 3.6x > 2x clean; Coverage 40.0% < 80%
  - *Likely Cause (Hypothesis):* Dirichlet boundary mismatch creates non-zero asymptotic temperature floor, destroying exponential decay assumption.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Joint estimation of boundary offsets u_0, u_1 alongside diffusivity alpha.

- **Module:** `Mode 3` | **Severity:** Constant offset BC = 0.05
  - *Failure Reason:* Error 4.2x > 2x clean; Coverage 40.0% < 80%
  - *Likely Cause (Hypothesis):* Dirichlet boundary mismatch creates non-zero asymptotic temperature floor, destroying exponential decay assumption.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Joint estimation of boundary offsets u_0, u_1 alongside diffusivity alpha.

- **Module:** `Mode 3+` | **Severity:** Constant offset BC = 0.05
  - *Failure Reason:* Error 3.6x > 2x clean; Coverage 40.0% < 80%
  - *Likely Cause (Hypothesis):* Dirichlet boundary mismatch creates non-zero asymptotic temperature floor, destroying exponential decay assumption.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Joint estimation of boundary offsets u_0, u_1 alongside diffusivity alpha.

- **Module:** `Two-Stage Placement` | **Severity:** Constant offset BC = 0.05
  - *Failure Reason:* Error 4.7x > 2x clean; Coverage 20.0% < 80%
  - *Likely Cause (Hypothesis):* Dirichlet boundary mismatch creates non-zero asymptotic temperature floor, destroying exponential decay assumption.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Joint estimation of boundary offsets u_0, u_1 alongside diffusivity alpha.

- **Module:** `Anomaly Cascade` | **Severity:** Constant offset BC = 0.05
  - *Failure Reason:* Healthy FAR 40.0% > 15%
  - *Likely Cause (Hypothesis):* Physical model mismatch (IC, BC, heating, variable alpha) produces large structured residuals that trip the physical jump gate C or sensor fault gate F.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Model discrepancy Gaussian process (Kennedy-O'Hagan framework) isolating structural bias from discrete jumps.

- **Module:** `Mode 2` | **Severity:** Moderate constant BC = 0.15
  - *Failure Reason:* Error 7.4x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Dirichlet boundary mismatch creates non-zero asymptotic temperature floor, destroying exponential decay assumption.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Joint estimation of boundary offsets u_0, u_1 alongside diffusivity alpha.

- **Module:** `Mode 3` | **Severity:** Moderate constant BC = 0.15
  - *Failure Reason:* Error 8.7x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Dirichlet boundary mismatch creates non-zero asymptotic temperature floor, destroying exponential decay assumption.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Joint estimation of boundary offsets u_0, u_1 alongside diffusivity alpha.

- **Module:** `Mode 3+` | **Severity:** Moderate constant BC = 0.15
  - *Failure Reason:* Error 7.4x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Dirichlet boundary mismatch creates non-zero asymptotic temperature floor, destroying exponential decay assumption.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Joint estimation of boundary offsets u_0, u_1 alongside diffusivity alpha.

- **Module:** `Two-Stage Placement` | **Severity:** Moderate constant BC = 0.15
  - *Failure Reason:* Error 12.2x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Dirichlet boundary mismatch creates non-zero asymptotic temperature floor, destroying exponential decay assumption.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Joint estimation of boundary offsets u_0, u_1 alongside diffusivity alpha.

- **Module:** `Anomaly Cascade` | **Severity:** Moderate constant BC = 0.15
  - *Failure Reason:* Healthy FAR 100.0% > 15%
  - *Likely Cause (Hypothesis):* Physical model mismatch (IC, BC, heating, variable alpha) produces large structured residuals that trip the physical jump gate C or sensor fault gate F.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Model discrepancy Gaussian process (Kennedy-O'Hagan framework) isolating structural bias from discrete jumps.

- **Module:** `Two-Stage Placement` | **Severity:** Time-drifting oscillating BC
  - *Failure Reason:* Error 2.4x > 2x clean; Coverage 60.0% < 80%
  - *Likely Cause (Hypothesis):* Dirichlet boundary mismatch creates non-zero asymptotic temperature floor, destroying exponential decay assumption.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Joint estimation of boundary offsets u_0, u_1 alongside diffusivity alpha.

### Scenario 6: Source-term / heating mismatch
- **Module:** `Mode 2` | **Severity:** Weak constant source s = 0.10
  - *Failure Reason:* Error 9.8x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Internal heat generation counteracts thermal diffusion decay, shifting apparent alpha toward zero.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Dual-parameter source-diffusivity inversion or PDE residual penalty term.

- **Module:** `Mode 3` | **Severity:** Weak constant source s = 0.10
  - *Failure Reason:* Error 11.8x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Internal heat generation counteracts thermal diffusion decay, shifting apparent alpha toward zero.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Dual-parameter source-diffusivity inversion or PDE residual penalty term.

- **Module:** `Mode 3+` | **Severity:** Weak constant source s = 0.10
  - *Failure Reason:* Error 9.8x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Internal heat generation counteracts thermal diffusion decay, shifting apparent alpha toward zero.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Dual-parameter source-diffusivity inversion or PDE residual penalty term.

- **Module:** `Two-Stage Placement` | **Severity:** Weak constant source s = 0.10
  - *Failure Reason:* Error 27.0x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Internal heat generation counteracts thermal diffusion decay, shifting apparent alpha toward zero.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Dual-parameter source-diffusivity inversion or PDE residual penalty term.

- **Module:** `Anomaly Cascade` | **Severity:** Weak constant source s = 0.10
  - *Failure Reason:* Healthy FAR 100.0% > 15%
  - *Likely Cause (Hypothesis):* Physical model mismatch (IC, BC, heating, variable alpha) produces large structured residuals that trip the physical jump gate C or sensor fault gate F.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Model discrepancy Gaussian process (Kennedy-O'Hagan framework) isolating structural bias from discrete jumps.

- **Module:** `Mode 2` | **Severity:** Moderate constant source s = 0.50
  - *Failure Reason:* Error 43.6x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Internal heat generation counteracts thermal diffusion decay, shifting apparent alpha toward zero.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Dual-parameter source-diffusivity inversion or PDE residual penalty term.

- **Module:** `Mode 3` | **Severity:** Moderate constant source s = 0.50
  - *Failure Reason:* Error 51.4x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Internal heat generation counteracts thermal diffusion decay, shifting apparent alpha toward zero.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Dual-parameter source-diffusivity inversion or PDE residual penalty term.

- **Module:** `Mode 3+` | **Severity:** Moderate constant source s = 0.50
  - *Failure Reason:* Error 43.6x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Internal heat generation counteracts thermal diffusion decay, shifting apparent alpha toward zero.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Dual-parameter source-diffusivity inversion or PDE residual penalty term.

- **Module:** `Two-Stage Placement` | **Severity:** Moderate constant source s = 0.50
  - *Failure Reason:* Error 112.8x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Internal heat generation counteracts thermal diffusion decay, shifting apparent alpha toward zero.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Dual-parameter source-diffusivity inversion or PDE residual penalty term.

- **Module:** `Anomaly Cascade` | **Severity:** Moderate constant source s = 0.50
  - *Failure Reason:* Healthy FAR 100.0% > 15%
  - *Likely Cause (Hypothesis):* Physical model mismatch (IC, BC, heating, variable alpha) produces large structured residuals that trip the physical jump gate C or sensor fault gate F.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Model discrepancy Gaussian process (Kennedy-O'Hagan framework) isolating structural bias from discrete jumps.

- **Module:** `Mode 2` | **Severity:** Strong localized heating s = 2.0 at core
  - *Failure Reason:* Error 60.5x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Internal heat generation counteracts thermal diffusion decay, shifting apparent alpha toward zero.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Dual-parameter source-diffusivity inversion or PDE residual penalty term.

- **Module:** `Mode 3` | **Severity:** Strong localized heating s = 2.0 at core
  - *Failure Reason:* Error 71.1x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Internal heat generation counteracts thermal diffusion decay, shifting apparent alpha toward zero.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Dual-parameter source-diffusivity inversion or PDE residual penalty term.

- **Module:** `Mode 3+` | **Severity:** Strong localized heating s = 2.0 at core
  - *Failure Reason:* Error 60.5x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Internal heat generation counteracts thermal diffusion decay, shifting apparent alpha toward zero.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Dual-parameter source-diffusivity inversion or PDE residual penalty term.

- **Module:** `Two-Stage Placement` | **Severity:** Strong localized heating s = 2.0 at core
  - *Failure Reason:* Error 159.6x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Internal heat generation counteracts thermal diffusion decay, shifting apparent alpha toward zero.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Dual-parameter source-diffusivity inversion or PDE residual penalty term.

- **Module:** `Anomaly Cascade` | **Severity:** Strong localized heating s = 2.0 at core
  - *Failure Reason:* Healthy FAR 100.0% > 15%
  - *Likely Cause (Hypothesis):* Physical model mismatch (IC, BC, heating, variable alpha) produces large structured residuals that trip the physical jump gate C or sensor fault gate F.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Model discrepancy Gaussian process (Kennedy-O'Hagan framework) isolating structural bias from discrete jumps.

### Scenario 7: Variable diffusivity alpha(x)
- **Module:** `Anomaly Cascade` | **Severity:** Linear gradient +/- 20%
  - *Failure Reason:* Healthy FAR 40.0% > 15%
  - *Likely Cause (Hypothesis):* Physical model mismatch (IC, BC, heating, variable alpha) produces large structured residuals that trip the physical jump gate C or sensor fault gate F.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Model discrepancy Gaussian process (Kennedy-O'Hagan framework) isolating structural bias from discrete jumps.

- **Module:** `Mode 2` | **Severity:** Linear gradient +/- 50%
  - *Failure Reason:* Coverage 60.0% < 80%
  - *Likely Cause (Hypothesis):* Spatially variable alpha(x) invalidates scalar constant diffusion hypothesis; fit settles on spatially averaged surrogate value.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Spatial spline parameterization alpha(x) = sum_k c_k B_k(x) with Tikhonov smoothness regularization.

- **Module:** `Mode 3` | **Severity:** Linear gradient +/- 50%
  - *Failure Reason:* Coverage 60.0% < 80%
  - *Likely Cause (Hypothesis):* Spatially variable alpha(x) invalidates scalar constant diffusion hypothesis; fit settles on spatially averaged surrogate value.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Spatial spline parameterization alpha(x) = sum_k c_k B_k(x) with Tikhonov smoothness regularization.

- **Module:** `Mode 3+` | **Severity:** Linear gradient +/- 50%
  - *Failure Reason:* Coverage 60.0% < 80%
  - *Likely Cause (Hypothesis):* Spatially variable alpha(x) invalidates scalar constant diffusion hypothesis; fit settles on spatially averaged surrogate value.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Spatial spline parameterization alpha(x) = sum_k c_k B_k(x) with Tikhonov smoothness regularization.

- **Module:** `Two-Stage Placement` | **Severity:** Linear gradient +/- 50%
  - *Failure Reason:* Error 3.0x > 2x clean
  - *Likely Cause (Hypothesis):* Spatially variable alpha(x) invalidates scalar constant diffusion hypothesis; fit settles on spatially averaged surrogate value.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Spatial spline parameterization alpha(x) = sum_k c_k B_k(x) with Tikhonov smoothness regularization.

- **Module:** `Anomaly Cascade` | **Severity:** Linear gradient +/- 50%
  - *Failure Reason:* Healthy FAR 100.0% > 15%
  - *Likely Cause (Hypothesis):* Physical model mismatch (IC, BC, heating, variable alpha) produces large structured residuals that trip the physical jump gate C or sensor fault gate F.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Model discrepancy Gaussian process (Kennedy-O'Hagan framework) isolating structural bias from discrete jumps.

- **Module:** `Mode 2` | **Severity:** Discontinuous step (alpha to 2.0 alpha)
  - *Failure Reason:* Error 26.6x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Spatially variable alpha(x) invalidates scalar constant diffusion hypothesis; fit settles on spatially averaged surrogate value.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Spatial spline parameterization alpha(x) = sum_k c_k B_k(x) with Tikhonov smoothness regularization.

- **Module:** `Mode 3` | **Severity:** Discontinuous step (alpha to 2.0 alpha)
  - *Failure Reason:* Error 31.5x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Spatially variable alpha(x) invalidates scalar constant diffusion hypothesis; fit settles on spatially averaged surrogate value.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Spatial spline parameterization alpha(x) = sum_k c_k B_k(x) with Tikhonov smoothness regularization.

- **Module:** `Mode 3+` | **Severity:** Discontinuous step (alpha to 2.0 alpha)
  - *Failure Reason:* Error 26.6x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Spatially variable alpha(x) invalidates scalar constant diffusion hypothesis; fit settles on spatially averaged surrogate value.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Spatial spline parameterization alpha(x) = sum_k c_k B_k(x) with Tikhonov smoothness regularization.

- **Module:** `Two-Stage Placement` | **Severity:** Discontinuous step (alpha to 2.0 alpha)
  - *Failure Reason:* Error 80.7x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Spatially variable alpha(x) invalidates scalar constant diffusion hypothesis; fit settles on spatially averaged surrogate value.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Spatial spline parameterization alpha(x) = sum_k c_k B_k(x) with Tikhonov smoothness regularization.

- **Module:** `Anomaly Cascade` | **Severity:** Discontinuous step (alpha to 2.0 alpha)
  - *Failure Reason:* Healthy FAR 100.0% > 15%
  - *Likely Cause (Hypothesis):* Physical model mismatch (IC, BC, heating, variable alpha) produces large structured residuals that trip the physical jump gate C or sensor fault gate F.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Model discrepancy Gaussian process (Kennedy-O'Hagan framework) isolating structural bias from discrete jumps.

### Scenario 8: Sensor dropout
- **Module:** `Two-Stage Placement` | **Severity:** 30% readings missing (3 sensors dropped)
  - *Failure Reason:* Error 2.0x > 2x clean
  - *Likely Cause (Hypothesis):* Sensor dropout reduces temporal Fisher information below threshold needed for narrow CI coverage.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Information-preserving adaptive re-sampling triggered upon sensor heartbeat loss.

- **Module:** `Mode 2` | **Severity:** 50% readings missing (5 sensors dropped)
  - *Failure Reason:* Error 2.4x > 2x clean
  - *Likely Cause (Hypothesis):* Sensor dropout reduces temporal Fisher information below threshold needed for narrow CI coverage.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Information-preserving adaptive re-sampling triggered upon sensor heartbeat loss.

- **Module:** `Mode 3` | **Severity:** 50% readings missing (5 sensors dropped)
  - *Failure Reason:* Error 2.3x > 2x clean
  - *Likely Cause (Hypothesis):* Sensor dropout reduces temporal Fisher information below threshold needed for narrow CI coverage.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Information-preserving adaptive re-sampling triggered upon sensor heartbeat loss.

- **Module:** `Mode 3+` | **Severity:** 50% readings missing (5 sensors dropped)
  - *Failure Reason:* Error 2.4x > 2x clean
  - *Likely Cause (Hypothesis):* Sensor dropout reduces temporal Fisher information below threshold needed for narrow CI coverage.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Information-preserving adaptive re-sampling triggered upon sensor heartbeat loss.

### Scenario 9: Sensor position error and time jitter
- **Module:** `Anomaly Cascade` | **Severity:** Small jitter sigma_jitter = 0.01
  - *Failure Reason:* Healthy FAR 40.0% > 15%
  - *Likely Cause (Hypothesis):* Severe input perturbation exceeds GLR threshold tolerance.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Nonparametric change-point CUSUM detector.

- **Module:** `Anomaly Cascade` | **Severity:** Moderate jitter sigma_jitter = 0.03
  - *Failure Reason:* Healthy FAR 100.0% > 15%
  - *Likely Cause (Hypothesis):* Severe input perturbation exceeds GLR threshold tolerance.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Nonparametric change-point CUSUM detector.

- **Module:** `Mode 2` | **Severity:** Large jitter sigma_jitter = 0.06
  - *Failure Reason:* Error 7.5x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Sensor position and timing jitter introduce observation coordinate errors that propagate nonlinearly into gradient-based fits.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Total least squares (TLS) or measurement-error model incorporating coordinate uncertainty.

- **Module:** `Mode 3` | **Severity:** Large jitter sigma_jitter = 0.06
  - *Failure Reason:* Error 8.7x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Sensor position and timing jitter introduce observation coordinate errors that propagate nonlinearly into gradient-based fits.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Total least squares (TLS) or measurement-error model incorporating coordinate uncertainty.

- **Module:** `Mode 3+` | **Severity:** Large jitter sigma_jitter = 0.06
  - *Failure Reason:* Error 7.5x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Sensor position and timing jitter introduce observation coordinate errors that propagate nonlinearly into gradient-based fits.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Total least squares (TLS) or measurement-error model incorporating coordinate uncertainty.

- **Module:** `Anomaly Cascade` | **Severity:** Large jitter sigma_jitter = 0.06
  - *Failure Reason:* Healthy FAR 100.0% > 15%
  - *Likely Cause (Hypothesis):* Severe input perturbation exceeds GLR threshold tolerance.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Nonparametric change-point CUSUM detector.

### Scenario 10: Constant sensor bias
- **Module:** `Two-Stage Placement` | **Severity:** Small sensor bias b = 3 sigma (0.03)
  - *Failure Reason:* Error 2.1x > 2x clean
  - *Likely Cause (Hypothesis):* Constant sensor offset acts as persistent non-zero residual, pulling fitted alpha away from true value.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Automated outlier sensor calibration gate and median-based spatial filtering.

- **Module:** `Anomaly Cascade` | **Severity:** Small sensor bias b = 3 sigma (0.03)
  - *Failure Reason:* Healthy FAR 20.0% > 15%
  - *Likely Cause (Hypothesis):* Constant sensor bias trips BIC fault gate; strong bias mimics physical regime shift if single-sensor gate saturates.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Enhanced LOO sensor exclusion with explicit sensor bias hypothesis M_B.

- **Module:** `Anomaly Cascade` | **Severity:** Medium sensor bias b = 6 sigma (0.06)
  - *Failure Reason:* Healthy FAR 100.0% > 15%
  - *Likely Cause (Hypothesis):* Constant sensor bias trips BIC fault gate; strong bias mimics physical regime shift if single-sensor gate saturates.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Enhanced LOO sensor exclusion with explicit sensor bias hypothesis M_B.

- **Module:** `Anomaly Cascade` | **Severity:** Strong sensor bias b = 15 sigma (0.15)
  - *Failure Reason:* Healthy FAR 100.0% > 15%
  - *Likely Cause (Hypothesis):* Constant sensor bias trips BIC fault gate; strong bias mimics physical regime shift if single-sensor gate saturates.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Enhanced LOO sensor exclusion with explicit sensor bias hypothesis M_B.

### Scenario 11: Very few sensors
- **Module:** `Mode 2` | **Severity:** Sparse array N = 5 sensors
  - *Failure Reason:* Error 2.0x > 2x clean
  - *Likely Cause (Hypothesis):* N <= 3 observations lack sufficient temporal support to constrain curvature of exponential decay.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Physics-informed Bayesian prior shrinkage to prevent unidentifiable divergence.

- **Module:** `Mode 3+` | **Severity:** Sparse array N = 5 sensors
  - *Failure Reason:* Error 2.0x > 2x clean
  - *Likely Cause (Hypothesis):* N <= 3 observations lack sufficient temporal support to constrain curvature of exponential decay.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Physics-informed Bayesian prior shrinkage to prevent unidentifiable divergence.

- **Module:** `Two-Stage Placement` | **Severity:** Sparse array N = 5 sensors
  - *Failure Reason:* Error 2.7x > 2x clean
  - *Likely Cause (Hypothesis):* N <= 3 observations lack sufficient temporal support to constrain curvature of exponential decay.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Physics-informed Bayesian prior shrinkage to prevent unidentifiable divergence.

- **Module:** `Mode 2` | **Severity:** Very sparse array N = 3 sensors
  - *Failure Reason:* Error 2.6x > 2x clean
  - *Likely Cause (Hypothesis):* N <= 3 observations lack sufficient temporal support to constrain curvature of exponential decay.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Physics-informed Bayesian prior shrinkage to prevent unidentifiable divergence.

- **Module:** `Mode 3+` | **Severity:** Very sparse array N = 3 sensors
  - *Failure Reason:* Error 2.6x > 2x clean
  - *Likely Cause (Hypothesis):* N <= 3 observations lack sufficient temporal support to constrain curvature of exponential decay.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Physics-informed Bayesian prior shrinkage to prevent unidentifiable divergence.

- **Module:** `Anomaly Cascade` | **Severity:** Very sparse array N = 3 sensors
  - *Failure Reason:* Healthy FAR 20.0% > 15%
  - *Likely Cause (Hypothesis):* Severe input perturbation exceeds GLR threshold tolerance.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Nonparametric change-point CUSUM detector.

- **Module:** `Mode 3` | **Severity:** Minimal array N = 2 sensors
  - *Failure Reason:* Error 2.7x > 2x clean
  - *Likely Cause (Hypothesis):* N <= 3 observations lack sufficient temporal support to constrain curvature of exponential decay.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Physics-informed Bayesian prior shrinkage to prevent unidentifiable divergence.

- **Module:** `Two-Stage Placement` | **Severity:** Minimal array N = 2 sensors
  - *Failure Reason:* Error 5.0x > 2x clean
  - *Likely Cause (Hypothesis):* N <= 3 observations lack sufficient temporal support to constrain curvature of exponential decay.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Physics-informed Bayesian prior shrinkage to prevent unidentifiable divergence.

### Scenario 12: True alpha beyond the grid
- **Module:** `Mode 2` | **Severity:** Sub-grid low diffusivity alpha = 5e-4
  - *Failure Reason:* Error 61.1x > 2x clean
  - *Likely Cause (Hypothesis):* Alpha lies outside surrogate precomputation grid [-3.0, 1.0], hitting artificial search boundary.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Dynamic multi-scale grid expansion with adaptive domain re-normalization.

- **Module:** `Mode 3` | **Severity:** Sub-grid low diffusivity alpha = 5e-4
  - *Failure Reason:* Error 135.8x > 2x clean
  - *Likely Cause (Hypothesis):* Alpha lies outside surrogate precomputation grid [-3.0, 1.0], hitting artificial search boundary.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Dynamic multi-scale grid expansion with adaptive domain re-normalization.

- **Module:** `Mode 3+` | **Severity:** Sub-grid low diffusivity alpha = 5e-4
  - *Failure Reason:* Error 61.1x > 2x clean
  - *Likely Cause (Hypothesis):* Alpha lies outside surrogate precomputation grid [-3.0, 1.0], hitting artificial search boundary.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Dynamic multi-scale grid expansion with adaptive domain re-normalization.

- **Module:** `Two-Stage Placement` | **Severity:** Sub-grid low diffusivity alpha = 5e-4
  - *Failure Reason:* Error 161.2x > 2x clean
  - *Likely Cause (Hypothesis):* Alpha lies outside surrogate precomputation grid [-3.0, 1.0], hitting artificial search boundary.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Dynamic multi-scale grid expansion with adaptive domain re-normalization.

- **Module:** `Anomaly Cascade` | **Severity:** Sub-grid low diffusivity alpha = 5e-4
  - *Failure Reason:* Healthy FAR 100.0% > 15%
  - *Likely Cause (Hypothesis):* Severe input perturbation exceeds GLR threshold tolerance.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Nonparametric change-point CUSUM detector.

- **Module:** `Mode 2` | **Severity:** Super-grid high diffusivity alpha = 5.0
  - *Failure Reason:* Error 8.0x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Alpha lies outside surrogate precomputation grid [-3.0, 1.0], hitting artificial search boundary.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Dynamic multi-scale grid expansion with adaptive domain re-normalization.

- **Module:** `Mode 3` | **Severity:** Super-grid high diffusivity alpha = 5.0
  - *Failure Reason:* Error 7.1x > 2x clean; Coverage 20.0% < 80%
  - *Likely Cause (Hypothesis):* Alpha lies outside surrogate precomputation grid [-3.0, 1.0], hitting artificial search boundary.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Dynamic multi-scale grid expansion with adaptive domain re-normalization.

- **Module:** `Mode 3+` | **Severity:** Super-grid high diffusivity alpha = 5.0
  - *Failure Reason:* Error 8.0x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Alpha lies outside surrogate precomputation grid [-3.0, 1.0], hitting artificial search boundary.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Dynamic multi-scale grid expansion with adaptive domain re-normalization.

- **Module:** `Anomaly Cascade` | **Severity:** Super-grid high diffusivity alpha = 5.0
  - *Failure Reason:* Healthy FAR 100.0% > 15%
  - *Likely Cause (Hypothesis):* Severe input perturbation exceeds GLR threshold tolerance.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Nonparametric change-point CUSUM detector.

- **Module:** `Mode 2` | **Severity:** Super-grid extreme diffusivity alpha = 20.0
  - *Failure Reason:* Error 30.6x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Alpha lies outside surrogate precomputation grid [-3.0, 1.0], hitting artificial search boundary.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Dynamic multi-scale grid expansion with adaptive domain re-normalization.

- **Module:** `Mode 3` | **Severity:** Super-grid extreme diffusivity alpha = 20.0
  - *Failure Reason:* Error 35.9x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Alpha lies outside surrogate precomputation grid [-3.0, 1.0], hitting artificial search boundary.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Dynamic multi-scale grid expansion with adaptive domain re-normalization.

- **Module:** `Mode 3+` | **Severity:** Super-grid extreme diffusivity alpha = 20.0
  - *Failure Reason:* Error 30.6x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Alpha lies outside surrogate precomputation grid [-3.0, 1.0], hitting artificial search boundary.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Dynamic multi-scale grid expansion with adaptive domain re-normalization.

- **Module:** `Two-Stage Placement` | **Severity:** Super-grid extreme diffusivity alpha = 20.0
  - *Failure Reason:* Error 80.6x > 2x clean; Coverage 0.0% < 80%
  - *Likely Cause (Hypothesis):* Alpha lies outside surrogate precomputation grid [-3.0, 1.0], hitting artificial search boundary.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Dynamic multi-scale grid expansion with adaptive domain re-normalization.

- **Module:** `Anomaly Cascade` | **Severity:** Super-grid extreme diffusivity alpha = 20.0
  - *Failure Reason:* Healthy FAR 100.0% > 15%
  - *Likely Cause (Hypothesis):* Severe input perturbation exceeds GLR threshold tolerance.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Nonparametric change-point CUSUM detector.

### Scenario 13: Baseline drift
- **Module:** `Anomaly Cascade` | **Severity:** Moderate drift delta = 5%
  - *Failure Reason:* Healthy FAR 20.0% > 15%
  - *Likely Cause (Hypothesis):* Slow baseline drift causes parameter mismatch between anchored alpha_0 and operational window, tripping change-point GLR.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Dynamic rolling baseline window with exponential forgetting factor.

- **Module:** `Anomaly Cascade` | **Severity:** Severe drift delta = 10%
  - *Failure Reason:* Healthy FAR 60.0% > 15%
  - *Likely Cause (Hypothesis):* Slow baseline drift causes parameter mismatch between anchored alpha_0 and operational window, tripping change-point GLR.
  - *V2 Candidate Fix (Hypothesis):* V2 candidate: Dynamic rolling baseline window with exponential forgetting factor.

