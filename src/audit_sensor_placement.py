"""Audit script for Task A: Sensor Time Placement Study.
Prints a short audit report (about 40 lines) and writes data/audit_sensor_placement.txt.
"""

import sys
import os
import pandas as pd
import numpy as np

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

D = sys.argv[1] if len(sys.argv) > 1 else "data"
out = []

def say(s=""):
    out.append(s)
    print(s)

raw_path = os.path.join(D, "raw", "sensor_placement_raw.csv")
summary_path = os.path.join(D, "sensor_placement_summary.csv")

say("=== 1. File existence and row counts ===")
if not os.path.exists(raw_path) or not os.path.exists(summary_path):
    say(f"ERROR: Files missing in {D}")
    sys.exit(1)

df_raw = pd.read_csv(raw_path)
df_sum = pd.read_csv(summary_path)

say(f"Raw data: {len(df_raw)} rows (expected 16,800 across 7 strategies), duplicate reps: {int(df_raw.duplicated(['strategy', 'alpha_true', 'sensors', 'sigma', 'rep']).sum())}")
say(f"Summary data: {len(df_sum)} cells (expected 84), duplicate cells: {int(df_sum.duplicated(['strategy', 'alpha_true', 'sensors', 'sigma']).sum())}")

say("\n=== 2. Seed integrity & pairing check ===")
say(f"Null values in raw: {df_raw[['alpha_hat', 'layout_seed', 'noise_seed']].isna().sum().to_dict()}")
say(f"Unique layout seeds: {df_raw['layout_seed'].nunique()} across 6 (alpha, N) configurations")
say(f"Unique noise seeds: {df_raw['noise_seed'].nunique()} (200 distinct seeds per cell)")
# Check exact noise pairing across strategies
piv = df_raw.pivot_table(index=['alpha_true', 'sensors', 'sigma', 'rep'], columns='strategy', values='noise_seed')
all_paired = bool((piv.nunique(axis=1) == 1).all())
say(f"Noise realizations identically paired across all 7 strategies: {all_paired}")

say("\n=== 3. Strategy performance comparison (median rel err across all 12 cells) ===")
strat_summary = df_sum.groupby('strategy')[['med_rel_err', 'crb_rel', 'sprd_crb', 'single_fit_time_ms']].median()
for strat, r in strat_summary.iterrows():
    say(f"  {strat:35s}: med_rel_err = {r['med_rel_err']:.4f} | med_CRB_rel = {r['crb_rel']:.4f} | sprd/CRB = {r['sprd_crb']:.2f} | time = {r['single_fit_time_ms']:.3f} ms")

say("\n=== 4. Deployable Two-Stage Design vs Baseline and Oracle Bounds (N=10, sigma=0.01) ===")
sub = df_sum[(df_sum.sensors == 10) & (df_sum.sigma == 0.01)]
for a, grp in sub.groupby('alpha_true'):
    log_err = grp[grp.strategy == 'log-spaced']['med_rel_err'].values[0]
    two_err = grp[grp.strategy == 'two-stage deployable']['med_rel_err'].values[0]
    inf_err = grp[grp.strategy == 'information-weighted (oracle alpha)']['med_rel_err'].values[0]
    tst_err = grp[grp.strategy == 'all-at-t-star (oracle alpha)']['med_rel_err'].values[0]
    gain = (log_err - two_err) / log_err * 100.0
    say(f"  alpha={a:5.3f} | log-spaced: {log_err:.4f} -> two-stage: {two_err:.4f} ({gain:+5.1f}%) | oracle info-wt: {inf_err:.4f} | all-at-t*: {tst_err:.4f}")

say("\n=== 5. Estimator spread vs Cramér-Rao Bound ===")
v = df_sum['sprd_crb']
say(f"Spread/CRB across all 84 cells: mean = {v.mean():.2f}, min = {v.min():.2f}, max = {v.max():.2f} (theoretical target = 1.00)")

say("\n=== 6. Runtime benchmark (Mode 2 fit time) ===")
say(f"Static placement single fit time: {df_sum[df_sum.strategy != 'two-stage deployable']['single_fit_time_ms'].mean():.3f} ms")
say(f"Two-stage adaptive single fit time: {df_sum[df_sum.strategy == 'two-stage deployable']['single_fit_time_ms'].mean():.3f} ms (includes 2 fits + adaptive design)")
say("Note: Single fit times (~0.3 ms) are for 1D temporal measurements at a single spatial sensor position (x = 0.5),")
say("allowing fast 1D spline evaluation rather than 2D PDE solves.")

say("\n=== 7. Spot-check key cells (including uniform at alpha=2.5) ===")
spot_checks = [
    ('all-at-t-star (oracle alpha)',        0.005, 10, 0.01),
    ('information-weighted (oracle alpha)', 0.005, 10, 0.01),
    ('two-stage deployable',                0.005, 10, 0.01),
    ('late-heavy',                          0.005, 10, 0.01),
    ('log-spaced',                           0.005, 10, 0.01),
    ('uniform',                             0.005, 10, 0.01),
    ('all-at-t-star (oracle alpha)',        2.500, 10, 0.01),
    ('information-weighted (oracle alpha)', 2.500, 10, 0.01),
    ('two-stage deployable',                2.500, 10, 0.01),
    ('early-heavy',                         2.500, 10, 0.01),
    ('log-spaced',                           2.500, 10, 0.01),
    ('uniform',                             2.500, 10, 0.01),
    ('late-heavy',                          2.500, 10, 0.01),
]
for st, a, n, sg in spot_checks:
    row = df_sum[(df_sum.strategy == st) & (df_sum.alpha_true == a) & (df_sum.sensors == n) & (df_sum.sigma == sg)].iloc[0]
    say(f"  {st:35s} a={a:5.3f} N={n:2d} sig={sg:.2f} -> med_err={row.med_rel_err:.4f}, CRB_rel={row.crb_rel:.4f}, sprd/CRB={row.sprd_crb:.2f}")

report_txt_path = os.path.join(D, "audit_sensor_placement.txt")
with open(report_txt_path, "w", encoding="utf-8") as f:
    f.write("\n".join(out))
say(f"\nAudit report saved to: {report_txt_path}")
