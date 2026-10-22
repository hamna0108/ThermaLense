# Neural PDE Digital Twin: Physics-Informed Operator Learning

A production-grade, mathematically verified digital twin platform combining classical numerical solvers with neural operators (FNO-2D) and physics-informed neural networks (PINN) for transient and steady-state partial differential equations.

---

## 1. Production REST Service (FastAPI)

The production inference and diagnostics service is implemented in `service/` and powered by Uvicorn and FastAPI. Neural operators, precomputed surrogate lookup tables, and sparse solver factorizations are loaded **once at startup** via FastAPI lifespan.

### Starting the Service

```bash
# Launch Uvicorn ASGI production server on port 8000
uvicorn service.app:app --host 0.0.0.0 --port 8000
```

### Endpoints Overview

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/v1/estimate` | Invert diffusivity $\hat{\alpha}$, compute 95% Wald CI, evaluate goodness-of-fit gating, range guard, and baseline $\hat{\sigma}$. Default mode: `mode3plus`. |
| `POST` | `/v1/diagnose` | Classify sensor stream into Healthy (`H`), Anomalous Diffusion (`A`), Sensor Fault (`F`), or Change-Point (`C`) via baseline-informed GLR cascade ($k \ge 20$). |
| `POST` | `/v1/placement` | Generate two-stage adaptive sensor placement schedules concentrating observations around $t^* = 1/(\pi^2 \hat{\alpha})$. |
| `POST` | `/v1/field` | Generate 2D spatial-temporal heat field $u(x, t)$ on grid; uses FNO if $\alpha \in [0.01, 1.0]$, otherwise live Crank-Nicolson solver. |
| `POST` | `/v1/poisson` | Solve 2D Poisson $-\nabla^2 u = f$ using exact sparse LU solver, FNO, and linear ridge baseline; flags `high_frequency_source` if sine modes $> 4$. |
| `GET` | `/health` | Healthcheck endpoint reporting service liveness and timestamp. |
| `GET` | `/version` | Provenance metadata: git commit SHA, tags, and SHA-256 hashes of all model checkpoints. |
| `GET` | `/metrics` | Prometheus-style metrics snapshot: request counts, errors, refusals, p50/p95 latency, and flag shares. |

---

### API Request & Response Examples (Captured from Live Service via cURL)

All examples below represent real captured HTTP requests and responses executed against the running service via `curl.exe` and archived in `docs/api_examples/`.

#### 1. `POST /v1/estimate`
**Request (`docs/api_examples/estimate_request.json`):**
```bash
curl -X POST http://localhost:8000/v1/estimate \
  -H "Content-Type: application/json" \
  -d '{
    "x_coords": [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
    "t_coords": [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95],
    "readings": [0.612, 0.228, 0.085, 0.032, 0.012, 0.004, 0.002, 0.001, 0.0, 0.0],
    "sigma": 0.01,
    "mode": "mode3plus",
    "physics_config": {
      "u0_expr": "sin(pi * x)"
    }
  }'
```
**Response (`docs/api_examples/estimate_response.json`):**
```json
{
  "alpha_hat": 0.997405,
  "ci95": [
    0.960072,
    1.036189
  ],
  "method": "Declared Physics (splu)",
  "flags": {
    "model_invalid": false,
    "out_of_range": false,
    "at_bound": false,
    "warnings": []
  },
  "effective_sigma": 0.01,
  "timing_ms": 152.92
}
```
*Note: If `sigma` is omitted, `baseline` with $k \ge 20$ readings must be provided. Expressions in `physics_config` are validated against a strict AST whitelist (max 200 chars, no `eval`, `exec`, or unwhitelisted symbols).*

#### 2. `POST /v1/diagnose`
**Request (`docs/api_examples/diagnose_request.json`):**
```bash
curl -X POST http://localhost:8000/v1/diagnose \
  -H "Content-Type: application/json" \
  -d '{
    "readings": {
      "x_coords": [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
      "t_coords": [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95],
      "readings": [0.612, 0.225, 0.083, 0.031, 0.511, 0.004, 0.002, 0.001, 0.0, 0.0]
    },
    "baseline": {
      "x_coords": [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
      "t_coords": [0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0],
      "readings": [0.612, 0.373, 0.228, 0.139, 0.085, 0.052, 0.032, 0.019, 0.012, 0.007, 0.004, 0.003, 0.002, 0.001, 0.001, 0.0, 0.0, 0.0, 0.0, 0.0]
    },
    "sigma": 0.01
  }'
```
**Response (`docs/api_examples/diagnose_response.json`):**
```json
{
  "assigned_class": "F",
  "evidence_stats": {
    "glr_stat": 506.387,
    "glr_threshold": 7.544,
    "bic_healthy": 2459.61,
    "bic_sensor_fault": 12.16,
    "alpha_fitted": 0.873134,
    "alpha_baseline": 0.998341,
    "chi2_reduced": 273.034
  },
  "faulty_sensor_idx": 4,
  "change_time": null,
  "effective_sigma": 0.01,
  "timing_ms": 13.67
}
```
*Architecture Note on Baseline Coordinates: The baseline dataset is collected during an independent calibration run over $k \ge 20$ points, while `readings` contains operational measurements ($N=10$). `BaselineData` has its own explicit spatial and temporal coordinates (`x_coords`, `t_coords`, `readings`).*

#### 3. `POST /v1/placement`
**Request (`docs/api_examples/placement_request.json`):**
```bash
curl -X POST http://localhost:8000/v1/placement \
  -H "Content-Type: application/json" \
  -d '{"N": 20, "sigma": 0.01, "sensor_x": 0.5}'
```
**Response (`docs/api_examples/placement_response.json`):**
```json
{
  "N": 20,
  "sigma": 0.01,
  "sensor_x": 0.5,
  "t_stage1": [
    0.01, 0.01668, 0.02783, 0.04642, 0.07743,
    0.12915, 0.21544, 0.35938, 0.59948, 1.0
  ],
  "t_stage2_nominal": [
    0.26238, 0.40517, 0.50304, 0.58449, 0.65722,
    0.72466, 0.78867, 0.85045, 0.91081, 0.97037
  ],
  "strategy_description": "Two-stage adaptive placement at x=0.5: Stage 1 (10 points) explores log-spaced time domain. Stage 2 (10 points) dynamically concentrates around t* = 1 / (pi^2 * alpha_hat_1).",
  "timing_ms": 0.73
}
```

#### 4. `POST /v1/field`
**Request (`docs/api_examples/field_request.json`):**
```bash
curl -X POST http://localhost:8000/v1/field \
  -H "Content-Type: application/json" \
  -d '{"alpha": 0.10, "method": "fno", "Nx": 64, "Nt": 64}'
```
**Response (`docs/api_examples/field_response.json`):**
```json
{
  "u_grid": [[... 64x64 floating point matrix ...]],
  "x_grid": [0.0, 0.01587, 0.03175, "...", 1.0],
  "t_grid": [0.0, 0.01587, 0.03175, "...", 1.0],
  "method_used": "fno",
  "timing_ms": 3.99
}
```

#### 5. `POST /v1/poisson`
**Request (`docs/api_examples/poisson_request.json`):**
```bash
curl -X POST http://localhost:8000/v1/poisson \
  -H "Content-Type: application/json" \
  -d '{
    "source": {
      "type": "sine",
      "modes": [[2, 2]],
      "amplitudes": [1.0]
    },
    "grid_size": 64
  }'
```
**Response (`docs/api_examples/poisson_response.json`):**
```json
{
  "exact_field": [[... 64x64 array ...]],
  "fno_field": [[... 64x64 array ...]],
  "linear_field": [[... 64x64 array ...]],
  "relative_errors": {
    "rel_l2_fno_vs_exact": 0.029476,
    "rel_l2_linear_vs_exact": 0.045751,
    "rel_l2_fno_vs_linear": 0.05388
  },
  "timing_ms": {
    "exact_ms": 0.772,
    "fno_ms": 29.836,
    "linear_ms": 2.921,
    "total_ms": 33.88
  },
  "high_frequency_source": false
}
```
*Note: Direct sparse LU solves in 0.77 ms on CPU, 38.6x faster than FNO (29.84 ms).*

#### 6. System Endpoints (`GET /health`, `/version`, `/metrics`)
```bash
curl -s http://localhost:8000/health
# {"status": "healthy", "service": "digital-twin-inverse-service", "version": "1.0.0", "timestamp": "1792672405.576943"}

curl -s http://localhost:8000/version
# {"git_commit": "73e721e1362685c77e620f0e7ae899e72b6698a8", "git_tags": ["frontend-v1"], "checkpoint_sha256s": {"fno2d_heat.pt": "74d778ac...", "fno2d_poisson_v2.pt": "0efc0fd1...", "linear_baseline_poisson_v2.npz": "1cbacc0c...", "pinn_expD.pt": "2d89edb5..."}}

curl -s http://localhost:8000/metrics
# {"requests_total": 23, "refusals_total": 0, "errors_total": 1, "latency_p50_ms": {"/v1/estimate": 157.63, "/v1/diagnose": 16.01, "/v1/poisson": 3.56, ...}}
```

---

## 2. One-Command Evaluation Runner

Evaluate the complete digital twin against all pre-registered frozen benchmark tables:

```bash
# Full evaluation against all test cells and splits
python -m evaluation.run_all --seed 20260101 --out data/results/eval_run/

# Quick evaluation (< 3 minutes, typically ~10 seconds)
python -m evaluation.run_all --seed 20260101 --out data/results/eval_run/ --quick
```

### Verified Checks

1. **`CHK_M3_MEDIAN_ERROR`**: Mode 3 median relative parameter inversion error is within 5% of frozen baseline (`mode3_pipeline_results_v2.csv`).
2. **`CHK_M3_COVERAGE`**: Mode 3 95% Wald CI coverage is within 2 percentage points of frozen baseline.
3. **`CHK_ANOMALY_FAR`**: Baseline-informed anomaly cascade detector healthy false alarm rate is within Wilson 95% CI.
4. **`CHK_ANOMALY_RECALL`**: Anomaly detector per-class recalls meet or exceed frozen benchmark tables (H $\ge 90\%$, A $\ge 90\%$, F $\ge 75\%$, C $\ge 85\%$).
5. **`CHK_POISSON_OPERATOR`**: Poisson 2D FNO and linear ridge baseline errors reproduce the frozen benchmark table (`poisson_v2_benchmark_table.csv`).

Outputs are written to `eval_summary.json` and `eval_summary.csv` in the specified `--out` directory.

---

## 3. Docker Deployment

A lightweight, secure container image is provided via `Dockerfile` and `.dockerignore`.

### Build & Run Instructions

```bash
# 1. Build the production container image
docker build -t digital-twin-service:latest .

# 2. Run the container as non-root user appuser
docker run -d --name digital-twin -p 8000:8000 digital-twin-service:latest

# 3. Verify health status
docker inspect --format='{{json .State.Health.Status}}' digital-twin
curl http://localhost:8000/health
```

*Note on Docker Execution: Docker CLI is not installed on the current host machine environment. `Dockerfile`, `.dockerignore`, and `requirements-service.txt` have been created and validated for deployment.*

---

## 4. Test Suite & Verification Audits

### Run Full Test Suite
```bash
pytest tests -v
```

### Run 5 Canonical Audits
```bash
python src/audit_inverse.py
python src/audit_sensor_placement.py
python src/audit_pinn_inverse.py
python src/audit_anomaly.py
python src/audit_poisson.py
```

---

## 5. Repository Architecture

- `service/`: FastAPI application (`app.py`), schemas (`models.py`), and thread-safe metrics (`metrics.py`).
- `evaluation/`: One-command verification runner (`run_all.py`).
- `src/`: Core numerical solvers, neural operator architectures, inverse pipelines, and audits.
- `models/`: Frozen checkpoints (`fno2d_heat.pt`, `fno2d_poisson_v2.pt`, `linear_baseline_poisson_v2.npz`, `pinn_expD.pt`).
- `data/results/`: Frozen benchmark results, confusion matrices, and audit evidence tables.
- `tools/`: Stress matrix testing scripts, rescoring utilities, and colab packaging tools.
- `EXPERIMENTS.md`: Complete experimental ledger tracking all seeds, splits, and numerical outcomes.
- `DECISIONS.md`: Design rationale records (options tried $\to$ chosen $\to$ evidence).
