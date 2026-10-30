# ThermaLens Evaluation & Hidden Challenge Suite

This directory contains the batch runner, automated Monte Carlo evaluation sweep, and reference test cases for the ThermaLens Hidden-Evaluation Challenge.

---

## 1. Quickstart & Exact Commands

### Batch Runner (Mentor JSONL Format)
Execute the batch runner on the mentor's JSONL or JSON cases:

```bash
python -m challenge.run_challenge --cases challenge/cases_mentor.jsonl --out challenge/output_mentor --seed 20260101 --config challenge/config.json
```

### Stage 4 Analytical Verification Suite
Verify the generalized Crank-Nicolson numerical PDE solver against 4 analytical benchmarks (asserts all errors $< 10^{-3}$):

```bash
python -m challenge.run_challenge --verify-exact
```

### Reproducibility Verification
Run the automated reproducibility check (`--check-repro`). This executes the suite twice with the same seed and asserts that the resulting fields, estimates, intervals, verdicts, and diagnostics are identical (ignoring execution runtimes):

```bash
python -m challenge.run_challenge --cases challenge/cases_mentor.jsonl --out challenge/output_mentor --seed 20260101 --config challenge/config.json --check-repro
```

### Batch Runner (Legacy Flat Cases & Invalid Rejection Suite)
The batch runner maintains 100% backward compatibility with flat JSON/CSV formats and validates input errors cleanly:

```bash
# Legacy flat test cases
python -m challenge.run_challenge --cases challenge/test_cases.json --out challenge/output_legacy --seed 20260101 --config challenge/config.json

# Input validation & rejection test suite
python -m challenge.run_challenge --cases challenge/invalid_cases.json --out challenge/output_invalid --seed 20260101 --config challenge/config.json
```

### Monte Carlo Sweep
Run the Monte Carlo evaluation sweep across sensor counts ($N \in \{5, 10, 20\}$) and noise levels ($\sigma \in \{0.01, 0.05\}$) with 40 episodes per condition:

```bash
python -m challenge.sweep --out challenge/sweep.csv --episodes 40 --seed 20260101
```

---

## 2. Input Formats Accepted by the Runner

The batch runner accepts `.jsonl` (one JSON object per line), `.json` (JSON array or JSONL lines), or `.csv` files. All field-name mapping is decoupled in `adapt_case()` at the top of [challenge/run_challenge.py](file:///c:/Users/HP/Desktop/Digital%20twin/challenge/run_challenge.py).

### Mentor Schema (JSONL)

```json
{
  "case_id": "case_01_baseline_zero_ends",
  "equation": "heat_1d",
  "domain": {"x": [0.0, 1.0], "t": [0.0, 1.0]},
  "grid": {"nx": 101, "nt": 101},
  "initial_condition": {"type": "sin_pi_x"},
  "boundary_conditions": {
    "x_min": {"type": "dirichlet", "value": 0.0},
    "x_max": {"type": "dirichlet", "value": 0.0}
  },
  "observations": [
    {"x": 0.25, "t": 0.1, "u": 0.64065},
    {"x": 0.50, "t": 0.2, "u": 0.82087}
  ],
  "known_parameters": {
    "sigma": 0.01,
    "alpha_nominal": 0.10,
    "truth_alpha": 0.10,
    "truth_field": [...]
  },
  "infer_parameters": ["alpha"]
}
```

### Supported Initial Conditions & Boundary Conditions

1. **Initial Conditions (`initial_condition.type`)**:
   - `"sin_pi_x"`: $u_0(x) = \sin(\pi \frac{x - x_{min}}{x_{max} - x_{min}})$
   - `"constant"`: $u_0(x) = \text{value}$
   - `"linear"`: $u_0(x) = \text{slope} \cdot x + \text{intercept}$
   - `"step"`: $u_0(x) = \text{val\_left}$ if $x < \text{step\_x}$ else $\text{val\_right}$
   - `"gaussian"`: $u_0(x) = \text{amp} \cdot \exp(- (x - \mu)^2 / (2 \sigma^2))$
   - `"sine_modes"`: $u_0(x) = \sum A_k \sin(k \pi \frac{x - x_{min}}{x_{max} - x_{min}})$
   - `"safe_expression"`: AST whitelist evaluator for math strings (e.g. `"cos(0.5 * pi * x)"`)
2. **Boundary Conditions (`boundary_conditions`)**:
   - `x_min` and `x_max`: each `{"type": "dirichlet" | "neumann", "value": float}`
   - Supports: Dirichlet at either/both ends with arbitrary values, Neumann (zero-derivative / insulated or prescribed flux), and mixed Dirichlet-Neumann.
3. **Poisson 2D Sources (`source_term.type`)**:
   - `"sin_sin"`, `"constant"`, `"gaussian"`, `"sine_modes"`, `"safe_expression"`
4. **Unsupported Types**:
   - Any unsupported initial condition or Poisson source term type produces `status: "invalid_input"` with a plain-language error message.

---

## 3. Two-Tier Dispatch Architecture (Stage 3)

The batch runner dynamically selects the optimal solving tier:

1. **Tier 1 (`fno`)**:
   - **Condition**: In-distribution cases (zero Dirichlet ends, `sin_pi_x` initial condition, $[0, 1] \times [0, 1]$ domain, and estimated $\hat{\alpha} \in [0.01, 1.0]$).
   - **Execution**: Evaluates the pre-trained Fourier Neural Operator surrogate.
   - **Grid Interpolation**: If the case specifies an arbitrary grid (e.g. $nx=51, nt=75$), the FNO field is interpolated using `scipy.interpolate.RegularGridInterpolator` to the exact grid requested.
2. **Tier 2 (`solver`)**:
   - **Condition**: Out-of-distribution cases (arbitrary BCs, non-trivial ICs, or $\hat{\alpha} \notin [0.01, 1.0]$).
   - **Execution**: Inverts $\hat{\alpha}$ and solves the PDE using the generalized Crank-Nicolson numerical solver directly on the exact grid $(nx, nt)$.
   - **Warning**: Automatically appends `"outside the neural model’s trained range; answered with the numerical solver"` to `out_of_domain`.
   - **Comparative Verification**: Evaluates the FNO out-of-domain and records `field_fno_out_of_domain` and `field_fno_rel_l2` in the output to demonstrate the domain discrepancy.

---

## 4. Few Observations & Missing Sigma (Stage 5)

1. **Rejection Rule**: A case is rejected for sensor count **only if 0 observations** are provided (`len(readings) == 0`).
2. **Sparse Observations ($1 \le N < 4$)**:
   - The runner proceeds with parameter estimation.
   - Adds warning: `"interval unreliable with this few readings"`.
3. **Missing Noise Level $\sigma$**:
   - When $\sigma$ is missing and cannot be estimated ($N < 4$, such as the mentor's 2-observation test):
     - $\hat{\alpha}$ is estimated via least-squares.
     - `ci95` is set to `null`.
     - Adds note: `"not available: noise level unknown"`.

---

## 5. Output Files & Results Structure

Each execution creates the following outputs in `--out`:

1. **`results.jsonl`**: One complete JSON object per line in input order.
2. **`results.json`**: Top-level JSON dictionary containing run metadata and the full list of case results.
3. **`results.csv`**: Tabular CSV with one row per case, including `tier`, `alpha_hat`, `ci95`, errors, warnings, verdicts, and stage latencies.
4. **`summary.csv`**: Duplicate tabular summary for spreadsheet inspection.
5. **`run_log.txt`**: Execution log capturing exact CLI arguments, random seed, Git commit hash (HEAD), working tree cleanliness, dependency versions, and status counts.
6. **`config.json`**: A preserved snapshot copy of the configuration used.
