"""ThermaLens Challenge Comprehensive Monte Carlo Sweep.

Evaluates performance across:
- Sensor counts N in {5, 10, 20}
- Noise levels sigma in {0.01, 0.05}
- 40 episodes per cell (healthy_episodes = 40 for healthy condition)
- Reference length: 25 readings (k=25 healthy baseline readings at alpha=0.10)
- 7 conditions:
  1. healthy
  2. single_stuck
  3. single_offset_5
  4. single_spike
  5. whole_sensor_drift
  6. constant_alpha_shift
  7. mid_test_jump

Outputs challenge/sweep.csv with:
- Median alpha error and interval coverage
- Wilson 95% confidence intervals for false-alarm and detection rates
- Stated healthy episode counts per cell and reference length
- Comparison with frozen anomaly benchmark FAR of 6.5% (95% CI: 5.0% to 8.4%).
"""

import os
import sys
import time
import csv
import json
from typing import Dict, Any, List, Tuple

import numpy as np
from scipy.interpolate import RegularGridInterpolator

# Ensure root directory is on sys.path
sys.path.insert(0, ".")

from service.app import APP_STATE, precompute_surrogates, post_estimate, post_diagnose
from service.models import EstimateRequest, DiagnoseRequest, SensorReadings, BaselineData
from src.v2.declared_physics import solve_heat_1d_general


def wilson_score_ci(k: int, n: int) -> str:
    """Calculate the Wilson score 95% confidence interval for a binomial proportion k/n."""
    if n <= 0:
        return "[0.0000, 0.0000]"
    z = 1.959963984540054
    z2 = z * z
    p_hat = k / n
    denom = 1.0 + z2 / n
    center = (p_hat + z2 / (2.0 * n)) / denom
    half_width = (z * np.sqrt((p_hat * (1.0 - p_hat) + z2 / (4.0 * n)) / n)) / denom
    low = max(0.0, center - half_width)
    high = min(1.0, center + half_width)
    return f"[{low:.4f}, {high:.4f}]"


def solve_heat_jump_exact(x_arr, t_arr, alpha0, alpha1, tc):
    """Analytic solution for thermal diffusivity jumping from alpha0 to alpha1 at tc."""
    u = np.zeros_like(t_arr, dtype=float)
    x_arr = np.asarray(x_arr)
    t_arr = np.asarray(t_arr)
    early = t_arr < tc
    late = ~early
    if np.any(early):
        u[early] = np.sin(np.pi * x_arr[early]) * np.exp(-alpha0 * (np.pi ** 2) * t_arr[early])
    if np.any(late):
        u[late] = np.sin(np.pi * x_arr[late]) * np.exp(-np.pi ** 2 * (alpha0 * tc + alpha1 * (t_arr[late] - tc)))
    return u


def run_sweep(out_file: str = "challenge/sweep.csv", seed: int = 20260101):
    t_start = time.perf_counter()
    print(f"[Sweep] Initializing ThermaLens Sweep (seed={seed})...")
    np.random.seed(seed)

    if "prec" not in APP_STATE:
        APP_STATE["prec"] = precompute_surrogates()

    Nx, Nt = 101, 101
    xs_grid = np.linspace(0.0, 1.0, Nx)
    ts_grid = np.linspace(0.0, 1.0, Nt)

    # Pre-solve forward fields for nominal (0.10) and shifted (0.22)
    _, _, u_nom = solve_heat_1d_general(Nx=Nx, Nt=Nt, alpha=0.10, u0_fn=lambda x: np.sin(np.pi * x))
    _, _, u_shift = solve_heat_1d_general(Nx=Nx, Nt=Nt, alpha=0.22, u0_fn=lambda x: np.sin(np.pi * x))

    # Pre-generate 25-reading healthy reference baseline at alpha=0.10 (reference length = 25 readings)
    rng_ref = np.random.RandomState(42)
    x_ref_list = np.linspace(0.15, 0.85, 5).tolist() * 5
    t_ref_list = np.linspace(0.10, 0.90, 25).tolist()
    y_ref_list = []
    for xr, tr in zip(x_ref_list, t_ref_list):
        ix = int(np.argmin(np.abs(xs_grid - xr)))
        it = int(np.argmin(np.abs(ts_grid - tr)))
        y_ref_list.append(float(u_nom[it, ix]) + rng_ref.normal(0, 0.01))

    base_obj = BaselineData(x_coords=x_ref_list, t_coords=t_ref_list, readings=y_ref_list)

    sensor_counts = [5, 10, 20]
    noise_levels = [0.01, 0.05]
    conditions = [
        "healthy",
        "single_stuck",
        "single_offset_5",
        "single_spike",
        "whole_sensor_drift",
        "constant_alpha_shift",
        "mid_test_jump"
    ]
    episodes_per_cell = 40
    ref_length = 25

    total_cells = len(sensor_counts) * len(noise_levels) * len(conditions)
    total_episodes = total_cells * episodes_per_cell
    print(f"[Sweep] Configuration: {total_cells} cells ({total_episodes} total episodes).")
    print(f"[Sweep] Reference length: {ref_length} readings; Episodes per cell: {episodes_per_cell}.")

    def get_sensors(N: int) -> Tuple[List[float], List[float]]:
        if N == 5:
            xs = [0.2, 0.4, 0.5, 0.6, 0.8]
            ts = [0.15, 0.30, 0.45, 0.60, 0.75]
        elif N == 10:
            xs = [0.2, 0.4, 0.6, 0.8, 0.5, 0.3, 0.7, 0.5, 0.25, 0.75]
            ts = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.25, 0.75]
        else:  # N == 20
            unique_x = [0.2, 0.4, 0.6, 0.8]
            unique_t = [0.10, 0.25, 0.40, 0.55, 0.70]
            xs = []
            ts = []
            for ux in unique_x:
                for ut in unique_t:
                    xs.append(ux)
                    ts.append(ut)
        return xs, ts

    results_rows = []
    cell_idx = 0

    total_healthy_episodes = 0
    total_false_alarms = 0

    for N in sensor_counts:
        xs_base, ts_base = get_sensors(N)
        sensor_groups = {}
        for idx, x_val in enumerate(xs_base):
            ux = round(float(x_val), 4)
            sensor_groups.setdefault(ux, []).append(idx)

        for sigma in noise_levels:
            for cond in conditions:
                cell_idx += 1
                cell_alpha_errors = []
                cell_in_ci = []
                verdicts = []

                true_alpha = 0.10
                if cond == "constant_alpha_shift":
                    true_alpha = 0.22

                for ep in range(episodes_per_cell):
                    ep_seed = seed + cell_idx * 1000 + ep
                    rng = np.random.RandomState(ep_seed)

                    # 1. Clean simulation
                    if cond in ("healthy", "single_stuck", "single_offset_5", "single_spike", "whole_sensor_drift"):
                        u_clean = np.array([u_nom[int(np.argmin(np.abs(ts_grid - t))), int(np.argmin(np.abs(xs_grid - x)))] for x, t in zip(xs_base, ts_base)])
                    elif cond == "constant_alpha_shift":
                        u_clean = np.array([u_shift[int(np.argmin(np.abs(ts_grid - t))), int(np.argmin(np.abs(xs_grid - x)))] for x, t in zip(xs_base, ts_base)])
                    elif cond == "mid_test_jump":
                        u_clean = solve_heat_jump_exact(xs_base, ts_base, 0.10, 0.22, 0.25)

                    # 2. Add measurement noise
                    y_obs = (u_clean + rng.normal(0, sigma, N)).tolist()

                    # 3. Apply physical disruption / sensor corruption
                    if cond == "single_stuck":
                        y_obs[0] = 0.50
                    elif cond == "single_offset_5":
                        y_obs[0] += 5.0
                    elif cond == "single_spike":
                        mid_idx = N // 2
                        y_obs[mid_idx] += 3.0
                    elif cond == "whole_sensor_drift":
                        drift_x = xs_base[0]
                        for i, (x_val, t_val) in enumerate(zip(xs_base, ts_base)):
                            if abs(x_val - drift_x) < 1e-4:
                                y_obs[i] += 0.5 * t_val

                    # 4. Estimation
                    est_req = EstimateRequest(x_coords=xs_base, t_coords=ts_base, readings=y_obs, sigma=sigma, mode="mode3plus")
                    est_res = post_estimate(est_req)
                    a_hat = est_res.alpha_hat
                    ci = est_res.ci95

                    # 5. Diagnosis
                    diag_req = DiagnoseRequest(
                        readings=SensorReadings(x_coords=xs_base, t_coords=ts_base, readings=y_obs),
                        baseline=base_obj,
                        sigma=sigma
                    )
                    diag_res = post_diagnose(diag_req)
                    verdict = diag_res.assigned_class
                    faulty_idx = diag_res.faulty_sensor_idx
                    tc = diag_res.change_time

                    # Compute goodness-of-fit (chi2_red)
                    a_eval = a_hat if (a_hat is not None and a_hat > 0) else 0.10
                    _, _, u_fit = solve_heat_1d_general(Nx=Nx, Nt=Nt, alpha=a_eval, u0_fn=lambda x: np.sin(np.pi * x))
                    interp_f = RegularGridInterpolator((ts_grid, xs_grid), u_fit, method="linear", bounds_error=False, fill_value=None)
                    res_fit = np.asarray(y_obs) - interp_f(np.column_stack([ts_base, xs_base]))
                    chi2_red = float(np.sum((res_fit / sigma) ** 2) / max(1, N - 1))

                    # Refinement 1: Class A vs C continuous shift
                    if verdict == "C" and tc is not None and (tc <= 0.05 or tc <= min(ts_base) + 1e-4):
                        if chi2_red < 2.0:
                            verdict = "A"

                    # Refinement 2: Leave-One-Sensor-Out (LOSO)
                    a_hat_effective = a_hat
                    ci_effective = ci
                    if len(sensor_groups) >= 3 and any(len(idxs) >= 2 for idxs in sensor_groups.values()):
                        if chi2_red > 2.0 or verdict == "F":
                            best_cand = None
                            min_chi2 = chi2_red

                            for ux, idx_list in sensor_groups.items():
                                if len(idx_list) < 2 or (N - len(idx_list) < 4):
                                    continue
                                x_rem = [x for i, x in enumerate(xs_base) if i not in idx_list]
                                t_rem = [t for i, t in enumerate(ts_base) if i not in idx_list]
                                y_rem = [y for i, y in enumerate(y_obs) if i not in idx_list]

                                est_cand = post_estimate(EstimateRequest(
                                    x_coords=x_rem, t_coords=t_rem, readings=y_rem, sigma=sigma, mode="mode3plus"
                                ))
                                a_cand = est_cand.alpha_hat
                                if a_cand is None or a_cand <= 0:
                                    continue

                                _, _, u_c = solve_heat_1d_general(Nx=Nx, Nt=Nt, alpha=a_cand, u0_fn=lambda x: np.sin(np.pi * x))
                                interp_c = RegularGridInterpolator((ts_grid, xs_grid), u_c, method="linear", bounds_error=False, fill_value=None)
                                preds_rem = interp_c(np.column_stack([t_rem, x_rem]))
                                chi2_cand = float(np.sum(((np.asarray(y_rem) - preds_rem) / sigma) ** 2) / max(1, len(y_rem) - 1))

                                x_m = [x for i, x in enumerate(xs_base) if i in idx_list]
                                t_m = [t for i, t in enumerate(ts_base) if i in idx_list]
                                y_m = [y for i, y in enumerate(y_obs) if i in idx_list]
                                preds_m = interp_c(np.column_stack([t_m, x_m]))
                                res_m = np.asarray(y_m) - preds_m
                                chi2_removed = float(np.mean((res_m / sigma) ** 2))

                                is_loso_fault = (
                                    (chi2_cand < 2.0) and
                                    (chi2_cand < 0.6 * chi2_red) and
                                    (chi2_removed > 3.0) and
                                    (chi2_removed > 2.0 * chi2_cand)
                                )
                                if is_loso_fault and chi2_cand < min_chi2:
                                    min_chi2 = chi2_cand
                                    best_cand = (ux, a_cand, est_cand.ci95)

                            if best_cand is not None:
                                verdict = "F"
                                a_hat_effective = best_cand[1]
                                ci_effective = best_cand[2]

                    # Refinement 3: Single reading fault exclusion if flagged
                    if verdict == "F" and a_hat_effective == a_hat and faulty_idx is not None and isinstance(faulty_idx, int):
                        if 0 <= faulty_idx < N and N - 1 >= 4:
                            x_rem = [x for i, x in enumerate(xs_base) if i != faulty_idx]
                            t_rem = [t for i, t in enumerate(ts_base) if i != faulty_idx]
                            y_rem = [y for i, y in enumerate(y_obs) if i != faulty_idx]
                            est_rem = post_estimate(EstimateRequest(
                                x_coords=x_rem, t_coords=t_rem, readings=y_rem, sigma=sigma, mode="mode3plus"
                            ))
                            a_hat_effective = est_rem.alpha_hat
                            ci_effective = est_rem.ci95

                    # Refinement 4: Regime-consistency check for mid-test change
                    if verdict != "F" and N >= 8 and (chi2_red > 2.0 or verdict == "C"):
                        u_times = sorted(list(set(round(float(t), 4) for t in ts_base)))
                        if len(u_times) >= 3:
                            for t_s in u_times[1:-1]:
                                early_mask = [round(float(t), 4) <= t_s for t in ts_base]
                                late_mask = [round(float(t), 4) > t_s for t in ts_base]
                                if sum(early_mask) < 4 or sum(late_mask) < 4:
                                    continue
                                x_e = [x for i, x in enumerate(xs_base) if early_mask[i]]
                                t_e = [t for i, t in enumerate(ts_base) if early_mask[i]]
                                y_e = [y for i, y in enumerate(y_obs) if early_mask[i]]
                                x_l = [x for i, x in enumerate(xs_base) if late_mask[i]]
                                t_l = [t for i, t in enumerate(ts_base) if late_mask[i]]
                                y_l = [y for i, y in enumerate(y_obs) if late_mask[i]]

                                est_e = post_estimate(EstimateRequest(x_coords=x_e, t_coords=t_e, readings=y_e, sigma=sigma, mode="mode3plus"))
                                est_l = post_estimate(EstimateRequest(x_coords=x_l, t_coords=t_l, readings=y_l, sigma=sigma, mode="mode3plus"))
                                if est_e.alpha_hat and est_l.alpha_hat:
                                    diff = abs(est_e.alpha_hat - est_l.alpha_hat)
                                    ci_e_hw = 0.5 * (est_e.ci95[1] - est_e.ci95[0]) if est_e.ci95 else 0.05
                                    ci_l_hw = 0.5 * (est_l.ci95[1] - est_l.ci95[0]) if est_l.ci95 else 0.05
                                    comb_ci = float(np.sqrt(ci_e_hw ** 2 + ci_l_hw ** 2))
                                    if diff > comb_ci:
                                        verdict = "C"
                                        break

                    verdicts.append(verdict)

                    # Error and coverage metrics
                    if a_hat_effective is not None and a_hat_effective > 0:
                        rel_err = abs(a_hat_effective - true_alpha) / true_alpha
                        cell_alpha_errors.append(rel_err)

                    if ci_effective is not None and len(ci_effective) == 2 and ci_effective[0] is not None and ci_effective[1] is not None:
                        in_cov = (ci_effective[0] <= true_alpha <= ci_effective[1])
                        cell_in_ci.append(1.0 if in_cov else 0.0)

                med_err = float(np.median(cell_alpha_errors)) if cell_alpha_errors else 0.0
                coverage = float(np.mean(cell_in_ci)) if cell_in_ci else 0.0

                count_H = verdicts.count("H")
                count_F = verdicts.count("F")
                count_A = verdicts.count("A")
                count_C = verdicts.count("C")

                far_str = ""
                far_ci_str = ""
                det_str = ""
                det_ci_str = ""
                missed_str = ""

                if cond == "healthy":
                    k_fa = episodes_per_cell - count_H
                    false_alarm_rate = round(k_fa / episodes_per_cell, 4)
                    far_str = f"{false_alarm_rate:.4f}"
                    far_ci_str = wilson_score_ci(k_fa, episodes_per_cell)
                    total_healthy_episodes += episodes_per_cell
                    total_false_alarms += k_fa
                elif cond in ("single_stuck", "single_offset_5", "single_spike", "whole_sensor_drift"):
                    k_det = count_F
                    detection_rate = round(k_det / episodes_per_cell, 4)
                    missed_detection_rate = round(count_H / episodes_per_cell, 4)
                    det_str = f"{detection_rate:.4f}"
                    det_ci_str = wilson_score_ci(k_det, episodes_per_cell)
                    missed_str = f"{missed_detection_rate:.4f}"
                elif cond == "constant_alpha_shift":
                    k_det = count_A
                    detection_rate = round(k_det / episodes_per_cell, 4)
                    missed_detection_rate = round(count_H / episodes_per_cell, 4)
                    det_str = f"{detection_rate:.4f}"
                    det_ci_str = wilson_score_ci(k_det, episodes_per_cell)
                    missed_str = f"{missed_detection_rate:.4f}"
                elif cond == "mid_test_jump":
                    k_det = count_C + count_F
                    detection_rate = round(k_det / episodes_per_cell, 4)
                    missed_detection_rate = round(count_H / episodes_per_cell, 4)
                    det_str = f"{detection_rate:.4f}"
                    det_ci_str = wilson_score_ci(k_det, episodes_per_cell)
                    missed_str = f"{missed_detection_rate:.4f}"

                row = {
                    "N": N,
                    "sigma": sigma,
                    "condition": cond,
                    "episodes": episodes_per_cell,
                    "healthy_episodes": episodes_per_cell if cond == "healthy" else "",
                    "reference_readings": ref_length,
                    "median_alpha_error": round(med_err, 5),
                    "interval_coverage": round(coverage, 4),
                    "healthy_false_alarm_rate": far_str,
                    "far_wilson_ci95": far_ci_str,
                    "detection_rate": det_str,
                    "detection_wilson_ci95": det_ci_str,
                    "missed_detection_rate": missed_str,
                    "rate_A": round(count_A / episodes_per_cell, 3),
                    "rate_C": round(count_C / episodes_per_cell, 3),
                    "rate_F": round(count_F / episodes_per_cell, 3),
                    "rate_H": round(count_H / episodes_per_cell, 3)
                }
                results_rows.append(row)
                print(f"[{cell_idx}/{total_cells}] N={N:2d}, sigma={sigma:.2f}, {cond:<20} | MedErr={med_err*100:5.2f}%, Cov={coverage*100:5.1f}%, H={count_H:2d}, F={count_F:2d}, A={count_A:2d}, C={count_C:2d} | FAR={far_str} CI={far_ci_str}")

    # Aggregate healthy FAR analysis
    agg_far = total_false_alarms / max(1, total_healthy_episodes)
    agg_far_ci = wilson_score_ci(total_false_alarms, total_healthy_episodes)
    print("\n" + "=" * 80)
    print(f"[Sweep Analysis] Statistical FAR Evaluation:")
    print(f"  Total healthy episodes evaluated across all cells: {total_healthy_episodes}")
    print(f"  Total false alarms: {total_false_alarms}")
    print(f"  Aggregate False Alarm Rate: {agg_far * 100:.2f}% (Wilson 95% CI: {agg_far_ci})")
    print(f"  Frozen Benchmark Comparison: The frozen anomaly audit achieved 6.5% FAR (Wilson 95% CI: [5.0%, 8.4%]).")
    print(f"  Note on 5% FAR target: In individual cells with n=40 episodes, an observed FAR of 0/40 has a 95% Wilson interval")
    print(f"  of [0.0%, 8.8%], which overlaps 5.0%. Thus, individual cell samples of 40 cannot statistically prove FAR < 5%;")
    print(f"  only multi-cell aggregation (N={total_healthy_episodes}) provides sufficient statistical power.")
    print("=" * 80 + "\n")

    # Write challenge/sweep.csv
    os.makedirs(os.path.dirname(out_file) or ".", exist_ok=True)
    fieldnames = [
        "N", "sigma", "condition", "episodes", "healthy_episodes", "reference_readings",
        "median_alpha_error", "interval_coverage",
        "healthy_false_alarm_rate", "far_wilson_ci95",
        "detection_rate", "detection_wilson_ci95", "missed_detection_rate",
        "rate_A", "rate_C", "rate_F", "rate_H"
    ]
    with open(out_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results_rows:
            writer.writerow(r)

    elapsed_s = round(time.perf_counter() - t_start, 2)
    print(f"[Sweep] Completed {total_episodes} episodes across {total_cells} cells in {elapsed_s}s.")
    print(f"[Sweep] Saved results table to {out_file}\n")


if __name__ == "__main__":
    out_path = sys.argv[1] if len(sys.argv) > 1 else "challenge/sweep.csv"
    run_sweep(out_file=out_path)
