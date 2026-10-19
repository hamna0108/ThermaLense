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
| `fno2d_training_log.csv` | superseded | 15-epoch training loss curve log for Poisson v1 FNO run. | `data/results/fno2d_v2_training_curves.csv` | `data/results/fno2d_v2_training_summary.json` |

---

## Dropped Methodologies & Conceptual Baselines (Decided by Evidence)

Approaches explored, empirically evaluated, and retired based on rigorous statistical and numerical criteria:

| Approach / Methodology | Reason Dropped | Replacement / Resolution | Status | Evidence File |
| :--- | :--- | :--- | :--- | :--- |
| **C-First Anomaly Cascade** | Evaluating physical change-points (Class C) before sensor faults (Class F) caused sensor drift/bias to leak into Class C ($F \to C$ false positive rate $>25\%$), triggering false alarms for physical degradation when only a sensor failed. | F-first model-selection cascade with leave-one-out (LOO) cross-sensor validation and $3\sigma$ residual filtering. | **Decided by evidence** | `data/audits/audit_anomaly.txt` (Sections 3 & 4), `data/results/anomaly_summary.csv` |
| **Stuck-at-Last-Good Sensor Fault Heuristic** | Sensor freezing at last valid reading was initially treated as drift anomaly; dynamic physical transients caused rapid divergence that mimicked system-level fault if analyzed via scalar variance. | Spatial isolation via LOO residual ratio: true physical jumps affect all spatial sensors coherently, whereas stuck reading is isolated to a single channel ($k=1$). | **Decided by evidence** | `data/audits/audit_anomaly.txt` (Section 4 fault breakdown), `data/raw/anomaly_raw.csv` |
| **Oracle-Grid GLR Testing** | Evaluating change-point GLR only at synthetic training grid times ($t_c \in \{0.2, 0.4, 0.6, 0.8\}$) masked severe discretization bias and gave an artificial grid-matching advantage. | Continuous-time 2D GLR test evaluated on off-grid physical change-points ($t_c \in \{0.15, 0.35, 0.70\}$, $m \in \{0.7, 1.5, 3.0\}$). | **Decided by evidence** | `data/audits/audit_anomaly.txt` (Section 6), `data/raw/anomaly_raw.csv` |
| **Unanchored Joint-Estimation GLR Detector** | At high noise ($\sigma = 0.05$), estimating baseline diffusion $\alpha_0$ simultaneously from the jump window soaked up the residual drop, collapsing Class C recall from $86\%$ to $37\%$. | Baseline-informed detector anchoring $\alpha_0$ using pre-event healthy observation window; surged recall back to $58\text{--}70\%$, recovering the gap to Neyman-Pearson Oracle power. | **Decided by evidence** | `data/audits/audit_anomaly.txt` (Sections 3 & 5), `data/results/anomaly_summary.csv` |
| **Poisson v1 FNO Formulation** | V1 model lacked hard boundary constraints, exhibiting $>10^{-2}$ unphysical boundary leakage on $\partial\Omega$; dataset seeds overlapped with earlier heat experiments. | Poisson v2 with hard zero-boundary projection ($u = 0$ on $\partial\Omega$), strictly disjoint seed ranges (100000..600199), and verified second-order convergence ($O(h^2)$). | **Decided by evidence** | `data/audits/audit_poisson.txt` (Sections 1–4), `data/results/poisson_v2_benchmark_table.csv` |
| **Mode 1: Direct PINN Inversion** | Inverting $\alpha$ via autograd through a frozen PINN surrogate degraded catastrophically out-of-range ($\alpha = 2.5$, $16.8\text{--}28.0\%$ error; $3.3\times\text{--}20.2\times$ worse than classical solver) while running $4\times$ slower (~$7.0$ ms vs ~$1.8$ ms). | Retired from production inverse pipeline; Mode 2 (Crank-Nicolson) and Mode 3+ (FNO + Solver Polish) selected for gold-standard and deployable real-time use. | **Decided by evidence** | `data/audits/audit_pinn_report.txt` (Sections 3–5), `data/results/mode1_pinn_summary.csv` |
| **Uniform Temporal Sensor Placement** | Uniform temporal spacing wastes sensor budget on rapidly decaying diffusion processes ($\alpha \ge 1.0$), failing to sample informative early-time transients. | Logarithmic temporal distribution and two-stage adaptive placement (preliminary probe + Fisher-information-weighted clustering), achieving spread within $1.1\times$ of CRB. | **Decided by evidence** | `data/audits/audit_sensor_placement.txt` (Sections 2 & 7), `data/results/sensor_placement_summary.csv` |

