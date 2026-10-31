"""exec() wrapper: runs a chart snippet in an isolated child process with a timeout."""
import json
import subprocess
import sys
from pathlib import Path

import plotly.io as pio

import config
from charts import CHART_CODE

_RUNNER = str(Path(__file__).with_name("exec_runner.py"))
_MARK = "@@RESULT@@"


def run_chart(spec: dict):
    """Return (figure, None) on success or (None, error_message) on failure."""
    code = CHART_CODE.get(spec.get("type"))
    if code is None:
        return None, f"Unknown chart type '{spec.get('type')}'. Allowed: {sorted(CHART_CODE)}"
    try:
        proc = subprocess.run(
            [sys.executable, _RUNNER],
            input=json.dumps({"code": code, "spec": spec}),
            capture_output=True, text=True, timeout=config.EXEC_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return None, f"Chart code timed out after {config.EXEC_TIMEOUT_SECONDS}s."
    if _MARK not in proc.stdout:
        return None, f"Chart process failed: {proc.stderr.strip()[-500:]}"
    result = json.loads(proc.stdout.split(_MARK, 1)[1])
    if not result["ok"]:
        return None, result["error"]
    return pio.from_json(result["fig"]), None
