#!/usr/bin/env python3
"""
Library Actions Module

Persists timestamps of library scan/clean actions per Kodi host.
Uses file-based storage with thread-safe access.
"""

import json
import logging
import os
import threading
from datetime import datetime
from typing import Dict, Optional

from kodi_client import canonical_server_key

logger = logging.getLogger(__name__)


class LibraryActionStore:
    """Thread-safe file-based store for library action timestamps"""

    def __init__(self):
        # Try /app/output first, fallback to ./output
        if os.path.exists("/app"):
            self._base_dir = "/app/output"
        else:
            self._base_dir = "./output"

        os.makedirs(self._base_dir, exist_ok=True)
        self._file_path = os.path.join(self._base_dir, "library_actions.json")
        self._lock = threading.Lock()

    def _load_data(self) -> Dict:
        """Load data from file"""
        if not os.path.exists(self._file_path):
            return {}

        try:
            with open(self._file_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

        if not isinstance(raw, dict):
            return {}
        return self._migrate_keys(raw)

    def _migrate_keys(self, data: Dict) -> Dict:
        """Merge legacy host keys into canonical scheme://host:port keys."""
        migrated: Dict[str, Dict[str, str]] = {}
        changed = False
        for host, actions in data.items():
            if not isinstance(actions, dict):
                continue
            key = canonical_server_key(str(host))
            if key != host:
                changed = True
            bucket = migrated.setdefault(key, {})
            for field, timestamp in actions.items():
                if not timestamp:
                    continue
                existing = bucket.get(field)
                if not existing or str(timestamp) > str(existing):
                    bucket[field] = timestamp
        if changed:
            try:
                with open(self._file_path, "w", encoding="utf-8") as f:
                    json.dump(migrated, f, indent=2)
            except OSError as exc:
                logger.warning("Failed to migrate library action keys: %s", exc)
        return migrated

    def _save_data(self, data: Dict):
        """Save data to file"""
        try:
            with open(self._file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            logger.warning("Failed to save library actions: %s", e)

    def record_action(self, host: str, action: str):
        """
        Record a library action timestamp

        Args:
            host: Kodi host identifier (e.g., "192.168.1.100:8080")
            action: One of "video_scan", "audio_scan", "video_clean", "music_clean"
        """
        valid_actions = ["video_scan", "audio_scan", "video_clean", "music_clean"]
        if action not in valid_actions:
            raise ValueError(f"Invalid action: {action}. Must be one of {valid_actions}")

        timestamp = datetime.now().isoformat()
        host_key = canonical_server_key(host)

        with self._lock:
            data = self._load_data()

            if host_key not in data:
                data[host_key] = {}

            field_name = f"last_{action}"
            data[host_key][field_name] = timestamp

            self._save_data(data)

    def get_actions(self, host: str) -> Dict[str, Optional[str]]:
        """
        Get all library action timestamps for a host

        Args:
            host: Kodi host identifier

        Returns:
            Dictionary with keys:
            - last_video_scan
            - last_audio_scan
            - last_video_clean
            - last_music_clean
            Values are ISO timestamp strings or None
        """
        host_key = canonical_server_key(host)
        with self._lock:
            data = self._load_data()
            host_data = data.get(host_key, {})

        return {
            "last_video_scan": host_data.get("last_video_scan"),
            "last_audio_scan": host_data.get("last_audio_scan"),
            "last_video_clean": host_data.get("last_video_clean"),
            "last_music_clean": host_data.get("last_music_clean"),
        }


# Global singleton instance
_action_store = LibraryActionStore()


def record_action(host: str, action: str):
    """
    Record a library action timestamp

    Args:
        host: Kodi host identifier
        action: One of "video_scan", "audio_scan", "video_clean", "music_clean"
    """
    _action_store.record_action(host, action)


def get_actions(host: str) -> Dict[str, Optional[str]]:
    """
    Get all library action timestamps for a host

    Args:
        host: Kodi host identifier

    Returns:
        Dictionary with last action timestamps (ISO format or None)
    """
    return _action_store.get_actions(host)
