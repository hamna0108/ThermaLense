"""Pydantic Request and Response Schemas with Strict Finite & Size Validation."""

import math
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

def validate_finite_list(vals: List[float], name: str, max_len: int = 1000) -> List[float]:
    if not vals:
        raise ValueError(f"'{name}' list cannot be empty.")
    if len(vals) > max_len:
        raise ValueError(f"'{name}' list exceeds maximum allowed length of {max_len} (received {len(vals)}).")
    for idx, v in enumerate(vals):
        if not math.isfinite(v):
            raise ValueError(f"'{name}' contains non-finite value at index {idx}: {v}")
    return vals

class BaselineData(BaseModel):
    model_config = ConfigDict(extra='forbid')
    x_coords: Optional[List[float]] = Field(None, description="Spatial sensor coordinates x in [0, 1]")
    t_coords: Optional[List[float]] = Field(None, description="Temporal sensor coordinates t in [0, 1]")
    readings: Optional[List[float]] = Field(None, description="Observed baseline sensor values")
    x: Optional[List[float]] = Field(None, description="Alias for x_coords")
    t: Optional[List[float]] = Field(None, description="Alias for t_coords")
    y: Optional[List[float]] = Field(None, description="Alias for readings")

    @model_validator(mode='before')
    @classmethod
    def resolve_aliases(cls, data):
        if isinstance(data, dict):
            if 'x' in data and 'x_coords' not in data:
                data['x_coords'] = data['x']
            if 't' in data and 't_coords' not in data:
                data['t_coords'] = data['t']
            if 'y' in data and 'readings' not in data:
                data['readings'] = data['y']
            if 'x_coords' in data and 'x' not in data:
                data['x'] = data['x_coords']
            if 't_coords' in data and 't' not in data:
                data['t'] = data['t_coords']
            if 'readings' in data and 'y' not in data:
                data['y'] = data['readings']
        return data

    @model_validator(mode='after')
    def check_lengths(self):
        xc = self.x_coords or self.x
        tc = self.t_coords or self.t
        yc = self.readings or self.y
        if xc is None or tc is None or yc is None:
            raise ValueError("Baseline must supply x_coords, t_coords, and readings (or x, t, y).")
        validate_finite_list(xc, "x_coords", max_len=1000)
        validate_finite_list(tc, "t_coords", max_len=1000)
        validate_finite_list(yc, "readings", max_len=1000)
        if not (len(xc) == len(tc) == len(yc)):
            raise ValueError(f"Baseline coordinate lengths must match: x({len(xc)}), t({len(tc)}), y({len(yc)})")
        return self

class PhysicsConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    u0_expr: Optional[str] = Field(None, description="Initial condition expression u0(x), e.g. 'sin(pi * x)'")
    bc_left_expr: Optional[str] = Field(None, description="Left boundary condition expression u(0, t)")
    bc_right_expr: Optional[str] = Field(None, description="Right boundary condition expression u(1, t)")
    source_expr: Optional[str] = Field(None, description="Distributed volumetric source expression s(x, t)")
    alpha_expr: Optional[str] = Field(None, description="Spatial variable diffusivity expression alpha(x)")

class NormalizationConstants(BaseModel):
    model_config = ConfigDict(extra='forbid')
    bar_length_m: Optional[float] = Field(None, description="Physical bar length L in metres")
    test_duration_s: Optional[float] = Field(None, description="Physical test duration T in seconds")
    boundary_temperature: Optional[float] = Field(None, description="Boundary temperature at bar ends T_boundary")
    initial_peak_temperature: Optional[float] = Field(None, description="Initial peak temperature T_peak")
    scale_factor: Optional[float] = Field(None, description="Diffusivity conversion factor L^2 / T")

class EstimateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    x: Optional[List[float]] = Field(None, description="Sensor spatial coordinates x")
    t: Optional[List[float]] = Field(None, description="Sensor temporal coordinates t")
    y: Optional[List[float]] = Field(None, description="Observed sensor values")
    x_coords: Optional[List[float]] = Field(None, description="Alias for x")
    t_coords: Optional[List[float]] = Field(None, description="Alias for t")
    readings: Optional[List[float]] = Field(None, description="Alias for y")
    sigma: Optional[float] = Field(None, description="Observation noise std. If None, estimated from baseline.")
    baseline: Optional[BaselineData] = Field(None, description="Healthy baseline readings (required if sigma is omitted; k >= 20)")
    physics: Optional[Dict[str, Any]] = Field(None, description="Optional declared physics inputs (u0_fn, bc_fn, source_fn)")
    physics_config: Optional[PhysicsConfig] = Field(None, description="Declared physics expression configuration strings")
    mode: Optional[str] = Field("mode3plus", description="Parameter inversion mode: 'mode3plus' (default), 'mode2', 'mode3', 'declared_physics'")
    # Real-world units normalization parameters
    bar_length_m: Optional[float] = Field(None, description="Physical bar length L in metres (L > 0)")
    test_duration_s: Optional[float] = Field(None, description="Physical test duration T in seconds (T > 0)")
    boundary_temperature: Optional[float] = Field(None, description="Boundary temperature at bar ends T_boundary")
    initial_peak_temperature: Optional[float] = Field(None, description="Initial peak temperature at t=0, x=L/2 T_peak")

    @model_validator(mode='before')
    @classmethod
    def resolve_aliases(cls, data):
        if isinstance(data, dict):
            # Coordinate aliases
            if 'x' in data and 'x_coords' not in data:
                data['x_coords'] = data['x']
            if 't' in data and 't_coords' not in data:
                data['t_coords'] = data['t']
            if 'y' in data and 'readings' not in data:
                data['readings'] = data['y']
            if 'x_coords' in data and 'x' not in data:
                data['x'] = data['x_coords']
            if 't_coords' in data and 't' not in data:
                data['t'] = data['t_coords']
            if 'readings' in data and 'y' not in data:
                data['y'] = data['readings']

            # Physical units field aliases
            if 'bar_length' in data and 'bar_length_m' not in data:
                data['bar_length_m'] = data.pop('bar_length')
            elif 'bar_length' in data:
                data.pop('bar_length')

            for t_alias in ('test_duration', 'duration'):
                if t_alias in data and 'test_duration_s' not in data:
                    data['test_duration_s'] = data.pop(t_alias)
                elif t_alias in data:
                    data.pop(t_alias)

            for b_alias in ('boundary_temp', 'ends_temperature', 'ends'):
                if b_alias in data and 'boundary_temperature' not in data:
                    data['boundary_temperature'] = data.pop(b_alias)
                elif b_alias in data:
                    data.pop(b_alias)

            for p_alias in ('initial_peak_temp', 'peak_temperature', 'hottest'):
                if p_alias in data and 'initial_peak_temperature' not in data:
                    data['initial_peak_temperature'] = data.pop(p_alias)
                elif p_alias in data:
                    data.pop(p_alias)
        return data

    @field_validator('sigma')
    @classmethod
    def check_sigma(cls, v):
        if v is not None:
            if not math.isfinite(v) or v <= 0.0:
                raise ValueError(f"sigma must be a positive finite float (received {v})")
        return v

    @model_validator(mode='after')
    def check_lengths(self):
        xc = self.x_coords or self.x
        tc = self.t_coords or self.t
        yc = self.readings or self.y
        if xc is None or tc is None or yc is None:
            raise ValueError("EstimateRequest must supply coordinates and readings (x_coords, t_coords, readings or x, t, y)")
        validate_finite_list(xc, "x_coords", max_len=1000)
        validate_finite_list(tc, "t_coords", max_len=1000)
        validate_finite_list(yc, "readings", max_len=1000)
        if not (len(xc) == len(tc) == len(yc)):
            raise ValueError(f"Observation coordinate lengths must match: x({len(xc)}), t({len(tc)}), y({len(yc)})")
        return self

class EstimateFlags(BaseModel):
    model_invalid: bool
    out_of_range: bool
    at_bound: bool
    warnings: List[str]

class EstimateResponse(BaseModel):
    alpha_hat: float
    ci95: List[float]
    method: str
    flags: EstimateFlags
    effective_sigma: float
    timing_ms: float
    chi2_dof: Optional[float] = None
    dw_stat: Optional[float] = None
    # Real-world units normalization metadata
    alpha_hat_normalized: Optional[float] = None
    ci95_normalized: Optional[List[float]] = None
    normalization: Optional[NormalizationConstants] = None
    units: Optional[str] = "dimensionless"

class SensorReadings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    x_coords: Optional[List[float]] = Field(None, description="Sensor spatial coordinates x in [0, 1]")
    t_coords: Optional[List[float]] = Field(None, description="Sensor temporal coordinates t in [0, 1]")
    readings: Optional[List[float]] = Field(None, description="Observed sensor values")
    x: Optional[List[float]] = Field(None, description="Alias for x_coords")
    t: Optional[List[float]] = Field(None, description="Alias for t_coords")
    y: Optional[List[float]] = Field(None, description="Alias for readings")

    @model_validator(mode='before')
    @classmethod
    def resolve_aliases(cls, data):
        if isinstance(data, dict):
            if 'x' in data and 'x_coords' not in data:
                data['x_coords'] = data['x']
            if 't' in data and 't_coords' not in data:
                data['t_coords'] = data['t']
            if 'y' in data and 'readings' not in data:
                data['readings'] = data['y']
            if 'x_coords' in data and 'x' not in data:
                data['x'] = data['x_coords']
            if 't_coords' in data and 't' not in data:
                data['t'] = data['t_coords']
            if 'readings' in data and 'y' not in data:
                data['y'] = data['readings']
        return data

    @model_validator(mode='after')
    def check_lengths(self):
        xc = self.x_coords or self.x
        tc = self.t_coords or self.t
        yc = self.readings or self.y
        if xc is None or tc is None or yc is None:
            raise ValueError("SensorReadings must supply coordinates and readings (x_coords, t_coords, readings or x, t, y)")
        validate_finite_list(xc, "x_coords", max_len=1000)
        validate_finite_list(tc, "t_coords", max_len=1000)
        validate_finite_list(yc, "readings", max_len=1000)
        if not (len(xc) == len(tc) == len(yc)):
            raise ValueError(f"Reading lengths must match: x({len(xc)}), t({len(tc)}), y({len(yc)})")
        return self

class DiagnoseRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    readings: Optional[SensorReadings] = Field(None, description="Operational sensor measurements: {x_coords, t_coords, readings}")
    baseline: BaselineData = Field(..., description="Healthy baseline readings: {x_coords, t_coords, readings} with k >= 20")
    sigma: Optional[float] = Field(None, description="Optional declared noise std")
    x_coords: Optional[List[float]] = Field(None, description="Top-level operational x coordinates (flat format)")
    t_coords: Optional[List[float]] = Field(None, description="Top-level operational t coordinates (flat format)")
    x: Optional[List[float]] = Field(None, description="Alias for x_coords")
    t: Optional[List[float]] = Field(None, description="Alias for t_coords")
    y: Optional[List[float]] = Field(None, description="Alias for readings")
    bar_length_m: Optional[float] = Field(None, description="Physical bar length L in metres (L > 0)")
    test_duration_s: Optional[float] = Field(None, description="Physical test duration T in seconds (T > 0)")
    boundary_temperature: Optional[float] = Field(None, description="Boundary temperature at bar ends T_boundary")
    initial_peak_temperature: Optional[float] = Field(None, description="Initial peak temperature at t=0, x=L/2 T_peak")

    @model_validator(mode='before')
    @classmethod
    def resolve_diagnose_payload(cls, data):
        if isinstance(data, dict):
            # Physical units field aliases
            if 'bar_length' in data and 'bar_length_m' not in data:
                data['bar_length_m'] = data.pop('bar_length')
            elif 'bar_length' in data:
                data.pop('bar_length')

            for t_alias in ('test_duration', 'duration'):
                if t_alias in data and 'test_duration_s' not in data:
                    data['test_duration_s'] = data.pop(t_alias)
                elif t_alias in data:
                    data.pop(t_alias)

            for b_alias in ('boundary_temp', 'ends_temperature', 'ends'):
                if b_alias in data and 'boundary_temperature' not in data:
                    data['boundary_temperature'] = data.pop(b_alias)
                elif b_alias in data:
                    data.pop(b_alias)

            for p_alias in ('initial_peak_temp', 'peak_temperature', 'hottest'):
                if p_alias in data and 'initial_peak_temperature' not in data:
                    data['initial_peak_temperature'] = data.pop(p_alias)
                elif p_alias in data:
                    data.pop(p_alias)

            # If readings is provided as a flat array of numbers and top-level x_coords/t_coords exist
            if isinstance(data.get('readings'), list):
                r_list = data['readings']
                xc = data.get('x_coords') or data.get('x')
                tc = data.get('t_coords') or data.get('t')
                data['readings'] = {'x_coords': xc, 't_coords': tc, 'readings': r_list}
            elif data.get('readings') is None and ('x_coords' in data or 'x' in data):
                xc = data.get('x_coords') or data.get('x')
                tc = data.get('t_coords') or data.get('t')
                yc = data.get('y')
                data['readings'] = {'x_coords': xc, 't_coords': tc, 'readings': yc}
        return data

class DiagnoseResponse(BaseModel):
    assigned_class: str = Field(..., description="'H' (Healthy), 'A' (Anomalous Diffusion), 'F' (Sensor Fault), 'C' (Change-Point)")
    evidence_stats: Dict[str, Any]
    faulty_sensor_idx: Optional[int] = None
    change_time: Optional[float] = None
    effective_sigma: float
    timing_ms: float
    normalization: Optional[NormalizationConstants] = None
    units: Optional[str] = "dimensionless"

class PlacementRequest(BaseModel):
    N: int = Field(..., ge=2, le=500, description="Total number of sensor observation points")
    sigma: float = Field(..., gt=0.0, description="Assumed measurement noise standard deviation")
    t_min: Optional[float] = Field(0.01, ge=1e-4, le=1.0)
    t_max: Optional[float] = Field(1.0, ge=0.01, le=10.0)
    sensor_x: Optional[float] = Field(0.5, ge=0.0, le=1.0)

class PlacementResponse(BaseModel):
    N: int
    sigma: float
    sensor_x: float
    t_stage1: List[float]
    t_stage2_nominal: List[float]
    strategy_description: str
    timing_ms: float

class FieldRequest(BaseModel):
    alpha: float = Field(..., gt=0.0, description="Diffusivity parameter alpha")
    physics: Optional[Dict[str, Any]] = None
    Nx: Optional[int] = Field(101, ge=11, le=501)
    Nt: Optional[int] = Field(201, ge=11, le=1001)
    method: Optional[str] = Field("auto", description="Execution method: 'auto' (default), 'solver', 'fno', or 'compare'")

    @field_validator('alpha')
    @classmethod
    def check_finite_alpha(cls, v):
        if not math.isfinite(v) or v <= 0.0:
            raise ValueError("alpha must be a finite positive number")
        return v

class FieldResponse(BaseModel):
    u_grid: List[List[float]]
    x_grid: List[float]
    t_grid: List[float]
    method_used: str = Field(..., description="'fno' if alpha in [0.01, 1.0], otherwise 'numerical_solver'")
    timing_ms: float
    fno_timing_ms: Optional[float] = None
    solver_timing_ms: Optional[float] = None
    relative_difference: Optional[float] = None
    compare_grid: Optional[List[List[float]]] = None

class PoissonGaussianSource(BaseModel):
    type: str = "gaussian"
    centers: List[List[float]] = Field(..., description="List of [x, y] coordinates in [0, 1]^2")
    amplitudes: List[float] = Field(..., description="List of peak amplitudes")
    sigmas: List[float] = Field(..., description="List of Gaussian widths")

    @model_validator(mode='after')
    def check_lens(self):
        if not (len(self.centers) == len(self.amplitudes) == len(self.sigmas)):
            raise ValueError("centers, amplitudes, and sigmas must have equal lengths")
        for c in self.centers:
            if len(c) != 2:
                raise ValueError(f"Each center must have exactly 2 coordinates [x, y] (received {c})")
            if not (0.0 <= c[0] <= 1.0 and 0.0 <= c[1] <= 1.0):
                raise ValueError(f"Center coordinates must lie in [0, 1] (received {c})")
        return self

class PoissonSineSource(BaseModel):
    type: str = "sine"
    modes: List[List[int]] = Field(..., description="List of [m, n] harmonic wavenumber pairs")
    amplitudes: List[float] = Field(..., description="List of mode amplitudes")

    @model_validator(mode='after')
    def check_lens(self):
        if len(self.modes) != len(self.amplitudes):
            raise ValueError("modes and amplitudes must have equal length")
        for m in self.modes:
            if len(m) != 2:
                raise ValueError(f"Each mode must have exactly 2 integers [m, n] (received {m})")
            if m[0] < 1 or m[1] < 1:
                raise ValueError(f"Wavenumbers must be positive integers (received {m})")
        return self

class PoissonRequest(BaseModel):
    source: Dict[str, Any] = Field(..., description="Source configuration: {'type': 'gaussian', ...} or {'type': 'sine', ...}")
    grid_size: Optional[int] = Field(64, ge=16, le=128, description="Spatial resolution N (default 64)")

class PoissonTiming(BaseModel):
    exact_ms: float
    fno_ms: float
    linear_ms: float
    total_ms: float

class PoissonErrors(BaseModel):
    rel_l2_fno_vs_exact: float
    rel_l2_linear_vs_exact: float
    rel_l2_fno_vs_linear: float

class PoissonResponse(BaseModel):
    exact_field: List[List[float]]
    fno_field: List[List[float]]
    linear_field: List[List[float]]
    relative_errors: PoissonErrors
    timing_ms: PoissonTiming
    high_frequency_source: bool = Field(..., description="True if sine modes exceed 4 (outside training family)")

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    timestamp: str

class VersionResponse(BaseModel):
    name: str = Field("ThermaLens", description="Product name")
    git_commit: str
    git_tags: List[str]
    checkpoint_sha256s: Dict[str, str]

class ErrorDetail(BaseModel):
    error_code: str
    message: str
    request_id: Optional[str] = None
    details: Optional[Any] = None
