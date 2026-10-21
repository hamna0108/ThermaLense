# Week 6 V2 Architecture Before/After Evaluation Report

> **Generated strictly from:** `data/results/v2_before_after_summary.csv`
> **Calibration Seed Record:** All threshold calibrations were frozen on seed range `1300000..1300999` and written to `data/results/v2_calibration_record.json` **BEFORE** evaluating on matrix seeds `1200000..1213399`.

## Executive Scorecard: Week 6 V2 Targets

**Total Benchmark Target Evaluations:** **34 Evaluations**
- **Targets MET:** **24 / 34** (`70.6%`)
- **Targets MISSED:** **10 / 34** (`29.4%`)

---

## 1. D1 Target: Baseline Sigma Estimation
**Requirement:** When $\sigma$ is undeclared or misspecified, estimate $\hat{\sigma}$ from $k=20$ baseline readings for Wald intervals and anomaly thresholds.
- **Target Criteria:** S1 coverage $\ge 80.0\%$, S1 healthy FAR $\le 15.0\%$.

| Scenario | Module | Metric | Before (Misspecified) | After (V2 Sigma Est) | Target | Status | Calibration / Details |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| S1 Sev 1 (true=0.01, assumed=0.05) | **Mode 2 (Sigma Est)** | 95% CI Coverage | `100.0% [96.3, 100.0]` | `84.0% [75.58, 89.9]` | Coverage >= 80.0% | **MET** | Sigma estimated as 0.0098 (true=0.01) |
| S1 Sev 1 (true=0.01, assumed=0.05) | **Anomaly Cascade (Sigma Est)** | Healthy FAR | `0.0% [0.0, 3.7]` | `11.0% [6.25, 18.63]` | Healthy FAR <= 15.0% | **MET** | Normalized by hat_sigma=0.0098 |
| S1 Sev 2 (true=0.05, assumed=0.01) | **Mode 2 (Sigma Est)** | 95% CI Coverage | `29.0% [21.01, 38.54]` | `96.0% [90.16, 98.43]` | Coverage >= 80.0% | **MET** | Sigma estimated as 0.0491 (true=0.05) |
| S1 Sev 2 (true=0.05, assumed=0.01) | **Anomaly Cascade (Sigma Est)** | Healthy FAR | `100.0% [96.3, 100.0]` | `6.0% [2.78, 12.48]` | Healthy FAR <= 15.0% | **MET** | Normalized by hat_sigma=0.0491 |
| S1 Sev 3 (true=0.03, assumed=0.01) | **Mode 2 (Sigma Est)** | 95% CI Coverage | `47.0% [37.51, 56.71]` | `97.0% [91.55, 98.97]` | Coverage >= 80.0% | **MET** | Sigma estimated as 0.0291 (true=0.03) |
| S1 Sev 3 (true=0.03, assumed=0.01) | **Anomaly Cascade (Sigma Est)** | Healthy FAR | `99.0% [94.55, 99.82]` | `4.0% [1.57, 9.84]` | Healthy FAR <= 15.0% | **MET** | Normalized by hat_sigma=0.0291 |

---

## 2. D2 Target: Goodness-of-Fit Gate ($\chi^2/\text{dof}$)
**Requirement:** Flag `'model_invalid'` when $\chi^2/\text{dof}$ of fit exceeds $\tau_{\text{gof}} = 1.878$ (calibrated on healthy runs on seeds 1300000+ for $\le 5.0\%$ false flags).
- **Target Criteria:** Detection rate $\ge 80.0\%$ on S4–S7 (wrong physics) and S3 (correlated noise); Healthy false-flag rate $\le 5.0\%$.

| Scenario | Module | Metric | Before (Ungated) | After (V2 GOF Gate) | Target | Status | Observed $\chi^2/\text{dof}$ |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| Healthy Control (sigma=0.01) | **GOF Gate (chi2/dof > 1.878)** | Healthy False Flag Rate | `0.0% (Ungated)` | `7.0% [3.43, 13.75]` | False Flags <= 5.0% | <span style='color:red;'>**MISSED**</span> | Median chi2/dof = 0.928 |
| S3 Sev 1 (AR(1) rho = 0.50) | **GOF Gate (chi2/dof > 1.878)** | Model Invalid Flag Rate | `0.0% (Ungated silent fit)` | `1.0% [0.18, 5.45]` | Flag Rate >= 80.0% | <span style='color:red;'>**MISSED**</span> | Median chi2/dof = 0.74 |
| S3 Sev 2 (AR(1) rho = 0.80) | **GOF Gate (chi2/dof > 1.878)** | Model Invalid Flag Rate | `0.0% (Ungated silent fit)` | `2.0% [0.55, 7.0]` | Flag Rate >= 80.0% | <span style='color:red;'>**MISSED**</span> | Median chi2/dof = 0.52 |
| S3 Sev 3 (AR(1) rho = 0.95) | **GOF Gate (chi2/dof > 1.878)** | Model Invalid Flag Rate | `0.0% (Ungated silent fit)` | `2.0% [0.55, 7.0]` | Flag Rate >= 80.0% | <span style='color:red;'>**MISSED**</span> | Median chi2/dof = 0.24 |
| S4 Sev 1 (Harmonic double mode sin(2 pi x)) | **GOF Gate (chi2/dof > 1.878)** | Model Invalid Flag Rate | `0.0% (Ungated silent fit)` | `100.0% [96.3, 100.0]` | Flag Rate >= 80.0% | **MET** | Median chi2/dof = 2848.47 |
| S4 Sev 2 (Two-mode sum sin(pi x) + 0.5 sin(3 pi x)) | **GOF Gate (chi2/dof > 1.878)** | Model Invalid Flag Rate | `0.0% (Ungated silent fit)` | `100.0% [96.3, 100.0]` | Flag Rate >= 80.0% | **MET** | Median chi2/dof = 358.37 |
| S4 Sev 3 (Gaussian bump exp(-(x-0.5)^2 / (2*0.08^2))) | **GOF Gate (chi2/dof > 1.878)** | Model Invalid Flag Rate | `0.0% (Ungated silent fit)` | `100.0% [96.3, 100.0]` | Flag Rate >= 80.0% | **MET** | Median chi2/dof = 639.53 |
| S5 Sev 1 (Small constant offset u_bc = 0.05) | **GOF Gate (chi2/dof > 1.878)** | Model Invalid Flag Rate | `0.0% (Ungated silent fit)` | `28.0% [20.14, 37.49]` | Flag Rate >= 80.0% | <span style='color:red;'>**MISSED**</span> | Median chi2/dof = 1.38 |
| S5 Sev 2 (Moderate constant offset u_bc = 0.15) | **GOF Gate (chi2/dof > 1.878)** | Model Invalid Flag Rate | `0.0% (Ungated silent fit)` | `60.0% [50.2, 69.06]` | Flag Rate >= 80.0% | <span style='color:red;'>**MISSED**</span> | Median chi2/dof = 2.14 |
| S5 Sev 3 (Linearly drifting boundary u_bc(t) = 0.20 * t) | **GOF Gate (chi2/dof > 1.878)** | Model Invalid Flag Rate | `0.0% (Ungated silent fit)` | `36.0% [27.27, 45.76]` | Flag Rate >= 80.0% | <span style='color:red;'>**MISSED**</span> | Median chi2/dof = 1.63 |
| S6 Sev 1 (Small constant source s = 0.1) | **GOF Gate (chi2/dof > 1.878)** | Model Invalid Flag Rate | `0.0% (Ungated silent fit)` | `69.0% [59.37, 77.22]` | Flag Rate >= 80.0% | <span style='color:red;'>**MISSED**</span> | Median chi2/dof = 2.57 |
| S6 Sev 2 (Moderate constant source s = 0.5) | **GOF Gate (chi2/dof > 1.878)** | Model Invalid Flag Rate | `0.0% (Ungated silent fit)` | `100.0% [96.3, 100.0]` | Flag Rate >= 80.0% | **MET** | Median chi2/dof = 51.01 |
| S6 Sev 3 (Strong constant source s = 2.0) | **GOF Gate (chi2/dof > 1.878)** | Model Invalid Flag Rate | `0.0% (Ungated silent fit)` | `100.0% [96.3, 100.0]` | Flag Rate >= 80.0% | **MET** | Median chi2/dof = 1505.22 |
| S7 Sev 1 (Mild linear ramp alpha(x) = alpha0*(1 + 0.5*(x-0.5))) | **GOF Gate (chi2/dof > 1.878)** | Model Invalid Flag Rate | `0.0% (Ungated silent fit)` | `81.0% [72.22, 87.49]` | Flag Rate >= 80.0% | **MET** | Median chi2/dof = 3.31 |
| S7 Sev 2 (Steep linear ramp alpha(x) = alpha0*(1 + 1.5*(x-0.5))) | **GOF Gate (chi2/dof > 1.878)** | Model Invalid Flag Rate | `0.0% (Ungated silent fit)` | `99.0% [94.55, 99.82]` | Flag Rate >= 80.0% | **MET** | Median chi2/dof = 10.59 |
| S7 Sev 3 (Step discontinuity alpha(x) = 2*alpha0 for x > 0.5) | **GOF Gate (chi2/dof > 1.878)** | Model Invalid Flag Rate | `0.0% (Ungated silent fit)` | `98.0% [93.0, 99.45]` | Flag Rate >= 80.0% | **MET** | Median chi2/dof = 6.14 |

---

## 3. D3 Target: Range Guard & Bound Pinning Flag
**Requirement:** Route Mode 3 to Mode 3+ if estimate $\notin [0.01, 1.0]$; flag `'estimate_at_bound'` / `'out_of_range'` if within 1% of grid bounds ($[0.001, 10.0]$).
- **Target Criteria:** S12 out-of-grid cells flagged $\ge 95.0\%$.

| Scenario | Module | Metric | Before (Unguarded) | After (V2 Range Guard) | Target | Status | Operational Notes |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| S12 Sev 1 (alpha=0.0005) | **Range Guard Mode 3** | At Bound / Out-of-Range % | `51.0%` | `72.0% [62.51, 79.86]` | Out-of-grid Flagged >= 95.0% | <span style='color:red;'>**MISSED**</span> | Routed to M3+: 100.0%; Median hat: 0.0010 |
| S12 Sev 2 (alpha=5.0) | **Range Guard Mode 3** | At Bound / Out-of-Range % | `0.0%` | `0.0% [0.0, 3.7]` | Inside grid: routed to Mode 3+ | **MET** | Routed to M3+: 100.0%; Median hat: 4.4626 |
| S12 Sev 3 (alpha=20.0) | **Range Guard Mode 3** | At Bound / Out-of-Range % | `100.0%` | `100.0% [96.3, 100.0]` | Out-of-grid Flagged >= 95.0% | **MET** | Routed to M3+: 100.0%; Median hat: 9.9988 |

---

## 4. D4 Target: Declared Physics Parameter Inversion
**Requirement:** Pass declared physics ($u_0(x)$, boundary values, volumetric source) to the general CN solver with live bounded-Brent optimization.
- **Target Criteria:** S4–S6 median relative error within $2.0\times$ clean reference ($0.0116$).

| Scenario | Module | Metric | Before (Frozen Model Mismatch) | After (V2 Declared Physics) | Target | Status | 95% CI Coverage |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| S4 Sev 1 (Harmonic double mode sin(2 pi x)) | **Declared Physics General CN** | Median Rel Error vs Clean | `98.998704 (8569.091x clean)` | `0.0216 (1.87x clean)` | Error <= 2.0x clean | **MET** | Coverage: 82.0% [73.33, 88.3] |
| S4 Sev 2 (Two-mode sum sin(pi x) + 0.5 sin(3 pi x)) | **Declared Physics General CN** | Median Rel Error vs Clean | `0.056251 (4.869x clean)` | `0.0149 (1.29x clean)` | Error <= 2.0x clean | **MET** | Coverage: 88.0% [80.19, 93.0] |
| S4 Sev 3 (Gaussian bump exp(-(x-0.5)^2 / (2*0.08^2))) | **Declared Physics General CN** | Median Rel Error vs Clean | `26.14309 (2262.883x clean)` | `0.0378 (3.27x clean)` | Error <= 2.0x clean | <span style='color:red;'>**MISSED**</span> | Coverage: 82.0% [73.33, 88.3] |
| S5 Sev 1 (Small constant offset u_bc = 0.05) | **Declared Physics General CN** | Median Rel Error vs Clean | `0.069225 (5.992x clean)` | `0.0156 (1.35x clean)` | Error <= 2.0x clean | **MET** | Coverage: 86.0% [77.86, 91.47] |
| S5 Sev 2 (Moderate constant offset u_bc = 0.15) | **Declared Physics General CN** | Median Rel Error vs Clean | `0.188555 (16.321x clean)` | `0.0179 (1.55x clean)` | Error <= 2.0x clean | **MET** | Coverage: 93.0% [86.25, 96.57] |
| S5 Sev 3 (Linearly drifting boundary u_bc(t) = 0.20 * t) | **Declared Physics General CN** | Median Rel Error vs Clean | `0.100709 (8.717x clean)` | `0.0141 (1.22x clean)` | Error <= 2.0x clean | **MET** | Coverage: 89.0% [81.37, 93.75] |
| S6 Sev 1 (Small constant source s = 0.1) | **Declared Physics General CN** | Median Rel Error vs Clean | `0.169442 (14.666x clean)` | `0.0097 (0.84x clean)` | Error <= 2.0x clean | **MET** | Coverage: 93.0% [86.25, 96.57] |
| S6 Sev 2 (Moderate constant source s = 0.5) | **Declared Physics General CN** | Median Rel Error vs Clean | `0.714372 (61.834x clean)` | `0.0120 (1.04x clean)` | Error <= 2.0x clean | **MET** | Coverage: 86.0% [77.86, 91.47] |
| S6 Sev 3 (Strong constant source s = 2.0) | **Declared Physics General CN** | Median Rel Error vs Clean | `0.99 (85.692x clean)` | `0.0094 (0.82x clean)` | Error <= 2.0x clean | **MET** | Coverage: 76.0% [66.77, 83.31] |

---

## 5. D5 Limitations & Warning Gates
The following regimes are mathematically or physically unidentifiable without additional structural models, and are formally guarded with warnings/refusal:
1. **Heavy-Tailed Noise (S2, Student-t):** L2 likelihood loss degrades under outliers; service emits excess kurtosis warning.
2. **Correlated Noise (S3, AR(1)):** Residual autocorrelation violates i.i.d. assumption; service emits Durbin-Watson autocorrelation warning.
3. **Baseline Drift $\ge 10\%$ (S13):** Persistent thermal drift biases null parameter fit; service emits drift warning.
4. **Baseline $< 20$ readings:** Sample variance estimator is unstable below $k=20$; service refuses execution with `ValueError` or emits warning.

---

## 6. Complete Before/After Comparison Table

| Target ID | Scenario | Module | Metric | Before | After | Target Spec | Status | Notes |
| :---: | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **D1** | S1 Sev 1 (true=0.01, assumed=0.05) | Mode 2 (Sigma Est) | 95% CI Coverage | `100.0% [96.3, 100.0]` | `84.0% [75.58, 89.9]` | Coverage >= 80.0% | **MET** | Sigma estimated as 0.0098 (true=0.01) |
| **D1** | S1 Sev 1 (true=0.01, assumed=0.05) | Anomaly Cascade (Sigma Est) | Healthy FAR | `0.0% [0.0, 3.7]` | `11.0% [6.25, 18.63]` | Healthy FAR <= 15.0% | **MET** | Normalized by hat_sigma=0.0098 |
| **D1** | S1 Sev 2 (true=0.05, assumed=0.01) | Mode 2 (Sigma Est) | 95% CI Coverage | `29.0% [21.01, 38.54]` | `96.0% [90.16, 98.43]` | Coverage >= 80.0% | **MET** | Sigma estimated as 0.0491 (true=0.05) |
| **D1** | S1 Sev 2 (true=0.05, assumed=0.01) | Anomaly Cascade (Sigma Est) | Healthy FAR | `100.0% [96.3, 100.0]` | `6.0% [2.78, 12.48]` | Healthy FAR <= 15.0% | **MET** | Normalized by hat_sigma=0.0491 |
| **D1** | S1 Sev 3 (true=0.03, assumed=0.01) | Mode 2 (Sigma Est) | 95% CI Coverage | `47.0% [37.51, 56.71]` | `97.0% [91.55, 98.97]` | Coverage >= 80.0% | **MET** | Sigma estimated as 0.0291 (true=0.03) |
| **D1** | S1 Sev 3 (true=0.03, assumed=0.01) | Anomaly Cascade (Sigma Est) | Healthy FAR | `99.0% [94.55, 99.82]` | `4.0% [1.57, 9.84]` | Healthy FAR <= 15.0% | **MET** | Normalized by hat_sigma=0.0291 |
| **D2** | Healthy Control (sigma=0.01) | GOF Gate (chi2/dof > 1.878) | Healthy False Flag Rate | `0.0% (Ungated)` | `7.0% [3.43, 13.75]` | False Flags <= 5.0% | <span style='color:red;'>**MISSED**</span> | Median chi2/dof = 0.928 |
| **D2** | S3 Sev 1 (AR(1) rho = 0.50) | GOF Gate (chi2/dof > 1.878) | Model Invalid Flag Rate | `0.0% (Ungated silent fit)` | `1.0% [0.18, 5.45]` | Flag Rate >= 80.0% | <span style='color:red;'>**MISSED**</span> | Median chi2/dof = 0.74 |
| **D2** | S3 Sev 2 (AR(1) rho = 0.80) | GOF Gate (chi2/dof > 1.878) | Model Invalid Flag Rate | `0.0% (Ungated silent fit)` | `2.0% [0.55, 7.0]` | Flag Rate >= 80.0% | <span style='color:red;'>**MISSED**</span> | Median chi2/dof = 0.52 |
| **D2** | S3 Sev 3 (AR(1) rho = 0.95) | GOF Gate (chi2/dof > 1.878) | Model Invalid Flag Rate | `0.0% (Ungated silent fit)` | `2.0% [0.55, 7.0]` | Flag Rate >= 80.0% | <span style='color:red;'>**MISSED**</span> | Median chi2/dof = 0.24 |
| **D2** | S4 Sev 1 (Harmonic double mode sin(2 pi x)) | GOF Gate (chi2/dof > 1.878) | Model Invalid Flag Rate | `0.0% (Ungated silent fit)` | `100.0% [96.3, 100.0]` | Flag Rate >= 80.0% | **MET** | Median chi2/dof = 2848.47 |
| **D2** | S4 Sev 2 (Two-mode sum sin(pi x) + 0.5 sin(3 pi x)) | GOF Gate (chi2/dof > 1.878) | Model Invalid Flag Rate | `0.0% (Ungated silent fit)` | `100.0% [96.3, 100.0]` | Flag Rate >= 80.0% | **MET** | Median chi2/dof = 358.37 |
| **D2** | S4 Sev 3 (Gaussian bump exp(-(x-0.5)^2 / (2*0.08^2))) | GOF Gate (chi2/dof > 1.878) | Model Invalid Flag Rate | `0.0% (Ungated silent fit)` | `100.0% [96.3, 100.0]` | Flag Rate >= 80.0% | **MET** | Median chi2/dof = 639.53 |
| **D2** | S5 Sev 1 (Small constant offset u_bc = 0.05) | GOF Gate (chi2/dof > 1.878) | Model Invalid Flag Rate | `0.0% (Ungated silent fit)` | `28.0% [20.14, 37.49]` | Flag Rate >= 80.0% | <span style='color:red;'>**MISSED**</span> | Median chi2/dof = 1.38 |
| **D2** | S5 Sev 2 (Moderate constant offset u_bc = 0.15) | GOF Gate (chi2/dof > 1.878) | Model Invalid Flag Rate | `0.0% (Ungated silent fit)` | `60.0% [50.2, 69.06]` | Flag Rate >= 80.0% | <span style='color:red;'>**MISSED**</span> | Median chi2/dof = 2.14 |
| **D2** | S5 Sev 3 (Linearly drifting boundary u_bc(t) = 0.20 * t) | GOF Gate (chi2/dof > 1.878) | Model Invalid Flag Rate | `0.0% (Ungated silent fit)` | `36.0% [27.27, 45.76]` | Flag Rate >= 80.0% | <span style='color:red;'>**MISSED**</span> | Median chi2/dof = 1.63 |
| **D2** | S6 Sev 1 (Small constant source s = 0.1) | GOF Gate (chi2/dof > 1.878) | Model Invalid Flag Rate | `0.0% (Ungated silent fit)` | `69.0% [59.37, 77.22]` | Flag Rate >= 80.0% | <span style='color:red;'>**MISSED**</span> | Median chi2/dof = 2.57 |
| **D2** | S6 Sev 2 (Moderate constant source s = 0.5) | GOF Gate (chi2/dof > 1.878) | Model Invalid Flag Rate | `0.0% (Ungated silent fit)` | `100.0% [96.3, 100.0]` | Flag Rate >= 80.0% | **MET** | Median chi2/dof = 51.01 |
| **D2** | S6 Sev 3 (Strong constant source s = 2.0) | GOF Gate (chi2/dof > 1.878) | Model Invalid Flag Rate | `0.0% (Ungated silent fit)` | `100.0% [96.3, 100.0]` | Flag Rate >= 80.0% | **MET** | Median chi2/dof = 1505.22 |
| **D2** | S7 Sev 1 (Mild linear ramp alpha(x) = alpha0*(1 + 0.5*(x-0.5))) | GOF Gate (chi2/dof > 1.878) | Model Invalid Flag Rate | `0.0% (Ungated silent fit)` | `81.0% [72.22, 87.49]` | Flag Rate >= 80.0% | **MET** | Median chi2/dof = 3.31 |
| **D2** | S7 Sev 2 (Steep linear ramp alpha(x) = alpha0*(1 + 1.5*(x-0.5))) | GOF Gate (chi2/dof > 1.878) | Model Invalid Flag Rate | `0.0% (Ungated silent fit)` | `99.0% [94.55, 99.82]` | Flag Rate >= 80.0% | **MET** | Median chi2/dof = 10.59 |
| **D2** | S7 Sev 3 (Step discontinuity alpha(x) = 2*alpha0 for x > 0.5) | GOF Gate (chi2/dof > 1.878) | Model Invalid Flag Rate | `0.0% (Ungated silent fit)` | `98.0% [93.0, 99.45]` | Flag Rate >= 80.0% | **MET** | Median chi2/dof = 6.14 |
| **D3** | S12 Sev 1 (alpha=0.0005) | Range Guard Mode 3 | At Bound / Out-of-Range % | `51.0%` | `72.0% [62.51, 79.86]` | Out-of-grid Flagged >= 95.0% | <span style='color:red;'>**MISSED**</span> | Routed to M3+: 100.0%; Median hat: 0.0010 |
| **D3** | S12 Sev 2 (alpha=5.0) | Range Guard Mode 3 | At Bound / Out-of-Range % | `0.0%` | `0.0% [0.0, 3.7]` | Inside grid: routed to Mode 3+ | **MET** | Routed to M3+: 100.0%; Median hat: 4.4626 |
| **D3** | S12 Sev 3 (alpha=20.0) | Range Guard Mode 3 | At Bound / Out-of-Range % | `100.0%` | `100.0% [96.3, 100.0]` | Out-of-grid Flagged >= 95.0% | **MET** | Routed to M3+: 100.0%; Median hat: 9.9988 |
| **D4** | S4 Sev 1 (Harmonic double mode sin(2 pi x)) | Declared Physics General CN | Median Rel Error vs Clean | `98.998704 (8569.091x clean)` | `0.0216 (1.87x clean)` | Error <= 2.0x clean | **MET** | Coverage: 82.0% [73.33, 88.3] |
| **D4** | S4 Sev 2 (Two-mode sum sin(pi x) + 0.5 sin(3 pi x)) | Declared Physics General CN | Median Rel Error vs Clean | `0.056251 (4.869x clean)` | `0.0149 (1.29x clean)` | Error <= 2.0x clean | **MET** | Coverage: 88.0% [80.19, 93.0] |
| **D4** | S4 Sev 3 (Gaussian bump exp(-(x-0.5)^2 / (2*0.08^2))) | Declared Physics General CN | Median Rel Error vs Clean | `26.14309 (2262.883x clean)` | `0.0378 (3.27x clean)` | Error <= 2.0x clean | <span style='color:red;'>**MISSED**</span> | Coverage: 82.0% [73.33, 88.3] |
| **D4** | S5 Sev 1 (Small constant offset u_bc = 0.05) | Declared Physics General CN | Median Rel Error vs Clean | `0.069225 (5.992x clean)` | `0.0156 (1.35x clean)` | Error <= 2.0x clean | **MET** | Coverage: 86.0% [77.86, 91.47] |
| **D4** | S5 Sev 2 (Moderate constant offset u_bc = 0.15) | Declared Physics General CN | Median Rel Error vs Clean | `0.188555 (16.321x clean)` | `0.0179 (1.55x clean)` | Error <= 2.0x clean | **MET** | Coverage: 93.0% [86.25, 96.57] |
| **D4** | S5 Sev 3 (Linearly drifting boundary u_bc(t) = 0.20 * t) | Declared Physics General CN | Median Rel Error vs Clean | `0.100709 (8.717x clean)` | `0.0141 (1.22x clean)` | Error <= 2.0x clean | **MET** | Coverage: 89.0% [81.37, 93.75] |
| **D4** | S6 Sev 1 (Small constant source s = 0.1) | Declared Physics General CN | Median Rel Error vs Clean | `0.169442 (14.666x clean)` | `0.0097 (0.84x clean)` | Error <= 2.0x clean | **MET** | Coverage: 93.0% [86.25, 96.57] |
| **D4** | S6 Sev 2 (Moderate constant source s = 0.5) | Declared Physics General CN | Median Rel Error vs Clean | `0.714372 (61.834x clean)` | `0.0120 (1.04x clean)` | Error <= 2.0x clean | **MET** | Coverage: 86.0% [77.86, 91.47] |
| **D4** | S6 Sev 3 (Strong constant source s = 2.0) | Declared Physics General CN | Median Rel Error vs Clean | `0.99 (85.692x clean)` | `0.0094 (0.82x clean)` | Error <= 2.0x clean | **MET** | Coverage: 76.0% [66.77, 83.31] |
