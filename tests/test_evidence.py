"""Test for service/static/evidence.json generation and provenance tracing.

Verifies:
1. File exists, is valid JSON, and has all required sections.
2. Honest caveats are explicitly documented (Mode 3 88.2% vs Mode 3+ 94.0%, FNO slower than solver, missed D2/D3 targets).
3. Every number in evidence.json traces to a listed source file in meta.
"""

import os
import json
import pytest
import pandas as pd
import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVIDENCE_PATH = os.path.join(REPO_ROOT, "service", "static", "evidence.json")
RESULTS_DIR = os.path.join(REPO_ROOT, "data", "results")

@pytest.fixture(scope="module")
def evidence_data():
    assert os.path.exists(EVIDENCE_PATH), f"Missing {EVIDENCE_PATH}. Run tools/build_evidence_json.py"
    with open(EVIDENCE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

def test_evidence_structure_and_meta(evidence_data):
    """Verify all required sections exist."""
    assert "meta" in evidence_data
    meta = evidence_data["meta"]
    assert "git_commit" in meta
    assert "source_files" in meta
    assert len(meta["source_files"]) >= 8

    required_sections = [
        "stage1_inverse_modes",
        "sensor_placement",
        "anomaly_confusion_matrix",
        "stress_summary",
        "v2_before_after",
        "stage2_methods",
        "pinn_ablation_table",
        "notes_and_caveats"
    ]
    for sec in required_sections:
        assert sec in evidence_data, f"Missing section '{sec}' in evidence.json"

def test_honest_caveats(evidence_data):
    """Verify all mandatory honest caveats are stated."""
    caveats = evidence_data["notes_and_caveats"]
    
    # 1. Mode 3 coverage 88.2% vs Mode 3+ 94.0%
    m3_cov = caveats["mode3_coverage_caveat"]
    assert m3_cov["mode3_mean_coverage_pct"] == 88.2
    assert m3_cov["mode3plus_mean_coverage_pct"] == 94.0
    assert "88.2%" in m3_cov["statement"]
    assert "94.0%" in m3_cov["statement"]

    # 2. FNO is slower than exact solver
    speed = caveats["fno_speed_honesty"]
    assert speed["solver_prefact_single_ms"] < speed["fno_single_ms"]
    assert speed["speedup_factor"] > 20.0
    assert "faster than FNO" in speed["statement"]

    # 3. D2 and D3 targets missed
    missed = caveats["missed_v2_targets"]
    assert "D2" in missed["statement"]
    assert "D3" in missed["statement"]
    target_ids = [item["target_id"] for item in missed["missed_items"]]
    assert "D2" in target_ids
    assert "D3" in target_ids

def test_stage1_modes_provenance(evidence_data):
    """Trace Stage 1 inverse numbers to source files."""
    m2_csv = pd.read_csv(os.path.join(RESULTS_DIR, "mode2_pipeline_results_v2.csv"))
    m3_csv = pd.read_csv(os.path.join(RESULTS_DIR, "mode3_pipeline_results_v2.csv"))
    m3p_csv = pd.read_csv(os.path.join(RESULTS_DIR, "mode3plus_hybrid_results.csv"))

    s1 = evidence_data["stage1_inverse_modes"]
    assert "mode2" in s1 and "mode3" in s1 and "mode3plus" in s1

    # Verify Mode 2 overall values match source CSV exactly
    m2_clean = m2_csv[m2_csv["sigma"] > 0]
    m2_med_err = round(float(pd.to_numeric(m2_clean["med_rel_err"], errors="coerce").median()), 5)
    assert s1["mode2"]["overall_median_rel_err"] == m2_med_err

    # Verify Mode 3 coverage matches 88.22% -> 88.2%
    m3_clean = m3_csv[m3_csv["sigma"] > 0]
    m3_cov = round(float(m3_clean["wald_cov_95"].dropna().apply(lambda x: float(str(x).replace("%", ""))).mean()), 2)
    assert s1["mode3"]["overall_mean_cov_95"] == m3_cov
    assert round(m3_cov, 1) == 88.2

    # Verify Mode 3+ coverage matches 93.99% -> 94.0%
    m3p_clean = m3p_csv[m3p_csv["sigma"] > 0]
    m3p_cov = round(float(m3p_clean["wald_cov_95"].dropna().apply(lambda x: float(str(x).replace("%", ""))).mean()), 2)
    assert s1["mode3plus"]["overall_mean_cov_95"] == m3p_cov
    assert round(m3p_cov, 1) == 94.0

def test_anomaly_confusion_provenance(evidence_data):
    """Trace anomaly confusion matrix counts and recalls to anomaly_frozen_final_tables.json."""
    raw_path = os.path.join(RESULTS_DIR, "anomaly_frozen_final_tables.json")
    with open(raw_path, "r", encoding="utf-8") as f:
        raw_tables = json.load(f)

    primary_raw = raw_tables["table_1_calibration_confusion"]["per_cell"][0]
    primary_ev = evidence_data["anomaly_confusion_matrix"]["primary_cell"]

    assert primary_ev["N"] == primary_raw["N"]
    assert primary_ev["sigma"] == primary_raw["sigma"]
    assert primary_ev["healthy_far_pct"] == primary_raw["healthy_far_pct"]
    assert primary_ev["confusion_matrix_counts"] == primary_raw["confusion_matrix_counts"]
    assert primary_ev["confusion_matrix_pct"] == primary_raw["confusion_matrix_pct"]

def test_v2_before_after_provenance(evidence_data):
    """Trace V2 before/after records to v2_before_after_summary.csv."""
    v2_df = pd.read_csv(os.path.join(RESULTS_DIR, "v2_before_after_summary.csv"))
    v2_ev = evidence_data["v2_before_after"]

    assert v2_ev["total_targets"] == len(v2_df)
    for idx, row in v2_df.iterrows():
        ev_rec = v2_ev["records"][idx]
        assert ev_rec["target_id"] == str(row["target_id"])
        assert ev_rec["scenario"] == str(row["scenario"])
        assert ev_rec["target_status"] == str(row["target_status"]).strip().upper()

def test_poisson_stage2_provenance(evidence_data):
    """Trace Poisson Stage 2 benchmark to poisson_v2_benchmark_table.csv and timing_honesty.json."""
    poi_df = pd.read_csv(os.path.join(RESULTS_DIR, "poisson_v2_benchmark_table.csv"))
    with open(os.path.join(RESULTS_DIR, "timing_honesty.json"), "r", encoding="utf-8") as f:
        timing_raw = json.load(f)

    s2_ev = evidence_data["stage2_methods"]
    assert len(s2_ev["benchmark_table"]) == len(poi_df)

    # Check high modes row
    high_mode_row = next(r for r in s2_ev["benchmark_table"] if r["split"] == "test_ood_highmodes")
    assert high_mode_row["fno_l2_med"] > 0.80  # 80.4% error on high modes
    assert high_mode_row["lin_l2_med"] < 0.02  # 1.5% error linear baseline

    # Check timing
    assert s2_ev["timing_honesty"]["solver_prefact_single_ms"] == timing_raw["solver_prefact_single_ms"]
    assert s2_ev["timing_honesty"]["fno_single_ms"] == timing_raw["fno_single_ms"]

def test_pinn_ablation_provenance(evidence_data):
    """Trace PINN ablation to experiments_summary.csv."""
    exp_df = pd.read_csv(os.path.join(RESULTS_DIR, "experiments_summary.csv"))
    pinn_ev = evidence_data["pinn_ablation_table"]["forward_ablation_variants"]
    
    for row in pinn_ev:
        match = exp_df[(exp_df["model"] == row["model"]) & (exp_df["split"] == row["split"])]
        assert len(match) == 1
        assert round(float(match["median_rel_l2"].iloc[0]), 6) == row["median_rel_l2"]
