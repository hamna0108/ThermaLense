"""Bar Profiles (Reference Library) Storage, Validation, and Save-Time Checks.

Manages persistent profile storage in data/profiles/ with strict security:
- Server-generated UUID identifiers
- Display names are metadata only (no user-supplied file paths)
- Max 50 profiles total
- Max 5,000 readings per profile
- Max 1 MB payload size
- Strict physical coordinate & numeric bounds validation
- Save-time model-fit check reusing existing inverse estimation functions
"""

import io
import os
import csv
import json
import math
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import numpy as np
from fastapi import HTTPException

# Repository root and storage directory
REPO_ROOT = Path(__file__).resolve().parent.parent
PROFILES_DIR = REPO_ROOT / "data" / "profiles"

MAX_PROFILES = 50
MAX_READINGS = 5000
MIN_READINGS = 20
MAX_PAYLOAD_BYTES = 1_000_000  # 1 MB

DEMO_UUID_1 = "00000000-0000-4000-8000-000000000001"
DEMO_UUID_2 = "00000000-0000-4000-8000-000000000002"

def ensure_profiles_dir():
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)

def validate_uuid_str(val: str) -> str:
    """Validate that val is a valid UUID string to prevent path traversal."""
    if not isinstance(val, str) or not val.strip():
        raise HTTPException(status_code=422, detail="Profile ID must be a valid non-empty UUID string.")
    cleaned = val.strip().lower()
    try:
        u = uuid.UUID(cleaned)
        return str(u)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid profile ID '{val}'. Must be a valid UUID format."
        )

def parse_csv_readings(csv_text: str) -> List[Dict[str, float]]:
    """Parse CSV text into list of {position_m, time_s, temperature_c}."""
    if not csv_text or not csv_text.strip():
        raise HTTPException(status_code=422, detail="CSV readings text cannot be empty.")
    
    if len(csv_text.encode('utf-8')) > MAX_PAYLOAD_BYTES:
        raise HTTPException(status_code=422, detail=f"CSV data exceeds maximum size of 1 MB.")

    f = io.StringIO(csv_text.strip())
    reader = csv.reader(f)
    rows = []
    
    header = None
    for row_idx, row in enumerate(reader):
        if not row or not any(field.strip() for field in row):
            continue
        cleaned = [c.strip() for c in row if c.strip() != '']
        if not cleaned or cleaned[0].startswith('#'):
            continue
            
        if header is None:
            # Check if header line
            if any(h.lower() in ('position', 'position_m', 'x', 'time', 'time_s', 't', 'temperature', 'temperature_c', 'temp', 'u') for h in cleaned):
                header = [c.lower() for c in cleaned]
                continue
            else:
                header = ['position_m', 'time_s', 'temperature_c']

        if len(cleaned) < 3:
            raise HTTPException(
                status_code=422,
                detail=f"Row {row_idx + 1} has {len(cleaned)} columns; expected 3 (position_m, time_s, temperature_c)."
            )
            
        try:
            p_val = float(cleaned[0])
            t_val = float(cleaned[1])
            u_val = float(cleaned[2])
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"Row {row_idx + 1} contains non-numeric values: {cleaned[:3]}"
            )
            
        rows.append({"position_m": p_val, "time_s": t_val, "temperature_c": u_val})
        if len(rows) > MAX_READINGS:
            raise HTTPException(
                status_code=422,
                detail=f"Readings exceed maximum limit of {MAX_READINGS} rows."
            )
            
    return rows

def validate_profile_physics(
    L: float,
    T: float,
    Tb: float,
    Tp: float,
    readings: List[Dict[str, float]]
):
    """Strict physical coordinate and bounds validation."""
    if not math.isfinite(L) or L <= 0:
        raise HTTPException(status_code=422, detail="bar_length_m must be a finite positive number.")
    if not math.isfinite(T) or T <= 0:
        raise HTTPException(status_code=422, detail="test_duration_s must be a finite positive number.")
    if not math.isfinite(Tb) or not math.isfinite(Tp):
        raise HTTPException(status_code=422, detail="Boundary and initial peak temperatures must be finite numbers.")
    if abs(Tp - Tb) < 1e-9:
        raise HTTPException(status_code=422, detail="initial_peak_temperature cannot equal boundary_temperature (zero temperature gradient).")

    if len(readings) < MIN_READINGS:
        raise HTTPException(
            status_code=422,
            detail=f"A reference profile requires at least {MIN_READINGS} readings (received {len(readings)})."
        )
    if len(readings) > MAX_READINGS:
        raise HTTPException(
            status_code=422,
            detail=f"Readings exceed maximum limit of {MAX_READINGS} rows."
        )

    for idx, r in enumerate(readings):
        x = r.get("position_m")
        t = r.get("time_s")
        y = r.get("temperature_c")
        if x is None or t is None or y is None:
            raise HTTPException(status_code=422, detail=f"Reading at row {idx + 1} is missing required keys.")
        if not math.isfinite(x) or not math.isfinite(t) or not math.isfinite(y):
            raise HTTPException(status_code=422, detail=f"Reading at row {idx + 1} contains non-finite values.")

        if x < -1e-7 or x > L + 1e-7:
            raise HTTPException(
                status_code=422,
                detail=f"Reading at row {idx + 1}: position {x} m is outside bar length [0, {L}] m."
            )
        if t < -1e-7 or t > T + 1e-7:
            raise HTTPException(
                status_code=422,
                detail=f"Reading at row {idx + 1}: time {t} s is outside test duration [0, {T}] s."
            )

def run_save_time_check(
    L: float,
    T: float,
    Tb: float,
    Tp: float,
    readings: List[Dict[str, float]],
    declared_sigma: Optional[float] = 0.5
) -> Tuple[Optional[str], float, float, float]:
    """Run reference readings through existing model-fit and autocorrelation checks.
    
    Returns:
        (warning_message_or_None, measured_alpha_real, measured_sigma_real, chi2_red)
    """
    from service.app import estimate_sigma_from_baseline, fit_three_models_bic_detailed

    delta_T = Tp - Tb
    x_raw = np.array([r["position_m"] for r in readings], dtype=float)
    t_raw = np.array([r["time_s"] for r in readings], dtype=float)
    y_raw = np.array([r["temperature_c"] for r in readings], dtype=float)

    # Normalization
    x_s = x_raw / L
    t_s = t_raw / T
    y_s = (y_raw - Tb) / delta_T

    # 1. Base estimation
    sig_info = estimate_sigma_from_baseline(x_s, t_s, y_s, min_readings=MIN_READINGS, allow_fewer=False)
    hat_a_norm = float(sig_info["alpha_base"])
    hat_sig_norm = float(sig_info["sigma_hat"])

    alpha_scale = (L ** 2) / T
    alpha_real = hat_a_norm * alpha_scale
    sigma_real = hat_sig_norm * abs(delta_T)

    # Effective sigma for detailed fit check
    eff_sigma = (float(declared_sigma) / abs(delta_T)) if (declared_sigma is not None and declared_sigma > 0) else hat_sig_norm

    # 2. Fit check
    fit_res = fit_three_models_bic_detailed(x_s, t_s, y_s, eff_sigma)
    chi2_red = float(fit_res["chi2_red"])
    alpha_hat = float(fit_res["alpha_hat"])
    bic_0 = float(fit_res["bic_0"])
    bic_f = float(fit_res["bic_f"])

    warning = None
    # If chi2/dof > 2.0 or sensor fault BIC preferred over healthy baseline BIC or extreme alpha:
    if chi2_red > 2.0 or (bic_f < bic_0 - 2.0) or (alpha_hat < 0.015 or alpha_hat > 0.60):
        warning = "This doesn't look like a clean normal run. Save anyway?"

    return warning, round(alpha_real, 6), round(sigma_real, 2), round(chi2_red, 3)

def generate_demo_profile_data(seed: int, L: float, T: float, Tb: float, Tp: float, sig: float, num_pts: int = 20) -> List[Dict[str, float]]:
    """Deterministic Box-Muller generator with Mulberry32 matching browser seed 0."""
    def mulberry32(a):
        curr = a
        def rng():
            nonlocal curr
            curr = (curr + 0x6D2B79F5) & 0xFFFFFFFF
            t = (curr ^ (curr >> 15)) * (curr | 1)
            t &= 0xFFFFFFFF
            t = (t ^ (t + ((t ^ (t >> 7)) * (t | 61)))) & 0xFFFFFFFF
            return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0
        return rng

    rng = mulberry32(seed)
    def normal():
        u1 = rng()
        u2 = rng()
        while u1 <= 0.0:
            u1 = rng()
        return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)

    delta_T = Tp - Tb
    tb_pts = [2.0 + (i / max(1, num_pts - 1)) * (T - 2.0) for i in range(num_pts)]
    xb_choices = [0.3 * L, 0.5 * L, 0.7 * L]
    
    rows = []
    for i in range(num_pts):
        x = xb_choices[i % 3]
        t = tb_pts[i]
        x_norm = x / L
        t_norm = t / T
        u_norm = math.sin(math.pi * x_norm) * math.exp(-0.10 * (math.pi ** 2) * t_norm)
        u_clean = Tb + delta_T * u_norm
        u_noisy = round(u_clean + normal() * sig, 2)
        rows.append({"position_m": round(x, 3), "time_s": round(t, 1), "temperature_c": u_noisy})
    return rows

def init_demo_profiles():
    """Ensure the 2 shipped demo profiles exist in data/profiles/."""
    ensure_profiles_dir()

    # Demo 1: Standard Steel Bar (0.1 m)
    p1_json = PROFILES_DIR / f"{DEMO_UUID_1}.json"
    p1_csv = PROFILES_DIR / f"{DEMO_UUID_1}.csv"
    if not p1_json.exists() or not p1_csv.exists():
        r1 = generate_demo_profile_data(seed=0, L=0.1, T=100.0, Tb=20.0, Tp=80.0, sig=0.5, num_pts=20)
        warn, alpha, sig, chi2 = run_save_time_check(0.1, 100.0, 20.0, 80.0, r1, 0.5)
        meta1 = {
            "id": DEMO_UUID_1,
            "name": "Demo: Standard Steel Bar (0.1 m)",
            "material_note": "AISI 1018 cold-drawn carbon steel reference bar",
            "bar_length_m": 0.1,
            "test_duration_s": 100.0,
            "boundary_temperature": 20.0,
            "initial_peak_temperature": 80.0,
            "sensor_accuracy": 0.5,
            "created": "2026-10-24T18:00:00Z",
            "updated": "2026-10-24T18:00:00Z",
            "measured_alpha_base": alpha,
            "measured_sigma": sig,
            "row_count": len(r1),
            "is_demo": True
        }
        with open(p1_json, "w", encoding="utf-8") as f:
            json.dump(meta1, f, indent=2)
        with open(p1_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["position_m", "time_s", "temperature_c"])
            for r in r1:
                writer.writerow([r["position_m"], r["time_s"], r["temperature_c"]])

    # Demo 2: Aluminum Test Rod (0.2 m)
    p2_json = PROFILES_DIR / f"{DEMO_UUID_2}.json"
    p2_csv = PROFILES_DIR / f"{DEMO_UUID_2}.csv"
    if not p2_json.exists() or not p2_csv.exists():
        r2 = generate_demo_profile_data(seed=0, L=0.2, T=50.0, Tb=25.0, Tp=75.0, sig=0.5, num_pts=20)
        warn, alpha, sig, chi2 = run_save_time_check(0.2, 50.0, 25.0, 75.0, r2, 0.5)
        meta2 = {
            "id": DEMO_UUID_2,
            "name": "Demo: Aluminum Test Rod (0.2 m)",
            "material_note": "6061-T6 aluminum high-conductivity reference rod",
            "bar_length_m": 0.2,
            "test_duration_s": 50.0,
            "boundary_temperature": 25.0,
            "initial_peak_temperature": 75.0,
            "sensor_accuracy": 0.5,
            "created": "2026-10-24T18:00:00Z",
            "updated": "2026-10-24T18:00:00Z",
            "measured_alpha_base": alpha,
            "measured_sigma": sig,
            "row_count": len(r2),
            "is_demo": True
        }
        with open(p2_json, "w", encoding="utf-8") as f:
            json.dump(meta2, f, indent=2)
        with open(p2_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["position_m", "time_s", "temperature_c"])
            for r in r2:
                writer.writerow([r["position_m"], r["time_s"], r["temperature_c"]])

def list_all_profiles() -> List[Dict[str, Any]]:
    """Return summaries for all stored profiles."""
    ensure_profiles_dir()
    profiles = []
    for json_file in PROFILES_DIR.glob("*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                profiles.append(data)
        except Exception:
            continue

    # Sort demos first, then by updated timestamp descending
    profiles.sort(key=lambda p: (not p.get("is_demo", False), p.get("updated", "")), reverse=True)
    return profiles

def get_profile_by_id(profile_id: str) -> Dict[str, Any]:
    """Retrieve full profile with metadata and readings."""
    ensure_profiles_dir()
    valid_id = validate_uuid_str(profile_id)
    
    json_path = PROFILES_DIR / f"{valid_id}.json"
    csv_path = PROFILES_DIR / f"{valid_id}.csv"
    
    if not json_path.exists() or not csv_path.exists():
        raise HTTPException(status_code=404, detail=f"Bar profile '{valid_id}' not found.")
        
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read profile metadata: {str(e)}")

    readings = []
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                readings.append({
                    "position_m": float(row["position_m"]),
                    "time_s": float(row["time_s"]),
                    "temperature_c": float(row["temperature_c"])
                })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read profile readings CSV: {str(e)}")

    meta["readings"] = readings
    return meta

def save_new_profile(
    name: str,
    material_note: str,
    bar_length_m: float,
    test_duration_s: float,
    boundary_temperature: float,
    initial_peak_temperature: float,
    sensor_accuracy: Optional[float],
    readings: List[Dict[str, float]],
    force: bool = False
) -> Dict[str, Any]:
    """Save a new profile to disk after security & save-time checks."""
    ensure_profiles_dir()
    
    # Check max profiles limit (excluding demo overwrite)
    existing_count = len(list(PROFILES_DIR.glob("*.json")))
    if existing_count >= MAX_PROFILES:
        raise HTTPException(
            status_code=422,
            detail=f"Profile library is full (maximum {MAX_PROFILES} profiles allowed). Please delete an existing profile to save a new one."
        )

    # Validate physical coordinates and bounds
    validate_profile_physics(bar_length_m, test_duration_s, boundary_temperature, initial_peak_temperature, readings)

    # Run save-time check
    warning, alpha_base, sig_base, chi2_red = run_save_time_check(
        bar_length_m, test_duration_s, boundary_temperature, initial_peak_temperature, readings, sensor_accuracy
    )

    if warning and not force:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "UNCLEAN_REFERENCE",
                "message": warning,
                "warning": warning,
                "measured_alpha_base": alpha_base,
                "measured_sigma": sig_base,
                "chi2_reduced": chi2_red
            }
        )

    new_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()

    meta = {
        "id": new_id,
        "name": name.strip(),
        "material_note": (material_note or "").strip(),
        "bar_length_m": bar_length_m,
        "test_duration_s": test_duration_s,
        "boundary_temperature": boundary_temperature,
        "initial_peak_temperature": initial_peak_temperature,
        "sensor_accuracy": sensor_accuracy or 0.5,
        "created": now_iso,
        "updated": now_iso,
        "measured_alpha_base": alpha_base,
        "measured_sigma": sig_base,
        "row_count": len(readings),
        "is_demo": False
    }

    json_path = PROFILES_DIR / f"{new_id}.json"
    csv_path = PROFILES_DIR / f"{new_id}.csv"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["position_m", "time_s", "temperature_c"])
        for r in readings:
            writer.writerow([r["position_m"], r["time_s"], r["temperature_c"]])

    meta["readings"] = readings
    meta["warning"] = warning
    return meta

def update_existing_profile(
    profile_id: str,
    name: Optional[str] = None,
    material_note: Optional[str] = None,
    bar_length_m: Optional[float] = None,
    test_duration_s: Optional[float] = None,
    boundary_temperature: Optional[float] = None,
    initial_peak_temperature: Optional[float] = None,
    sensor_accuracy: Optional[float] = None,
    readings: Optional[List[Dict[str, float]]] = None,
    force: bool = False
) -> Dict[str, Any]:
    """Update profile metadata and/or readings."""
    current = get_profile_by_id(profile_id)
    valid_id = validate_uuid_str(profile_id)

    updated_name = name.strip() if name is not None else current["name"]
    updated_note = material_note.strip() if material_note is not None else current.get("material_note", "")
    updated_L = bar_length_m if bar_length_m is not None else current["bar_length_m"]
    updated_T = test_duration_s if test_duration_s is not None else current["test_duration_s"]
    updated_Tb = boundary_temperature if boundary_temperature is not None else current["boundary_temperature"]
    updated_Tp = initial_peak_temperature if initial_peak_temperature is not None else current["initial_peak_temperature"]
    updated_sig = sensor_accuracy if sensor_accuracy is not None else current["sensor_accuracy"]
    updated_readings = readings if readings is not None else current["readings"]

    validate_profile_physics(updated_L, updated_T, updated_Tb, updated_Tp, updated_readings)

    warning, alpha_base, sig_base, chi2_red = run_save_time_check(
        updated_L, updated_T, updated_Tb, updated_Tp, updated_readings, updated_sig
    )

    if warning and not force:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "UNCLEAN_REFERENCE",
                "message": warning,
                "warning": warning,
                "measured_alpha_base": alpha_base,
                "measured_sigma": sig_base,
                "chi2_reduced": chi2_red
            }
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    meta = {
        "id": valid_id,
        "name": updated_name,
        "material_note": updated_note,
        "bar_length_m": updated_L,
        "test_duration_s": updated_T,
        "boundary_temperature": updated_Tb,
        "initial_peak_temperature": updated_Tp,
        "sensor_accuracy": updated_sig,
        "created": current.get("created", now_iso),
        "updated": now_iso,
        "measured_alpha_base": alpha_base,
        "measured_sigma": sig_base,
        "row_count": len(updated_readings),
        "is_demo": current.get("is_demo", False)
    }

    json_path = PROFILES_DIR / f"{valid_id}.json"
    csv_path = PROFILES_DIR / f"{valid_id}.csv"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["position_m", "time_s", "temperature_c"])
        for r in updated_readings:
            writer.writerow([r["position_m"], r["time_s"], r["temperature_c"]])

    meta["readings"] = updated_readings
    meta["warning"] = warning
    return meta

def delete_profile_by_id(profile_id: str) -> Dict[str, Any]:
    """Delete a profile from disk."""
    valid_id = validate_uuid_str(profile_id)
    json_path = PROFILES_DIR / f"{valid_id}.json"
    csv_path = PROFILES_DIR / f"{valid_id}.csv"

    if not json_path.exists() and not csv_path.exists():
        raise HTTPException(status_code=404, detail=f"Bar profile '{valid_id}' not found.")

    if json_path.exists():
        os.remove(json_path)
    if csv_path.exists():
        os.remove(csv_path)

    return {"deleted": True, "id": valid_id}

def create_profile_export_zip(profile_id: str) -> Tuple[io.BytesIO, str]:
    """Create in-memory zip archive containing profile JSON and CSV."""
    profile = get_profile_by_id(profile_id)
    valid_id = validate_uuid_str(profile_id)
    
    json_path = PROFILES_DIR / f"{valid_id}.json"
    csv_path = PROFILES_DIR / f"{valid_id}.csv"

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(json_path, arcname=f"{valid_id}.json")
        z.write(csv_path, arcname=f"{valid_id}.csv")
    buf.seek(0)
    
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in profile.get("name", valid_id))
    filename = f"bar_profile_{safe_name}.zip"
    return buf, filename

def import_profile_from_zip(zip_bytes: bytes, force: bool = False) -> Dict[str, Any]:
    """Extract, validate, and save a profile from an uploaded zip."""
    if len(zip_bytes) > MAX_PAYLOAD_BYTES:
        raise HTTPException(status_code=422, detail="Uploaded file exceeds 1 MB limit.")

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            json_file = next((name for name in z.namelist() if name.endswith(".json")), None)
            csv_file = next((name for name in z.namelist() if name.endswith(".csv")), None)

            if not json_file or not csv_file:
                raise HTTPException(status_code=422, detail="Zip file must contain both a .json metadata file and a .csv readings file.")

            meta_data = json.loads(z.read(json_file).decode("utf-8"))
            csv_text = z.read(csv_file).decode("utf-8")
    except zipfile.BadZipFile:
        raise HTTPException(status_code=422, detail="Malformed zip archive.")
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse imported zip: {str(e)}")

    readings = parse_csv_readings(csv_text)
    return save_new_profile(
        name=meta_data.get("name", "Imported Bar Profile"),
        material_note=meta_data.get("material_note", ""),
        bar_length_m=float(meta_data["bar_length_m"]),
        test_duration_s=float(meta_data["test_duration_s"]),
        boundary_temperature=float(meta_data["boundary_temperature"]),
        initial_peak_temperature=float(meta_data["initial_peak_temperature"]),
        sensor_accuracy=float(meta_data.get("sensor_accuracy", 0.5)),
        readings=readings,
        force=force
    )
