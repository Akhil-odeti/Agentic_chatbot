"""Runs inside a child process. Reads {"code","spec"} JSON on stdin, exec()s the
snippet with restricted globals/builtins, prints {"ok","fig"|"error"} JSON."""
import json
import sys
import traceback

SAFE_BUILTINS = {
    n: __builtins__[n] if isinstance(__builtins__, dict) else getattr(__builtins__, n)
    for n in (
        "abs", "all", "any", "bool", "dict", "enumerate", "float", "int", "len", "list",
        "max", "min", "range", "round", "set", "sorted", "str", "sum", "tuple", "zip",
        "isinstance", "True", "False", "None", "ValueError", "TypeError", "KeyError",
        "IndexError", "Exception",
    )
}


def main():
    payload = json.loads(sys.stdin.read())
    try:
        import numpy as np
        import pandas as pd
        import plotly.graph_objects as go

        scope = {"__builtins__": SAFE_BUILTINS, "go": go, "np": np, "pd": pd, "spec": payload["spec"]}
        exec(payload["code"], scope)
        fig = scope.get("fig")
        if not isinstance(fig, go.Figure):
            raise TypeError("Code did not produce a plotly Figure in variable 'fig'.")
        out = {"ok": True, "fig": fig.to_json()}
    except Exception as e:  # report to parent so the agent can fix the spec
        out = {"ok": False, "error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc(limit=3)}
    sys.stdout.write("\n@@RESULT@@" + json.dumps(out))


if __name__ == "__main__":
    main()
