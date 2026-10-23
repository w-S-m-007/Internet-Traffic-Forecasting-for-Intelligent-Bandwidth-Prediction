"""Build combined result tables and scientific plots from saved experiment CSVs."""
import csv
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MODELS = [('persistence','Persistence'), ('moving_average_4','Moving average'),
          ('lstm','LSTM'), ('gru','GRU'), ('transformer','Transformer')]


def main():
    combined = []
    for horizon in (10, 30, 60):
        for source in ('baselines','lstm','gru','transformer'):
            with (ROOT / f'results/{source}/{horizon}min/metrics.csv').open(newline='') as handle:
                combined.extend(csv.DictReader(handle))
    if len(combined) != 30:
        raise ValueError('Expected 30 model/split/horizon metric rows')
    output = ROOT / 'results/comparison'
    output.mkdir(parents=True, exist_ok=True)
    with (output / 'forecast_metrics_10_30_60min.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(combined[0]))
        writer.writeheader()
        writer.writerows(combined)
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.8))
    for ax, metric, label in zip(axes, ('mae_mbps','rmse_mbps','mape_pct'), ('MAE (nominal Mbps)','RMSE (nominal Mbps)','MAPE (%)')):
        for i, (name, title) in enumerate(MODELS):
            values = [float(next(row for row in combined if row['model'] == name and row['split'] == 'test' and int(row['horizon_minutes']) == h)[metric]) for h in (10,30,60)]
            ax.bar(np.arange(3) + (i - 2) * .14, values, width=.14, label=title)
        ax.set(xticks=[0,1,2], xticklabels=['10 min','30 min','60 min'], xlabel='Forecast horizon', ylabel=label)
        ax.grid(axis='y', alpha=.2)
        ax.set_axisbelow(True)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', ncol=5, bbox_to_anchor=(.5,.94), frameon=False)
    fig.suptitle('Test forecasting comparison | fixed seed 42', y=.995)
    counts = [next(row['n_samples'] for row in combined if row['split']=='test' and int(row['horizon_minutes'])==h) for h in (10,30,60)]
    fig.text(.5,.015, f'Test targets: 10 min {counts[0]}; 30 min {counts[1]}; 60 min {counts[2]}. Eligible target sets differ by horizon.', ha='center', fontsize=9)
    fig.tight_layout(rect=(0,.06,1,.87))
    fig.savefig(output / 'forecast_test_10_30_60min.png', dpi=160)
    plt.close(fig)
    print(f'Combined table and figure saved in {output}')


if __name__ == '__main__':
    main()
