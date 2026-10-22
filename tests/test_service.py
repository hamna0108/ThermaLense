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
    assert "Novatore Digital Twin" in res.text
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
