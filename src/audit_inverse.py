"""Audit the inverse-problem result CSVs. Prints a short report (about 40 lines).

Usage (from the project root):  python src/audit_inverse.py [data_dir]
Reads: mode2_pipeline_results_v2.csv, mode3_pipeline_results_v2.csv, mode3plus_hybrid_results.csv
Writes: audit_report.txt next to the CSVs, and prints the same text.
"""
import sys, os
import pandas as pd
import numpy as np

D = sys.argv[1] if len(sys.argv) > 1 else "data"
out = []
def say(s=""):
    out.append(s); print(s)

def load(name):
    return pd.read_csv(os.path.join(D, name), skipinitialspace=True)

def pct(s):
    return pd.to_numeric(s.astype(str).str.rstrip("%"), errors="coerce")

M2 = load("mode2_pipeline_results_v2.csv")
M3 = load("mode3_pipeline_results_v2.csv")
HP = load("mode3plus_hybrid_results.csv")
err_col = {"Mode2": "med_rel_err", "Mode3": "med_wide", "Hybrid": "med_rel_err"}
files = {"Mode2": M2, "Mode3": M3, "Hybrid": HP}
expected_rows = {"Mode2": 180, "Mode3": 135, "Hybrid": 135}
KEY = ["alpha", "sensors", "sigma"]

def expected_status(r, ec):
    if r["sigma"] == 0:
        return "sigma=0"
    e, fb = r[ec], r["frac_bound"]
    w, b = pct(pd.Series([r["wald_cov_95"]]))[0], pct(pd.Series([r["deploy_cov_95"]]))[0]
    if e > 0.20 or fb >= 0.10:
        return "Not Identifiable"
    if w >= 90:
        return "Identifiable"
    return "bias-dominated" if b >= 90 else "bias-uncorrected"

def norm_status(s):
    s = str(s)
    if s.startswith("sigma=0"):
        return "sigma=0"
    return s.replace(" (FNO)", "")

say("=== 1. Shape, duplicates, status rule ===")
for n, d in files.items():
    ec = err_col[n]
    dup = int(d.duplicated(KEY).sum())
    bad = 0
    for _, r in d.iterrows():
        if norm_status(r["status"]) != expected_status(r, ec):
            bad += 1
    say(f"{n}: rows {len(d)} (expected {expected_rows[n]}), duplicate cells {dup}, rule violations {bad}")
    say(f"   status counts: {d.status.value_counts().to_dict()}")

say("\n=== 2. alpha = 4.0 narrow-bound flag (Mode 3) ===")
a4 = M3[M3.alpha == 4.0]
say(f"narrow column flagged N/A in {int(a4.med_narrow.astype(str).str.contains('N/A').sum())} of {len(a4)} rows at alpha=4.0 (want 9 of 9)")

say("\n=== 3. sigma=0 floor (median rel err) by split ===")
for n, d in files.items():
    z = d[d.sigma == 0]
    say(f"{n}: " + ", ".join(f"{k}: {v:.4f}" for k, v in z.groupby("split")[err_col[n]].median().items()))

say("\n=== 4. Coverage (sigma>0) ===")
for n, d in files.items():
    v = pct(d.wald_cov_95)[d.sigma > 0]
    say(f"{n}: Wald mean {v.mean():.1f}%, cells under 90%: {int((v < 90).sum())} of {int(v.notna().sum())}")

say("\n=== 5. Pairing check (same noise draws) ===")
p = M2.merge(HP, on=KEY, suffixes=("_2", "_p"))
p = p[p.sigma > 0]
rel = (p.med_rel_err_2 - p.med_rel_err_p).abs() / p.med_rel_err_2
say(f"Mode 2 vs Hybrid: median |diff|/error {rel.median():.4f}, max {rel.max():.3f} (earlier run: 0.0002 / 0.070)")
q = M3.merge(M2, on=KEY, suffixes=("_3", "_2"))
q = q[(q.sigma == 0.05) & (q.alpha >= 0.02)]
say(f"Mode 3 / Mode 2 error ratio at sigma=0.05, alpha>=0.02: median {(q.med_wide / q.med_rel_err).median():.3f} (earlier run: about 1.02)")

say("\n=== 6. Timing (mean single fit, ms) ===")
for n, d in files.items():
    say(f"{n}: {d.single_fit_time_ms.mean():.2f}")

say("\n=== 7. Spot-check cells vs earlier run (value now / value before) ===")
ref = [
    ("Mode3", M3, "med_wide", (0.1, 5, 0.01), 0.019132),
    ("Mode3", M3, "med_wide", (3.0, 5, 0.01), 0.056753),
    ("Mode3", M3, "med_wide", (4.0, 5, 0.01), 0.059465),
    ("Mode3", M3, "med_wide", (0.002, 5, 0.0), 0.100317),
    ("Mode3", M3, "med_wide", (2.5, 20, 0.05), 0.039649),
    ("Mode3", M3, "med_wide", (0.5, 20, 0.01), 0.010675),
    ("Mode2", M2, "med_rel_err", (0.1, 5, 0.01), 0.017353),
    ("Mode2", M2, "med_rel_err", (3.0, 5, 0.01), 0.015125),
    ("Mode2", M2, "med_rel_err", (4.0, 10, 0.01), 0.015647),
    ("Hybrid", HP, "med_rel_err", (0.1, 5, 0.01), 0.017362),
    ("Hybrid", HP, "med_rel_err", (2.5, 5, 0.01), 0.018704),
]
nchg = 0
for n, d, c, (a, s, sg), old in ref:
    r = d[(d.alpha == a) & (d.sensors == s) & (d.sigma == sg)]
    if len(r) == 0:
        say(f"{n} a={a} N={s} sig={sg}: MISSING"); nchg += 1; continue
    v = float(r[c].iloc[0]); same = abs(v - old) < 5e-6
    nchg += (not same)
    say(f"{n} a={a} N={s} sig={sg}: {v:.6f} / {old:.6f}  {'same' if same else 'CHANGED'}  status={r.status.iloc[0]}")
say(f"cells changed vs earlier run: {nchg} of {len(ref)}")

open(os.path.join(D, "audit_report.txt"), "w", encoding="utf-8").write("\n".join(out))
