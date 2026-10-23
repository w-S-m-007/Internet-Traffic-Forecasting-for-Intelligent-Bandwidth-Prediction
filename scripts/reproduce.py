"""Run the complete experiment, preserving older outputs before a fresh run."""
import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(module, *args):
    command = [sys.executable, '-m', module, *args]
    print('Running ' + ' '.join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', choices=('auto','cpu','cuda'), default='auto')
    parser.add_argument('--fresh', action='store_true', help='Archive generated preparation/results and regenerate all experiments')
    parser.add_argument('--download', action='store_true', help='Download/check the original archives if the raw sample is absent')
    args = parser.parse_args()
    raw = ROOT / 'data/raw/cesnet/sample'
    if not all((raw / name).is_file() for name in ('institution_0.csv','times_10_minutes.csv')):
        if not args.download:
            parser.error('Raw CESNET sample absent. Use --download to obtain checksum-verified source archives.')
        run('data_processing.download_data')
    if args.fresh:
        backup = ROOT / 'archive' / ('experiment_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        for relative in ('data/prepared', 'results'):
            source = (ROOT / relative).resolve()
            target = (backup / relative).resolve()
            if not source.is_relative_to(ROOT.resolve()) or not target.is_relative_to((ROOT / 'archive').resolve()):
                raise ValueError('Backup paths escaped the project')
            if source.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(target))
        print(f'Previous generated outputs preserved in {backup}', flush=True)
    prepared = ROOT / 'data/prepared'
    if not (prepared / 'preparation_config.json').exists():
        if prepared.exists() and any(prepared.iterdir()):
            parser.error('Partial preparation exists; use --fresh to archive it first.')
        run('data_processing.prepare_dataset')
    for horizon in (10, 30, 60):
        for model in ('baselines','lstm','gru','transformer'):
            output = ROOT / f'results/{model}/{horizon}min'
            names = ['metrics.csv','predictions.csv','run_config.json']
            if model != 'baselines':
                names += ['best_model.pt','scalers.json','training_history.csv']
            if all((output / name).is_file() for name in names):
                print(f'Reusing {model}/{horizon}min; final verification checks provenance.', flush=True)
                continue
            if output.exists() and any(output.iterdir()):
                parser.error(f'Partial {output} exists; use --fresh to preserve and regenerate it.')
            module = 'experiments.evaluate_baselines' if model == 'baselines' else f'experiments.train_{model}'
            options = ['--horizon', str(horizon)]
            if model != 'baselines':
                options += ['--device', args.device]
            run(module, *options)
    run('experiments.evaluate_allocation')
    run('scripts.summarize_results')
    run('scripts.verify_results', '--checkpoints', '--device', args.device)
    run('unittest', 'discover', '-s', 'tests', '-v')
    print('Complete. Start the dashboard: python -m streamlit run dashboard/app.py', flush=True)


if __name__ == '__main__':
    main()
