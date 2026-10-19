# Experiments & Pipelines Register

A comprehensive registry of every script in the repository detailing its purpose, inputs, outputs, verification audit/table, and operational classification.

| Script | Purpose | Inputs | Outputs | Verification Audit / Table | Classification |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `src/train.py` | Trains official 1D Heat FNO surrogate model | `data/interim/train.npz`, `val.npz` | `models/fno2d_heat.pt`, `plots/fno_generalization.png` | `eval_final_all.py`, `audit_inverse.py` | **FINAL** |
| `src/train_fno_poisson_v2.py` | Trains 2D Poisson FNO with zero boundary masking | `data/poisson_v2_train.npz`, `val.npz` | `models/fno2d_poisson_v2.pt`, `data/fno2d_v2_training_curves.csv`, `summary.json` | `data/poisson_v2_benchmark_table.csv` | **FINAL** |
| `src/train_pinn_poisson.py` | Trains hard-constrained PINN on 2D Poisson | Exact PDE collocation points | `models/pinn_poisson.pt`, `data/pinn_poisson_summary.json` | `data/audit_poisson.txt`, `test_poisson_stage2.py` | **FINAL** |
| `src/train_expD_pinn.py` | Trains Task B bounded reparametrized PINN | PDE collocation grid | `models/pinn_expD.pt` | `data/audit_pinn_report.txt`, `study_pinn_inverse.py` | **FINAL** |
| `src/train_expD_fno.py` | Trains bounded reparametrized FNO | `data/interim/train.npz`, `val.npz` | `models/fno2d_expD.pt` | `src/eval_final_all.py` | **FINAL** |
| `src/eval_final_all.py` | Comprehensive decision verification across FNO/PINN models | `data/interim/test_*.npz`, `models/fno2d_heat.pt`, `models/pinn_expD.pt` | Terminal metrics summary | `DECISIONS.md` | **FINAL** |
| `src/eval_poisson_v2.py` | Evaluates FNO and fits linear baseline on all 7 Poisson splits | `data/poisson_v2_*.npz`, `models/fno2d_poisson_v2.pt` | `data/poisson_v2_eval_results.json`, `data/poisson_v2_benchmark_table.csv`, `models/linear_baseline_poisson_v2.npz` | `data/poisson_v2_benchmark_table.csv` | **FINAL** |
| `src/benchmark_timing_honesty.py` | Benchmarks inference latency of FNO vs classical sparse solver vs linear baseline | `models/fno2d_poisson_v2.pt`, `models/linear_baseline_poisson_v2.npz` | `data/timing_honesty.json` | `data/audit_poisson.txt` | **FINAL** |
| `src/inverse_mode2.py` | Mode 2 finite-difference spline inverse parameter estimation | Synthetic noisy sensor measurements | Terminal metrics, `plots/mode2_bias_vs_alpha_sigma0.png` | `data/mode2_pipeline_results_v2.csv`, `data/audit_report.txt` | **FINAL** |
| `src/inverse_mode3.py` | Mode 3 FNO spline inverse parameter estimation with autograd | Synthetic measurements, `models/fno2d_heat.pt` | `plots/mode3_spurious_loss_alpha*.png` | `data/mode3_pipeline_results_v2.csv`, `data/audit_report.txt` | **FINAL** |
| `src/inverse_spline_benchmark.py` | Runs systematic parameter grid benchmark for spline inversion | Exact solver, `models/fno2d_heat.pt` | `data/spline_pipeline_results.npz` | `data/audit_report.txt` | **FINAL** |
| `src/run_definitive_pipeline.py` | Reproduces full Mode 2 and Mode 3 benchmark evaluation | `models/fno2d_heat.pt`, sensor layouts | `data/mode2_pipeline_results_v2.csv`, `data/mode3_pipeline_results_v2.csv` | `data/audit_report.txt` | **FINAL** |
| `src/run_hybrid_benchmark.py` | Runs Mode 3+ solver-polish ablation against Mode 2 and 3 | `models/fno2d_heat.pt`, finite difference solver | `data/mode3plus_hybrid_results.csv` | `data/audit_report.txt` | **FINAL** |
| `src/study_anomaly.py` | Detects physical regime shifts and sensor corruptions | `models/fno2d_heat.pt`, simulation seeds | `data/raw/anomaly_raw.csv` | `data/audit_anomaly.txt`, `data/anomaly_summary.csv` | **FINAL** |
| `src/study_sensor_placement.py` | Task A: Tests 7 sensor time placement strategies vs CRB | Heat FD solver, simulation seeds | `data/raw/sensor_placement_raw.csv`, `data/sensor_placement_summary.csv` | `data/audit_sensor_placement.txt` | **FINAL** |
| `src/study_pinn_inverse.py` | Task B: Mode 1 frozen PINN surrogate inversion | `models/pinn_expD.pt`, `models/fno2d_heat.pt` | `data/raw/mode1_pinn_raw.csv`, `data/mode1_pinn_summary.csv` | `data/audit_pinn_report.txt` | **FINAL** |
| `src/study_linear_baseline.py` | Hyperparameter search and evaluation of dual ridge baseline | `data/poisson_v2_*.npz` | `data/linear_baseline_study.json` | `data/poisson_v2_benchmark_table.csv` | **FINAL** |
| `src/audit_anomaly.py` | Audits anomaly detection confusion matrices & recall | `data/raw/anomaly_raw.csv` | `data/audit_anomaly.txt`, `data/anomaly_summary.csv` | `run_manifest.json` | **FINAL** |
| `src/audit_inverse.py` | Audits Mode 2, Mode 3, and Mode 3+ results vs spec | `data/mode2_pipeline_results_v2.csv`, `mode3_*.csv` | `data/audit_report.txt` | `run_manifest.json` | **FINAL** |
| `src/audit_pinn_inverse.py` | Audits Task B PINN inversion against CRB and bounds | `data/mode1_pinn_summary.csv`, `raw/mode1_pinn_raw.csv` | `data/audit_pinn_report.txt` | `run_manifest.json` | **FINAL** |
| `src/audit_poisson.py` | Audits 2D Poisson deliverables, solver convergence, timings | Poisson v1 splits, `poisson_eval_results.json` | `data/audit_poisson.txt` | `run_manifest.json` | **FINAL** |
| `src/audit_sensor_placement.py` | Audits Task A placement strategies vs theoretical bound | `data/sensor_placement_summary.csv` | `data/audit_sensor_placement.txt` | `run_manifest.json` | **FINAL** |
| `src/data/generate_dataset.py` | Generates 1D Heat training, validation, and test splits | Fourier exact solution series | `data/interim/train.npz`, `val.npz`, `test_*.npz` | `verify_dataset.py` | **FINAL** |
| `src/data/generate_poisson_dataset_v2.py` | Generates 7 Poisson evaluation splits with disjoint seeds | Exact 2D Poisson solver | `data/poisson_v2_*.npz` (7 splits) | `tests/test_poisson_stage2.py` | **FINAL** |
| `src/data/verify_dataset.py` | Verifies 1D heat dataset distributions and BCs | `data/interim/*.npz` | `plots/alpha_histogram.png` | Terminal check | **FINAL** |
| `experiments/train_pinn_expA.py` | Exp A: Soft-penalty PINN training ablation | Collocation points | `experiments/models/pinn_expA.pt` | `experiments/diagnostics_exp.py` | **EXPERIMENT** |
| `experiments/train_pinn_expB.py` | Exp B: Boundary-reparametrized PINN ablation | Collocation points | `experiments/models/pinn_expB.pt` | `experiments/diagnostics_exp.py` | **EXPERIMENT** |
| `experiments/train_expC.py` | Exp C: Boundary-reparametrized FNO ablation | `data/interim/*.npz` | `experiments/models/fno2d_expC.pt` | `src/eval_final_all.py` | **EXPERIMENT** |
| `experiments/train_pinn.py` | Base parametric PINN training | Collocation points | `experiments/models/pinn_heat.pt` | `experiments/eval_full_rollout.py` | **EXPERIMENT** |
| `experiments/eval_fno_compare.py` | Evaluates base FNO vs Exp D on OOD test split | `data/interim/test_ood.npz`, checkpoints | Terminal error metrics | `DECISIONS.md` | **EXPERIMENT** |
| `experiments/eval_fno_t1_99.py` | Evaluates FNO prediction error on t=1 to 99 | `data/interim/*.npz`, `models/fno2d_heat.pt` | Terminal MAE summary | `DECISIONS.md` | **EXPERIMENT** |
| `experiments/eval_full_rollout.py` | Multi-step autoregressive rollout comparison across models | `data/interim/test_ood.npz`, all model weights | `plots/full_rollout_abs_error_comparison.png` | `DECISIONS.md` | **EXPERIMENT** |
| `experiments/eval_pinn_timesteps.py` | PINN timestep-by-timestep error analysis | `models/pinn_heat.pt`, exact solution | Terminal error breakdown | `DECISIONS.md` | **EXPERIMENT** |
| `experiments/eval_summary.py` | Evaluates rollout errors across all heat ablation models | `data/interim/test_ood.npz`, model checkpoints | Terminal summary table | `DECISIONS.md` | **EXPERIMENT** |
| `experiments/eval_timesteps.py` | Per-timestep error evaluation of FNO | `data/interim/test_ood.npz`, `models/fno2d_heat.pt` | `plots/per_timestep_error.png` | `DECISIONS.md` | **EXPERIMENT** |
| `experiments/diagnostics.py` | Investigates t=0 error behavior in baseline FNO | `models/fno2d_heat.pt`, `data/interim/*.npz` | `plots/t0_error_vs_alpha.png` | `DECISIONS.md` | **EXPERIMENT** |
| `experiments/diagnostics_exp.py` | Investigates t=0 error across ablation models Exp A-D | Model checkpoints, `data/interim/*.npz` | `plots/t0_error_experiments.png` | `DECISIONS.md` | **EXPERIMENT** |
| `tools/generate_final_pipeline_tables.py` | Assembles final benchmark tables into structured pickle | Benchmark CSVs, `models/fno2d_heat.pt` | `data/final_pipeline_tables.pkl` | `data/audit_report.txt` | **TOOL** |
| `tools/generate_markdown_tables.py` | Converts benchmark CSVs into formatted GitHub Markdown tables | Benchmark CSVs | `data/mode2_table.md`, `mode3_table.md`, `mode3plus_table.md` | `data/audit_report.txt` | **TOOL** |
| `tools/generate_heatmaps.py` | Generates 3x3 median error and ratio comparison heatmaps | Benchmark CSVs | `plots/inverse_pipeline_error_heatmaps.png`, `ratio_heatmaps.png` | `run_manifest.json` | **TOOL** |
| `tools/export_csv.py` | Exports table data from serialized pickle to CSV | `data/final_pipeline_tables.pkl` | `data/mode2_pipeline_results.csv`, `mode3_results.csv` | Data export | **TOOL** |
