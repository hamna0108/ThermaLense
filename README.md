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

### API Request & Response Examples

#### 1. `POST /v1/estimate`
**Request:**
```bash
curl -X POST http://localhost:8000/v1/estimate \
  -H "Content-Type: application/json" \
  -d '{
    "x": [0.5, 0.5, 0.5, 0.5, 0.5],
    "t": [0.1, 0.2, 0.3, 0.4, 0.5],
    "y": [0.3698, 0.1367, 0.0506, 0.0187, 0.0069],
    "sigma": 0.01
  }'
```
**Response:**
```json
{
  "alpha_hat": 0.10012,
  "ci95": [0.09634, 0.10405],
  "method": "Mode 3 (in-range)",
  "flags": {
    "model_invalid": false,
    "out_of_range": false,
    "at_bound": false,
    "warnings": []
  },
  "effective_sigma": 0.01,
  "timing_ms": 7.53
}
```

*Note: If `sigma` is omitted, `baseline` with $k \ge 20$ readings must be provided. If $k < 20$, the service returns HTTP 400 with code `REFUSED_INSUFFICIENT_BASELINE`.*

#### 2. `POST /v1/diagnose`
**Request:**
```bash
curl -X POST http://localhost:8000/v1/diagnose \
  -H "Content-Type: application/json" \
  -d '{
    "readings": {
      "x": [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
      "t": [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95],
      "y": [0.610, 0.225, 0.083, 0.031, 0.511, 0.004, 0.002, 0.001, 0.000, 0.000]
    },
    "baseline": {
      "x": [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
      "t": [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00],
      "y": [0.612, 0.373, 0.228, 0.139, 0.085, 0.052, 0.032, 0.019, 0.012, 0.007, 0.004, 0.003, 0.002, 0.001, 0.001, 0.000, 0.000, 0.000, 0.000, 0.000]
    }
  }'
```
**Response:**
```json
{
  "assigned_class": "F",
  "evidence_stats": {
    "glr_stat": 2.14,
    "glr_threshold": 7.50,
    "bic_healthy": 84.12,
    "bic_sensor_fault": 18.23,
    "alpha_fitted": 0.09871,
    "alpha_baseline": 0.09985,
    "chi2_reduced": 8.12
  },
  "faulty_sensor_idx": 4,
  "change_time": null,
  "effective_sigma": 0.01004,
  "timing_ms": 19.86
}
```

#### 3. `POST /v1/placement`
**Request:**
```bash
curl -X POST http://localhost:8000/v1/placement \
  -H "Content-Type: application/json" \
  -d '{"N": 10, "sigma": 0.01, "sensor_x": 0.5}'
```
**Response:**
```json
{
  "N": 10,
  "sigma": 0.01,
  "sensor_x": 0.5,
  "t_stage1": [0.01, 0.03162, 0.1, 0.31623, 1.0],
  "t_stage2_nominal": [0.0325, 0.0612, 0.0984, 0.1521, 0.2483],
  "strategy_description": "Two-stage adaptive placement at x=0.5: Stage 1 (5 points) explores log-spaced time domain. Stage 2 (5 points) dynamically concentrates around t* = 1 / (pi^2 * alpha_hat_1).",
  "timing_ms": 5.46
}
```

#### 4. `POST /v1/field`
**Request:**
```bash
curl -X POST http://localhost:8000/v1/field \
  -H "Content-Type: application/json" \
  -d '{"alpha": 0.10, "Nx": 101, "Nt": 201}'
```
**Response:**
```json
{
  "u_grid": [[...], ...],
  "x_grid": [0.0, 0.01, ..., 1.0],
  "t_grid": [0.0, 0.005, ..., 1.0],
  "method_used": "fno",
  "timing_ms": 98.93
}
```

#### 5. `POST /v1/poisson`
**Request (Sine Source with high-frequency check):**
```bash
curl -X POST http://localhost:8000/v1/poisson \
  -H "Content-Type: application/json" \
  -d '{
    "source": {
      "type": "sine",
      "modes": [[5, 2]],
      "amplitudes": [1.0]
    },
    "grid_size": 64
  }'
```
**Response:**
```json
{
  "exact_field": [[...], ...],
  "fno_field": [[...], ...],
  "linear_field": [[...], ...],
  "relative_errors": {
    "rel_l2_fno_vs_exact": 0.4215,
    "rel_l2_linear_vs_exact": 0.0149,
    "rel_l2_fno_vs_linear": 0.4198
  },
  "timing_ms": {
    "exact_ms": 0.485,
    "fno_ms": 12.31,
    "linear_ms": 1.12,
    "total_ms": 47.16
  },
  "high_frequency_source": true
}
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
