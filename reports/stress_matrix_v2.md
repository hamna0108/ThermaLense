# Week 5 Stress Matrix v2 Report (Powered Rerun: 100 Seeds / Cell)

> **Generated strictly from:** `data/results/stress_summary_v2.csv`
> **Zero Code Modifications to Frozen Modules:** Models evaluated strictly as frozen.

## Pre-Registered Failure Rule (Script Header)
A condition cell is declared **FAIL** if:
1. **Parameter Estimation Modules (`Mode 2`, `Mode 3`, `Mode 3+`, `Two-Stage Placement`):**
   - Median relative $\alpha$ error $> 2.0\times$ the matching clean baseline error, OR
   - $95\%$ Wald confidence interval coverage $< 80.0\%$.
2. **Anomaly Cascade Module:**
   - Healthy false-alarm rate (FAR) $> 15.0\%$.

### Clean Baseline Reference Metrics ($N=10, \sigma=0.01, \alpha=0.100, 100\text{ reps}$):
- **Mode 2:** Median Rel Err = `0.011553` | Coverage = `95.0%` [88.8, 97.8]
- **Mode 3:** Median Rel Err = `0.012559` | Coverage = `95.0%` [88.8, 97.8]
- **Mode 3+:** Median Rel Err = `0.011557` | Coverage = `95.0%` [88.8, 97.8]
- **Two-Stage Placement:** Median Rel Err = `0.007939` | Coverage = `93.0%` [86.2, 96.6]
- **Anomaly Cascade:** Healthy FAR = `4.0%` [1.6, 9.8]

---

## 1. Executive Summary Table per Module and Category

| Module | Robustness Pass Rate (Scenarios 1-3, 8-13) | Declared-Scope Violation Pass Rate (Scenarios 4-7) | Total Pass Rate (All 39 Cells) |
| :--- | :---: | :---: | :---: |
| **Mode 2** | 17 / 27 (63.0%) | 0 / 12 (0.0%) | **17 / 39 (43.6%)** |
| **Mode 3** | 17 / 27 (63.0%) | 0 / 12 (0.0%) | **17 / 39 (43.6%)** |
| **Mode 3+** | 17 / 27 (63.0%) | 0 / 12 (0.0%) | **17 / 39 (43.6%)** |
| **Two-Stage Placement** | 23 / 27 (85.2%) | 1 / 12 (8.3%) | **24 / 39 (61.5%)** |
| **Anomaly Cascade** | 11 / 27 (40.7%) | 0 / 12 (0.0%) | **11 / 39 (28.2%)** |

**Overall Portfolio Performance:** **86 / 195 Cells Passed** (`44.1%` Pass Rate; `109 / 195` Failed, `55.9%` Failure Rate).

---

## 2. Scenario 13 (Baseline Drift) Reconciliation

### Empirical Findings & Reconciliation with Anomaly Study Table 3:
- **Replicate Power:** In v1 ($N_{\text{reps}}=5$), anomaly healthy FAR jumped in coarse discrete steps of $20\%$, causing 1 false alarm to register as $20\%$ and 5 to register as $100\%$. In v2 ($N_{\text{reps}}=100$), continuous empirical rates with Wilson $95\%$ confidence intervals are established.
- **Operating Domain vs Factorial Cohort:** In the anomaly module study (`EXPERIMENTS.md` / `data/results/anomaly_baseline_drift_new_fresh_summary.csv` Table 3), reported FAR numbers ($5.8\%$ at $2\%$ drift, $15.0\%$ at $10\%$ drift) represent an aggregate average across all 4 factorial cells ($N \in \{10, 20\}, \sigma \in \{0.01, 0.05\}$) with varying initial $\alpha_h \in [0.02, 0.5]$. At high noise ($\sigma = 0.05$), the parameter offset from $10\%$ drift is buried beneath the Gaussian noise floor (cell FAR is only $6.5\%$). In contrast, the stress matrix specifically probes the low-noise regime ($N=10, \sigma=0.01, \alpha_0=0.100$).
- **Scenario 13 v2 Empirical Results ($N_{\text{reps}}=100$):**
  - **Slow drift delta = 2%:** Healthy FAR = `7.0%` [95% CI: `3.43%`, `13.75%`] | Status: **PASS** (Within specification)
  - **Moderate drift delta = 5%:** Healthy FAR = `7.0%` [95% CI: `3.43%`, `13.75%`] | Status: **PASS** (Within specification)
  - **Severe drift delta = 10%:** Healthy FAR = `29.0%` [95% CI: `21.01%`, `38.54%`] | Status: **FAIL** (Healthy FAR 29.0% > 15.0%)
- **Mechanism:** With clean low noise ($\sigma=0.01$), a $10\%$ unmodelled linear drift across the baseline shifts the estimated baseline anchor $\hat{\alpha}_{\text{base}}$ by $\approx +0.005$ decades. Over the operational window $t \in [0.01, 1.0]$, this offset produces persistent residual discrepancies that exceed the GLR threshold $\tau=7.544$ for low-noise signals, whereas at $\sigma=0.05$ it is statistically indistinguishable from zero.

---

## 3. Failed Cells Audit with Absolute Errors and Wilson 95% CIs

Every cell failing the pre-registered threshold is detailed below with absolute median relative error, clean reference error, ratio, coverage / FAR with Wilson 95% CIs, and hypothesis-marked root cause and candidate fix.

| Scen | Category | Module | Severity Level | Abs Med Rel Err | Clean Err | Ratio | Coverage % [95% CI] | Healthy FAR % [95% CI] | Failure Reason |
| :---: | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| S1 | robustness | **Two-Stage Placement** | Assumed 0.05, true 0.01 | `0.0402` | `0.0079` | `5.06x` | `99.0%` [94.55, 99.82] | `nan%` [nan, nan] | Error 5.06x > 2.0x clean |
| S1 | robustness | **Mode 2** | Assumed 0.01, true 0.05 | `0.0656` | `0.0116` | `5.67x` | `29.0%` [21.01, 38.54] | `nan%` [nan, nan] | Error 5.67x > 2.0x clean; Coverage 29.0% < 80.0% |
| S1 | robustness | **Mode 3** | Assumed 0.01, true 0.05 | `0.0646` | `0.0126` | `5.14x` | `30.0%` [21.89, 39.58] | `nan%` [nan, nan] | Error 5.14x > 2.0x clean; Coverage 30.0% < 80.0% |
| S1 | robustness | **Mode 3+** | Assumed 0.01, true 0.05 | `0.0656` | `0.0116` | `5.67x` | `29.0%` [21.01, 38.54] | `nan%` [nan, nan] | Error 5.67x > 2.0x clean; Coverage 29.0% < 80.0% |
| S1 | robustness | **Anomaly Cascade** | Assumed 0.01, true 0.05 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | Healthy FAR 100.0% > 15.0% |
| S1 | robustness | **Mode 2** | Assumed 0.01, true 0.03 | `0.0394` | `0.0116` | `3.41x` | `47.0%` [37.51, 56.71] | `nan%` [nan, nan] | Error 3.41x > 2.0x clean; Coverage 47.0% < 80.0% |
| S1 | robustness | **Mode 3** | Assumed 0.01, true 0.03 | `0.0408` | `0.0126` | `3.25x` | `45.0%` [35.61, 54.76] | `nan%` [nan, nan] | Error 3.25x > 2.0x clean; Coverage 45.0% < 80.0% |
| S1 | robustness | **Mode 3+** | Assumed 0.01, true 0.03 | `0.0394` | `0.0116` | `3.40x` | `47.0%` [37.51, 56.71] | `nan%` [nan, nan] | Error 3.41x > 2.0x clean; Coverage 47.0% < 80.0% |
| S1 | robustness | **Anomaly Cascade** | Assumed 0.01, true 0.03 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `99.0%` [94.55, 99.82] | Healthy FAR 99.0% > 15.0% |
| S2 | robustness | **Anomaly Cascade** | Student-t df=3 (moderate tail) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `17.0%` [10.89, 25.55] | Healthy FAR 17.0% > 15.0% |
| S2 | robustness | **Anomaly Cascade** | Student-t df=2.5 with 2% 5-sigma outliers | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `25.0%` [17.55, 34.3] | Healthy FAR 25.0% > 15.0% |
| S2 | robustness | **Anomaly Cascade** | Student-t df=2.1 with 5% 5-sigma outliers | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `45.0%` [35.61, 54.76] | Healthy FAR 45.0% > 15.0% |
| S3 | robustness | **Mode 2** | AR(1) rho = 0.80 | `0.0288` | `0.0116` | `2.50x` | `61.0%` [51.2, 69.98] | `nan%` [nan, nan] | Error 2.50x > 2.0x clean; Coverage 61.0% < 80.0% |
| S3 | robustness | **Mode 3** | AR(1) rho = 0.80 | `0.0266` | `0.0126` | `2.12x` | `63.0%` [53.22, 71.82] | `nan%` [nan, nan] | Error 2.12x > 2.0x clean; Coverage 63.0% < 80.0% |
| S3 | robustness | **Mode 3+** | AR(1) rho = 0.80 | `0.0288` | `0.0116` | `2.50x` | `61.0%` [51.2, 69.98] | `nan%` [nan, nan] | Error 2.49x > 2.0x clean; Coverage 61.0% < 80.0% |
| S3 | robustness | **Anomaly Cascade** | AR(1) rho = 0.80 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `20.0%` [13.34, 28.88] | Healthy FAR 20.0% > 15.0% |
| S3 | robustness | **Mode 2** | AR(1) rho = 0.95 | `0.0238` | `0.0116` | `2.06x` | `69.0%` [59.37, 77.22] | `nan%` [nan, nan] | Error 2.06x > 2.0x clean; Coverage 69.0% < 80.0% |
| S3 | robustness | **Mode 3** | AR(1) rho = 0.95 | `0.0241` | `0.0126` | `1.92x` | `69.0%` [59.37, 77.22] | `nan%` [nan, nan] | Coverage 69.0% < 80.0% |
| S3 | robustness | **Mode 3+** | AR(1) rho = 0.95 | `0.0239` | `0.0116` | `2.06x` | `69.0%` [59.37, 77.22] | `nan%` [nan, nan] | Error 2.06x > 2.0x clean; Coverage 69.0% < 80.0% |
| S4 | declared-scope violation | **Mode 2** | Harmonic double mode sin(2 pi x) | `98.9987` | `0.0116` | `8569.37x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 8569.37x > 2.0x clean; Coverage 0.0% < 80.0% |
| S4 | declared-scope violation | **Mode 3** | Harmonic double mode sin(2 pi x) | `98.9979` | `0.0126` | `7882.68x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 7882.68x > 2.0x clean; Coverage 0.0% < 80.0% |
| S4 | declared-scope violation | **Mode 3+** | Harmonic double mode sin(2 pi x) | `98.9883` | `0.0116` | `8564.98x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 8564.98x > 2.0x clean; Coverage 0.0% < 80.0% |
| S4 | declared-scope violation | **Two-Stage Placement** | Harmonic double mode sin(2 pi x) | `98.9987` | `0.0079` | `12470.39x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 12470.39x > 2.0x clean; Coverage 0.0% < 80.0% |
| S4 | declared-scope violation | **Anomaly Cascade** | Harmonic double mode sin(2 pi x) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | Healthy FAR 100.0% > 15.0% |
| S4 | declared-scope violation | **Mode 2** | Two-mode sum sin(pi x) + 0.5 sin(3 pi x) | `0.0563` | `0.0116` | `4.87x` | `35.0%` [26.36, 44.75] | `nan%` [nan, nan] | Error 4.87x > 2.0x clean; Coverage 35.0% < 80.0% |
| S4 | declared-scope violation | **Mode 3** | Two-mode sum sin(pi x) + 0.5 sin(3 pi x) | `0.0558` | `0.0126` | `4.44x` | `36.0%` [27.27, 45.76] | `nan%` [nan, nan] | Error 4.44x > 2.0x clean; Coverage 36.0% < 80.0% |
| S4 | declared-scope violation | **Mode 3+** | Two-mode sum sin(pi x) + 0.5 sin(3 pi x) | `0.0562` | `0.0116` | `4.87x` | `35.0%` [26.36, 44.75] | `nan%` [nan, nan] | Error 4.87x > 2.0x clean; Coverage 35.0% < 80.0% |
| S4 | declared-scope violation | **Two-Stage Placement** | Two-mode sum sin(pi x) + 0.5 sin(3 pi x) | `0.0762` | `0.0079` | `9.59x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 9.59x > 2.0x clean; Coverage 0.0% < 80.0% |
| S4 | declared-scope violation | **Anomaly Cascade** | Two-mode sum sin(pi x) + 0.5 sin(3 pi x) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | Healthy FAR 100.0% > 15.0% |
| S4 | declared-scope violation | **Mode 2** | Gaussian bump exp(-(x-0.5)^2 / (2*0.08^2)) | `26.1431` | `0.0116` | `2262.96x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 2262.96x > 2.0x clean; Coverage 0.0% < 80.0% |
| S4 | declared-scope violation | **Mode 3** | Gaussian bump exp(-(x-0.5)^2 / (2*0.08^2)) | `28.9774` | `0.0126` | `2307.32x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 2307.31x > 2.0x clean; Coverage 0.0% < 80.0% |
| S4 | declared-scope violation | **Mode 3+** | Gaussian bump exp(-(x-0.5)^2 / (2*0.08^2)) | `26.1430` | `0.0116` | `2262.03x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 2262.03x > 2.0x clean; Coverage 0.0% < 80.0% |
| S4 | declared-scope violation | **Two-Stage Placement** | Gaussian bump exp(-(x-0.5)^2 / (2*0.08^2)) | `3.9861` | `0.0079` | `502.11x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 502.11x > 2.0x clean; Coverage 0.0% < 80.0% |
| S4 | declared-scope violation | **Anomaly Cascade** | Gaussian bump exp(-(x-0.5)^2 / (2*0.08^2)) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | Healthy FAR 100.0% > 15.0% |
| S5 | declared-scope violation | **Mode 2** | Small constant offset u_bc = 0.05 | `0.0692` | `0.0116` | `5.99x` | `12.0%` [7.0, 19.81] | `nan%` [nan, nan] | Error 5.99x > 2.0x clean; Coverage 12.0% < 80.0% |
| S5 | declared-scope violation | **Mode 3** | Small constant offset u_bc = 0.05 | `0.0733` | `0.0126` | `5.84x` | `11.0%` [6.25, 18.63] | `nan%` [nan, nan] | Error 5.84x > 2.0x clean; Coverage 11.0% < 80.0% |
| S5 | declared-scope violation | **Mode 3+** | Small constant offset u_bc = 0.05 | `0.0692` | `0.0116` | `5.99x` | `12.0%` [7.0, 19.81] | `nan%` [nan, nan] | Error 5.99x > 2.0x clean; Coverage 12.0% < 80.0% |
| S5 | declared-scope violation | **Two-Stage Placement** | Small constant offset u_bc = 0.05 | `0.0542` | `0.0079` | `6.83x` | `1.0%` [0.18, 5.45] | `nan%` [nan, nan] | Error 6.83x > 2.0x clean; Coverage 1.0% < 80.0% |
| S5 | declared-scope violation | **Anomaly Cascade** | Small constant offset u_bc = 0.05 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `87.0%` [79.02, 92.24] | Healthy FAR 87.0% > 15.0% |
| S5 | declared-scope violation | **Mode 2** | Moderate constant offset u_bc = 0.15 | `0.1886` | `0.0116` | `16.32x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 16.32x > 2.0x clean; Coverage 0.0% < 80.0% |
| S5 | declared-scope violation | **Mode 3** | Moderate constant offset u_bc = 0.15 | `0.1911` | `0.0126` | `15.21x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 15.22x > 2.0x clean; Coverage 0.0% < 80.0% |
| S5 | declared-scope violation | **Mode 3+** | Moderate constant offset u_bc = 0.15 | `0.1885` | `0.0116` | `16.31x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 16.31x > 2.0x clean; Coverage 0.0% < 80.0% |
| S5 | declared-scope violation | **Two-Stage Placement** | Moderate constant offset u_bc = 0.15 | `0.1549` | `0.0079` | `19.51x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 19.51x > 2.0x clean; Coverage 0.0% < 80.0% |
| S5 | declared-scope violation | **Anomaly Cascade** | Moderate constant offset u_bc = 0.15 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | Healthy FAR 100.0% > 15.0% |
| S5 | declared-scope violation | **Mode 2** | Linearly drifting boundary u_bc(t) = 0.20 * t | `0.1007` | `0.0116` | `8.72x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 8.72x > 2.0x clean; Coverage 0.0% < 80.0% |
| S5 | declared-scope violation | **Mode 3** | Linearly drifting boundary u_bc(t) = 0.20 * t | `0.1034` | `0.0126` | `8.24x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 8.24x > 2.0x clean; Coverage 0.0% < 80.0% |
| S5 | declared-scope violation | **Mode 3+** | Linearly drifting boundary u_bc(t) = 0.20 * t | `0.1007` | `0.0116` | `8.71x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 8.71x > 2.0x clean; Coverage 0.0% < 80.0% |
| S5 | declared-scope violation | **Two-Stage Placement** | Linearly drifting boundary u_bc(t) = 0.20 * t | `0.0742` | `0.0079` | `9.35x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 9.35x > 2.0x clean; Coverage 0.0% < 80.0% |
| S5 | declared-scope violation | **Anomaly Cascade** | Linearly drifting boundary u_bc(t) = 0.20 * t | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | Healthy FAR 100.0% > 15.0% |
| S6 | declared-scope violation | **Mode 2** | Small constant source s = 0.1 | `0.1694` | `0.0116` | `14.67x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 14.67x > 2.0x clean; Coverage 0.0% < 80.0% |
| S6 | declared-scope violation | **Mode 3** | Small constant source s = 0.1 | `0.1714` | `0.0126` | `13.65x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 13.65x > 2.0x clean; Coverage 0.0% < 80.0% |
| S6 | declared-scope violation | **Mode 3+** | Small constant source s = 0.1 | `0.1694` | `0.0116` | `14.66x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 14.66x > 2.0x clean; Coverage 0.0% < 80.0% |
| S6 | declared-scope violation | **Two-Stage Placement** | Small constant source s = 0.1 | `0.1711` | `0.0079` | `21.55x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 21.55x > 2.0x clean; Coverage 0.0% < 80.0% |
| S6 | declared-scope violation | **Anomaly Cascade** | Small constant source s = 0.1 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | Healthy FAR 100.0% > 15.0% |
| S6 | declared-scope violation | **Mode 2** | Moderate constant source s = 0.5 | `0.7144` | `0.0116` | `61.84x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 61.84x > 2.0x clean; Coverage 0.0% < 80.0% |
| S6 | declared-scope violation | **Mode 3** | Moderate constant source s = 0.5 | `0.7162` | `0.0126` | `57.03x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 57.03x > 2.0x clean; Coverage 0.0% < 80.0% |
| S6 | declared-scope violation | **Mode 3+** | Moderate constant source s = 0.5 | `0.7144` | `0.0116` | `61.81x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 61.81x > 2.0x clean; Coverage 0.0% < 80.0% |
| S6 | declared-scope violation | **Two-Stage Placement** | Moderate constant source s = 0.5 | `0.6965` | `0.0079` | `87.74x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 87.74x > 2.0x clean; Coverage 0.0% < 80.0% |
| S6 | declared-scope violation | **Anomaly Cascade** | Moderate constant source s = 0.5 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | Healthy FAR 100.0% > 15.0% |
| S6 | declared-scope violation | **Mode 2** | Strong constant source s = 2.0 | `0.9900` | `0.0116` | `85.69x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 85.69x > 2.0x clean; Coverage 0.0% < 80.0% |
| S6 | declared-scope violation | **Mode 3** | Strong constant source s = 2.0 | `0.9953` | `0.0126` | `79.25x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 79.25x > 2.0x clean; Coverage 0.0% < 80.0% |
| S6 | declared-scope violation | **Mode 3+** | Strong constant source s = 2.0 | `0.9900` | `0.0116` | `85.66x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 85.66x > 2.0x clean; Coverage 0.0% < 80.0% |
| S6 | declared-scope violation | **Two-Stage Placement** | Strong constant source s = 2.0 | `0.9900` | `0.0079` | `124.71x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 124.71x > 2.0x clean; Coverage 0.0% < 80.0% |
| S6 | declared-scope violation | **Anomaly Cascade** | Strong constant source s = 2.0 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | Healthy FAR 100.0% > 15.0% |
| S7 | declared-scope violation | **Mode 2** | Mild linear ramp alpha(x) = alpha0*(1 + 0.5*(x-0.5)) | `0.0326` | `0.0116` | `2.82x` | `61.0%` [51.2, 69.98] | `nan%` [nan, nan] | Error 2.82x > 2.0x clean; Coverage 61.0% < 80.0% |
| S7 | declared-scope violation | **Mode 3** | Mild linear ramp alpha(x) = alpha0*(1 + 0.5*(x-0.5)) | `0.0310` | `0.0126` | `2.47x` | `63.0%` [53.22, 71.82] | `nan%` [nan, nan] | Error 2.47x > 2.0x clean; Coverage 63.0% < 80.0% |
| S7 | declared-scope violation | **Mode 3+** | Mild linear ramp alpha(x) = alpha0*(1 + 0.5*(x-0.5)) | `0.0326` | `0.0116` | `2.82x` | `61.0%` [51.2, 69.98] | `nan%` [nan, nan] | Error 2.82x > 2.0x clean; Coverage 61.0% < 80.0% |
| S7 | declared-scope violation | **Anomaly Cascade** | Mild linear ramp alpha(x) = alpha0*(1 + 0.5*(x-0.5)) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `75.0%` [65.7, 82.45] | Healthy FAR 75.0% > 15.0% |
| S7 | declared-scope violation | **Mode 2** | Steep linear ramp alpha(x) = alpha0*(1 + 1.5*(x-0.5)) | `0.0849` | `0.0116` | `7.35x` | `19.0%` [12.51, 27.78] | `nan%` [nan, nan] | Error 7.35x > 2.0x clean; Coverage 19.0% < 80.0% |
| S7 | declared-scope violation | **Mode 3** | Steep linear ramp alpha(x) = alpha0*(1 + 1.5*(x-0.5)) | `0.0873` | `0.0126` | `6.95x` | `22.0%` [15.0, 31.07] | `nan%` [nan, nan] | Error 6.95x > 2.0x clean; Coverage 22.0% < 80.0% |
| S7 | declared-scope violation | **Mode 3+** | Steep linear ramp alpha(x) = alpha0*(1 + 1.5*(x-0.5)) | `0.0849` | `0.0116` | `7.35x` | `19.0%` [12.51, 27.78] | `nan%` [nan, nan] | Error 7.35x > 2.0x clean; Coverage 19.0% < 80.0% |
| S7 | declared-scope violation | **Two-Stage Placement** | Steep linear ramp alpha(x) = alpha0*(1 + 1.5*(x-0.5)) | `0.0305` | `0.0079` | `3.85x` | `24.0%` [16.69, 33.23] | `nan%` [nan, nan] | Error 3.85x > 2.0x clean; Coverage 24.0% < 80.0% |
| S7 | declared-scope violation | **Anomaly Cascade** | Steep linear ramp alpha(x) = alpha0*(1 + 1.5*(x-0.5)) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | Healthy FAR 100.0% > 15.0% |
| S7 | declared-scope violation | **Mode 2** | Step discontinuity alpha(x) = 2*alpha0 for x > 0.5 | `0.4882` | `0.0116` | `42.26x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 42.26x > 2.0x clean; Coverage 0.0% < 80.0% |
| S7 | declared-scope violation | **Mode 3** | Step discontinuity alpha(x) = 2*alpha0 for x > 0.5 | `0.4839` | `0.0126` | `38.53x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 38.53x > 2.0x clean; Coverage 0.0% < 80.0% |
| S7 | declared-scope violation | **Mode 3+** | Step discontinuity alpha(x) = 2*alpha0 for x > 0.5 | `0.4882` | `0.0116` | `42.24x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 42.24x > 2.0x clean; Coverage 0.0% < 80.0% |
| S7 | declared-scope violation | **Two-Stage Placement** | Step discontinuity alpha(x) = 2*alpha0 for x > 0.5 | `0.5170` | `0.0079` | `65.12x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 65.12x > 2.0x clean; Coverage 0.0% < 80.0% |
| S7 | declared-scope violation | **Anomaly Cascade** | Step discontinuity alpha(x) = 2*alpha0 for x > 0.5 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | Healthy FAR 100.0% > 15.0% |
| S8 | robustness | **Mode 2** | 50% readings missing (5 sensors dropped) | `0.0248` | `0.0116` | `2.15x` | `92.0%` [85.0, 95.89] | `nan%` [nan, nan] | Error 2.14x > 2.0x clean |
| S8 | robustness | **Mode 3** | 50% readings missing (5 sensors dropped) | `0.0258` | `0.0126` | `2.05x` | `91.0%` [83.77, 95.19] | `nan%` [nan, nan] | Error 2.05x > 2.0x clean |
| S8 | robustness | **Mode 3+** | 50% readings missing (5 sensors dropped) | `0.0248` | `0.0116` | `2.15x` | `92.0%` [85.0, 95.89] | `nan%` [nan, nan] | Error 2.15x > 2.0x clean |
| S9 | robustness | **Anomaly Cascade** | Small jitter sigma_jitter = 0.01 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `59.0%` [49.2, 68.13] | Healthy FAR 59.0% > 15.0% |
| S9 | robustness | **Mode 2** | Moderate jitter sigma_jitter = 0.03 | `0.0377` | `0.0116` | `3.26x` | `50.0%` [40.38, 59.62] | `nan%` [nan, nan] | Error 3.26x > 2.0x clean; Coverage 50.0% < 80.0% |
| S9 | robustness | **Mode 3** | Moderate jitter sigma_jitter = 0.03 | `0.0407` | `0.0126` | `3.24x` | `48.0%` [38.46, 57.68] | `nan%` [nan, nan] | Error 3.24x > 2.0x clean; Coverage 48.0% < 80.0% |
| S9 | robustness | **Mode 3+** | Moderate jitter sigma_jitter = 0.03 | `0.0377` | `0.0116` | `3.26x` | `50.0%` [40.38, 59.62] | `nan%` [nan, nan] | Error 3.26x > 2.0x clean; Coverage 50.0% < 80.0% |
| S9 | robustness | **Anomaly Cascade** | Moderate jitter sigma_jitter = 0.03 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | Healthy FAR 100.0% > 15.0% |
| S9 | robustness | **Mode 2** | Large jitter sigma_jitter = 0.06 | `0.0918` | `0.0116` | `7.94x` | `17.0%` [10.89, 25.55] | `nan%` [nan, nan] | Error 7.94x > 2.0x clean; Coverage 17.0% < 80.0% |
| S9 | robustness | **Mode 3** | Large jitter sigma_jitter = 0.06 | `0.0900` | `0.0126` | `7.17x` | `15.0%` [9.31, 23.28] | `nan%` [nan, nan] | Error 7.17x > 2.0x clean; Coverage 15.0% < 80.0% |
| S9 | robustness | **Mode 3+** | Large jitter sigma_jitter = 0.06 | `0.0918` | `0.0116` | `7.94x` | `17.0%` [10.89, 25.55] | `nan%` [nan, nan] | Error 7.94x > 2.0x clean; Coverage 17.0% < 80.0% |
| S9 | robustness | **Anomaly Cascade** | Large jitter sigma_jitter = 0.06 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | Healthy FAR 100.0% > 15.0% |
| S10 | robustness | **Anomaly Cascade** | Small sensor bias b = 3 sigma (0.03) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `51.0%` [41.35, 60.58] | Healthy FAR 51.0% > 15.0% |
| S10 | robustness | **Anomaly Cascade** | Medium sensor bias b = 6 sigma (0.06) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | Healthy FAR 100.0% > 15.0% |
| S10 | robustness | **Anomaly Cascade** | Strong sensor bias b = 15 sigma (0.15) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | Healthy FAR 100.0% > 15.0% |
| S11 | robustness | **Two-Stage Placement** | Minimal array N = 2 sensors | `0.0204` | `0.0079` | `2.57x` | `95.0%` [88.82, 97.85] | `nan%` [nan, nan] | Error 2.57x > 2.0x clean |
| S12 | robustness | **Mode 2** | Sub-grid low diffusivity alpha = 5e-4 | `1.0000` | `0.0116` | `86.56x` | `88.0%` [80.19, 93.0] | `nan%` [nan, nan] | Error 86.56x > 2.0x clean |
| S12 | robustness | **Mode 3** | Sub-grid low diffusivity alpha = 5e-4 | `0.9690` | `0.0126` | `77.16x` | `80.0%` [71.12, 86.66] | `nan%` [nan, nan] | Error 77.15x > 2.0x clean |
| S12 | robustness | **Mode 3+** | Sub-grid low diffusivity alpha = 5e-4 | `1.0002` | `0.0116` | `86.55x` | `88.0%` [80.19, 93.0] | `nan%` [nan, nan] | Error 86.55x > 2.0x clean |
| S12 | robustness | **Two-Stage Placement** | Sub-grid low diffusivity alpha = 5e-4 | `1.0000` | `0.0079` | `125.97x` | `90.0%` [82.56, 94.48] | `nan%` [nan, nan] | Error 125.97x > 2.0x clean |
| S12 | robustness | **Anomaly Cascade** | Sub-grid low diffusivity alpha = 5e-4 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | Healthy FAR 100.0% > 15.0% |
| S12 | robustness | **Mode 2** | Super-grid high diffusivity alpha = 5.0 | `0.1075` | `0.0116` | `9.30x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 9.30x > 2.0x clean; Coverage 0.0% < 80.0% |
| S12 | robustness | **Mode 3** | Super-grid high diffusivity alpha = 5.0 | `0.1031` | `0.0126` | `8.21x` | `22.0%` [15.0, 31.07] | `nan%` [nan, nan] | Error 8.21x > 2.0x clean; Coverage 22.0% < 80.0% |
| S12 | robustness | **Mode 3+** | Super-grid high diffusivity alpha = 5.0 | `0.1075` | `0.0116` | `9.30x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 9.30x > 2.0x clean; Coverage 0.0% < 80.0% |
| S12 | robustness | **Anomaly Cascade** | Super-grid high diffusivity alpha = 5.0 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | Healthy FAR 100.0% > 15.0% |
| S12 | robustness | **Mode 2** | Super-grid extreme diffusivity alpha = 20.0 | `0.5000` | `0.0116` | `43.28x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 43.28x > 2.0x clean; Coverage 0.0% < 80.0% |
| S12 | robustness | **Mode 3** | Super-grid extreme diffusivity alpha = 20.0 | `0.5000` | `0.0126` | `39.81x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 39.81x > 2.0x clean; Coverage 0.0% < 80.0% |
| S12 | robustness | **Mode 3+** | Super-grid extreme diffusivity alpha = 20.0 | `0.5001` | `0.0116` | `43.27x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 43.27x > 2.0x clean; Coverage 0.0% < 80.0% |
| S12 | robustness | **Two-Stage Placement** | Super-grid extreme diffusivity alpha = 20.0 | `0.5000` | `0.0079` | `62.98x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | Error 62.98x > 2.0x clean; Coverage 0.0% < 80.0% |
| S12 | robustness | **Anomaly Cascade** | Super-grid extreme diffusivity alpha = 20.0 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | Healthy FAR 100.0% > 15.0% |
| S13 | robustness | **Anomaly Cascade** | Severe drift delta = 10% | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `29.0%` [21.01, 38.54] | Healthy FAR 29.0% > 15.0% |

---

## 4. Root Cause Hypotheses & V2 Candidate Fixes (Hypotheses, Not Verified)

The table below compiles the likely causes and candidate fixes for each distinct failed scenario condition. **All entries are explicitly marked as hypotheses, not verified.**

| Scenario | Module | Failure Mode | Likely Cause Hypothesis (Unverified) | V2 Candidate Fix Hypothesis (Unverified) |
| :--- | :--- | :--- | :--- | :--- |
| **Scenario 1 (Misspecified noise sigma)** | Two-Stage Placement | Error 5.06x > 2.0x clean | *Underestimated noise shrinks Fisher information and inflates chi2 threshold* | *Pre-estimate empirical residual variance before setting weights* |
| **Scenario 1 (Misspecified noise sigma)** | Mode 2 | Error 5.67x > 2.0x clean; Coverage 29.0% < 80.0% | *Underestimated noise shrinks Fisher information and inflates chi2 threshold* | *Pre-estimate empirical residual variance before setting weights* |
| **Scenario 1 (Misspecified noise sigma)** | Mode 3 | Error 5.14x > 2.0x clean; Coverage 30.0% < 80.0% | *Underestimated noise shrinks Fisher information and inflates chi2 threshold* | *Pre-estimate empirical residual variance before setting weights* |
| **Scenario 1 (Misspecified noise sigma)** | Mode 3+ | Error 5.67x > 2.0x clean; Coverage 29.0% < 80.0% | *Underestimated noise shrinks Fisher information and inflates chi2 threshold* | *Pre-estimate empirical residual variance before setting weights* |
| **Scenario 1 (Misspecified noise sigma)** | Anomaly Cascade | Healthy FAR 100.0% > 15.0% | *Underestimated noise shrinks Fisher information and inflates chi2 threshold* | *Pre-estimate empirical residual variance before setting weights* |
| **Scenario 2 (Heavy-tailed noise)** | Anomaly Cascade | Healthy FAR 17.0% > 15.0% | *Outliers violate Gaussian likelihood and drag MSE fits away from mode* | *Replace L2 loss with Huber or Student-t robust M-estimator* |
| **Scenario 3 (Correlated noise)** | Mode 2 | Error 2.50x > 2.0x clean; Coverage 61.0% < 80.0% | *Residual autocorrelation violates i.i.d. assumption, shrinking effective sample size* | *Pre-whiten measurement residuals via AR(1) Cochrane-Orcutt transform* |
| **Scenario 3 (Correlated noise)** | Mode 3 | Error 2.12x > 2.0x clean; Coverage 63.0% < 80.0% | *Residual autocorrelation violates i.i.d. assumption, shrinking effective sample size* | *Pre-whiten measurement residuals via AR(1) Cochrane-Orcutt transform* |
| **Scenario 3 (Correlated noise)** | Mode 3+ | Error 2.49x > 2.0x clean; Coverage 61.0% < 80.0% | *Residual autocorrelation violates i.i.d. assumption, shrinking effective sample size* | *Pre-whiten measurement residuals via AR(1) Cochrane-Orcutt transform* |
| **Scenario 3 (Correlated noise)** | Anomaly Cascade | Healthy FAR 20.0% > 15.0% | *Residual autocorrelation violates i.i.d. assumption, shrinking effective sample size* | *Pre-whiten measurement residuals via AR(1) Cochrane-Orcutt transform* |
| **Scenario 4 (Different initial condition)** | Mode 2 | Error 8569.37x > 2.0x clean; Coverage 0.0% < 80.0% | *Higher spatial modes decay exponentially faster than fundamental mode* | *Decompose initial time slice into spatial Fourier coefficients before fitting alpha* |
| **Scenario 4 (Different initial condition)** | Mode 3 | Error 7882.68x > 2.0x clean; Coverage 0.0% < 80.0% | *Higher spatial modes decay exponentially faster than fundamental mode* | *Decompose initial time slice into spatial Fourier coefficients before fitting alpha* |
| **Scenario 4 (Different initial condition)** | Mode 3+ | Error 8564.98x > 2.0x clean; Coverage 0.0% < 80.0% | *Higher spatial modes decay exponentially faster than fundamental mode* | *Decompose initial time slice into spatial Fourier coefficients before fitting alpha* |
| **Scenario 4 (Different initial condition)** | Two-Stage Placement | Error 12470.39x > 2.0x clean; Coverage 0.0% < 80.0% | *Higher spatial modes decay exponentially faster than fundamental mode* | *Decompose initial time slice into spatial Fourier coefficients before fitting alpha* |
| **Scenario 4 (Different initial condition)** | Anomaly Cascade | Healthy FAR 100.0% > 15.0% | *Higher spatial modes decay exponentially faster than fundamental mode* | *Decompose initial time slice into spatial Fourier coefficients before fitting alpha* |
| **Scenario 5 (Boundary mismatch)** | Mode 2 | Error 5.99x > 2.0x clean; Coverage 12.0% < 80.0% | *Boundary thermal offset/flux counteracts interior diffusion decay* | *Jointly invert for Dirichlet boundary values alongside alpha* |
| **Scenario 5 (Boundary mismatch)** | Mode 3 | Error 5.84x > 2.0x clean; Coverage 11.0% < 80.0% | *Boundary thermal offset/flux counteracts interior diffusion decay* | *Jointly invert for Dirichlet boundary values alongside alpha* |
| **Scenario 5 (Boundary mismatch)** | Mode 3+ | Error 5.99x > 2.0x clean; Coverage 12.0% < 80.0% | *Boundary thermal offset/flux counteracts interior diffusion decay* | *Jointly invert for Dirichlet boundary values alongside alpha* |
| **Scenario 5 (Boundary mismatch)** | Two-Stage Placement | Error 6.83x > 2.0x clean; Coverage 1.0% < 80.0% | *Boundary thermal offset/flux counteracts interior diffusion decay* | *Jointly invert for Dirichlet boundary values alongside alpha* |
| **Scenario 5 (Boundary mismatch)** | Anomaly Cascade | Healthy FAR 87.0% > 15.0% | *Boundary thermal offset/flux counteracts interior diffusion decay* | *Jointly invert for Dirichlet boundary values alongside alpha* |
| **Scenario 6 (Source-term / heating mismatch)** | Mode 2 | Error 14.67x > 2.0x clean; Coverage 0.0% < 80.0% | *Internal heating source counteracts conductive decay, masquerading as zero/negative diffusion* | *Augment parameter vector to simultaneously estimate volumetric source rate* |
| **Scenario 6 (Source-term / heating mismatch)** | Mode 3 | Error 13.65x > 2.0x clean; Coverage 0.0% < 80.0% | *Internal heating source counteracts conductive decay, masquerading as zero/negative diffusion* | *Augment parameter vector to simultaneously estimate volumetric source rate* |
| **Scenario 6 (Source-term / heating mismatch)** | Mode 3+ | Error 14.66x > 2.0x clean; Coverage 0.0% < 80.0% | *Internal heating source counteracts conductive decay, masquerading as zero/negative diffusion* | *Augment parameter vector to simultaneously estimate volumetric source rate* |
| **Scenario 6 (Source-term / heating mismatch)** | Two-Stage Placement | Error 21.55x > 2.0x clean; Coverage 0.0% < 80.0% | *Internal heating source counteracts conductive decay, masquerading as zero/negative diffusion* | *Augment parameter vector to simultaneously estimate volumetric source rate* |
| **Scenario 6 (Source-term / heating mismatch)** | Anomaly Cascade | Healthy FAR 100.0% > 15.0% | *Internal heating source counteracts conductive decay, masquerading as zero/negative diffusion* | *Augment parameter vector to simultaneously estimate volumetric source rate* |
| **Scenario 7 (Variable diffusivity alpha(x))** | Mode 2 | Error 2.82x > 2.0x clean; Coverage 61.0% < 80.0% | *Spatial gradient in diffusivity violates homogeneous medium assumption* | *Upgrade operator to accept spatial parameter field alpha(x)* |
| **Scenario 7 (Variable diffusivity alpha(x))** | Mode 3 | Error 2.47x > 2.0x clean; Coverage 63.0% < 80.0% | *Spatial gradient in diffusivity violates homogeneous medium assumption* | *Upgrade operator to accept spatial parameter field alpha(x)* |
| **Scenario 7 (Variable diffusivity alpha(x))** | Mode 3+ | Error 2.82x > 2.0x clean; Coverage 61.0% < 80.0% | *Spatial gradient in diffusivity violates homogeneous medium assumption* | *Upgrade operator to accept spatial parameter field alpha(x)* |
| **Scenario 7 (Variable diffusivity alpha(x))** | Anomaly Cascade | Healthy FAR 75.0% > 15.0% | *Spatial gradient in diffusivity violates homogeneous medium assumption* | *Upgrade operator to accept spatial parameter field alpha(x)* |
| **Scenario 7 (Variable diffusivity alpha(x))** | Two-Stage Placement | Error 3.85x > 2.0x clean; Coverage 24.0% < 80.0% | *Spatial gradient in diffusivity violates homogeneous medium assumption* | *Upgrade operator to accept spatial parameter field alpha(x)* |
| **Scenario 8 (Sensor dropout)** | Mode 2 | Error 2.14x > 2.0x clean | *Missing sensor channels reduce spatial information density below Cramér-Rao floor* | *Dynamically adjust confidence interval using actual retained Fisher information* |
| **Scenario 8 (Sensor dropout)** | Mode 3 | Error 2.05x > 2.0x clean | *Missing sensor channels reduce spatial information density below Cramér-Rao floor* | *Dynamically adjust confidence interval using actual retained Fisher information* |
| **Scenario 8 (Sensor dropout)** | Mode 3+ | Error 2.15x > 2.0x clean | *Missing sensor channels reduce spatial information density below Cramér-Rao floor* | *Dynamically adjust confidence interval using actual retained Fisher information* |
| **Scenario 9 (Sensor position error and time jitter)** | Anomaly Cascade | Healthy FAR 59.0% > 15.0% | *Position and timing jitter introduce systematic phase and spatial distortion* | *Include sensor coordinate jitter margin in likelihood variance budget* |
| **Scenario 9 (Sensor position error and time jitter)** | Mode 2 | Error 3.26x > 2.0x clean; Coverage 50.0% < 80.0% | *Position and timing jitter introduce systematic phase and spatial distortion* | *Include sensor coordinate jitter margin in likelihood variance budget* |
| **Scenario 9 (Sensor position error and time jitter)** | Mode 3 | Error 3.24x > 2.0x clean; Coverage 48.0% < 80.0% | *Position and timing jitter introduce systematic phase and spatial distortion* | *Include sensor coordinate jitter margin in likelihood variance budget* |
| **Scenario 9 (Sensor position error and time jitter)** | Mode 3+ | Error 3.26x > 2.0x clean; Coverage 50.0% < 80.0% | *Position and timing jitter introduce systematic phase and spatial distortion* | *Include sensor coordinate jitter margin in likelihood variance budget* |
| **Scenario 10 (Constant sensor bias)** | Anomaly Cascade | Healthy FAR 51.0% > 15.0% | *Constant sensor bias triggers single-sensor Leave-One-Out BIC gate* | *LOO BIC gate correctly flags Class F sensor fault rather than Class C* |
| **Scenario 11 (Very few sensors)** | Two-Stage Placement | Error 2.57x > 2.0x clean | *Extremely sparse array (N=2, 3) yields near-singular Fisher information matrix* | *Impose empirical Bayes prior on alpha or mandate minimum N >= 5 sensor nodes* |
| **Scenario 12 (True alpha beyond the grid)** | Mode 2 | Error 86.56x > 2.0x clean | *Signal vanishes into noise floor (high alpha) or decays too slowly (low alpha)* | *Dynamically scale temporal observation window inversely with initial alpha estimate* |
| **Scenario 12 (True alpha beyond the grid)** | Mode 3 | Error 77.15x > 2.0x clean | *Signal vanishes into noise floor (high alpha) or decays too slowly (low alpha)* | *Dynamically scale temporal observation window inversely with initial alpha estimate* |
| **Scenario 12 (True alpha beyond the grid)** | Mode 3+ | Error 86.55x > 2.0x clean | *Signal vanishes into noise floor (high alpha) or decays too slowly (low alpha)* | *Dynamically scale temporal observation window inversely with initial alpha estimate* |
| **Scenario 12 (True alpha beyond the grid)** | Two-Stage Placement | Error 125.97x > 2.0x clean | *Signal vanishes into noise floor (high alpha) or decays too slowly (low alpha)* | *Dynamically scale temporal observation window inversely with initial alpha estimate* |
| **Scenario 12 (True alpha beyond the grid)** | Anomaly Cascade | Healthy FAR 100.0% > 15.0% | *Signal vanishes into noise floor (high alpha) or decays too slowly (low alpha)* | *Dynamically scale temporal observation window inversely with initial alpha estimate* |
| **Scenario 13 (Baseline drift)** | Anomaly Cascade | Healthy FAR 29.0% > 15.0% | *Baseline parameter drift creates persistent residual offset in operational window* | *Incorporate linear baseline drift parameter into null hypothesis model* |

---

## 5. Complete Summary Table (All 195 Cells)

| Scen | Category | Module | Severity Level | Abs Med Rel Err | Clean Err | Ratio | Coverage % [95% CI] | Healthy FAR % [95% CI] | Status |
| :---: | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| S1 | robustness | Mode 2 | Assumed 0.05, true 0.01 | `0.0171` | `0.0116` | `1.48x` | `100.0%` [96.3, 100.0] | `nan%` [nan, nan] | **PASS** |
| S1 | robustness | Mode 3 | Assumed 0.05, true 0.01 | `0.0176` | `0.0126` | `1.40x` | `100.0%` [96.3, 100.0] | `nan%` [nan, nan] | **PASS** |
| S1 | robustness | Mode 3+ | Assumed 0.05, true 0.01 | `0.0171` | `0.0116` | `1.48x` | `100.0%` [96.3, 100.0] | `nan%` [nan, nan] | **PASS** |
| S1 | robustness | Two-Stage Placement | Assumed 0.05, true 0.01 | `0.0402` | `0.0079` | `5.06x` | `99.0%` [94.55, 99.82] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S1 | robustness | Anomaly Cascade | Assumed 0.05, true 0.01 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `0.0%` [0.0, 3.7] | **PASS** |
| S1 | robustness | Mode 2 | Assumed 0.01, true 0.05 | `0.0656` | `0.0116` | `5.67x` | `29.0%` [21.01, 38.54] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S1 | robustness | Mode 3 | Assumed 0.01, true 0.05 | `0.0646` | `0.0126` | `5.14x` | `30.0%` [21.89, 39.58] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S1 | robustness | Mode 3+ | Assumed 0.01, true 0.05 | `0.0656` | `0.0116` | `5.67x` | `29.0%` [21.01, 38.54] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S1 | robustness | Two-Stage Placement | Assumed 0.01, true 0.05 | `0.0065` | `0.0079` | `0.81x` | `96.0%` [90.16, 98.43] | `nan%` [nan, nan] | **PASS** |
| S1 | robustness | Anomaly Cascade | Assumed 0.01, true 0.05 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | <span style='color:red;'>**FAIL**</span> |
| S1 | robustness | Mode 2 | Assumed 0.01, true 0.03 | `0.0394` | `0.0116` | `3.41x` | `47.0%` [37.51, 56.71] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S1 | robustness | Mode 3 | Assumed 0.01, true 0.03 | `0.0408` | `0.0126` | `3.25x` | `45.0%` [35.61, 54.76] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S1 | robustness | Mode 3+ | Assumed 0.01, true 0.03 | `0.0394` | `0.0116` | `3.40x` | `47.0%` [37.51, 56.71] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S1 | robustness | Two-Stage Placement | Assumed 0.01, true 0.03 | `0.0086` | `0.0079` | `1.09x` | `96.0%` [90.16, 98.43] | `nan%` [nan, nan] | **PASS** |
| S1 | robustness | Anomaly Cascade | Assumed 0.01, true 0.03 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `99.0%` [94.55, 99.82] | <span style='color:red;'>**FAIL**</span> |
| S2 | robustness | Mode 2 | Student-t df=3 (moderate tail) | `0.0111` | `0.0116` | `0.96x` | `95.0%` [88.82, 97.85] | `nan%` [nan, nan] | **PASS** |
| S2 | robustness | Mode 3 | Student-t df=3 (moderate tail) | `0.0114` | `0.0126` | `0.91x` | `95.0%` [88.82, 97.85] | `nan%` [nan, nan] | **PASS** |
| S2 | robustness | Mode 3+ | Student-t df=3 (moderate tail) | `0.0111` | `0.0116` | `0.96x` | `95.0%` [88.82, 97.85] | `nan%` [nan, nan] | **PASS** |
| S2 | robustness | Two-Stage Placement | Student-t df=3 (moderate tail) | `0.0056` | `0.0079` | `0.70x` | `96.0%` [90.16, 98.43] | `nan%` [nan, nan] | **PASS** |
| S2 | robustness | Anomaly Cascade | Student-t df=3 (moderate tail) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `17.0%` [10.89, 25.55] | <span style='color:red;'>**FAIL**</span> |
| S2 | robustness | Mode 2 | Student-t df=2.5 with 2% 5-sigma outliers | `0.0093` | `0.0116` | `0.81x` | `88.0%` [80.19, 93.0] | `nan%` [nan, nan] | **PASS** |
| S2 | robustness | Mode 3 | Student-t df=2.5 with 2% 5-sigma outliers | `0.0089` | `0.0126` | `0.71x` | `88.0%` [80.19, 93.0] | `nan%` [nan, nan] | **PASS** |
| S2 | robustness | Mode 3+ | Student-t df=2.5 with 2% 5-sigma outliers | `0.0093` | `0.0116` | `0.81x` | `88.0%` [80.19, 93.0] | `nan%` [nan, nan] | **PASS** |
| S2 | robustness | Two-Stage Placement | Student-t df=2.5 with 2% 5-sigma outliers | `0.0072` | `0.0079` | `0.91x` | `98.0%` [93.0, 99.45] | `nan%` [nan, nan] | **PASS** |
| S2 | robustness | Anomaly Cascade | Student-t df=2.5 with 2% 5-sigma outliers | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `25.0%` [17.55, 34.3] | <span style='color:red;'>**FAIL**</span> |
| S2 | robustness | Mode 2 | Student-t df=2.1 with 5% 5-sigma outliers | `0.0116` | `0.0116` | `1.00x` | `87.0%` [79.02, 92.24] | `nan%` [nan, nan] | **PASS** |
| S2 | robustness | Mode 3 | Student-t df=2.1 with 5% 5-sigma outliers | `0.0130` | `0.0126` | `1.04x` | `86.0%` [77.86, 91.47] | `nan%` [nan, nan] | **PASS** |
| S2 | robustness | Mode 3+ | Student-t df=2.1 with 5% 5-sigma outliers | `0.0116` | `0.0116` | `1.00x` | `87.0%` [79.02, 92.24] | `nan%` [nan, nan] | **PASS** |
| S2 | robustness | Two-Stage Placement | Student-t df=2.1 with 5% 5-sigma outliers | `0.0066` | `0.0079` | `0.83x` | `95.0%` [88.82, 97.85] | `nan%` [nan, nan] | **PASS** |
| S2 | robustness | Anomaly Cascade | Student-t df=2.1 with 5% 5-sigma outliers | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `45.0%` [35.61, 54.76] | <span style='color:red;'>**FAIL**</span> |
| S3 | robustness | Mode 2 | AR(1) rho = 0.50 | `0.0199` | `0.0116` | `1.72x` | `83.0%` [74.45, 89.11] | `nan%` [nan, nan] | **PASS** |
| S3 | robustness | Mode 3 | AR(1) rho = 0.50 | `0.0222` | `0.0126` | `1.76x` | `83.0%` [74.45, 89.11] | `nan%` [nan, nan] | **PASS** |
| S3 | robustness | Mode 3+ | AR(1) rho = 0.50 | `0.0198` | `0.0116` | `1.72x` | `83.0%` [74.45, 89.11] | `nan%` [nan, nan] | **PASS** |
| S3 | robustness | Two-Stage Placement | AR(1) rho = 0.50 | `0.0078` | `0.0079` | `0.98x` | `97.0%` [91.55, 98.97] | `nan%` [nan, nan] | **PASS** |
| S3 | robustness | Anomaly Cascade | AR(1) rho = 0.50 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `5.0%` [2.15, 11.18] | **PASS** |
| S3 | robustness | Mode 2 | AR(1) rho = 0.80 | `0.0288` | `0.0116` | `2.50x` | `61.0%` [51.2, 69.98] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S3 | robustness | Mode 3 | AR(1) rho = 0.80 | `0.0266` | `0.0126` | `2.12x` | `63.0%` [53.22, 71.82] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S3 | robustness | Mode 3+ | AR(1) rho = 0.80 | `0.0288` | `0.0116` | `2.50x` | `61.0%` [51.2, 69.98] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S3 | robustness | Two-Stage Placement | AR(1) rho = 0.80 | `0.0083` | `0.0079` | `1.04x` | `94.0%` [87.52, 97.22] | `nan%` [nan, nan] | **PASS** |
| S3 | robustness | Anomaly Cascade | AR(1) rho = 0.80 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `20.0%` [13.34, 28.88] | <span style='color:red;'>**FAIL**</span> |
| S3 | robustness | Mode 2 | AR(1) rho = 0.95 | `0.0238` | `0.0116` | `2.06x` | `69.0%` [59.37, 77.22] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S3 | robustness | Mode 3 | AR(1) rho = 0.95 | `0.0241` | `0.0126` | `1.92x` | `69.0%` [59.37, 77.22] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S3 | robustness | Mode 3+ | AR(1) rho = 0.95 | `0.0239` | `0.0116` | `2.06x` | `69.0%` [59.37, 77.22] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S3 | robustness | Two-Stage Placement | AR(1) rho = 0.95 | `0.0086` | `0.0079` | `1.08x` | `94.0%` [87.52, 97.22] | `nan%` [nan, nan] | **PASS** |
| S3 | robustness | Anomaly Cascade | AR(1) rho = 0.95 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `13.0%` [7.76, 20.98] | **PASS** |
| S4 | declared-scope violation | Mode 2 | Harmonic double mode sin(2 pi x) | `98.9987` | `0.0116` | `8569.37x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S4 | declared-scope violation | Mode 3 | Harmonic double mode sin(2 pi x) | `98.9979` | `0.0126` | `7882.68x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S4 | declared-scope violation | Mode 3+ | Harmonic double mode sin(2 pi x) | `98.9883` | `0.0116` | `8564.98x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S4 | declared-scope violation | Two-Stage Placement | Harmonic double mode sin(2 pi x) | `98.9987` | `0.0079` | `12470.39x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S4 | declared-scope violation | Anomaly Cascade | Harmonic double mode sin(2 pi x) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | <span style='color:red;'>**FAIL**</span> |
| S4 | declared-scope violation | Mode 2 | Two-mode sum sin(pi x) + 0.5 sin(3 pi x) | `0.0563` | `0.0116` | `4.87x` | `35.0%` [26.36, 44.75] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S4 | declared-scope violation | Mode 3 | Two-mode sum sin(pi x) + 0.5 sin(3 pi x) | `0.0558` | `0.0126` | `4.44x` | `36.0%` [27.27, 45.76] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S4 | declared-scope violation | Mode 3+ | Two-mode sum sin(pi x) + 0.5 sin(3 pi x) | `0.0562` | `0.0116` | `4.87x` | `35.0%` [26.36, 44.75] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S4 | declared-scope violation | Two-Stage Placement | Two-mode sum sin(pi x) + 0.5 sin(3 pi x) | `0.0762` | `0.0079` | `9.59x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S4 | declared-scope violation | Anomaly Cascade | Two-mode sum sin(pi x) + 0.5 sin(3 pi x) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | <span style='color:red;'>**FAIL**</span> |
| S4 | declared-scope violation | Mode 2 | Gaussian bump exp(-(x-0.5)^2 / (2*0.08^2)) | `26.1431` | `0.0116` | `2262.96x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S4 | declared-scope violation | Mode 3 | Gaussian bump exp(-(x-0.5)^2 / (2*0.08^2)) | `28.9774` | `0.0126` | `2307.32x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S4 | declared-scope violation | Mode 3+ | Gaussian bump exp(-(x-0.5)^2 / (2*0.08^2)) | `26.1430` | `0.0116` | `2262.03x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S4 | declared-scope violation | Two-Stage Placement | Gaussian bump exp(-(x-0.5)^2 / (2*0.08^2)) | `3.9861` | `0.0079` | `502.11x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S4 | declared-scope violation | Anomaly Cascade | Gaussian bump exp(-(x-0.5)^2 / (2*0.08^2)) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | <span style='color:red;'>**FAIL**</span> |
| S5 | declared-scope violation | Mode 2 | Small constant offset u_bc = 0.05 | `0.0692` | `0.0116` | `5.99x` | `12.0%` [7.0, 19.81] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S5 | declared-scope violation | Mode 3 | Small constant offset u_bc = 0.05 | `0.0733` | `0.0126` | `5.84x` | `11.0%` [6.25, 18.63] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S5 | declared-scope violation | Mode 3+ | Small constant offset u_bc = 0.05 | `0.0692` | `0.0116` | `5.99x` | `12.0%` [7.0, 19.81] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S5 | declared-scope violation | Two-Stage Placement | Small constant offset u_bc = 0.05 | `0.0542` | `0.0079` | `6.83x` | `1.0%` [0.18, 5.45] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S5 | declared-scope violation | Anomaly Cascade | Small constant offset u_bc = 0.05 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `87.0%` [79.02, 92.24] | <span style='color:red;'>**FAIL**</span> |
| S5 | declared-scope violation | Mode 2 | Moderate constant offset u_bc = 0.15 | `0.1886` | `0.0116` | `16.32x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S5 | declared-scope violation | Mode 3 | Moderate constant offset u_bc = 0.15 | `0.1911` | `0.0126` | `15.21x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S5 | declared-scope violation | Mode 3+ | Moderate constant offset u_bc = 0.15 | `0.1885` | `0.0116` | `16.31x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S5 | declared-scope violation | Two-Stage Placement | Moderate constant offset u_bc = 0.15 | `0.1549` | `0.0079` | `19.51x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S5 | declared-scope violation | Anomaly Cascade | Moderate constant offset u_bc = 0.15 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | <span style='color:red;'>**FAIL**</span> |
| S5 | declared-scope violation | Mode 2 | Linearly drifting boundary u_bc(t) = 0.20 * t | `0.1007` | `0.0116` | `8.72x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S5 | declared-scope violation | Mode 3 | Linearly drifting boundary u_bc(t) = 0.20 * t | `0.1034` | `0.0126` | `8.24x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S5 | declared-scope violation | Mode 3+ | Linearly drifting boundary u_bc(t) = 0.20 * t | `0.1007` | `0.0116` | `8.71x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S5 | declared-scope violation | Two-Stage Placement | Linearly drifting boundary u_bc(t) = 0.20 * t | `0.0742` | `0.0079` | `9.35x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S5 | declared-scope violation | Anomaly Cascade | Linearly drifting boundary u_bc(t) = 0.20 * t | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | <span style='color:red;'>**FAIL**</span> |
| S6 | declared-scope violation | Mode 2 | Small constant source s = 0.1 | `0.1694` | `0.0116` | `14.67x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S6 | declared-scope violation | Mode 3 | Small constant source s = 0.1 | `0.1714` | `0.0126` | `13.65x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S6 | declared-scope violation | Mode 3+ | Small constant source s = 0.1 | `0.1694` | `0.0116` | `14.66x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S6 | declared-scope violation | Two-Stage Placement | Small constant source s = 0.1 | `0.1711` | `0.0079` | `21.55x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S6 | declared-scope violation | Anomaly Cascade | Small constant source s = 0.1 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | <span style='color:red;'>**FAIL**</span> |
| S6 | declared-scope violation | Mode 2 | Moderate constant source s = 0.5 | `0.7144` | `0.0116` | `61.84x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S6 | declared-scope violation | Mode 3 | Moderate constant source s = 0.5 | `0.7162` | `0.0126` | `57.03x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S6 | declared-scope violation | Mode 3+ | Moderate constant source s = 0.5 | `0.7144` | `0.0116` | `61.81x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S6 | declared-scope violation | Two-Stage Placement | Moderate constant source s = 0.5 | `0.6965` | `0.0079` | `87.74x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S6 | declared-scope violation | Anomaly Cascade | Moderate constant source s = 0.5 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | <span style='color:red;'>**FAIL**</span> |
| S6 | declared-scope violation | Mode 2 | Strong constant source s = 2.0 | `0.9900` | `0.0116` | `85.69x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S6 | declared-scope violation | Mode 3 | Strong constant source s = 2.0 | `0.9953` | `0.0126` | `79.25x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S6 | declared-scope violation | Mode 3+ | Strong constant source s = 2.0 | `0.9900` | `0.0116` | `85.66x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S6 | declared-scope violation | Two-Stage Placement | Strong constant source s = 2.0 | `0.9900` | `0.0079` | `124.71x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S6 | declared-scope violation | Anomaly Cascade | Strong constant source s = 2.0 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | <span style='color:red;'>**FAIL**</span> |
| S7 | declared-scope violation | Mode 2 | Mild linear ramp alpha(x) = alpha0*(1 + 0.5*(x-0.5)) | `0.0326` | `0.0116` | `2.82x` | `61.0%` [51.2, 69.98] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S7 | declared-scope violation | Mode 3 | Mild linear ramp alpha(x) = alpha0*(1 + 0.5*(x-0.5)) | `0.0310` | `0.0126` | `2.47x` | `63.0%` [53.22, 71.82] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S7 | declared-scope violation | Mode 3+ | Mild linear ramp alpha(x) = alpha0*(1 + 0.5*(x-0.5)) | `0.0326` | `0.0116` | `2.82x` | `61.0%` [51.2, 69.98] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S7 | declared-scope violation | Two-Stage Placement | Mild linear ramp alpha(x) = alpha0*(1 + 0.5*(x-0.5)) | `0.0089` | `0.0079` | `1.11x` | `96.0%` [90.16, 98.43] | `nan%` [nan, nan] | **PASS** |
| S7 | declared-scope violation | Anomaly Cascade | Mild linear ramp alpha(x) = alpha0*(1 + 0.5*(x-0.5)) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `75.0%` [65.7, 82.45] | <span style='color:red;'>**FAIL**</span> |
| S7 | declared-scope violation | Mode 2 | Steep linear ramp alpha(x) = alpha0*(1 + 1.5*(x-0.5)) | `0.0849` | `0.0116` | `7.35x` | `19.0%` [12.51, 27.78] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S7 | declared-scope violation | Mode 3 | Steep linear ramp alpha(x) = alpha0*(1 + 1.5*(x-0.5)) | `0.0873` | `0.0126` | `6.95x` | `22.0%` [15.0, 31.07] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S7 | declared-scope violation | Mode 3+ | Steep linear ramp alpha(x) = alpha0*(1 + 1.5*(x-0.5)) | `0.0849` | `0.0116` | `7.35x` | `19.0%` [12.51, 27.78] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S7 | declared-scope violation | Two-Stage Placement | Steep linear ramp alpha(x) = alpha0*(1 + 1.5*(x-0.5)) | `0.0305` | `0.0079` | `3.85x` | `24.0%` [16.69, 33.23] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S7 | declared-scope violation | Anomaly Cascade | Steep linear ramp alpha(x) = alpha0*(1 + 1.5*(x-0.5)) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | <span style='color:red;'>**FAIL**</span> |
| S7 | declared-scope violation | Mode 2 | Step discontinuity alpha(x) = 2*alpha0 for x > 0.5 | `0.4882` | `0.0116` | `42.26x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S7 | declared-scope violation | Mode 3 | Step discontinuity alpha(x) = 2*alpha0 for x > 0.5 | `0.4839` | `0.0126` | `38.53x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S7 | declared-scope violation | Mode 3+ | Step discontinuity alpha(x) = 2*alpha0 for x > 0.5 | `0.4882` | `0.0116` | `42.24x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S7 | declared-scope violation | Two-Stage Placement | Step discontinuity alpha(x) = 2*alpha0 for x > 0.5 | `0.5170` | `0.0079` | `65.12x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S7 | declared-scope violation | Anomaly Cascade | Step discontinuity alpha(x) = 2*alpha0 for x > 0.5 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | <span style='color:red;'>**FAIL**</span> |
| S8 | robustness | Mode 2 | 10% readings missing (1 sensor dropped) | `0.0155` | `0.0116` | `1.34x` | `87.0%` [79.02, 92.24] | `nan%` [nan, nan] | **PASS** |
| S8 | robustness | Mode 3 | 10% readings missing (1 sensor dropped) | `0.0132` | `0.0126` | `1.05x` | `86.0%` [77.86, 91.47] | `nan%` [nan, nan] | **PASS** |
| S8 | robustness | Mode 3+ | 10% readings missing (1 sensor dropped) | `0.0155` | `0.0116` | `1.34x` | `87.0%` [79.02, 92.24] | `nan%` [nan, nan] | **PASS** |
| S8 | robustness | Two-Stage Placement | 10% readings missing (1 sensor dropped) | `0.0092` | `0.0079` | `1.16x` | `92.0%` [85.0, 95.89] | `nan%` [nan, nan] | **PASS** |
| S8 | robustness | Anomaly Cascade | 10% readings missing (1 sensor dropped) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `9.0%` [4.81, 16.23] | **PASS** |
| S8 | robustness | Mode 2 | 30% readings missing (3 sensors dropped) | `0.0185` | `0.0116` | `1.60x` | `95.0%` [88.82, 97.85] | `nan%` [nan, nan] | **PASS** |
| S8 | robustness | Mode 3 | 30% readings missing (3 sensors dropped) | `0.0184` | `0.0126` | `1.46x` | `94.0%` [87.52, 97.22] | `nan%` [nan, nan] | **PASS** |
| S8 | robustness | Mode 3+ | 30% readings missing (3 sensors dropped) | `0.0185` | `0.0116` | `1.60x` | `95.0%` [88.82, 97.85] | `nan%` [nan, nan] | **PASS** |
| S8 | robustness | Two-Stage Placement | 30% readings missing (3 sensors dropped) | `0.0090` | `0.0079` | `1.13x` | `94.0%` [87.52, 97.22] | `nan%` [nan, nan] | **PASS** |
| S8 | robustness | Anomaly Cascade | 30% readings missing (3 sensors dropped) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `3.0%` [1.03, 8.45] | **PASS** |
| S8 | robustness | Mode 2 | 50% readings missing (5 sensors dropped) | `0.0248` | `0.0116` | `2.15x` | `92.0%` [85.0, 95.89] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S8 | robustness | Mode 3 | 50% readings missing (5 sensors dropped) | `0.0258` | `0.0126` | `2.05x` | `91.0%` [83.77, 95.19] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S8 | robustness | Mode 3+ | 50% readings missing (5 sensors dropped) | `0.0248` | `0.0116` | `2.15x` | `92.0%` [85.0, 95.89] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S8 | robustness | Two-Stage Placement | 50% readings missing (5 sensors dropped) | `0.0081` | `0.0079` | `1.02x` | `97.0%` [91.55, 98.97] | `nan%` [nan, nan] | **PASS** |
| S8 | robustness | Anomaly Cascade | 50% readings missing (5 sensors dropped) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `5.0%` [2.15, 11.18] | **PASS** |
| S9 | robustness | Mode 2 | Small jitter sigma_jitter = 0.01 | `0.0184` | `0.0116` | `1.59x` | `82.0%` [73.33, 88.3] | `nan%` [nan, nan] | **PASS** |
| S9 | robustness | Mode 3 | Small jitter sigma_jitter = 0.01 | `0.0174` | `0.0126` | `1.38x` | `82.0%` [73.33, 88.3] | `nan%` [nan, nan] | **PASS** |
| S9 | robustness | Mode 3+ | Small jitter sigma_jitter = 0.01 | `0.0184` | `0.0116` | `1.59x` | `82.0%` [73.33, 88.3] | `nan%` [nan, nan] | **PASS** |
| S9 | robustness | Two-Stage Placement | Small jitter sigma_jitter = 0.01 | `0.0086` | `0.0079` | `1.08x` | `95.0%` [88.82, 97.85] | `nan%` [nan, nan] | **PASS** |
| S9 | robustness | Anomaly Cascade | Small jitter sigma_jitter = 0.01 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `59.0%` [49.2, 68.13] | <span style='color:red;'>**FAIL**</span> |
| S9 | robustness | Mode 2 | Moderate jitter sigma_jitter = 0.03 | `0.0377` | `0.0116` | `3.26x` | `50.0%` [40.38, 59.62] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S9 | robustness | Mode 3 | Moderate jitter sigma_jitter = 0.03 | `0.0407` | `0.0126` | `3.24x` | `48.0%` [38.46, 57.68] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S9 | robustness | Mode 3+ | Moderate jitter sigma_jitter = 0.03 | `0.0377` | `0.0116` | `3.26x` | `50.0%` [40.38, 59.62] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S9 | robustness | Two-Stage Placement | Moderate jitter sigma_jitter = 0.03 | `0.0079` | `0.0079` | `0.99x` | `95.0%` [88.82, 97.85] | `nan%` [nan, nan] | **PASS** |
| S9 | robustness | Anomaly Cascade | Moderate jitter sigma_jitter = 0.03 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | <span style='color:red;'>**FAIL**</span> |
| S9 | robustness | Mode 2 | Large jitter sigma_jitter = 0.06 | `0.0918` | `0.0116` | `7.94x` | `17.0%` [10.89, 25.55] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S9 | robustness | Mode 3 | Large jitter sigma_jitter = 0.06 | `0.0900` | `0.0126` | `7.17x` | `15.0%` [9.31, 23.28] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S9 | robustness | Mode 3+ | Large jitter sigma_jitter = 0.06 | `0.0918` | `0.0116` | `7.94x` | `17.0%` [10.89, 25.55] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S9 | robustness | Two-Stage Placement | Large jitter sigma_jitter = 0.06 | `0.0080` | `0.0079` | `1.01x` | `96.0%` [90.16, 98.43] | `nan%` [nan, nan] | **PASS** |
| S9 | robustness | Anomaly Cascade | Large jitter sigma_jitter = 0.06 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | <span style='color:red;'>**FAIL**</span> |
| S10 | robustness | Mode 2 | Small sensor bias b = 3 sigma (0.03) | `0.0155` | `0.0116` | `1.34x` | `93.0%` [86.25, 96.57] | `nan%` [nan, nan] | **PASS** |
| S10 | robustness | Mode 3 | Small sensor bias b = 3 sigma (0.03) | `0.0163` | `0.0126` | `1.29x` | `93.0%` [86.25, 96.57] | `nan%` [nan, nan] | **PASS** |
| S10 | robustness | Mode 3+ | Small sensor bias b = 3 sigma (0.03) | `0.0155` | `0.0116` | `1.34x` | `93.0%` [86.25, 96.57] | `nan%` [nan, nan] | **PASS** |
| S10 | robustness | Two-Stage Placement | Small sensor bias b = 3 sigma (0.03) | `0.0079` | `0.0079` | `1.00x` | `94.0%` [87.52, 97.22] | `nan%` [nan, nan] | **PASS** |
| S10 | robustness | Anomaly Cascade | Small sensor bias b = 3 sigma (0.03) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `51.0%` [41.35, 60.58] | <span style='color:red;'>**FAIL**</span> |
| S10 | robustness | Mode 2 | Medium sensor bias b = 6 sigma (0.06) | `0.0133` | `0.0116` | `1.15x` | `89.0%` [81.37, 93.75] | `nan%` [nan, nan] | **PASS** |
| S10 | robustness | Mode 3 | Medium sensor bias b = 6 sigma (0.06) | `0.0146` | `0.0126` | `1.17x` | `89.0%` [81.37, 93.75] | `nan%` [nan, nan] | **PASS** |
| S10 | robustness | Mode 3+ | Medium sensor bias b = 6 sigma (0.06) | `0.0133` | `0.0116` | `1.15x` | `89.0%` [81.37, 93.75] | `nan%` [nan, nan] | **PASS** |
| S10 | robustness | Two-Stage Placement | Medium sensor bias b = 6 sigma (0.06) | `0.0059` | `0.0079` | `0.74x` | `94.0%` [87.52, 97.22] | `nan%` [nan, nan] | **PASS** |
| S10 | robustness | Anomaly Cascade | Medium sensor bias b = 6 sigma (0.06) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | <span style='color:red;'>**FAIL**</span> |
| S10 | robustness | Mode 2 | Strong sensor bias b = 15 sigma (0.15) | `0.0153` | `0.0116` | `1.33x` | `96.0%` [90.16, 98.43] | `nan%` [nan, nan] | **PASS** |
| S10 | robustness | Mode 3 | Strong sensor bias b = 15 sigma (0.15) | `0.0165` | `0.0126` | `1.31x` | `93.0%` [86.25, 96.57] | `nan%` [nan, nan] | **PASS** |
| S10 | robustness | Mode 3+ | Strong sensor bias b = 15 sigma (0.15) | `0.0153` | `0.0116` | `1.33x` | `96.0%` [90.16, 98.43] | `nan%` [nan, nan] | **PASS** |
| S10 | robustness | Two-Stage Placement | Strong sensor bias b = 15 sigma (0.15) | `0.0079` | `0.0079` | `0.99x` | `98.0%` [93.0, 99.45] | `nan%` [nan, nan] | **PASS** |
| S10 | robustness | Anomaly Cascade | Strong sensor bias b = 15 sigma (0.15) | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | <span style='color:red;'>**FAIL**</span> |
| S11 | robustness | Mode 2 | Sparse array N = 5 sensors | `0.0166` | `0.0116` | `1.44x` | `95.0%` [88.82, 97.85] | `nan%` [nan, nan] | **PASS** |
| S11 | robustness | Mode 3 | Sparse array N = 5 sensors | `0.0182` | `0.0126` | `1.45x` | `95.0%` [88.82, 97.85] | `nan%` [nan, nan] | **PASS** |
| S11 | robustness | Mode 3+ | Sparse array N = 5 sensors | `0.0166` | `0.0116` | `1.44x` | `95.0%` [88.82, 97.85] | `nan%` [nan, nan] | **PASS** |
| S11 | robustness | Two-Stage Placement | Sparse array N = 5 sensors | `0.0083` | `0.0079` | `1.04x` | `97.0%` [91.55, 98.97] | `nan%` [nan, nan] | **PASS** |
| S11 | robustness | Anomaly Cascade | Sparse array N = 5 sensors | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `1.0%` [0.18, 5.45] | **PASS** |
| S11 | robustness | Mode 2 | Very sparse array N = 3 sensors | `0.0216` | `0.0116` | `1.86x` | `91.0%` [83.77, 95.19] | `nan%` [nan, nan] | **PASS** |
| S11 | robustness | Mode 3 | Very sparse array N = 3 sensors | `0.0247` | `0.0126` | `1.97x` | `89.0%` [81.37, 93.75] | `nan%` [nan, nan] | **PASS** |
| S11 | robustness | Mode 3+ | Very sparse array N = 3 sensors | `0.0216` | `0.0116` | `1.87x` | `91.0%` [83.77, 95.19] | `nan%` [nan, nan] | **PASS** |
| S11 | robustness | Two-Stage Placement | Very sparse array N = 3 sensors | `0.0156` | `0.0079` | `1.97x` | `96.0%` [90.16, 98.43] | `nan%` [nan, nan] | **PASS** |
| S11 | robustness | Anomaly Cascade | Very sparse array N = 3 sensors | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `5.0%` [2.15, 11.18] | **PASS** |
| S11 | robustness | Mode 2 | Minimal array N = 2 sensors | `0.0205` | `0.0116` | `1.77x` | `94.0%` [87.52, 97.22] | `nan%` [nan, nan] | **PASS** |
| S11 | robustness | Mode 3 | Minimal array N = 2 sensors | `0.0245` | `0.0126` | `1.95x` | `95.0%` [88.82, 97.85] | `nan%` [nan, nan] | **PASS** |
| S11 | robustness | Mode 3+ | Minimal array N = 2 sensors | `0.0205` | `0.0116` | `1.77x` | `94.0%` [87.52, 97.22] | `nan%` [nan, nan] | **PASS** |
| S11 | robustness | Two-Stage Placement | Minimal array N = 2 sensors | `0.0204` | `0.0079` | `2.57x` | `95.0%` [88.82, 97.85] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S11 | robustness | Anomaly Cascade | Minimal array N = 2 sensors | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `6.0%` [2.78, 12.48] | **PASS** |
| S12 | robustness | Mode 2 | Sub-grid low diffusivity alpha = 5e-4 | `1.0000` | `0.0116` | `86.56x` | `88.0%` [80.19, 93.0] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S12 | robustness | Mode 3 | Sub-grid low diffusivity alpha = 5e-4 | `0.9690` | `0.0126` | `77.16x` | `80.0%` [71.12, 86.66] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S12 | robustness | Mode 3+ | Sub-grid low diffusivity alpha = 5e-4 | `1.0002` | `0.0116` | `86.55x` | `88.0%` [80.19, 93.0] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S12 | robustness | Two-Stage Placement | Sub-grid low diffusivity alpha = 5e-4 | `1.0000` | `0.0079` | `125.97x` | `90.0%` [82.56, 94.48] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S12 | robustness | Anomaly Cascade | Sub-grid low diffusivity alpha = 5e-4 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | <span style='color:red;'>**FAIL**</span> |
| S12 | robustness | Mode 2 | Super-grid high diffusivity alpha = 5.0 | `0.1075` | `0.0116` | `9.30x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S12 | robustness | Mode 3 | Super-grid high diffusivity alpha = 5.0 | `0.1031` | `0.0126` | `8.21x` | `22.0%` [15.0, 31.07] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S12 | robustness | Mode 3+ | Super-grid high diffusivity alpha = 5.0 | `0.1075` | `0.0116` | `9.30x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S12 | robustness | Two-Stage Placement | Super-grid high diffusivity alpha = 5.0 | `0.0101` | `0.0079` | `1.28x` | `94.0%` [87.52, 97.22] | `nan%` [nan, nan] | **PASS** |
| S12 | robustness | Anomaly Cascade | Super-grid high diffusivity alpha = 5.0 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | <span style='color:red;'>**FAIL**</span> |
| S12 | robustness | Mode 2 | Super-grid extreme diffusivity alpha = 20.0 | `0.5000` | `0.0116` | `43.28x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S12 | robustness | Mode 3 | Super-grid extreme diffusivity alpha = 20.0 | `0.5000` | `0.0126` | `39.81x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S12 | robustness | Mode 3+ | Super-grid extreme diffusivity alpha = 20.0 | `0.5001` | `0.0116` | `43.27x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S12 | robustness | Two-Stage Placement | Super-grid extreme diffusivity alpha = 20.0 | `0.5000` | `0.0079` | `62.98x` | `0.0%` [0.0, 3.7] | `nan%` [nan, nan] | <span style='color:red;'>**FAIL**</span> |
| S12 | robustness | Anomaly Cascade | Super-grid extreme diffusivity alpha = 20.0 | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `100.0%` [96.3, 100.0] | <span style='color:red;'>**FAIL**</span> |
| S13 | robustness | Mode 2 | Slow drift delta = 2% | `0.0144` | `0.0116` | `1.24x` | `92.0%` [85.0, 95.89] | `nan%` [nan, nan] | **PASS** |
| S13 | robustness | Mode 3 | Slow drift delta = 2% | `0.0132` | `0.0126` | `1.05x` | `91.0%` [83.77, 95.19] | `nan%` [nan, nan] | **PASS** |
| S13 | robustness | Mode 3+ | Slow drift delta = 2% | `0.0144` | `0.0116` | `1.24x` | `92.0%` [85.0, 95.89] | `nan%` [nan, nan] | **PASS** |
| S13 | robustness | Two-Stage Placement | Slow drift delta = 2% | `0.0075` | `0.0079` | `0.94x` | `96.0%` [90.16, 98.43] | `nan%` [nan, nan] | **PASS** |
| S13 | robustness | Anomaly Cascade | Slow drift delta = 2% | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `7.0%` [3.43, 13.75] | **PASS** |
| S13 | robustness | Mode 2 | Moderate drift delta = 5% | `0.0172` | `0.0116` | `1.49x` | `89.0%` [81.37, 93.75] | `nan%` [nan, nan] | **PASS** |
| S13 | robustness | Mode 3 | Moderate drift delta = 5% | `0.0169` | `0.0126` | `1.35x` | `90.0%` [82.56, 94.48] | `nan%` [nan, nan] | **PASS** |
| S13 | robustness | Mode 3+ | Moderate drift delta = 5% | `0.0172` | `0.0116` | `1.49x` | `89.0%` [81.37, 93.75] | `nan%` [nan, nan] | **PASS** |
| S13 | robustness | Two-Stage Placement | Moderate drift delta = 5% | `0.0080` | `0.0079` | `1.01x` | `94.0%` [87.52, 97.22] | `nan%` [nan, nan] | **PASS** |
| S13 | robustness | Anomaly Cascade | Moderate drift delta = 5% | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `7.0%` [3.43, 13.75] | **PASS** |
| S13 | robustness | Mode 2 | Severe drift delta = 10% | `0.0158` | `0.0116` | `1.37x` | `94.0%` [87.52, 97.22] | `nan%` [nan, nan] | **PASS** |
| S13 | robustness | Mode 3 | Severe drift delta = 10% | `0.0157` | `0.0126` | `1.25x` | `95.0%` [88.82, 97.85] | `nan%` [nan, nan] | **PASS** |
| S13 | robustness | Mode 3+ | Severe drift delta = 10% | `0.0158` | `0.0116` | `1.37x` | `94.0%` [87.52, 97.22] | `nan%` [nan, nan] | **PASS** |
| S13 | robustness | Two-Stage Placement | Severe drift delta = 10% | `0.0079` | `0.0079` | `0.99x` | `95.0%` [88.82, 97.85] | `nan%` [nan, nan] | **PASS** |
| S13 | robustness | Anomaly Cascade | Severe drift delta = 10% | `nan` | `nan` | `nanx` | `nan%` [nan, nan] | `29.0%` [21.01, 38.54] | <span style='color:red;'>**FAIL**</span> |
