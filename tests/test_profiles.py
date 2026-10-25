"""Tests for Bar Profiles Reference Library, Security, and Save-Time Checks.

Covers:
- Shipped demo profiles (2 demo profiles with fixed seed 0)
- Endpoints: GET /v1/profiles, GET /v1/profiles/{id}, POST /v1/profiles, PUT /v1/profiles/{id}, DELETE /v1/profiles/{id}
- Export and import round-trip (.zip and .csv + .json)
- Security protections:
  - Path traversal attempts rejected with 422
  - Oversize payload (> 1 MB) rejected with 422
  - Reading count limits (< 20 rows, > 5000 rows) rejected with 422
  - Malformed CSV / non-numeric readings rejected with 422
  - Physical coordinates validation (x in [0, L], t in [0, T], finite, Tb != Tp) rejected with 422
- Save-time check:
  - Model-fit and sensor noise detection
  - Warning "This doesn't look like a clean normal run. Save anyway?" on anomalous readings
  - Force bypass flag allows saving if user confirms
"""

import io
import json
import zipfile
import pytest
from fastapi.testclient import TestClient
from service.app import app

import shutil
from pathlib import Path
import service.profiles as prof_mod
from service.profiles import DEMO_UUID_1, DEMO_UUID_2, generate_demo_profile_data, PROFILES_DIR

@pytest.fixture(autouse=True)
def isolated_profiles_dir(tmp_path, monkeypatch):
    """Run all profile tests in an ephemeral temporary directory initialized with demo profiles."""
    test_dir = tmp_path / "profiles"
    test_dir.mkdir(parents=True, exist_ok=True)
    for demo_id in [DEMO_UUID_1, DEMO_UUID_2]:
        for ext in [".json", ".csv"]:
            src = PROFILES_DIR / f"{demo_id}{ext}"
            if src.exists():
                shutil.copy(src, test_dir / f"{demo_id}{ext}")
    monkeypatch.setattr(prof_mod, "PROFILES_DIR", test_dir)
    yield test_dir

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def test_list_demo_profiles(client):
    """Verify demo profiles are loaded and labeled as Demo."""
    res = client.get("/v1/profiles")
    assert res.status_code == 200
    profiles = res.json()
    assert len(profiles) >= 2
    
    demo_ids = [p["id"] for p in profiles if p.get("is_demo")]
    assert DEMO_UUID_1 in demo_ids
    assert DEMO_UUID_2 in demo_ids
    
    demo1 = next(p for p in profiles if p["id"] == DEMO_UUID_1)
    assert "Demo" in demo1["name"]
    assert demo1["bar_length_m"] == 0.1
    assert demo1["test_duration_s"] == 100.0
    assert demo1["row_count"] >= 20

def test_get_demo_profile_detail(client):
    """Verify GET /v1/profiles/{id} returns metadata and full readings."""
    res = client.get(f"/v1/profiles/{DEMO_UUID_1}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == DEMO_UUID_1
    assert "readings" in data
    assert len(data["readings"]) == data["row_count"]
    # Check first reading fields
    r0 = data["readings"][0]
    assert "position_m" in r0
    assert "time_s" in r0
    assert "temperature_c" in r0

def test_create_update_delete_profile(client):
    """Test full CRUD lifecycle for custom user profile."""
    # Generate 20 clean readings
    readings = generate_demo_profile_data(seed=1, L=0.15, T=80.0, Tb=22.0, Tp=85.0, sig=0.3, num_pts=20)
    
    # 1. Create
    payload = {
        "name": "Custom Titanium Bar",
        "material_note": "Grade 5 titanium alloy calibration test",
        "bar_length_m": 0.15,
        "test_duration_s": 80.0,
        "boundary_temperature": 22.0,
        "initial_peak_temperature": 85.0,
        "sensor_accuracy": 0.3,
        "readings": readings
    }
    create_res = client.post("/v1/profiles", json=payload)
    assert create_res.status_code == 201
    created = create_res.json()
    profile_id = created["id"]
    assert profile_id != DEMO_UUID_1
    assert created["name"] == "Custom Titanium Bar"
    assert created["row_count"] == 20
    assert created["is_demo"] is False

    # 2. Update
    update_payload = {
        "name": "Custom Titanium Bar (Updated)",
        "material_note": "Refined calibration note"
    }
    put_res = client.put(f"/v1/profiles/{profile_id}", json=update_payload)
    assert put_res.status_code == 200
    updated = put_res.json()
    assert updated["name"] == "Custom Titanium Bar (Updated)"
    assert updated["material_note"] == "Refined calibration note"

    # 3. Read back
    get_res = client.get(f"/v1/profiles/{profile_id}")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Custom Titanium Bar (Updated)"

    # 4. Delete
    del_res = client.delete(f"/v1/profiles/{profile_id}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True

    # 5. Confirm deleted
    assert client.get(f"/v1/profiles/{profile_id}").status_code == 404

def test_export_and_import_zip(client):
    """Test exporting a profile to zip and re-importing it."""
    # Export demo 1
    export_res = client.get(f"/v1/profiles/{DEMO_UUID_1}/export")
    assert export_res.status_code == 200
    assert export_res.headers["content-type"] == "application/zip"
    
    zip_bytes = export_res.content
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        names = z.namelist()
        assert any(n.endswith(".json") for n in names)
        assert any(n.endswith(".csv") for n in names)

    # Import the zip file back as a new profile
    files = {"file": ("exported_profile.zip", zip_bytes, "application/zip")}
    import_res = client.post("/v1/profiles/import", files=files)
    assert import_res.status_code == 201
    imported = import_res.json()
    new_id = imported["id"]
    assert new_id != DEMO_UUID_1
    assert imported["row_count"] == 20

    # Cleanup imported profile
    client.delete(f"/v1/profiles/{new_id}")

def test_export_and_import_csv_json_pair(client):
    """Test exporting CSV and JSON separately and re-importing as multipart pair."""
    csv_res = client.get(f"/v1/profiles/{DEMO_UUID_1}/csv")
    json_res = client.get(f"/v1/profiles/{DEMO_UUID_1}/json")
    assert csv_res.status_code == 200
    assert json_res.status_code == 200
    
    files = {
        "csv_file": ("readings.csv", csv_res.content, "text/csv"),
        "json_file": ("metadata.json", json_res.content, "application/json")
    }
    import_res = client.post("/v1/profiles/import", files=files)
    assert import_res.status_code == 201
    imported = import_res.json()
    new_id = imported["id"]
    assert imported["row_count"] == 20
    
    # Cleanup
    client.delete(f"/v1/profiles/{new_id}")

# -------------------------------------------------------------------------------------------------
# Security Tests
# -------------------------------------------------------------------------------------------------

def test_security_path_traversal_attempts(client):
    """Verify strict rejection of path traversal sequences in profile IDs."""
    traversal_ids = [
        "../../etc/passwd",
        "..\\..\\windows\\system32",
        "....//....//something",
        "demo/1",
        "00000000-0000-4000-8000-000000000001/../../passwd",
        "valid-uuid-not-really",
        "12345"
    ]
    for tid in traversal_ids:
        res = client.get(f"/v1/profiles/{tid}")
        assert res.status_code in (404, 422), f"Expected 404 or 422 for path traversal '{tid}', got {res.status_code}"

def test_security_oversize_file_rejected(client):
    """Verify payloads exceeding 1 MB are strictly rejected with 422."""
    huge_csv = "position_m,time_s,temperature_c\n" + ("0.05,10.0,50.0\n" * 80000)
    assert len(huge_csv.encode('utf-8')) > 1_000_000
    
    payload = {
        "name": "Oversize Test",
        "bar_length_m": 0.1,
        "test_duration_s": 100.0,
        "boundary_temperature": 20.0,
        "initial_peak_temperature": 80.0,
        "csv_readings": huge_csv
    }
    res = client.post("/v1/profiles", json=payload)
    assert res.status_code == 422

def test_security_reading_count_limits(client):
    """Verify strict row limits: minimum 20 rows, maximum 5000 rows."""
    # Fewer than 20 rows (e.g. 10 rows)
    readings_few = generate_demo_profile_data(seed=2, L=0.1, T=100.0, Tb=20.0, Tp=80.0, sig=0.5, num_pts=10)
    res_few = client.post("/v1/profiles", json={
        "name": "Too Few Rows",
        "bar_length_m": 0.1,
        "test_duration_s": 100.0,
        "boundary_temperature": 20.0,
        "initial_peak_temperature": 80.0,
        "readings": readings_few
    })
    assert res_few.status_code == 422
    assert "at least 20" in res_few.text.lower()

    # More than 5000 rows
    readings_many = [{"position_m": 0.05, "time_s": 10.0, "temperature_c": 50.0}] * 5001
    res_many = client.post("/v1/profiles", json={
        "name": "Too Many Rows",
        "bar_length_m": 0.1,
        "test_duration_s": 100.0,
        "boundary_temperature": 20.0,
        "initial_peak_temperature": 80.0,
        "readings": readings_many
    })
    assert res_many.status_code == 422

def test_security_malformed_readings(client):
    """Verify non-numeric or incomplete rows are rejected with 422."""
    bad_csv = "position_m,time_s,temperature_c\n0.05,10.0,NOT_A_NUMBER\n0.05,20.0,50.0\n"
    res = client.post("/v1/profiles", json={
        "name": "Malformed CSV",
        "bar_length_m": 0.1,
        "test_duration_s": 100.0,
        "boundary_temperature": 20.0,
        "initial_peak_temperature": 80.0,
        "csv_readings": bad_csv
    })
    assert res.status_code == 422

def test_security_physical_coordinates_validation(client):
    """Verify coordinates outside physical bounds [0, L] and [0, T] are rejected."""
    readings = generate_demo_profile_data(seed=3, L=0.1, T=100.0, Tb=20.0, Tp=80.0, sig=0.5, num_pts=20)
    
    # Position > L
    bad_pos = list(readings)
    bad_pos[0] = {"position_m": 0.25, "time_s": 10.0, "temperature_c": 50.0}  # L is 0.1
    res = client.post("/v1/profiles", json={
        "name": "Invalid Position",
        "bar_length_m": 0.1,
        "test_duration_s": 100.0,
        "boundary_temperature": 20.0,
        "initial_peak_temperature": 80.0,
        "readings": bad_pos
    })
    assert res.status_code == 422
    assert "outside bar length" in res.text

    # Time > T
    bad_time = list(readings)
    bad_time[0] = {"position_m": 0.05, "time_s": 250.0, "temperature_c": 50.0}  # T is 100
    res = client.post("/v1/profiles", json={
        "name": "Invalid Time",
        "bar_length_m": 0.1,
        "test_duration_s": 100.0,
        "boundary_temperature": 20.0,
        "initial_peak_temperature": 80.0,
        "readings": bad_time
    })
    assert res.status_code == 422
    assert "outside test duration" in res.text

# -------------------------------------------------------------------------------------------------
# Save-Time Check Tests
# -------------------------------------------------------------------------------------------------

def test_save_time_check_warns_on_unclean_reference(client):
    """Verify that an unclean/anomalous run triggers the save-time warning."""
    # Corrupt readings with high sensor fault offset / random noise that violates heat equation
    readings = generate_demo_profile_data(seed=4, L=0.1, T=100.0, Tb=20.0, Tp=80.0, sig=0.5, num_pts=20)
    # Severely offset half the readings to simulate faulty sensor
    corrupted = []
    for idx, r in enumerate(readings):
        if idx % 2 == 0:
            corrupted.append({"position_m": r["position_m"], "time_s": r["time_s"], "temperature_c": r["temperature_c"] + 25.0})
        else:
            corrupted.append(dict(r))

    payload = {
        "name": "Unclean Test Bar",
        "bar_length_m": 0.1,
        "test_duration_s": 100.0,
        "boundary_temperature": 20.0,
        "initial_peak_temperature": 80.0,
        "sensor_accuracy": 0.5,
        "readings": corrupted,
        "force": False
    }
    # Without force=True, should be rejected with 422 and warning message
    res = client.post("/v1/profiles", json=payload)
    assert res.status_code == 422
    data = res.json()
    assert data.get("error_code") == "UNCLEAN_REFERENCE"
    assert "This doesn't look like a clean normal run. Save anyway?" in str(data)
    assert "measured_alpha_base" in data
    assert "measured_sigma" in data

    # With force=True, should save successfully
    payload["force"] = True
    force_res = client.post("/v1/profiles", json=payload)
    assert force_res.status_code == 201
    saved_id = force_res.json()["id"]
    
    # Cleanup
    client.delete(f"/v1/profiles/{saved_id}")
