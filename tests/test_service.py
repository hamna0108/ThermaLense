"""Comprehensive tests for FastAPI Digital Twin Inverse & Diagnostics Service.

Tests:
- GET /health, GET /version, GET /metrics
- POST /v1/estimate: happy paths, baseline k>=20, refusal k<20, out_of_range, model_invalid
- POST /v1/diagnose: refusal k<20, healthy (H), sensor fault (F), change-point (C)
- POST /v1/placement: two-stage adaptive schedule
- POST /v1/field: FNO for in-range alpha, live solver for out-of-range alpha
- POST /v1/poisson: Gaussian source, low-frequency sine, high-frequency sine (flag)
- Pydantic validation errors (NaN, Inf, mismatched lengths, size limit)
- CPU Latency recording per endpoint
"""

import math
import time
import numpy as np
import pytest
from fastapi.testclient import TestClient

from service.app import app
from src.solvers.heat_1d import solve_heat_1d_exact

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def generate_heat_readings(alpha: float, N: int = 10, sigma: float = 0.01, seed: int = 42):
    rng = np.random.RandomState(seed)
    x = np.full(N, 0.5)
    t = np.linspace(0.05, 0.95, N)
    u_exact = solve_heat_1d_exact(x, t, alpha)
    noise = rng.normal(0.0, sigma, size=N) if sigma > 0 else np.zeros(N)
    y = u_exact + noise
    return x.tolist(), t.tolist(), y.tolist()

# -------------------------------------------------------------------------------------------------
# Frontend Static Files & Root
# -------------------------------------------------------------------------------------------------

def test_static_frontend_served(client):
    """Verify that GET / serves index.html, returns 200, and contains the title."""
    res = client.get("/")
    assert res.status_code == 200
    assert "ThermaLens" in res.text
    assert "<nav" in res.text
    assert "style.css" in res.text
    assert "app.js" in res.text

    # Also verify static assets
    res_css = client.get("/style.css")
    assert res_css.status_code == 200
    assert "Scientific Design System" in res_css.text

    res_js = client.get("/app.js")
    assert res_js.status_code == 200

    res_ev = client.get("/evidence.json")
    assert res_ev.status_code == 200
    data = res_ev.json()
    assert "headline_findings" in data

# -------------------------------------------------------------------------------------------------
# Health, Version, Metrics
# -------------------------------------------------------------------------------------------------

def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["service"] == "digital-twin-inverse-service"
    assert "timestamp" in data
    assert "X-Request-ID" in res.headers

def test_version(client):
    res = client.get("/version")
    assert res.status_code == 200
    data = res.json()
    assert data.get("name") == "ThermaLens"
    assert "git_commit" in data
    assert "git_tags" in data
    assert "checkpoint_sha256s" in data
    assert "fno2d_heat.pt" in data["checkpoint_sha256s"]
    assert "fno2d_poisson_v2.pt" in data["checkpoint_sha256s"]
    assert "linear_baseline_poisson_v2.npz" in data["checkpoint_sha256s"]

def test_metrics(client):
    res = client.get("/metrics")
    assert res.status_code == 200
    data = res.json()
    assert data["requests_total"] >= 1
    assert "latency_p50_ms" in data
    assert "flags" in data

# -------------------------------------------------------------------------------------------------
# POST /v1/estimate
# -------------------------------------------------------------------------------------------------

def test_estimate_happy_path_explicit_sigma(client):
    x, t, y = generate_heat_readings(alpha=0.10, N=10, sigma=0.01, seed=101)
    payload = {"x": x, "t": t, "y": y, "sigma": 0.01}
    res = client.post("/v1/estimate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert abs(data["alpha_hat"] - 0.10) < 0.04
    assert len(data["ci95"]) == 2
    assert data["ci95"][0] <= data["alpha_hat"] <= data["ci95"][1]
    assert not data["flags"]["model_invalid"]
    assert not data["flags"]["out_of_range"]
    assert data["timing_ms"] > 0

def test_estimate_happy_path_baseline(client):
    x, t, y = generate_heat_readings(alpha=0.10, N=10, sigma=0.01, seed=102)
    xb, tb, yb = generate_heat_readings(alpha=0.10, N=20, sigma=0.01, seed=103)
    payload = {
        "x": x, "t": t, "y": y,
        "baseline": {"x": xb, "t": tb, "y": yb}
    }
    res = client.post("/v1/estimate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert abs(data["alpha_hat"] - 0.10) < 0.04
    assert 0.005 < data["effective_sigma"] < 0.025
    assert not data["flags"]["model_invalid"]

def test_estimate_refusal_insufficient_baseline(client):
    x, t, y = generate_heat_readings(alpha=0.10, N=10, sigma=0.01)
    xb, tb, yb = generate_heat_readings(alpha=0.10, N=12, sigma=0.01)  # k=12 < 20
    payload = {
        "x": x, "t": t, "y": y,
        "baseline": {"x": xb, "t": tb, "y": yb}
    }
    res = client.post("/v1/estimate", json=payload)
    assert res.status_code == 400
    data = res.json()
    assert data["error_code"] == "REFUSED_INSUFFICIENT_BASELINE"
    assert "k=12 < 20" in data["message"]

def test_estimate_refusal_no_sigma_no_baseline(client):
    x, t, y = generate_heat_readings(alpha=0.10, N=10, sigma=0.01)
    payload = {"x": x, "t": t, "y": y}
    res = client.post("/v1/estimate", json=payload)
    assert res.status_code == 400
    data = res.json()
    assert data["error_code"] == "REFUSED_INSUFFICIENT_BASELINE"

def test_estimate_out_of_range_flag(client):
    # True alpha = 15.0 (way above upper bound 1.0)
    x, t, y = generate_heat_readings(alpha=15.0, N=10, sigma=0.01, seed=201)
    payload = {"x": x, "t": t, "y": y, "sigma": 0.01}
    res = client.post("/v1/estimate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["flags"]["out_of_range"] is True

def test_estimate_model_invalid_flag(client):
    # Corrupt readings with severe mismatch (source heating / huge offset)
    x, t, y = generate_heat_readings(alpha=0.10, N=10, sigma=0.01, seed=301)
    y_corrupt = [val + 3.0 for val in y]
    payload = {"x": x, "t": t, "y": y_corrupt, "sigma": 0.01}
    res = client.post("/v1/estimate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["flags"]["model_invalid"] is True

def test_estimate_declared_physics_mode(client):
    x, t, y = generate_heat_readings(alpha=0.10, N=10, sigma=0.01, seed=401)
    payload = {"x": x, "t": t, "y": y, "sigma": 0.01, "mode": "declared_physics"}
    res = client.post("/v1/estimate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "Declared Physics" in data["method"]
    assert abs(data["alpha_hat"] - 0.10) < 0.05

def test_estimate_physics_config_valid(client):
    x, t, y = generate_heat_readings(alpha=0.10, N=10, sigma=0.01, seed=402)
    payload = {
        "x_coords": x, "t_coords": t, "readings": y,
        "sigma": 0.01,
        "physics_config": {
            "u0_expr": "sin(pi * x)",
            "bc_left_expr": "0",
            "bc_right_expr": "0",
            "source_expr": "0",
            "alpha_expr": "1.0"
        }
    }
    res = client.post("/v1/estimate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["alpha_hat"] > 0

def test_estimate_security_rejections(client):
    x, t, y = generate_heat_readings(alpha=0.10, N=10, sigma=0.01, seed=403)
    
    # 1. Reject __import__('os')
    payload1 = {
        "x": x, "t": t, "y": y,
        "physics_config": {"u0_expr": "__import__('os')"}
    }
    res1 = client.post("/v1/estimate", json=payload1)
    assert res1.status_code == 400
    data1 = res1.json()
    assert data1["error_code"] == "SECURITY_VALIDATION_ERROR"
    assert "disallowed" in data1["message"].lower()

    # 2. Reject open('x')
    payload2 = {
        "x": x, "t": t, "y": y,
        "physics_config": {"bc_left_expr": "open('x')"}
    }
    res2 = client.post("/v1/estimate", json=payload2)
    assert res2.status_code == 400
    data2 = res2.json()
    assert data2["error_code"] == "SECURITY_VALIDATION_ERROR"
    assert "disallowed" in data2["message"].lower()

    # 3. Reject length > 200
    payload3 = {
        "x": x, "t": t, "y": y,
        "physics_config": {"u0_expr": "x + " * 100 + "x"}
    }
    res3 = client.post("/v1/estimate", json=payload3)
    assert res3.status_code == 400
    data3 = res3.json()
    assert data3["error_code"] == "SECURITY_VALIDATION_ERROR"
    assert "length" in data3["message"].lower() and "maximum" in data3["message"].lower()

# -------------------------------------------------------------------------------------------------
# POST /v1/diagnose
# -------------------------------------------------------------------------------------------------

def test_diagnose_refusal_k_less_than_20(client):
    x, t, y = generate_heat_readings(alpha=0.10, N=10, sigma=0.01)
    xb, tb, yb = generate_heat_readings(alpha=0.10, N=15, sigma=0.01)  # k=15 < 20
    payload = {
        "readings": {"x": x, "t": t, "y": y},
        "baseline": {"x": xb, "t": tb, "y": yb}
    }
    res = client.post("/v1/diagnose", json=payload)
    assert res.status_code == 400
    data = res.json()
    assert data["error_code"] == "REFUSED_INSUFFICIENT_BASELINE"
    assert "k=15" in data["message"]

def test_diagnose_healthy(client):
    x, t, y = generate_heat_readings(alpha=0.10, N=10, sigma=0.01, seed=501)
    xb, tb, yb = generate_heat_readings(alpha=0.10, N=20, sigma=0.01, seed=502)
    payload = {
        "readings": {"x": x, "t": t, "y": y},
        "baseline": {"x": xb, "t": tb, "y": yb}
    }
    res = client.post("/v1/diagnose", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["assigned_class"] == "H"
    assert data["faulty_sensor_idx"] is None
    assert data["change_time"] is None
    assert "glr_stat" in data["evidence_stats"]

def test_diagnose_canonical_coordinates(client):
    """Verify diagnose accepts canonical {x_coords, t_coords, readings} with k>=20 independent baseline."""
    xo, to, yo = generate_heat_readings(alpha=0.10, N=10, sigma=0.01, seed=510)
    xb, tb, yb = generate_heat_readings(alpha=0.10, N=25, sigma=0.01, seed=511)
    payload = {
        "readings": {"x_coords": xo, "t_coords": to, "readings": yo},
        "baseline": {"x_coords": xb, "t_coords": tb, "readings": yb},
        "sigma": 0.01
    }
    res = client.post("/v1/diagnose", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["assigned_class"] == "H"
    assert data["evidence_stats"]["alpha_baseline"] > 0

def test_diagnose_sensor_fault(client):
    x, t, y = generate_heat_readings(alpha=0.10, N=10, sigma=0.01, seed=601)
    fault_sensor = 4
    y[fault_sensor] += 0.50  # Inject prominent sensor bias
    xb, tb, yb = generate_heat_readings(alpha=0.10, N=20, sigma=0.01, seed=602)
    payload = {
        "readings": {"x": x, "t": t, "y": y},
        "baseline": {"x": xb, "t": tb, "y": yb}
    }
    res = client.post("/v1/diagnose", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["assigned_class"] == "F"
    assert data["faulty_sensor_idx"] == fault_sensor

def test_diagnose_change_point(client):
    # Step change in alpha from 0.05 to 0.50 at tc = 0.35
    x = np.full(10, 0.5)
    t = np.linspace(0.05, 0.95, 10)
    tc = 0.35
    u = np.zeros_like(t)
    early = t < tc
    late = ~early
    u[early] = np.sin(np.pi * x[early]) * np.exp(-0.05 * (np.pi**2) * t[early])
    u[late] = np.sin(np.pi * x[late]) * np.exp(-np.pi**2 * (0.05 * tc + 0.50 * (t[late] - tc)))
    
    xb, tb, yb = generate_heat_readings(alpha=0.05, N=20, sigma=0.01, seed=702)
    payload = {
        "readings": {"x": x.tolist(), "t": t.tolist(), "y": u.tolist()},
        "baseline": {"x": xb, "t": tb, "y": yb}
    }
    res = client.post("/v1/diagnose", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["assigned_class"] == "C"
    assert data["change_time"] is not None
    assert abs(data["change_time"] - tc) <= 0.15

# -------------------------------------------------------------------------------------------------
# POST /v1/placement
# -------------------------------------------------------------------------------------------------

def test_placement(client):
    payload = {"N": 20, "sigma": 0.01, "sensor_x": 0.5}
    res = client.post("/v1/placement", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["N"] == 20
    assert len(data["t_stage1"]) == 10
    assert len(data["t_stage2_nominal"]) == 10
    assert data["t_stage1"][0] < data["t_stage1"][-1]
    assert data["timing_ms"] > 0

# -------------------------------------------------------------------------------------------------
# POST /v1/field
# -------------------------------------------------------------------------------------------------

def test_field_fno_in_range(client):
    payload = {"alpha": 0.10, "Nx": 101, "Nt": 201}
    res = client.post("/v1/field", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["method_used"] == "fno"
    assert len(data["u_grid"]) == 201
    assert len(data["u_grid"][0]) == 101
    assert data["u_grid"][0][50] > 0.9  # Initial peak at x=0.5
    assert data["u_grid"][-1][50] < 0.5  # Decayed at t=1.0

def test_field_solver_out_of_range(client):
    payload = {"alpha": 5.0, "Nx": 101, "Nt": 201}
    res = client.post("/v1/field", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["method_used"] == "numerical_solver"
    assert len(data["u_grid"]) == 201
    assert len(data["u_grid"][0]) == 101

# -------------------------------------------------------------------------------------------------
# POST /v1/poisson
# -------------------------------------------------------------------------------------------------

def test_poisson_gaussian_source(client):
    payload = {
        "source": {
            "type": "gaussian",
            "centers": [[0.5, 0.5]],
            "amplitudes": [1.0],
            "sigmas": [0.15]
        },
        "grid_size": 64
    }
    res = client.post("/v1/poisson", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert len(data["exact_field"]) == 64
    assert len(data["fno_field"]) == 64
    assert len(data["linear_field"]) == 64
    assert data["relative_errors"]["rel_l2_fno_vs_exact"] < 0.10
    assert data["high_frequency_source"] is False
    assert data["timing_ms"]["exact_ms"] >= 0
    assert data["timing_ms"]["fno_ms"] >= 0

def test_poisson_sine_low_frequency(client):
    payload = {
        "source": {
            "type": "sine",
            "modes": [[2, 2]],
            "amplitudes": [1.0]
        },
        "grid_size": 64
    }
    res = client.post("/v1/poisson", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["high_frequency_source"] is False
    assert data["relative_errors"]["rel_l2_fno_vs_exact"] < 0.10

def test_poisson_sine_high_frequency_flag(client):
    payload = {
        "source": {
            "type": "sine",
            "modes": [[6, 2]],  # mode 6 > 4 triggers flag
            "amplitudes": [1.0]
        },
        "grid_size": 64
    }
    res = client.post("/v1/poisson", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["high_frequency_source"] is True

# -------------------------------------------------------------------------------------------------
# Validation & Error Handling
# -------------------------------------------------------------------------------------------------

def test_validation_error_nan(client):
    # Send non-finite value (inf via 1e999) directly as json payload
    raw_payload = '{"x": [0.5, 1e999], "t": [0.1, 0.2], "y": [0.5, 0.4], "sigma": 0.01}'
    res = client.post("/v1/estimate", content=raw_payload, headers={"Content-Type": "application/json"})
    assert res.status_code == 422
    data = res.json()
    assert data["error_code"] == "VALIDATION_ERROR"
    assert "X-Request-ID" in res.headers
    assert any("non-finite value" in d for d in data.get("details", []))

def test_validation_error_length_mismatch(client):
    payload = {
        "x": [0.5],
        "t": [0.1, 0.2],
        "y": [0.5],
        "sigma": 0.01
    }
    res = client.post("/v1/estimate", json=payload)
    assert res.status_code == 422
    data = res.json()
    assert data["error_code"] == "VALIDATION_ERROR"

def test_validation_error_max_size_exceeded(client):
    payload = {
        "x": [0.5] * 1005,
        "t": [0.1] * 1005,
        "y": [0.5] * 1005,
        "sigma": 0.01
    }
    res = client.post("/v1/estimate", json=payload)
    assert res.status_code == 422
    data = res.json()
    assert data["error_code"] == "VALIDATION_ERROR"

# -------------------------------------------------------------------------------------------------
# Latency Profiling across all endpoints
# -------------------------------------------------------------------------------------------------

def test_record_endpoint_latencies(client):
    endpoints = {
        "GET /health": lambda: client.get("/health"),
        "GET /version": lambda: client.get("/version"),
        "GET /metrics": lambda: client.get("/metrics"),
        "POST /v1/placement": lambda: client.post("/v1/placement", json={"N": 10, "sigma": 0.01}),
        "POST /v1/field (fno)": lambda: client.post("/v1/field", json={"alpha": 0.10}),
        "POST /v1/field (solver)": lambda: client.post("/v1/field", json={"alpha": 5.0}),
        "POST /v1/estimate (sigma)": lambda: client.post("/v1/estimate", json={
            "x": [0.5]*10, "t": np.linspace(0.05, 0.95, 10).tolist(),
            "y": solve_heat_1d_exact(np.full(10, 0.5), np.linspace(0.05, 0.95, 10), 0.1).tolist(),
            "sigma": 0.01
        }),
        "POST /v1/diagnose (k=20)": lambda: client.post("/v1/diagnose", json={
            "readings": {
                "x": [0.5]*10, "t": np.linspace(0.05, 0.95, 10).tolist(),
                "y": solve_heat_1d_exact(np.full(10, 0.5), np.linspace(0.05, 0.95, 10), 0.1).tolist()
            },
            "baseline": {
                "x": [0.5]*20, "t": np.linspace(0.05, 0.95, 20).tolist(),
                "y": solve_heat_1d_exact(np.full(20, 0.5), np.linspace(0.05, 0.95, 20), 0.1).tolist()
            }
        }),
        "POST /v1/poisson (gaussian)": lambda: client.post("/v1/poisson", json={
            "source": {"type": "gaussian", "centers": [[0.5, 0.5]], "amplitudes": [1.0], "sigmas": [0.15]}
        }),
        "POST /v1/poisson (sine)": lambda: client.post("/v1/poisson", json={
            "source": {"type": "sine", "modes": [[2, 2]], "amplitudes": [1.0]}
        })
    }
    
    latencies = {}
    print("\n" + "="*70)
    print("SERVICE ENDPOINT CPU LATENCY BENCHMARK (10 repetitions each)")
    print("="*70)
    for name, call_fn in endpoints.items():
        # Warmup
        call_fn()
        times = []
        for _ in range(10):
            t0 = time.perf_counter()
            resp = call_fn()
            t_el = (time.perf_counter() - t0) * 1000.0
            assert resp.status_code == 200
            times.append(t_el)
        p50 = float(np.percentile(times, 50))
        p95 = float(np.percentile(times, 95))
        latencies[name] = {"p50_ms": p50, "p95_ms": p95}
        print(f"{name:<30} | p50: {p50:7.2f} ms | p95: {p95:7.2f} ms")
    print("="*70)
    
    # Check metrics
    m_resp = client.get("/metrics")
    assert m_resp.status_code == 200
    m_data = m_resp.json()
    assert m_data["requests_total"] > 50

def test_mode3plus_equivalence_50_datasets(client):
    """Verify that POST /v1/estimate mode3plus is bit-level equivalent to evaluate_mode3plus."""
    from tools.run_stress_matrix_v2 import precompute_surrogates, evaluate_mode3, evaluate_mode3plus
    prec = precompute_surrogates()
    
    max_abs_diff = 0.0
    max_rel_diff = 0.0
    
    for seed in range(50):
        rng = np.random.RandomState(seed + 42)
        alpha_true = float(10**rng.uniform(np.log10(0.02), np.log10(0.8)))
        N = int(rng.choice([5, 10, 15, 20]))
        sigma = float(rng.choice([0.01, 0.02, 0.05]))
        
        x_s = np.sort(rng.uniform(0.2, 0.8, size=N))
        t_s = np.sort(rng.uniform(0.05, 0.95, size=N))
        
        y_exact = solve_heat_1d_exact(x_s, t_s, alpha_true)
        noise = rng.normal(0, sigma, size=N)
        y_s = y_exact + noise
        
        # Benchmark path
        hat_m3, _, _ = evaluate_mode3(x_s, t_s, y_s, sigma, alpha_true, prec)
        hat_bench, _, _ = evaluate_mode3plus(x_s, t_s, y_s, sigma, alpha_true, hat_m3, prec)
        
        # Service API path
        payload = {
            "x_coords": x_s.tolist(),
            "t_coords": t_s.tolist(),
            "readings": y_s.tolist(),
            "sigma": sigma,
            "mode": "mode3plus"
        }
        res = client.post("/v1/estimate", json=payload)
        assert res.status_code == 200, res.text
        hat_api = res.json()["alpha_hat"]
        
        diff = abs(hat_bench - hat_api)
        rel_diff = diff / max(1e-6, hat_bench)
        if diff > max_abs_diff:
            max_abs_diff = diff
        if rel_diff > max_rel_diff:
            max_rel_diff = rel_diff
            
    assert max_abs_diff < 1e-6, f"Mode 3+ absolute diff exceeded 1e-6: {max_abs_diff}"
    assert max_rel_diff < 1e-6, f"Mode 3+ relative diff exceeded 1e-6: {max_rel_diff}"

def test_default_example_200_seeds_coverage_and_bias(client):
    """Verify 200-seed coverage and bias on the default example layout (uncherry-picked seeds 0..199).
    
    Default example layout:
    - 10 sensors at x = 0.50
    - t logarithmically spaced in [0.01, 1.0]
    - alpha_true = 0.10, sigma = 0.01 (Sensor accuracy default)
    """
    alpha_true = 0.10
    sigma = 0.01
    x_coords = [0.50] * 10
    t_coords = [0.0100, 0.0167, 0.0278, 0.0464, 0.0774, 0.1292, 0.2154, 0.3594, 0.5995, 1.0000]
    x_arr = np.array(x_coords)
    t_arr = np.array(t_coords)
    u_exact = np.sin(np.pi * x_arr) * np.exp(-alpha_true * np.pi**2 * t_arr)

    covered = 0
    rel_biases = []
    rel_errors = []

    for seed in range(200):
        rng = np.random.RandomState(seed)
        noise = rng.normal(0, sigma, size=10)
        y = u_exact + noise
        payload = {
            "x_coords": x_coords,
            "t_coords": t_coords,
            "readings": y.tolist(),
            "sigma": sigma,
            "mode": "mode3plus"
        }
        res = client.post("/v1/estimate", json=payload)
        assert res.status_code == 200, res.text
        data = res.json()
        ahat = data["alpha_hat"]
        ci = data["ci95"]
        if ci[0] <= alpha_true <= ci[1]:
            covered += 1
        rel_biases.append((ahat - alpha_true) / alpha_true)
        rel_errors.append(abs(ahat - alpha_true) / alpha_true)

    cov_pct = (covered / 200.0) * 100.0
    mean_bias_pct = np.mean(rel_biases) * 100.0
    median_err_pct = np.median(rel_errors) * 100.0

    print(f"\n[200-Seed Default Example Evaluation]")
    print(f"Coverage: {covered}/200 = {cov_pct:.1f}%")
    print(f"Mean Relative Bias: {mean_bias_pct:+.3f}%")
    print(f"Median Relative Error: {median_err_pct:.3f}%")

    # Assert standard statistical performance: nominal 95% Wald CI with >= 90% coverage
    assert cov_pct >= 90.0, f"Coverage {cov_pct:.1f}% was below 90.0% threshold"
    assert abs(mean_bias_pct) < 1.0, f"Mean relative bias {mean_bias_pct:.3f}% was >= 1.0%"
    assert median_err_pct < 3.0, f"Median relative error {median_err_pct:.3f}% was >= 3.0%"

# -------------------------------------------------------------------------------------------------
# Real-World Units Normalisation Layer Tests
# -------------------------------------------------------------------------------------------------

def test_real_units_recovery_cooling_and_heating(client):
    """Synthetic data generated in °C, metres, seconds with known alpha_real must recover alpha_real in 95% CI."""
    t_norm = np.array([0.0100, 0.0167, 0.0278, 0.0464, 0.0774, 0.1292, 0.2154, 0.3594, 0.5995, 1.0000])
    x_norm = np.full(10, 0.50)

    # Configuration 1: Standard cooling in °C, m, s
    L1 = 0.50      # metres
    T1 = 10.0      # seconds
    Tb1 = 20.0     # °C (boundary)
    Tp1 = 100.0    # °C (initial peak)
    alpha_norm1 = 0.10
    alpha_real1 = alpha_norm1 * (L1 ** 2) / T1  # 0.0025 m²/s
    delta_T1 = Tp1 - Tb1
    sigma_u = 0.005
    sigma_real1 = sigma_u * abs(delta_T1)  # 0.40 °C

    u_norm1 = np.sin(np.pi * x_norm) * np.exp(-alpha_norm1 * (np.pi ** 2) * t_norm)
    rng1 = np.random.RandomState(42)
    y_real1 = Tb1 + delta_T1 * u_norm1 + rng1.normal(0, sigma_real1, size=len(u_norm1))

    payload1 = {
        "x": (x_norm * L1).tolist(),
        "t": (t_norm * T1).tolist(),
        "y": y_real1.tolist(),
        "bar_length_m": L1,
        "test_duration_s": T1,
        "boundary_temperature": Tb1,
        "initial_peak_temperature": Tp1,
        "sigma": sigma_real1,
        "mode": "mode3plus"
    }

    res1 = client.post("/v1/estimate", json=payload1)
    assert res1.status_code == 200, res1.text
    d1 = res1.json()
    assert d1["units"] == "m²/s"
    assert d1["ci95"][0] <= alpha_real1 <= d1["ci95"][1], f"True {alpha_real1} not in CI {d1['ci95']}"
    assert abs(d1["alpha_hat"] - alpha_real1) / alpha_real1 < 0.06
    assert abs(d1["alpha_hat_normalized"] - alpha_norm1) / alpha_norm1 < 0.06
    assert d1["normalization"]["bar_length_m"] == L1
    assert d1["normalization"]["test_duration_s"] == T1
    assert d1["normalization"]["boundary_temperature"] == Tb1
    assert d1["normalization"]["initial_peak_temperature"] == Tp1
    assert d1["normalization"]["scale_factor"] == pytest.approx((L1**2)/T1, rel=1e-5)

    # Configuration 2: Heating case (Tp < Tb: cold bar heated from warm ends)
    L2 = 1.0       # metres
    T2 = 5.0       # seconds
    Tb2 = 100.0    # °C (boundary maintained hot)
    Tp2 = 20.0     # °C (initial center cold)
    alpha_norm2 = 0.10
    alpha_real2 = alpha_norm2 * (L2 ** 2) / T2  # 0.020 m²/s
    delta_T2 = Tp2 - Tb2  # -80.0 °C
    sigma_real2 = sigma_u * abs(delta_T2)  # 0.40 °C

    u_norm2 = np.sin(np.pi * x_norm) * np.exp(-alpha_norm2 * (np.pi ** 2) * t_norm)
    rng2 = np.random.RandomState(0)
    y_real2 = Tb2 + delta_T2 * u_norm2 + rng2.normal(0, sigma_real2, size=len(u_norm2))

    payload2 = {
        "x": (x_norm * L2).tolist(),
        "t": (t_norm * T2).tolist(),
        "y": y_real2.tolist(),
        "bar_length_m": L2,
        "test_duration_s": T2,
        "boundary_temperature": Tb2,
        "initial_peak_temperature": Tp2,
        "sigma": sigma_real2,
        "mode": "mode3plus"
    }

    res2 = client.post("/v1/estimate", json=payload2)
    assert res2.status_code == 200, res2.text
    d2 = res2.json()
    assert d2["units"] == "m²/s"
    assert d2["ci95"][0] <= alpha_real2 <= d2["ci95"][1], f"Heating true {alpha_real2} not in CI {d2['ci95']}"
    assert abs(d2["alpha_hat"] - alpha_real2) / alpha_real2 < 0.06
    assert abs(d2["alpha_hat_normalized"] - alpha_norm2) / alpha_norm2 < 0.06

def test_real_units_affine_invariance(client):
    """Affine-rescaling temperatures (Celsius to Fahrenheit) must produce mathematically identical normalized requests."""
    t_norm = np.array([0.0100, 0.0200, 0.0500, 0.1000, 0.2000, 0.4000, 0.8000, 1.0000])
    x_norm = np.full(8, 0.50)
    alpha_true = 0.10
    u_norm = np.sin(np.pi * x_norm) * np.exp(-alpha_true * (np.pi ** 2) * t_norm)

    # Celsius inputs
    Tb_C = 20.0
    Tp_C = 100.0
    sigma_C = 0.80
    rng = np.random.RandomState(99)
    y_C = Tb_C + (Tp_C - Tb_C) * u_norm + rng.normal(0, sigma_C, size=len(u_norm))

    # Fahrenheit affine scaling: T_F = 1.8 * T_C + 32.0, sigma_F = 1.8 * sigma_C
    Tb_F = 1.8 * Tb_C + 32.0
    Tp_F = 1.8 * Tp_C + 32.0
    sigma_F = 1.8 * sigma_C
    y_F = 1.8 * y_C + 32.0

    payload_C = {
        "x": x_norm.tolist(),
        "t": t_norm.tolist(),
        "y": y_C.tolist(),
        "boundary_temperature": Tb_C,
        "initial_peak_temperature": Tp_C,
        "sigma": sigma_C,
        "mode": "mode3plus"
    }

    payload_F = {
        "x": x_norm.tolist(),
        "t": t_norm.tolist(),
        "y": y_F.tolist(),
        "boundary_temperature": Tb_F,
        "initial_peak_temperature": Tp_F,
        "sigma": sigma_F,
        "mode": "mode3plus"
    }

    res_C = client.post("/v1/estimate", json=payload_C)
    res_F = client.post("/v1/estimate", json=payload_F)

    assert res_C.status_code == 200, res_C.text
    assert res_F.status_code == 200, res_F.text

    d_C = res_C.json()
    d_F = res_F.json()

    # Normalized estimates and statistics must be strictly identical under affine transformation
    assert d_C["alpha_hat_normalized"] == pytest.approx(d_F["alpha_hat_normalized"], rel=1e-5)
    assert d_C["ci95_normalized"][0] == pytest.approx(d_F["ci95_normalized"][0], rel=1e-5)
    assert d_C["ci95_normalized"][1] == pytest.approx(d_F["ci95_normalized"][1], rel=1e-5)
    assert d_C["effective_sigma"] == pytest.approx(d_F["effective_sigma"], rel=1e-5)
    assert d_C["chi2_dof"] == pytest.approx(d_F["chi2_dof"], rel=1e-5)

def test_real_units_validation_errors(client):
    """Backend must return clear HTTP 400 errors for invalid physical unit inputs."""
    base_payload = {
        "x": [0.2, 0.5, 0.8],
        "t": [0.1, 0.2, 0.3],
        "y": [0.8, 0.6, 0.4],
        "sigma": 0.01
    }

    # 1. T_peak == T_boundary
    p = dict(base_payload, boundary_temperature=50.0, initial_peak_temperature=50.0)
    r = client.post("/v1/estimate", json=p)
    assert r.status_code == 400
    assert "division by zero" in r.text or "cannot equal" in r.text

    # 2. Only one temperature provided
    p = dict(base_payload, boundary_temperature=50.0)
    r = client.post("/v1/estimate", json=p)
    assert r.status_code == 400
    assert "Both boundary_temperature and initial_peak_temperature" in r.text

    # 3. Only one dimension provided (bar_length_m without test_duration_s)
    p = dict(base_payload, bar_length_m=1.0)
    r = client.post("/v1/estimate", json=p)
    assert r.status_code == 400
    assert "Both bar_length_m and test_duration_s" in r.text

    # 4. Positions outside [0, L]
    p = dict(base_payload, bar_length_m=1.0, test_duration_s=2.0, x=[0.2, 1.25, 0.8])
    r = client.post("/v1/estimate", json=p)
    assert r.status_code == 400
    assert "Positions must be within [0, 1.0] m" in r.text

    # 5. Times outside [0, T]
    p = dict(base_payload, bar_length_m=1.0, test_duration_s=2.0, t=[0.1, 2.5, 1.0])
    r = client.post("/v1/estimate", json=p)
    assert r.status_code == 400
    assert "Times must be within [0, 2.0] s" in r.text

    # 6. Non-positive bar length
    p = dict(base_payload, bar_length_m=-0.5, test_duration_s=1.0)
    r = client.post("/v1/estimate", json=p)
    assert r.status_code == 400

def test_real_units_reasonableness_warning_on_unphysical_mix(client):
    """Normalised readings falling far outside [-0.5, 1.5] trigger warning without silent conversion."""
    # User provides Kelvin readings (~300 K) with Celsius boundaries (20°C, 100°C)
    # Normalized: u = (300 - 20) / 80 = 3.5 >> 1.5
    payload = {
        "x": [0.5, 0.5, 0.5],
        "t": [0.1, 0.2, 0.3],
        "y": [300.0, 295.0, 290.0],
        "boundary_temperature": 20.0,
        "initial_peak_temperature": 100.0,
        "sigma": 1.0
    }
    r = client.post("/v1/estimate", json=payload)
    assert r.status_code == 200
    d = r.json()
    warnings = d["flags"]["warnings"]
    expected_warning = "These readings don't look like cooling from your stated start. Check units or values."
    assert any(expected_warning in w for w in warnings), f"Warning not found in {warnings}"

def test_real_units_diagnose_endpoint(client):
    """Verify that /v1/diagnose accepts physical units, validates inputs, and echoes scaling metadata."""
    L = 0.5
    T = 10.0
    Tb = 20.0
    Tp = 100.0
    sigma_real = 0.80

    xb = np.full(20, 0.25)
    tb = np.linspace(0.5, 9.5, 20)
    yb = Tb + (Tp - Tb) * np.sin(np.pi * 0.5) * np.exp(-0.10 * (np.pi**2) * (tb / T))

    x_test = [0.25] * 10
    t_test = np.linspace(0.5, 9.0, 10).tolist()
    y_test = (Tb + (Tp - Tb) * np.sin(np.pi * 0.5) * np.exp(-0.10 * (np.pi**2) * (np.array(t_test) / T))).tolist()

    payload = {
        "readings": {"x": x_test, "t": t_test, "y": y_test},
        "baseline": {"x": xb.tolist(), "t": tb.tolist(), "y": yb.tolist()},
        "bar_length_m": L,
        "test_duration_s": T,
        "boundary_temperature": Tb,
        "initial_peak_temperature": Tp,
        "sigma": sigma_real
    }

    res = client.post("/v1/diagnose", json=payload)
    assert res.status_code == 200, res.text
    d = res.json()
    assert d["assigned_class"] in ["H", "A", "F", "C"]
    assert d["normalization"]["bar_length_m"] == L
    assert d["normalization"]["test_duration_s"] == T
    assert d["normalization"]["boundary_temperature"] == Tb
    assert d["normalization"]["initial_peak_temperature"] == Tp
    assert "alpha_fitted" in d["evidence_stats"]
    assert "alpha_fitted_normalized" in d["evidence_stats"]

def test_real_units_all_four_methods_with_nonunit_dimensions(client):
    """Verify all 4 estimation methods with L != 1, T != 1, T_edge != 0."""
    L = 0.2  # != 1
    T = 50.0 # != 1
    Tb = 15.0 # != 0
    Tp = 75.0
    alpha_true_norm = 0.10
    alpha_true_real = alpha_true_norm * (L**2) / T # 0.10 * 0.04 / 50 = 8.0e-5 m^2/s

    t_vals = [0.5, 1.0, 2.0, 4.0, 7.5, 12.5, 20.0, 30.0, 40.0, 50.0]
    x_vals = [0.10] * len(t_vals) # x/L = 0.5
    y_vals = []
    for t_s in t_vals:
        t_norm = t_s / T
        u_norm = np.sin(np.pi * 0.5) * np.exp(-alpha_true_norm * (np.pi**2) * t_norm)
        y_vals.append(float(Tb + (Tp - Tb) * u_norm))

    payload = {
        "x": x_vals,
        "t": t_vals,
        "y": y_vals,
        "bar_length_m": L,
        "test_duration_s": T,
        "boundary_temperature": Tb,
        "initial_peak_temperature": Tp,
        "sigma": 0.5
    }

    for mode in ["mode3plus", "mode3", "mode2", "declared_physics"]:
        p = dict(payload, mode=mode)
        if mode == "declared_physics":
            p["physics_config"] = {"u0_expr": "sin(pi*x)"}
        res = client.post("/v1/estimate", json=p)
        assert res.status_code == 200, f"Mode {mode} failed: {res.text}"
        data = res.json()
        alpha_hat = data["alpha_hat"]
        ci95 = data["ci95"]
        norm_alpha = data["alpha_hat_normalized"]

        # Within 10% of 8.0e-5 m^2/s
        assert 0.90 * alpha_true_real <= alpha_hat <= 1.10 * alpha_true_real, (
            f"Mode {mode}: alpha_hat {alpha_hat} outside 10% of {alpha_true_real}"
        )
        # CI contains true alpha
        assert ci95[0] <= alpha_true_real <= ci95[1], (
            f"Mode {mode}: CI {ci95} does not contain {alpha_true_real}"
        )
        assert norm_alpha == pytest.approx(alpha_true_norm, rel=0.05)

def test_real_units_heating_case(client):
    """Verify estimation when bar starts cold and ends are heated (T_peak < T_edge)."""
    L = 0.15
    T = 80.0
    Tb = 90.0 # Hot ends
    Tp = 20.0 # Cold start
    alpha_true_norm = 0.10
    alpha_true_real = alpha_true_norm * (L**2) / T

    t_vals = [1.0, 2.5, 5.0, 10.0, 20.0, 35.0, 50.0, 65.0, 80.0]
    x_vals = [0.075] * len(t_vals) # x/L = 0.5
    y_vals = []
    for t_s in t_vals:
        t_norm = t_s / T
        u_norm = np.sin(np.pi * 0.5) * np.exp(-alpha_true_norm * (np.pi**2) * t_norm)
        # T(t) = 90 + (20 - 90) * u_norm = 90 - 70 * u_norm (heating from 20 up towards 90)
        y_vals.append(float(Tb + (Tp - Tb) * u_norm))

    payload = {
        "x": x_vals,
        "t": t_vals,
        "y": y_vals,
        "bar_length_m": L,
        "test_duration_s": T,
        "boundary_temperature": Tb,
        "initial_peak_temperature": Tp,
        "sigma": 0.5,
        "mode": "mode3plus"
    }

    res = client.post("/v1/estimate", json=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert 0.90 * alpha_true_real <= data["alpha_hat"] <= 1.10 * alpha_true_real
    assert data["ci95"][0] <= alpha_true_real <= data["ci95"][1]
    assert data["alpha_hat_normalized"] == pytest.approx(0.10, rel=0.05)

def test_estimate_request_forbids_extra_fields(client):
    """EstimateRequest must reject unknown fields with HTTP 422 (extra='forbid')."""
    payload = {
        "x": [0.5, 0.5, 0.5],
        "t": [0.1, 0.2, 0.3],
        "y": [0.8, 0.6, 0.4],
        "sigma": 0.01,
        "unexpected_bogus_field": 12345
    }
    res = client.post("/v1/estimate", json=payload)
    assert res.status_code == 422
    assert "extra" in res.text.lower() or "unexpected_bogus_field" in res.text



