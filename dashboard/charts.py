"""Interactive figures over saved observations; excluded gaps remain visible."""

import pandas as pd
import plotly.graph_objects as go


COLORS = {"Actual": "#253957", "Forecast": "#3c6bf1", "Reactive capacity": "#a1adc1",
          "Proactive capacity": "#10a48c", "Shortfall": "#e16b58"}


def traffic_chart(frame, series, markers=None):
    # A NaN row prevents connecting a line across excluded/missing intervals.
    timestamps = pd.DatetimeIndex(frame["target_completion_utc"])
    gaps = timestamps.to_series().diff().gt(pd.Timedelta(seconds=600))
    breaks = timestamps[gaps.to_numpy()] - pd.Timedelta(seconds=1)
    index = timestamps.union(breaks).sort_values()
    figure = go.Figure()
    for label, column in series.items():
        values = pd.Series(frame[column].to_numpy(), index=timestamps).reindex(index)
        figure.add_trace(go.Scatter(x=index.to_pydatetime().tolist(), y=values.to_numpy(), name=label,
                                   mode="lines", connectgaps=False,
                                   line={"color": COLORS[label], "width": 2.4 if label in ("Forecast", "Proactive capacity") else 1.6},
                                   fill="tozeroy" if label == "Forecast" else None,
                                   fillcolor="rgba(60,107,241,0.055)" if label == "Forecast" else None,
                                   hovertemplate="%{y:.2f} Mbps<extra>" + label + "</extra>"))
    if markers is not None:
        selected = frame[markers]
        figure.add_trace(go.Scatter(x=selected["target_completion_utc"].tolist(), y=selected["actual_mbps"],
                                   name="Shortfall", mode="markers", marker={"color": COLORS["Shortfall"], "size": 7},
                                   hovertemplate="%{y:.2f} Mbps<extra>Demand exceeds proactive capacity</extra>"))
    figure.update_layout(height=360, margin={"l": 10, "r": 16, "t": 36, "b": 10},
                         paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                         font={"family": "Segoe UI, Arial, sans-serif", "color": "#7b889f", "size": 12},
                         legend={"orientation": "h", "y": 1.15, "x": 1, "xanchor": "right"},
                         hovermode="x unified", hoverlabel={"bgcolor": "white"},
                         xaxis={"title": "Target interval completion (UTC)", "showgrid": False, "zeroline": False,
                                "hoverformat": "%Y-%m-%d %H:%M UTC"},
                         yaxis={"title": "Nominal recorded Mbps", "gridcolor": "#edf1f7", "zeroline": False, "rangemode": "tozero"})
    return figure


def comparison_chart(table):
    """Display the saved split's RMSE values; this chart does not select a model."""
    labels = {"persistence": "Persistence", "moving_average_4": "Moving average", "lstm": "LSTM", "gru": "GRU", "transformer": "Transformer"}
    colors = ["#a4afc2", "#7589ac", "#3c6bf1", "#10a48c", "#9275dc"]
    figure = go.Figure(go.Bar(x=table["model"].map(labels), y=table["rmse_mbps"],
                             marker_color=colors, marker_line_width=0,
                             text=table["rmse_mbps"].map(lambda v: f"{v:.3f}"), textposition="outside",
                             hovertemplate="%{x}<br>RMSE %{y:.3f} Mbps<extra></extra>"))
    figure.update_layout(height=285, margin=dict(l=15,r=15,t=35,b=15), bargap=.55,
                         paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                         font=dict(family="Segoe UI, sans-serif", color="#7b889f"),
                         yaxis=dict(title="RMSE (Mbps)", gridcolor="#edf1f7", zeroline=False,
                                    range=[0, float(table["rmse_mbps"].max()) * 1.22]),
                         xaxis=dict(showgrid=False), showlegend=False)
    return figure
