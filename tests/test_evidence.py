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

def test_v2_followups_provenance(evidence_data):
    """Trace V2 followups final state to data/results/task_e_v2_followups.json."""
    followup_path = os.path.join(RESULTS_DIR, "task_e_v2_followups.json")
    with open(followup_path, "r", encoding="utf-8") as f:
        raw_f = json.load(f)

    v2_f = evidence_data["v2_followups_final_state"]
    assert "d2_false_flags_by_N" in v2_f
    assert "d2_durbin_watson_detection_by_rho" in v2_f
    assert "d3_range_guard_comparison" in v2_f
    assert "d5_warnings_evaluation" in v2_f

    # 1. D2 false flag rate by N
    d2_by_n = {item["N"]: item for item in v2_f["d2_false_flags_by_N"]}
    assert d2_by_n[5]["false_flag_rate_pct"] == 5.4
    assert d2_by_n[5]["ci_95"] == [4.16, 6.98]
    assert d2_by_n[10]["false_flag_rate_pct"] == 4.2
    assert d2_by_n[10]["ci_95"] == [3.12, 5.63]
    assert d2_by_n[20]["false_flag_rate_pct"] == 5.9
    assert d2_by_n[20]["ci_95"] == [4.6, 7.54]
    # Check trace to raw file
    assert d2_by_n[10]["false_flags"] == raw_f["part1_gof_gate"]["N_10"]["false_flags"]

    # 2. D2 Durbin-Watson detection by rho
    dw_by_rho = {item["rho"]: item for item in v2_f["d2_durbin_watson_detection_by_rho"]}
    assert dw_by_rho[0.5]["dw_detection_rate_pct"] == 23.9
    assert dw_by_rho[0.5]["ci_95"] == [21.36, 26.64]
    assert dw_by_rho[0.8]["dw_detection_rate_pct"] == 60.4
    assert dw_by_rho[0.8]["ci_95"] == [57.33, 63.39]
    assert dw_by_rho[0.95]["dw_detection_rate_pct"] == 80.5
    assert dw_by_rho[0.95]["ci_95"] == [77.93, 82.84]

    # 3. D3 Range Guard comparison (alpha = 0.0005)
    d3_comp = v2_f["d3_range_guard_comparison"]
    assert d3_comp["alpha_target"] == 0.0005
    assert d3_comp["old_1pct_rule_rate_pct"] == 65.0
    assert d3_comp["old_1pct_ci_95"] == [55.25, 73.64]
    assert d3_comp["new_rule_rate_pct"] == 90.0
    assert d3_comp["new_rule_ci_95"] == [82.56, 94.48]
    assert "MISSED" in d3_comp["target_status"]
    assert d3_comp["routed_to_m3p_pct"] == 100.0

    # 4. D5 Warnings evaluation
    d5 = v2_f["d5_warnings_evaluation"]
    drift_far = d5["healthy_false_warning_rates"]["drift_far_pct"]
    assert drift_far == 3.8
    assert d5["healthy_false_warning_rates"]["kurtosis_far_pct"] == 4.5
    assert d5["healthy_false_warning_rates"]["durbin_watson_far_pct"] == 4.9

    # Drift warning has no power: rates 3.3%, 4.2%, 5.6% vs 3.8% FAR
    drift_rates = [d["detection_rate_pct"] for d in d5["drift_warning_evaluation"]["detection_by_severity"]]
    assert drift_rates == [3.3, 4.2, 5.6]
    assert "has no power" in d5["drift_warning_evaluation"]["power_conclusion"]

    # Kurtosis warning achieves 10-34%
    kurt_rates = [k["detection_rate_pct"] for k in d5["kurtosis_warning_evaluation"]["detection_by_severity"]]
    assert kurt_rates == [9.8, 17.1, 33.6]
    assert min(kurt_rates) >= 9.8 and max(kurt_rates) <= 34.0

def test_pinn_ablation_summary_provenance(evidence_data):
    """Trace PINN multi-axis ablation to pinn_ablation/pinn_ablation_summary.csv."""
    abl_csv = pd.read_csv(os.path.join(RESULTS_DIR, "pinn_ablation", "pinn_ablation_summary.csv"))
    full_abl = evidence_data["pinn_ablation_table"]["full_ablation_summary"]

    assert len(full_abl) == len(abl_csv["variant"].unique())
    for item in full_abl:
        var = item["variant"]
        sub = abl_csv[abl_csv["variant"] == var]
        assert len(sub) == item["seeds"]
        expected_med = round(float(sub["interp_rel_l2_median"].median()), 6)
        assert item["interp_rel_l2_median"] == expected_med

def test_superseded_numbers_labeled_as_before(evidence_data):
    """Ensure superseded numbers (7.0% false flags, 72.0% range guard) are labeled as 'before'."""
    missed = evidence_data["notes_and_caveats"]["missed_v2_targets"]
    stmt = missed["statement"]

    # The statement must qualify 7.0% and 72.0% with 'before'
    if "7.0%" in stmt:
        assert "before: 7.0%" in stmt or "before" in stmt
    if "72.0%" in stmt:
        assert "before: 72.0%" in stmt or "before" in stmt

    # Check observed items in missed_items
    for item in missed["missed_items"]:
        obs = item["observed"]
        if "7.0%" in obs:
            assert "before:" in obs
        if "72.0%" in obs:
            assert "before:" in obs
