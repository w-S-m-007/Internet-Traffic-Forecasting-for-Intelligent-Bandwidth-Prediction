"""Export validated saved experiment results for the browser-only Pages dashboard."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from dashboard.artifacts import MODEL_LABELS, load_allocation, load_forecasts, model_forecasts

ROOT = Path(__file__).resolve().parents[1]


def write_json(path, value):
    path.write_text(json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n', encoding='utf-8')


def main():
    output = ROOT / 'web/data'
    output.mkdir(parents=True, exist_ok=True)
    metadata = {'schema_version': 1, 'exported_at_utc': datetime.now(timezone.utc).isoformat(),
                'models': MODEL_LABELS, 'horizons': [10, 30, 60], 'metrics': [],
                'dataset': 'CESNET-TimeSeries24 v1', 'institution': 0, 'interval_seconds': 600,
                'dataset_url': 'https://doi.org/10.5281/zenodo.13382427', 'license': 'CC BY 4.0',
                'allocation_defaults': None, 'allocation_metrics': None}
    source_hashes = {}
    for horizon in metadata['horizons']:
        artifacts = load_forecasts(ROOT, horizon)
        if len(artifacts.metrics) != 10 or set(artifacts.configs) != set(MODEL_LABELS):
            raise ValueError(f'Expected all five complete predictors at {horizon} minutes')
        metadata['metrics'].extend(artifacts.metrics.to_dict('records'))
        horizon_data = {}
        for split in ('validation', 'test'):
            reference = model_forecasts(artifacts, 'persistence', split)
            horizon_data[split] = {
                'timestamps': (reference['target_completion_utc'].astype('int64') // 1_000_000).tolist(),
                'actual': reference['actual_mbps'].tolist(),
                'predictions': {model: model_forecasts(artifacts, model, split)['predicted_mbps'].tolist()
                                for model in MODEL_LABELS}}
            # Compare exact UTC values rather than assuming a pandas internal timestamp resolution.
            horizon_data[split]['timestamps'] = [int(stamp.timestamp() * 1000) for stamp in reference['target_completion_utc']]
        write_json(output / f'horizon-{horizon}.json', horizon_data)
        if horizon == 10:
            allocation = load_allocation(ROOT, artifacts)
            if allocation is None or len(allocation['selected_defaults']) != 5:
                raise ValueError('Complete five-policy allocation experiment required')
            metadata['allocation_defaults'] = allocation['selected_defaults']
            import csv
            with (ROOT / 'results/allocation/10min/metrics.csv').open(newline='') as handle:
                metadata['allocation_metrics'] = [{k: float(v) if k not in ('policy', 'split') else v for k, v in row.items()}
                                                  for row in csv.DictReader(handle)]
        for source in ('baselines', 'lstm', 'gru', 'transformer'):
            for name in ('metrics.csv', 'predictions.csv', 'run_config.json'):
                path = ROOT / f'results/{source}/{horizon}min/{name}'
                source_hashes[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    write_json(output / 'metadata.json', metadata)
    exported = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in output.glob('*.json') if path.name != 'manifest.json'}
    write_json(output / 'manifest.json', {'schema_version': 1, 'files': exported, 'source_sha256': source_hashes})
    print(f'Exported verified results for all three horizons to {output}')


if __name__ == '__main__':
    main()
