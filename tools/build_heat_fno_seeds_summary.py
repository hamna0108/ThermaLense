import json
import glob
import os
import pandas as pd

def build_heat_fno_seeds_summary():
    json_dir = "data/results/heat_fno_seeds"
    frozen_file = os.path.join(json_dir, "metrics_heat_frozen.json")
    seed_files = sorted(glob.glob(os.path.join(json_dir, "metrics_heat_seed*.json")))
    
    rows = []
    
    # 1. Frozen row
    with open(frozen_file, "r") as f:
        d_frz = json.load(f)
    rows.append({
        "seed": "frozen",
        "best_epoch": "N/A",
        "rel_l2_interp": round(d_frz["test_interpolation"]["rel_l2_median"], 6),
        "rel_l2_low_ood": round(d_frz["test_ood_low_alpha"]["rel_l2_median"], 6),
        "rel_l2_high_ood": round(d_frz["test_ood_high_alpha"]["rel_l2_median"], 6),
        "t0_mae": round(d_frz["test_interpolation"]["t0_mae_median"], 6),
        "t1_mae": round(d_frz["test_interpolation"]["t1_mae_median"], 6),
        "sensor_mae": round(d_frz["test_interpolation"]["sensor_mae_median"], 6),
        "bias_floor_0_005": round(d_frz["mode3_sigma0_bias_floor"]["0.005"]["rel_error"], 6),
        "bias_floor_0_1": round(d_frz["mode3_sigma0_bias_floor"]["0.1"]["rel_error"], 6),
        "bias_floor_2_5": round(d_frz["mode3_sigma0_bias_floor"]["2.5"]["rel_error"], 6),
    })
    
    # 2. Seed rows
    for sf in seed_files:
        with open(sf, "r") as f:
            d = json.load(f)
        rows.append({
            "seed": str(d.get("seed", os.path.basename(sf))),
            "best_epoch": str(d.get("best_epoch", "N/A")),
            "rel_l2_interp": round(d["test_interpolation"]["rel_l2_median"], 6),
            "rel_l2_low_ood": round(d["test_ood_low_alpha"]["rel_l2_median"], 6),
            "rel_l2_high_ood": round(d["test_ood_high_alpha"]["rel_l2_median"], 6),
            "t0_mae": round(d["test_interpolation"]["t0_mae_median"], 6),
            "t1_mae": round(d["test_interpolation"]["t1_mae_median"], 6),
            "sensor_mae": round(d["test_interpolation"]["sensor_mae_median"], 6),
            "bias_floor_0_005": round(d["mode3_sigma0_bias_floor"]["0.005"]["rel_error"], 6),
            "bias_floor_0_1": round(d["mode3_sigma0_bias_floor"]["0.1"]["rel_error"], 6),
            "bias_floor_2_5": round(d["mode3_sigma0_bias_floor"]["2.5"]["rel_error"], 6),
        })
        
    df = pd.DataFrame(rows)
    out_csv = "data/results/heat_fno_seeds_summary.csv"
    df.to_csv(out_csv, index=False)
    print(f"Saved summary CSV to {out_csv}")
    print(df.to_string(index=False))

if __name__ == "__main__":
    build_heat_fno_seeds_summary()
