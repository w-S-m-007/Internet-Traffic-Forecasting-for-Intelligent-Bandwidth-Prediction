"""Interactive figures over saved observations; excluded gaps remain visible."""

import pandas as pd
import plotly.graph_objects as go


COLORS = {"Actual": "#142b49", "Forecast": "#009da4", "Reactive capacity": "#8c97aa",
          "Proactive capacity": "#009da4", "Shortfall": "#d84f4f"}


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
                                   line={"color": COLORS[label], "width": 2},
                                   hovertemplate="%{y:.2f} Mbps<extra>" + label + "</extra>"))
    if markers is not None:
        selected = frame[markers]
        figure.add_trace(go.Scatter(x=selected["target_completion_utc"].tolist(), y=selected["actual_mbps"],
                                   name="Shortfall", mode="markers", marker={"color": COLORS["Shortfall"], "size": 7},
                                   hovertemplate="%{y:.2f} Mbps<extra>Demand exceeds proactive capacity</extra>"))
    figure.update_layout(height=330, margin={"l": 10, "r": 10, "t": 12, "b": 10},
                         paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                         font={"family": "Arial, sans-serif", "color": "#52637a"},
                         legend={"orientation": "h", "y": 1.12, "x": 1, "xanchor": "right"},
                         hovermode="x unified", hoverlabel={"bgcolor": "white"},
                         xaxis={"title": "Target interval completion (UTC)", "gridcolor": "#edf1f5",
                                "hoverformat": "%Y-%m-%d %H:%M UTC"},
                         yaxis={"title": "Nominal recorded Mbps", "gridcolor": "#edf1f5", "rangemode": "tozero"})
    return figure
