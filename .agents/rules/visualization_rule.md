---
name: Save Visualizations to Plots Directory
description: Ensures all generated visualizations and plots are explicitly saved to the 'plots/' directory.
---

# Visualization Rule
Always explicitly save generated visualizations (such as Matplotlib plots) to the `plots/` directory as high-resolution PNG files before showing or closing them. 
For example, use `os.makedirs('plots', exist_ok=True)` and `plt.savefig(os.path.join('plots', '<filename>.png'), dpi=300)` before `plt.show()`.

Additionally, make sure that tests or analysis scripts that generate numerical data explicitly print the key metrics (like max error, L2 error) so they are visible even when graphical outputs are suppressed in environments like pytest.
