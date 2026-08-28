"""Backend paths & runtime state.

- DATA_DIR / DEFAULT_CSV can be overridden through environment variables
  (used by tests / deployments that keep data elsewhere).
- A lightweight thread-safe state holds the "rebuild in progress" flag and
  the current in-memory database instance.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent

DATA_DIR = Path(os.environ.get("WORD_QUERY_DATA") or (BACKEND_DIR / "data"))
DEFAULT_CSV = Path(
    os.environ.get("WORD_QUERY_CSV") or (PROJECT_DIR / "考研英语大纲词汇5500.csv")
)

# ---- runtime state ---------------------------------------------------------
_state_lock = threading.Lock()
_state = {
    "db": None,          # Database instance (set once by main.py)
    "building": False,   # an index rebuild is running
    "last_built_at": None,
}


def set_db(db) -> None:
    with _state_lock:
        _state["db"] = db


def get_db():
    with _state_lock:
        return _state["db"]


def set_building(value: bool) -> None:
    with _state_lock:
        _state["building"] = value


def is_building() -> bool:
    with _state_lock:
        return _state["building"]


def set_last_built(value) -> None:
    with _state_lock:
        _state["last_built_at"] = value


def get_last_built():
    with _state_lock:
        return _state["last_built_at"]
