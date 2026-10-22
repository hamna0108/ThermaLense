"""Capture real live curl requests and responses from the running service.

Runs curl.exe against http://127.0.0.1:8000 for each endpoint and saves the
exact real request and response into docs/api_examples/.
"""

import os
import sys
import json
import subprocess

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES_DIR = os.path.join(REPO_ROOT, "docs", "api_examples")
os.makedirs(EXAMPLES_DIR, exist_ok=True)

BASE_URL = "http://127.0.0.1:8000"

def run_curl_get(endpoint: str, out_name: str):
    url = f"{BASE_URL}{endpoint}"
    cmd = ["curl.exe", "-s", "-X", "GET", url]
    print(f"Running GET {url} ...")
    raw_res = subprocess.check_output(cmd, text=True)
    res_data = json.loads(raw_res)
    
    out_path = os.path.join(EXAMPLES_DIR, f"{out_name}_response.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(res_data, f, indent=2)
    print(f"  Saved {out_path} ({len(raw_res)} bytes)")
    return res_data

def run_curl_post(endpoint: str, payload: dict, out_name: str):
    url = f"{BASE_URL}{endpoint}"
    req_path = os.path.join(EXAMPLES_DIR, f"{out_name}_request.json")
    with open(req_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        
    cmd = [
        "curl.exe", "-s", "-X", "POST", url,
        "-H", "Content-Type: application/json",
        "-d", "@" + req_path.replace("\\", "/")
    ]
    print(f"Running POST {url} ...")
    raw_res = subprocess.check_output(cmd, text=True)
    res_data = json.loads(raw_res)
    
    out_path = os.path.join(EXAMPLES_DIR, f"{out_name}_response.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(res_data, f, indent=2)
    print(f"  Saved {out_path} ({len(raw_res)} bytes)")
    return payload, res_data

def main():
    print("Capturing live service curl requests & responses...")

    # 1. GET /health
    run_curl_get("/health", "health")

    # 2. GET /version
    run_curl_get("/version", "version")

    # 3. GET /metrics
    run_curl_get("/metrics", "metrics")

    # 4. POST /v1/estimate
    est_req = {
        "x_coords": [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
        "t_coords": [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95],
        "readings": [0.612, 0.228, 0.085, 0.032, 0.012, 0.004, 0.002, 0.001, 0.000, 0.000],
        "sigma": 0.01,
        "mode": "mode3plus",
        "physics_config": {
            "u0_expr": "sin(pi * x)"
        }
    }
    run_curl_post("/v1/estimate", est_req, "estimate")

    # 5. POST /v1/diagnose
    diag_req = {
        "readings": {
            "x_coords": [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
            "t_coords": [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95],
            "readings": [0.612, 0.225, 0.083, 0.031, 0.511, 0.004, 0.002, 0.001, 0.000, 0.000]
        },
        "baseline": {
            "x_coords": [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
            "t_coords": [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00],
            "readings": [0.612, 0.373, 0.228, 0.139, 0.085, 0.052, 0.032, 0.019, 0.012, 0.007, 0.004, 0.003, 0.002, 0.001, 0.001, 0.000, 0.000, 0.000, 0.000, 0.000]
        },
        "sigma": 0.01
    }
    run_curl_post("/v1/diagnose", diag_req, "diagnose")

    # 6. POST /v1/placement
    placement_req = {
        "N": 20,
        "sigma": 0.01,
        "sensor_x": 0.5
    }
    run_curl_post("/v1/placement", placement_req, "placement")

    # 7. POST /v1/field
    field_req = {
        "alpha": 0.10,
        "method": "fno",
        "Nx": 64,
        "Nt": 64
    }
    run_curl_post("/v1/field", field_req, "field")

    # 8. POST /v1/poisson
    poisson_req = {
        "source": {
            "type": "sine",
            "modes": [[2, 2]],
            "amplitudes": [1.0]
        },
        "grid_size": 64
    }
    run_curl_post("/v1/poisson", poisson_req, "poisson")

    print("All live curl examples successfully captured into docs/api_examples/")

if __name__ == "__main__":
    main()
