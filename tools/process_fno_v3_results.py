import json
import csv
import hashlib
import os
import numpy as np

def compute_sha256(filepath):
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

def main():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    
    # 1. Dataset checksums
    datasets_dir = os.path.join(base_dir, "data", "datasets")
    dataset_files = [
        "poisson_v2_train.npz",
        "poisson_v2_val.npz",
        "poisson_v2_test_interp.npz",
        "poisson_v2_test_ood_narrow.npz",
        "poisson_v2_test_ood_count.npz",
        "poisson_v2_test_ood_boundary.npz",
        "poisson_v2_test_ood_highmodes.npz",
        "poisson_v2_manufactured_sanity.npz"
    ]
    checksums = {}
    for fn in dataset_files:
        fp = os.path.join(datasets_dir, fn)
        if os.path.exists(fp):
            checksums[fn] = {
                "sha256": compute_sha256(fp),
                "bytes": os.path.getsize(fp)
            }
    
    checksums_path = os.path.join(base_dir, "data", "results", "poisson_fno_v3", "dataset_checksums.json")
    with open(checksums_path, "w") as f:
        json.dump(checksums, f, indent=2)
    print(f"Saved dataset checksums to {checksums_path}")

    # 2. Read acceptance report
    report_path = os.path.join(base_dir, "data", "results", "poisson_fno_v3", "fno_v3_acceptance_report.json")
    with open(report_path, "r") as f:
        report = json.load(f)

    # 3. Read v2 benchmark table
    v2_table_path = os.path.join(base_dir, "data", "results", "poisson_v2_benchmark_table.csv")
    v2_medians = {}
    with open(v2_table_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            v2_medians[row["split"]] = float(row["fno_l2_med"])

    # 4. Extract per-seed, per-split numbers
    # Columns: seed, split, median, p90, max, pde_residual
    per_seed_rows = []
    splits = ["train", "val", "test_interp", "test_ood_narrow", "test_ood_count", "test_ood_boundary", "test_ood_highmodes"]
    
    # Collect by split for summary statistics
    split_medians = {s: [] for s in splits}

    for seed_entry in report["per_seed_results"]:
        seed = seed_entry["seed"]
        metrics = seed_entry["metrics"]
        for s in splits:
            if s in metrics:
                med = metrics[s]["rel_l2_median"]
                p90 = metrics[s]["rel_l2_p90"]
                mx = metrics[s]["rel_l2_max"]
                res = metrics[s]["res_median"]
                per_seed_rows.append({
                    "seed": seed,
                    "split": s,
                    "rel_l2_median": med,
                    "rel_l2_p90": p90,
                    "rel_l2_max": mx,
                    "pde_residual_median": res
                })
                split_medians[s].append(med)

    out_csv = os.path.join(base_dir, "data", "results", "poisson_fno_v3_per_seed.csv")
    with open(out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["seed", "split", "rel_l2_median", "rel_l2_p90", "rel_l2_max", "pde_residual_median"])
        writer.writeheader()
        writer.writerows(per_seed_rows)
    print(f"Saved per-seed metrics to {out_csv}")

    # 5. Compute improvement factor & seed spread per split
    print("\n--- Split Analysis (v2 vs v3) ---")
    print(f"{'Split':<20} | {'v2 Med':<10} | {'v3 Mean Med':<12} | {'Improvement':<12} | {'Seed Min':<10} | {'Seed Max':<10} | {'Seed Spread (Max/Min)':<22}")
    print("-" * 105)
    
    analysis_results = {}
    for s in splits:
        v2_val = v2_medians.get(s, None)
        vals = split_medians[s]
        mean_med = float(np.mean(vals))
        min_med = float(np.min(vals))
        max_med = float(np.max(vals))
        spread = max_med / min_med if min_med > 0 else np.nan
        improvement = v2_val / mean_med if v2_val and mean_med > 0 else np.nan

        analysis_results[s] = {
            "v2_median": v2_val,
            "v3_mean_median": mean_med,
            "improvement_factor": improvement,
            "v3_seed_min": min_med,
            "v3_seed_max": max_med,
            "v3_seed_spread_ratio": spread
        }
        print(f"{s:<20} | {v2_val:<10.6f} | {mean_med:<12.6f} | {improvement:<11.3f}x | {min_med:<10.6f} | {max_med:<10.6f} | {spread:<22.3f}x")

    analysis_json = os.path.join(base_dir, "data", "results", "poisson_fno_v3", "split_analysis.json")
    with open(analysis_json, "w") as f:
        json.dump(analysis_results, f, indent=2)
    print(f"\nSaved split analysis to {analysis_json}")

if __name__ == "__main__":
    main()
