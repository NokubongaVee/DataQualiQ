"""Generate publication-ready standalone plots from completed measured results."""
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(os.environ['TEMP']) / 'DataQualiQ-experiment-plots'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root = Path(__file__).resolve().parents[2] / 'docs/phase16'
report = json.loads((root / 'experiment_results.json').read_text())
if not report.get('complete'): raise ValueError('Plot only completed experiment results')
output = root / 'plots'; output.mkdir(exist_ok=True)
plt.rcParams.update({'font.size': 11, 'axes.spines.top': False, 'axes.spines.right': False, 'svg.fonttype': 'none'})
baseline = report['conditions'][0]
styles = [('numeric_missing', 'Numeric missingness', '#2274a5', 'o'), ('categorical_missing', 'Categorical missingness', '#e07a35', 's'), ('representation', 'Safe representation changes', '#238b68', '^')]
for key, title, ylabel in [('quality_score', 'Data-quality score vs degradation', 'Heuristic quality score (0-100)'), ('accuracy', 'Accuracy vs degradation', 'Accuracy (%)'), ('recall', 'Recall vs degradation', 'Recall for Malicious class (%)'), ('f1', 'F1-score vs degradation', 'F1-score (%)'), ('false_negatives', 'Missed attacks vs degradation', 'False negatives (records)')]:
    figure, axes = plt.subplots(figsize=(8, 5.1), layout='constrained')
    for kind, label, color, marker in styles:
        items = [baseline] + [item for item in report['conditions'] if item['condition'] == kind]
        factor = 100 if key in ['accuracy', 'recall', 'f1'] else 1
        axes.plot([item['degradation_percent'] for item in items], [item[key] * factor for item in items], label=label, color=color, marker=marker, linewidth=2, markersize=6)
    axes.set_title(title, loc='left', fontweight='bold')
    axes.set_xlabel('Affected eligible predictor cells in declared group (%)')
    axes.set_ylabel(ylabel); axes.set_xticks([0,5,10,20]); axes.grid(axis='y', alpha=.22)
    if key == 'quality_score': axes.set_ylim(-2,102)
    if key == 'false_negatives': axes.set_ylim(bottom=0)
    axes.legend(loc='best', frameon=False, fontsize=10)
    figure.savefig(output / (key + '.png'), dpi=220)
    figure.savefig(output / (key + '.svg'))
    plt.close(figure)
print('Saved 5 plots in PNG and SVG; no values synthesized.')
