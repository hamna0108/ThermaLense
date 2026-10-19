# Phase A Cleanup Plan: Repository Reorganization & Dependency Audit
> **Status:** DRY RUN COMPLETE & STOPPED FOR APPROVAL. No files have been moved or modified.
> **Baseline Integrity:** Repository initialized with Git, all 149 files committed, tagged `pre-cleanup`, and full zip backup created at `C:\Users\HP\Desktop\Digital_twin_backup_pre_cleanup.zip` (263.7 MB).

## 1. Overview and Target Layout

The objective is to establish a pristine separation between **FINAL** production work, **EXPERIMENTS** (required ablation evidence), **TOOLS** (report post-processing), **ARCHIVE** (superseded older versions & scratch dumps), and **DOCS** (system architecture & specifications).

```
Digital twin/
  README.md                  # Concise guide to the final pipeline
  EXPERIMENTS.md             # Purpose, inputs, outputs, audits for all ablation studies
  DECISIONS.md               # Architecture decisions (options tried -> chosen -> evidence)
  PROJECT_CONTEXT.md         # Context documentation
  requirements.txt           # Python dependencies
  run_manifest.json          # Canonical 7-section run manifest
  src/                       # Final library & final pipeline scripts only
    solvers/                 # Exact/numerical solvers (heat_1d.py, poisson_2d.py)
    models/                  # Final neural architectures (fno2d.py, pinn.py, pinn_poisson.py, linear_baseline.py)
    data/                    # Final data loaders and dataset generation utilities
  tests/                     # Test suite (test_heat_1d.py, test_poisson_2d.py, test_poisson_stage2.py)
  data/                      # Final datasets and benchmark results
    raw/                     # Task A/B and Anomaly simulation replications
    interim/                 # 1D Heat dataset splits
  models/                    # Final checkpoints only (fno2d_heat.pt, pinn_expD.pt, fno2d_poisson_v2.pt, pinn_poisson.pt, linear_baseline_poisson_v2.npz)
  plots/                     # Final diagnostic and benchmark plots
  docs/                      # Brief docx, Architecture docx, clean UTF-8 text extracts
  experiments/               # Runnable ablation experiments (with __init__.py and README.md)
    models/                  # Experiment checkpoints (fno2d_expC.pt, fno2d_expD.pt, pinn_expA.pt, pinn_expB.pt, pinn_heat.pt)
  tools/                     # Post-processing & table generation tools
  archive/
    superseded/              # Poisson v1 scripts/data/models, old manifest, old inverse_mode2_old.py
    failed/                  # Dead ends
    scratch/                 # Raw UTF-16 extraction dumps
    INDEX.md                 # Traceability index: item | category | why moved | what replaced it | evidence
```

## 2. Complete Inventory Table (All 149 Tracked Files)

### Root Files

| Path | User Category | Recommended Category (After Dep Check) | Referenced By | Reason & Notes |
| :--- | :--- | :--- | :--- | :--- |
| `06_Hamna_Neural_PDE_Digital_Twin.docx` | DOCS -> docs/ | **DOCS -> docs/** | *None (leaf/standalone)* | Original client project brief specification docx. |
| `Implementation Plan & System Architectur.docx` | DOCS -> docs/ | **DOCS -> docs/** | *None (leaf/standalone)* | System architecture and implementation plan docx. |
| `arch_text.txt` | ARCHIVE/scratch -> archive/scratch/ | **ARCHIVE/scratch -> archive/scratch/** | *None (leaf/standalone)* | Raw UTF-16 text dump with BOM from architecture docx extraction. |
| `arch_text_utf8.txt` | ARCHIVE/scratch or DOCS | **DOCS -> docs/** | *None (leaf/standalone)* | Clean UTF-8 text extraction of system architecture docx; essential reference. |
| `brief_text.txt` | ARCHIVE/scratch -> archive/scratch/ | **ARCHIVE/scratch -> archive/scratch/** | *None (leaf/standalone)* | Raw UTF-16 text dump with BOM from project brief docx extraction. |
| `brief_text_utf8.txt` | ARCHIVE/scratch or DOCS | **DOCS -> docs/** | *None (leaf/standalone)* | Clean UTF-8 text extraction of client brief docx; essential reference. |
| `inverse_mode2_old.py` | ARCHIVE/superseded -> archive/superseded/ | **ARCHIVE/superseded -> archive/superseded/** | *None (leaf/standalone)* | Old slow un-vectorized version of Mode 2 spline inverse solver. |
| `mode2_results_v2.txt` | DOCS -> data/ | **data/ (or archive/superseded/)** | *None (leaf/standalone)* | PowerShell stdout capture of inverse_mode2.py execution; move to data/ beside CSVs. |
| `mode3_results_v2.txt` | DOCS -> data/ | **data/ (or archive/superseded/)** | *None (leaf/standalone)* | PowerShell stdout capture of inverse_mode3.py execution; move to data/ beside CSVs. |
| `requirements.txt` | FINAL (root) | **FINAL (root)** | *None (leaf/standalone)* | Project environment requirements and Python dependencies. |
| `run_manifest.json` | FINAL (root) | **FINAL (root)** | *None (leaf/standalone)* | Canonical, complete run manifest (7 sections: Stage 1 Inversion, Anomaly, Tasks A/B, Stage 2 Poisson). |

### Agent Rules (.agents/)

| Path | User Category | Recommended Category (After Dep Check) | Referenced By | Reason & Notes |
| :--- | :--- | :--- | :--- | :--- |
| `.agents/rules/visualization_rule.md` | FINAL (customization) | **FINAL (customization)** | *None (leaf/standalone)* | Agent IDE visualization and aesthetic styling rule for matplotlib figures. |

### Documentation & Text Extracts (Root)

| Path | User Category | Recommended Category (After Dep Check) | Referenced By | Reason & Notes |
| :--- | :--- | :--- | :--- | :--- |

### Core Source Library (src/solvers, src/models, src/data, src/__init__.py)

| Path | User Category | Recommended Category (After Dep Check) | Referenced By | Reason & Notes |
| :--- | :--- | :--- | :--- | :--- |
| `src/__init__.py` | FINAL | **FINAL** | *None (leaf/standalone)* | Library root package initialization. |
| `src/data/dataset.py` | FINAL | **FINAL** | `src/diagnostics.py`, `src/diagnostics_exp.py`, `src/eval_final_all.py`, `src/eval_fno_compare.py`, +7 more | PyTorch Dataset and normalization routines for 1D heat data. |
| `src/data/generate_dataset.py` | FINAL | **FINAL** | `src/data/verify_dataset.py` | Generator script producing 1D heat training, val, and test datasets in data/interim/. |
| `src/data/generate_poisson_dataset.py` | FINAL (user table) | **ARCHIVE/superseded -> archive/superseded/** | `src/data/generate_poisson_dataset_v2.py` | Poisson v1 dataset generator; superseded by generate_poisson_dataset_v2.py. |
| `src/data/generate_poisson_dataset_v2.py` | FINAL | **FINAL** | *None (leaf/standalone)* | Final Poisson v2 dataset generator with disjoint seeds and 7 evaluation splits. |
| `src/data/poisson_loader.py` | FINAL | **FINAL** | `src/audit_poisson.py`, `src/eval_poisson_all.py`, `src/eval_poisson_v2.py`, `src/study_linear_baseline.py`, +3 more | Data loading and PyTorch Dataset utilities for 2D Poisson datasets. |
| `src/data/verify_dataset.py` | FINAL | **FINAL** | *None (leaf/standalone)* | Verification script checking heat dataset distributions and boundary conditions. |
| `src/models/fno2d.py` | FINAL | **FINAL** | `src/benchmark_timing_honesty.py`, `src/diagnostics.py`, `src/diagnostics_exp.py`, `src/eval_final_all.py`, +19 more | Core Fourier Neural Operator (FNO-2D) architecture implementation. |
| `src/models/linear_baseline.py` | FINAL | **FINAL** | `src/benchmark_timing_honesty.py`, `src/eval_poisson_all.py`, `src/eval_poisson_v2.py`, `src/study_linear_baseline.py`, +1 more | Linear ridge regression dual operator baseline for Poisson equation. |
| `src/models/pinn.py` | FINAL | **FINAL** | `src/eval_final_all.py`, `src/eval_full_rollout.py`, `src/eval_summary.py`, `src/train_expD_pinn.py`, +5 more | Base MLP architecture for Physics-Informed Neural Networks. |
| `src/models/pinn_poisson.py` | FINAL | **FINAL** | `src/train_pinn_poisson.py`, `tests/test_poisson_stage2.py` | Exact hard-boundary constrained PINN architecture for 2D Poisson. |
| `src/solvers/__init__.py` | FINAL | **FINAL** | *None (leaf/standalone)* | Solvers package initialization. |
| `src/solvers/heat_1d.py` | FINAL | **FINAL** | `src/data/generate_dataset.py`, `tests/test_heat_1d.py` | Core finite-difference Crank-Nicolson solver for 1D heat equation. |
| `src/solvers/poisson_2d.py` | FINAL | **FINAL** | `src/audit_poisson.py`, `src/benchmark_timing_honesty.py`, `src/data/generate_poisson_dataset.py`, `src/data/generate_poisson_dataset_v2.py`, +4 more | Core sparse direct LU solver for 2D Poisson equation on uniform grids. |

### Final Inverse, Studies & Audits (src/)

| Path | User Category | Recommended Category (After Dep Check) | Referenced By | Reason & Notes |
| :--- | :--- | :--- | :--- | :--- |
| `src/audit_anomaly.py` | FINAL | **FINAL** | *None (leaf/standalone)* | Audit script verifying anomaly detection metrics and confusion matrices. |
| `src/audit_inverse.py` | FINAL | **FINAL** | *None (leaf/standalone)* | Audit script verifying Mode 2, Mode 3, and Mode 3+ tables against requirements. |
| `src/audit_pinn_inverse.py` | FINAL | **FINAL** | *None (leaf/standalone)* | Audit script verifying Task B Mode 1 PINN inverse results. |
| `src/audit_poisson.py` | FINAL | **FINAL** | *None (leaf/standalone)* | Audit script verifying 2D Poisson Week 1 deliverables. |
| `src/audit_sensor_placement.py` | FINAL | **FINAL** | *None (leaf/standalone)* | Audit script verifying Task A sensor time placement results. |
| `src/benchmark_timing_honesty.py` | FINAL | **FINAL** | *None (leaf/standalone)* | Inference latency benchmark comparing classical sparse solver, FNO, and linear baseline. |
| `src/eval_poisson_v2.py` | FINAL | **FINAL** | *None (leaf/standalone)* | Final comprehensive evaluation script for 2D Poisson models across all 7 splits. |
| `src/inverse_mode2.py` | FINAL | **FINAL** | *None (leaf/standalone)* | Final Mode 2 Crank-Nicolson spline inverse parameter estimator. |
| `src/inverse_mode3.py` | FINAL | **FINAL** | *None (leaf/standalone)* | Final Mode 3 FNO spline inverse parameter estimator with gradient refinement. |
| `src/inverse_spline_benchmark.py` | FINAL | **FINAL** | *None (leaf/standalone)* | Benchmark runner for spline-based inverse estimation over parameter grids. |
| `src/run_definitive_pipeline.py` | FINAL | **FINAL** | *None (leaf/standalone)* | Definitive inverse pipeline reproducing Mode 2 and Mode 3 benchmark CSVs. |
| `src/run_hybrid_benchmark.py` | FINAL | **FINAL** | `data/run_manifest.json`, `run_manifest.json` | Runner for Mode 3+ Solver-Polish ablation alongside Mode 2 and Mode 3. |
| `src/study_anomaly.py` | FINAL | **FINAL** | *None (leaf/standalone)* | Comprehensive anomaly detection study across physics mismatch and sensor failure modes. |
| `src/study_linear_baseline.py` | FINAL | **FINAL** | *None (leaf/standalone)* | Evaluation and hyperparameter regularization search for Poisson linear baseline. |
| `src/study_pinn_inverse.py` | FINAL | **FINAL** | *None (leaf/standalone)* | Task B: Mode 1 frozen PINN surrogate inverse evaluation across parameter cells. |
| `src/study_sensor_placement.py` | FINAL | **FINAL** | *None (leaf/standalone)* | Task A: Evaluation of 7 temporal sensor placement strategies vs Cramér-Rao bound. |
| `src/train.py` | ASK | **FINAL** | *None (leaf/standalone)* | Official 1D Heat FNO training script; produces models/fno2d_heat.pt used by entire final inverse pipeline. |
| `src/train_fno_poisson_v2.py` | FINAL | **FINAL** | *None (leaf/standalone)* | Final training script for 2D Poisson FNO with hard zero-boundary masking. |
| `src/train_pinn_poisson.py` | FINAL | **FINAL** | *None (leaf/standalone)* | Final training script for hard-constrained Poisson PINN baseline. |

### Experiments & Ablations (src/)

| Path | User Category | Recommended Category (After Dep Check) | Referenced By | Reason & Notes |
| :--- | :--- | :--- | :--- | :--- |
| `src/diagnostics.py` | EXPERIMENTS -> experiments/ | **EXPERIMENTS -> experiments/** | *None (leaf/standalone)* | Diagnostic script investigating t=0 error in base FNO. |
| `src/diagnostics_exp.py` | EXPERIMENTS -> experiments/ | **EXPERIMENTS -> experiments/** | *None (leaf/standalone)* | Diagnostic script investigating t=0 error across ablation models Exp A-D. |
| `src/eval_final_all.py` | EXPERIMENTS -> experiments/ | **EXPERIMENTS -> experiments/ (UPDATE IMPORT)** | `src/study_pinn_inverse.py` | Comprehensive model comparison script. Defines BoundedReparametrizedPINN imported by src/study_pinn_inverse.py. |
| `src/eval_fno_compare.py` | EXPERIMENTS -> experiments/ | **EXPERIMENTS -> experiments/** | *None (leaf/standalone)* | Comparative evaluation of base FNO vs Exp D on OOD test split. |
| `src/eval_fno_t1_99.py` | EXPERIMENTS -> experiments/ | **EXPERIMENTS -> experiments/** | *None (leaf/standalone)* | Evaluation of FNO prediction accuracy across timesteps t=1 to 99. |
| `src/eval_full_rollout.py` | EXPERIMENTS -> experiments/ | **EXPERIMENTS -> experiments/** | *None (leaf/standalone)* | Multi-step autoregressive rollout evaluation comparing FNO and PINN variants. |
| `src/eval_pinn_timesteps.py` | EXPERIMENTS -> experiments/ | **EXPERIMENTS -> experiments/** | *None (leaf/standalone)* | Evaluation of PINN prediction accuracy across individual timesteps. |
| `src/eval_summary.py` | EXPERIMENTS -> experiments/ | **EXPERIMENTS -> experiments/** | *None (leaf/standalone)* | Summary evaluation script computing rollout errors across all heat experiment models. |
| `src/eval_timesteps.py` | EXPERIMENTS -> experiments/ | **EXPERIMENTS -> experiments/** | *None (leaf/standalone)* | Per-timestep error evaluation script generating plots/per_timestep_error.png. |
| `src/train_expC.py` | EXPERIMENTS -> experiments/ | **EXPERIMENTS -> experiments/** | `src/diagnostics_exp.py`, `src/eval_final_all.py`, `src/eval_full_rollout.py`, `src/eval_summary.py` | Exp C: Hard-constraint FNO training ablation; produces models/fno2d_expC.pt. |
| `src/train_expD_fno.py` | EXPERIMENTS -> experiments/ | **EXPERIMENTS -> experiments/** | `src/eval_final_all.py`, `src/eval_fno_compare.py`, `src/eval_fno_t1_99.py`, `src/eval_full_rollout.py`, +1 more | Exp D: Bounded reparametrized FNO training ablation; produces models/fno2d_expD.pt. |
| `src/train_expD_pinn.py` | EXPERIMENTS -> experiments/ | **EXPERIMENTS -> experiments/** | `src/eval_full_rollout.py`, `src/eval_summary.py` | Exp D: Bounded reparametrized PINN training script; produces models/pinn_expD.pt. |
| `src/train_pinn.py` | ASK | **EXPERIMENTS -> experiments/** | `src/diagnostics.py`, `src/diagnostics_exp.py`, `src/eval_full_rollout.py`, `src/eval_pinn_timesteps.py` | Trains heat PINN producing models/pinn_heat.pt; not used by final inverse code (Task B uses pinn_expD.pt). |
| `src/train_pinn_expA.py` | EXPERIMENTS -> experiments/ | **EXPERIMENTS -> experiments/** | *None (leaf/standalone)* | Exp A: Soft penalty PINN training ablation; produces models/pinn_expA.pt. |
| `src/train_pinn_expB.py` | EXPERIMENTS -> experiments/ | **EXPERIMENTS -> experiments/** | `src/diagnostics_exp.py`, `src/eval_full_rollout.py`, `src/eval_summary.py` | Exp B: Reparametrized PINN training ablation; produces models/pinn_expB.pt. |

### Report Tooling (src/ -> tools/)

| Path | User Category | Recommended Category (After Dep Check) | Referenced By | Reason & Notes |
| :--- | :--- | :--- | :--- | :--- |
| `src/export_csv.py` | TOOLS -> tools/ | **TOOLS -> tools/** | *None (leaf/standalone)* | Utility script exporting final tables pickle to CSV. |
| `src/generate_final_pipeline_tables.py` | TOOLS -> tools/ | **TOOLS -> tools/** | *None (leaf/standalone)* | Post-processing script assembling benchmark metrics into data/final_pipeline_tables.pkl. |
| `src/generate_heatmaps.py` | TOOLS -> tools/ | **TOOLS -> tools/** | *None (leaf/standalone)* | Tool generating 3x3 error and ratio comparison heatmaps in plots/. |
| `src/generate_markdown_tables.py` | TOOLS -> tools/ | **TOOLS -> tools/** | *None (leaf/standalone)* | Tool converting CSV results into formatted Markdown benchmark tables in data/. |

### Superseded Scripts (src/ -> archive/superseded/)

| Path | User Category | Recommended Category (After Dep Check) | Referenced By | Reason & Notes |
| :--- | :--- | :--- | :--- | :--- |
| `src/eval_poisson_all.py` | ARCHIVE/superseded | **ARCHIVE/superseded -> archive/superseded/** | `src/audit_poisson.py` | Poisson v1 evaluation script; superseded by eval_poisson_v2.py. |
| `src/train_fno_poisson.py` | ARCHIVE/superseded | **ARCHIVE/superseded -> archive/superseded/** | *None (leaf/standalone)* | Poisson Stage 2 v1 FNO training script; produces models/fno2d_poisson.pt and fno2d_training_log.csv. |

### Tests (tests/)

| Path | User Category | Recommended Category (After Dep Check) | Referenced By | Reason & Notes |
| :--- | :--- | :--- | :--- | :--- |
| `tests/__init__.py` | FINAL (unchanged) | **FINAL (unchanged)** | *None (leaf/standalone)* | Test package initialization. |
| `tests/test_heat_1d.py` | FINAL (unchanged) | **FINAL (unchanged)** | *None (leaf/standalone)* | Unit tests verifying Crank-Nicolson 1D heat solver convergence and physics. |
| `tests/test_poisson_2d.py` | FINAL (unchanged) | **FINAL (unchanged)** | *None (leaf/standalone)* | Unit tests verifying 5-point stencil 2D Poisson solver second-order convergence. |
| `tests/test_poisson_stage2.py` | FINAL (unchanged) | **FINAL (unchanged)** | *None (leaf/standalone)* | Comprehensive regression test suite verifying all Stage 2 deliverables and baselines. |

### Models & Checkpoints (models/)

| Path | User Category | Recommended Category (After Dep Check) | Referenced By | Reason & Notes |
| :--- | :--- | :--- | :--- | :--- |
| `models/fno2d_expC.pt` | EXPERIMENTS -> experiments/ | **EXPERIMENTS -> experiments/** | `src/diagnostics_exp.py`, `src/eval_final_all.py`, `src/eval_full_rollout.py`, `src/eval_summary.py`, +1 more | Exp C: Hard-constraint FNO checkpoint; evaluated only in experiment rollouts. |
| `models/fno2d_expD.pt` | EXPERIMENTS (check if loaded by final) | **EXPERIMENTS -> experiments/** | `src/eval_final_all.py`, `src/eval_fno_compare.py`, `src/eval_fno_t1_99.py`, `src/eval_full_rollout.py`, +2 more | Exp D: Bounded reparametrized FNO checkpoint; evaluated only in experiment scripts. |
| `models/fno2d_heat.pt` | FINAL (if used by final) | **FINAL** | `src/diagnostics.py`, `src/diagnostics_exp.py`, `src/eval_final_all.py`, `src/eval_fno_compare.py`, +16 more | Official 1D Heat FNO forward surrogate checkpoint used by all final inverse pipelines. |
| `models/fno2d_poisson.pt` | ARCHIVE/superseded | **ARCHIVE/superseded -> archive/superseded/** | `run_manifest.json`, `src/benchmark_timing_honesty.py`, `src/eval_poisson_all.py`, `src/eval_poisson_v2.py`, +1 more | Poisson v1 FNO model checkpoint; superseded by fno2d_poisson_v2.pt. |
| `models/fno2d_poisson_v2.pt` | FINAL | **FINAL** | `src/eval_poisson_v2.py`, `src/train_fno_poisson_v2.py` | Official 2D Poisson FNO forward operator checkpoint. |
| `models/linear_baseline_poisson.npz` | ARCHIVE/superseded | **ARCHIVE/superseded -> archive/superseded/** | `run_manifest.json`, `src/benchmark_timing_honesty.py`, `src/eval_poisson_all.py` | Poisson v1 linear dual regression parameters; superseded by v2. |
| `models/linear_baseline_poisson_v2.npz` | FINAL | **FINAL** | `src/eval_poisson_v2.py` | Official 2D Poisson linear dual ridge regression baseline parameters. |
| `models/pinn_expA.pt` | EXPERIMENTS -> experiments/ | **EXPERIMENTS -> experiments/** | `src/diagnostics_exp.py`, `src/train_pinn_expA.py` | Exp A: Soft penalty PINN checkpoint; evaluated in diagnostics_exp.py. |
| `models/pinn_expB.pt` | EXPERIMENTS -> experiments/ | **EXPERIMENTS -> experiments/** | `src/diagnostics_exp.py`, `src/eval_full_rollout.py`, `src/eval_summary.py`, `src/train_pinn_expB.py` | Exp B: Reparametrized PINN checkpoint; evaluated in diagnostics_exp and rollouts. |
| `models/pinn_expD.pt` | EXPERIMENTS (check if loaded by final) | **FINAL (DEPENDENCY OVERRIDE)** | `src/eval_final_all.py`, `src/eval_full_rollout.py`, `src/eval_summary.py`, `src/study_pinn_inverse.py`, +1 more | Loaded by final script src/study_pinn_inverse.py (Task B surrogate). Must stay in models/. |
| `models/pinn_heat.pt` | EXPERIMENTS (check) | **EXPERIMENTS -> experiments/** | `src/diagnostics.py`, `src/diagnostics_exp.py`, `src/eval_full_rollout.py`, `src/eval_pinn_timesteps.py`, +2 more | Trained by train_pinn.py; evaluated only in experiment ablation comparisons. |
| `models/pinn_poisson.pt` | FINAL | **FINAL** | `run_manifest.json`, `src/train_pinn_poisson.py` | Hard-constrained PINN model checkpoint for 2D Poisson single-source task. |

### Data - Interim (data/interim/)

| Path | User Category | Recommended Category (After Dep Check) | Referenced By | Reason & Notes |
| :--- | :--- | :--- | :--- | :--- |
| `data/interim/test_interpolation.npz` | FINAL | **FINAL** | `src/data/generate_dataset.py`, `src/diagnostics.py`, `src/diagnostics_exp.py`, `src/eval_final_all.py`, +4 more | 1D Heat interpolation test split (100 samples, alpha in [0.01, 1.0]). |
| `data/interim/test_ood.npz` | FINAL | **FINAL** | `src/data/generate_dataset.py`, `src/diagnostics.py`, `src/diagnostics_exp.py`, `src/eval_final_all.py`, +6 more | 1D Heat OOD extrapolation test split (100 samples, alpha outside [0.01, 1.0]). |
| `data/interim/train.npz` | FINAL | **FINAL** | `run_manifest.json`, `src/benchmark_timing_honesty.py`, `src/data/generate_dataset.py`, `src/train.py`, +4 more | 1D Heat training split (800 samples, 100x50 spatiotemporal grids). |
| `data/interim/val.npz` | FINAL | **FINAL** | `run_manifest.json`, `src/data/generate_dataset.py`, `src/train.py`, `src/train_expC.py`, +3 more | 1D Heat validation split (100 samples, 100x50 spatiotemporal grids). |

### Data - Raw (data/raw/)

| Path | User Category | Recommended Category (After Dep Check) | Referenced By | Reason & Notes |
| :--- | :--- | :--- | :--- | :--- |
| `data/raw/anomaly_dev_raw.csv` | FINAL | **FINAL** | `data/audit_anomaly.txt`, `src/audit_anomaly.py`, `src/study_anomaly.py` | Development set feature vectors for anomaly detection threshold calibration. |
| `data/raw/anomaly_raw.csv` | FINAL | **FINAL** | `data/audit_anomaly.txt`, `data/run_manifest.json`, `run_manifest.json`, `src/audit_anomaly.py`, +1 more | Raw 6480-episode simulation outputs and features for anomaly detection study. |
| `data/raw/mode1_pinn_raw.csv` | FINAL | **FINAL** | `data/run_manifest.json`, `run_manifest.json`, `src/audit_pinn_inverse.py`, `src/study_pinn_inverse.py` | Raw 240-replication outputs for Mode 1 PINN inverse evaluation. |
| `data/raw/sensor_placement_raw.csv` | FINAL | **FINAL** | `data/run_manifest.json`, `run_manifest.json`, `src/audit_sensor_placement.py`, `src/study_sensor_placement.py` | Raw 16800-replication outputs for Task A sensor time placement study. |

### Data - Final Results & Audits (data/)

| Path | User Category | Recommended Category (After Dep Check) | Referenced By | Reason & Notes |
| :--- | :--- | :--- | :--- | :--- |
| `data/anomaly_summary.csv` | FINAL | **FINAL** | `data/run_manifest.json`, `run_manifest.json`, `src/audit_anomaly.py` | Per-cell aggregated anomaly detection metrics across all test seeds. |
| `data/audit_anomaly.txt` | FINAL | **FINAL** | `data/run_manifest.json`, `run_manifest.json`, `src/audit_anomaly.py` | Comprehensive 240-line audit report verifying anomaly detection deliverables. |
| `data/audit_pinn_report.txt` | FINAL | **FINAL** | `data/run_manifest.json`, `run_manifest.json`, `src/audit_pinn_inverse.py` | 53-line audit report verifying Task B Mode 1 PINN inverse results. |
| `data/audit_poisson.txt` | FINAL | **FINAL** | `run_manifest.json`, `src/audit_poisson.py` | 41-line audit report verifying 2D Poisson Week 1 deliverables. |
| `data/audit_report.txt` | FINAL | **FINAL** | `src/audit_inverse.py` | Audit report for Mode 2, Mode 3, and Mode 3+ inverse pipeline results. |
| `data/audit_sensor_placement.txt` | FINAL | **FINAL** | `data/run_manifest.json`, `run_manifest.json`, `src/audit_sensor_placement.py` | 47-line audit report verifying Task A sensor time placement results. |
| `data/final_pipeline_tables.pkl` | FINAL | **FINAL** | `src/export_csv.py`, `src/generate_final_pipeline_tables.py` | Serialized dictionary of final pipeline tables produced by generate_final_pipeline_tables.py. |
| `data/fno2d_training_log.csv` | ARCHIVE/superseded (check) | **ARCHIVE/superseded -> archive/superseded/** | `run_manifest.json`, `src/train_fno_poisson.py` | Training log from 15-epoch Poisson v1 run (written by train_fno_poisson.py). |
| `data/fno2d_v2_training_curves.csv` | FINAL | **FINAL** | `src/train_fno_poisson_v2.py` | Epoch-by-epoch training and validation loss curves for final Poisson v2 FNO. |
| `data/fno2d_v2_training_summary.json` | FINAL | **FINAL** | `src/train_fno_poisson_v2.py` | Summary metadata for final Poisson v2 FNO training run. |
| `data/linear_baseline_study.json` | FINAL | **FINAL** | `src/study_linear_baseline.py` | Results of alpha_reg hyperparameter search and evaluation for Poisson linear baseline. |
| `data/mode1_pinn_summary.csv` | FINAL | **FINAL** | `data/run_manifest.json`, `run_manifest.json`, `src/audit_pinn_inverse.py`, `src/study_pinn_inverse.py` | Task B Mode 1 PINN inverse cell metrics (median error, spread/CRB, wall time). |
| `data/mode2_pipeline_results_v2.csv` | FINAL | **FINAL** | `data/run_manifest.json`, `run_manifest.json`, `src/audit_inverse.py`, `src/audit_pinn_inverse.py`, +4 more | Final benchmark table for Mode 2 (Crank-Nicolson Spline) inverse pipeline (180 rows). |
| `data/mode2_table.md` | FINAL | **FINAL** | `data/run_manifest.json`, `run_manifest.json`, `src/generate_markdown_tables.py` | Formatted Markdown table of Mode 2 benchmark results. |
| `data/mode3_pipeline_results_v2.csv` | FINAL | **FINAL** | `data/run_manifest.json`, `run_manifest.json`, `src/audit_inverse.py`, `src/generate_heatmaps.py`, +3 more | Final benchmark table for Mode 3 (FNO Spline) inverse pipeline (135 rows). |
| `data/mode3_table.md` | FINAL | **FINAL** | `data/run_manifest.json`, `run_manifest.json`, `src/generate_markdown_tables.py` | Formatted Markdown table of Mode 3 benchmark results. |
| `data/mode3plus_hybrid_results.csv` | FINAL | **FINAL** | `data/run_manifest.json`, `run_manifest.json`, `src/audit_inverse.py`, `src/generate_heatmaps.py`, +2 more | Final benchmark table for Mode 3+ (Solver Polish ablation) inverse pipeline (135 rows). |
| `data/mode3plus_table.md` | FINAL | **FINAL** | `data/run_manifest.json`, `run_manifest.json`, `src/generate_markdown_tables.py` | Formatted Markdown table of Mode 3+ ablation results. |
| `data/pinn_poisson_summary.json` | FINAL | **FINAL** | `run_manifest.json`, `src/eval_poisson_all.py`, `src/train_pinn_poisson.py` | Benchmark metrics and training time for hard-constrained Poisson PINN. |
| `data/poisson_benchmark_table.csv` | ARCHIVE/superseded | **ARCHIVE/superseded -> archive/superseded/** | `run_manifest.json`, `src/eval_poisson_all.py` | Poisson v1 benchmark table; superseded by poisson_v2_benchmark_table.csv. |
| `data/poisson_eval_results.json` | ARCHIVE/superseded | **ARCHIVE/superseded -> archive/superseded/** | `run_manifest.json`, `src/audit_poisson.py`, `src/eval_poisson_all.py` | Poisson v1 evaluation results; superseded by poisson_v2_eval_results.json. |
| `data/poisson_manufactured_sanity.npz` | ARCHIVE/superseded | **ARCHIVE/superseded -> archive/superseded/** | `run_manifest.json`, `src/data/generate_poisson_dataset.py`, `src/eval_poisson_all.py` | Poisson v1 manufactured solution sanity test split; superseded by v2. |
| `data/poisson_test_interp.npz` | ARCHIVE/superseded | **ARCHIVE/superseded -> archive/superseded/** | `run_manifest.json` | Poisson v1 interpolation test split; superseded by v2. |
| `data/poisson_test_ood_boundary.npz` | ARCHIVE/superseded | **ARCHIVE/superseded -> archive/superseded/** | `run_manifest.json` | Poisson v1 boundary OOD test split; superseded by v2. |
| `data/poisson_test_ood_count.npz` | ARCHIVE/superseded | **ARCHIVE/superseded -> archive/superseded/** | `run_manifest.json` | Poisson v1 source-count OOD test split; superseded by v2. |
| `data/poisson_test_ood_narrow.npz` | ARCHIVE/superseded | **ARCHIVE/superseded -> archive/superseded/** | `run_manifest.json` | Poisson v1 narrow-source OOD test split; superseded by v2. |
| `data/poisson_train.npz` | ARCHIVE/superseded | **ARCHIVE/superseded -> archive/superseded/** | `run_manifest.json`, `src/train_fno_poisson.py` | Poisson v1 training dataset (1000 samples); superseded by poisson_v2_train.npz. |
| `data/poisson_v2_benchmark_table.csv` | FINAL | **FINAL** | `src/eval_poisson_v2.py` | Final summary benchmark table comparing FNO and Linear baseline on Poisson v2. |
| `data/poisson_v2_eval_results.json` | FINAL | **FINAL** | `src/eval_poisson_v2.py` | Final evaluation metrics across all splits and baselines on Poisson v2. |
| `data/poisson_v2_manufactured_sanity.npz` | FINAL | **FINAL** | `src/data/generate_poisson_dataset_v2.py`, `src/eval_poisson_v2.py` | Final Poisson v2 manufactured solution sanity benchmark. |
| `data/poisson_v2_test_interp.npz` | FINAL | **FINAL** | *None (leaf/standalone)* | Final Poisson v2 interpolation test split (200 samples). |
| `data/poisson_v2_test_ood_boundary.npz` | FINAL | **FINAL** | *None (leaf/standalone)* | Final Poisson v2 boundary OOD test split (200 samples). |
| `data/poisson_v2_test_ood_count.npz` | FINAL | **FINAL** | *None (leaf/standalone)* | Final Poisson v2 source count OOD test split (200 samples). |
| `data/poisson_v2_test_ood_highmodes.npz` | FINAL | **FINAL** | *None (leaf/standalone)* | Final Poisson v2 high-frequency Fourier modes OOD test split (200 samples). |
| `data/poisson_v2_test_ood_narrow.npz` | FINAL | **FINAL** | *None (leaf/standalone)* | Final Poisson v2 narrow sources OOD test split (200 samples). |
| `data/poisson_v2_train.npz` | FINAL | **FINAL** | `src/benchmark_timing_honesty.py`, `src/train_fno_poisson_v2.py` | Final Poisson v2 training split (1000 samples, 64x64). |
| `data/poisson_v2_val.npz` | FINAL | **FINAL** | `src/train_fno_poisson_v2.py` | Final Poisson v2 validation split (100 samples, 64x64). |
| `data/poisson_val.npz` | ARCHIVE/superseded | **ARCHIVE/superseded -> archive/superseded/** | `run_manifest.json`, `src/train_fno_poisson.py` | Poisson v1 validation split; superseded by poisson_v2_val.npz. |
| `data/run_manifest.json` | ASK | **ARCHIVE/superseded -> archive/superseded/** | *None (leaf/standalone)* | Older 6-section manifest snapshot lacking Stage 2 Poisson. Root copy is canonical. |
| `data/sensor_placement_summary.csv` | FINAL | **FINAL** | `data/run_manifest.json`, `run_manifest.json`, `src/audit_sensor_placement.py`, `src/study_sensor_placement.py` | Task A: Aggregated cell metrics across 7 sensor placement strategies. |
| `data/spline_pipeline_results.npz` | FINAL | **FINAL** | `src/inverse_spline_benchmark.py` | Full simulation array results of the spline inverse pipeline. |
| `data/timing_honesty.json` | FINAL | **FINAL** | `src/benchmark_timing_honesty.py` | Timing honesty benchmark metrics comparing FNO, classical solver, and linear baseline. |

### Plots (plots/)

| Path | User Category | Recommended Category (After Dep Check) | Referenced By | Reason & Notes |
| :--- | :--- | :--- | :--- | :--- |
| `plots/alpha_histogram.png` | FINAL (unchanged) | **FINAL (unchanged)** | `src/data/verify_dataset.py` | Histogram of alpha parameter distribution generated by src/data/verify_dataset.py. |
| `plots/fno_generalization.png` | FINAL (unchanged) | **FINAL (unchanged)** | `src/train.py`, `src/train_expC.py` | FNO generalization curve: relative error vs alpha on interpolation and OOD. |
| `plots/full_rollout_abs_error_comparison.png` | FINAL (unchanged) | **FINAL (unchanged)** | `src/eval_full_rollout.py` | Full rollout absolute error comparison across FNO and PINN variants. |
| `plots/full_rollout_comparison.png` | FINAL (unchanged) | **FINAL (unchanged)** | *None (leaf/standalone)* | Rollout trajectory comparison plot across models. |
| `plots/heat_1d_convergence.png` | FINAL (unchanged) | **FINAL (unchanged)** | `tests/test_heat_1d.py` | Spatial/temporal discretization convergence for 1D heat solver generated by test suite. |
| `plots/heatmap_A_absolute_error.png` | FINAL (unchanged) | **FINAL (unchanged)** | *None (leaf/standalone)* | Heatmap of absolute parameter estimation error. |
| `plots/inverse_pipeline_error_heatmaps.png` | FINAL (unchanged) | **FINAL (unchanged)** | `data/run_manifest.json`, `run_manifest.json`, `src/generate_heatmaps.py` | 3x3 absolute median error heatmaps comparing Mode 2, Mode 3, and Mode 3+. |
| `plots/mode2_bias_vs_alpha_sigma0.png` | FINAL (unchanged) | **FINAL (unchanged)** | `src/inverse_mode2.py` | Mode 2 inversion bias vs alpha under zero noise generated by inverse_mode2.py. |
| `plots/mode3_loss_wide_alpha_0.005.png` | FINAL (unchanged) | **FINAL (unchanged)** | *None (leaf/standalone)* | Mode 3 loss landscape for alpha=0.005 demonstrating spurious local minima. |
| `plots/mode3_loss_wide_alpha_0.1.png` | FINAL (unchanged) | **FINAL (unchanged)** | *None (leaf/standalone)* | Mode 3 loss landscape for alpha=0.100. |
| `plots/mode3_loss_wide_alpha_0.5.png` | FINAL (unchanged) | **FINAL (unchanged)** | *None (leaf/standalone)* | Mode 3 loss landscape for alpha=0.500. |
| `plots/mode3_loss_wide_alpha_2.5.png` | FINAL (unchanged) | **FINAL (unchanged)** | *None (leaf/standalone)* | Mode 3 loss landscape for alpha=2.500. |
| `plots/mode3_vs_mode2_ratio_heatmaps.png` | FINAL (unchanged) | **FINAL (unchanged)** | `data/run_manifest.json`, `run_manifest.json`, `src/generate_heatmaps.py` | Error ratio heatmaps (Mode 3 / Mode 2) with [NI] marked cells. |
| `plots/per_timestep_error.png` | FINAL (unchanged) | **FINAL (unchanged)** | `src/eval_timesteps.py` | Error evolution over rollout timesteps generated by src/eval_timesteps.py. |
| `plots/poisson_2d_convergence.png` | FINAL (unchanged) | **FINAL (unchanged)** | `tests/test_poisson_2d.py` | 2D Poisson 5-point stencil second-order convergence plot generated by test suite. |
| `plots/t0_error_experiments.png` | FINAL (unchanged) | **FINAL (unchanged)** | `src/diagnostics_exp.py` | Initial condition t=0 error across ablation experiments. |
| `plots/t0_error_vs_alpha.png` | FINAL (unchanged) | **FINAL (unchanged)** | `src/diagnostics.py` | Initial condition t=0 error vs diffusivity parameter. |

## 3. Disagreements with User Classification

Applying the **HARD DEPENDENCY RULE** (*"If a FINAL script, a test, an audit script, or run_manifest.json uses it, it is FINAL and stays, whatever the table says"*), we identified the following critical disagreements and resolutions:

### 1. `models/pinn_expD.pt` -> **FINAL** (User listed under EXPERIMENTS)
- **Dependency:** `src/study_pinn_inverse.py` (which is the final Task B evaluation script) explicitly loads `models/pinn_expD.pt` on line 55:
  ```python
  pinn_chk_path = os.path.join(base_dir, 'models', 'pinn_expD.pt')
  ```
- **Resolution:** Per hard rule, `models/pinn_expD.pt` MUST stay in `models/` as a FINAL model checkpoint.

### 2. `src/eval_final_all.py` -> **EXPERIMENTS** with Reference Update (User listed under EXPERIMENTS)
- **Dependency:** `src/study_pinn_inverse.py` imports `BoundedReparametrizedPINN` on line 29:
  ```python
  from eval_final_all import BoundedReparametrizedPINN
  ```
- **Resolution:** Moving `eval_final_all.py` to `experiments/` would break `study_pinn_inverse.py` unless the reference is updated. We recommend updating the import in `src/study_pinn_inverse.py` to `from experiments.eval_final_all import BoundedReparametrizedPINN` (or moving `BoundedReparametrizedPINN` to `src/models/pinn.py`).

### 3. `src/data/generate_poisson_dataset.py` -> **ARCHIVE/superseded** (User listed under `src/data/*` as FINAL)
- **Dependency:** It generates the Poisson v1 dataset (`poisson_train.npz`, etc.). Poisson v2 has its own generator `src/data/generate_poisson_dataset_v2.py` which is final.
- **Resolution:** To prevent accidental data contamination, move `generate_poisson_dataset.py` to `archive/superseded/generate_poisson_dataset_v1.py` (or keep in `archive/superseded/generate_poisson_dataset.py`).

### 4. `src/benchmark_timing_honesty.py` Default Checkpoint References
- **Dependency:** Default argument is `fno_path="models/fno2d_poisson.pt"` (v1) and it checks `models/linear_baseline_poisson.npz` (v1).
- **Resolution:** Since `benchmark_timing_honesty.py` is kept as a FINAL script, update default to `"models/fno2d_poisson_v2.pt"` and `"models/linear_baseline_poisson_v2.npz"` during Phase B so it does not rely on archived v1 files.

### 5. `src/audit_poisson.py` Reference to `poisson_eval_results.json`
- **Dependency:** `src/audit_poisson.py` loads `data/poisson_eval_results.json` (v1) and compares against `data/audit_poisson.txt`.
- **Resolution:** When `poisson_eval_results.json` is archived, `src/audit_poisson.py` should point to `archive/superseded/poisson_eval_results.json`, OR `poisson_eval_results.json` must remain in `data/` as historical audit evidence.

## 4. Resolution of ASK Items

### ASK 1: `src/train.py` vs `src/train_pinn.py`
- **`src/train.py` -> FINAL (stays in `src/`):**
  - **Model Produced:** `models/fno2d_heat.pt`.
  - **Usage:** Loaded by `src/inverse_mode3.py`, `src/run_definitive_pipeline.py`, `src/run_hybrid_benchmark.py`, `src/inverse_spline_benchmark.py`, `src/study_anomaly.py`, `src/study_pinn_inverse.py`, and `src/generate_final_pipeline_tables.py`. It is the foundational forward operator model for the entire inverse digital twin.
- **`src/train_pinn.py` -> EXPERIMENTS (`experiments/train_pinn.py`):**
  - **Model Produced:** `models/pinn_heat.pt`.
  - **Usage:** Only evaluated in experiment scripts (`eval_full_rollout.py`, `eval_pinn_timesteps.py`, `eval_summary.py`, `diagnostics.py`). The final Task B Mode 1 PINN inverse pipeline uses `models/pinn_expD.pt` (produced by `train_expD_pinn.py`).

### ASK 2: Two Copies of `run_manifest.json` (`run_manifest.json` vs `data/run_manifest.json`)
- **Code References:** Neither copy is read or written dynamically by Python code (verified by repository-wide AST and regex grep).
- **Content Comparison:**
  - `run_manifest.json` (root) has **7 sections**, including `stage2_poisson` and the complete 6,480-episode anomaly dataset.
  - `data/run_manifest.json` has only **6 sections** (it was generated at the conclusion of Stage 1 heat inversion and lacks `stage2_poisson`).
- **Resolution:** The root copy `run_manifest.json` is the canonical, complete superset. In Phase B, keep `run_manifest.json` at root and move `data/run_manifest.json` to `archive/superseded/run_manifest_older.json` (per "move only" rule).

### ASK 3: Text Files (`brief_text*.txt` and `arch_text*.txt`)
- `brief_text.txt` and `arch_text.txt` are raw UTF-16 files with BOM created during PowerShell CLI extraction.
- `brief_text_utf8.txt` and `arch_text_utf8.txt` are clean UTF-8 transcriptions containing the complete client brief and system architecture text.
- **Resolution:** Move the clean UTF-8 text versions (`brief_text_utf8.txt`, `arch_text_utf8.txt`) to `docs/` alongside the docx files. Move the raw UTF-16 dumps (`brief_text.txt`, `arch_text.txt`) to `archive/scratch/`.

## 5. Scripts That Write into `data/` or `models/` (Future Overwrite Risk Map)

To ensure safe reproduction, the following table lists every kept script and exactly what files it will overwrite if rerun:

| Script | Category | Files Overwritten on Rerun |
| :--- | :--- | :--- |
| `src/train.py` | FINAL | `models/fno2d_heat.pt`, `plots/fno_generalization.png` |
| `src/data/generate_dataset.py` | FINAL | `data/interim/train.npz`, `data/interim/val.npz`, `data/interim/test_interpolation.npz`, `data/interim/test_ood.npz` |
| `src/data/generate_poisson_dataset_v2.py` | FINAL | All `data/poisson_v2_*.npz` files (7 splits + manufactured sanity) |
| `src/data/verify_dataset.py` | FINAL | `plots/alpha_histogram.png` |
| `src/run_definitive_pipeline.py` | FINAL | `data/mode2_pipeline_results_v2.csv`, `data/mode3_pipeline_results_v2.csv` |
| `src/run_hybrid_benchmark.py` | FINAL | `data/mode2_pipeline_results_v2.csv`, `data/mode3_pipeline_results_v2.csv`, `data/mode3plus_hybrid_results.csv` |
| `src/inverse_spline_benchmark.py` | FINAL | `data/spline_pipeline_results.npz` |
| `src/inverse_mode2.py` | FINAL | `plots/mode2_bias_vs_alpha_sigma0.png` |
| `src/inverse_mode3.py` | FINAL | `plots/mode3_spurious_loss_alpha*.png` |
| `src/study_sensor_placement.py` | FINAL | `data/raw/sensor_placement_raw.csv`, `data/sensor_placement_summary.csv` |
| `src/study_pinn_inverse.py` | FINAL | `data/raw/mode1_pinn_raw.csv`, `data/mode1_pinn_summary.csv` |
| `src/study_anomaly.py` | FINAL | `data/raw/anomaly_raw.csv` |
| `src/study_linear_baseline.py` | FINAL | `data/linear_baseline_study.json` |
| `src/train_fno_poisson_v2.py` | FINAL | `models/fno2d_poisson_v2.pt`, `data/fno2d_v2_training_curves.csv`, `data/fno2d_v2_training_summary.json` |
| `src/eval_poisson_v2.py` | FINAL | `models/linear_baseline_poisson_v2.npz`, `data/poisson_v2_eval_results.json`, `data/poisson_v2_benchmark_table.csv` |
| `src/train_pinn_poisson.py` | FINAL | `models/pinn_poisson.pt`, `data/pinn_poisson_summary.json` |
| `src/benchmark_timing_honesty.py` | FINAL | `data/timing_honesty.json` |
| `src/audit_anomaly.py` | FINAL | `data/audit_anomaly.txt`, `data/anomaly_summary.csv` |
| `src/audit_inverse.py` | FINAL | `data/audit_report.txt` |
| `src/audit_pinn_inverse.py` | FINAL | `data/audit_pinn_report.txt` |
| `src/audit_sensor_placement.py` | FINAL | `data/audit_sensor_placement.txt` |
| `src/audit_poisson.py` | FINAL | `data/audit_poisson.txt` |
| `tools/generate_final_pipeline_tables.py` | TOOLS | `data/final_pipeline_tables.pkl` |
| `tools/generate_markdown_tables.py` | TOOLS | `data/mode2_table.md`, `data/mode3_table.md`, `data/mode3plus_table.md` |
| `tools/generate_heatmaps.py` | TOOLS | `plots/inverse_pipeline_error_heatmaps.png`, `plots/mode3_vs_mode2_ratio_heatmaps.png` |
| `tools/export_csv.py` | TOOLS | `data/mode2_pipeline_results.csv`, `data/mode3_pipeline_results.csv` |
| `experiments/train_expD_pinn.py` | EXPERIMENTS | `models/pinn_expD.pt` |
| `experiments/train_pinn.py` | EXPERIMENTS | `models/pinn_heat.pt` |
| `experiments/train_pinn_expA.py` | EXPERIMENTS | `models/pinn_expA.pt` |
| `experiments/train_pinn_expB.py` | EXPERIMENTS | `models/pinn_expB.pt` |
| `experiments/train_expC.py` | EXPERIMENTS | `models/fno2d_expC.pt` |
| `experiments/train_expD_fno.py` | EXPERIMENTS | `models/fno2d_expD.pt` |
| `experiments/eval_full_rollout.py` | EXPERIMENTS | `plots/full_rollout_abs_error_comparison.png` |
| `experiments/eval_timesteps.py` | EXPERIMENTS | `plots/per_timestep_error.png` |
| `tests/test_heat_1d.py` | TESTS | `plots/heat_1d_convergence.png` |
| `tests/test_poisson_2d.py` | TESTS | `plots/poisson_2d_convergence.png` |

## 6. Planned Batch Moves for Phase B

When approved, moves will be performed in atomic batches with `git mv`, followed by `python -m compileall` and `pytest tests` validation after each batch:

- **Batch 1 (Documentation & Root Captures):**
  - `06_Hamna_Neural_PDE_Digital_Twin.docx` -> `docs/`
  - `Implementation Plan & System Architectur.docx` -> `docs/`
  - `brief_text_utf8.txt` -> `docs/`
  - `arch_text_utf8.txt` -> `docs/`
  - `brief_text.txt` -> `archive/scratch/`
  - `arch_text.txt` -> `archive/scratch/`
  - `mode2_results_v2.txt` -> `data/mode2_results_v2.txt`
  - `mode3_results_v2.txt` -> `data/mode3_results_v2.txt`
  - `data/run_manifest.json` -> `archive/superseded/data_run_manifest_older.json`
  - `inverse_mode2_old.py` -> `archive/superseded/`

- **Batch 2 (Report Tools):**
  - `src/generate_final_pipeline_tables.py` -> `tools/`
  - `src/generate_markdown_tables.py` -> `tools/`
  - `src/generate_heatmaps.py` -> `tools/`
  - `src/export_csv.py` -> `tools/`

- **Batch 3 (Experiments Code & Models):**
  - Create `experiments/__init__.py` and `experiments/README.md`
  - `src/train_pinn_expA.py` -> `experiments/`
  - `src/train_pinn_expB.py` -> `experiments/`
  - `src/train_expC.py` -> `experiments/`
  - `src/train_expD_fno.py` -> `experiments/`
  - `src/train_expD_pinn.py` -> `experiments/`
  - `src/train_pinn.py` -> `experiments/`
  - `src/eval_final_all.py` -> `experiments/`
  - `src/eval_fno_compare.py` -> `experiments/`
  - `src/eval_fno_t1_99.py` -> `experiments/`
  - `src/eval_full_rollout.py` -> `experiments/`
  - `src/eval_pinn_timesteps.py` -> `experiments/`
  - `src/eval_summary.py` -> `experiments/`
  - `src/eval_timesteps.py` -> `experiments/`
  - `src/diagnostics.py` -> `experiments/`
  - `src/diagnostics_exp.py` -> `experiments/`
  - `models/pinn_expA.pt` -> `experiments/models/`
  - `models/pinn_expB.pt` -> `experiments/models/`
  - `models/fno2d_expC.pt` -> `experiments/models/`
  - `models/fno2d_expD.pt` -> `experiments/models/`
  - `models/pinn_heat.pt` -> `experiments/models/`
  - *Update import in `src/study_pinn_inverse.py`:* `from experiments.eval_final_all import BoundedReparametrizedPINN`

- **Batch 4 (Archive Superseded Poisson v1 Code, Models & Data):**
  - `src/train_fno_poisson.py` -> `archive/superseded/`
  - `src/eval_poisson_all.py` -> `archive/superseded/`
  - `src/data/generate_poisson_dataset.py` -> `archive/superseded/`
  - `models/fno2d_poisson.pt` -> `archive/superseded/`
  - `models/linear_baseline_poisson.npz` -> `archive/superseded/`
  - `data/poisson_train.npz` -> `archive/superseded/`
  - `data/poisson_val.npz` -> `archive/superseded/`
  - `data/poisson_test_interp.npz` -> `archive/superseded/`
  - `data/poisson_test_ood_boundary.npz` -> `archive/superseded/`
  - `data/poisson_test_ood_count.npz` -> `archive/superseded/`
  - `data/poisson_test_ood_narrow.npz` -> `archive/superseded/`
  - `data/poisson_manufactured_sanity.npz` -> `archive/superseded/`
  - `data/poisson_benchmark_table.csv` -> `archive/superseded/`
  - `data/poisson_eval_results.json` -> `archive/superseded/`
  - `data/fno2d_training_log.csv` -> `archive/superseded/`

## 7. Awaiting User Approval

**PHASE A COMPLETE.** No moves have been made. Review the classification, disagreements, and risk map above. Reply with **`approved`** to begin Phase B execution.
