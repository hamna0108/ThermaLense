# Archive Index

Traceability register for all superseded, failed, and scratch artifacts moved out of the active codebase.

| Item | Category | Why Moved | What Replaced It | Evidence File |
| :--- | :--- | :--- | :--- | :--- |
| `inverse_mode2_old.py` | superseded | Initial non-vectorized implementation of Mode 2 spline solver. | `src/inverse_mode2.py` | `data/mode2_pipeline_results_v2.csv` |
| `data_run_manifest_older.json` | superseded | Older 6-section snapshot of the manifest created before Stage 2 Poisson. | `run_manifest.json` (root) | `run_manifest.json` |
| `arch_text.txt` | scratch | Raw UTF-16 CLI text dump with BOM from Word document extraction. | `docs/arch_text_utf8.txt` | `docs/arch_text_utf8.txt` |
| `brief_text.txt` | scratch | Raw UTF-16 CLI text dump with BOM from client brief extraction. | `docs/brief_text_utf8.txt` | `docs/brief_text_utf8.txt` |
| `train_fno_poisson.py` | superseded | Poisson Stage 2 v1 training script; lacked explicit zero-boundary hard masking. | `src/train_fno_poisson_v2.py` | `data/poisson_v2_benchmark_table.csv` |
| `eval_poisson_all.py` | superseded | Poisson Stage 2 v1 evaluation script across 6 splits. | `src/eval_poisson_v2.py` | `data/poisson_v2_eval_results.json` |
| `generate_poisson_dataset.py` | superseded | Poisson Stage 2 v1 dataset generator; seed range overlapped with heat studies. | `src/data/generate_poisson_dataset_v2.py` | `tests/test_poisson_stage2.py` |
| `fno2d_poisson.pt` | superseded | Trained FNO checkpoint from Poisson v1 (without hard boundary constraint). | `models/fno2d_poisson_v2.pt` | `data/poisson_v2_eval_results.json` |
| `linear_baseline_poisson.npz` | superseded | Dual ridge regression parameters fitted on Poisson v1. | `models/linear_baseline_poisson_v2.npz` | `data/poisson_v2_eval_results.json` |
| `poisson_train.npz` | superseded | Poisson v1 training split (seeds 100000-100999). | `data/poisson_v2_train.npz` | `data/audit_poisson.txt` |
| `poisson_val.npz` | superseded | Poisson v1 validation split (seeds 200000-200099). | `data/poisson_v2_val.npz` | `data/audit_poisson.txt` |
| `poisson_test_interp.npz` | superseded | Poisson v1 interpolation test split. | `data/poisson_v2_test_interp.npz` | `data/audit_poisson.txt` |
| `poisson_test_ood_boundary.npz` | superseded | Poisson v1 boundary OOD test split. | `data/poisson_v2_test_ood_boundary.npz` | `data/audit_poisson.txt` |
| `poisson_test_ood_count.npz` | superseded | Poisson v1 source count OOD test split. | `data/poisson_v2_test_ood_count.npz` | `data/audit_poisson.txt` |
| `poisson_test_ood_narrow.npz` | superseded | Poisson v1 narrow source width OOD test split. | `data/poisson_v2_test_ood_narrow.npz` | `data/audit_poisson.txt` |
| `poisson_manufactured_sanity.npz` | superseded | Poisson v1 manufactured solution sanity test sample. | `data/poisson_v2_manufactured_sanity.npz` | `data/audit_poisson.txt` |
| `poisson_benchmark_table.csv` | superseded | Summary benchmark table for Poisson v1 models. | `data/poisson_v2_benchmark_table.csv` | `data/audit_poisson.txt` |
| `poisson_eval_results.json` | superseded | Detailed metrics across all splits for Poisson v1; kept for before/after comparison. | `data/poisson_v2_eval_results.json` | `data/audit_poisson.txt` |
| `fno2d_training_log.csv` | superseded | 15-epoch training loss curve log for Poisson v1 FNO run. | `data/fno2d_v2_training_curves.csv` | `data/fno2d_v2_training_summary.json` |
