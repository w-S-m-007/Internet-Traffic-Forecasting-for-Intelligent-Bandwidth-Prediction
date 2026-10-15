"""Shared neural training: select by validation, then evaluate once."""

import argparse
import csv
import hashlib
import json
import os
import platform
import random
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset

from experiments.evaluate_baselines import inference_ms, plot_prefix
from experiments.forecast_metrics import forecast_metrics
from models.lstm_model import TrafficLSTM
from models.gru_model import TrafficGRU
from models.transformer_model import TrafficTransformer


def predict(model, features, device, batch_size=64):
    model.eval()
    parts = []
    with torch.inference_mode():
        for start in range(0, len(features), batch_size):
            parts.append(model(features[start:start + batch_size].to(device)).cpu().numpy())
    return np.concatenate(parts)


def validation_mse(model, features, targets, device):
    predicted = predict(model, features, device)
    return float(np.mean(np.square(predicted.astype(float) - targets.numpy())))


def main(model_name='lstm'):
    model_types = {'lstm': TrafficLSTM, 'gru': TrafficGRU, 'transformer': TrafficTransformer}
    if model_name not in model_types:
        raise ValueError('Expected lstm, gru or transformer')
    parser = argparse.ArgumentParser(description=f'Train {model_name.upper()} on saved windows')
    parser.add_argument("--horizon", type=int, choices=[10, 30, 60], default=10)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    args = parser.parse_args()
    seed, batch_size, max_epochs, patience = 42, 64, 30, 5
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.set_num_threads(1)
    if model_name == "transformer":
        # Keep evaluation on the same attention implementation as training.
        torch.backends.mha.set_fastpath_enabled(False)
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable; use --device cpu or install a CUDA build")
    device = torch.device("cuda" if args.device == "auto" and torch.cuda.is_available()
                          else "cpu" if args.device == "auto" else args.device)
    project = Path(__file__).resolve().parents[1]
    prepared = project / "data/prepared"
    paths = [prepared / f"windows_{args.horizon}min.npz", prepared / f"windows_{args.horizon}min.csv",
             prepared / f"scalers_{args.horizon}min.json", prepared / "preparation_config.json"]
    if not all(path.exists() for path in paths):
        raise FileNotFoundError("Run python -m data_processing.prepare_dataset first")
    with np.load(paths[0], allow_pickle=False) as artifact:
        x, y = artifact["X"].copy(), artifact["y"].copy()
        actual, splits = artifact["target_mbps"].copy(), artifact["split"].copy()
    with paths[1].open(newline="", encoding="utf-8-sig") as handle:
        metadata = list(csv.DictReader(handle))
    scalers = json.loads(paths[2].read_text())
    preparation = json.loads(paths[3].read_text())
    if x.shape != (len(y), 18, len(preparation["features"])) or len(metadata) != len(y):
        raise ValueError("Prepared feature shapes or metadata do not align")
    if not np.isfinite(x).all() or not np.isfinite(y).all() or not np.isfinite(actual).all():
        raise ValueError("Prepared arrays contain nonfinite values")
    names = {0: "train", 1: "validation", 2: "test"}
    if any(int(code) not in names or row["split"] != names[int(code)]
           for row, code in zip(metadata, splits)):
        raise ValueError("Split metadata mismatch")
    tensors = {code: (torch.from_numpy(x[splits == code]), torch.from_numpy(y[splits == code]))
               for code in names}
    if any(not len(features) for features, _ in tensors.values()):
        raise ValueError("All three splits must be nonempty")
    source_hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    comparison_folders = [project / "results/baselines" / f"{args.horizon}min"]
    if model_name in ("gru", "transformer"):
        comparison_folders.append(project / "results/lstm" / f"{args.horizon}min")
    if model_name == "transformer":
        comparison_folders.append(project / "results/gru" / f"{args.horizon}min")
    # Check comparison prerequisites before spending time on training.
    for folder in comparison_folders:
        if (folder / "run_config.json").exists():
            if not all((folder / name).is_file() for name in ("metrics.csv", "predictions.csv")):
                raise FileNotFoundError(f"Incomplete comparison artifacts in {folder}")
            saved = json.loads((folder / "run_config.json").read_text())
            if saved["horizon_minutes"] != args.horizon or any(
                    source_hashes.get(name) != digest for name, digest in saved["artifact_sha256"].items()):
                raise ValueError(f"Comparison preparation differs in {folder}; regenerate matching forecasts")
    output = project / "results" / model_name / f"{args.horizon}min"
    output.mkdir(parents=True, exist_ok=True)
    model = model_types[model_name](input_features=x.shape[-1]).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=.001)
    generator = torch.Generator().manual_seed(seed)
    train_loader = DataLoader(TensorDataset(*tensors[0]), batch_size=batch_size,
                              shuffle=True, generator=generator, num_workers=0,
                              pin_memory=device.type == "cuda")
    best_loss, best_epoch, stale = float("inf"), 0, 0
    history = []
    print(f"Device: {device}; {torch.cuda.get_device_name(0) if device.type == 'cuda' else 'CPU'}", flush=True)
    print(f"Parameters: {sum(parameter.numel() for parameter in model.parameters())}; seed={seed}", flush=True)
    if device.type == "cuda":
        torch.cuda.synchronize()
    training_start = perf_counter()
    for epoch in range(1, max_epochs + 1):
        epoch_start = perf_counter()
        model.train()
        total_loss, observations = 0., 0
        for features, targets in train_loader:
            features, targets = features.to(device), targets.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = torch.nn.functional.mse_loss(model(features), targets)
            if not torch.isfinite(loss):
                raise RuntimeError("Training loss became nonfinite")
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * len(features)
            observations += len(features)
        validation_loss = validation_mse(model, *tensors[1], device)
        if not np.isfinite(validation_loss):
            raise RuntimeError("Validation loss became nonfinite")
        improved = validation_loss < best_loss
        if improved:
            best_loss, best_epoch, stale = validation_loss, epoch, 0
            torch.save({key: value.detach().cpu() for key, value in model.state_dict().items()}, output / "best_model.pt")
        else:
            stale += 1
        history.append({"epoch": epoch, "train_scaled_mse": total_loss / observations,
                        "validation_scaled_mse": validation_loss,
                        "epoch_time_s": perf_counter() - epoch_start, "new_best": int(improved)})
        print(f"Epoch {epoch}: train MSE={total_loss / observations:.6f}; "
              f"validation MSE={validation_loss:.6f}; best={best_epoch}", flush=True)
        if stale >= patience:
            print(f"Early stopping after {patience} epochs without improvement", flush=True)
            break
    if device.type == "cuda":
        torch.cuda.synchronize()
    training_time = perf_counter() - training_start
    model.load_state_dict(torch.load(output / "best_model.pt", map_location=device, weights_only=True))
    predictions = {}
    for code in [1, 2]:
        predictions[code] = predict(model, tensors[code][0], device).astype(float) * scalers["y_std"] + scalers["y_mean"]
    # Time a CPU model on preloaded single-window tensors with the same 25/1000 protocol.
    model = model.to("cpu").eval()
    metric_rows, prediction_rows = [], []
    combined_predictions = np.full(len(y), np.nan)
    for code in [1, 2]:
        indices = np.flatnonzero(splits == code)
        values = predictions[code]
        combined_predictions[indices] = values
        with torch.inference_mode():
            def predict_one(features):
                return float(model(features.unsqueeze(0)).item() * scalers["y_std"] + scalers["y_mean"])
            timing = inference_ms(predict_one, tensors[code][0])
        metrics = forecast_metrics(actual[indices], values)
        metric_rows.append({"model": model_name, "horizon_minutes": args.horizon, "split": names[code],
                            **metrics, "training_time_s": training_time, "cpu_inference_ms": timing})
        for index, predicted in zip(indices, values):
            prediction_rows.append({"model": model_name, "horizon_minutes": args.horizon,
                                    "split": names[code], "target_id": metadata[index]["target_id"],
                                    "forecast_origin_utc": metadata[index]["forecast_origin_utc"],
                                    "target_interval_start_utc": metadata[index]["target_interval_start_utc"],
                                    "target_completion_utc": metadata[index]["target_completion_utc"],
                                    "actual_mbps": actual[index], "predicted_mbps": predicted})
        print(f"{names[code]}: MAE={metrics['mae_mbps']:.3f}; RMSE={metrics['rmse_mbps']:.3f}; R2={metrics['r2']}", flush=True)
    for name, rows in [("metrics.csv", metric_rows), ("predictions.csv", prediction_rows), ("training_history.csv", history)]:
        with (output / name).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    configuration = {
        "run_time_utc": datetime.now(timezone.utc).isoformat(), "horizon_minutes": args.horizon,
        "model": model_name, "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
        "seed": seed, "layers": 2, "hidden_units": 64 if model_name != "transformer" else None,
        "dropout": 0., "input_features": preparation["features"],
        "batch_size": batch_size, "optimizer": "Adam", "learning_rate": .001, "loss": "scaled target MSE",
        "max_epochs": max_epochs, "patience": patience, "min_delta": 0., "best_epoch": best_epoch,
        "epochs_completed": len(history), "best_validation_scaled_mse": best_loss, "training_time_s": training_time,
        "training_time_scope": "epoch loop, validation, and saving improved checkpoints; excludes data loading and final evaluation",
        "checkpoint_selection": "lowest validation MSE; test evaluated only after checkpoint selection",
        "train_window_order": "shuffled with seeded generator; validation/test remain chronological",
        "training_device": str(device), "gpu": torch.cuda.get_device_name(0) if device.type == "cuda" else None,
        "cpu_threads": torch.get_num_threads(), "cpu_inference": "25 warm-up, 1000 timed single-window CPU calls; includes inverse scaling; preloaded feature tensors",
        "deterministic_algorithms": True, "cublas_workspace_config": os.environ["CUBLAS_WORKSPACE_CONFIG"],
        "python": platform.python_version(), "numpy": np.__version__, "torch": torch.__version__,
        "platform": platform.platform(), "processor": platform.processor(),
        "artifact_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
        "negative_prediction_count": {names[code]: int((values < 0).sum()) for code, values in predictions.items()},
        "forecast_clipping": "none; later allocation capacity may clamp forecasts at zero",
        "limitation": "one fixed seed; no uncertainty estimate or cross-platform bitwise reproducibility claim",
    }
    if model_name == "transformer":
        configuration["architecture"] = {
            "model_dimension": 64, "attention_heads": 4, "feedforward_dimension": 128,
            "activation": "gelu", "normalization": "post-norm; LayerNorm epsilon 1e-5",
            "position_encoding": "fixed sinusoidal, historical positions 0 to 17",
            "readout": "linear head on last historical position",
            "attention_scope": "full attention within available history only; no future target tokens",
            "layer_initialization": "separately constructed encoder layers",
            "attention_backend": "SDPA MATH; MHA fastpath disabled in this experiment",
        }
    (output / "run_config.json").write_text(json.dumps(configuration, indent=2) + "\n", encoding="utf-8")
    (output / "scalers.json").write_text(json.dumps(scalers, indent=2) + "\n", encoding="utf-8")
    (output / "preparation_config.json").write_text(json.dumps(preparation, indent=2) + "\n", encoding="utf-8")
    comparison = list(metric_rows)
    plotted = {model_name: combined_predictions}
    for comparison_folder in comparison_folders:
        if not (comparison_folder / "run_config.json").exists():
            continue
        with (comparison_folder / "metrics.csv").open(newline="", encoding="utf-8") as handle:
            comparison.extend(csv.DictReader(handle))
        lookup = {row["target_id"]: index for index, row in enumerate(metadata)}
        with (comparison_folder / "predictions.csv").open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                index = lookup[row["target_id"]]
                if row["split"] != metadata[index]["split"] or row["target_completion_utc"] != metadata[index]["target_completion_utc"]:
                    raise ValueError("Comparison forecast target alignment differs")
                if not np.isclose(float(row["actual_mbps"]), actual[index], rtol=1e-10, atol=1e-9):
                    raise ValueError("Comparison actual targets differ")
                if row["model"] not in plotted:
                    plotted[row["model"]] = np.full(len(y), np.nan)
                plotted[row["model"]][index] = float(row["predicted_mbps"])
    with (output / "comparison.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(metric_rows[0]))
        writer.writeheader()
        writer.writerows(comparison)
    plot_prefix(output, metadata, actual, plotted, splits, args.horizon)
    plot_learning(output, history, model_name)
    print(f"Best epoch {best_epoch}; artifacts saved in {output}", flush=True)


def plot_learning(output, history, model_name="lstm"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axis = plt.subplots(figsize=(8, 4), constrained_layout=True)
    axis.plot([row["epoch"] for row in history], [row["train_scaled_mse"] for row in history], label="Training")
    axis.plot([row["epoch"] for row in history], [row["validation_scaled_mse"] for row in history], label="Validation")
    axis.set(xlabel="Epoch", ylabel="MSE in scaled target units", title=f"{model_name.upper()} learning curve")
    axis.legend()
    axis.grid(alpha=.2)
    figure.savefig(output / "learning_curve.png", dpi=160)
    plt.close(figure)


if __name__ == "__main__":
    main()
