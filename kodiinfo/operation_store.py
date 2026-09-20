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
_TERMINAL_STATES = {"completed", "failed", "timed_out"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


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
            self._reconcile_all_servers()

    def _mark_terminal(self, job: Dict[str, Any], state: str, message: str) -> None:
        job["state"] = state
        job["message"] = message
        job["updated_at"] = utc_now()
        if not job.get("finished_at"):
            job["finished_at"] = utc_now()
        try:
            started = datetime.fromisoformat(job["started_at"]).timestamp()
            ended = datetime.fromisoformat(job["finished_at"]).timestamp()
            job["elapsed_seconds"] = max(0, int(ended - started))
        except (KeyError, TypeError, ValueError):
            pass

    def _collect_active_jobs(self, server: Dict[str, Any]) -> List[Dict[str, Any]]:
        jobs: List[Dict[str, Any]] = []
        seen = set()
        current = server.get("current")
        if current and current.get("state") in _ACTIVE_STATES:
            job_id = current.get("job_id")
            if job_id and job_id not in seen:
                jobs.append(current)
                seen.add(job_id)
        for item in server.get("history", []):
            job_id = item.get("job_id")
            if not job_id or job_id in seen:
                continue
            if item.get("state") in _ACTIVE_STATES:
                jobs.append(item)
                seen.add(job_id)
        return jobs

    def _stale_active_reason(self, job: Dict[str, Any]) -> tuple[bool, str]:
        state = job.get("state")
        if state not in _ACTIVE_STATES:
            return False, ""
        try:
            started = datetime.fromisoformat(job["started_at"]).timestamp()
            updated = datetime.fromisoformat(job["updated_at"]).timestamp()
            now = time.time()
            status_timeout = max(3600.0, _env_float("LIBRARY_STATUS_TIMEOUT_SECONDS", 86400))
            max_scan = max(7200.0, _env_float("LIBRARY_MAX_SCAN_SECONDS", 43200))
            grace = max(60.0, _env_float("LIBRARY_STATUS_GRACE_SECONDS", 7200))
            op = str(job.get("operation") or "")
            is_clean = op.endswith(".Clean")
            max_duration = (
                max(7200.0, _env_float("LIBRARY_CLEAN_TIMEOUT_SECONDS", 86400))
                if is_clean
                else max_scan
            )
            if state == "running":
                if now - updated > status_timeout:
                    return True, (
                        "Clean status lost contact with Kodi"
                        if is_clean
                        else "Scan status lost contact with Kodi"
                    )
                if now - started > max_duration:
                    return True, (
                        "Clean exceeded maximum expected duration"
                        if is_clean
                        else "Scan exceeded maximum expected duration"
                    )
            elif state == "accepted":
                if now - updated > grace:
                    return True, "Operation status expired; Kodi completion could not be confirmed"
            elif state == "requested":
                request_timeout = max(120.0, _env_float("LIBRARY_STATUS_TIMEOUT_SECONDS", 1800))
                if now - updated > request_timeout:
                    return True, "Operation never started after restart"
        except (KeyError, TypeError, ValueError):
            return False, ""
        return False, ""

    def _reconcile_server(self, server_key: str) -> bool:
        server = self._server(server_key)
        changed = False
        for job in list(self._collect_active_jobs(server)):
            stale, message = self._stale_active_reason(job)
            if stale:
                terminal_state = "failed" if job.get("state") == "requested" else "completed"
                self._mark_terminal(job, terminal_state, message)
                changed = True

        actives = self._collect_active_jobs(server)
        if len(actives) > 1:
            actives.sort(key=lambda row: row.get("started_at") or "", reverse=True)
            for job in actives[1:]:
                self._mark_terminal(job, "completed", "Superseded by a newer library operation")
                changed = True
            server["current"] = actives[0]
            changed = True
        elif len(actives) == 1:
            if server.get("current") is not actives[0]:
                server["current"] = actives[0]
                changed = True
        return changed

    def _reconcile_all_servers(self) -> None:
        changed = False
        for server_key in list(self._data.get("servers", {}).keys()):
            if self._reconcile_server(server_key):
                changed = True
        if changed:
            self._save()

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
            for prior in self._collect_active_jobs(server):
                self._mark_terminal(
                    prior,
                    "completed",
                    "Superseded by a newer library operation",
                )
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
            if self._reconcile_server(server_key):
                self._save()
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
                        stale, message = self._stale_active_reason(current)
                        if stale:
                            self._mark_terminal(current, "completed", message)
                            self._save()
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
        changed = False
        with self._lock:
            for stored_key, bucket in self._data.get("servers", {}).items():
                if canonical_server_key(stored_key) != target:
                    continue
                if self._reconcile_server(stored_key):
                    changed = True
                bucket = self._server(stored_key)
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
        if changed:
            self._save()
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
