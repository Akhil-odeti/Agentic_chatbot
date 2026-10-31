"""Checks that chart numbers actually appear in what the user said or in tool results
(search / scrape output), so the model cannot silently invent or 'estimate' data."""
import re

from validator import _numbers

_NUM = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def numbers_in_text(text: str) -> set[float]:
    found = set()
    for m in _NUM.findall(text):
        found.add(round(float(m.replace(",", "")), 6))
        for part in m.split(","):  # lists such as "10,20,30"
            if part.strip("-"):
                found.add(round(float(part), 6))
    return found


def ungrounded_numbers(spec: dict, messages) -> list[float]:
    """Spec numbers not present in any human or tool message. AI messages are ignored on purpose:
    they may contain the model's own guesses."""
    known: set[float] = set()
    for m in messages:
        if getattr(m, "type", "") in ("human", "tool"):
            known |= numbers_in_text(str(m.content))
    wanted = {k: v for k, v in spec.items() if k not in ("bins", "computed")}
    return sorted({n for n in _numbers(wanted) if n not in known})
