"""Durable per-server library operation state and history."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OperationStore:
    """Small thread-safe JSON store suitable for the mounted output volume."""

    def __init__(self, path: Optional[str] = None, history_limit: int = 100):
        base = Path("/app/output" if os.path.exists("/app") else "./output")
        base.mkdir(parents=True, exist_ok=True)
        self.path = Path(path) if path else base / "library_operations.json"
        self.history_limit = max(10, int(history_limit))
        self._lock = threading.RLock()
        self._data: Dict[str, Any] = {"version": 1, "servers": {}}

        with self._lock:
            self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self._data = raw
                self._data.setdefault("version", 1)
                self._data.setdefault("servers", {})
        except (OSError, ValueError) as exc:
            logger.warning("Could not load operation state: %s", exc)

    def _save(self) -> None:
        try:
            temp = self.path.with_suffix(".tmp")
            temp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
            temp.replace(self.path)
        except OSError as exc:
            logger.warning("Could not save operation state: %s", exc)

    def _server(self, server_key: str) -> Dict[str, Any]:
        return self._data.setdefault("servers", {}).setdefault(
            server_key, {"current": None, "history": []}
        )

    def start(self, server_key: str, target: Dict[str, Any], operation: str) -> Dict[str, Any]:
        job = {
            "job_id": uuid.uuid4().hex,
            "server_key": server_key,
            "server": dict(target),
            "operation": operation,
            "state": "requested",
            "message": "Requesting Kodi",
            "started_at": utc_now(),
            "updated_at": utc_now(),
            "finished_at": None,
            "elapsed_seconds": 0,
        }
        with self._lock:
            server = self._server(server_key)
            server["current"] = job
            server["history"] = [job] + server.get("history", [])[: self.history_limit - 1]
            self._save()
        return dict(job)

    def update(self, server_key: str, job_id: str, **changes: Any) -> Optional[Dict[str, Any]]:
        with self._lock:
            server = self._server(server_key)
            current = server.get("current")
            if not current or current.get("job_id") != job_id:
                for item in server.get("history", []):
                    if item.get("job_id") == job_id:
                        current = item
                        break
            if not current:
                return None
            current.update(changes)
            current["updated_at"] = utc_now()
            try:
                started = datetime.fromisoformat(current["started_at"]).timestamp()
                ended = time.time()
                current["elapsed_seconds"] = max(0, int(ended - started))
            except (KeyError, TypeError, ValueError):
                pass
            if changes.get("state") in {"completed", "failed", "timed_out"}:
                current["finished_at"] = current.get("finished_at") or utc_now()
            self._save()
            return dict(current)

    def get_current(self, server_key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            current = self._server(server_key).get("current")
            return dict(current) if current else None

    def get_history(self, server_key: str, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(x) for x in self._server(server_key).get("history", [])[:limit]]

    def all_servers(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return {
                key: {
                    "current": dict(value.get("current")) if value.get("current") else None,
                    "history": [dict(x) for x in value.get("history", [])],
                }
                for key, value in self._data.get("servers", {}).items()
            }


_store = OperationStore()


def start(server_key: str, target: Dict[str, Any], operation: str) -> Dict[str, Any]:
    return _store.start(server_key, target, operation)


def update(server_key: str, job_id: str, **changes: Any) -> Optional[Dict[str, Any]]:
    return _store.update(server_key, job_id, **changes)


def get_current(server_key: str) -> Optional[Dict[str, Any]]:
    return _store.get_current(server_key)


def get_history(server_key: str, limit: int = 20) -> List[Dict[str, Any]]:
    return _store.get_history(server_key, limit)


def all_servers() -> Dict[str, Dict[str, Any]]:
    return _store.all_servers()
