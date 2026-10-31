"""Chart-selector agent.

A separate, focused LLM call that decides WHICH chart type(s) fit the user's request and the
data. The main agent used to pick the type itself and defaulted to 'bar'. Now it must ask this
selector first (plan_charts tool), and make_charts only accepts the types the selector planned.

Why a separate call works better than one more line in the main prompt:
- it reads the conversation itself, so the main agent cannot bias it with its own habit;
- it has one job and a full decision table, instead of a rule buried in a long prompt;
- code checks its answer (user-named types honoured, different types for several charts).
"""
from typing import Literal, get_args

from pydantic import BaseModel, Field

import config

ChartType = Literal[
    "bar", "grouped_bar", "stacked_bar", "line", "area",
    "pie", "scatter", "histogram", "box", "heatmap",
]
CHART_TYPES: tuple[str, ...] = get_args(ChartType)


class PlannedChart(BaseModel):
    type: ChartType
    title: str = Field(description="Short chart title.")
    plot: str = Field(
        description="Exactly what goes where, e.g. 'x = year, one line per product, y = revenue'."
    )
    reason: str = Field(description="One sentence: why this type fits THIS data and request.")


class ChartPlan(BaseModel):
    user_named_types: list[ChartType] = Field(
        description="Chart types the user explicitly asked for in their request. Empty list if none."
    )
    charts: list[PlannedChart]


SELECTOR_PROMPT = """You are the chart-selector. You do NOT draw charts and you do NOT write any \
numbers. Given the user's request, the data in the conversation and the charts already drawn, you \
decide which chart type each chart should use.

Chart types and when each one fits:
- bar: ONE measure across categories; a ranking or comparison of named items.
- grouped_bar: 2+ measures (or series) per category, compared side by side on a similar scale.
- stacked_bar: 2+ parts that add up to a total for each category (composition per category).
- line: change over time or an ordered sequence (years, months, dates, rounds); trends, one or many series.
- area: like line, but the cumulative size or volume over time is the point.
- pie: share of a whole. At most 7 slices, all non-negative. Not for ranking 8+ items.
- scatter: relationship or correlation between two NUMERIC measures per item (e.g. runs vs matches).
- histogram: distribution of ONE numeric column with MANY raw values (15 or more).
- box: spread and outliers of raw values across 2+ groups.
- heatmap: one measure across two categorical dimensions (a grid), or a correlation-style matrix.

Rules:
1. If the user names a chart type, use exactly that type for that chart and list it in user_named_types.
2. Otherwise choose by the SHAPE of the data and the question being asked, never by habit. Bar is \
right only when the data really is one measure across categories. Look for: a time axis, several \
numeric columns, parts of a whole, raw value lists, two categorical dimensions.
3. When the user asks for several charts ("5 different charts", "give me the graphs", "different \
views"), every chart must use a DIFFERENT type and show a different angle of the data (for example \
ranking, share, relationship, trend, distribution). Do not return the same type twice unless the \
data cannot support anything else.
4. Only pick a type the available data can support. No time axis means no line or area. Fewer than \
two numeric measures means no scatter. Fewer than 15 raw values means no histogram.
5. Plan at most {max_charts} charts. If the user gave no number: 1 chart when the question has a \
single angle, 2 or 3 for broad asks like "give me the graphs".
6. If the user only wants to change colors, labels or values of an existing chart, keep that chart's \
type unless they ask to change it.
7. In "plot", name the actual columns, series or categories from the data.
"""

_MAX_REQUEST_CHARS = 6000
_MAX_DATA_CHARS = 8000


def _text(message) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, list):  # content blocks
        content = " ".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
    return str(content)


def existing_charts(messages) -> list[str]:
    """Charts the agent already drew in this chat, read from its earlier make_charts calls."""
    out = []
    for m in messages:
        if getattr(m, "type", "") != "ai":
            continue
        for tc in getattr(m, "tool_calls", None) or []:
            if tc.get("name") != "make_charts":
                continue
            for ch in (tc.get("args") or {}).get("charts") or []:
                if isinstance(ch, dict):
                    out.append(f'{ch.get("type")}: "{ch.get("title")}"')
    return out[-6:]


def build_context(messages, notes: str = "") -> str:
    """What the selector sees: the latest request, the data available in the conversation
    (earlier user messages and search/scrape results), and charts already drawn."""
    humans = [m for m in messages if getattr(m, "type", "") == "human"]
    last = humans[-1] if humans else None
    request = _text(last) if last is not None else ""
    data = []
    for m in messages:
        kind = getattr(m, "type", "")
        if m is last:
            continue
        if kind == "tool" and getattr(m, "name", "") in ("make_charts", "plan_charts"):
            continue  # our own outputs are not data
        if kind in ("human", "tool"):
            data.append(_text(m))
    data_text = "\n---\n".join(data)[-_MAX_DATA_CHARS:]
    drawn = existing_charts(messages)
    parts = [f"LATEST USER REQUEST:\n{request[:_MAX_REQUEST_CHARS]}"]
    parts.append("DATA AVAILABLE IN THE CONVERSATION (earlier messages, search/scrape results):\n"
                 + (data_text or "(none beyond the request itself)"))
    parts.append("CHARTS ALREADY DRAWN:\n" + ("\n".join(drawn) if drawn else "(none)"))
    if notes.strip():
        parts.append(f"AGENT'S NOTE ABOUT THE DATA:\n{notes.strip()[:500]}")
    return "\n\n".join(parts)


async def _ask_llm(llm, system: str, user: str) -> ChartPlan:
    """One structured-output call on the user's own model (llm already holds their API key).
    No temperature is set, so every OpenAI chat model accepts the call."""
    return await llm.with_structured_output(ChartPlan, method="function_calling").ainvoke(
        [("system", system), ("user", user)]
    )


def _problems(plan: ChartPlan) -> str:
    """Code-side checks on the selector's answer. Returns feedback text, or '' if fine."""
    types = [c.type for c in plan.charts]
    named = list(dict.fromkeys(plan.user_named_types))
    issues = []
    missing = [t for t in named if t not in types]
    if missing:
        issues.append(f"The user named these types: {missing}. Include a chart of each.")
    if len(types) > 1 and not named and len(set(types)) < len(types):
        issues.append(
            "Several charts must each use a DIFFERENT type and show a different angle of the data."
        )
    return " ".join(issues)


async def select_charts(messages, llm, notes: str = "") -> ChartPlan | None:
    """Return the validated plan, or None if the selector could not run (caller fails open)."""
    context = build_context(messages, notes)
    system = SELECTOR_PROMPT.format(max_charts=config.MAX_CHARTS)
    plan, feedback = None, ""
    for _ in range(2):  # at most one retry, only to fix a problem found by _problems
        try:
            candidate = await _ask_llm(llm, system, context + feedback)
        except Exception:
            break
        plan = candidate
        problem = _problems(plan)
        if not problem:
            break
        feedback = f"\n\nYOUR PREVIOUS PLAN HAD A PROBLEM: {problem} Fix it."
    if plan is not None:
        plan.charts = plan.charts[: config.MAX_CHARTS]
    return plan


def format_plan(plan: ChartPlan) -> str:
    lines = ["Chart plan from the chart-selector (based on the user's request and the data):"]
    for i, c in enumerate(plan.charts, 1):
        lines.append(f'{i}. type={c.type} | "{c.title}" | plot: {c.plot} | why: {c.reason}')
    lines.append(
        f"Now call make_charts with exactly these types, one chart per item, using only real "
        f"numbers. Do not change a planned type to bar. At most {config.MAX_CHARTS} charts per "
        f"request: if the user asked for more, say the rest can be drawn in a follow-up."
    )
    return "\n".join(lines)
