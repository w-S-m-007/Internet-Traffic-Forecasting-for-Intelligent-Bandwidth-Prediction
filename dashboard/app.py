"""Run with: python -m streamlit run dashboard/app.py (from project root)."""

import sys
from html import escape
from pathlib import Path

# Streamlit runs this file as a script; retain package imports from the root.
PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

import numpy as np
import streamlit as st

from dashboard.artifacts import (MODEL_LABELS, ArtifactError, allocation_snapshot,
                                 available_horizons, fingerprint, load_allocation,
                                 load_forecasts, model_forecasts)
from dashboard.charts import traffic_chart
from dashboard.charts import comparison_chart


@st.cache_data(show_spinner="Checking saved results…")
def cached_artifacts(project, horizon, signature):
    forecasts = load_forecasts(Path(project), horizon)
    try:
        allocation = load_allocation(Path(project), forecasts)
        allocation_error = None
    except (ArtifactError, OSError, ValueError, KeyError) as exc:
        allocation, allocation_error = None, str(exc)
    return forecasts, allocation, allocation_error


def number(value, decimals=3, suffix=""):
    return "—" if value is None or not np.isfinite(float(value)) else f"{value:,.{decimals}f}{suffix}"


def comparison_panel(artifacts, split, expanded=False):
    st.subheader(f"Model comparison · {artifacts.horizon}-minute forecasts")
    order = list(MODEL_LABELS)
    table = artifacts.metrics[artifacts.metrics["split"] == split].copy()
    table["order"] = table["model"].map(order.index)
    table = table.sort_values("order")
    if expanded:
        st.plotly_chart(comparison_chart(table), width="stretch", key="comparison_chart")
    table["model"] = table["model"].map(MODEL_LABELS)
    view = table[["model", "mae_mbps", "rmse_mbps", "mape_pct", "r2"]].rename(columns={
        "model": "Model", "mae_mbps": "MAE", "rmse_mbps": "RMSE", "mape_pct": "MAPE (%)", "r2": "R²"})
    styled = view.style.format({"MAE": "{:.3f}", "RMSE": "{:.3f}", "MAPE (%)": "{:.2f}", "R²": "{:.3f}"}, na_rep="—")
    styled = styled.highlight_min(subset=["MAE", "RMSE", "MAPE (%)"], color="#dff6ef")
    st.dataframe(styled, hide_index=True, width="stretch")
    st.caption("MAE / RMSE in nominal Mbps. Highlighted cells have the lowest error in this split. One fixed seed.")
    with st.expander("Training and inference measurements"):
        timing = table[["model", "training_time_s", "cpu_inference_ms"]].rename(columns={
            "model": "Model", "training_time_s": "Training (s)", "cpu_inference_ms": "CPU inference (ms)"})
        st.dataframe(timing, hide_index=True, width="stretch")
        st.caption("CPU: one preloaded window per call; 25 warm-ups and 1,000 timed calls. Neural models use one CPU thread. Timings vary with machine/load.")
    st.download_button("Download comparison CSV", table.drop(columns="order").to_csv(index=False),
                       file_name=f"comparison_{artifacts.horizon}min_{split}.csv", mime="text/csv")


def allocation_panel(artifacts, allocation, allocation_error, split, replay_target, window, expanded=False):
    st.subheader("Bandwidth allocation")
    if allocation_error:
        st.warning(f"Allocation results need attention: {allocation_error}")
        return
    if allocation is None:
        st.info("No matching allocation experiment is saved for this horizon. The initial experiment uses 10-minute forecasts.")
        return
    options = [name for name in ("lstm", "gru", "transformer", "moving_average_4")
               if f"proactive_{name}" in allocation["selected_defaults"]]
    model = st.selectbox("Allocation model", options, format_func=MODEL_LABELS.get, key="allocation_model")
    st.caption("Compare each saved proactive policy with reactive capacity at the same margin.")
    default = allocation["selected_defaults"][f"proactive_{model}"]
    margin_pct = st.slider("Safety margin", 5, 20, int(round(default["margin"] * 100)), step=5,
                           format="%d%%", key=f"margin_{model}")
    frame, scores = allocation_snapshot(artifacts, model, split, margin_pct / 100)
    left, right = st.columns(2)
    for column, policy, label in ((left, "reactive", "Reactive"), (right, "proactive", MODEL_LABELS[model])):
        with column:
            st.markdown(f"**{label}**")
            st.metric("Shortfall intervals", number(scores[policy]["shortfall_pct"], 2, "%"))
            st.caption(f"Mean capacity: {scores[policy]['mean_capacity_mbps']:,.2f} Mbps")
    if not default["validation_target_met"]:
        st.warning(f"1% validation shortfall target unmet. Default: {default['margin']:.0%} fallback. Viewing: {margin_pct}% margin.")
    else:
        st.info(f"Default {default['margin']:.0%} margin selected on validation only; viewing {margin_pct}%.")
    current = frame[frame["target_id"] == replay_target].iloc[0]
    st.caption(f"At replay interval · Forecast {current['predicted_mbps']:,.2f} Mbps · Capacity {current['proactive_capacity']:,.2f} Mbps · Deficit {current['proactive_deficit'] * 75:,.2f} MB")
    st.caption("Offline capacity pool. Shortfall is simulated unserved demand, not measured packet loss.")
    if expanded:
        selected = frame[frame["target_id"].isin(window["target_id"])].copy()
        st.plotly_chart(traffic_chart(selected, {"Actual": "actual_mbps", "Reactive capacity": "reactive_capacity",
                                               "Proactive capacity": "proactive_capacity"}, selected["proactive_deficit"] > 0),
                        width="stretch", key="allocation_chart")
        st.dataframe([{"Policy": label, "Deficit volume (MB)": scores[key]["deficit_volume_mb"],
                       "Mean excess capacity (Mbps)": scores[key]["mean_overprovision_mbps"],
                       "Served demand / capacity": scores[key]["served_demand_to_capacity_ratio"]}
                      for key, label in (("reactive", "Reactive"), ("proactive", MODEL_LABELS[model]))],
                     hide_index=True, width="stretch")
        st.download_button("Download allocation replay CSV", frame.to_csv(index=False),
                           file_name=f"allocation_{model}_{split}_{margin_pct}pct.csv", mime="text/csv")
    st.caption(f"Allocation scores cover all {len(frame):,} eligible {split} intervals, at identical margins.")


def main(project_root=PROJECT):
    project = Path(project_root)
    st.set_page_config(page_title="Traffic Forecasting", page_icon="📈", layout="wide")
    st.markdown(f"<style>{Path(__file__).with_name('styles.css').read_text()}</style>", unsafe_allow_html=True)
    with st.sidebar:
        st.markdown('<div class="brand-mark" aria-hidden="true">⌁</div><div class="brand-eyebrow">NETWORK ANALYTICS</div>', unsafe_allow_html=True)
        st.title("Traffic Forecasting")
        st.caption("Forecast demand. Explore capacity.")
        st.divider()
        st.selectbox("Dataset", ["CESNET-TimeSeries24"], disabled=True)
        st.selectbox("Institution", ["Institution 0"], disabled=True)
    horizons = available_horizons(project)
    if not horizons:
        st.title("Traffic forecasting & bandwidth allocation")
        st.info("No saved forecast results found. Run preparation, baselines and neural experiments first.")
        st.code("python -m data_processing.prepare_dataset\npython -m experiments.evaluate_baselines --horizon 10\npython -m experiments.train_lstm --horizon 10 --device auto", language="bash")
        return
    with st.sidebar:
        horizon = st.selectbox("Horizon", horizons, format_func=lambda value: f"{value} minutes", key="horizon")
        missing = [str(value) for value in (10, 30, 60) if value not in horizons]
        if missing:
            st.caption(f"{' / '.join(missing)} min: pending evaluation")
    try:
        artifacts, allocation, allocation_error = cached_artifacts(str(project), horizon, fingerprint(project))
    except (ArtifactError, OSError, ValueError, KeyError) as exc:
        st.error(f"Cannot display these saved results: {exc}")
        return
    models = [name for name in MODEL_LABELS if name in artifacts.configs]
    with st.sidebar:
        model = st.selectbox("Model", models, index=models.index("lstm") if "lstm" in models else 0,
                             format_func=MODEL_LABELS.get, key="model")
        split = st.selectbox("Evaluation split", ["test", "validation"], format_func=str.title, key="split")
        page = st.radio("View", ["Overview", "Forecasts", "Comparison", "Allocation"], key="view")
        records = st.selectbox("Chart history", [36, 72, 144, 288], index=2,
                              format_func=lambda value: f"{value // 6} nominal hours", key="chart_history")
    forecasts = model_forecasts(artifacts, model, split)
    with st.sidebar:
        end = st.slider("Replay position", 1, len(forecasts), min(records, len(forecasts)), key=f"replay_{horizon}_{split}") if len(forecasts) > 1 else 1
        st.caption("Move through observed intervals. Excluded gaps remain excluded.")
        st.markdown('<span class="offline-badge">Saved results · Offline</span>', unsafe_allow_html=True)
    window = forecasts.iloc[max(0, end - records):end]
    current = forecasts.iloc[end - 1]
    metric = artifacts.metrics[(artifacts.metrics["model"] == model) & (artifacts.metrics["split"] == split)].iloc[0]
    st.markdown(f'''<section class="workspace-hero">
<div class="hero-copy"><div class="eyebrow">TRAFFIC INTELLIGENCE / {escape(page.upper())}</div>
<h1>See demand.<br><span>Plan ahead.</span></h1>
<p>Internet traffic forecasting &amp; bandwidth allocation</p>
<div class="hero-tags"><span>CESNET · Institution 0</span><span>{horizon}-minute horizon</span><span>{escape(MODEL_LABELS[model])}</span></div></div>
<div class="hero-aside"><div class="replay-status"><i></i> HISTORICAL REPLAY</div>
<strong>{len(forecasts):,}</strong><span>eligible {escape(split)} intervals</span>
<small>Recorded observations · One fixed seed</small></div></section>''', unsafe_allow_html=True)
    st.markdown('<div class="section-eyebrow">FORECAST PERFORMANCE <span>Full eligible split · Original units</span></div>', unsafe_allow_html=True)
    for column, label, field, unit, digits in zip(st.columns(4), ["MAE", "RMSE", "MAPE", "R²"],
                                                ["mae_mbps", "rmse_mbps", "mape_pct", "r2"],
                                                [" Mbps", " Mbps", "%", ""], [3, 3, 2, 3]):
        column.metric(label, number(metric[field], digits, unit))
    st.caption(f"{len(forecasts):,} eligible {split} intervals · {MODEL_LABELS[model]} · One fixed seed · Metrics use the full split")
    if page in ("Overview", "Forecasts"):
        with st.container(border=True, key="forecast_surface"):
            st.subheader("Actual vs predicted traffic")
            st.caption(f"{MODEL_LABELS[model]} · {len(window)} observed intervals · {window.iloc[0]['target_completion_utc']:%d %b %Y %H:%M} to {current['target_completion_utc']:%d %b %Y %H:%M} UTC")
            st.plotly_chart(traffic_chart(window, {"Actual": "actual_mbps", "Forecast": "predicted_mbps"}), width="stretch", key="forecast_chart")
            st.caption(f"Replay target {current['target_completion_utc']:%Y-%m-%d %H:%M} UTC · Actual {current['actual_mbps']:,.2f} Mbps · Forecast {current['predicted_mbps']:,.2f} Mbps")
            if page == "Forecasts":
                st.download_button("Download saved forecasts CSV", forecasts.to_csv(index=False),
                                   file_name=f"forecasts_{model}_{horizon}min_{split}.csv", mime="text/csv")
    if page == "Overview":
        left, right = st.columns([1.15, 1], gap="medium")
        with left, st.container(border=True, key="comparison_surface"):
            comparison_panel(artifacts, split)
        with right, st.container(border=True, key="allocation_surface"):
            allocation_panel(artifacts, allocation, allocation_error, split, current["target_id"], window)
    elif page == "Comparison":
        with st.container(border=True, key="comparison_surface"):
            comparison_panel(artifacts, split, expanded=True)
    elif page == "Allocation":
        with st.container(border=True, key="allocation_surface"):
            allocation_panel(artifacts, allocation, allocation_error, split, current["target_id"], window, expanded=True)
    with st.expander("Data definitions and limitations"):
        st.write("Nominal recorded Mbps = n_bytes × 8 / (600 × 1,000,000). This includes both traffic directions and is not physical-link utilization. The experiment excludes the recorded outage policy dates and guarded timestamp boundaries.")
        st.write(f"MAPE uses positive targets only; excluded targets for this model/split: {int(metric['mape_excluded'])}. Predictions are not clipped for accuracy metrics. Allocation clamps negative forecasts at zero.")
        st.write("All charts use saved UTC timestamps. Lines break across excluded intervals. Replay changes the displayed history, not the full-split scores or validation-selected default margins. No model training occurs in this app.")
    st.caption("CESNET-TimeSeries24 · Recorded experiment results · Offline research prototype")


if __name__ == "__main__":
    main()
