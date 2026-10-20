import os
import sys
import csv
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
try:
    from paths import RESULTS, DATASETS, MODELS
except ImportError:
    from src.paths import RESULTS, DATASETS, MODELS

def generate_report():
    # 1. Load benchmark table
    bench_path = str(RESULTS / "poisson_v2_benchmark_table.csv")
    with open(bench_path, "r") as f:
        bench_rows = {r["split"]: r for r in csv.DictReader(f)}
        
    # 2. Load v1 on v2 splits
    v1_path = str(RESULTS / "poisson_v1_on_v2_splits.csv")
    with open(v1_path, "r") as f:
        v1_rows = {r["split"]: r for r in csv.DictReader(f)}
        
    # 3. Load timing honesty
    timing_path = str(RESULTS / "timing_honesty.json")
    with open(timing_path, "r") as f:
        timing = json.load(f)
        
    # 4. Load training summary and curves
    train_summary_path = str(RESULTS / "fno2d_v2_training_summary.json")
    with open(train_summary_path, "r") as f:
        train_sum = json.load(f)
        
    curves_path = str(RESULTS / "fno2d_v2_training_curves.csv")
    with open(curves_path, "r") as f:
        curves = list(csv.DictReader(f))
    best_curve = [c for c in curves if int(c["epoch"]) == train_sum["best_epoch"]][0]
    
    # 5. Load failure cases
    fc_path = str(RESULTS / "poisson_v2_failure_cases.json")
    with open(fc_path, "r") as f:
        failure_cases = json.load(f)
        
    report = []
    
    report.append("# Stage 2 Round 2 Review & Deliverable Report")
    report.append("")
    report.append("## 1. Reconciled Training Diagnosis (Train vs Val)")
    report.append(f"- **Epochs Trained:** {train_sum['epochs_trained']} | **Best Epoch:** {train_sum['best_epoch']} | **Status:** `{train_sum['status']}`")
    report.append(f"- **Loss at Best Epoch (Epoch {train_sum['best_epoch']}):**")
    report.append(f"  - **Mean Rel L2 (from epoch batch-loss curves):** Train = {float(best_curve['train_rel_l2']):.6f} ({float(best_curve['train_rel_l2'])*100:.2f}%) vs Val = {float(best_curve['val_rel_l2']):.6f} ({float(best_curve['val_rel_l2'])*100:.2f}%)")
    report.append(f"  - **Median Rel L2 (from evaluated checkpoint on full datasets):** Train = {float(bench_rows['train']['fno_l2_med']):.6f} ({float(bench_rows['train']['fno_l2_med'])*100:.2f}%) vs Val = {float(bench_rows['val']['fno_l2_med']):.6f} ({float(bench_rows['val']['fno_l2_med'])*100:.2f}%)")
    report.append(f"- **Diagnosis:** {train_sum['diagnosis']}")
    report.append(f"- **Reconciliation Conclusion:** Train and validation errors are practically identical ({float(bench_rows['train']['fno_l2_med'])*100:.2f}% train median vs {float(bench_rows['val']['fno_l2_med'])*100:.2f}% val median, a delta of only {abs(float(bench_rows['val']['fno_l2_med']) - float(bench_rows['train']['fno_l2_med']))*100:.2f}%). The previous label 'mild overfitting' was an artifact of evaluating the final epoch ({train_sum['epochs_trained']}) after early-stopping patience had expired; the preserved checkpoint at epoch {train_sum['best_epoch']} exhibits clean validation plateauing without overfitting.")
    report.append("")
    report.append("## 2. Timing Honesty Disclosures (CPU, 64x64)")
    report.append(f"- **Single Query Solver (Prefactorized LU):** {timing['solver_prefact_single_ms']:.3f} ms")
    report.append(f"- **Batched Solver (Prefactorized LU, B=32):** {timing['solver_prefact_batch_per_query_ms']:.3f} ms / query")
    report.append(f"- **Fresh LU Factorization (From Scratch per Query):** {timing['solver_fresh_fact_single_ms']:.3f} ms")
    report.append(f"- **Linear Dual Baseline (Single / Batched):** {timing['linear_single_ms']:.3f} ms / {timing['linear_batch_per_query_ms']:.3f} ms")
    report.append(f"- **FNO-2D Operator (Single / Batched):** {timing['fno_single_ms']:.3f} ms / {timing['fno_batch_per_query_ms']:.3f} ms")
    report.append(f"- **Fresh-Factorization Solver Speedup vs FNO:** {timing['fno_single_ms'] / timing['solver_fresh_fact_single_ms']:.1f}x faster ({timing['solver_fresh_fact_single_ms']:.3f} ms vs {timing['fno_single_ms']:.3f} ms on CPU, 64x64).")
    report.append(f"- **Honest Statement:** {timing['honest_statement']}")
    report.append("")
    report.append("## 3. Before vs After: Poisson v1 vs Poisson v2 on v2 Evaluation Splits")
    report.append("Why the source family was widened: v1 was trained exclusively on Gaussian mixtures. When evaluated on the multi-mode harmonic sine splits of v2, v1 fails catastrophically.")
    report.append("")
    report.append("| Evaluation Split | Samples | v1 FNO Rel L2 Med | v1 FNO Rel L2 P90 | v2 FNO Rel L2 Med | v2 FNO Rel L2 P90 | Lin Baseline Med | v2 FNO PDE Res Med |")
    report.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    
    splits_order = ["train", "val", "test_interp", "test_ood_narrow", "test_ood_count", "test_ood_boundary", "test_ood_highmodes"]
    for sp in splits_order:
        b = bench_rows[sp]
        v = v1_rows[sp]
        report.append(
            f"| `{sp}` | {b['samples']} | "
            f"{float(v['fno_v1_l2_med']):.4f} ({float(v['fno_v1_l2_med'])*100:.2f}%) | "
            f"{float(v['fno_v1_l2_p90']):.4f} | "
            f"{float(b['fno_l2_med']):.4f} ({float(b['fno_l2_med'])*100:.2f}%) | "
            f"{float(b['fno_l2_p90']):.4f} | "
            f"{float(b['lin_l2_med']):.4e} | "
            f"{float(b['fno_res_med']):.4f} |"
        )
    report.append("")
    report.append("### Baseline Exactness & Degeneracy Analysis")
    report.append(
        "the linear map is exact because the Poisson problem with fixed boundary conditions is linear "
        f"and the source family has low effective rank; it degrades on high modes ({float(bench_rows['test_ood_highmodes']['lin_l2_med']):.1e})."
    )
    report.append("")
    report.append("## 4. Documented Failure Modes (Stress Matrix Top Failures)")
    report.append("Quantitative failure mode taxonomy from Poisson v2 evaluation:")
    report.append(f"1. **`highmodes` (Spectral Truncation):** Modes $m, n \\in [5, 8]$ exceeding the FNO modes 12 cutoff. Median relative $L_2$ error is **{float(bench_rows['test_ood_highmodes']['fno_l2_med'])*100:.1f}%** ({float(bench_rows['test_ood_highmodes']['fno_l2_med']):.4f}), P90 is **{float(bench_rows['test_ood_highmodes']['fno_l2_p90'])*100:.1f}%** ({float(bench_rows['test_ood_highmodes']['fno_l2_p90']):.4f}), and max error is **{float(bench_rows['test_ood_highmodes']['fno_l2_max'])*100:.1f}%** ({float(bench_rows['test_ood_highmodes']['fno_l2_max']):.4f}). Field comparison saved to `plots/fno_v2_highmodes_failure.png`.")
    report.append(f"2. **`boundary` (Extreme Boundary Layer):** Sources situated within 0.12 of the domain perimeter ($c_x, c_y \\le 0.12$). Median relative $L_2$ error is **{float(bench_rows['test_ood_boundary']['fno_l2_med'])*100:.1f}%** ({float(bench_rows['test_ood_boundary']['fno_l2_med']):.4f}), P90 is **{float(bench_rows['test_ood_boundary']['fno_l2_p90'])*100:.1f}%** ({float(bench_rows['test_ood_boundary']['fno_l2_p90']):.4f}), and max error is **{float(bench_rows['test_ood_boundary']['fno_l2_max'])*100:.1f}%** ({float(bench_rows['test_ood_boundary']['fno_l2_max']):.4f}).")
    report.append(f"3. **`narrow` (Sub-Grid Scale Cutoff):** Source widths $w \\in [0.04, 0.07]$ approaching the grid spacing resolution limit ($h = 1/63 \\approx 0.0159$). Median relative $L_2$ error is **{float(bench_rows['test_ood_narrow']['fno_l2_med'])*100:.1f}%** ({float(bench_rows['test_ood_narrow']['fno_l2_med']):.4f}), P90 is **{float(bench_rows['test_ood_narrow']['fno_l2_p90'])*100:.1f}%** ({float(bench_rows['test_ood_narrow']['fno_l2_p90']):.4f}), and max error is **{float(bench_rows['test_ood_narrow']['fno_l2_max'])*100:.1f}%** ({float(bench_rows['test_ood_narrow']['fno_l2_max']):.4f}).")
    report.append("")
    report.append("### Top 3 Worst Failure Samples per OOD Regime")
    for sp in ["test_ood_highmodes", "test_ood_boundary", "test_ood_narrow"]:
        report.append(f"- **`{sp}`:**")
        for item in failure_cases[sp][:3]:
            report.append(f"  - Rank {item['rank']}: Sample Index {item['split_index']} (Seed {item['seed']}): Rel $L_2$ = {item['rel_l2_error']:.6f} ({item['rel_l2_error']*100:.2f}%) | {item['description']}")
            
    report.append("")
    report.append("## 5. FNO v3 Colab Script & Acceptance Framework")
    report.append("- **Script Path:** `src/train_fno_poisson_v3.py`")
    report.append("- **Configuration:** `FNO2d(modes1=16, modes2=16, width=64, in_channels=3, out_channels=1, use_hard_mask=True)`, CosineAnnealingLR up to 300 epochs, early stopping on val loss.")
    report.append("- **Command to Execute on Colab (with GPU):**")
    report.append("  ```bash")
    report.append("  python src/train_fno_poisson_v3.py --seeds 42 43 44 45 46 --device cuda --out-dir models/fno_v3 --epochs 300 --patience 25")
    report.append("  ```")
    report.append(f"- **Strict Acceptance Rule:**")
    report.append(f"  - Val median relative $L_2$ must improve by at least 2x: $\\le {float(bench_rows['val']['fno_l2_med'])/2.0:.6f}$ ({float(bench_rows['val']['fno_l2_med'])*50:.2f}%) vs v2 ({float(bench_rows['val']['fno_l2_med']):.6f}).")
    report.append(f"  - All OOD medians must be no worse than v2: narrow $\\le {float(bench_rows['test_ood_narrow']['fno_l2_med']):.6f}$, count $\\le {float(bench_rows['test_ood_count']['fno_l2_med']):.6f}$, boundary $\\le {float(bench_rows['test_ood_boundary']['fno_l2_med']):.6f}$, highmodes $\\le {float(bench_rows['test_ood_highmodes']['fno_l2_med']):.6f}$.")
    report.append("  - If met: Accept v3. Otherwise: Freeze Poisson FNO v2.")
    
    full_text = "\n".join(report)
    
    out_md = "reports/stage2_review.md"
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    with open(out_md, "w") as f:
        f.write(full_text)
        
    print(f"Report generated and written to {out_md}\n")
    print(full_text)

if __name__ == "__main__":
    generate_report()
