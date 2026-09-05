"""Append-only JSONL audit trail. Thread-safe via a module-level lock."""

import json
import threading
from pathlib import Path

from src.models import AuditEntry

_lock = threading.Lock()
LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "audit.jsonl"


def append(entry: AuditEntry) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = entry.model_dump_json()
    with _lock:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def read_all() -> list[AuditEntry]:
    if not LOG_PATH.exists():
        return []
    entries = []
    with LOG_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(AuditEntry.model_validate(json.loads(line)))
    return entries
