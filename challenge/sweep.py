"""ThermaLens Monte Carlo Simulation Sweep.

Runs parameter estimation and anomaly diagnosis across sensor counts (5, 10, 20)
and noise levels (0.01, 0.05) using 40 fixed-seed episodes per cell.

Writes sweep.csv with:
- median alpha error
- 95% interval coverage
- healthy false-alarm rate
- stuck fault detection & missed-detection rates
- offset fault detection & missed-detection rates
- drift fault detection & missed-detection rates (reported separately)

Usage:
    python -m challenge.sweep [--out challenge/sweep.csv] [--episodes 40] [--seed 20260101]
"""

import os
import sys
import csv
import time
import argparse
from typing import Dict, Any, List

import numpy as np
import scipy.stats as stats

from service.app import (
    APP_STATE,
    precompute_surrogates,
    post_estimate,
    post_diagnose,
    solve_heat_1d_exact
)
from service.models import (
    EstimateRequest,
    DiagnoseRequest,
    SensorReadings,
    BaselineData
)


def run_sweep(out_csv: str = "challenge/sweep.csv", episodes_per_cell: int = 40, base_seed: int = 20260101):
    t_start = time.time()
    print("=" * 80)
    print(f"Starting ThermaLens Monte Carlo Sweep ({episodes_per_cell} episodes/cell, seed={base_seed})")
    print("=" * 80)

    # 1. Initialize surrogates once
    if "prec" not in APP_STATE:
        APP_STATE["prec"] = precompute_surrogates()

    sensor_counts = [5, 10, 20]
    noise_levels = [0.01, 0.05]

    total_runs = len(sensor_counts) * len(noise_levels) * episodes_per_cell * 4
    print(f"Total model evaluations to perform: {total_runs}")
    print("Beginning execution across grid cells...\n")

    summary_rows = []

    cell_idx = 0
    total_cells = len(sensor_counts) * len(noise_levels)

    for N in sensor_counts:
        for sigma in noise_levels:
            cell_idx += 1
            cell_seed = base_seed + (N * 1000) + int(sigma * 100000)
            rng = np.random.RandomState(cell_seed)
            print(f"[{cell_idx}/{total_cells}] Evaluating Cell: N={N:2d} sensors, sigma={sigma:.2f}...")

            # Arrays for Healthy metric collection
            alpha_errors = []
            interval_coverage = []
            healthy_false_alarms = []

            # Arrays for Fault metric collection
            stuck_detected = []
            stuck_missed = []
            offset_detected = []
            offset_missed = []
            drift_detected = []
            drift_missed = []

            # -------------------------------------------------------------
            # Condition 1: Healthy Episodes (Estimation & False Alarms)
            # -------------------------------------------------------------
            for ep in range(episodes_per_cell):
                alpha_true = float(rng.uniform(0.06, 0.35))
                x_ops = np.full(N, 0.5)
                t_ops = np.linspace(0.05, 0.95, N)
                u_ops = solve_heat_1d_exact(x_ops, t_ops, alpha_true)
                y_ops = (u_ops + rng.normal(0.0, sigma, size=N)).tolist()

                # Baseline reference k=25
                x_b = np.tile(np.linspace(0.15, 0.85, 5), 5)[:25]
                t_b = np.repeat(np.linspace(0.10, 0.90, 5), 5)[:25]
                u_b = solve_heat_1d_exact(x_b, t_b, alpha_true)
                y_b = (u_b + rng.normal(0.0, sigma, size=25)).tolist()

                # Estimate
                est_req = EstimateRequest(
                    x_coords=x_ops.tolist(),
                    t_coords=t_ops.tolist(),
                    readings=y_ops,
                    sigma=sigma,
                    mode="mode3plus"
                )
                est_resp = post_estimate(est_req)
                rel_err = abs(est_resp.alpha_hat - alpha_true) / alpha_true
                alpha_errors.append(rel_err)

                in_ci = bool(est_resp.ci95[0] <= alpha_true <= est_resp.ci95[1])
                interval_coverage.append(1.0 if in_ci else 0.0)

                # Diagnose
                diag_req = DiagnoseRequest(
                    readings=SensorReadings(x_coords=x_ops.tolist(), t_coords=t_ops.tolist(), readings=y_ops),
                    baseline=BaselineData(x_coords=x_b.tolist(), t_coords=t_b.tolist(), readings=y_b),
                    sigma=sigma
                )
                diag_resp = post_diagnose(diag_req)
                is_false_alarm = bool(diag_resp.assigned_class != "H")
                healthy_false_alarms.append(1.0 if is_false_alarm else 0.0)

            # -------------------------------------------------------------
            # Condition 2: Stuck Fault Episodes
            # -------------------------------------------------------------
            for ep in range(episodes_per_cell):
                alpha_true = 0.10
                x_ops = np.full(N, 0.5)
                t_ops = np.linspace(0.05, 0.95, N)
                u_ops = solve_heat_1d_exact(x_ops, t_ops, alpha_true)
                y_ops = (u_ops + rng.normal(0.0, sigma, size=N)).copy()

                # Stuck reading on a middle-to-late sensor (frozen at initial decay or fixed high)
                fault_idx = rng.randint(max(1, N // 2), N)
                y_ops[fault_idx] = float(u_ops[0])  # stuck at high initial reading

                x_b = np.tile(np.linspace(0.15, 0.85, 5), 5)[:25]
                t_b = np.repeat(np.linspace(0.10, 0.90, 5), 5)[:25]
                u_b = solve_heat_1d_exact(x_b, t_b, alpha_true)
                y_b = (u_b + rng.normal(0.0, sigma, size=25)).tolist()

                diag_req = DiagnoseRequest(
                    readings=SensorReadings(x_coords=x_ops.tolist(), t_coords=t_ops.tolist(), readings=y_ops.tolist()),
                    baseline=BaselineData(x_coords=x_b.tolist(), t_coords=t_b.tolist(), readings=y_b),
                    sigma=sigma
                )
                diag_resp = post_diagnose(diag_req)
                stuck_detected.append(1.0 if diag_resp.assigned_class == "F" else 0.0)
                stuck_missed.append(1.0 if diag_resp.assigned_class == "H" else 0.0)

            # -------------------------------------------------------------
            # Condition 3: Offset Bias Fault Episodes (+0.25 bias)
            # -------------------------------------------------------------
            for ep in range(episodes_per_cell):
                alpha_true = 0.10
                x_ops = np.full(N, 0.5)
                t_ops = np.linspace(0.05, 0.95, N)
                u_ops = solve_heat_1d_exact(x_ops, t_ops, alpha_true)
                y_ops = (u_ops + rng.normal(0.0, sigma, size=N)).copy()

                fault_idx = rng.randint(0, N)
                y_ops[fault_idx] += 0.25  # +0.25 offset bias

                x_b = np.tile(np.linspace(0.15, 0.85, 5), 5)[:25]
                t_b = np.repeat(np.linspace(0.10, 0.90, 5), 5)[:25]
                u_b = solve_heat_1d_exact(x_b, t_b, alpha_true)
                y_b = (u_b + rng.normal(0.0, sigma, size=25)).tolist()

                diag_req = DiagnoseRequest(
                    readings=SensorReadings(x_coords=x_ops.tolist(), t_coords=t_ops.tolist(), readings=y_ops.tolist()),
                    baseline=BaselineData(x_coords=x_b.tolist(), t_coords=t_b.tolist(), readings=y_b),
                    sigma=sigma
                )
                diag_resp = post_diagnose(diag_req)
                offset_detected.append(1.0 if diag_resp.assigned_class == "F" else 0.0)
                offset_missed.append(1.0 if diag_resp.assigned_class == "H" else 0.0)

            # -------------------------------------------------------------
            # Condition 4: Drift Fault Episodes (Linear ramp drift)
            # -------------------------------------------------------------
            for ep in range(episodes_per_cell):
                alpha_true = 0.10
                x_ops = np.full(N, 0.5)
                t_ops = np.linspace(0.05, 0.95, N)
                u_ops = solve_heat_1d_exact(x_ops, t_ops, alpha_true)
                y_ops = (u_ops + rng.normal(0.0, sigma, size=N)).copy()

                fault_idx = rng.randint(0, N)
                # Linear drift on sensor reading over observation time
                y_ops[fault_idx] += float(0.25 * t_ops[fault_idx])

                x_b = np.tile(np.linspace(0.15, 0.85, 5), 5)[:25]
                t_b = np.repeat(np.linspace(0.10, 0.90, 5), 5)[:25]
                u_b = solve_heat_1d_exact(x_b, t_b, alpha_true)
                y_b = (u_b + rng.normal(0.0, sigma, size=25)).tolist()

                diag_req = DiagnoseRequest(
                    readings=SensorReadings(x_coords=x_ops.tolist(), t_coords=t_ops.tolist(), readings=y_ops.tolist()),
                    baseline=BaselineData(x_coords=x_b.tolist(), t_coords=t_b.tolist(), readings=y_b),
                    sigma=sigma
                )
                diag_resp = post_diagnose(diag_req)
                drift_detected.append(1.0 if diag_resp.assigned_class == "F" else 0.0)
                drift_missed.append(1.0 if diag_resp.assigned_class == "H" else 0.0)

            # Aggregate row
            summary_rows.append({
                "sensors_N": N,
                "noise_sigma": sigma,
                "episodes_per_condition": episodes_per_cell,
                "median_alpha_error": round(float(np.median(alpha_errors)), 4),
                "interval_coverage": round(float(np.mean(interval_coverage)), 4),
                "healthy_false_alarm_rate": round(float(np.mean(healthy_false_alarms)), 4),
                "stuck_detection_rate": round(float(np.mean(stuck_detected)), 4),
                "stuck_missed_rate": round(float(np.mean(stuck_missed)), 4),
                "offset_detection_rate": round(float(np.mean(offset_detected)), 4),
                "offset_missed_rate": round(float(np.mean(offset_missed)), 4),
                "drift_detection_rate": round(float(np.mean(drift_detected)), 4),
                "drift_missed_rate": round(float(np.mean(drift_missed)), 4)
            })

    total_elapsed = round(time.time() - t_start, 2)

    # Write CSV
    os.makedirs(os.path.dirname(os.path.abspath(out_csv)), exist_ok=True)
    fieldnames = [
        "sensors_N", "noise_sigma", "episodes_per_condition",
        "median_alpha_error", "interval_coverage", "healthy_false_alarm_rate",
        "stuck_detection_rate", "stuck_missed_rate",
        "offset_detection_rate", "offset_missed_rate",
        "drift_detection_rate", "drift_missed_rate"
    ]

    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in summary_rows:
            writer.writerow(r)

    print("\n" + "=" * 110)
    print(f" THERMALENS MONTE CARLO SWEEP SUMMARY (Total Time: {total_elapsed}s)")
    print("=" * 110)
    hdr = f"{'N':<4} {'Sigma':<6} {'Med Err':<10} {'Coverage':<10} {'FalseAlarm':<12} {'StuckDet':<10} {'OffsetDet':<11} {'DriftDet':<10} {'DriftMiss':<10}"
    print(hdr)
    print("-" * 110)
    for r in summary_rows:
        n = r['sensors_N']
        s = r['noise_sigma']
        me = f"{r['median_alpha_error']:.4f}"
        cov = f"{r['interval_coverage'] * 100:.1f}%"
        fa = f"{r['healthy_false_alarm_rate'] * 100:.1f}%"
        stuck = f"{r['stuck_detection_rate'] * 100:.1f}%"
        offset = f"{r['offset_detection_rate'] * 100:.1f}%"
        drift = f"{r['drift_detection_rate'] * 100:.1f}%"
        drift_m = f"{r['drift_missed_rate'] * 100:.1f}%"
        print(f"{n:<4} {s:<6.2f} {me:<10} {cov:<10} {fa:<12} {stuck:<10} {offset:<11} {drift:<10} {drift_m:<10}")
    print("=" * 110)
    print(f"\n[Sweep] Results successfully written to: {os.path.abspath(out_csv)}\n")


def main():
    parser = argparse.ArgumentParser(description="ThermaLens Monte Carlo Simulation Sweep")
    parser.add_argument("--out", default="challenge/sweep.csv", help="Output path for sweep.csv (default: challenge/sweep.csv)")
    parser.add_argument("--episodes", type=int, default=40, help="Episodes per cell condition (default: 40)")
    parser.add_argument("--seed", type=int, default=20260101, help="Fixed random seed (default: 20260101)")

    args = parser.parse_args()
    run_sweep(out_csv=args.out, episodes_per_cell=args.episodes, base_seed=args.seed)


if __name__ == "__main__":
    main()

