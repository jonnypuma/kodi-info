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

from kodi_client import canonical_server_key

logger = logging.getLogger(__name__)

_ACTIVE_STATES = {"requested", "running", "accepted"}


def _enrich_elapsed(item: Dict[str, Any]) -> Dict[str, Any]:
    try:
        started = datetime.fromisoformat(item["started_at"]).timestamp()
        if item.get("finished_at"):
            ended = datetime.fromisoformat(item["finished_at"]).timestamp()
            item["elapsed_seconds"] = max(0, int(ended - started))
        elif item.get("state") in _ACTIVE_STATES:
            item["elapsed_seconds"] = max(0, int(time.time() - started))
    except (KeyError, TypeError, ValueError):
        pass
    return item


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
            self._migrate_server_keys()

    def _migrate_server_keys(self) -> None:
        servers = self._data.get("servers", {})
        if not servers:
            return
        migrated: Dict[str, Dict[str, Any]] = {}
        changed = False
        for key, value in servers.items():
            new_key = canonical_server_key(str(key))
            if new_key != key:
                changed = True
            bucket = migrated.setdefault(new_key, {"current": None, "history": []})
            incoming = value.get("current")
            existing = bucket.get("current")
            if incoming and (
                not existing
                or (
                    incoming.get("state") in _ACTIVE_STATES
                    and existing.get("state") not in _ACTIVE_STATES
                )
                or (incoming.get("updated_at") or "") > (existing.get("updated_at") or "")
            ):
                bucket["current"] = incoming
            seen = {item.get("job_id") for item in bucket.get("history", [])}
            merged_history = list(bucket.get("history", []))
            for item in value.get("history", []):
                job_id = item.get("job_id")
                if job_id in seen:
                    continue
                merged_history.append(item)
                seen.add(job_id)
            merged_history.sort(key=lambda row: row.get("started_at") or "", reverse=True)
            bucket["history"] = merged_history[: self.history_limit]
        if changed or migrated != servers:
            self._data["servers"] = migrated
            self._save()

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
            if current and current.get("state") in {"requested", "running", "accepted"}:
                try:
                    started = datetime.fromisoformat(current["started_at"]).timestamp()
                    current["elapsed_seconds"] = max(0, int(time.time() - started))
                except (KeyError, TypeError, ValueError):
                    pass
                try:
                    state = current.get("state")
                    if state == "running":
                        pass
                    elif state == "accepted":
                        env_name = "LIBRARY_STATUS_GRACE_SECONDS"
                        default_timeout = "7200"
                        timeout = max(60.0, float(os.getenv(env_name, default_timeout)))
                        updated = datetime.fromisoformat(current["updated_at"]).timestamp()
                        if time.time() - updated > timeout:
                            current.update(
                                {
                                    "state": "completed",
                                    "message": "Operation status expired; Kodi completion could not be confirmed",
                                    "finished_at": utc_now(),
                                    "updated_at": utc_now(),
                                    "elapsed_seconds": int(
                                        time.time()
                                        - datetime.fromisoformat(current["started_at"]).timestamp()
                                    ),
                                }
                            )
                            self._save()
                    elif state == "requested":
                        timeout = max(120.0, float(os.getenv("LIBRARY_STATUS_TIMEOUT_SECONDS", "1800")))
                        updated = datetime.fromisoformat(current["updated_at"]).timestamp()
                        if time.time() - updated > timeout:
                            current.update(
                                {
                                    "state": "failed",
                                    "message": "Operation never started after restart",
                                    "finished_at": utc_now(),
                                    "updated_at": utc_now(),
                                    "elapsed_seconds": int(
                                        time.time()
                                        - datetime.fromisoformat(current["started_at"]).timestamp()
                                    ),
                                }
                            )
                            self._save()
                except (KeyError, TypeError, ValueError):
                    pass
            return dict(current) if current else None

    def get_history(self, server_key: str, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(x) for x in self._server(server_key).get("history", [])[:limit]]

    def find_for_host(self, host: str, history_limit: int = 20) -> tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        """Read operation state for a host without mutating stored job state."""
        target = canonical_server_key(str(host or ""))
        current: Optional[Dict[str, Any]] = None
        history: List[Dict[str, Any]] = []
        seen_jobs = set()
        with self._lock:
            for stored_key, bucket in self._data.get("servers", {}).items():
                if canonical_server_key(stored_key) != target:
                    continue
                raw_current = bucket.get("current")
                if raw_current:
                    item = _enrich_elapsed(dict(raw_current))
                    if not current or (item.get("updated_at") or "") > (current.get("updated_at") or ""):
                        current = item
                for row in bucket.get("history", []):
                    job_id = row.get("job_id")
                    if job_id in seen_jobs:
                        continue
                    history.append(_enrich_elapsed(dict(row)))
                    seen_jobs.add(job_id)
        history.sort(key=lambda row: row.get("started_at") or "", reverse=True)
        if not current:
            for item in history:
                if item.get("state") in _ACTIVE_STATES:
                    current = item
                    break
        return current, history[:history_limit]

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


def find_for_host(host: str, history_limit: int = 20) -> tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    return _store.find_for_host(host, history_limit=history_limit)


def all_servers() -> Dict[str, Dict[str, Any]]:
    return _store.all_servers()
