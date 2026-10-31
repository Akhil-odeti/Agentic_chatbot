"""Computes exact facts about a chart's data. The agent writes its 'key insights' from these,
so figures such as shares, changes and correlations are calculated by code, not by the LLM."""
import math
import statistics as st


def _f(x: float) -> str:
    return f"{x:,.0f}" if abs(x) >= 1000 or float(x).is_integer() else f"{x:,.2f}"


def _pct(part: float, whole: float) -> str:
    return f"{part / whole * 100:.1f}%" if whole else "n/a"


def _extremes(labels, values, what="value"):
    i, j = values.index(max(values)), values.index(min(values))
    return f"highest {what}: {labels[i]} ({_f(values[i])}); lowest: {labels[j]} ({_f(values[j])})"


def _series_facts(x, series):
    out = []
    for s in series:
        v = s["values"]
        line = f"{s['name']}: {_extremes(x, v)}; total {_f(sum(v))}"
        if len(v) > 1 and v[0]:
            line += f"; change {x[0]}->{x[-1]}: {(v[-1] - v[0]) / abs(v[0]) * 100:+.1f}%"
        out.append(line)
    return out


def _corr(a, b):
    if len(a) < 3 or st.pstdev(a) == 0 or st.pstdev(b) == 0:
        return None
    ma, mb = st.mean(a), st.mean(b)
    cov = sum((p - ma) * (q - mb) for p, q in zip(a, b))
    return cov / math.sqrt(sum((p - ma) ** 2 for p in a) * sum((q - mb) ** 2 for q in b))


def chart_facts(spec: dict) -> list[str]:
    t = spec["type"]
    if t == "bar":
        x, y = spec["x"], spec["y"]
        total = sum(y)
        top = y.index(max(y))
        return [_extremes(x, y), f"total {_f(total)}, average {_f(st.mean(y))}",
                f"{x[top]} is {_pct(y[top], total)} of the total"]
    if t in ("grouped_bar", "stacked_bar", "line", "area"):
        x, series = spec["x"], spec["series"]
        out = _series_facts(x, series)
        if len(series) > 1:
            totals = [sum(s["values"][i] for s in series) for i in range(len(x))]
            out.append(f"combined by {spec.get('x_title') or 'category'}: " + _extremes(x, totals))
        return out
    if t == "pie":
        labels, v = spec["labels"], spec["values"]
        total = sum(v)
        order = sorted(range(len(v)), key=lambda i: -v[i])
        out = [f"largest share: {labels[order[0]]} ({_pct(v[order[0]], total)}); "
               f"smallest: {labels[order[-1]]} ({_pct(v[order[-1]], total)})"]
        if len(v) > 2:
            out.append(f"top two ({labels[order[0]]}, {labels[order[1]]}) = "
                       f"{_pct(v[order[0]] + v[order[1]], total)} of the total")
        return out
    if t == "scatter":
        x, y = spec["x"], spec["y"]
        r = _corr(x, y)
        out = [f"{len(x)} points; x range {_f(min(x))} to {_f(max(x))}; y range {_f(min(y))} to {_f(max(y))}"]
        if r is not None:
            strength = "strong" if abs(r) >= 0.7 else "moderate" if abs(r) >= 0.4 else "weak"
            out.append(f"correlation r = {r:.2f} ({strength} {'positive' if r > 0 else 'negative'})")
        return out
    if t == "histogram":
        v = spec["values"]
        return [f"{len(v)} values; mean {_f(st.mean(v))}, median {_f(st.median(v))}; "
                f"min {_f(min(v))}, max {_f(max(v))}"
                + (f"; std dev {_f(st.pstdev(v))}" if len(v) > 1 else "")]
    if t == "box":
        out = []
        for g in spec["groups"]:
            v = sorted(g["values"])
            line = f"{g['name']}: median {_f(st.median(v))}, min {_f(v[0])}, max {_f(v[-1])}"
            if len(v) >= 4:
                q = st.quantiles(v, n=4)
                iqr = q[2] - q[0]
                outl = [a for a in v if a < q[0] - 1.5 * iqr or a > q[2] + 1.5 * iqr]
                line += f", IQR {_f(iqr)}" + (f", outliers {[_f(o) for o in outl]}" if outl else "")
            out.append(line)
        return out
    if t == "heatmap":
        x, y, z = spec["x"], spec["y"], spec["z"]
        cells = [(z[r][c], y[r], x[c]) for r in range(len(y)) for c in range(len(x))]
        hi, lo = max(cells), min(cells)
        row_avg = [st.mean(row) for row in z]
        return [f"highest cell: {hi[1]} / {hi[2]} ({_f(hi[0])}); lowest: {lo[1]} / {lo[2]} ({_f(lo[0])})",
                f"row with highest average: {y[row_avg.index(max(row_avg))]} ({_f(max(row_avg))})"]
    return []
