"""Checks a rendered figure against its spec: type is a Figure, has data, and every
number the spec holds actually appears in the figure."""
from collections import Counter

import plotly.graph_objects as go


def _numbers(obj):
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        yield round(float(obj), 6)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("title", "colors", "type", "name", "x_title", "y_title"):
                continue
            yield from _numbers(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _numbers(v)


def _fig_numbers(fig):
    out = []
    for tr in fig.data:
        for attr in ("x", "y", "z", "values"):
            v = getattr(tr, attr, None)
            if v is not None:
                out.extend(_numbers(v.tolist() if hasattr(v, "tolist") else list(v)))
    return Counter(out)


def validate(fig, spec: dict):
    """Return None if OK, else an error string for the agent."""
    if not isinstance(fig, go.Figure) or not fig.data:
        return "Figure is empty."
    spec_nums = Counter(_numbers({k: v for k, v in spec.items() if k not in ("bins",)}))
    missing = spec_nums - _fig_numbers(fig)
    if missing:
        return f"Figure is missing values from the spec: {sorted(missing)[:10]}"
    return None
