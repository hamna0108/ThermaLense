"""Task C2: Rescoring of Stress Matrix v2 into stress_summary_v2b.csv and reports/stress_matrix_v2b.md.

AMENDMENT TO PRE-REGISTERED FAILURE RULE (Formulated after seeing v2 results):
1. Anomaly Scoring by Ground Truth:
   - Healthy ground truth (S1, S2, S3, S8, S11, S13): Rule stays healthy False Alarm Rate (FAR) <= 15.0%.
   - Non-healthy ground truth (S4-S7 wrong physics, S9 jitter, S10 bias, S12 out of range):
     Evaluating FAR on non-healthy data was a conceptual scoring error (flagging anomalous data is a True Positive,
     not a false alarm). Under C2, report Detection Rate (pred != 'H') with Wilson 95% CI.
     Cell PASSES if Detection Rate >= 80.0%, and also reports class assigned (S10 expected Class F;
     S12 expected Class A; S4-S7 no single expected class).
2. S1 (Misspecified Sigma):
   - Compare observed median relative error against matching true sigma clean baseline:
     * Sev 1 (assumed 0.05, true 0.01) -> matching clean sigma 0.01
     * Sev 2 (assumed 0.01, true 0.05) -> matching clean sigma 0.05
     * Sev 3 (assumed 0.01, true 0.03) -> matching clean sigma 0.03
   - Coverage remains the primary S1 failure criterion (< 80.0% fails).
3. S8 (Sensor Dropout) and S11 (Very Few Sensors):
   - Add CRB-predicted error for the reduced sensor set.
   - If observed median error <= 1.5x CRB-predicted error, label cell "degradation as predicted" and PASS.
4. S12 (Diffusivity Range):
   - Rename 'Super-grid high diffusivity alpha = 5.0' to 'high-alpha, information-limited' (alpha=5 is inside the grid [0.001, 10.0]).
   - Add 'estimate_at_bound_pct' column (fraction of estimates within 1% of grid bound [<= 0.00101 or >= 9.90]).
"""

import os
import sys
import numpy as np
import pandas as pd
import scipy.stats as stats

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from src.paths import RESULTS, REPORTS

def wilson_ci(k, n, confidence=0.95):
    if n == 0:
        return 0.0, 0.0
    z = stats.norm.ppf(1 - (1 - confidence) / 2)
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    spread = (z * np.sqrt((p * (1 - p) / n) + (z**2 / (4 * n**2)))) / denom
    lo = max(0.0, (center - spread) * 100.0)
    hi = min(100.0, (center + spread) * 100.0)
    return round(lo, 2), round(hi, 2)

def crb_rel_exact(x_s, t_s, alpha, sigma):
    du_da = - (np.pi**2) * t_s * np.exp(-alpha * (np.pi**2) * t_s) * np.sin(np.pi * x_s)
    fi = np.sum((du_da**2) / (sigma**2))
    if fi <= 0:
        return np.inf
    return np.sqrt(1.0 / fi) / alpha

def rescore_matrix():
    print("=" * 115)
    print("TASK C2: RESCORING STRESS MATRIX V2 INTO V2B")
    print("=" * 115)
    
    matrix_v2_path = os.path.join(RESULTS, 'stress_matrix_v2.csv')
    df_raw = pd.read_csv(matrix_v2_path)
    print(f"Loaded raw replication data: {len(df_raw)} rows.")
    
    # Matching clean reference baselines (computed from clean seeds 1200000..1200099)
    clean_baselines = {
        0.01: {
            'Mode 2': 0.011553,
            'Mode 3': 0.012559,
            'Mode 3+': 0.011557,
            'Two-Stage Placement': 0.007939,
            'cov': 95.0,
            'far': 4.0
        },
        0.03: {
            'Mode 2': 0.034477,
            'Mode 3': 0.034546,
            'Mode 3+': 0.034477,
            'Two-Stage Placement': 0.021613,
            'cov': 98.0
        },
        0.05: {
            'Mode 2': 0.055013,
            'Mode 3': 0.057229,
            'Mode 3+': 0.055017,
            'Two-Stage Placement': 0.045403,
            'cov': 96.0
        }
    }
    
    # Hypotheses dictionary
    hypotheses = {
        1: ("Underestimated noise shrinks Fisher information and inflates chi2 threshold", "Pre-estimate empirical residual variance before setting weights"),
        2: ("Outliers violate Gaussian likelihood and drag MSE fits away from mode", "Replace L2 loss with Huber or Student-t robust M-estimator"),
        3: ("Residual autocorrelation violates i.i.d. assumption, shrinking effective sample size", "Pre-whiten measurement residuals via AR(1) Cochrane-Orcutt transform"),
        4: ("Higher spatial modes decay exponentially faster than fundamental mode", "Decompose initial time slice into spatial Fourier coefficients before fitting alpha"),
        5: ("Boundary thermal offset/flux counteracts interior diffusion decay", "Jointly invert for Dirichlet boundary values alongside alpha"),
        6: ("Internal heating source counteracts conductive decay, masquerading as zero/negative diffusion", "Augment parameter vector to simultaneously estimate volumetric source rate"),
        7: ("Spatial gradient in diffusivity violates homogeneous medium assumption", "Upgrade operator to accept spatial parameter field alpha(x)"),
        8: ("Missing sensor channels reduce spatial information density below Cramér-Rao floor", "Dynamically adjust confidence interval using actual retained Fisher information"),
        9: ("Position and timing jitter introduce systematic phase and spatial distortion", "Include sensor coordinate jitter margin in likelihood variance budget"),
        10: ("Constant sensor bias triggers single-sensor Leave-One-Out BIC gate", "LOO BIC gate correctly flags Class F sensor fault rather than Class C"),
        11: ("Extremely sparse array (N=2, 3) yields near-singular Fisher information matrix", "Impose empirical Bayes prior on alpha or mandate minimum N >= 5 sensor nodes"),
        12: ("Signal vanishes into noise floor (high alpha) or decays too slowly (low alpha)", "Dynamically scale temporal observation window inversely with initial alpha estimate"),
        13: ("Baseline parameter drift creates persistent residual offset in operational window", "Incorporate linear baseline drift parameter into null hypothesis model"),
    }
    
    # Precompute CRBs for S8 and S11
    s8_crbs = {}
    alpha_nom = 0.100
    sig_nom = 0.01
    t_full = np.logspace(np.log10(0.01), 0, 10)
    for sev_idx, k_drop in [(1, 1), (2, 3), (3, 5)]:
        N_rem = 10 - k_drop
        crb_list = []
        for s in range(100):
            seed = 1200000 + 8 * 1000 + sev_idx * 100 + s
            rng = np.random.RandomState(seed)
            x_s = rng.uniform(0.2, 0.8, 10)
            idx = np.sort(rng.choice(10, size=N_rem, replace=False))
            crb_list.append(crb_rel_exact(x_s[idx], t_full[idx], alpha_nom, sig_nom))
        s8_crbs[sev_idx] = float(np.median(crb_list))
        
    s11_crbs = {}
    for sev_idx, N_few in [(1, 5), (2, 3), (3, 2)]:
        crb_list = []
        for s in range(100):
            seed = 1200000 + 11 * 1000 + sev_idx * 100 + s
            rng = np.random.RandomState(seed)
            t_s = np.logspace(np.log10(0.01), 0, N_few)
            x_s = rng.uniform(0.2, 0.8, N_few)
            crb_list.append(crb_rel_exact(x_s, t_s, alpha_nom, sig_nom))
        s11_crbs[sev_idx] = float(np.median(crb_list))
        
    summary_rows = []
    
    # Group raw data by scenario, severity, module
    grouped = df_raw.groupby(['scenario_idx', 'scenario_name', 'severity_idx', 'severity_level', 'category', 'module'])
    
    for (scen_id, scen_name, sev_idx, sev_desc, category, mod_name), g in grouped:
        num_reps = len(g)
        
        # 1. Rename S12 severity 2
        if scen_id == 12 and sev_idx == 2:
            sev_desc = "high-alpha, information-limited"
            
        # 2. Check estimate at bound pct for S12 (and record across all parameter modules)
        if mod_name != 'Anomaly Cascade':
            # grid bounds: low = 0.001, high = 10.0
            # within 1%: <= 0.00101 or >= 9.90
            at_bound_count = sum((g['alpha_hat'] <= 0.00101) | (g['alpha_hat'] >= 9.90))
            at_bound_pct = round(at_bound_count / num_reps * 100.0, 1)
        else:
            at_bound_pct = 'N/A'
            
        # 3. Anomaly Cascade Rescoring
        if mod_name == 'Anomaly Cascade':
            preds = g['anomaly_pred'].tolist()
            pred_counts = pd.Series(preds).value_counts().to_dict()
            pct_H = round(pred_counts.get('H', 0) / num_reps * 100.0, 1)
            pct_A = round(pred_counts.get('A', 0) / num_reps * 100.0, 1)
            pct_F = round(pred_counts.get('F', 0) / num_reps * 100.0, 1)
            pct_C = round(pred_counts.get('C', 0) / num_reps * 100.0, 1)
            class_assigned_str = f"H:{pct_H}%, A:{pct_A}%, F:{pct_F}%, C:{pct_C}%"
            
            # Ground truth classification:
            # Healthy truth: S1, S2, S3, S8, S11, S13
            # Non-healthy truth: S4, S5, S6, S7 (wrong physics), S9 (jitter), S10 (bias), S12 (alpha out of range)
            is_healthy_truth = scen_id in [1, 2, 3, 8, 11, 13]
            
            if is_healthy_truth:
                fa_count = sum([p != 'H' for p in preds])
                far_pct = round(fa_count / num_reps * 100.0, 2)
                far_lo, far_hi = wilson_ci(fa_count, num_reps)
                det_pct, det_lo, det_hi = 'N/A', 'N/A', 'N/A'
                
                failed = (far_pct > 15.0)
                status = 'FAIL' if failed else 'PASS'
                fail_str = f"Healthy FAR {far_pct:.1f}% > 15.0%" if failed else "Within specification"
            else:
                # Non-healthy ground truth: evaluate Detection Rate (pred != 'H')
                # Pre-registered amendment rule: PASS if detection rate (pred != 'H') >= 80.0%
                # Also report class assigned (S10 expected F; S12 expected A; S4-S7 no expected class).
                det_count = sum([p != 'H' for p in preds])
                det_pct = round(det_count / num_reps * 100.0, 2)
                det_lo, det_hi = wilson_ci(det_count, num_reps)
                far_pct, far_lo, far_hi = 'N/A', 'N/A', 'N/A'
                
                pass_det = (det_pct >= 80.0)
                status = 'PASS' if pass_det else 'FAIL'
                
                if not pass_det:
                    fail_str = f"Detection rate {det_pct:.1f}% < 80.0%"
                else:
                    if scen_id == 10:
                        if pct_F >= 80.0:
                            fail_str = f"Detected as expected Class F ({pct_F:.1f}%)"
                        else:
                            fail_str = f"Detected ({det_pct:.1f}%); Class F recall {pct_F:.1f}% < 80% (expected F)"
                    elif scen_id == 12:
                        if pct_A >= 80.0:
                            fail_str = f"Detected as expected Class A ({pct_A:.1f}%)"
                        else:
                            fail_str = f"Detected ({det_pct:.1f}%); Class A recall {pct_A:.1f}% < 80% (expected A; assigned F:{pct_F:.1f}%)"
                    else:
                        fail_str = f"Detected as physical anomaly (A:{pct_A}%, F:{pct_F}%, C:{pct_C}%)"
                failed = (status == 'FAIL')
                
            cause_hyp, fix_hyp = hypotheses.get(scen_id, ("Perturbation degrades detector", "Calibrate thresholds"))
            
            summary_rows.append({
                'scenario_idx': scen_id, 'scenario_name': scen_name, 'severity_idx': sev_idx,
                'severity_level': sev_desc, 'category': category, 'module': mod_name,
                'med_rel_err': 'N/A', 'clean_rel_err': 'N/A', 'err_ratio': 'N/A',
                'coverage_pct': 'N/A', 'coverage_ci_low': 'N/A', 'coverage_ci_high': 'N/A',
                'crb_predicted_err': 'N/A', 'estimate_at_bound_pct': at_bound_pct,
                'is_healthy_truth': is_healthy_truth,
                'healthy_far_pct': far_pct, 'healthy_far_ci_low': far_lo, 'healthy_far_ci_high': far_hi,
                'detection_rate_pct': det_pct, 'detection_ci_low': det_lo, 'detection_ci_high': det_hi,
                'class_assigned': class_assigned_str,
                'status': status, 'fail_reasons': fail_str,
                'likely_cause_hypothesis': cause_hyp if failed else 'N/A',
                'v2_candidate_fix_hypothesis': fix_hyp if failed else 'N/A'
            })
            
        else: # Parameter Estimation Modules
            med_err = float(g['rel_error'].median())
            cov_count = sum(g['in_ci_95'])
            cov_pct = round(cov_count / num_reps * 100.0, 2)
            cov_lo, cov_hi = wilson_ci(cov_count, num_reps)
            
            # Matching clean baseline
            if scen_id == 1:
                # S1: compare against matching true sigma clean baseline
                true_sig = 0.01 if sev_idx == 1 else (0.05 if sev_idx == 2 else 0.03)
                clean_err = clean_baselines[true_sig][mod_name]
            else:
                clean_err = clean_baselines[0.01][mod_name]
                
            err_ratio = round(med_err / max(1e-5, clean_err), 3)
            
            # S8 and S11 CRB check
            crb_pred = 'N/A'
            degradation_as_predicted = False
            if scen_id == 8:
                crb_pred = round(s8_crbs[sev_idx], 5)
                if med_err <= 1.5 * crb_pred:
                    degradation_as_predicted = True
            elif scen_id == 11:
                crb_pred = round(s11_crbs[sev_idx], 5)
                if med_err <= 1.5 * crb_pred:
                    degradation_as_predicted = True
                    
            # Failure rule evaluation:
            if scen_id in [8, 11] and degradation_as_predicted:
                status = 'PASS'
                fail_str = f"degradation as predicted (err {med_err:.4f} <= 1.5x CRB {crb_pred:.4f})"
                failed = False
            elif scen_id == 1:
                # S1: Coverage stays the main S1 failure criterion; error compared to matching true sigma
                failed = (err_ratio > 2.0) or (cov_pct < 80.0)
                status = 'FAIL' if failed else 'PASS'
                reasons = []
                if err_ratio > 2.0: reasons.append(f"Error {err_ratio:.2f}x > 2.0x matching clean ({clean_err:.4f})")
                if cov_pct < 80.0: reasons.append(f"Coverage {cov_pct:.1f}% < 80.0%")
                fail_str = "; ".join(reasons) if failed else "Within specification"
            else:
                failed = (err_ratio > 2.0) or (cov_pct < 80.0)
                status = 'FAIL' if failed else 'PASS'
                reasons = []
                if err_ratio > 2.0: reasons.append(f"Error {err_ratio:.2f}x > 2.0x clean")
                if cov_pct < 80.0: reasons.append(f"Coverage {cov_pct:.1f}% < 80.0%")
                fail_str = "; ".join(reasons) if failed else "Within specification"
                
            cause_hyp, fix_hyp = hypotheses.get(scen_id, ("Model mismatch degrades estimator", "Calibrate model on perturbed regime"))
            
            summary_rows.append({
                'scenario_idx': scen_id, 'scenario_name': scen_name, 'severity_idx': sev_idx,
                'severity_level': sev_desc, 'category': category, 'module': mod_name,
                'med_rel_err': round(med_err, 6), 'clean_rel_err': round(clean_err, 6),
                'err_ratio': err_ratio, 'coverage_pct': cov_pct,
                'coverage_ci_low': cov_lo, 'coverage_ci_high': cov_hi,
                'crb_predicted_err': crb_pred, 'estimate_at_bound_pct': at_bound_pct,
                'is_healthy_truth': True,
                'healthy_far_pct': 'N/A', 'healthy_far_ci_low': 'N/A', 'healthy_far_ci_high': 'N/A',
                'detection_rate_pct': 'N/A', 'detection_ci_low': 'N/A', 'detection_ci_high': 'N/A',
                'class_assigned': 'N/A',
                'status': status, 'fail_reasons': fail_str,
                'likely_cause_hypothesis': cause_hyp if failed else 'N/A',
                'v2_candidate_fix_hypothesis': fix_hyp if failed else 'N/A'
            })
            
    df_sum_v2b = pd.DataFrame(summary_rows)
    out_csv = os.path.join(RESULTS, 'stress_summary_v2b.csv')
    df_sum_v2b.to_csv(out_csv, index=False)
    print(f"Saved rescored summary CSV ({len(df_sum_v2b)} rows) to: {out_csv}")
    
    # Generate reports/stress_matrix_v2b.md
    generate_markdown_report_v2b(out_csv, clean_baselines)

def generate_markdown_report_v2b(summary_csv_path, clean_baselines):
    print("\nGenerating reports/stress_matrix_v2b.md strictly from CSV...")
    df = pd.read_csv(summary_csv_path)
    
    total_cells = len(df)
    pass_cells = len(df[df['status'] == 'PASS'])
    fail_cells = len(df[df['status'] == 'FAIL'])
    overall_pass_rate = pass_cells / total_cells * 100.0
    
    modules = ['Mode 2', 'Mode 3', 'Mode 3+', 'Two-Stage Placement', 'Anomaly Cascade']
    exec_rows = []
    for m in modules:
        m_df = df[df['module'] == m]
        
        r_df = m_df[m_df['category'] == 'robustness']
        r_pass = len(r_df[r_df['status'] == 'PASS'])
        r_tot = len(r_df)
        r_str = f"{r_pass} / {r_tot} ({r_pass/r_tot*100.0:.1f}%)" if r_tot > 0 else "N/A"
        
        s_df = m_df[m_df['category'] == 'declared-scope violation']
        s_pass = len(s_df[s_df['status'] == 'PASS'])
        s_tot = len(s_df)
        s_str = f"{s_pass} / {s_tot} ({s_pass/s_tot*100.0:.1f}%)" if s_tot > 0 else "N/A"
        
        t_pass = len(m_df[m_df['status'] == 'PASS'])
        t_tot = len(m_df)
        t_str = f"{t_pass} / {t_tot} ({t_pass/t_tot*100.0:.1f}%)"
        
        exec_rows.append({
            'module': m,
            'robustness': r_str,
            'scope_violation': s_str,
            'total': t_str
        })
        
    md = []
    md.append("# Week 5 Stress Matrix v2b Report (Corrected Scoring)")
    md.append("")
    md.append("> **Generated strictly from:** `data/results/stress_summary_v2b.csv`")
    md.append("> **Amendment Note:** This report applies the Task C2 scoring corrections formulated after reviewing v2 results. All frozen modules remain completely untouched.")
    md.append("")
    md.append("## Rule Amendments Applied in v2b")
    md.append("1. **Anomaly Ground Truth Distinction:** In v1/v2, False Alarm Rate (`pred != 'H'`) was erroneously evaluated against non-healthy scenarios (S4-S7, S9, S10, S12), incorrectly penalizing true positive detections as 'false alarms'. In v2b:")
    md.append("   - **Healthy Truth (S1, S2, S3, S8, S11, S13):** Evaluated by FAR; cell FAILS if FAR $> 15.0\\%$.")
    md.append("   - **Non-Healthy Truth (S4-S7 wrong physics, S9 jitter, S10 bias, S12 out-of-range):** Evaluated by Detection Rate (`pred != 'H'`); cell PASSES if Detection Rate $\\ge 80.0\\%$, and checks expected class assignment (S10 expected Class F; S12 expected Class A; S4-S7 physical anomaly).")
    md.append("2. **S1 Matching Clean Baseline:** Error ratio compares against the clean reference at matching true $\\sigma$ ($\\sigma=0.01, 0.03, 0.05$). Coverage ($< 80.0\\%$) remains the primary failure criterion.")
    md.append("3. **S8 and S11 Reduced Sensor Degradation:** Observed errors are benchmarked against the Cramér-Rao Bound for reduced sensor arrays. Cells where observed median error $\\le 1.5\\times$ CRB-predicted error are labeled **'degradation as predicted'** and PASS.")
    md.append("4. **S12 Clarification & Boundary Analysis:** Renamed $\\alpha=5.0$ to 'high-alpha, information-limited' (inside grid $[0.001, 10.0]$). Added `estimate_at_bound_pct` tracking boundary pinning.")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 1. Executive Summary Table per Module and Category")
    md.append("")
    md.append("| Module | Robustness Pass Rate (Scenarios 1–3, 8–13) | Declared-Scope Violation Pass Rate (Scenarios 4–7) | Total Pass Rate (All 39 Cells) |")
    md.append("| :--- | :---: | :---: | :---: |")
    for r in exec_rows:
        md.append(f"| **{r['module']}** | {r['robustness']} | {r['scope_violation']} | **{r['total']}** |")
    md.append("")
    md.append(f"**Overall Portfolio Performance:** **{pass_cells} / {total_cells} Cells Passed** (`{overall_pass_rate:.1f}%` Pass Rate; `{fail_cells} / {total_cells}` Failed, `{100.0 - overall_pass_rate:.1f}%` Failure Rate).")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 2. Anomaly Ground Truth Rescoring Breakdown")
    md.append("")
    md.append("| Scen | Ground Truth State | Severity Level | Healthy FAR % [95% CI] | Detection Rate % [95% CI] | Class Assigned Distribution | Status | Rule Assessment |")
    md.append("| :---: | :--- | :--- | :---: | :---: | :--- | :---: | :--- |")
    anom_df = df[df['module'] == 'Anomaly Cascade']
    for _, r in anom_df.iterrows():
        gt_state = "Healthy" if r['is_healthy_truth'] else "Non-Healthy"
        far_str = f"`{r['healthy_far_pct']}%` [{r['healthy_far_ci_low']}, {r['healthy_far_ci_high']}]" if r['healthy_far_pct'] != 'N/A' else "N/A"
        det_str = f"`{r['detection_rate_pct']}%` [{r['detection_ci_low']}, {r['detection_ci_high']}]" if r['detection_rate_pct'] != 'N/A' else "N/A"
        status_b = f"**{r['status']}**" if r['status'] == 'PASS' else f"<span style='color:red;'>**{r['status']}**</span>"
        md.append(f"| S{r['scenario_idx']} | {gt_state} | {r['severity_level']} | {far_str} | {det_str} | `{r['class_assigned']}` | {status_b} | {r['fail_reasons']} |")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 3. S8 & S11 Degradation vs Cramér-Rao Bound")
    md.append("")
    md.append("| Scen | Module | Severity Level | Observed Med Rel Err | CRB Predicted Rel Err | Ratio (Obs/CRB) | Status | Assessment |")
    md.append("| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :--- |")
    s8_11_df = df[(df['scenario_idx'].isin([8, 11])) & (df['module'] != 'Anomaly Cascade')]
    for _, r in s8_11_df.iterrows():
        obs = float(r['med_rel_err'])
        crb = float(r['crb_predicted_err'])
        ratio_crb = obs / crb
        status_b = f"**{r['status']}**" if r['status'] == 'PASS' else f"<span style='color:red;'>**{r['status']}**</span>"
        md.append(f"| S{r['scenario_idx']} | {r['module']} | {r['severity_level']} | `{obs:.4f}` | `{crb:.4f}` | `{ratio_crb:.2f}x` | {status_b} | {r['fail_reasons']} |")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 4. S12 Boundary Pinning Analysis")
    md.append("")
    md.append("| Scen | Module | Severity Level | Abs Med Rel Err | Ratio vs Clean | Coverage % [95% CI] | At Bound % (<=0.001 or >=9.9) | Status |")
    md.append("| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: |")
    s12_df = df[df['scenario_idx'] == 12]
    for _, r in s12_df.iterrows():
        if r['module'] != 'Anomaly Cascade':
            cov_str = f"`{r['coverage_pct']}%` [{r['coverage_ci_low']}, {r['coverage_ci_high']}]"
            bnd_str = f"`{r['estimate_at_bound_pct']}%`"
            status_b = f"**{r['status']}**" if r['status'] == 'PASS' else f"<span style='color:red;'>**{r['status']}**</span>"
            md.append(f"| S12 | {r['module']} | {r['severity_level']} | `{r['med_rel_err']:.4f}` | `{r['err_ratio']:.2f}x` | {cov_str} | {bnd_str} | {status_b} |")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 5. All FAILED Cells in v2b with Absolute Errors and 95% CIs")
    md.append("")
    md.append("| Scen | Category | Module | Severity Level | Abs Med Rel Err | Clean Err | Ratio | Coverage % [95% CI] | Healthy FAR % / Det % [95% CI] | Failure Reason |")
    md.append("| :---: | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |")
    fail_df = df[df['status'] == 'FAIL']
    for _, r in fail_df.iterrows():
        err_str = f"`{r['med_rel_err']:.4f}`" if r['med_rel_err'] != 'N/A' else "N/A"
        clean_str = f"`{r['clean_rel_err']:.4f}`" if r['clean_rel_err'] != 'N/A' else "N/A"
        ratio_str = f"`{r['err_ratio']:.2f}x`" if r['err_ratio'] != 'N/A' else "N/A"
        cov_str = f"`{r['coverage_pct']:.1f}%` [{r['coverage_ci_low']}, {r['coverage_ci_high']}]" if r['coverage_pct'] != 'N/A' else "N/A"
        if r['healthy_far_pct'] != 'N/A':
            metric_str = f"FAR `{r['healthy_far_pct']:.1f}%` [{r['healthy_far_ci_low']}, {r['healthy_far_ci_high']}]"
        elif r['detection_rate_pct'] != 'N/A':
            metric_str = f"Det `{r['detection_rate_pct']:.1f}%` [{r['detection_ci_low']}, {r['detection_ci_high']}]"
        else:
            metric_str = "N/A"
        md.append(f"| S{r['scenario_idx']} | {r['category']} | **{r['module']}** | {r['severity_level']} | {err_str} | {clean_str} | {ratio_str} | {cov_str} | {metric_str} | {r['fail_reasons']} |")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 6. Complete Table of All 195 Cells in v2b")
    md.append("")
    md.append("| Scen | Category | Module | Severity Level | Abs Med Rel Err | Clean Err | Ratio | Coverage % [95% CI] | FAR / Det % [95% CI] | Status |")
    md.append("| :---: | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |")
    for _, r in df.iterrows():
        err_str = f"`{r['med_rel_err']:.4f}`" if r['med_rel_err'] != 'N/A' else "N/A"
        clean_str = f"`{r['clean_rel_err']:.4f}`" if r['clean_rel_err'] != 'N/A' else "N/A"
        ratio_str = f"`{r['err_ratio']:.2f}x`" if r['err_ratio'] != 'N/A' else "N/A"
        cov_str = f"`{r['coverage_pct']:.1f}%` [{r['coverage_ci_low']}, {r['coverage_ci_high']}]" if r['coverage_pct'] != 'N/A' else "N/A"
        if r['healthy_far_pct'] != 'N/A':
            metric_str = f"FAR `{r['healthy_far_pct']:.1f}%` [{r['healthy_far_ci_low']}, {r['healthy_far_ci_high']}]"
        elif r['detection_rate_pct'] != 'N/A':
            metric_str = f"Det `{r['detection_rate_pct']:.1f}%` [{r['detection_ci_low']}, {r['detection_ci_high']}]"
        else:
            metric_str = "N/A"
        status_b = f"**{r['status']}**" if r['status'] == 'PASS' else f"<span style='color:red;'>**{r['status']}**</span>"
        md.append(f"| S{r['scenario_idx']} | {r['category']} | {r['module']} | {r['severity_level']} | {err_str} | {clean_str} | {ratio_str} | {cov_str} | {metric_str} | {status_b} |")
    md.append("")
    
    out_md = os.path.join(REPO_ROOT, 'reports', 'stress_matrix_v2b.md')
    with open(out_md, 'w', encoding='utf-8') as f:
        f.write("\n".join(md))
    print(f"Generated comprehensive report v2b at: {out_md}")

if __name__ == '__main__':
    rescore_matrix()
