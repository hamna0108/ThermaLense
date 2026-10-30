"""ThermaLens Challenge Batch Runner.

Usage:
    python -m challenge.run_challenge --cases <file.jsonl|file.json|file.csv> --out <dir> --seed 20260101 --config challenge/config.json [--check-repro] [--verify-exact]
"""

import os
import sys
import json
import csv
import time
import math
import ast
import argparse
import shutil
import subprocess
from typing import Dict, Any, List, Optional, Tuple, Union, Callable

import numpy as np
import torch
import scipy
from scipy.interpolate import RegularGridInterpolator

# Package versions for run_log
import fastapi
import pydantic

# ThermaLens in-process imports
from service.app import (
    app,
    APP_STATE,
    precompute_surrogates,
    post_estimate,
    post_field,
    post_diagnose,
    fit_three_models_bic_detailed,
    solve_heat_1d_exact
)
from service.models import (
    EstimateRequest,
    DiagnoseRequest,
    FieldRequest,
    SensorReadings,
    BaselineData,
    PhysicsConfig
)
from src.v2.declared_physics import solve_heat_1d_general, invert_with_declared_physics
from src.solvers.poisson_2d import Poisson2DSolver, solve_poisson_2d_exact, manufactured_source_2d
from src.v2.range_guard import check_bound_pinning
from src.v2.gof_gate import evaluate_goodness_of_fit
from src.models.fno2d import FNO2d
from src.paths import MODELS


class FileLevelError(Exception):
    """Exception raised when an input file cannot be opened, parsed, or contains no usable cases."""
    pass


# =================================================================================================
# 1. AST WHITELIST EVALUATOR FOR SAFE EXPRESSIONS
# =================================================================================================

ALLOWED_AST_FUNCS = {
    "sin": np.sin,
    "cos": np.cos,
    "exp": np.exp,
    "sqrt": np.sqrt
}

ALLOWED_AST_NODES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Call, ast.Constant,
    ast.Name, ast.Load, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow,
    ast.UAdd, ast.USub
)

def evaluate_safe_ast(expr_str: str, allowed_vars: Tuple[str, ...] = ("x",)) -> Callable:
    """Compile and safely evaluate mathematical expressions using AST whitelist."""
    if not isinstance(expr_str, str) or not expr_str.strip():
        raise ValueError("Expression must be a non-empty string.")
    if len(expr_str) > 250:
        raise ValueError(f"Expression too long ({len(expr_str)} > 250 characters).")
    try:
        tree = ast.parse(expr_str.strip(), mode='eval')
    except SyntaxError as e:
        raise ValueError(f"Syntax error in expression '{expr_str}': {e}")

    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_AST_NODES):
            raise ValueError(f"Disallowed syntax element '{type(node).__name__}' in expression.")
        if isinstance(node, ast.Name):
            if node.id not in allowed_vars and node.id != "pi" and node.id not in ALLOWED_AST_FUNCS:
                raise ValueError(f"Disallowed variable '{node.id}'. Allowed: {allowed_vars}, pi, functions.")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_AST_FUNCS:
                raise ValueError(f"Disallowed function call in expression.")

    def _eval_node(n, env):
        if isinstance(n, ast.Expression):
            return _eval_node(n.body, env)
        if isinstance(n, ast.Constant):
            return n.value
        if isinstance(n, ast.Name):
            if n.id == "pi":
                return np.pi
            return env[n.id]
        if isinstance(n, ast.UnaryOp):
            val = _eval_node(n.operand, env)
            return +val if isinstance(n.op, ast.UAdd) else -val
        if isinstance(n, ast.BinOp):
            l = _eval_node(n.left, env)
            r = _eval_node(n.right, env)
            if isinstance(n.op, ast.Add): return l + r
            if isinstance(n.op, ast.Sub): return l - r
            if isinstance(n.op, ast.Mult): return l * r
            if isinstance(n.op, ast.Div): return l / r
            if isinstance(n.op, ast.Pow): return l ** r
        if isinstance(n, ast.Call):
            fn = ALLOWED_AST_FUNCS[n.func.id]
            arg = _eval_node(n.args[0], env)
            return fn(arg)
        raise ValueError("Unsupported AST node.")

    def safe_callable(**kwargs):
        env = {k: np.asarray(v, dtype=float) for k, v in kwargs.items()}
        res = _eval_node(tree, env)
        first_arr = next(iter(env.values()))
        if np.isscalar(res) or (isinstance(res, np.ndarray) and res.ndim == 0):
            return np.full_like(first_arr, float(res), dtype=float)
        return res

    return safe_callable


SUPPORTED_IC_TYPES = {"sin_pi_x", "constant", "linear", "step", "gaussian", "sine_modes", "safe_expression"}
SUPPORTED_POISSON_SOURCE_TYPES = {"sin_sin", "constant", "gaussian", "sine_modes", "safe_expression"}


def parse_initial_condition(
    ic_dict: Optional[Dict[str, Any]],
    domain_x: Tuple[float, float] = (0.0, 1.0)
) -> Tuple[Optional[Callable], Optional[str]]:
    """Parse heat equation initial condition into a callable u0(x)."""
    x_min, x_max = domain_x
    span_x = max(1e-9, x_max - x_min)

    if ic_dict is None:
        return (lambda x: np.sin(np.pi * (x - x_min) / span_x)), None

    if not isinstance(ic_dict, dict):
        return None, "initial_condition must be an object with a 'type' field."

    ic_type = str(ic_dict.get("type", "sin_pi_x")).strip().lower()

    if ic_type not in SUPPORTED_IC_TYPES:
        return None, f"Unsupported initial_condition type: '{ic_type}'. Supported types: {sorted(list(SUPPORTED_IC_TYPES))}."

    if ic_type == "sin_pi_x":
        return (lambda x: np.sin(np.pi * (x - x_min) / span_x)), None

    elif ic_type == "constant":
        val = float(ic_dict.get("value", 0.0))
        return (lambda x: np.full_like(x, val, dtype=float)), None

    elif ic_type == "linear":
        slope = float(ic_dict.get("slope", 1.0))
        intercept = float(ic_dict.get("intercept", 0.0))
        return (lambda x: slope * x + intercept), None

    elif ic_type == "step":
        step_x = float(ic_dict.get("step_x", 0.5 * (x_min + x_max)))
        val_left = float(ic_dict.get("val_left", 1.0))
        val_right = float(ic_dict.get("val_right", 0.0))
        return (lambda x: np.where(x < step_x, val_left, val_right)), None

    elif ic_type == "gaussian":
        mu = float(ic_dict.get("mu", 0.5 * (x_min + x_max)))
        std = float(ic_dict.get("std", 0.1))
        amp = float(ic_dict.get("amp", 1.0))
        return (lambda x: amp * np.exp(-((x - mu) ** 2) / (2.0 * max(1e-9, std) ** 2))), None

    elif ic_type == "sine_modes":
        modes = ic_dict.get("modes", [{"k": 1, "amp": 1.0}])
        def _sine_modes(x):
            out = np.zeros_like(x, dtype=float)
            for m in modes:
                k = int(m.get("k", 1))
                amp = float(m.get("amp", 1.0))
                out += amp * np.sin(k * np.pi * (x - x_min) / span_x)
            return out
        return _sine_modes, None

    elif ic_type == "safe_expression":
        expr = ic_dict.get("expr", "")
        try:
            fn = evaluate_safe_ast(expr, allowed_vars=("x",))
            return (lambda x: fn(x=x)), None
        except Exception as e:
            return None, f"Invalid safe_expression in initial_condition: {e}"

    return None, f"Unsupported initial_condition type: '{ic_type}'."


def parse_poisson_source(
    source_dict: Optional[Dict[str, Any]],
    domain_x: Tuple[float, float] = (0.0, 1.0),
    domain_y: Tuple[float, float] = (0.0, 1.0)
) -> Tuple[Optional[Callable], Optional[str]]:
    """Parse 2D Poisson source term f(X, Y)."""
    x_min, x_max = domain_x
    y_min, y_max = domain_y
    span_x = max(1e-9, x_max - x_min)
    span_y = max(1e-9, y_max - y_min)

    if source_dict is None:
        return manufactured_source_2d, None

    if not isinstance(source_dict, dict):
        return None, "source_term must be an object with a 'type' field."

    st_type = str(source_dict.get("type", "sin_sin")).strip().lower()

    if st_type not in SUPPORTED_POISSON_SOURCE_TYPES:
        return None, f"Unsupported source_term type: '{st_type}'. Supported types: {sorted(list(SUPPORTED_POISSON_SOURCE_TYPES))}."

    if st_type == "sin_sin":
        amp = float(source_dict.get("amp", 2.0 * (np.pi ** 2)))
        return (lambda X, Y: amp * np.sin(np.pi * (X - x_min) / span_x) * np.sin(np.pi * (Y - y_min) / span_y)), None

    elif st_type == "constant":
        val = float(source_dict.get("value", 1.0))
        return (lambda X, Y: np.full_like(X, val, dtype=float)), None

    elif st_type == "gaussian":
        x0 = float(source_dict.get("x0", 0.5 * (x_min + x_max)))
        y0 = float(source_dict.get("y0", 0.5 * (y_min + y_max)))
        std = float(source_dict.get("std", 0.1))
        amp = float(source_dict.get("amp", 1.0))
        return (lambda X, Y: amp * np.exp(-(((X - x0)**2 + (Y - y0)**2) / (2.0 * max(1e-9, std)**2)))), None

    elif st_type == "sine_modes":
        modes = source_dict.get("modes", [{"kx": 1, "ky": 1, "amp": 1.0}])
        def _sine_modes(X, Y):
            out = np.zeros_like(X, dtype=float)
            for m in modes:
                kx = int(m.get("kx", 1))
                ky = int(m.get("ky", 1))
                amp = float(m.get("amp", 1.0))
                out += amp * np.sin(kx * np.pi * (X - x_min) / span_x) * np.sin(ky * np.pi * (Y - y_min) / span_y)
            return out
        return _sine_modes, None

    elif st_type == "safe_expression":
        expr = source_dict.get("expr", "")
        try:
            fn = evaluate_safe_ast(expr, allowed_vars=("x", "y"))
            return (lambda X, Y: fn(x=X, y=Y)), None
        except Exception as e:
            return None, f"Invalid safe_expression in source_term: {e}"

    return None, f"Unsupported source_term type: '{st_type}'."


# =================================================================================================
# 2. CANONICAL ADAPTER FUNCTION
# Handles mentor schema (JSONL/JSON) and legacy flat format transparently.
# =================================================================================================

def adapt_case(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Map external / mentor case dictionary to internal canonical schema.

    Preserves backward compatibility with earlier challenge flat test formats.
    """
    def _first_val(keys: List[str], default=None):
        for k in keys:
            if k in raw and raw[k] is not None:
                return raw[k]
        return default

    def _to_float_list(val: Any) -> Optional[List[Any]]:
        if val is None:
            return None
        if isinstance(val, (list, tuple, np.ndarray)):
            items = []
            for v in val:
                if v is None:
                    items.append(None)
                elif isinstance(v, (int, float)):
                    items.append(float(v))
                elif isinstance(v, str):
                    v_str = v.strip().lower()
                    if v_str in ("nan", "+nan", "-nan"):
                        items.append(float("nan"))
                    elif v_str in ("inf", "+inf", "infinity", "+infinity"):
                        items.append(float("inf"))
                    elif v_str in ("-inf", "-infinity"):
                        items.append(float("-inf"))
                    else:
                        try:
                            items.append(float(v))
                        except (ValueError, TypeError):
                            items.append(v)
                else:
                    try:
                        items.append(float(v))
                    except (ValueError, TypeError):
                        items.append(v)
            return items
        if isinstance(val, str):
            val = val.strip()
            if not val:
                return None
            if val.startswith("[") and val.endswith("]"):
                try:
                    parsed = json.loads(val)
                    return _to_float_list(parsed)
                except Exception:
                    pass
            cleaned = val.replace(";", ",").replace("\t", ",").replace(" ", ",")
            parts = [p.strip() for p in cleaned.split(",") if p.strip()]
            return _to_float_list(parts)
        return None

    def _to_float(val: Any) -> Optional[float]:
        if val is None:
            return None
        try:
            f = float(val)
            return f if math.isfinite(f) else f
        except (ValueError, TypeError):
            return None

    # Detect Mentor Schema vs Legacy Flat Schema
    is_mentor_format = ("equation" in raw or "observations" in raw or "boundary_conditions" in raw)

    raw_case_id = _first_val(["case_id", "id", "name", "case", "test_id", "sample_id"], default=None)
    raw_case_id_missing = (raw_case_id is None or str(raw_case_id).strip() == "")
    case_id = str(raw_case_id) if not raw_case_id_missing else "case_unknown"

    raw_eq = _first_val(["equation", "case_type", "type"], default=None)
    if raw_eq is not None:
        eq_str = str(raw_eq).strip().lower()
        if eq_str in ("heat_1d", "heat"):
            equation = "heat_1d"
        elif eq_str in ("poisson_2d", "poisson"):
            equation = "poisson_2d"
        else:
            equation = eq_str
    else:
        equation = "heat_1d"

    # Domain & Grid
    raw_domain = raw.get("domain") or {}
    domain_x = raw_domain.get("x", [0.0, 1.0]) if isinstance(raw_domain, dict) else [0.0, 1.0]
    domain_t = raw_domain.get("t", [0.0, 1.0]) if isinstance(raw_domain, dict) else [0.0, 1.0]
    domain_y = raw_domain.get("y", [0.0, 1.0]) if isinstance(raw_domain, dict) else [0.0, 1.0]

    raw_grid = raw.get("grid") or {}
    grid_nx = raw_grid.get("nx", 101) if isinstance(raw_grid, dict) else 101
    grid_nt = raw_grid.get("nt", 101) if isinstance(raw_grid, dict) else 101
    grid_ny = raw_grid.get("ny", 64) if isinstance(raw_grid, dict) else 64

    # Boundary conditions & initial conditions
    boundary_conditions = raw.get("boundary_conditions")
    initial_condition = raw.get("initial_condition")
    source_term = raw.get("source_term")

    # Known parameters
    known_params = raw.get("known_parameters") or {}
    infer_parameters = raw.get("infer_parameters", ["alpha"])

    # Observations
    raw_obs = raw.get("observations")
    x_coords = None
    t_coords = None
    readings = None

    if raw_obs is not None and isinstance(raw_obs, list):
        # Mentor format observations: list of {"x": ..., "t": ..., "u": ...}
        x_list = []
        t_list = []
        u_list = []
        for item in raw_obs:
            if isinstance(item, dict):
                x_list.append(item.get("x"))
                t_list.append(item.get("t") if "t" in item else item.get("y"))
                u_list.append(item.get("u") if "u" in item else item.get("reading"))
            elif isinstance(item, (list, tuple)) and len(item) >= 3:
                x_list.append(item[0])
                t_list.append(item[1])
                u_list.append(item[2])
        x_coords = _to_float_list(x_list)
        t_coords = _to_float_list(t_list)
        readings = _to_float_list(u_list)
    else:
        # Legacy flat format
        x_coords = _to_float_list(_first_val(["x_coords", "x", "xs", "x_coord", "positions", "x_sensors"]))
        t_coords = _to_float_list(_first_val(["t_coords", "t", "ts", "t_coord", "times", "t_sensors", "y_coords", "ys"]))
        readings = _to_float_list(_first_val(["readings", "y", "reading", "temperatures", "values", "u", "u_obs"]))

    # Sigma, Alpha Nominal, Reference, Truth
    sigma = _to_float(known_params.get("sigma") if is_mentor_format else _first_val(["sigma", "noise", "std", "noise_std"]))
    alpha_nominal = _to_float(known_params.get("alpha_nominal") if is_mentor_format else _first_val(["alpha_nominal", "alpha_base", "nominal_alpha"]))
    truth_alpha = _to_float(known_params.get("truth_alpha") if is_mentor_format else _first_val(["truth_alpha", "alpha_true", "alpha_truth"]))
    truth_field = known_params.get("truth_field") if is_mentor_format else _first_val(["truth_field", "field_true", "field_truth"])

    # Reference / Baseline
    raw_ref = known_params.get("reference") if is_mentor_format else _first_val(["reference", "baseline", "ref", "healthy_ref"])
    adapted_ref = None
    if isinstance(raw_ref, dict):
        rx = _to_float_list(raw_ref.get("x_coords") or raw_ref.get("x") or raw_ref.get("xs"))
        rt = _to_float_list(raw_ref.get("t_coords") or raw_ref.get("t") or raw_ref.get("ts"))
        ry = _to_float_list(raw_ref.get("readings") or raw_ref.get("y") or raw_ref.get("ys"))
        if rx is not None or rt is not None or ry is not None:
            adapted_ref = {"x_coords": rx, "t_coords": rt, "readings": ry}
    elif raw_ref is not None:
        adapted_ref = raw_ref

    # Physical scaling
    L = _to_float(known_params.get("L") if is_mentor_format else _first_val(["L", "bar_length_m", "bar_length"]))
    T = _to_float(known_params.get("T") if is_mentor_format else _first_val(["T", "test_duration_s", "test_duration"]))
    T_boundary = _to_float(known_params.get("T_boundary") if is_mentor_format else _first_val(["T_boundary", "boundary_temperature"]))
    T_peak = _to_float(known_params.get("T_peak") if is_mentor_format else _first_val(["T_peak", "initial_peak_temperature"]))

    # Convert truth field to list of lists if numpy
    if truth_field is not None:
        try:
            arr = np.array(truth_field, dtype=float)
            if arr.ndim == 2:
                truth_field = arr.tolist()
        except Exception:
            truth_field = None

    return {
        "case_id": case_id,
        "raw_case_id_missing": raw_case_id_missing,
        "equation": equation,
        "case_type": equation,
        "domain_x": domain_x,
        "domain_t": domain_t,
        "domain_y": domain_y,
        "grid_nx": grid_nx,
        "grid_nt": grid_nt,
        "grid_ny": grid_ny,
        "initial_condition": initial_condition,
        "source_term": source_term,
        "boundary_conditions": boundary_conditions,
        "infer_parameters": infer_parameters,
        "x_coords": x_coords,
        "t_coords": t_coords,
        "readings": readings,
        "sigma": sigma,
        "reference": adapted_ref,
        "L": L,
        "T": T,
        "T_boundary": T_boundary,
        "T_peak": T_peak,
        "alpha_nominal": alpha_nominal,
        "truth_alpha": truth_alpha,
        "truth_field": truth_field,
        "physics_config": raw.get("physics_config")
    }


# =================================================================================================
# 3. CASE INPUT VALIDATOR
# =================================================================================================

def validate_case(case: Dict[str, Any]) -> List[str]:
    """Validate case schema and physical inputs prior to execution.

    Stage 5 Rule: Reject only if 0 observations. Warn if < 4 observations.
    Unsupported initial_condition or source_term must produce status 'invalid_input'.
    """
    errors: List[str] = []

    # 1. Check equation
    eq = case.get("equation", "heat_1d")
    if eq not in ("heat_1d", "poisson_2d", "heat", "poisson"):
        errors.append(f"Unknown equation '{eq}'. Supported equations are: 'heat_1d', 'poisson_2d'.")

    # 2. Required case_id
    if case.get("raw_case_id_missing"):
        errors.append("Missing required field: case_id.")

    # 3. Initial condition / source term validation
    if eq in ("heat_1d", "heat"):
        ic = case.get("initial_condition")
        if ic is not None:
            _, ic_err = parse_initial_condition(ic, domain_x=case.get("domain_x", (0.0, 1.0)))
            if ic_err:
                errors.append(ic_err)
    elif eq in ("poisson_2d", "poisson"):
        st = case.get("source_term")
        if st is not None:
            _, st_err = parse_poisson_source(st, domain_x=case.get("domain_x", (0.0, 1.0)), domain_y=case.get("domain_y", (0.0, 1.0)))
            if st_err:
                errors.append(st_err)

    # 4. Check observations presence
    x_coords = case.get("x_coords")
    t_coords = case.get("t_coords")
    readings = case.get("readings")

    if x_coords is None or t_coords is None or readings is None:
        errors.append("Missing required observations (x, t, u).")
        return errors

    # Stage 5: Reject ONLY if 0 observations!
    if len(readings) == 0:
        errors.append("No observations provided: observations list is empty.")
        return errors

    nx = len(x_coords)
    nt = len(t_coords)
    ny = len(readings)

    if ny != nt:
        errors.append(f"readings has {ny} values but t_coords has {nt}.")
    if nx != nt:
        errors.append(f"x_coords has {nx} values but t_coords has {nt}.")
    if nx != ny and nx == nt:
        errors.append(f"x_coords has {nx} values but readings has {ny}.")

    # 5. Check finite numbers
    def _find_non_finite(arr: List[Any], name: str):
        for idx, val in enumerate(arr):
            if val is None:
                errors.append(f"{name} contains empty (None) value at index {idx}.")
                return
            if not isinstance(val, (int, float)):
                errors.append(f"{name} contains invalid non-numeric value '{val}' at index {idx}.")
                return
            if not math.isfinite(float(val)):
                nan_or_inf = "NaN" if math.isnan(float(val)) else "Inf"
                errors.append(f"{name} contains non-finite value ({nan_or_inf}) at index {idx}.")
                return

    _find_non_finite(x_coords, "x_coords")
    _find_non_finite(t_coords, "t_coords")
    _find_non_finite(readings, "readings")

    # Range and geometry checks
    has_finite_vals = not any("non-finite" in e or "empty" in e or "invalid non-numeric" in e or "has " in e for e in errors)
    if has_finite_vals and nx == nt == ny:
        seen_points: Dict[Tuple[float, float], int] = {}
        for idx, (x_val, t_val) in enumerate(zip(x_coords, t_coords)):
            pt_key = (round(float(x_val), 7), round(float(t_val), 7))
            if pt_key in seen_points:
                orig_idx = seen_points[pt_key]
                errors.append(
                    f"Duplicate sensor reading at position x={x_val} and time/y={t_val} (indices {orig_idx} and {idx})."
                )
                break
            else:
                seen_points[pt_key] = idx

        L = case.get("L")
        T = case.get("T")
        if L is not None and L > 0:
            for idx, x_val in enumerate(x_coords):
                if float(x_val) < -1e-6 or float(x_val) > L + 1e-6:
                    errors.append(f"Position x={x_val} at index {idx} is outside physical bar domain [0, {L}].")
                    break
        if T is not None and T > 0 and eq in ("heat_1d", "heat"):
            for idx, t_val in enumerate(t_coords):
                if float(t_val) < -1e-6 or float(t_val) > T + 1e-6:
                    errors.append(f"Time t={t_val} at index {idx} is outside test duration window [0, {T}].")
                    break

        T_b = case.get("T_boundary")
        T_p = case.get("T_peak")
        if T_b is not None and T_p is not None:
            if abs(float(T_p) - float(T_b)) < 1e-7:
                errors.append(f"T_peak ({T_p}) cannot equal T_boundary ({T_b}): peak temperature must differ from boundary temperature.")

    # Reference check
    raw_ref = case.get("reference")
    if raw_ref is not None:
        if not isinstance(raw_ref, dict):
            errors.append("Supplied reference must be an object with x_coords, t_coords, and readings.")
        else:
            rx = raw_ref.get("x_coords")
            rt = raw_ref.get("t_coords")
            ry = raw_ref.get("readings")
            if rx is None or rt is None or ry is None:
                errors.append("Supplied reference is missing required coordinates.")
            else:
                if not (len(rx) == len(rt) == len(ry)):
                    errors.append(f"Supplied reference lengths do not match: {len(rx)}, {len(rt)}, {len(ry)}.")
                if len(ry) < 20:
                    errors.append(f"Supplied reference has {len(ry)} readings, but at least 20 readings are required for baseline calibration.")
                _find_non_finite(rx, "reference x_coords")
                _find_non_finite(rt, "reference t_coords")
                _find_non_finite(ry, "reference readings")

    return errors


# =================================================================================================
# 4. RUNNER INITIALIZATION & CONTEXT
# =================================================================================================

def init_runner(config: Dict[str, Any], seed: int) -> Dict[str, Any]:
    """Precompute surrogates and preload trained neural models into memory."""
    print(f"[Init] Initializing ThermaLens Runner (seed={seed})...")
    np.random.seed(seed)
    torch.manual_seed(seed)

    if "prec" not in APP_STATE:
        prec = precompute_surrogates()
        APP_STATE["prec"] = prec
    else:
        prec = APP_STATE["prec"]

    heat_ckpt_path = os.path.join(MODELS, "fno2d_heat.pt")
    if os.path.exists(heat_ckpt_path) and "fno_heat" not in APP_STATE:
        try:
            ckpt_heat = torch.load(heat_ckpt_path, map_location="cpu")
            fno_heat = FNO2d(modes1=16, modes2=12, width=32, use_hard_mask=ckpt_heat.get("use_hard_mask", False))
            fno_heat.load_state_dict(ckpt_heat["model_state_dict"])
            fno_heat.eval()
            APP_STATE["fno_heat"] = fno_heat
            APP_STATE["heat_log_alpha_mean"] = ckpt_heat["log_alpha_mean"].item()
            APP_STATE["heat_log_alpha_std"] = ckpt_heat["log_alpha_std"].item()
            print("[Init] FNO Heat 1D model loaded successfully.")
        except Exception as e:
            print(f"[Init] Warning: Could not load FNO heat model: {e}")

    poi_ckpt_path = os.path.join(MODELS, "fno2d_poisson_v2.pt")
    if os.path.exists(poi_ckpt_path) and "fno_poisson" not in APP_STATE:
        try:
            fno_poi = FNO2d(modes1=12, modes2=12, width=32, in_channels=3, out_channels=1, use_hard_mask=True)
            fno_poi.load_state_dict(torch.load(poi_ckpt_path, map_location="cpu"))
            fno_poi.eval()
            APP_STATE["fno_poisson"] = fno_poi
            print("[Init] FNO Poisson 2D model loaded successfully.")
        except Exception as e:
            print(f"[Init] Warning: Could not load FNO Poisson model: {e}")

    poi_lin_path = os.path.join(MODELS, "linear_baseline_poisson_v2.npz")
    if os.path.exists(poi_lin_path) and "lin_poisson" not in APP_STATE:
        try:
            from src.models.linear_baseline import LinearPoissonBaseline
            lin_poi = LinearPoissonBaseline().load(poi_lin_path)
            APP_STATE["lin_poisson"] = lin_poi
            print("[Init] Linear Poisson baseline model loaded successfully.")
        except Exception as e:
            print(f"[Init] Warning: Could not load Linear Poisson baseline: {e}")

    print("[Init] Initialization complete.")
    return {"prec": prec, "seed": seed}


# =================================================================================================
# 5. EXACT VERIFICATION SUITE (STAGE 4)
# =================================================================================================

def verify_exact_suite() -> bool:
    """Verify numerical solver against exact analytical benchmarks.

    Asserts all relative errors < 1e-3:
    Heat Benchmarks:
    - Zero Dirichlet ends: u(x, t) = sin(pi * x) * exp(-alpha * pi^2 * t) for alpha in {0.02, 0.10, 0.50}
    - Dynamic Unequal ends (0, 1): u(x, t) = x + exp(-alpha * pi^2 * t) * sin(pi * x) for alpha in {0.02, 0.10, 0.50}
    - Dynamic One insulated end: u(x, t) = exp(-alpha * pi^2 * t / 4) * sin(pi * x / 2) for alpha in {0.02, 0.10, 0.50}
    - Dynamic Insulated at x=0, Dir 0 at x=1: u(x, t) = exp(-alpha * pi^2 * t / 4) * cos(pi * x / 2) for alpha in {0.02, 0.10, 0.50}
    - Mentor 2-observation parameter inversion: alpha_hat close to 0.10
    Poisson Benchmarks:
    - (a) Baseline: u = sin(pi*x) * sin(pi*y), zero Dirichlet
    - (b) Neumann on x edges, zero Dirichlet on y edges: u = cos(pi*x) * sin(pi*y)
    - (c) Unequal Dirichlet edges: u = x + sin(pi*x) * sin(pi*y)
    """
    print("\n[Verify-Exact] Running Stage 4 Analytical Verification Suite...")
    tol = 1e-3
    Nx, Nt = 101, 201
    alphas = [0.02, 0.10, 0.50]

    # 1. Zero Dirichlet ends
    for a in alphas:
        xg, tg, ug = solve_heat_1d_general(Nx=Nx, Nt=Nt, alpha=a, u0_fn=lambda x: np.sin(np.pi * x),
                                           bc_left=("dirichlet", 0.0), bc_right=("dirichlet", 0.0))
        X_m, T_m = np.meshgrid(xg, tg)
        u_exact = np.sin(np.pi * X_m) * np.exp(-a * (np.pi ** 2) * T_m)
        err = float(np.linalg.norm(ug - u_exact) / np.linalg.norm(u_exact))
        print(f"  Heat Benchmark [Zero ends, alpha={a}]: Rel L2 error = {err:.3e}")
        assert err < tol, f"Failed for alpha={a}: error {err} >= {tol}"

    # 2. Dynamic Benchmark (a): Unequal Dirichlet ends (0, 1), start x + sin(pi*x)
    for a in alphas:
        xg, tg, ug = solve_heat_1d_general(Nx=Nx, Nt=Nt, alpha=a, u0_fn=lambda x: x + np.sin(np.pi * x),
                                           bc_left=("dirichlet", 0.0), bc_right=("dirichlet", 1.0))
        X_m, T_m = np.meshgrid(xg, tg)
        u_exact = X_m + np.exp(-a * (np.pi ** 2) * T_m) * np.sin(np.pi * X_m)
        err = float(np.linalg.norm(ug - u_exact) / np.linalg.norm(u_exact))
        print(f"  Heat Dynamic (a) [Unequal ends (0, 1), alpha={a}]: Rel L2 error = {err:.3e}")
        assert err < tol, f"Dynamic (a) failed for alpha={a}: error {err} >= {tol}"

    # 3. Dynamic Benchmark (b): One insulated end, start sin(pi*x/2)
    for a in alphas:
        xg, tg, ug = solve_heat_1d_general(Nx=Nx, Nt=Nt, alpha=a, u0_fn=lambda x: np.sin(0.5 * np.pi * x),
                                           bc_left=("dirichlet", 0.0), bc_right=("neumann", 0.0))
        X_m, T_m = np.meshgrid(xg, tg)
        u_exact = np.exp(-a * (np.pi ** 2) * T_m / 4.0) * np.sin(0.5 * np.pi * X_m)
        err = float(np.linalg.norm(ug - u_exact) / np.linalg.norm(u_exact))
        print(f"  Heat Dynamic (b) [Dir 0 left, Neu 0 right, alpha={a}]: Rel L2 error = {err:.3e}")
        assert err < tol, f"Dynamic (b) failed for alpha={a}: error {err} >= {tol}"

    # 4. Dynamic Benchmark (c): Insulated at x=0, Dir 0 at x=1, start cos(pi*x/2)
    for a in alphas:
        xg, tg, ug = solve_heat_1d_general(Nx=Nx, Nt=Nt, alpha=a, u0_fn=lambda x: np.cos(0.5 * np.pi * x),
                                           bc_left=("neumann", 0.0), bc_right=("dirichlet", 0.0))
        X_m, T_m = np.meshgrid(xg, tg)
        u_exact = np.exp(-a * (np.pi ** 2) * T_m / 4.0) * np.cos(0.5 * np.pi * X_m)
        err = float(np.linalg.norm(ug - u_exact) / np.linalg.norm(u_exact))
        print(f"  Heat Dynamic (c) [Neu 0 left, Dir 0 right, alpha={a}]: Rel L2 error = {err:.3e}")
        assert err < tol, f"Dynamic (c) failed for alpha={a}: error {err} >= {tol}"

    # 5. Mentor 2-observation test
    x_obs = [0.25, 0.5]
    t_obs = [0.1, 0.2]
    y_obs = [0.64065, 0.82087]
    inv_res = invert_with_declared_physics(x_s=x_obs, t_s=t_obs, y_s=y_obs, sigma=None, alpha_true=0.10)
    hat_alpha = inv_res["alpha_hat"]
    err_d = abs(hat_alpha - 0.10)
    print(f"  Heat Benchmark (d) [Mentor 2-obs inversion]: alpha_hat = {hat_alpha:.5f}, Abs error = {err_d:.3e}")
    assert err_d < tol, f"Benchmark (d) failed: error {err_d} >= {tol}"

    # 6. Poisson Benchmark (a): Baseline zero Dirichlet
    p_solver = Poisson2DSolver(Nx=65, Ny=65)
    f_p_a = lambda X, Y: 2.0 * (np.pi ** 2) * np.sin(np.pi * X) * np.sin(np.pi * Y)
    u_p_a = p_solver.solve(f_p_a)
    u_p_a_exact = np.sin(np.pi * p_solver.X) * np.sin(np.pi * p_solver.Y)
    err_p_a = float(np.linalg.norm(u_p_a - u_p_a_exact) / np.linalg.norm(u_p_a_exact))
    print(f"  Poisson Benchmark (a) [Zero Dirichlet]: Rel L2 error = {err_p_a:.3e}")
    assert err_p_a < tol, f"Poisson (a) failed: error {err_p_a} >= {tol}"

    # 7. Poisson Benchmark (b): Neumann on x edges, zero Dirichlet on y edges
    bc_p_b = {
        "x_min": {"type": "neumann", "value": 0.0},
        "x_max": {"type": "neumann", "value": 0.0},
        "y_min": {"type": "dirichlet", "value": 0.0},
        "y_max": {"type": "dirichlet", "value": 0.0}
    }
    f_p_b = lambda X, Y: 2.0 * (np.pi ** 2) * np.cos(np.pi * X) * np.sin(np.pi * Y)
    u_p_b = p_solver.solve(f_p_b, bc=bc_p_b)
    u_p_b_exact = np.cos(np.pi * p_solver.X) * np.sin(np.pi * p_solver.Y)
    err_p_b = float(np.linalg.norm(u_p_b - u_p_b_exact) / np.linalg.norm(u_p_b_exact))
    print(f"  Poisson Benchmark (b) [Neumann on X, Dir 0 on Y]: Rel L2 error = {err_p_b:.3e}")
    assert err_p_b < tol, f"Poisson (b) failed: error {err_p_b} >= {tol}"

    # 8. Poisson Benchmark (c): Unequal Dirichlet edges
    bc_p_c = {
        "x_min": {"type": "dirichlet", "value": 0.0},
        "x_max": {"type": "dirichlet", "value": 1.0},
        "y_min": {"type": "dirichlet", "value": lambda x: x},
        "y_max": {"type": "dirichlet", "value": lambda x: x}
    }
    f_p_c = lambda X, Y: 2.0 * (np.pi ** 2) * np.sin(np.pi * X) * np.sin(np.pi * Y)
    u_p_c = p_solver.solve(f_p_c, bc=bc_p_c)
    u_p_c_exact = p_solver.X + np.sin(np.pi * p_solver.X) * np.sin(np.pi * p_solver.Y)
    err_p_c = float(np.linalg.norm(u_p_c - u_p_c_exact) / np.linalg.norm(u_p_c_exact))
    print(f"  Poisson Benchmark (c) [Unequal Dirichlet]: Rel L2 error = {err_p_c:.3e}")
    assert err_p_c < tol, f"Poisson (c) failed: error {err_p_c} >= {tol}"

    print("[Verify-Exact] ALL EXACT ANALYTICAL BENCHMARKS PASSED (errors < 1e-3).\n")
    return True


# =================================================================================================
# 6. SIMULATOR & REFERENCE HELPER
# =================================================================================================

def simulate_healthy_reference(
    alpha_nominal: float,
    L: Optional[float] = None,
    T: Optional[float] = None,
    T_boundary: Optional[float] = None,
    T_peak: Optional[float] = None,
    sigma: Optional[float] = None,
    count: int = 25,
    rng: Optional[np.random.RandomState] = None
) -> Dict[str, List[float]]:
    """Simulate a healthy reference run with at least 20 readings using the simulator."""
    if rng is None:
        rng = np.random.RandomState(42)

    k = max(20, count)
    has_physical_scale = (L is not None and T is not None)
    if has_physical_scale:
        alpha_norm = float(alpha_nominal * T / (L ** 2))
    else:
        alpha_norm = float(alpha_nominal)

    x_norm_grid = np.linspace(0.15, 0.85, 5)
    t_norm_grid = np.linspace(0.10, 0.90, max(4, int(np.ceil(k / 5))))
    x_mesh, t_mesh = np.meshgrid(x_norm_grid, t_norm_grid)
    x_norm_flat = x_mesh.flatten()[:k]
    t_norm_flat = t_mesh.flatten()[:k]

    u_norm = np.sin(np.pi * x_norm_flat) * np.exp(-alpha_norm * (np.pi ** 2) * t_norm_flat)
    effective_sigma = sigma if (sigma is not None and sigma > 0) else 0.01
    y_norm = u_norm + rng.normal(0, effective_sigma, size=k)

    if has_physical_scale:
        x_phys = (x_norm_flat * L).tolist()
        t_phys = (t_norm_flat * T).tolist()
        if T_boundary is not None and T_peak is not None:
            delta_T = T_peak - T_boundary
            y_phys = (y_norm * delta_T + T_boundary).tolist()
        else:
            y_phys = y_norm.tolist()
        return {"x_coords": x_phys, "t_coords": t_phys, "readings": y_phys}
    else:
        return {"x_coords": x_norm_flat.tolist(), "t_coords": t_norm_flat.tolist(), "readings": y_norm.tolist()}


# =================================================================================================
# 7. HEAT CASE RUNNER (STAGES 1, 2, 3, 5)
# =================================================================================================

def _estimate_alpha_helper(
    x_coords: List[float],
    t_coords: List[float],
    readings: List[float],
    sigma: Optional[float],
    is_zero_bc: bool,
    is_sin_ic: bool,
    is_std_domain: bool,
    L: Optional[float],
    T: Optional[float],
    T_boundary: Optional[float],
    T_peak: Optional[float],
    truth_alpha: Optional[float],
    u0_fn: Any,
    bc_left: Any,
    bc_right: Any,
    domain_x: Tuple[float, float],
    domain_t: Tuple[float, float],
    grid_nx: int,
    grid_nt: int,
    mode: str = "mode3plus"
) -> Tuple[Optional[float], Optional[List[float]], Dict[str, Any]]:
    """Helper function to run parameter estimation across standard in-distribution and arbitrary BCs paths."""
    N_obs = len(readings)
    has_physical_scale = (L is not None and T is not None and L > 0 and T > 0)

    if is_zero_bc and is_sin_ic and is_std_domain and N_obs >= 4:
        est_req = EstimateRequest(
            x_coords=x_coords,
            t_coords=t_coords,
            readings=readings,
            sigma=sigma,
            bar_length_m=L,
            test_duration_s=T,
            boundary_temperature=T_boundary,
            initial_peak_temperature=T_peak,
            mode=mode
        )
        est_resp = post_estimate(est_req)
        return est_resp.alpha_hat, est_resp.ci95, (est_resp.flags or {})
    else:
        if has_physical_scale:
            x_norm_inv = [xv / L for xv in x_coords]
            t_norm_inv = [tv / T for tv in t_coords]
            if T_boundary is not None and T_peak is not None and abs(T_peak - T_boundary) > 1e-7:
                delta_T = T_peak - T_boundary
                y_norm_inv = [(yv - T_boundary) / delta_T for yv in readings]
                sigma_norm = (sigma / delta_T) if (sigma is not None and sigma > 0) else None
            else:
                y_norm_inv = readings
                sigma_norm = sigma
            alpha_true_norm = (truth_alpha * T / (L ** 2)) if truth_alpha is not None else 0.10
        else:
            x_norm_inv = x_coords
            t_norm_inv = t_coords
            y_norm_inv = readings
            sigma_norm = sigma
            alpha_true_norm = truth_alpha or 0.10

        inv_res = invert_with_declared_physics(
            x_s=x_norm_inv,
            t_s=t_norm_inv,
            y_s=y_norm_inv,
            sigma=sigma_norm,
            alpha_true=alpha_true_norm,
            u0_fn=u0_fn,
            bc_left=bc_left,
            bc_right=bc_right,
            domain_x=domain_x,
            domain_t=domain_t,
            Nx=grid_nx,
            Nt=grid_nt
        )
        hat_a = inv_res["alpha_hat"]
        ci_a = inv_res["ci95"]
        if has_physical_scale:
            scale_fac = (L ** 2) / T
            alpha_hat = hat_a * scale_fac
            ci95 = [ci_a[0] * scale_fac, ci_a[1] * scale_fac] if ci_a is not None else None
        else:
            alpha_hat = hat_a
            ci95 = ci_a
        return alpha_hat, ci95, inv_res


def run_heat_case(case: Dict[str, Any], config: Dict[str, Any], app_context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute end-to-end evaluation for a 1D heat diffusion case with two-tier dispatch."""
    case_id = case["case_id"]
    timing_breakdown = {}
    ood_warnings = []
    case_notes = []

    # Coordinate & sensor readings
    x_coords = case["x_coords"]
    t_coords = case["t_coords"]
    readings = case["readings"]
    N_obs = len(readings)
    sigma = case.get("sigma")
    reference = case.get("reference")
    alpha_nominal = case.get("alpha_nominal")
    truth_alpha = case.get("truth_alpha")
    truth_field = case.get("truth_field")

    # Domain & Grid (interpolate or recompute; never silently use another grid)
    domain_x = tuple(case.get("domain_x", (0.0, 1.0)))
    domain_t = tuple(case.get("domain_t", (0.0, 1.0)))
    grid_nx = int(case.get("grid_nx", config.get("Nx", 101)))
    grid_nt = int(case.get("grid_nt", config.get("Nt", 101)))

    # Boundaries and Initial Conditions
    raw_bcs = case.get("boundary_conditions") or {}
    bc_dict = {}
    for edge, spec in raw_bcs.items():
        if isinstance(spec, dict):
            b_type = spec.get("type", "dirichlet")
            b_val = spec.get("value", 0.0)
            if isinstance(b_val, str):
                try:
                    b_val = float(b_val)
                except ValueError:
                    var = "y" if edge in ("x_min", "x_max") else "x"
                    fn = evaluate_safe_ast(b_val, allowed_vars=(var,))
                    b_val = (lambda coords, fn=fn, var=var: fn(**{var: coords}))
            bc_dict[edge] = {"type": b_type, "value": b_val}
        else:
            bc_dict[edge] = spec
    bc_left = bc_dict.get("x_min", {"type": "dirichlet", "value": 0.0})
    bc_right = bc_dict.get("x_max", {"type": "dirichlet", "value": 0.0})

    ic_dict = case.get("initial_condition")
    u0_fn, _ = parse_initial_condition(ic_dict, domain_x=domain_x)

    # Physical scaling
    L = case.get("L")
    T = case.get("T")
    T_boundary = case.get("T_boundary")
    T_peak = case.get("T_peak")
    has_physical_scale = (L is not None and T is not None and L > 0 and T > 0)

    # Stage 5 Warning: fewer than 4 readings
    if N_obs < 4:
        ood_warnings.append("interval unreliable with this few readings")

    # Check In-Distribution Criteria for Neural FNO
    # 1. Zero Dirichlet boundaries at both ends
    def _is_zero_dirichlet(bc_val):
        if isinstance(bc_val, dict):
            return bc_val.get("type", "dirichlet").lower() == "dirichlet" and abs(float(bc_val.get("value", 0.0))) < 1e-6
        if isinstance(bc_val, (tuple, list)):
            return str(bc_val[0]).lower() == "dirichlet" and abs(float(bc_val[1])) < 1e-6
        return abs(float(bc_val)) < 1e-6

    is_zero_bc = _is_zero_dirichlet(bc_left) and _is_zero_dirichlet(bc_right)
    # 2. Initial condition sin_pi_x
    is_sin_ic = (ic_dict is None or str(ic_dict.get("type", "sin_pi_x")).strip().lower() == "sin_pi_x")
    # 3. Standard dimensionless domain [0, 1]
    is_std_domain = (abs(domain_x[0]) < 1e-6 and abs(domain_x[1] - 1.0) < 1e-6 and
                     abs(domain_t[0]) < 1e-6 and abs(domain_t[1] - 1.0) < 1e-6)

    # ---------------------------------------------------------------------------------------------
    # Stage 1: Parameter Estimation
    # ---------------------------------------------------------------------------------------------
    t0_est = time.perf_counter()

    alpha_hat, ci95, est_flags = _estimate_alpha_helper(
        x_coords=x_coords,
        t_coords=t_coords,
        readings=readings,
        sigma=sigma,
        is_zero_bc=is_zero_bc,
        is_sin_ic=is_sin_ic,
        is_std_domain=is_std_domain,
        L=L,
        T=T,
        T_boundary=T_boundary,
        T_peak=T_peak,
        truth_alpha=truth_alpha,
        u0_fn=u0_fn,
        bc_left=bc_left,
        bc_right=bc_right,
        domain_x=domain_x,
        domain_t=domain_t,
        grid_nx=grid_nx,
        grid_nt=grid_nt,
        mode=config.get("mode", "mode3plus")
    )

    t_est_ms = round((time.perf_counter() - t0_est) * 1000.0, 2)
    timing_breakdown["estimate_ms"] = t_est_ms

    # Stage 5: Missing sigma handling
    if (sigma is None or sigma <= 0) and N_obs < 4:
        ci95 = None
        case_notes.append("not available: noise level unknown")

    # Alpha relative error and interval coverage
    alpha_rel_error = None
    if truth_alpha is not None and truth_alpha > 0 and alpha_hat is not None:
        alpha_rel_error = float(abs(alpha_hat - truth_alpha) / truth_alpha)

    in_ci = None
    if ci95 is not None and len(ci95) == 2 and ci95[0] is not None and ci95[1] is not None and truth_alpha is not None:
        in_ci = bool(ci95[0] <= truth_alpha <= ci95[1])

    # ---------------------------------------------------------------------------------------------
    # Stage 2: Two Tiers Field Prediction (Stage 3)
    # ---------------------------------------------------------------------------------------------
    t0_field = time.perf_counter()

    # Determine Tier: in-distribution requires zero BCs, sin_pi_x, std domain, AND alpha in [0.01, 1.0]
    alpha_for_tier = alpha_hat if alpha_hat is not None else (alpha_nominal if alpha_nominal is not None else 0.10)
    is_in_distribution = (is_zero_bc and is_sin_ic and is_std_domain and (0.01 <= alpha_for_tier <= 1.0))

    field_grid = None
    method_used = None
    field_fno_out_of_domain = None
    field_fno_rel_l2 = None

    if is_in_distribution:
        tier = "fno"
        method_used = "fno"
        # Run FNO Heat
        fld_req = FieldRequest(
            alpha=alpha_for_tier,
            bar_length_m=L,
            test_duration_s=T,
            boundary_temperature=T_boundary,
            initial_peak_temperature=T_peak,
            Nx=101,
            Nt=201,
            method="fno"
        )
        fld_resp = post_field(fld_req)
        raw_fno_grid = np.array(fld_resp.u_grid)  # (201, 101)

        # Interpolate FNO to exact case grid (grid_nt, grid_nx) if grid differs
        if raw_fno_grid.shape != (grid_nt, grid_nx):
            fno_t = np.linspace(domain_t[0], domain_t[1], raw_fno_grid.shape[0])
            fno_x = np.linspace(domain_x[0], domain_x[1], raw_fno_grid.shape[1])
            interp = RegularGridInterpolator((fno_t, fno_x), raw_fno_grid, method="linear")
            target_t = np.linspace(domain_t[0], domain_t[1], grid_nt)
            target_x = np.linspace(domain_x[0], domain_x[1], grid_nx)
            T_target, X_target = np.meshgrid(target_t, target_x, indexing="ij")
            field_grid = interp(np.column_stack([T_target.flatten(), X_target.flatten()])).reshape((grid_nt, grid_nx))
        else:
            field_grid = raw_fno_grid

    else:
        tier = "solver"
        method_used = "solver"
        ood_warnings.append("outside the neural model’s trained range; answered with the numerical solver")

        # Solve directly on exact grid with numerical solver
        _, _, u_solved = solve_heat_1d_general(
            Nx=grid_nx,
            Nt=grid_nt,
            alpha=alpha_for_tier,
            u0_fn=u0_fn,
            bc_left=bc_left,
            bc_right=bc_right,
            domain_x=domain_x,
            domain_t=domain_t
        )
        if has_physical_scale and T_boundary is not None and T_peak is not None and abs(T_peak - T_boundary) > 1e-7:
            delta_T = T_peak - T_boundary
            field_grid = u_solved * delta_T + T_boundary
        else:
            field_grid = u_solved

        # If FNO can run, include FNO field as field_fno_out_of_domain with its error
        if "fno_heat" in APP_STATE:
            try:
                clamped_a = float(np.clip(alpha_for_tier, 0.01, 1.0))
                fld_req = FieldRequest(alpha=clamped_a, Nx=101, Nt=201, method="fno")
                fld_resp = post_field(fld_req)
                raw_fno_grid = np.array(fld_resp.u_grid)

                fno_t = np.linspace(domain_t[0], domain_t[1], raw_fno_grid.shape[0])
                fno_x = np.linspace(domain_x[0], domain_x[1], raw_fno_grid.shape[1])
                interp = RegularGridInterpolator((fno_t, fno_x), raw_fno_grid, method="linear")
                target_t = np.linspace(domain_t[0], domain_t[1], grid_nt)
                target_x = np.linspace(domain_x[0], domain_x[1], grid_nx)
                T_target, X_target = np.meshgrid(target_t, target_x, indexing="ij")
                fno_interp = interp(np.column_stack([T_target.flatten(), X_target.flatten()])).reshape((grid_nt, grid_nx))
                field_fno_out_of_domain = fno_interp.tolist()

                if truth_field is not None:
                    tf_arr = np.array(truth_field, dtype=float)
                    if tf_arr.shape == fno_interp.shape:
                        denom = np.linalg.norm(tf_arr)
                        field_fno_rel_l2 = float(np.linalg.norm(fno_interp - tf_arr) / max(1e-12, denom))
            except Exception:
                field_fno_out_of_domain = None
                field_fno_rel_l2 = None

    t_field_ms = round((time.perf_counter() - t0_field) * 1000.0, 2)
    timing_breakdown["field_ms"] = t_field_ms

    # Field relative L2 error against truth_field
    field_rel_l2 = None
    if truth_field is not None:
        try:
            tf_arr = np.array(truth_field, dtype=float)
            if tf_arr.shape == field_grid.shape:
                denom = np.linalg.norm(tf_arr)
                field_rel_l2 = float(np.linalg.norm(field_grid - tf_arr) / max(1e-12, denom))
        except Exception:
            field_rel_l2 = None

    # ---------------------------------------------------------------------------------------------
    # Stage 3: Diagnosis (3-Branch Reference Logic with LOSO and Class A Refinement)
    # ---------------------------------------------------------------------------------------------
    t0_diag = time.perf_counter()

    verdict = "-"
    faulty_idx = None
    faulty_sensor_x = None
    diag_note = None
    diag_resp = None

    if reference is not None and isinstance(reference, dict):
        base_obj = BaselineData(
            x_coords=reference["x_coords"],
            t_coords=reference["t_coords"],
            readings=reference["readings"]
        )
        diag_req = DiagnoseRequest(
            readings=SensorReadings(x_coords=x_coords, t_coords=t_coords, readings=readings),
            baseline=base_obj,
            bar_length_m=L,
            test_duration_s=T,
            boundary_temperature=T_boundary,
            initial_peak_temperature=T_peak,
            sigma=sigma
        )
        diag_resp = post_diagnose(diag_req)
        verdict = diag_resp.assigned_class
        faulty_idx = diag_resp.faulty_sensor_idx

    elif alpha_nominal is not None and alpha_nominal > 0:
        sim_data = simulate_healthy_reference(
            alpha_nominal=alpha_nominal,
            L=L,
            T=T,
            T_boundary=T_boundary,
            T_peak=T_peak,
            sigma=sigma,
            count=25
        )
        base_obj = BaselineData(
            x_coords=sim_data["x_coords"],
            t_coords=sim_data["t_coords"],
            readings=sim_data["readings"]
        )
        diag_req = DiagnoseRequest(
            readings=SensorReadings(x_coords=x_coords, t_coords=t_coords, readings=readings),
            baseline=base_obj,
            bar_length_m=L,
            test_duration_s=T,
            boundary_temperature=T_boundary,
            initial_peak_temperature=T_peak,
            sigma=sigma
        )
        diag_resp = post_diagnose(diag_req)
        verdict = diag_resp.assigned_class
        faulty_idx = diag_resp.faulty_sensor_idx
        case_notes.append("Reference baseline was synthesized from alpha_nominal using the forward heat simulator.")

    else:
        diag_note = "physical-change detection was not possible without a reference"
        case_notes.append(diag_note)
        # Residual screening for sensor fault
        alpha_local = alpha_hat if alpha_hat is not None else 0.10
        _, _, u_ref = solve_heat_1d_general(Nx=grid_nx, Nt=grid_nt, alpha=alpha_local, u0_fn=u0_fn,
                                            bc_left=bc_left, bc_right=bc_right, domain_x=domain_x, domain_t=domain_t)
        tg = np.linspace(domain_t[0], domain_t[1], grid_nt)
        xg = np.linspace(domain_x[0], domain_x[1], grid_nx)
        interp = RegularGridInterpolator((tg, xg), u_ref, method="linear", bounds_error=False, fill_value=None)
        preds = interp(np.column_stack([t_coords, x_coords]))
        resids = np.asarray(readings) - preds

        med_r = np.median(resids)
        mad = float(np.median(np.abs(resids - med_r)))
        sigma_eff = max(1.4826 * mad, 0.01)
        z_scores = np.abs(resids - med_r) / sigma_eff
        max_idx = int(np.argmax(z_scores))
        max_z = float(z_scores[max_idx])
        sorted_z = np.sort(z_scores)

        if max_z > 4.5 and (len(sorted_z) < 2 or max_z > 1.8 * sorted_z[-2]):
            verdict = "F"
            faulty_idx = max_idx
        else:
            verdict = "H"
            faulty_idx = None

    # Compute goodness-of-fit (reduced chi2) for single-diffusivity fit
    alpha_local_fit = alpha_hat if (alpha_hat is not None and alpha_hat > 0) else (alpha_nominal or 0.10)
    _, _, u_fit_field = solve_heat_1d_general(
        Nx=grid_nx, Nt=grid_nt, alpha=alpha_local_fit, u0_fn=u0_fn,
        bc_left=bc_left, bc_right=bc_right, domain_x=domain_x, domain_t=domain_t
    )
    if has_physical_scale and T_boundary is not None and T_peak is not None and abs(T_peak - T_boundary) > 1e-7:
        u_fit_field = u_fit_field * (T_peak - T_boundary) + T_boundary

    tg_eval = np.linspace(domain_t[0], domain_t[1], grid_nt)
    xg_eval = np.linspace(domain_x[0], domain_x[1], grid_nx)
    interp_fit = RegularGridInterpolator((tg_eval, xg_eval), u_fit_field, method="linear", bounds_error=False, fill_value=None)
    preds_fit = interp_fit(np.column_stack([t_coords, x_coords]))
    resids_fit = np.asarray(readings) - preds_fit
    sig_eff = sigma if (sigma is not None and sigma > 0) else max(1.4826 * float(np.median(np.abs(resids_fit - np.median(resids_fit)))), 0.01)
    chi2_red_single = float(np.sum((resids_fit / sig_eff) ** 2) / max(1, len(readings) - 1))

    # Refinement 1: Class A vs Class C continuous shift check
    # If change_time is at lower search boundary (<=0.05 or <= min(t)) and single-diffusivity fit is good (<2.0),
    # the shift has been present from t=0 (constant shift across whole test = Class A).
    if verdict == "C" and diag_resp is not None:
        c_time = getattr(diag_resp, "change_time", None)
        if c_time is not None and (c_time <= 0.05 or c_time <= min(t_coords) + 1e-4):
            if chi2_red_single < 2.0:
                verdict = "A"
                case_notes.append(
                    f"Diagnose verdict refined from C to A: detected change-time t_c={c_time} is at lower boundary "
                    f"and single-diffusivity fit has reduced chi2={chi2_red_single:.2f} < 2.0 (constant shift from t=0)."
                )

    # Refinement 2: Leave-One-Sensor-Out (LOSO) for whole-sensor corruption
    sensor_groups = {}
    for idx, (x, t, y) in enumerate(zip(x_coords, t_coords, readings)):
        ux = round(float(x), 4)
        sensor_groups.setdefault(ux, []).append(idx)

    alpha_hat_excluding_faulty = None
    ci95_excluding_faulty = None

    # Check for multi-reading sensor setup (at least 3 unique sensor locations and at least one sensor with >= 2 readings)
    # Only run LOSO if goodness of fit is poor (chi2_red_single > 2.0) or cascade already flagged a fault
    if len(sensor_groups) >= 3 and any(len(idxs) >= 2 for idxs in sensor_groups.values()):
        if chi2_red_single > 2.0 or verdict == "F":
            best_candidate = None
            min_chi2_cand = chi2_red_single

            for ux, idx_list in sensor_groups.items():
                if len(idx_list) < 2:
                    continue
                if len(readings) - len(idx_list) < 4:
                    continue
                x_rem = [x for i, x in enumerate(x_coords) if i not in idx_list]
                t_rem = [t for i, t in enumerate(t_coords) if i not in idx_list]
                y_rem = [y for i, y in enumerate(readings) if i not in idx_list]

                a_cand, ci_cand, _ = _estimate_alpha_helper(
                    x_coords=x_rem, t_coords=t_rem, readings=y_rem, sigma=sigma,
                    is_zero_bc=is_zero_bc, is_sin_ic=is_sin_ic, is_std_domain=is_std_domain,
                    L=L, T=T, T_boundary=T_boundary, T_peak=T_peak, truth_alpha=truth_alpha,
                    u0_fn=u0_fn, bc_left=bc_left, bc_right=bc_right, domain_x=domain_x, domain_t=domain_t,
                    grid_nx=grid_nx, grid_nt=grid_nt, mode=config.get("mode", "mode3plus")
                )
                if a_cand is None or a_cand <= 0:
                    continue

                _, _, u_cand_field = solve_heat_1d_general(
                    Nx=grid_nx, Nt=grid_nt, alpha=a_cand, u0_fn=u0_fn,
                    bc_left=bc_left, bc_right=bc_right, domain_x=domain_x, domain_t=domain_t
                )
                if has_physical_scale and T_boundary is not None and T_peak is not None and abs(T_peak - T_boundary) > 1e-7:
                    u_cand_field = u_cand_field * (T_peak - T_boundary) + T_boundary

                interp_cand = RegularGridInterpolator((tg_eval, xg_eval), u_cand_field, method="linear", bounds_error=False, fill_value=None)
                preds_rem = interp_cand(np.column_stack([t_rem, x_rem]))
                chi2_cand = float(np.sum(((np.asarray(y_rem) - preds_rem) / sig_eff) ** 2) / max(1, len(y_rem) - 1))

                # Removed sensor residuals under a_cand
                x_m = [x for i, x in enumerate(x_coords) if i in idx_list]
                t_m = [t for i, t in enumerate(t_coords) if i in idx_list]
                y_m = [y for i, y in enumerate(readings) if i in idx_list]
                preds_m = interp_cand(np.column_stack([t_m, x_m]))
                res_m = np.asarray(y_m) - preds_m
                chi2_removed = float(np.mean((res_m / sig_eff) ** 2))

                # Condition (a): LOSO may flag a sensor only if remaining data fit a single healthy alpha well
                # (chi2_cand < 2.0) AND the removed sensor's own residuals are the large ones.
                # If removing a sensor does not give a good fit, do NOT flag F.
                is_improvement = (
                    (chi2_cand < 2.0) and
                    (chi2_cand < 0.6 * chi2_red_single) and
                    (chi2_removed > 3.0) and
                    (chi2_removed > 2.0 * chi2_cand)
                )
                if is_improvement and chi2_cand < min_chi2_cand:
                    min_chi2_cand = chi2_cand
                    best_candidate = {
                        "ux": ux,
                        "idx_list": idx_list,
                        "alpha_hat": a_cand,
                        "ci95": ci_cand,
                        "chi2": chi2_cand,
                        "chi2_removed": chi2_removed
                    }

            if best_candidate is not None:
                verdict = "F"
                faulty_sensor_x = best_candidate["ux"]
                faulty_idx = best_candidate["idx_list"][0]
                alpha_hat_excluding_faulty = best_candidate["alpha_hat"]
                ci95_excluding_faulty = best_candidate["ci95"]
                case_notes.append(
                    f"Whole sensor fault detected at x={faulty_sensor_x} across {len(best_candidate['idx_list'])} readings via LOSO; "
                    f"chi2_red dropped from {chi2_red_single:.2f} to {best_candidate['chi2']:.2f}."
                )

    # Refinement 3: Regime-consistency check (Condition b)
    # Fit alpha separately on early and late readings (split by time).
    # If the two estimates differ by more than their combined 95% intervals and no single sensor explains the misfit,
    # report verdict C with the estimated change time.
    if verdict != "F" and len(readings) >= 8:
        u_times = sorted(list(set(round(float(t), 5) for t in t_coords)))
        if len(u_times) >= 3:
            best_regime_split = None
            max_z_diff = 0.0

            for t_s in u_times[1:-1]:
                early_mask = [round(float(t), 5) <= t_s for t in t_coords]
                late_mask = [round(float(t), 5) > t_s for t in t_coords]
                if sum(early_mask) < 4 or sum(late_mask) < 4:
                    continue

                x_e = [x for i, x in enumerate(x_coords) if early_mask[i]]
                t_e = [t for i, t in enumerate(t_coords) if early_mask[i]]
                y_e = [y for i, y in enumerate(readings) if early_mask[i]]

                x_l = [x for i, x in enumerate(x_coords) if late_mask[i]]
                t_l = [t for i, t in enumerate(t_coords) if late_mask[i]]
                y_l = [y for i, y in enumerate(readings) if late_mask[i]]

                a_e, ci_e, _ = _estimate_alpha_helper(
                    x_coords=x_e, t_coords=t_e, readings=y_e, sigma=sigma,
                    is_zero_bc=is_zero_bc, is_sin_ic=is_sin_ic, is_std_domain=is_std_domain,
                    L=L, T=T, T_boundary=T_boundary, T_peak=T_peak, truth_alpha=truth_alpha,
                    u0_fn=u0_fn, bc_left=bc_left, bc_right=bc_right, domain_x=domain_x, domain_t=domain_t,
                    grid_nx=grid_nx, grid_nt=grid_nt, mode=config.get("mode", "mode3plus")
                )
                a_l, ci_l, _ = _estimate_alpha_helper(
                    x_coords=x_l, t_coords=t_l, readings=y_l, sigma=sigma,
                    is_zero_bc=is_zero_bc, is_sin_ic=is_sin_ic, is_std_domain=is_std_domain,
                    L=L, T=T, T_boundary=T_boundary, T_peak=T_peak, truth_alpha=truth_alpha,
                    u0_fn=u0_fn, bc_left=bc_left, bc_right=bc_right, domain_x=domain_x, domain_t=domain_t,
                    grid_nx=grid_nx, grid_nt=grid_nt, mode=config.get("mode", "mode3plus")
                )

                if a_e is not None and a_l is not None and a_e > 0 and a_l > 0:
                    ci_e_hw = 0.5 * (ci_e[1] - ci_e[0]) if (ci_e and ci_e[0] is not None) else 0.05
                    ci_l_hw = 0.5 * (ci_l[1] - ci_l[0]) if (ci_l and ci_l[0] is not None) else 0.05
                    comb_ci = float(np.sqrt(ci_e_hw ** 2 + ci_l_hw ** 2))
                    diff = float(abs(a_e - a_l))
                    z_ratio = diff / max(comb_ci, 1e-6)
                    if diff > comb_ci and z_ratio > max_z_diff:
                        max_z_diff = z_ratio
                        best_regime_split = {
                            "t_split": t_s,
                            "a_early": a_e,
                            "ci_early": ci_e,
                            "a_late": a_l,
                            "ci_late": ci_l,
                            "diff": diff,
                            "comb_ci": comb_ci
                        }

            if best_regime_split is not None and (chi2_red_single > 2.0 or verdict == "C"):
                verdict = "C"
                t_ch = best_regime_split["t_split"]
                case_notes.append(
                    f"Regime-consistency check: alpha_early={best_regime_split['a_early']:.4f} and "
                    f"alpha_late={best_regime_split['a_late']:.4f} differ by {best_regime_split['diff']:.4f} "
                    f"(> combined 95% CI {best_regime_split['comb_ci']:.4f}); reported verdict C with estimated change time t_c={t_ch}."
                )

    # If single reading was flagged by cascade and not yet excluded by whole sensor
    if verdict == "F" and alpha_hat_excluding_faulty is None and faulty_idx is not None and isinstance(faulty_idx, int):
        if 0 <= faulty_idx < len(readings) and (len(readings) - 1) >= 4:
            faulty_sensor_x = round(float(x_coords[faulty_idx]), 4)
            x_excl = [x for i, x in enumerate(x_coords) if i != faulty_idx]
            t_excl = [t for i, t in enumerate(t_coords) if i != faulty_idx]
            y_excl = [y for i, y in enumerate(readings) if i != faulty_idx]
            a_ex, ci_ex, _ = _estimate_alpha_helper(
                x_coords=x_excl,
                t_coords=t_excl,
                readings=y_excl,
                sigma=sigma,
                is_zero_bc=is_zero_bc,
                is_sin_ic=is_sin_ic,
                is_std_domain=is_std_domain,
                L=L,
                T=T,
                T_boundary=T_boundary,
                T_peak=T_peak,
                truth_alpha=truth_alpha,
                u0_fn=u0_fn,
                bc_left=bc_left,
                bc_right=bc_right,
                domain_x=domain_x,
                domain_t=domain_t,
                grid_nx=grid_nx,
                grid_nt=grid_nt,
                mode=config.get("mode", "mode3plus")
            )
            alpha_hat_excluding_faulty = a_ex
            ci95_excluding_faulty = ci_ex
            case_notes.append(f"Single sensor fault flagged at index {faulty_idx} (x={faulty_sensor_x}); re-estimated alpha without faulty reading.")

    t_diag_ms = round((time.perf_counter() - t0_diag) * 1000.0, 2)
    timing_breakdown["diagnose_ms"] = t_diag_ms
    timing_breakdown["total_ms"] = round(t_est_ms + t_field_ms + t_diag_ms, 2)

    return {
        "case_id": case_id,
        "equation": "heat_1d",
        "case_type": "heat",
        "tier": tier,
        "truth_alpha": truth_alpha,
        "alpha_hat": alpha_hat,
        "ci95": ci95,
        "in_ci": in_ci,
        "alpha_rel_error": alpha_rel_error,
        "alpha_hat_excluding_faulty": alpha_hat_excluding_faulty,
        "ci95_excluding_faulty": ci95_excluding_faulty,
        "field_grid": field_grid.tolist() if isinstance(field_grid, np.ndarray) else field_grid,
        "field_method": method_used,
        "field_rel_l2": field_rel_l2,
        "field_fno_out_of_domain": field_fno_out_of_domain,
        "field_fno_rel_to_solver": field_fno_rel_l2,
        "field_linear_rel_to_solver": None,
        "field_fno_rel_l2": field_fno_rel_l2,
        "field_fno": None,
        "field_linear": None,
        "field_linear_rel_l2": None,
        "verdict": verdict,
        "faulty_sensor_x": faulty_sensor_x,
        "faulty_reading_idx": faulty_idx,
        "diagnose_note": diag_note,
        "out_of_domain": ood_warnings,
        "notes": case_notes,
        "timing_ms": timing_breakdown
    }


# =================================================================================================
# 8. POISSON CASE RUNNER (POISSON 2D DISPATCH)
# =================================================================================================

def run_poisson_case(case: Dict[str, Any], config: Dict[str, Any], app_context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute evaluation for a 2D Poisson case using Poisson2DSolver."""
    case_id = case["case_id"]
    timing_breakdown = {}
    ood_warnings = []
    case_notes = []

    domain_x = tuple(case.get("domain_x", (0.0, 1.0)))
    domain_y = tuple(case.get("domain_y", (0.0, 1.0)))
    grid_nx = int(case.get("grid_nx", 64))
    grid_ny = int(case.get("grid_ny", 64))

    raw_bcs = case.get("boundary_conditions") or {}
    bc_dict = {}
    for edge, spec in raw_bcs.items():
        if isinstance(spec, dict):
            b_type = spec.get("type", "dirichlet")
            b_val = spec.get("value", 0.0)
            if isinstance(b_val, str):
                try:
                    b_val = float(b_val)
                except ValueError:
                    var = "y" if edge in ("x_min", "x_max") else "x"
                    fn = evaluate_safe_ast(b_val, allowed_vars=(var,))
                    b_val = (lambda coords, fn=fn, var=var: fn(**{var: coords}))
            bc_dict[edge] = {"type": b_type, "value": b_val}
        else:
            bc_dict[edge] = spec

    source_dict = case.get("source_term")
    source_fn, _ = parse_poisson_source(source_dict, domain_x=domain_x, domain_y=domain_y)

    truth_field = case.get("truth_field")

    t0_solve = time.perf_counter()
    solver = Poisson2DSolver(Nx=grid_nx, Ny=grid_ny, domain_x=domain_x, domain_y=domain_y)
    u_field = solver.solve(source_fn, bc=bc_dict)
    t_field_ms = round((time.perf_counter() - t0_solve) * 1000.0, 2)
    timing_breakdown["field_ms"] = t_field_ms
    timing_breakdown["estimate_ms"] = 0.0
    timing_breakdown["diagnose_ms"] = 0.0
    timing_breakdown["total_ms"] = t_field_ms

    field_rel_l2 = None
    if truth_field is not None:
        try:
            tf_arr = np.array(truth_field, dtype=float)
            if tf_arr.shape == u_field.shape:
                denom = np.linalg.norm(tf_arr)
                field_rel_l2 = float(np.linalg.norm(u_field - tf_arr) / max(1e-12, denom))
        except Exception:
            field_rel_l2 = None

    # Check for zero Dirichlet boundaries
    def _is_all_zero_dirichlet(bcs):
        if not bcs:
            return True
        for edge in ("x_min", "x_max", "y_min", "y_max"):
            spec = bcs.get(edge)
            if spec is not None:
                if isinstance(spec, dict):
                    if spec.get("type", "dirichlet").lower() != "dirichlet":
                        return False
                    if abs(float(spec.get("value", 0.0))) > 1e-6:
                        return False
                elif isinstance(spec, (tuple, list)):
                    if str(spec[0]).lower() != "dirichlet" or abs(float(spec[1])) > 1e-6:
                        return False
                else:
                    if abs(float(spec)) > 1e-6:
                        return False
        return True

    is_zero_dir = _is_all_zero_dirichlet(bc_dict)
    field_fno = None
    field_fno_rel_to_solver = None
    field_linear = None
    field_linear_rel_to_solver = None

    if is_zero_dir and grid_nx == 64 and grid_ny == 64:
        # FNO-2D and Linear Baseline operate on 64x64 grid
        X_grid, Y_grid = solver.X, solver.Y
        f_grid = source_fn(X_grid, Y_grid)
        norm_solver = max(1e-12, float(np.linalg.norm(u_field)))

        # 1. FNO-2D Poisson
        fno_poi = APP_STATE.get("fno_poisson")
        if fno_poi is not None:
            try:
                coords = torch.from_numpy(np.stack([X_grid, Y_grid], axis=0)).float()
                f_tensor = torch.from_numpy(f_grid).unsqueeze(0).unsqueeze(0).float()
                fno_in = torch.cat([f_tensor, coords.unsqueeze(0)], dim=1)
                with torch.no_grad():
                    u_fno_arr = fno_poi(fno_in).squeeze().cpu().numpy()
                field_fno = u_fno_arr.tolist()
                field_fno_rel_to_solver = float(np.linalg.norm(u_fno_arr - u_field) / norm_solver)
            except Exception as e:
                case_notes.append(f"FNO Poisson failed: {e}")

        # 2. Linear Baseline Poisson
        lin_poi = APP_STATE.get("lin_poisson")
        if lin_poi is not None:
            try:
                u_lin_arr = lin_poi.predict(f_grid)
                field_linear = u_lin_arr.tolist()
                field_linear_rel_to_solver = float(np.linalg.norm(u_lin_arr - u_field) / norm_solver)
            except Exception as e:
                case_notes.append(f"Linear baseline Poisson failed: {e}")

        case_notes.append("Primary answer is the exact numerical solver; FNO-2D and Linear baseline errors are relative to the solver.")

    return {
        "case_id": case_id,
        "equation": "poisson_2d",
        "case_type": "poisson",
        "tier": "solver",
        "truth_alpha": None,
        "alpha_hat": None,
        "ci95": None,
        "in_ci": None,
        "alpha_rel_error": None,
        "alpha_hat_excluding_faulty": None,
        "ci95_excluding_faulty": None,
        "field_grid": u_field.tolist(),
        "field_method": "solver",
        "field_rel_l2": field_rel_l2,
        "field_fno_out_of_domain": None,
        "field_fno_rel_to_solver": field_fno_rel_to_solver,
        "field_linear_rel_to_solver": field_linear_rel_to_solver,
        "field_fno_rel_l2": field_fno_rel_to_solver,
        "field_fno": field_fno,
        "field_linear": field_linear,
        "field_linear_rel_l2": field_linear_rel_to_solver,
        "verdict": "-",
        "faulty_sensor_x": None,
        "faulty_reading_idx": None,
        "diagnose_note": None,
        "out_of_domain": ood_warnings,
        "notes": case_notes,
        "timing_ms": timing_breakdown
    }


CASE_DISPATCHER = {
    "heat_1d": run_heat_case,
    "heat": run_heat_case,
    "poisson_2d": run_poisson_case,
    "poisson": run_poisson_case
}


# =================================================================================================
# 9. INPUT PARSER (JSONL, JSON ARRAY, & CSV SUPPORT)
# =================================================================================================

def load_cases(file_path: str) -> List[Dict[str, Any]]:
    """Load cases from JSONL, JSON array, or CSV file."""
    if not os.path.exists(file_path):
        raise FileLevelError(f"Cases file not found: '{file_path}'")
    if os.path.getsize(file_path) == 0:
        raise FileLevelError(f"Cases file is empty (0 bytes): '{file_path}'")

    ext = os.path.splitext(file_path)[1].lower()

    if ext in (".jsonl", ".ndjson"):
        cases = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                s = line.strip()
                if not s:
                    continue
                try:
                    c = json.loads(s)
                    cases.append(adapt_case(c))
                except json.JSONDecodeError as e:
                    raise FileLevelError(f"Unreadable JSONL in '{file_path}' at line {line_no}: {e.msg}")
        return cases

    elif ext == ".json":
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            raise FileLevelError(f"Cases file is empty: '{file_path}'")

        # Try parsing as standard JSON array or object
        try:
            data = json.loads(content)
            if isinstance(data, list):
                return [adapt_case(c) for c in data]
            elif isinstance(data, dict):
                raw_cases = data.get("cases", [data])
                return [adapt_case(c) for c in raw_cases]
        except json.JSONDecodeError:
            # Fall back to reading as JSONL lines
            cases = []
            for line_no, line in enumerate(content.splitlines(), start=1):
                s = line.strip()
                if not s:
                    continue
                try:
                    cases.append(adapt_case(json.loads(s)))
                except json.JSONDecodeError as e:
                    raise FileLevelError(f"Unreadable JSON/JSONL in '{file_path}' at line {line_no}: {e.msg}")
            if cases:
                return cases
            raise FileLevelError(f"Failed to parse JSON file '{file_path}'.")

    elif ext == ".csv":
        try:
            with open(file_path, "r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        except csv.Error as e:
            raise FileLevelError(f"Unreadable CSV in '{file_path}': {e}")
        if not rows:
            raise FileLevelError(f"No usable cases found in CSV file '{file_path}'.")

        case_ids = [r.get("case_id") or r.get("id") or r.get("case") for r in rows]
        has_duplicate_case_ids = len(case_ids) != len(set(case_ids))

        if has_duplicate_case_ids and any(k in rows[0] for k in ("x", "x_coords")):
            grouped: Dict[str, Dict[str, Any]] = {}
            for r in rows:
                cid = str(r.get("case_id") or r.get("id") or "case_0")
                if cid not in grouped:
                    grouped[cid] = {
                        "case_id": cid,
                        "x_coords": [],
                        "t_coords": [],
                        "readings": [],
                        "sigma": r.get("sigma"),
                        "alpha_nominal": r.get("alpha_nominal"),
                        "truth_alpha": r.get("truth_alpha"),
                        "equation": r.get("equation", "heat_1d")
                    }
                xv = r.get("x") or r.get("x_coords")
                tv = r.get("t") or r.get("t_coords")
                yv = r.get("u") or r.get("readings")
                if xv is not None and tv is not None and yv is not None:
                    try:
                        grouped[cid]["x_coords"].append(float(xv))
                        grouped[cid]["t_coords"].append(float(tv))
                        grouped[cid]["readings"].append(float(yv))
                    except Exception:
                        pass
            return [adapt_case(c) for c in grouped.values()]
        else:
            return [adapt_case(r) for r in rows]

    else:
        raise FileLevelError(f"Unsupported file format '{ext}'. Must be .jsonl, .json, or .csv.")


# =================================================================================================
# 10. OUTPUT WRITER & REPRODUCIBILITY HELPER
# =================================================================================================

def strip_timing_and_timestamps(obj: Any) -> Any:
    """Recursively strip execution timings and timestamps for strict reproducibility comparison."""
    if isinstance(obj, dict):
        cleaned = {}
        for k, v in obj.items():
            if k in ("timing_ms", "field_ms", "estimate_ms", "diagnose_ms", "total_ms",
                     "solver_timing_ms", "fno_timing_ms", "timestamp", "total_runtime_s"):
                continue
            cleaned[k] = strip_timing_and_timestamps(v)
        return cleaned
    elif isinstance(obj, list):
        return [strip_timing_and_timestamps(item) for item in obj]
    elif isinstance(obj, float):
        return round(obj, 7)
    return obj


def write_run_log(
    out_dir: str,
    metadata: Dict[str, Any],
    start_time_iso: str,
    end_time_iso: str,
    file_error: Optional[str] = None
):
    """Write run_log.txt containing git commit, working tree status, package versions, and timings."""
    os.makedirs(out_dir, exist_ok=True)
    log_path = os.path.join(out_dir, "run_log.txt")

    try:
        git_head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        git_head = "git unavailable"

    try:
        git_status_raw = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True).stdout.strip()
        git_clean = "Clean" if not git_status_raw else f"Dirty ({len(git_status_raw.splitlines())} modified/untracked files)"
    except Exception:
        git_clean = "Unknown"

    lines = [
        "=" * 80,
        "THERMALENS CHALLENGE RUN LOG",
        "=" * 80,
        f"Command Line      : {' '.join(sys.argv)}",
        f"Execution Seed    : {metadata.get('seed', 'N/A')}",
        f"Start Time (UTC)  : {start_time_iso}",
        f"End Time (UTC)    : {end_time_iso}",
        f"Elapsed Runtime   : {metadata.get('total_runtime_s', 0.0)}s",
        f"Total Cases       : {metadata.get('num_cases', 0)}"
    ]

    if file_error:
        lines.extend([
            f"Run Status        : FAILED (File-Level Error)",
            f"Error Message     : {file_error}",
            ""
        ])
    else:
        lines.extend([
            f"Run Status        : COMPLETED",
            f"Status Counts     : ok={metadata.get('num_ok', 0)}, ok_with_warnings={metadata.get('num_ok_with_warnings', 0)}, invalid_input={metadata.get('num_invalid_input', 0)}",
            ""
        ])

    lines.extend([
        "--- Git Environment ---",
        f"Git Commit (HEAD) : {git_head}",
        f"Working Tree      : {git_clean}",
        "",
        "--- Python & Environment ---",
        f"Python Version    : {sys.version.splitlines()[0]}",
        f"PyTorch Version   : {torch.__version__}",
        f"NumPy Version     : {np.__version__}",
        f"SciPy Version     : {scipy.__version__}",
        f"FastAPI Version   : {fastapi.__version__}",
        f"Pydantic Version  : {pydantic.__version__}",
        "=" * 80,
        ""
    ])

    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def write_results(
    results: List[Dict[str, Any]],
    out_dir: str,
    metadata: Dict[str, Any],
    config_file: Optional[str] = None
):
    """Write results.jsonl, results.json, results.csv, summary.csv, run_log.txt, and copy of config."""
    os.makedirs(out_dir, exist_ok=True)

    jsonl_path = os.path.join(out_dir, "results.jsonl")
    json_path = os.path.join(out_dir, "results.json")
    csv_results_path = os.path.join(out_dir, "results.csv")
    csv_summary_path = os.path.join(out_dir, "summary.csv")

    # 1. results.jsonl (one JSON object per line in input order)
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    # 2. results.json
    full_payload = {
        "metadata": metadata,
        "cases": results
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(full_payload, f, indent=2)

    # 3. results.csv & summary.csv
    fieldnames = [
        "case_id", "equation", "status", "tier", "message",
        "truth_alpha", "alpha_hat", "ci95_low", "ci95_high", "in_ci", "alpha_rel_error",
        "alpha_hat_excluding_faulty", "ci95_excl_low", "ci95_excl_high",
        "field_method", "field_rel_l2", "field_fno_rel_to_solver", "field_linear_rel_to_solver", "field_fno_rel_l2", "field_linear_rel_l2",
        "verdict", "faulty_sensor_x", "faulty_reading_idx", "diagnose_note",
        "ood_count", "notes_count", "errors_count",
        "errors", "out_of_domain", "notes",
        "field_ms", "estimate_ms", "diagnose_ms", "total_ms"
    ]

    rows_to_write = []
    for r in results:
        tim = r.get("timing_ms") or {}
        ood = r.get("out_of_domain") or []
        nts = r.get("notes") or []
        errs = r.get("errors") or []
        ci = r.get("ci95") or [None, None]
        ci_ex = r.get("ci95_excluding_faulty") or [None, None]

        row = {
            "case_id": r.get("case_id"),
            "equation": r.get("equation", r.get("case_type")),
            "status": r.get("status"),
            "tier": r.get("tier", ""),
            "message": r.get("message", ""),
            "truth_alpha": r.get("truth_alpha") if r.get("truth_alpha") is not None else "",
            "alpha_hat": r.get("alpha_hat") if r.get("alpha_hat") is not None else "",
            "ci95_low": ci[0] if (isinstance(ci, (list, tuple)) and len(ci) > 0 and ci[0] is not None) else "",
            "ci95_high": ci[1] if (isinstance(ci, (list, tuple)) and len(ci) > 1 and ci[1] is not None) else "",
            "in_ci": ("YES" if r.get("in_ci") is True else ("NO" if r.get("in_ci") is False else "")) if r.get("in_ci") is not None else "",
            "alpha_rel_error": r.get("alpha_rel_error") if r.get("alpha_rel_error") is not None else "",
            "alpha_hat_excluding_faulty": r.get("alpha_hat_excluding_faulty") if r.get("alpha_hat_excluding_faulty") is not None else "",
            "ci95_excl_low": ci_ex[0] if (isinstance(ci_ex, (list, tuple)) and len(ci_ex) > 0 and ci_ex[0] is not None) else "",
            "ci95_excl_high": ci_ex[1] if (isinstance(ci_ex, (list, tuple)) and len(ci_ex) > 1 and ci_ex[1] is not None) else "",
            "field_method": r.get("field_method", ""),
            "field_rel_l2": r.get("field_rel_l2") if r.get("field_rel_l2") is not None else "",
            "field_fno_rel_to_solver": r.get("field_fno_rel_to_solver") if r.get("field_fno_rel_to_solver") is not None else "",
            "field_linear_rel_to_solver": r.get("field_linear_rel_to_solver") if r.get("field_linear_rel_to_solver") is not None else "",
            "field_fno_rel_l2": r.get("field_fno_rel_l2") if r.get("field_fno_rel_l2") is not None else "",
            "field_linear_rel_l2": r.get("field_linear_rel_l2") if r.get("field_linear_rel_l2") is not None else "",
            "verdict": r.get("verdict") if r.get("verdict") is not None else "",
            "faulty_sensor_x": r.get("faulty_sensor_x") if r.get("faulty_sensor_x") is not None else "",
            "faulty_reading_idx": r.get("faulty_reading_idx") if r.get("faulty_reading_idx") is not None else "",
            "diagnose_note": r.get("diagnose_note") if r.get("diagnose_note") is not None else "",
            "ood_count": len(ood),
            "notes_count": len(nts),
            "errors_count": len(errs),
            "errors": "; ".join(errs),
            "out_of_domain": "; ".join(ood),
            "notes": "; ".join(nts),
            "field_ms": tim.get("field_ms", ""),
            "estimate_ms": tim.get("estimate_ms", ""),
            "diagnose_ms": tim.get("diagnose_ms", ""),
            "total_ms": tim.get("total_ms", "")
        }
        rows_to_write.append(row)

    for p in (csv_results_path, csv_summary_path):
        with open(p, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in rows_to_write:
                writer.writerow(r)

    # Copy config
    if config_file and os.path.exists(config_file):
        dest_cfg = os.path.join(out_dir, "config.json")
        try:
            shutil.copyfile(config_file, dest_cfg)
        except Exception:
            pass

    print(f"\n[Output] Saved JSONL results to : {jsonl_path}")
    print(f"[Output] Saved JSON results to  : {json_path}")
    print(f"[Output] Saved CSV table to     : {csv_results_path}")
    print(f"[Output] Saved run log to       : {os.path.join(out_dir, 'run_log.txt')}")


def print_summary_table(results: List[Dict[str, Any]], metadata: Dict[str, Any]):
    """Print ASCII summary table to stdout."""
    print("\n" + "=" * 135)
    print(f" THERMALENS CHALLENGE EVALUATION SUMMARY (Cases: {metadata['num_cases']}, Seed: {metadata['seed']})")
    print("=" * 135)
    header = f"{'Case ID':<32} {'Truth':<8} {'AlphaHat':<10} {'RelErr':<8} {'CI95':<19} {'InCI':<6} {'Verd':<10} {'AlphaExcl':<10} {'Status':<18}"
    print(header)
    print("-" * 135)

    for r in results:
        cid = str(r.get("case_id", "unknown"))[:31]
        st = str(r.get("status", "unknown"))[:17]

        truth = f"{r.get('truth_alpha', 0.0):.4f}" if r.get("truth_alpha") is not None else "-"
        ahat = f"{r.get('alpha_hat', 0.0):.5f}" if r.get("alpha_hat") is not None else "-"
        rel_err = f"{r.get('alpha_rel_error', 0.0)*100:.2f}%" if r.get("alpha_rel_error") is not None else "-"

        ci = r.get("ci95")
        if isinstance(ci, (list, tuple)) and len(ci) == 2 and ci[0] is not None and ci[1] is not None:
            ci_str = f"[{ci[0]:.4f}, {ci[1]:.4f}]"
        else:
            ci_str = "-"

        in_ci_val = r.get("in_ci")
        in_ci_str = "YES" if in_ci_val is True else ("NO" if in_ci_val is False else "-")

        verd = str(r.get("verdict") or "-")
        f_idx = r.get("faulty_reading_idx")
        f_x = r.get("faulty_sensor_x")
        if verd == "F":
            if f_x is not None:
                verd = f"F(x={f_x})"
            elif f_idx is not None:
                verd = f"F({f_idx})"

        a_excl = f"{r.get('alpha_hat_excluding_faulty', 0.0):.5f}" if r.get("alpha_hat_excluding_faulty") is not None else "-"

        print(f"{cid:<32} {truth:<8} {ahat:<10} {rel_err:<8} {ci_str:<19} {in_ci_str:<6} {verd:<10} {a_excl:<10} {st:<18}")

    n_ok = metadata.get("num_ok", 0)
    n_warn = metadata.get("num_ok_with_warnings", 0)
    n_invalid = metadata.get("num_invalid_input", 0)

    print("=" * 135)
    print(f" SUMMARY COUNTS: ok: {n_ok}, ok_with_warnings: {n_warn}, invalid_input: {n_invalid} (Total: {len(results)})")
    print("=" * 135 + "\n")


# =================================================================================================
# 11. MAIN ENTRY POINT
# =================================================================================================

def main():
    parser = argparse.ArgumentParser(description="ThermaLens Challenge Batch Runner")
    parser.add_argument("--cases", help="Path to input cases file (.jsonl, .json, or .csv)")
    parser.add_argument("--out", default="challenge/output", help="Directory to save output results")
    parser.add_argument("--seed", type=int, default=20260101, help="Random seed (default: 20260101)")
    parser.add_argument("--config", default="challenge/config.json", help="Path to configuration JSON file")
    parser.add_argument("--check-repro", action="store_true", help="Run cases twice and verify deterministic identical results")
    parser.add_argument("--verify-exact", action="store_true", help="Run Stage 4 exact analytical verification benchmarks")
    args = parser.parse_args()

    # Stage 4 self-verification if requested or prior to processing
    if args.verify_exact:
        success = verify_exact_suite()
        if not args.cases:
            sys.exit(0 if success else 1)

    if not args.cases:
        parser.error("--cases is required when not running standalone --verify-exact.")

    # Always verify exact suite before processing cases
    verify_exact_suite()

    t_start = time.time()
    start_time_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    cfg = {}
    if os.path.exists(args.config):
        with open(args.config, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    else:
        print(f"[Config] Note: Config file '{args.config}' not found, using default settings.")

    seed = args.seed if args.seed is not None else cfg.get("seed", 20260101)

    # 1. Load cases
    try:
        cases = load_cases(args.cases)
    except FileLevelError as fle:
        t_end = time.time()
        end_time_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        err_msg = str(fle)
        print(f"\n[File Error] {err_msg}\n", file=sys.stderr)
        write_run_log(
            out_dir=args.out,
            metadata={"seed": seed, "total_runtime_s": round(t_end - t_start, 3), "num_cases": 0},
            start_time_iso=start_time_iso,
            end_time_iso=end_time_iso,
            file_error=err_msg
        )
        sys.exit(1)

    print(f"[Data] Loaded {len(cases)} cases from {args.cases}.")

    # 2. Initialize app context
    app_ctx = init_runner(config=cfg, seed=seed)

    def _execute_all():
        res_list = []
        for idx, case in enumerate(cases):
            cid = case.get("case_id", f"case_{idx}")
            eq = case.get("equation", "heat_1d")

            # Validate case
            errors = validate_case(case)
            if errors:
                short_msg = errors[0]
                res_list.append({
                    "case_id": cid,
                    "equation": eq,
                    "case_type": eq,
                    "status": "invalid_input",
                    "tier": None,
                    "message": short_msg,
                    "errors": errors,
                    "errors_count": len(errors),
                    "alpha_hat": None,
                    "ci95": None,
                    "alpha_rel_error": None,
                    "field": None,
                    "field_method": None,
                    "field_rel_l2": None,
                    "field_fno_out_of_domain": None,
                    "field_fno_rel_l2": None,
                    "verdict": None,
                    "faulty_reading_idx": None,
                    "diagnose_note": None,
                    "out_of_domain": [],
                    "notes": [],
                    "timing_ms": {"field_ms": 0.0, "estimate_ms": 0.0, "diagnose_ms": 0.0, "total_ms": 0.0}
                })
                continue

            if eq not in CASE_DISPATCHER:
                err_msg = f"Unknown equation '{eq}'. Supported equations: 'heat_1d', 'poisson_2d'."
                res_list.append({
                    "case_id": cid,
                    "equation": eq,
                    "case_type": eq,
                    "status": "invalid_input",
                    "tier": None,
                    "message": err_msg,
                    "errors": [err_msg],
                    "errors_count": 1,
                    "alpha_hat": None,
                    "ci95": None,
                    "alpha_rel_error": None,
                    "field": None,
                    "field_method": None,
                    "field_rel_l2": None,
                    "field_fno_out_of_domain": None,
                    "field_fno_rel_l2": None,
                    "verdict": None,
                    "faulty_reading_idx": None,
                    "diagnose_note": None,
                    "out_of_domain": [],
                    "notes": [],
                    "timing_ms": {"field_ms": 0.0, "estimate_ms": 0.0, "diagnose_ms": 0.0, "total_ms": 0.0}
                })
                continue

            try:
                handler = CASE_DISPATCHER[eq]
                case_res = handler(case, cfg, app_ctx)
                ood = case_res.get("out_of_domain", [])
                if len(ood) > 0:
                    case_status = "ok_with_warnings"
                    short_msg = ood[0]
                else:
                    case_status = "ok"
                    short_msg = "OK"

                res_list.append({
                    "case_id": cid,
                    "equation": eq,
                    "case_type": eq,
                    "status": case_status,
                    "tier": case_res.get("tier"),
                    "message": short_msg,
                    "errors": [],
                    "errors_count": 0,
                    "truth_alpha": case_res.get("truth_alpha"),
                    "alpha_hat": case_res.get("alpha_hat"),
                    "ci95": case_res.get("ci95"),
                    "in_ci": case_res.get("in_ci"),
                    "alpha_rel_error": case_res.get("alpha_rel_error"),
                    "alpha_hat_excluding_faulty": case_res.get("alpha_hat_excluding_faulty"),
                    "ci95_excluding_faulty": case_res.get("ci95_excluding_faulty"),
                    "field": case_res.get("field_grid"),
                    "field_method": case_res.get("field_method"),
                    "field_rel_l2": case_res.get("field_rel_l2"),
                    "field_fno_out_of_domain": case_res.get("field_fno_out_of_domain"),
                    "field_fno_rel_to_solver": case_res.get("field_fno_rel_to_solver"),
                    "field_linear_rel_to_solver": case_res.get("field_linear_rel_to_solver"),
                    "field_fno_rel_l2": case_res.get("field_fno_rel_l2"),
                    "field_fno": case_res.get("field_fno"),
                    "field_linear": case_res.get("field_linear"),
                    "field_linear_rel_l2": case_res.get("field_linear_rel_l2"),
                    "verdict": case_res.get("verdict"),
                    "faulty_sensor_x": case_res.get("faulty_sensor_x"),
                    "faulty_reading_idx": case_res.get("faulty_reading_idx"),
                    "diagnose_note": case_res.get("diagnose_note"),
                    "out_of_domain": ood,
                    "notes": case_res.get("notes", []),
                    "timing_ms": case_res.get("timing_ms", {})
                })
            except Exception as e:
                err_msg = f"Runtime execution failed: {e}"
                res_list.append({
                    "case_id": cid,
                    "equation": eq,
                    "case_type": eq,
                    "status": "invalid_input",
                    "tier": None,
                    "message": err_msg,
                    "errors": [err_msg],
                    "errors_count": 1,
                    "alpha_hat": None,
                    "ci95": None,
                    "alpha_rel_error": None,
                    "field": None,
                    "field_method": None,
                    "field_rel_l2": None,
                    "field_fno_out_of_domain": None,
                    "field_fno_rel_l2": None,
                    "verdict": None,
                    "faulty_reading_idx": None,
                    "diagnose_note": None,
                    "out_of_domain": [],
                    "notes": [],
                    "timing_ms": {"field_ms": 0.0, "estimate_ms": 0.0, "diagnose_ms": 0.0, "total_ms": 0.0}
                })

        return res_list

    # Primary pass
    results = _execute_all()

    # Reproducibility check if requested
    if args.check_repro:
        print("\n[Reproducibility] Running second pass with identical seed to verify determinism...")
        results_pass2 = _execute_all()
        clean1 = strip_timing_and_timestamps(results)
        clean2 = strip_timing_and_timestamps(results_pass2)
        if clean1 == clean2:
            print("[Reproducibility] PASS: Results are identical across consecutive runs (excluding timing fields).\n")
        else:
            print("[Reproducibility] WARNING: Differences detected between consecutive runs under same seed!")

    end_time_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    total_time_s = round(time.time() - t_start, 3)

    num_ok = sum(1 for r in results if r.get("status") == "ok")
    num_warn = sum(1 for r in results if r.get("status") == "ok_with_warnings")
    num_invalid = sum(1 for r in results if r.get("status") == "invalid_input")

    metadata = {
        "timestamp": start_time_iso,
        "cases_file": os.path.abspath(args.cases),
        "seed": seed,
        "config_file": os.path.abspath(args.config) if os.path.exists(args.config) else None,
        "num_cases": len(cases),
        "num_ok": num_ok,
        "num_ok_with_warnings": num_warn,
        "num_invalid_input": num_invalid,
        "total_runtime_s": total_time_s
    }

    # Write output files (results.jsonl, results.json, results.csv, summary.csv, run_log.txt, config copy)
    write_results(results, args.out, metadata, config_file=args.config)
    write_run_log(args.out, metadata, start_time_iso, end_time_iso)

    # Print summary table
    print_summary_table(results, metadata)


if __name__ == "__main__":
    main()
