"""Pydantic Request and Response Schemas with Strict Finite & Size Validation."""

import math
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator, model_validator

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
    x: List[float] = Field(..., description="Spatial sensor coordinates x in [0, 1]")
    t: List[float] = Field(..., description="Temporal sensor coordinates t in [0, 1]")
    y: List[float] = Field(..., description="Observed sensor values")

    @field_validator('x', 't', 'y')
    @classmethod
    def check_finite(cls, v, info):
        return validate_finite_list(v, info.field_name, max_len=1000)

    @model_validator(mode='after')
    def check_lengths(self):
        if not (len(self.x) == len(self.t) == len(self.y)):
            raise ValueError(f"Baseline coordinate lengths must match: x({len(self.x)}), t({len(self.t)}), y({len(self.y)})")
        return self

class EstimateRequest(BaseModel):
    x: List[float] = Field(..., description="Sensor spatial coordinates x in [0, 1]")
    t: List[float] = Field(..., description="Sensor temporal coordinates t in [0, 1]")
    y: List[float] = Field(..., description="Observed sensor values")
    sigma: Optional[float] = Field(None, description="Observation noise std. If None, estimated from baseline.")
    baseline: Optional[BaselineData] = Field(None, description="Healthy baseline readings (required if sigma is omitted; k >= 20)")
    physics: Optional[Dict[str, Any]] = Field(None, description="Optional declared physics inputs (u0_fn, bc_fn, source_fn)")
    mode: Optional[str] = Field("mode3plus", description="Parameter inversion mode: 'mode3plus' (default), 'mode2', 'mode3', 'declared_physics'")

    @field_validator('x', 't', 'y')
    @classmethod
    def check_finite(cls, v, info):
        return validate_finite_list(v, info.field_name, max_len=1000)

    @field_validator('sigma')
    @classmethod
    def check_sigma(cls, v):
        if v is not None:
            if not math.isfinite(v) or v <= 0.0:
                raise ValueError(f"sigma must be a positive finite float (received {v})")
        return v

    @model_validator(mode='after')
    def check_lengths(self):
        if not (len(self.x) == len(self.t) == len(self.y)):
            raise ValueError(f"Observation coordinate lengths must match: x({len(self.x)}), t({len(self.t)}), y({len(self.y)})")
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

class SensorReadings(BaseModel):
    x: List[float]
    t: List[float]
    y: List[float]

    @field_validator('x', 't', 'y')
    @classmethod
    def check_finite(cls, v, info):
        return validate_finite_list(v, info.field_name, max_len=1000)

    @model_validator(mode='after')
    def check_lengths(self):
        if not (len(self.x) == len(self.t) == len(self.y)):
            raise ValueError(f"Reading lengths must match: x({len(self.x)}), t({len(self.t)}), y({len(self.y)})")
        return self

class DiagnoseRequest(BaseModel):
    readings: SensorReadings = Field(..., description="Operational sensor measurements")
    baseline: BaselineData = Field(..., description="Healthy baseline readings (minimum k >= 20 required)")
    sigma: Optional[float] = Field(None, description="Optional declared noise std")

class DiagnoseResponse(BaseModel):
    assigned_class: str = Field(..., description="'H' (Healthy), 'A' (Anomalous Diffusion), 'F' (Sensor Fault), 'C' (Change-Point)")
    evidence_stats: Dict[str, Any]
    faulty_sensor_idx: Optional[int] = None
    change_time: Optional[float] = None
    effective_sigma: float
    timing_ms: float

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
    git_commit: str
    git_tags: List[str]
    checkpoint_sha256s: Dict[str, str]

class ErrorDetail(BaseModel):
    error_code: str
    message: str
    request_id: Optional[str] = None
    details: Optional[Any] = None
