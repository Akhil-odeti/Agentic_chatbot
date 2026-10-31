"""The 10 chart snippets. Each runs via exec() with `spec` (dict), `go`, `np`, `pd`
in scope and must leave a plotly Figure in `fig`. The LLM never writes this code;
it only supplies `spec`. Add a chart by adding a snippet and a CHART_CODE entry."""

_COMMON = '''
colors = spec.get("colors") or []
def pick(i):
    return colors[i % len(colors)] if colors else None
def finish(fig):
    fig.update_layout(title=spec["title"], xaxis_title=spec.get("x_title"),
                      yaxis_title=spec.get("y_title"), template="plotly_white")
    return fig
'''

BAR = _COMMON + '''
x, y = spec["x"], spec["y"]
if colors:
    marker = colors if len(colors) == len(x) else colors[0]
else:
    marker = None
fig = finish(go.Figure(go.Bar(x=x, y=y, marker_color=marker)))
'''

GROUPED_BAR = _COMMON + '''
fig = go.Figure([go.Bar(name=s["name"], x=spec["x"], y=s["values"], marker_color=pick(i))
                 for i, s in enumerate(spec["series"])])
fig.update_layout(barmode="group")
fig = finish(fig)
'''

STACKED_BAR = _COMMON + '''
fig = go.Figure([go.Bar(name=s["name"], x=spec["x"], y=s["values"], marker_color=pick(i))
                 for i, s in enumerate(spec["series"])])
fig.update_layout(barmode="stack")
fig = finish(fig)
'''

LINE = _COMMON + '''
fig = go.Figure([go.Scatter(name=s["name"], x=spec["x"], y=s["values"], mode="lines+markers",
                            line=dict(color=pick(i))) for i, s in enumerate(spec["series"])])
fig = finish(fig)
'''

AREA = _COMMON + '''
fig = go.Figure([go.Scatter(name=s["name"], x=spec["x"], y=s["values"], mode="lines",
                            fill="tozeroy", line=dict(color=pick(i)))
                 for i, s in enumerate(spec["series"])])
fig = finish(fig)
'''

PIE = _COMMON + '''
fig = go.Figure(go.Pie(labels=spec["labels"], values=spec["values"],
                       hole=0.4 if spec.get("donut") else 0,
                       marker=dict(colors=colors) if colors else None))
fig.update_layout(title=spec["title"], template="plotly_white")
'''

SCATTER = _COMMON + '''
fig = go.Figure(go.Scatter(x=spec["x"], y=spec["y"], mode="markers",
                           marker=dict(color=pick(0), size=10)))
fig = finish(fig)
'''

HISTOGRAM = _COMMON + '''
fig = go.Figure(go.Histogram(x=spec["values"], nbinsx=spec.get("bins"), marker_color=pick(0)))
fig = finish(fig)
'''

BOX = _COMMON + '''
fig = go.Figure([go.Box(y=g["values"], name=g["name"], marker_color=pick(i))
                 for i, g in enumerate(spec["groups"])])
fig = finish(fig)
'''

HEATMAP = _COMMON + '''
scale = colors if len(colors) >= 2 else "Viridis"
fig = go.Figure(go.Heatmap(z=spec["z"], x=spec["x"], y=spec["y"], colorscale=scale))
fig = finish(fig)
'''

CHART_CODE = {
    "bar": BAR,
    "grouped_bar": GROUPED_BAR,
    "stacked_bar": STACKED_BAR,
    "line": LINE,
    "area": AREA,
    "pie": PIE,
    "scatter": SCATTER,
    "histogram": HISTOGRAM,
    "box": BOX,
    "heatmap": HEATMAP,
}
