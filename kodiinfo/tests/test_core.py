"""Unit tests for credential fallback, URL parsing, tokens, and connection resolve."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Ensure project root on path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from connection_tokens import TokenStore, issue_token, get_connection
from kodi_client import (
    KodiLibraryProbe,
    _normalize_manual_url,
    _slot_kodi_credentials,
    clamp_recent_limit,
    connection_dict_for_preset,
    recent_limit_from_env,
    resolve_start_load_connection,
)
import library_actions


class TestUrlParse(unittest.TestCase):
    def test_normalize_manual_url(self):
        url, err = _normalize_manual_url("192.168.1.10", 6668, "http")
        self.assertIsNone(err)
        self.assertEqual(url, "http://192.168.1.10:6668")

    def test_probe_parses_host_port_url(self):
        p = KodiLibraryProbe("http://192.168.0.19:6666", None, "u", "p")
        self.assertEqual(p.host, "192.168.0.19")
        self.assertEqual(p.port, 6666)
        self.assertEqual(p.scheme, "http")
        self.assertEqual(p.base_url, "http://192.168.0.19:6666/jsonrpc")

    def test_probe_parses_bare_host_port(self):
        p = KodiLibraryProbe("192.168.0.30:6668")
        self.assertEqual(p.host, "192.168.0.30")
        self.assertEqual(p.port, 6668)

    def test_probe_userinfo_in_url(self):
        p = KodiLibraryProbe("http://kodi:secret@192.168.1.5:8080")
        self.assertEqual(p.username, "kodi")
        self.assertEqual(p.password, "secret")
        self.assertEqual(p.host, "192.168.1.5")


class TestCredentials(unittest.TestCase):
    def test_slot_falls_back_to_global(self):
        with mock.patch.dict(
            os.environ,
            {
                "KODI_USERNAME": "global_user",
                "KODI_PASSWORD": "global_pass",
                "KODI_USERNAME_3": "",
                "KODI_PASSWORD_3": "",
            },
            clear=False,
        ):
            # Clear numbered if set
            os.environ.pop("KODI_USERNAME_3", None)
            os.environ.pop("KODI_PASSWORD_3", None)
            u, p = _slot_kodi_credentials(3)
            self.assertEqual(u, "global_user")
            self.assertEqual(p, "global_pass")

    def test_slot_override_wins(self):
        with mock.patch.dict(
            os.environ,
            {
                "KODI_USERNAME": "global_user",
                "KODI_PASSWORD": "global_pass",
                "KODI_USERNAME_2": "slot2",
                "KODI_PASSWORD_2": "pass2",
            },
            clear=False,
        ):
            u, p = _slot_kodi_credentials(2)
            self.assertEqual(u, "slot2")
            self.assertEqual(p, "pass2")


class TestResolveConnection(unittest.TestCase):
    def test_custom(self):
        conn, err = resolve_start_load_connection(
            {
                "custom": True,
                "host": "10.0.0.5",
                "port": 8080,
                "scheme": "http",
                "username": "a",
                "password": "b",
            },
            [],
        )
        self.assertIsNone(err)
        self.assertEqual(conn["host"], "http://10.0.0.5:8080")
        self.assertEqual(conn["username"], "a")

    def test_preset(self):
        presets = [
            {
                "id": "1",
                "label": "Living",
                "host": "http://192.168.1.1:8080",
                "username": "u",
                "password": "p",
            }
        ]
        conn, err = resolve_start_load_connection({"preset": "1"}, presets)
        self.assertIsNone(err)
        self.assertEqual(conn["host"], "http://192.168.1.1:8080")
        self.assertEqual(conn["preset_id"], "1")


class TestTokens(unittest.TestCase):
    def test_issue_and_get(self):
        tok = issue_token({"host": "http://x:1", "username": "u", "password": "secret"})
        conn = get_connection(tok)
        self.assertIsNotNone(conn)
        self.assertEqual(conn["password"], "secret")
        self.assertIsNone(get_connection("nope"))


class TestRecentLimit(unittest.TestCase):
    def test_clamp(self):
        self.assertEqual(clamp_recent_limit(100), 50)
        self.assertEqual(clamp_recent_limit(0), 1)
        self.assertEqual(clamp_recent_limit("20"), 20)

    def test_env_default(self):
        with mock.patch.dict(os.environ, {"RECENT_LIMIT": "20"}, clear=False):
            self.assertEqual(recent_limit_from_env(), 20)


class TestLibraryActions(unittest.TestCase):
    def test_record_and_get(self):
        with tempfile.TemporaryDirectory() as td:
            store = library_actions.LibraryActionStore()
            store._base_dir = td
            store._file_path = os.path.join(td, "library_actions.json")
            store.record_action("http://192.168.0.19:6666", "video_scan")
            store.record_action("http://192.168.0.19:6666", "video_clean")
            a = store.get_actions("http://192.168.0.19:6666")
            self.assertIsNotNone(a["last_video_scan"])
            self.assertIsNotNone(a["last_video_clean"])
            self.assertIsNone(a["last_audio_scan"])


class TestRpcErrorFormat(unittest.TestCase):
    def test_format(self):
        from webapp import _format_kodi_rpc_error

        msg = _format_kodi_rpc_error(
            {"message": "CleanLibrary is not possible while scanning for media info"}
        )
        self.assertIn("CleanLibrary", msg)


if __name__ == "__main__":
    unittest.main()
