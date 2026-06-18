"""Tiny persisted state so the briefing can compare day-over-day.

We keep one JSON file (committed to the repo under reports/state/) mapping
each mapped market to its last implied probability and when we first saw it.
That lets the daily run compute overnight probability shifts and detect
markets that are new today.
"""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_STATE = Path("reports/state/edge_state.json")


def load_state(path: Path | str = DEFAULT_STATE) -> dict:
    p = Path(path)
    if not p.exists():
        return {"markets": {}}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        data.setdefault("markets", {})
        return data
    except Exception:
        return {"markets": {}}


def save_state(state: dict, path: Path | str = DEFAULT_STATE) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2), encoding="utf-8")
