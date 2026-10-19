import csv

def generate_markdown_tables():
    # Read Mode 2
    with open('data/mode2_pipeline_results_v2.csv', 'r') as f:
        reader = csv.DictReader(f)
        m2_rows = list(reader)

    # Read Mode 3
    with open('data/mode3_pipeline_results_v2.csv', 'r') as f:
        reader = csv.DictReader(f)
        m3_rows = list(reader)

    # Read Mode 3+
    with open('data/mode3plus_hybrid_results.csv', 'r') as f:
        reader = csv.DictReader(f)
        m3p_rows = list(reader)

    print(f"Total Mode 2 rows loaded from CSV: {len(m2_rows)}")
    print(f"Total Mode 3 rows loaded from CSV: {len(m3_rows)}")
    print(f"Total Mode 3+ rows loaded from CSV: {len(m3p_rows)}")

    # Generate Mode 2 Markdown Table
    m2_md = []
    m2_md.append("| Split | $\\alpha_{\\text{true}}$ | Sensors | $\\sigma$ | MedRelErr | Spread($\\log_{10}\\alpha$) | Wald Cov 95% | Bias-Corr Cov | FracBound | Fit Time | Status |")
    m2_md.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |")
    for r in m2_rows:
        status_fmt = f"**{r['status']}**" if r['status'] in ['Not Identifiable', 'bias-dominated'] else r['status']
        line = f"| {r['split']} | {float(r['alpha']):.3f} | {int(r['sensors'])} | {float(r['sigma']):.2f} | {float(r['med_rel_err']):.4f} | {float(r['spread_log']):.4f} | {r['wald_cov_95']} | {r['deploy_cov_95']} | {float(r['frac_bound']):.2f} | {float(r['single_fit_time_ms']):.2f} ms | {status_fmt} |"
        m2_md.append(line)

    # Generate Mode 3 Markdown Table
    m3_md = []
    m3_md.append("| Split | $\\alpha_{\\text{true}}$ | Sensors | $\\sigma$ | MedRelErr (Narrow $\\le 4$) | MedRelErr (Wide $\\le 10$) | Sprd/CRB | Wald Cov 95% | Bias-Corr Cov | FracBound | Fit Time | Status |")
    m3_md.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |")
    for r in m3_rows:
        status_fmt = f"**{r['status']}**" if any(k in r['status'] for k in ['Not Identifiable', 'bias-dominated', 'bias-uncorrected']) else r['status']
        try:
            med_n_str = f"{float(r['med_narrow']):.4f}"
        except ValueError:
            med_n_str = r['med_narrow']
        line = f"| {r['split']} | {float(r['alpha']):.3f} | {int(r['sensors'])} | {float(r['sigma']):.2f} | {med_n_str} | {float(r['med_wide']):.4f} | {r['sprd_crb']} | {r['wald_cov_95']} | {r['deploy_cov_95']} | {float(r['frac_bound']):.2f} | {float(r['single_fit_time_ms']):.2f} ms | {status_fmt} |"
        m3_md.append(line)

    # Generate Mode 3+ Markdown Table
    m3p_md = []
    m3p_md.append("| Split | $\\alpha_{\\text{true}}$ | Sensors | $\\sigma$ | MedRelErr | Spread($\\log_{10}\\alpha$) | Sprd/CRB | Wald Cov 95% | Bias-Corr Cov | FracBound | Fit Time | Status |")
    m3p_md.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |")
    for r in m3p_rows:
        status_fmt = f"**{r['status']}**" if 'Not Identifiable' in r['status'] or 'bias-dominated' in r['status'] else r['status']
        line = f"| {r['split']} | {float(r['alpha']):.3f} | {int(r['sensors'])} | {float(r['sigma']):.2f} | {float(r['med_rel_err']):.4f} | {float(r['spread_log']):.4f} | {r['sprd_crb']} | {r['wald_cov_95']} | {r['deploy_cov_95']} | {float(r['frac_bound']):.2f} | {float(r['single_fit_time_ms']):.2f} ms | {status_fmt} |"
        m3p_md.append(line)

    with open('data/mode2_table.md', 'w', encoding='utf-8') as f:
        f.write('\n'.join(m2_md))

    with open('data/mode3_table.md', 'w', encoding='utf-8') as f:
        f.write('\n'.join(m3_md))

    with open('data/mode3plus_table.md', 'w', encoding='utf-8') as f:
        f.write('\n'.join(m3p_md))

    print("Markdown tables written to data/mode2_table.md, data/mode3_table.md, and data/mode3plus_table.md.")

if __name__ == '__main__':
    generate_markdown_tables()
