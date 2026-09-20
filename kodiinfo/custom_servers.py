"""Persisted manually added Kodi servers (survives container rebuilds)."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from kodi_client import _normalize_manual_url, canonical_server_key

logger = logging.getLogger(__name__)

CUSTOM_SERVER_ID_START = 100
_ENC_PREFIX = "enc:v1:"


def _output_dir() -> Path:
    base = Path("/app/output" if os.path.exists("/app") else "./output")
    base.mkdir(parents=True, exist_ok=True)
    return base


def _secret_bytes() -> Optional[bytes]:
    secret = (os.getenv("WEB_SECRET_KEY") or "").strip()
    if not secret:
        return None
    return secret.encode("utf-8")


def _xor(data: bytes, key: bytes) -> bytes:
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def encrypt_secret(plain: str) -> str:
    text = plain or ""
    if not text:
        return ""
    secret = _secret_bytes()
    if not secret:
        return text
    nonce = os.urandom(16)
    key = hashlib.sha256(secret + nonce).digest()
    token = base64.urlsafe_b64encode(nonce + _xor(text.encode("utf-8"), key)).decode("ascii")
    return _ENC_PREFIX + token


def decrypt_secret(stored: str) -> str:
    raw = stored or ""
    if not raw:
        return ""
    if not raw.startswith(_ENC_PREFIX):
        return raw
    secret = _secret_bytes()
    if not secret:
        logger.warning("Stored custom-server password is encrypted but WEB_SECRET_KEY is unset")
        return ""
    try:
        blob = base64.urlsafe_b64decode(raw[len(_ENC_PREFIX) :].encode("ascii"))
        nonce, ct = blob[:16], blob[16:]
        key = hashlib.sha256(secret + nonce).digest()
        return _xor(ct, key).decode("utf-8")
    except (ValueError, TypeError, UnicodeDecodeError):
        logger.warning("Could not decrypt a stored Kodi password; treating it as empty")
        return ""


def resolve_custom_host(data: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    host = str(data.get("host") or "").strip()
    if host.lower().startswith("http://") or host.lower().startswith("https://"):
        return host.rstrip("/"), None
    return _normalize_manual_url(host, data.get("port", 8080), data.get("scheme", "http"))


class CustomServerStore:
    def __init__(self, path: Optional[str] = None):
        self.path = Path(path) if path else _output_dir() / "custom_servers.json"
        self._lock = threading.RLock()
        self._servers: List[Dict[str, Any]] = []
        with self._lock:
            self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self._servers = []
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("Could not load custom servers: %s", exc)
            self._servers = []
            return
        rows = raw.get("servers") if isinstance(raw, dict) else raw
        if not isinstance(rows, list):
            self._servers = []
            return
        loaded: List[Dict[str, Any]] = []
        stale_plaintext = False
        for entry in rows:
            if not isinstance(entry, dict):
                continue
            try:
                server_id = int(entry.get("id"))
            except (TypeError, ValueError):
                continue
            host = str(entry.get("host") or "").strip().rstrip("/")
            if not host or server_id < CUSTOM_SERVER_ID_START:
                continue
            encrypted = entry.get("password_enc") or ""
            legacy = entry.get("password") or ""
            if encrypted:
                password = decrypt_secret(encrypted)
            elif legacy:
                password = legacy
                stale_plaintext = True
            else:
                password = ""
            loaded.append(
                {
                    "id": str(server_id),
                    "host": host,
                    "username": str(entry.get("username") or ""),
                    "password": password,
                    "label": str(entry.get("label") or "").strip(),
                    "source": "custom",
                }
            )
        self._servers = loaded
        if stale_plaintext:
            self._save()

    def _save(self) -> None:
        dumped = []
        for row in self._servers:
            item: Dict[str, Any] = {
                "id": int(row["id"]),
                "host": row.get("host") or "",
                "username": row.get("username") or "",
                "label": row.get("label") or "",
            }
            secret = row.get("password") or ""
            if secret:
                enc = encrypt_secret(secret)
                if enc.startswith(_ENC_PREFIX):
                    item["password_enc"] = enc
                else:
                    item["password"] = enc
            dumped.append(item)
        try:
            temp = self.path.with_suffix(".tmp")
            temp.write_text(json.dumps({"version": 1, "servers": dumped}, indent=2), encoding="utf-8")
            temp.replace(self.path)
        except OSError as exc:
            logger.warning("Could not save custom servers: %s", exc)

    def list_servers(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(row) for row in self._servers]

    def as_presets(self) -> List[Dict[str, str]]:
        with self._lock:
            return [
                {
                    "id": row["id"],
                    "label": row.get("label") or row.get("host") or f"Server {row['id']}",
                    "host": row["host"],
                    "username": row.get("username") or "",
                    "password": row.get("password") or "",
                    "source": "custom",
                }
                for row in self._servers
            ]

    def _next_id(self) -> int:
        ids = []
        for row in self._servers:
            try:
                ids.append(int(row["id"]))
            except (TypeError, ValueError):
                continue
        if not ids:
            return CUSTOM_SERVER_ID_START
        return max(ids) + 1

    def add(
        self,
        host: str,
        username: str = "",
        password: str = "",
        label: str = "",
        existing_hosts: Optional[List[str]] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        host = (host or "").strip().rstrip("/")
        if not host:
            return None, "Host / IP is required"
        target = canonical_server_key(host)
        with self._lock:
            for row in self._servers:
                if canonical_server_key(row.get("host") or "") == target:
                    return None, "That Kodi host is already saved"
            for other in existing_hosts or []:
                if canonical_server_key(other) == target:
                    return None, "That Kodi host is already configured"
            server_id = str(self._next_id())
            row = {
                "id": server_id,
                "host": host,
                "username": username or "",
                "password": password or "",
                "label": (label or "").strip() or host,
                "source": "custom",
            }
            self._servers.append(row)
            self._save()
            return dict(row), None

    def update(
        self,
        server_id: str,
        host: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        label: Optional[str] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        with self._lock:
            current = next((row for row in self._servers if str(row.get("id")) == str(server_id)), None)
            if not current:
                return None, "Unknown custom server"
            if host is not None:
                host = host.strip().rstrip("/")
                if not host:
                    return None, "Host / IP is required"
                current["host"] = host
            if username is not None:
                current["username"] = username
            if password is not None:
                current["password"] = password
            if label is not None:
                current["label"] = (label or "").strip() or current.get("host") or current["id"]
            self._save()
            return dict(current), None

    def delete(self, server_id: str) -> Tuple[bool, Optional[str]]:
        with self._lock:
            before = len(self._servers)
            self._servers = [row for row in self._servers if str(row.get("id")) != str(server_id)]
            if len(self._servers) == before:
                return False, "Unknown custom server"
            self._save()
            return True, None


_store = CustomServerStore()


def list_servers() -> List[Dict[str, Any]]:
    return _store.list_servers()


def as_presets() -> List[Dict[str, str]]:
    return _store.as_presets()


def add(
    host: str,
    username: str = "",
    password: str = "",
    label: str = "",
    existing_hosts: Optional[List[str]] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    return _store.add(host, username, password, label, existing_hosts=existing_hosts)


def update(
    server_id: str,
    host: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    label: Optional[str] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    return _store.update(server_id, host=host, username=username, password=password, label=label)


def delete(server_id: str) -> Tuple[bool, Optional[str]]:
    return _store.delete(server_id)


def merged_presets(env_presets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Env presets first, then saved custom hosts that are not duplicates."""
    seen = set()
    out: List[Dict[str, Any]] = []
    for preset in env_presets or []:
        row = dict(preset)
        row.setdefault("source", "env")
        out.append(row)
        seen.add(canonical_server_key(str(row.get("host") or "")))
    for row in as_presets():
        key = canonical_server_key(str(row.get("host") or ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def public_payload(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "host": row.get("host") or "",
        "label": row.get("label") or row.get("host") or "",
        "source": row.get("source") or "custom",
        "editable": True,
        "has_auth": bool(row.get("username")),
    }
