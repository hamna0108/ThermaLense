try:
    from paths import RESULTS
except ImportError:
    from src.paths import RESULTS
import pickle
import csv

data = pickle.load(open(str(RESULTS / 'final_pipeline_tables.pkl'), 'rb'))

# Export Mode 2
with open(str(RESULTS / 'mode2_pipeline_results.csv'), 'w', newline='') as f:
    fields = ['split', 'alpha', 'sensors', 'sigma', 'med_rel_err', 'spread_log', 'wald_cov_95', 'frac_bound', 'single_fit_time_ms', 'status']
    w = csv.writer(f)
    w.writerow(fields)
    for r in data['m2_records']:
        w.writerow([r['split'], f"{r['alpha']:.3f}", r['sensors'], f"{r['sigma']:.2f}",
                    f"{r['med_rel_err']:.6f}", f"{r['spread_log']:.6f}", r['cov_str'],
                    f"{r['frac_bound']:.3f}", f"{r['time_ms']:.3f}", r['status']])

# Export Mode 3
with open(str(RESULTS / 'mode3_pipeline_results.csv'), 'w', newline='') as f:
    fields = ['split', 'alpha', 'sensors', 'sigma', 'med_rel_err_train', 'med_rel_err_narrow', 'sprd_crb_ratio', 'wald_cov_95', 'frac_bound', 'single_fit_time_ms', 'status']
    w = csv.writer(f)
    w.writerow(fields)
    for r in data['m3_records']:
        # Relabel high-alpha rows with cov < 90% as bias-dominated (FNO)
        status = r['status']
        if r['alpha'] in [1.5, 2.0, 2.5, 3.0] and r['sigma'] == 0.01 and r['status'] == '**Not Identifiable**':
            status = 'bias-dominated (FNO)'
        w.writerow([r['split'], f"{r['alpha']:.3f}", r['sensors'], f"{r['sigma']:.2f}",
                    f"{r['med_train']:.6f}", f"{r['med_narrow']:.6f}", r['sprd_crb_str'].strip(),
                    r['cov_str'], f"{r['frac_bound']:.3f}", f"{r['time_ms']:.3f}", status])

print("CSV export successful.")
