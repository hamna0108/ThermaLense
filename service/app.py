"""FastAPI Digital Twin Service Implementation.

Implements:
- POST /v1/estimate
- POST /v1/diagnose
- POST /v1/placement
- POST /v1/field
- POST /v1/poisson
- GET /health
- GET /version
- GET /metrics
"""

import os
import sys
import time
import math
import uuid
import json
import logging
import hashlib
import subprocess
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional

import numpy as np
import torch
from scipy.interpolate import CubicSpline, interp1d
import scipy.optimize as opt
from fastapi import FastAPI, Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from service.models import (
    EstimateRequest, EstimateResponse, EstimateFlags,
    DiagnoseRequest, DiagnoseResponse,
    PlacementRequest, PlacementResponse,
    FieldRequest, FieldResponse,
    PoissonRequest, PoissonResponse, PoissonErrors, PoissonTiming,
    PoissonGaussianSource, PoissonSineSource,
    HealthResponse, VersionResponse, ErrorDetail
)
from service.metrics import GLOBAL_METRICS
from service.security import parse_whitelisted_expression, SecurityError, ExpressionSecurityError

from src.paths import MODELS, RESULTS
from src.solvers.heat_1d import solve_heat_1d_exact
from src.v2.sigma_estimator import estimate_sigma_from_baseline
from src.v2.gof_gate import evaluate_goodness_of_fit, compute_gof_threshold
from src.v2.range_guard import range_guarded_mode3_inversion, check_bound_pinning
from src.v2.declared_physics import invert_with_declared_physics, solve_heat_1d_general

from src.models.fno2d import FNO2d
from src.models.linear_baseline import LinearPoissonBaseline
from src.solvers.poisson_2d import Poisson2DSolver

from tools.run_stress_matrix_v2 import (
    precompute_surrogates, evaluate_mode2, evaluate_mode3, evaluate_mode3plus,
    cramer_rao_bound, BOUND_LOG_LOW, BOUND_LOG_HIGH, GLR_THRESHOLDS
)

# Configure structured logging
logger = logging.getLogger("service")
logger.setLevel(logging.INFO)
log_handler = logging.StreamHandler()
log_handler.setFormatter(logging.Formatter('%(message)s'))
logger.handlers = [log_handler]

# Global application state loaded once at startup
APP_STATE: Dict[str, Any] = {}

def get_git_info():
    """Retrieve git commit hash and tags."""
    commit = "unknown"
    tags = []
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
        tags_raw = subprocess.check_output(
            ["git", "tag", "--points-at", "HEAD"], cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
        if tags_raw:
            tags = tags_raw.splitlines()
        else:
            all_tags = subprocess.check_output(
                ["git", "tag"], cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL
            ).strip().splitlines()
            tags = all_tags[-3:] if all_tags else []
    except Exception:
        pass
    return commit, tags

def compute_checkpoint_hashes():
    """Compute SHA-256 for all official checkpoints."""
    hashes = {}
    checkpoints = [
        "fno2d_heat.pt",
        "fno2d_poisson_v2.pt",
        "linear_baseline_poisson_v2.npz",
        "pinn_expD.pt"
    ]
    for ckpt in checkpoints:
        path = os.path.join(MODELS, ckpt)
        if os.path.exists(path):
            with open(path, "rb") as f:
                hashes[ckpt] = hashlib.sha256(f.read()).hexdigest()
        else:
            hashes[ckpt] = "missing"
    return hashes

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load models, lookup tables, and solver factorizations ONCE at startup."""
    t0 = time.time()
    logger.info(json.dumps({"event": "startup_begin", "message": "Preloading models and surrogates..."}))
    
    # 1. Precompute surrogate lookup tables (Mode 2, Mode 3, Mode 3+)
    prec = precompute_surrogates()
    APP_STATE["prec"] = prec
    
    # 2. Load 1D Heat FNO model
    heat_ckpt_path = os.path.join(MODELS, "fno2d_heat.pt")
    if os.path.exists(heat_ckpt_path):
        ckpt_heat = torch.load(heat_ckpt_path, map_location="cpu")
        fno_heat = FNO2d(modes1=16, modes2=12, width=32, use_hard_mask=ckpt_heat.get("use_hard_mask", False))
        fno_heat.load_state_dict(ckpt_heat["model_state_dict"])
        fno_heat.eval()
        APP_STATE["fno_heat"] = fno_heat
        APP_STATE["heat_log_alpha_mean"] = ckpt_heat["log_alpha_mean"].item()
        APP_STATE["heat_log_alpha_std"] = ckpt_heat["log_alpha_std"].item()
        logger.info(json.dumps({"event": "loaded_model", "model": "fno2d_heat.pt"}))
    else:
        logger.warning(json.dumps({"event": "missing_model", "model": "fno2d_heat.pt"}))
        
    # 3. Load 2D Poisson FNO v2 model
    poi_ckpt_path = os.path.join(MODELS, "fno2d_poisson_v2.pt")
    if os.path.exists(poi_ckpt_path):
        fno_poi = FNO2d(modes1=12, modes2=12, width=32, in_channels=3, out_channels=1, use_hard_mask=True)
        fno_poi.load_state_dict(torch.load(poi_ckpt_path, map_location="cpu"))
        fno_poi.eval()
        APP_STATE["fno_poisson"] = fno_poi
        logger.info(json.dumps({"event": "loaded_model", "model": "fno2d_poisson_v2.pt"}))
        
    # 4. Load 2D Poisson Linear Baseline
    poi_lin_path = os.path.join(MODELS, "linear_baseline_poisson_v2.npz")
    if os.path.exists(poi_lin_path):
        lin_poi = LinearPoissonBaseline().load(poi_lin_path)
        APP_STATE["lin_poisson"] = lin_poi
        logger.info(json.dumps({"event": "loaded_model", "model": "linear_baseline_poisson_v2.npz"}))
        
    # 5. Poisson Sparse Direct Solver (N=64 pre-factorized)
    APP_STATE["poisson_solver_64"] = Poisson2DSolver(N=64)
    logger.info(json.dumps({"event": "solver_init", "solver": "Poisson2DSolver(N=64)"}))
    
    # 6. Metadata hashes & Git info
    git_commit, git_tags = get_git_info()
    APP_STATE["git_commit"] = git_commit
    APP_STATE["git_tags"] = git_tags
    APP_STATE["checkpoint_sha256s"] = compute_checkpoint_hashes()
    
    elapsed = round((time.time() - t0) * 1000.0, 2)
    logger.info(json.dumps({
        "event": "startup_complete",
        "timing_ms": elapsed,
        "commit": git_commit[:8],
        "tags": git_tags
    }))
    
    yield
    
    logger.info(json.dumps({"event": "shutdown"}))

app = FastAPI(
    title="ThermaLens: Thermal & PDE Digital Twin API",
    description="Production-grade physical parameter estimation, sensor fault diagnosis, and PDE operator inference for ThermaLens.",
    version="1.0.0",
    lifespan=lifespan
)

# -------------------------------------------------------------------------------------------------
# Middleware & Exception Handlers (Request-ID, JSON Logging, No Bare 500s)
# -------------------------------------------------------------------------------------------------

@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = req_id
    t_start = time.perf_counter()
    
    endpoint = request.url.path
    GLOBAL_METRICS.record_request(endpoint)
    
    try:
        response = await call_next(request)
        latency_ms = round((time.perf_counter() - t_start) * 1000.0, 3)
        GLOBAL_METRICS.record_latency(endpoint, latency_ms)
        
        response.headers["X-Request-ID"] = req_id
        
        log_entry = {
            "timestamp": time.time(),
            "request_id": req_id,
            "method": request.method,
            "path": endpoint,
            "status_code": response.status_code,
            "latency_ms": latency_ms
        }
        logger.info(json.dumps(log_entry))
        return response
    except Exception as exc:
        latency_ms = round((time.perf_counter() - t_start) * 1000.0, 3)
        GLOBAL_METRICS.record_latency(endpoint, latency_ms)
        GLOBAL_METRICS.record_error()
        
        log_entry = {
            "timestamp": time.time(),
            "request_id": req_id,
            "method": request.method,
            "path": endpoint,
            "status_code": 500,
            "latency_ms": latency_ms,
            "error": str(exc)
        }
        logger.error(json.dumps(log_entry))
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error_code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected internal server error occurred.",
                "request_id": req_id
            },
            headers={"X-Request-ID": req_id}
        )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    GLOBAL_METRICS.record_error()
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    errors_detail = []
    for err in exc.errors():
        loc = " -> ".join(str(l) for l in err.get("loc", []))
        errors_detail.append(f"{loc}: {err.get('msg', 'validation error')}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error_code": "VALIDATION_ERROR",
            "message": "Input request validation failed.",
            "request_id": req_id,
            "details": errors_detail
        },
        headers={"X-Request-ID": req_id}
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    if exc.status_code >= 400 and exc.status_code < 500:
        GLOBAL_METRICS.record_refusal()
    else:
        GLOBAL_METRICS.record_error()
        
    error_code = "HTTP_ERROR"
    message = str(exc.detail)
    if isinstance(exc.detail, dict):
        error_code = exc.detail.get("error_code", error_code)
        message = exc.detail.get("message", message)
        
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": error_code,
            "message": message,
            "request_id": req_id
        },
        headers={"X-Request-ID": req_id}
    )

# -------------------------------------------------------------------------------------------------
# Anomaly Cascade Helper Functions
# -------------------------------------------------------------------------------------------------

def solve_heat_1d_jump(x, t, alpha0, alpha1, tc):
    u = np.zeros_like(t, dtype=float)
    early = t < tc
    late = ~early
    if np.any(early):
        u[early] = np.sin(np.pi * x[early]) * np.exp(-alpha0 * (np.pi**2) * t[early])
    if np.any(late):
        u[late] = np.sin(np.pi * x[late]) * np.exp(-np.pi**2 * (alpha0 * tc + alpha1 * (t[late] - tc)))
    return u

def compute_glr_baseline_informed(x_s, t_s, y_s, sigma, hat_a_base, tc_grid=np.arange(0.05, 0.75, 0.05)):
    y_pred0 = solve_heat_1d_exact(x_s, t_s, hat_a_base)
    rss0 = np.sum((y_pred0 - y_s)**2)
    best_rss = rss0
    best_tc = 0.5
    for tc in tc_grid:
        m_l = t_s >= tc
        if np.sum(m_l) >= 1:
            res1 = opt.minimize_scalar(
                lambda l: np.sum((solve_heat_1d_jump(x_s, t_s, hat_a_base, 10**l, tc) - y_s)**2),
                bounds=(BOUND_LOG_LOW, BOUND_LOG_HIGH), method='bounded'
            )
            rss = np.sum((solve_heat_1d_jump(x_s, t_s, hat_a_base, 10**res1.x, tc) - y_s)**2)
            if rss < best_rss:
                best_rss = rss
                best_tc = tc
    glr_stat = (rss0 - best_rss) / (sigma**2 + 1e-12)
    return float(glr_stat), float(best_tc), float(best_rss)

def fit_three_models_bic_detailed(x_s, t_s, y_s, sigma, gamma_f=7.456, gamma_c=1.5):
    N = len(t_s)
    res0 = opt.minimize_scalar(
        lambda l: np.sum((solve_heat_1d_exact(x_s, t_s, 10**l) - y_s)**2),
        bounds=(BOUND_LOG_LOW, BOUND_LOG_HIGH), method='bounded'
    )
    hat_alpha0 = float(10**res0.x)
    y_pred0 = solve_heat_1d_exact(x_s, t_s, hat_alpha0)
    rss0 = float(np.sum((y_pred0 - y_s)**2))
    chi2_0 = rss0 / (sigma**2 + 1e-12)
    bic_0 = chi2_0 + 1.0 * np.log(max(2, N))
    
    # Sensor fault LOO
    rss_f_list = []
    for k in range(N):
        idx = [i for i in range(N) if i != k]
        if len(idx) < 1:
            continue
        res_k = opt.minimize_scalar(
            lambda l: np.sum((solve_heat_1d_exact(x_s[idx], t_s[idx], 10**l) - y_s[idx])**2),
            bounds=(BOUND_LOG_LOW, BOUND_LOG_HIGH), method='bounded'
        )
        rss_f_list.append(float(np.sum((solve_heat_1d_exact(x_s[idx], t_s[idx], 10**res_k.x) - y_s[idx])**2)))
        
    best_fault_sensor = int(np.argmin(rss_f_list)) if rss_f_list else 0
    rss_f = min(rss_f_list) if rss_f_list else rss0
    chi2_f = rss_f / (sigma**2 + 1e-12)
    bic_f = chi2_f + 2.0 * np.log(max(2, N)) + gamma_f
    
    return {
        'N': N,
        'alpha_hat': hat_alpha0,
        'chi2_red': chi2_0 / max(1, N - 1),
        'bic_0': float(bic_0),
        'bic_f': float(bic_f),
        'chi2_0': float(chi2_0),
        'chi2_f': float(chi2_f),
        'best_fault_sensor': best_fault_sensor
    }

def predict_cascade_class(glr_stat, tau_cell, fit_res, alpha_hat, best_rss_c, sigma, gamma_c=1.5):
    if ((alpha_hat < 0.018) or (alpha_hat > 0.55)) and fit_res['chi2_red'] < 2.0:
        return 'A'
    N = fit_res['N']
    bic_0 = fit_res['bic_0']
    bic_f = fit_res['bic_f']
    chi2_c = best_rss_c / (sigma**2 + 1e-12)
    bic_c = chi2_c + 2.0 * np.log(max(2, N)) + gamma_c
    
    f_valid = bic_f < bic_0
    c_valid = glr_stat > tau_cell
    if f_valid and c_valid:
        return 'F' if bic_f <= bic_c else 'C'
    elif f_valid:
        return 'F'
    elif c_valid:
        return 'C'
    else:
        return 'A' if (alpha_hat < 0.018 or alpha_hat > 0.55) else 'H'

# -------------------------------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
def get_health():
    """Health check endpoint for container orchestrators."""
    return HealthResponse(
        status="healthy",
        service="digital-twin-inverse-service",
        version="1.0.0",
        timestamp=str(time.time())
    )

@app.get("/version", response_model=VersionResponse)
def get_version():
    """Version and provenance metadata: git commit, tags, and checkpoint SHA256 hashes."""
    return VersionResponse(
        name="ThermaLens",
        git_commit=APP_STATE.get("git_commit", "unknown"),
        git_tags=APP_STATE.get("git_tags", []),
        checkpoint_sha256s=APP_STATE.get("checkpoint_sha256s", {})
    )

@app.get("/metrics")
def get_metrics():
    """Prometheus-style metrics snapshot: request counts, errors, refusals, p50/p95 latency, flag shares."""
    return GLOBAL_METRICS.get_summary()

@app.post("/v1/estimate", response_model=EstimateResponse)
def post_estimate(req: EstimateRequest):
    """Parameter inversion with goodness-of-fit gating, range guard, and baseline estimation."""
    t0 = time.perf_counter()
    x_coords = req.x_coords or req.x
    t_coords = req.t_coords or req.t
    readings = req.readings or req.y
    x_s = np.array(x_coords, dtype=float)
    t_s = np.array(t_coords, dtype=float)
    y_s = np.array(readings, dtype=float)
    prec = APP_STATE.get("prec")
    if prec is None:
        prec = precompute_surrogates()
        APP_STATE["prec"] = prec
    warnings_list = []
    
    # 0. Secure Expression Parsing for Declared Physics
    u0_fn = None
    bc_fn = None
    source_fn = None
    alpha_fn = None
    bc_left_fn = None
    bc_right_fn = None

    if req.physics_config is not None:
        try:
            if req.physics_config.u0_expr:
                u0_fn = parse_whitelisted_expression(req.physics_config.u0_expr)
            if req.physics_config.bc_left_expr:
                bc_left_fn = parse_whitelisted_expression(req.physics_config.bc_left_expr)
            if req.physics_config.bc_right_expr:
                bc_right_fn = parse_whitelisted_expression(req.physics_config.bc_right_expr)
            if req.physics_config.source_expr:
                source_fn = parse_whitelisted_expression(req.physics_config.source_expr)
            if req.physics_config.alpha_expr:
                alpha_fn = parse_whitelisted_expression(req.physics_config.alpha_expr)
            if bc_left_fn is not None or bc_right_fn is not None:
                def combined_bc(t):
                    b0 = bc_left_fn(t=t) if bc_left_fn else 0.0
                    b1 = bc_right_fn(t=t) if bc_right_fn else 0.0
                    return (b0, b1)
                bc_fn = combined_bc
        except (SecurityError, ValueError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "SECURITY_VALIDATION_ERROR",
                    "message": f"Declared physics expression rejected by security sandbox: {str(e)}"
                }
            )
    elif req.physics is not None:
        u0_candidate = req.physics.get("u0_expr") or req.physics.get("u0_fn")
        if isinstance(u0_candidate, str):
            try:
                u0_fn = parse_whitelisted_expression(u0_candidate)
            except (SecurityError, ValueError) as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error_code": "SECURITY_VALIDATION_ERROR",
                        "message": f"Declared physics expression rejected by security sandbox: {str(e)}"
                    }
                )
        elif callable(u0_candidate):
            u0_fn = u0_candidate

    # 1. Determine effective sigma
    if req.sigma is not None:
        effective_sigma = float(req.sigma)
    elif req.baseline is not None:
        xb_coords = req.baseline.x_coords or req.baseline.x
        tb_coords = req.baseline.t_coords or req.baseline.t
        yb_readings = req.baseline.readings or req.baseline.y
        xb = np.array(xb_coords, dtype=float)
        tb = np.array(tb_coords, dtype=float)
        yb = np.array(yb_readings, dtype=float)
        k = len(yb)
        if k < 20:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "REFUSED_INSUFFICIENT_BASELINE",
                    "message": f"Measurement noise sigma was not provided and baseline readings k={k} < 20. Service requires declared sigma or k >= 20 baseline readings."
                }
            )
        sig_info = estimate_sigma_from_baseline(xb, tb, yb, min_readings=20, allow_fewer=False)
        effective_sigma = float(sig_info["sigma_hat"])
        warnings_list.extend(sig_info["warnings"])
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "REFUSED_INSUFFICIENT_BASELINE",
                "message": "Measurement noise sigma was not provided and no baseline was supplied. Service requires declared sigma or k >= 20 baseline readings."
            }
        )
        
    # 2. Execute estimation
    mode = req.mode.lower() if req.mode else "mode3plus"

    if req.physics_config is not None or req.physics is not None or mode == "declared_physics":
        res_d4 = invert_with_declared_physics(
            x_s, t_s, y_s, effective_sigma, alpha_true=0.1,
            u0_fn=u0_fn, bc_fn=bc_fn, source_fn=source_fn, alpha_fn=alpha_fn
        )
        hat_alpha = res_d4["alpha_hat"]
        se_log10 = float(np.sqrt(res_d4["crb"]) / (hat_alpha * np.log(10))) if res_d4["crb"] != np.inf and res_d4["crb"] > 0 else 0.1
        method_str = "Declared Physics (splu)"
        is_at_b, _, b_info = check_bound_pinning(hat_alpha, se_log10=se_log10, return_info=True)
    elif mode == "mode2":
        hat_alpha, _, _ = evaluate_mode2(x_s, t_s, y_s, effective_sigma, alpha_true=0.1, prec=prec)
        method_str = "Mode 2"
        is_at_b, _, b_info = check_bound_pinning(hat_alpha, return_info=True)
    elif mode == "mode3":
        hat_alpha, _, _ = evaluate_mode3(x_s, t_s, y_s, effective_sigma, alpha_true=0.1, prec=prec)
        method_str = "Mode 3"
        is_at_b, _, b_info = check_bound_pinning(hat_alpha, return_info=True)
    else: # mode3plus (default)
        hat_m3, _, _ = evaluate_mode3(x_s, t_s, y_s, effective_sigma, alpha_true=0.1, prec=prec)
        hat_alpha, _, _ = evaluate_mode3plus(x_s, t_s, y_s, effective_sigma, alpha_true=0.1, hat_m3=hat_m3, prec=prec)
        method_str = "Mode 3+"
        crb_check = cramer_rao_bound(hat_alpha, t_s, x_s, effective_sigma)
        se_log_chk = np.sqrt(crb_check) / (hat_alpha * np.log(10)) if (crb_check != np.inf and crb_check > 0) else None
        is_at_b, _, b_info = check_bound_pinning(hat_alpha, se_log10=se_log_chk, return_info=True)

    # 3. Compute 95% Wald Confidence Interval
    crb_val = cramer_rao_bound(hat_alpha, t_s, x_s, effective_sigma)
    if crb_val != np.inf and crb_val > 0:
        se_log = np.sqrt(crb_val) / (hat_alpha * np.log(10))
        ci_lo = float(10**(np.log10(hat_alpha) - 1.96 * se_log))
        ci_hi = float(10**(np.log10(hat_alpha) + 1.96 * se_log))
    else:
        ci_lo = float(max(1e-4, hat_alpha * 0.8))
        ci_hi = float(min(20.0, hat_alpha * 1.2))

    # 4. Goodness-of-Fit Gate (D2)
    gof_res = evaluate_goodness_of_fit(x_s, t_s, y_s, hat_alpha, effective_sigma)
    model_invalid = gof_res["model_invalid"]
    warnings_list.extend(gof_res["warnings"])
    
    out_of_range = bool(is_at_b)
    GLOBAL_METRICS.record_estimate_flags(model_invalid, out_of_range)
    
    timing_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    
    return EstimateResponse(
        alpha_hat=float(hat_alpha),
        ci95=[float(ci_lo), float(ci_hi)],
        method=method_str,
        flags=EstimateFlags(
            model_invalid=model_invalid,
            out_of_range=out_of_range,
            at_bound=b_info.get("flag_1pct", False),
            warnings=warnings_list
        ),
        effective_sigma=round(effective_sigma, 6),
        timing_ms=timing_ms,
        chi2_dof=round(float(gof_res.get("chi2_dof", 0.0)), 4),
        dw_stat=round(float(gof_res.get("dw_stat", 2.0)), 4) if gof_res.get("dw_stat") is not None else None,
    )

@app.post("/v1/diagnose", response_model=DiagnoseResponse)
def post_diagnose(req: DiagnoseRequest):
    """Sensor anomaly and physical change-point diagnosis via baseline-informed cascade."""
    t0 = time.perf_counter()
    x_coords = req.readings.x_coords or req.readings.x
    t_coords = req.readings.t_coords or req.readings.t
    readings = req.readings.readings or req.readings.y
    x_s = np.array(x_coords, dtype=float)
    t_s = np.array(t_coords, dtype=float)
    y_s = np.array(readings, dtype=float)
    
    xb_coords = req.baseline.x_coords or req.baseline.x
    tb_coords = req.baseline.t_coords or req.baseline.t
    yb_readings = req.baseline.readings or req.baseline.y
    xb = np.array(xb_coords, dtype=float)
    tb = np.array(tb_coords, dtype=float)
    yb = np.array(yb_readings, dtype=float)
    
    k = len(yb)
    if k < 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "REFUSED_INSUFFICIENT_BASELINE",
                "message": f"Diagnose service requires k >= 20 baseline readings (received k={k}). Refusing request."
            }
        )
        
    sig_info = estimate_sigma_from_baseline(xb, tb, yb, min_readings=20, allow_fewer=False)
    effective_sigma = float(req.sigma) if req.sigma is not None else float(sig_info["sigma_hat"])
    hat_a_base = float(sig_info["alpha_base"])
    
    N = len(t_s)
    tau_cell = GLR_THRESHOLDS.get((N, round(effective_sigma, 2)), 7.500)
    fit_res = fit_three_models_bic_detailed(x_s, t_s, y_s, effective_sigma)
    glr_stat, best_tc, best_rss_c = compute_glr_baseline_informed(x_s, t_s, y_s, effective_sigma, hat_a_base)
    
    assigned_class = predict_cascade_class(glr_stat, tau_cell, fit_res, fit_res["alpha_hat"], best_rss_c, effective_sigma)
    
    faulty_idx = fit_res["best_fault_sensor"] if assigned_class == "F" else None
    change_time = best_tc if assigned_class == "C" else None
    
    timing_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    
    return DiagnoseResponse(
        assigned_class=assigned_class,
        evidence_stats={
            "glr_stat": round(glr_stat, 3),
            "glr_threshold": round(tau_cell, 3),
            "bic_healthy": round(fit_res["bic_0"], 2),
            "bic_sensor_fault": round(fit_res["bic_f"], 2),
            "alpha_fitted": round(fit_res["alpha_hat"], 6),
            "alpha_baseline": round(hat_a_base, 6),
            "chi2_reduced": round(fit_res["chi2_red"], 3)
        },
        faulty_sensor_idx=faulty_idx,
        change_time=change_time,
        effective_sigma=round(effective_sigma, 6),
        timing_ms=timing_ms
    )

@app.post("/v1/placement", response_model=PlacementResponse)
def post_placement(req: PlacementRequest):
    """Deployable Two-Stage Adaptive Placement schedule."""
    t0 = time.perf_counter()
    N = req.N
    N1 = max(1, N // 2)
    N2 = N - N1
    
    t_stage1 = np.logspace(np.log10(req.t_min), np.log10(req.t_max), N1).tolist()
    
    # Nominal Stage 2 schedule assuming typical alpha=0.1
    alpha_nom = 0.10
    t_fine = np.linspace(req.t_min, req.t_max, 2000)
    w = (t_fine ** 2) * np.exp(-2.0 * alpha_nom * (np.pi ** 2) * t_fine)
    cdf = np.cumsum(w)
    cdf = (cdf - cdf[0]) / (cdf[-1] - cdf[0] + 1e-15)
    u_q = (np.arange(N2) + 0.5) / max(1, N2)
    inv_cdf = interp1d(cdf, t_fine, bounds_error=False, fill_value=(req.t_min, req.t_max))
    t_stage2_nom = inv_cdf(u_q).tolist()
    
    timing_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    
    return PlacementResponse(
        N=N,
        sigma=req.sigma,
        sensor_x=req.sensor_x,
        t_stage1=[round(t, 5) for t in t_stage1],
        t_stage2_nominal=[round(t, 5) for t in t_stage2_nom],
        strategy_description=(
            f"Two-stage adaptive placement at x={req.sensor_x}: Stage 1 ({N1} points) explores log-spaced time domain. "
            f"Stage 2 ({N2} points) dynamically concentrates around t* = 1 / (pi^2 * alpha_hat_1)."
        ),
        timing_ms=timing_ms
    )

@app.post("/v1/field", response_model=FieldResponse)
def post_field(req: FieldRequest):
    """Generate 2D spatial-temporal heat diffusion field u(x, t) on grid."""
    t0 = time.perf_counter()
    alpha = req.alpha
    Nx = req.Nx
    Nt = req.Nt
    method_req = (req.method or "auto").lower()
    
    # FNO is verified for alpha in [0.01, 1.0] under standard initial-boundary physics
    can_use_fno = bool(
        0.01 <= alpha <= 1.0 and
        req.physics is None and
        "fno_heat" in APP_STATE and
        Nx == 101 and Nt == 201
    )
    
    x_grid = np.linspace(0, 1, Nx).tolist()
    t_grid = np.linspace(0, 1, Nt).tolist()
    
    def run_fno():
        fno_model = APP_STATE["fno_heat"]
        mean_la = APP_STATE["heat_log_alpha_mean"]
        std_la = APP_STATE["heat_log_alpha_std"]
        t_mesh, x_mesh = np.meshgrid(np.linspace(0, 1, Nt), np.linspace(0, 1, Nx), indexing='ij')
        t_tensor = torch.tensor(2 * t_mesh - 1, dtype=torch.float32)
        x_tensor = torch.tensor(2 * x_mesh - 1, dtype=torch.float32)
        norm_alpha = (np.log10(alpha) - mean_la) / std_la
        alpha_tensor = torch.full_like(t_tensor, norm_alpha)
        grid_input = torch.stack([t_tensor, x_tensor, alpha_tensor], dim=0).unsqueeze(0)
        with torch.no_grad():
            u_out = fno_model(grid_input).squeeze().cpu().numpy()
        return u_out

    def run_solver():
        _, _, u_num = solve_heat_1d_general(Nx=Nx, Nt=Nt, alpha=alpha)
        return u_num

    if method_req == "compare":
        t_sol_0 = time.perf_counter()
        u_solver = run_solver()
        sol_ms = round((time.perf_counter() - t_sol_0) * 1000.0, 2)
        
        if can_use_fno or ("fno_heat" in APP_STATE and Nx == 101 and Nt == 201):
            t_fno_0 = time.perf_counter()
            u_fno = run_fno()
            fno_ms = round((time.perf_counter() - t_fno_0) * 1000.0, 2)
        else:
            u_fno = u_solver
            fno_ms = sol_ms

        norm_sol = float(np.linalg.norm(u_solver)) + 1e-12
        rel_diff = float(np.linalg.norm(u_fno - u_solver) / norm_sol)
        total_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        return FieldResponse(
            u_grid=[[round(float(v), 5) for v in row] for row in u_solver],
            x_grid=x_grid,
            t_grid=t_grid,
            method_used="compare",
            timing_ms=total_ms,
            solver_timing_ms=sol_ms,
            fno_timing_ms=fno_ms,
            relative_difference=round(rel_diff, 6),
            compare_grid=[[round(float(v), 5) for v in row] for row in u_fno]
        )
    elif method_req in ["solver", "numerical_solver"]:
        u_solver = run_solver()
        total_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        return FieldResponse(
            u_grid=[[round(float(v), 5) for v in row] for row in u_solver],
            x_grid=x_grid,
            t_grid=t_grid,
            method_used="numerical_solver",
            timing_ms=total_ms,
            solver_timing_ms=total_ms
        )
    elif method_req == "fno":
        if can_use_fno or ("fno_heat" in APP_STATE and Nx == 101 and Nt == 201):
            u_fno = run_fno()
            total_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            return FieldResponse(
                u_grid=[[round(float(v), 5) for v in row] for row in u_fno],
                x_grid=x_grid,
                t_grid=t_grid,
                method_used="fno",
                timing_ms=total_ms,
                fno_timing_ms=total_ms
            )
        else:
            u_solver = run_solver()
            total_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            return FieldResponse(
                u_grid=[[round(float(v), 5) for v in row] for row in u_solver],
                x_grid=x_grid,
                t_grid=t_grid,
                method_used="numerical_solver",
                timing_ms=total_ms,
                solver_timing_ms=total_ms
            )
    else:  # auto
        if can_use_fno:
            u_fno = run_fno()
            total_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            return FieldResponse(
                u_grid=[[round(float(v), 5) for v in row] for row in u_fno],
                x_grid=x_grid,
                t_grid=t_grid,
                method_used="fno",
                timing_ms=total_ms,
                fno_timing_ms=total_ms
            )
        else:
            u_solver = run_solver()
            total_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            return FieldResponse(
                u_grid=[[round(float(v), 5) for v in row] for row in u_solver],
                x_grid=x_grid,
                t_grid=t_grid,
                method_used="numerical_solver",
                timing_ms=total_ms,
                solver_timing_ms=total_ms
            )

@app.post("/v1/poisson", response_model=PoissonResponse)
def post_poisson(req: PoissonRequest):
    """Solve 2D Poisson equation -nabla^2 u = f using exact sparse solver, FNO, and Linear baseline."""
    t0_all = time.perf_counter()
    N = req.grid_size
    src_cfg = req.source
    src_type = src_cfg.get("type", "").lower()
    
    # 1. Build Source Field f(x, y)
    solver = APP_STATE.get("poisson_solver_64")
    if solver is None or solver.N != N:
        solver = Poisson2DSolver(N=N)
        
    X, Y = solver.X, solver.Y
    f_grid = np.zeros((N, N), dtype=np.float32)
    high_freq = False
    
    if src_type == "gaussian":
        try:
            g_src = PoissonGaussianSource(**src_cfg)
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
        for c, a, s in zip(g_src.centers, g_src.amplitudes, g_src.sigmas):
            r2 = (X - c[0])**2 + (Y - c[1])**2
            f_grid += a * np.exp(-r2 / (2.0 * s**2 + 1e-12)).astype(np.float32)
    elif src_type == "sine":
        try:
            s_src = PoissonSineSource(**src_cfg)
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
        for m, a in zip(s_src.modes, s_src.amplitudes):
            if m[0] > 4 or m[1] > 4:
                high_freq = True
            f_grid += a * (m[0]**2 + m[1]**2) * (np.pi**2) * np.sin(m[0] * np.pi * X) * np.sin(m[1] * np.pi * Y)
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown source type '{src_type}'. Supported: 'gaussian' or 'sine'."
        )

    # 2. Exact Sparse LU Solve
    t_exact_0 = time.perf_counter()
    u_exact = solver.solve(f_grid)
    exact_ms = round((time.perf_counter() - t_exact_0) * 1000.0, 3)

    # 3. FNO Operator Prediction
    t_fno_0 = time.perf_counter()
    fno_poi = APP_STATE.get("fno_poisson")
    if fno_poi is not None:
        coords = torch.from_numpy(np.stack([X, Y], axis=0)).float()
        f_tensor = torch.from_numpy(f_grid).unsqueeze(0).unsqueeze(0).float()
        fno_in = torch.cat([f_tensor, coords.unsqueeze(0)], dim=1)
        with torch.no_grad():
            u_fno = fno_poi(fno_in).squeeze().cpu().numpy()
    else:
        u_fno = u_exact.copy()
    fno_ms = round((time.perf_counter() - t_fno_0) * 1000.0, 3)

    # 4. Linear Ridge Baseline Prediction
    t_lin_0 = time.perf_counter()
    lin_poi = APP_STATE.get("lin_poisson")
    if lin_poi is not None:
        u_lin = lin_poi.predict(f_grid)
    else:
        u_lin = u_exact.copy()
    linear_ms = round((time.perf_counter() - t_lin_0) * 1000.0, 3)

    # 5. Relative Errors
    norm_exact = float(np.linalg.norm(u_exact)) + 1e-12
    err_fno_exact = float(np.linalg.norm(u_fno - u_exact) / norm_exact)
    err_lin_exact = float(np.linalg.norm(u_lin - u_exact) / norm_exact)
    norm_fno = float(np.linalg.norm(u_fno)) + 1e-12
    err_fno_lin = float(np.linalg.norm(u_fno - u_lin) / norm_fno)

    total_ms = round((time.perf_counter() - t0_all) * 1000.0, 2)

    return PoissonResponse(
        exact_field=[[round(float(v), 5) for v in row] for row in u_exact],
        fno_field=[[round(float(v), 5) for v in row] for row in u_fno],
        linear_field=[[round(float(v), 5) for v in row] for row in u_lin],
        relative_errors=PoissonErrors(
            rel_l2_fno_vs_exact=round(err_fno_exact, 6),
            rel_l2_linear_vs_exact=round(err_lin_exact, 6),
            rel_l2_fno_vs_linear=round(err_fno_lin, 6)
        ),
        timing_ms=PoissonTiming(
            exact_ms=exact_ms,
            fno_ms=fno_ms,
            linear_ms=linear_ms,
            total_ms=total_ms
        ),
        high_frequency_source=high_freq
    )

# -------------------------------------------------------------------------------------------------
# Static Frontend Files Mount (served at /)
# -------------------------------------------------------------------------------------------------
from fastapi.staticfiles import StaticFiles

STATIC_DIR = os.path.join(REPO_ROOT, "service", "static")
if os.path.exists(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

