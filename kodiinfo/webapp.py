#!/usr/bin/env python3
"""Flask web application for Kodi library statistics (JSON API + SPA)."""

from __future__ import annotations

import logging
import hmac
import os
import secrets
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests
from flask import Flask, jsonify, request, send_file, send_from_directory, session

import connection_tokens
import custom_servers
import library_actions
import operation_store
from kodi_client import (
    KodiLibraryProbe,
    LibraryStats,
    RecentlyAdded,
    _watched_episodes_paginated,
    canonical_server_key,
    clamp_recent_limit,
    collect_preset_kodi_servers,
    connection_dict_for_preset,
    recent_limit_from_env,
    resolve_start_load_connection,
    stats_to_dict,
)

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
APP_VERSION = "1.1.0"
TRACE_LEVEL = 5
LIBRARY_COMMANDS = {
    "VideoLibrary.Scan": ("video_scan", 60.0),
    "AudioLibrary.Scan": ("audio_scan", 60.0),
    "VideoLibrary.Clean": ("video_clean", 120.0),
    "AudioLibrary.Clean": ("music_clean", 120.0),
}
logging.addLevelName(TRACE_LEVEL, "TRACE")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def is_clean_operation(method: str) -> bool:
    return str(method or "").endswith(".Clean")


def library_http_timeout(method: str, default_wait: float) -> float:
    """HTTP read timeout for the initial Kodi JSON-RPC call.

    Scan returns quickly (accepted), then we poll IsScanning*. Clean is often
    a blocking RPC (showdialogs default true / CleanLibraryModal) that only
    returns when the database cleanup finishes — 120s is far too short.
    """
    if is_clean_operation(method):
        return max(120.0, _env_float("LIBRARY_CLEAN_TIMEOUT_SECONDS", 86400.0))
    try:
        return max(5.0, float(default_wait))
    except (TypeError, ValueError):
        return 60.0


def _configure_logging() -> None:
    level_name = (os.getenv("LOG_LEVEL") or "INFO").strip().upper()
    level = TRACE_LEVEL if level_name == "TRACE" else getattr(logging, level_name, logging.INFO)
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
            stream=sys.stderr,
        )
    root.setLevel(level)
    logging.getLogger("werkzeug").setLevel(logging.WARNING if level <= logging.INFO else level)


_configure_logging()


def _format_kodi_rpc_error(rpc_err: Any) -> str:
    if isinstance(rpc_err, dict):
        msg = (rpc_err.get("message") or "").strip()
        data = rpc_err.get("data")
        if msg and data not in (None, ""):
            return f"{msg} ({data})"
        if msg:
            return msg
        if data not in (None, ""):
            return str(data)
    return str(rpc_err)


def create_app(web_port: int = 5005, container_host: str = "localhost") -> Flask:
    app = Flask(
        __name__,
        static_folder=str(BASE_DIR / "static"),
        template_folder=str(BASE_DIR / "templates"),
    )
    secret = (os.getenv("WEB_SECRET_KEY") or "").strip()
    if not secret:
        secret = secrets.token_hex(32)
        logger.warning(
            "WEB_SECRET_KEY is unset — using a random key for this process. "
            "Sessions/tokens will not survive container restarts. Set WEB_SECRET_KEY in .env."
        )
    app.secret_key = secret
    basic_auth = (os.getenv("BASIC_AUTH") or "").strip()
    auth_user, auth_password = basic_auth.split(":", 1) if ":" in basic_auth else ("", "")
    auth_enabled = bool(auth_user and auth_password)
    if basic_auth and not auth_enabled:
        logger.warning("BASIC_AUTH is set but must use username:password; authentication disabled")
    app.config["AUTH_ENABLED"] = auth_enabled

    load_jobs: Dict[str, Dict[str, Any]] = {}
    load_lock = threading.Lock()
    preset_servers: List[Dict[str, Any]] = []

    def _reload_preset_servers() -> None:
        env = collect_preset_kodi_servers()
        preset_servers[:] = custom_servers.merged_presets(env)

    _reload_preset_servers()
    seen_hosts = set()
    for preset in preset_servers:
        host = str(preset.get("host") or "").strip()
        parsed = urlparse(host if "://" in host else "http://" + host)
        try:
            port = parsed.port or 8080
        except ValueError:
            port = 0
        canonical = (parsed.scheme.lower(), (parsed.hostname or "").lower(), port)
        if not parsed.hostname:
            logger.warning("Invalid Kodi preset endpoint: %s", host)
        if canonical in seen_hosts:
            logger.warning("Duplicate Kodi preset endpoint: %s", host)
        seen_hosts.add(canonical)

    _configure_logging()
    logger.setLevel(logging.getLogger().level)

    @app.before_request
    def require_auth():
        if not auth_enabled:
            return None
        allowed = {
            "index",
            "health",
            "ready",
            "auth_status",
            "login",
            "logout",
            "static",
            "favicon",
            "kodi_png",
            "movies_png",
            "tv_png",
            "music_png",
            "new_png",
            "refresh_png",
            "background_jpg",
            "artwork",
        }
        if request.endpoint in allowed or request.endpoint is None:
            return None
        if session.get("authenticated"):
            return None
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "message": "Authentication required"}), 401
        return jsonify({"success": False, "message": "Authentication required"}), 401

    def _token_from_request() -> Optional[str]:
        data = request.get_json(silent=True) or {}
        tok = (
            data.get("connection_token")
            or request.headers.get("X-Connection-Token")
            or request.args.get("token")
            or session.get("connection_token")
        )
        if tok is None:
            return None
        tok = str(tok).strip()
        return tok or None

    def _conn_from_token() -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        tok = _token_from_request()
        if not tok:
            return None, "Missing connection token — open the home page and choose a server"
        conn = connection_tokens.get_connection(tok)
        if not conn or not conn.get("host"):
            return None, "Connection token expired or invalid — choose a server again"
        return conn, None

    def _server_log_label(conn: Optional[Dict[str, Any]]) -> str:
        if not conn:
            return "(unknown server)"
        host = (conn.get("host") or "").strip() or "?"
        label = (conn.get("label") or "").strip()
        preset = conn.get("preset_id")
        parts = []
        if label:
            parts.append(label)
        parts.append(host)
        if preset is not None and str(preset).strip() != "":
            parts.append(f"preset={preset}")
        return " · ".join(parts)

    def _server_key(conn: Dict[str, Any]) -> str:
        """Stable identity used for persisted per-server state."""
        return canonical_server_key(
            str(conn.get("host") or ""),
            conn.get("port"),
            str(conn.get("scheme") or ""),
        )

    def _conn_from_operation(server_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        preset_id = server_info.get("preset_id")
        if preset_id is not None and str(preset_id).strip() != "":
            for preset in preset_servers:
                if str(preset.get("id")) == str(preset_id):
                    return connection_dict_for_preset(preset)
        host = str(server_info.get("host") or "").strip()
        if not host:
            return None
        target_key = canonical_server_key(host)
        for preset in preset_servers:
            if canonical_server_key(preset["host"]) == target_key:
                return connection_dict_for_preset(preset)
        return {
            "host": host,
            "username": "",
            "password": "",
            "label": server_info.get("label") or host,
            "preset_id": preset_id,
        }

    def _resume_in_progress_operations() -> None:
        for server_key, bucket in operation_store.all_servers().items():
            current = bucket.get("current")
            if not current or current.get("state") not in {"requested", "running", "accepted"}:
                continue
            method = str(current.get("operation") or "")
            command = LIBRARY_COMMANDS.get(method)
            if not command:
                continue
            action_key, max_wait = command
            conn = _conn_from_operation(current.get("server") or {})
            if not conn:
                logger.warning(
                    "Cannot resume library operation %s for %s — missing connection",
                    (current.get("job_id") or "")[:8],
                    server_key,
                )
                continue
            job = dict(current)
            job["server_key"] = server_key
            logger.info(
                "Resuming library operation %s (%s) for %s",
                (job.get("job_id") or "")[:8],
                method,
                _server_log_label(conn),
            )
            threading.Thread(
                target=_run_library_job,
                args=(job, dict(conn), method, action_key, max_wait),
                kwargs={"resume_monitor_only": True},
                daemon=True,
            ).start()

    def _operation_state_for_conn(conn: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        current, history = operation_store.find_for_host(str(conn.get("host") or ""))
        if current and current.get("state") in {"completed", "failed", "timed_out"}:
            current = None
        return current, history

    def _operation_json(conn: Dict[str, Any]) -> Dict[str, Any]:
        current, history = _operation_state_for_conn(conn)
        return {"current_operation": current, "operation_history": history}

    def _preset_conn(preset_id: str) -> Optional[Dict[str, Any]]:
        for preset in preset_servers:
            if str(preset.get("id")) == str(preset_id):
                return {
                    "host": preset["host"],
                    "username": preset.get("username") or "",
                    "password": preset.get("password") or "",
                    "label": preset.get("label") or preset["host"],
                    "preset_id": preset.get("id"),
                }
        return None

    def _conn_for_operation_lookup() -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        preset_id = (request.args.get("preset") or "").strip()
        if preset_id:
            for preset in preset_servers:
                if str(preset.get("id")) == preset_id:
                    return connection_dict_for_preset(preset), None
        host = (request.args.get("host") or "").strip()
        if host:
            return {
                "host": host,
                "username": "",
                "password": "",
                "label": host,
                "preset_id": None,
            }, None
        tok = _token_from_request()
        conn = None
        err = None
        if tok:
            conn, err = _conn_from_token()
            if conn:
                return conn, None
        if tok:
            return None, err or "Connection token expired or invalid"
        return None, err or "Missing connection token — open the home page and choose a server"

    def _server_target(conn: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "label": conn.get("label") or conn.get("host") or "",
            "host": conn.get("host") or "",
            "preset_id": conn.get("preset_id"),
        }

    def _kodi_rpc_post(
        probe: KodiLibraryProbe,
        method: str,
        read_timeout: Optional[float],
    ) -> Tuple[Optional[dict], Optional[str]]:
        payload = {"jsonrpc": "2.0", "method": method, "id": 1}
        response_obj = None
        try:
            response_obj = requests.post(
                probe.base_url,
                headers={"Content-Type": "application/json"},
                json=payload,
                auth=probe.auth,
                timeout=(10, read_timeout),
            )
            response_obj.raise_for_status()
            body = response_obj.json()
        except requests.Timeout:
            return None, "timeout"
        except requests.RequestException as e:
            return None, f"Request error: {str(e)}"
        except ValueError:
            return None, "Invalid response from Kodi (not JSON)"
        except Exception as e:
            return None, f"Error: {str(e)}"

        rpc_err = body.get("error")
        if rpc_err:
            return None, _format_kodi_rpc_error(rpc_err)
        if body.get("result") == "OK":
            return body, None
        return None, f"Unexpected response from Kodi: {body.get('result', body)}"

    def _run_library_job(
        job: Dict[str, Any],
        conn: Dict[str, Any],
        method: str,
        action_key: str,
        max_wait_s: float,
        resume_monitor_only: bool = False,
    ) -> None:
        server_key = job["server_key"]
        job_id = job["job_id"]
        target = _server_log_label(conn)
        probe = KodiLibraryProbe(
            conn["host"], None, conn.get("username") or "", conn.get("password") or ""
        )
        media = "music" if method.startswith("AudioLibrary.") else "video"
        try:
            status_grace = max(60.0, float(os.getenv("LIBRARY_STATUS_GRACE_SECONDS", "7200")))
            status_timeout = max(status_grace, float(os.getenv("LIBRARY_STATUS_TIMEOUT_SECONDS", "86400")))
        except ValueError:
            status_grace, status_timeout = 7200.0, 86400.0

        if is_clean_operation(method):
            _run_library_clean_job(
                job,
                conn,
                probe,
                method,
                action_key,
                media,
                target,
                resume_monitor_only=resume_monitor_only,
            )
            return

        if resume_monitor_only:
            prior_state = str(job.get("state") or "")
            observed_scanning = prior_state == "running"
            last_scan_seen = time.time() if observed_scanning else None
            status_started = time.time()
            operation_store.update(
                server_key,
                job_id,
                message=job.get("message") or "Resuming operation monitor after restart",
            )
            logger.info("Resumed library operation monitor: %s → %s", method, target)
        else:
            operation_store.update(server_key, job_id, state="running", message="Contacting Kodi")
            response, err = _kodi_rpc_post(probe, method, read_timeout=library_http_timeout(method, max_wait_s))
            if err:
                logger.warning("Library action failed: %s → %s — %s", method, target, err)
                operation_store.update(
                    server_key,
                    job_id,
                    state="timed_out" if err == "timeout" else "failed",
                    message=err,
                )
                return
            operation_store.update(
                server_key,
                job_id,
                state="accepted",
                message="Kodi accepted the request; completion is not confirmed by HTTP RPC",
            )
            logger.info("Library action accepted: %s → %s", method, target)
            try:
                library_actions.record_action(conn["host"], action_key)
            except Exception:
                logger.exception("Could not persist library action (job=%s)", job_id[:8])
            status_started = time.time()
            observed_scanning = False
            last_scan_seen = None

        while True:
            scan_status = probe.get_scan_status(media)
            elapsed = time.time() - status_started
            if scan_status is True:
                observed_scanning = True
                last_scan_seen = time.time()
                operation_store.update(
                    server_key,
                    job_id,
                    state="running",
                    message=f"Kodi is scanning the {media} library",
                )
            elif observed_scanning and scan_status is False:
                operation_store.update(
                    server_key,
                    job_id,
                    state="completed",
                    message="Kodi reports that the library scan has finished",
                )
                logger.info("Library action completed: %s → %s", method, target)
                return
            elif scan_status is None and probe._scan_status_unavailable:
                if not observed_scanning and elapsed >= status_grace:
                    observed_scanning = True
                if observed_scanning:
                    last_scan_seen = time.time()
                    operation_store.update(
                        server_key,
                        job_id,
                        state="running",
                        message=(
                            f"Kodi is scanning the {media} library "
                            "(Kodi does not report scan progress)"
                        ),
                    )
            elif not observed_scanning and elapsed >= status_grace:
                operation_store.update(
                    server_key,
                    job_id,
                    state="completed",
                    message="Kodi accepted the request; scan completion could not be confirmed",
                )
                logger.info("Library action status expired: %s → %s", method, target)
                return
            elif observed_scanning and last_scan_seen is not None and time.time() - last_scan_seen >= status_timeout:
                operation_store.update(
                    server_key,
                    job_id,
                    state="timed_out",
                    message="Timed out waiting for Kodi to report the scan as finished",
                )
                logger.warning("Library action status timed out: %s → %s", method, target)
                return
            time.sleep(5)

    def _run_library_clean_job(
        job: Dict[str, Any],
        conn: Dict[str, Any],
        probe: KodiLibraryProbe,
        method: str,
        action_key: str,
        media: str,
        target: str,
        resume_monitor_only: bool = False,
    ) -> None:
        """Clean is not IsScanning*. Default Kodi Clean RPC blocks until cleanup finishes."""
        server_key = job["server_key"]
        job_id = job["job_id"]
        message = f"Kodi is cleaning the {media} library"
        timeout_s = library_http_timeout(method, 86400.0)
        stop_heartbeat = threading.Event()

        def heartbeat() -> None:
            while not stop_heartbeat.wait(10):
                operation_store.update(server_key, job_id, state="running", message=message)

        operation_store.update(server_key, job_id, state="running", message=message)
        hb = threading.Thread(target=heartbeat, name=f"clean-hb-{job_id[:8]}", daemon=True)
        hb.start()
        try:
            if resume_monitor_only:
                logger.info("Resumed library clean monitor: %s → %s", method, target)
                deadline = time.time() + timeout_s
                try:
                    started = datetime.fromisoformat(str(job.get("started_at") or "")).timestamp()
                    deadline = started + timeout_s
                except (TypeError, ValueError):
                    pass
                while time.time() < deadline:
                    ping = probe._make_request("JSONRPC.Ping", {}, timeout=10)
                    if ping.get("result") == "pong":
                        try:
                            library_actions.record_action(conn["host"], action_key)
                        except Exception:
                            logger.exception("Could not persist library action (job=%s)", job_id[:8])
                        operation_store.update(
                            server_key,
                            job_id,
                            state="completed",
                            message="Kodi reports that the library clean has finished",
                        )
                        logger.info("Library clean completed after resume: %s → %s", method, target)
                        return
                    time.sleep(5)
                operation_store.update(
                    server_key,
                    job_id,
                    state="timed_out",
                    message="Timed out waiting for Kodi to finish cleaning",
                )
                logger.warning("Library clean timed out after resume: %s → %s", method, target)
                return

            _, err = _kodi_rpc_post(probe, method, read_timeout=timeout_s)
            if err == "timeout":
                operation_store.update(
                    server_key,
                    job_id,
                    state="timed_out",
                    message="Timed out waiting for Kodi to finish cleaning",
                )
                logger.warning("Library clean timed out: %s → %s", method, target)
                return
            if err:
                logger.warning("Library action failed: %s → %s — %s", method, target, err)
                operation_store.update(server_key, job_id, state="failed", message=err)
                return
            try:
                library_actions.record_action(conn["host"], action_key)
            except Exception:
                logger.exception("Could not persist library action (job=%s)", job_id[:8])
            operation_store.update(
                server_key,
                job_id,
                state="completed",
                message="Kodi reports that the library clean has finished",
            )
            logger.info("Library action completed: %s → %s", method, target)
        finally:
            stop_heartbeat.set()

    def _dispatch_library_command(
        method: str, action_key: str, max_wait_s: float
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        conn, err = _conn_from_token()
        if not conn:
            logger.warning("Library action %s refused — no connection: %s", method, err)
            return None, err or "No connection"
        target = _server_log_label(conn)
        logger.info("Library action requested: %s → %s", method, target)
        server_key = _server_key(conn)
        job = operation_store.start(server_key, _server_target(conn), method)
        job["server_key"] = server_key
        logger.info(
            "Library action queued: %s → %s (job=%s)",
            method,
            target,
            job["job_id"][:8],
        )
        threading.Thread(
            target=_run_library_job,
            args=(job, dict(conn), method, action_key, max_wait_s),
            daemon=True,
        ).start()
        return job, None

    def update_job(job_id: str, progress: int, message: str = None, status: str = "running"):
        with load_lock:
            job = load_jobs.get(job_id)
            if not job:
                return
            job["progress"] = min(100, max(0, int(progress)))
            if message is not None:
                job["message"] = message
            job["status"] = status
            job["updated_at"] = time.time()

    def run_load_job(job_id: str, conn: Dict[str, Any], recent_limit: int):
        target = _server_log_label(conn)
        started = time.time()
        logger.info("Library load started: %s (job=%s recent=%s)", target, job_id[:8], recent_limit)
        try:
            update_job(job_id, 5, "Connecting")
            probe = KodiLibraryProbe(
                conn["host"], None, conn.get("username") or "", conn.get("password") or ""
            )
            if not probe.connect():
                msg = probe.last_error or f"Unable to connect to Kodi at {conn.get('host', '')}"
                logger.warning("Library load connect failed: %s — %s", target, msg)
                update_job(job_id, 100, msg, status="error")
                return

            stats = LibraryStats()
            update_job(job_id, 10, "Movies")
            movies_result = probe._make_request(
                "VideoLibrary.GetMovies",
                {"properties": ["playcount"], "limits": {"start": 0, "end": 100000}},
            )
            movies = movies_result.get("result", {}).get("movies", [])
            limits = movies_result.get("result", {}).get("limits", {})
            stats.total_movies = limits.get("total", 0)
            watched_movies = 0
            movie_count = len(movies)
            if movie_count == 0:
                update_job(job_id, 25, "Movies")
            else:
                step = max(1, movie_count // 20)
                for idx, movie in enumerate(movies, 1):
                    if movie.get("playcount", 0) > 0:
                        watched_movies += 1
                    if idx % step == 0 or idx == movie_count:
                        update_job(job_id, 10 + int(15 * (idx / movie_count)), "Movies")
            stats.watched_movies = watched_movies

            update_job(job_id, 30, "TV shows")
            tv_shows_result = probe._make_request(
                "VideoLibrary.GetTVShows", {"limits": {"start": 0, "end": 100000}}
            )
            stats.total_tv_shows = tv_shows_result.get("result", {}).get("limits", {}).get("total", 0)
            update_job(job_id, 35, "TV stats")
            ep_quick = probe._make_request(
                "VideoLibrary.GetEpisodes", {"limits": {"start": 0, "end": 1}}, timeout=60
            )
            stats.total_episodes = int(
                (ep_quick.get("result") or {}).get("limits", {}).get("total") or 0
            )
            stats_result = probe._make_request("VideoLibrary.GetStatistics", {}, timeout=30)
            if stats_result and "result" in stats_result:
                statistics = stats_result["result"].get("statistics", {})
                stats.watched_episodes = int(statistics.get("episode.watched", 0) or 0)
                if stats.total_episodes <= 0:
                    stats.total_episodes = int(statistics.get("episode", 0) or 0)
                update_job(job_id, 45, "TV stats")
            elif stats.total_episodes > 0:
                update_job(job_id, 38, "Watched episodes")
                stats.watched_episodes, scan_total = _watched_episodes_paginated(probe)
                if stats.total_episodes <= 0 and scan_total > 0:
                    stats.total_episodes = scan_total
                update_job(job_id, 45, "TV stats")
            else:
                update_job(job_id, 36, "Episodes")
                episodes_result = probe._make_request(
                    "VideoLibrary.GetEpisodes",
                    {"properties": ["playcount"], "limits": {"start": 0, "end": 100000}},
                    timeout=120,
                )
                episodes = episodes_result.get("result", {}).get("episodes", [])
                stats.total_episodes = episodes_result.get("result", {}).get("limits", {}).get("total", 0)
                watched_episodes = 0
                episode_count = len(episodes)
                if episode_count == 0:
                    update_job(job_id, 45, "TV stats")
                else:
                    step = max(1, episode_count // 20)
                    for idx, episode in enumerate(episodes, 1):
                        if episode.get("playcount", 0) > 0:
                            watched_episodes += 1
                        if idx % step == 0 or idx == episode_count:
                            update_job(job_id, 36 + int(19 * (idx / episode_count)), "Episodes")
                stats.watched_episodes = watched_episodes

            if stats.total_episodes > 0 and stats.watched_episodes > stats.total_episodes:
                stats.watched_episodes = stats.total_episodes

            update_job(job_id, 58, "Artists")
            artists_result = probe._make_request(
                "AudioLibrary.GetArtists", {"limits": {"start": 0, "end": 100000}}
            )
            stats.total_artists = artists_result.get("result", {}).get("limits", {}).get("total", 0)
            update_job(job_id, 65, "Albums")
            albums_result = probe._make_request(
                "AudioLibrary.GetAlbums", {"limits": {"start": 0, "end": 100000}}
            )
            stats.total_albums = albums_result.get("result", {}).get("limits", {}).get("total", 0)
            update_job(job_id, 72, "Songs")
            songs_result = probe._make_request(
                "AudioLibrary.GetSongs", {"limits": {"start": 0, "end": 100000}}
            )
            stats.total_songs = songs_result.get("result", {}).get("limits", {}).get("total", 0)

            update_job(job_id, 78, "Recent")
            stats.recently_added = probe.get_recently_added_content(limit=recent_limit)

            update_job(job_id, 95, "Packaging")
            artwork_base = f"{probe.scheme}://{probe.host}:{probe.port}"
            payload = stats_to_dict(stats, probe, artwork_base, recent_limit)
            host_key = canonical_server_key(conn.get("host") or artwork_base)
            actions = library_actions.get_actions(host_key)
            op_current, op_history = _operation_state_for_conn(conn)
            label = conn.get("label") or host_key
            display = f"{label} — {host_key}" if label and label != host_key else host_key
            last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            with load_lock:
                job = load_jobs.get(job_id)
                if job is not None:
                    job["payload"] = {
                        "stats": payload,
                        "kodi_display": display,
                        "host": host_key,
                        "label": label,
                        "last_updated": last_updated,
                        "library_actions": actions,
                        "current_operation": op_current,
                        "operation_history": op_history,
                        "recent_limit": recent_limit,
                        "default_recent_limit": recent_limit_from_env(),
                    }
            update_job(job_id, 100, "Done", status="done")
            elapsed = time.time() - started
            logger.info(
                "Library load OK: %s in %.1fs (movies=%s shows=%s episodes=%s)",
                target,
                elapsed,
                stats.total_movies,
                stats.total_tv_shows,
                stats.total_episodes,
            )
        except Exception as e:
            logger.exception("Library load failed: %s — %s", target, e)
            update_job(job_id, 100, f"Error: {str(e)}", status="error")

    @app.route("/")
    def index():
        return send_from_directory(app.template_folder, "index.html")

    @app.route("/api/auth-status")
    def auth_status():
        return jsonify({"success": True, "enabled": auth_enabled, "authenticated": bool(session.get("authenticated"))})

    @app.route("/api/login", methods=["POST"])
    def login():
        if not auth_enabled:
            return jsonify({"success": True, "authenticated": True})
        data = request.get_json(silent=True) or {}
        user = str(data.get("username") or "")
        password = str(data.get("password") or "")
        valid = hmac.compare_digest(user, auth_user) and hmac.compare_digest(password, auth_password)
        if not valid:
            logger.warning("Web login failed for username %r", user[:64])
            return jsonify({"success": False, "message": "Invalid username or password"}), 401
        session["authenticated"] = True
        session.permanent = True
        return jsonify({"success": True, "authenticated": True})

    @app.route("/api/logout", methods=["POST"])
    def logout():
        session.clear()
        return jsonify({"success": True})

    def _public_server_row(preset: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": preset.get("id"),
            "label": preset.get("label") or preset.get("host"),
            "host": preset.get("host"),
            "source": preset.get("source") or "env",
            "editable": (preset.get("source") == "custom"),
            "has_auth": bool(preset.get("username")),
        }

    @app.route("/api/config")
    def api_config():
        presets = [_public_server_row(p) for p in preset_servers]
        return jsonify(
            {
                "version": APP_VERSION,
                "presets": presets,
                "default_recent_limit": recent_limit_from_env(),
                "recent_limit_options": [5, 10, 20, 50],
            }
        )

    @app.route("/api/servers")
    def api_servers():
        return jsonify({"success": True, "servers": [_public_server_row(p) for p in preset_servers]})

    @app.route("/api/servers", methods=["POST"])
    def api_create_server():
        payload = request.get_json(silent=True) or {}
        host, err = custom_servers.resolve_custom_host(payload)
        if err or not host:
            return jsonify({"success": False, "message": err or "Invalid address"}), 400
        existing = [str(p.get("host") or "") for p in preset_servers]
        server, err = custom_servers.add(
            host,
            payload.get("username") or "",
            payload.get("password") or "",
            payload.get("label") or "",
            existing_hosts=existing,
        )
        if err or not server:
            return jsonify({"success": False, "message": err or "Could not save server"}), 400
        _reload_preset_servers()
        logger.info("Saved custom Kodi server %s [%s]", server.get("label"), server.get("host"))
        return jsonify({"success": True, "server": custom_servers.public_payload(server)})

    @app.route("/api/servers/<server_id>", methods=["PUT", "PATCH"])
    def api_edit_server(server_id: str):
        current = next((p for p in preset_servers if str(p.get("id")) == str(server_id)), None)
        if not current or current.get("source") != "custom":
            return jsonify({"success": False, "message": "Only saved custom servers can be edited"}), 400
        payload = request.get_json(silent=True) or {}
        host = None
        if payload.get("host") is not None:
            host, err = custom_servers.resolve_custom_host(payload)
            if err or not host:
                return jsonify({"success": False, "message": err or "Invalid address"}), 400
        server, err = custom_servers.update(
            server_id,
            host=host,
            username=payload.get("username"),
            password=payload.get("password"),
            label=payload.get("label"),
        )
        if err or not server:
            return jsonify({"success": False, "message": err or "Could not update server"}), 400
        _reload_preset_servers()
        return jsonify({"success": True, "server": custom_servers.public_payload(server)})

    @app.route("/api/servers/<server_id>", methods=["DELETE"])
    def api_delete_server(server_id: str):
        current = next((p for p in preset_servers if str(p.get("id")) == str(server_id)), None)
        if not current or current.get("source") != "custom":
            return jsonify({"success": False, "message": "Only saved custom servers can be removed"}), 400
        ok, err = custom_servers.delete(server_id)
        if not ok:
            return jsonify({"success": False, "message": err or "Could not remove server"}), 400
        _reload_preset_servers()
        logger.info("Removed custom Kodi server %s", server_id)
        return jsonify({"success": True})

    def _overview_probe_timeout() -> float:
        try:
            return max(1.0, float(os.getenv("OVERVIEW_PROBE_TIMEOUT_SECONDS", "3")))
        except ValueError:
            return 3.0

    def _probe_overview_server(preset: Dict[str, Any], timeout: float) -> Dict[str, Any]:
        conn = {
            "host": preset["host"],
            "username": preset.get("username") or "",
            "password": preset.get("password") or "",
            "label": preset.get("label") or preset["host"],
            "preset_id": preset.get("id"),
        }
        probe = KodiLibraryProbe(conn["host"], None, conn["username"], conn["password"])
        ok, detail = probe.ping(timeout=timeout)
        current_operation, history = _operation_state_for_conn(conn)
        if current_operation and current_operation.get("state") in {
            "completed",
            "failed",
            "timed_out",
        }:
            current_operation = None
        return {
            "id": preset.get("id"),
            "label": conn["label"],
            "host": conn["host"],
            "reachable": bool(ok),
            "detail": detail,
            "kodi_version": probe.kodi_version or None,
            "actions": library_actions.get_actions(conn["host"]),
            "current_operation": current_operation,
            "history": history[:5],
            "source": preset.get("source") or "env",
            "editable": (preset.get("source") == "custom"),
        }

    @app.route("/api/server-overview")
    def server_overview():
        timeout = _overview_probe_timeout()
        if not preset_servers:
            return jsonify({"success": True, "servers": []})

        result: list[Optional[Dict[str, Any]]] = [None] * len(preset_servers)
        workers = min(len(preset_servers), 10)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(_probe_overview_server, preset, timeout): idx
                for idx, preset in enumerate(preset_servers)
            }
            for future in as_completed(futures):
                idx = futures[future]
                preset = preset_servers[idx]
                try:
                    result[idx] = future.result()
                except Exception as exc:
                    logger.warning(
                        "Server overview probe failed for %s: %s",
                        preset.get("label") or preset.get("host"),
                        exc,
                    )
                    result[idx] = {
                        "id": preset.get("id"),
                        "label": preset.get("label") or preset.get("host"),
                        "host": preset.get("host"),
                        "reachable": False,
                        "detail": str(exc),
                        "kodi_version": None,
                        "actions": library_actions.get_actions(preset.get("host") or ""),
                        "current_operation": None,
                        "history": [],
                        "source": preset.get("source") or "env",
                        "editable": (preset.get("source") == "custom"),
                    }
        return jsonify({"success": True, "servers": [item for item in result if item]})

    @app.route("/api/ensure-connection", methods=["POST"])
    def api_ensure_connection():
        """
        Issue/refresh an opaque connection token without loading the library.
        Used when serving a cached dashboard so Scan/Clean/Refresh still work.
        """
        data = request.get_json(silent=True) or {}
        resolved_conn, _ = resolve_start_load_connection(data, preset_servers)
        tok = (data.get("connection_token") or "").strip()
        if tok:
            conn = connection_tokens.get_connection(tok)
            if conn and conn.get("host"):
                connection_tokens.touch(tok)
                session["connection_token"] = tok
                session.permanent = True
                session.modified = True
                logger.info("Ensure-connection reused token → %s", _server_log_label(conn))
                op_conn = resolved_conn or conn
                payload = {
                    "success": True,
                    "connection_token": tok,
                    "host": conn.get("host"),
                    "label": conn.get("label") or "",
                }
                payload.update(_operation_json(op_conn))
                return jsonify(payload)

        conn, err = resolve_start_load_connection(data, preset_servers)
        if err or not conn:
            logger.warning("Ensure-connection resolve failed: %s", err or "Unable to resolve Kodi connection")
            return jsonify({"success": False, "message": err or "Unable to resolve Kodi connection"}), 400

        token = connection_tokens.issue_token(dict(conn))
        session["connection_token"] = token
        session["kodi_connection"] = {
            "host": conn["host"],
            "label": conn.get("label") or "",
            "preset_id": conn.get("preset_id"),
        }
        session.permanent = True
        session.modified = True
        logger.info("Ensure-connection issued token → %s", _server_log_label(conn))
        payload = {
            "success": True,
            "connection_token": token,
            "host": conn["host"],
            "label": conn.get("label") or "",
        }
        payload.update(_operation_json(conn))
        return jsonify(payload)

    @app.route("/api/start-load", methods=["POST"])
    def api_start_load():
        data = request.get_json(silent=True) or {}

        # Refresh with existing opaque token (no credentials in browser)
        tok = (data.get("connection_token") or "").strip()
        if tok and not data.get("custom") and not data.get("preset") and not data.get("server_id"):
            conn = connection_tokens.get_connection(tok)
            if not conn:
                logger.warning("Start-load refused — connection token expired or invalid")
                return jsonify(
                    {"success": False, "message": "Connection token expired — choose a server again"}
                ), 400
            recent_limit = clamp_recent_limit(data.get("recent_limit", recent_limit_from_env()))
            job_id = uuid.uuid4().hex
            with load_lock:
                load_jobs[job_id] = {
                    "status": "pending",
                    "progress": 0,
                    "message": "Starting",
                    "created_at": time.time(),
                    "updated_at": time.time(),
                    "payload": None,
                    "connection_token": tok,
                }
            threading.Thread(
                target=run_load_job, args=(job_id, dict(conn), recent_limit), daemon=True
            ).start()
            session["connection_token"] = tok
            session.permanent = True
            session.modified = True
            return jsonify({"job_id": job_id, "connection_token": tok})

        conn, err = resolve_start_load_connection(data, preset_servers)
        if err or not conn:
            logger.warning("Start-load resolve failed: %s", err or "Unable to resolve Kodi connection")
            return jsonify({"success": False, "message": err or "Unable to resolve Kodi connection"}), 400

        token = connection_tokens.issue_token(dict(conn))
        session["connection_token"] = token
        session["kodi_connection"] = {
            "host": conn["host"],
            "label": conn.get("label") or "",
            "preset_id": conn.get("preset_id"),
        }
        session.permanent = True
        session.modified = True

        recent_limit = clamp_recent_limit(data.get("recent_limit", recent_limit_from_env()))
        job_id = uuid.uuid4().hex
        with load_lock:
            load_jobs[job_id] = {
                "status": "pending",
                "progress": 0,
                "message": "Starting",
                "created_at": time.time(),
                "updated_at": time.time(),
                "payload": None,
                "connection_token": token,
            }
        threading.Thread(
            target=run_load_job, args=(job_id, dict(conn), recent_limit), daemon=True
        ).start()
        return jsonify({"job_id": job_id, "connection_token": token})

    # Backward-compatible alias
    @app.route("/start-load", methods=["POST", "GET"])
    def start_load_compat():
        if request.method == "GET":
            if not preset_servers:
                return jsonify({"success": False, "message": "No preset servers"}), 400
            data = {"preset": preset_servers[0]["id"]}
            # reuse POST body path via temporary request — just call resolve
            conn, err = resolve_start_load_connection(data, preset_servers)
            if err or not conn:
                logger.warning("Start-load (compat GET) resolve failed: %s", err)
                return jsonify({"success": False, "message": err}), 400
            token = connection_tokens.issue_token(dict(conn))
            job_id = uuid.uuid4().hex
            with load_lock:
                load_jobs[job_id] = {
                    "status": "pending",
                    "progress": 0,
                    "message": "Starting",
                    "created_at": time.time(),
                    "updated_at": time.time(),
                    "payload": None,
                    "connection_token": token,
                }
            threading.Thread(
                target=run_load_job,
                args=(job_id, dict(conn), recent_limit_from_env()),
                daemon=True,
            ).start()
            return jsonify({"job_id": job_id, "connection_token": token})
        return api_start_load()

    @app.route("/api/load-status/<job_id>")
    @app.route("/load-status/<job_id>")
    def load_status(job_id):
        with load_lock:
            job = load_jobs.get(job_id)
            if not job:
                return jsonify({"status": "missing", "progress": 0, "message": "Not found"}), 404
            return jsonify(
                {
                    "status": job["status"],
                    "progress": job["progress"],
                    "message": job.get("message", ""),
                }
            )

    @app.route("/api/dashboard/<job_id>")
    def dashboard_payload(job_id):
        with load_lock:
            job = load_jobs.get(job_id)
            if not job:
                return jsonify({"success": False, "message": "Job not found"}), 404
            if job["status"] == "error":
                return jsonify({"success": False, "message": job.get("message", "Error")}), 400
            if job["status"] != "done" or not job.get("payload"):
                return jsonify({"success": False, "message": "Still loading", "status": job["status"]}), 202
            payload = dict(job["payload"])
            token = job.get("connection_token")
        if token:
            payload["connection_token"] = token
        return jsonify({"success": True, "data": payload})

    @app.route("/api/recent", methods=["POST"])
    def api_recent():
        conn, err = _conn_from_token()
        if not conn:
            return jsonify({"success": False, "message": err}), 400
        data = request.get_json(silent=True) or {}
        limit = clamp_recent_limit(data.get("recent_limit", recent_limit_from_env()))
        probe = KodiLibraryProbe(
            conn["host"], None, conn.get("username") or "", conn.get("password") or ""
        )
        if not probe.connect():
            return jsonify({"success": False, "message": probe.last_error or "Connect failed"}), 502
        recent = probe.get_recently_added_content(limit=limit)
        artwork_base = f"{probe.scheme}://{probe.host}:{probe.port}"
        fake = LibraryStats(recently_added=recent)
        formatted = stats_to_dict(fake, probe, artwork_base, limit)["recently_added"]
        return jsonify({"success": True, "recently_added": formatted, "recent_limit": limit})

    @app.route("/api/library-actions")
    def api_library_actions():
        conn, err = _conn_from_token()
        if not conn:
            return jsonify({"success": False, "message": err}), 400
        return jsonify({"success": True, "actions": library_actions.get_actions(conn["host"])})

    def _library_action_route(method: str, action_key: str, ok_message: str, max_wait: float):
        job, err = _dispatch_library_command(method, action_key, max_wait_s=max_wait)
        if not job:
            return jsonify({"success": False, "message": err})
        return jsonify(
            {
                "success": True,
                "message": "Library operation started",
                "job": job,
                "operation": method,
            }
        ), 202

    def _library_action_route_for(method: str):
        action_key, max_wait = LIBRARY_COMMANDS[method]
        return _library_action_route(method, action_key, "Library operation started", max_wait)

    @app.route("/api/library-operation/<job_id>")
    def library_operation(job_id):
        conn, err = _conn_from_token()
        if not conn:
            return jsonify({"success": False, "message": err}), 400
        key = _server_key(conn)
        current = operation_store.get_current(key)
        history = operation_store.get_history(key)
        job = next((item for item in history if item.get("job_id") == job_id), None)
        if not job and current and current.get("job_id") == job_id:
            job = current
        if not job:
            return jsonify({"success": False, "message": "Operation not found"}), 404
        return jsonify({"success": True, "job": job, "history": history})

    @app.route("/api/server-operation/<preset_id>")
    def server_operation_by_preset(preset_id: str):
        conn = _preset_conn(preset_id)
        if not conn:
            return jsonify({"success": False, "message": "Unknown preset server"}), 404
        current, history = _operation_state_for_conn(conn)
        logger.info(
            "Server operation lookup preset=%s host=%s current=%s history=%s",
            preset_id,
            conn.get("host"),
            (current or {}).get("state") if current else None,
            len(history),
        )
        return jsonify(
            {
                "success": True,
                "current": current,
                "current_operation": current,
                "history": history,
                "operation_history": history,
            }
        )

    @app.route("/api/library-operation-history")
    def library_operation_history():
        conn, err = _conn_for_operation_lookup()
        if not conn:
            return jsonify({"success": False, "message": err}), 400
        current, history = _operation_state_for_conn(conn)
        return jsonify(
            {
                "success": True,
                "current": current,
                "history": history,
            }
        )

    @app.route("/api/update-video-library", methods=["POST"])
    @app.route("/update-video-library", methods=["POST"])
    def update_video_library():
        return _library_action_route_for("VideoLibrary.Scan")

    @app.route("/api/update-audio-library", methods=["POST"])
    @app.route("/update-audio-library", methods=["POST"])
    def update_audio_library():
        return _library_action_route_for("AudioLibrary.Scan")

    @app.route("/api/clean-video-library", methods=["POST"])
    @app.route("/clean-video-library", methods=["POST"])
    def clean_video_library():
        return _library_action_route_for("VideoLibrary.Clean")

    @app.route("/api/clean-music-library", methods=["POST"])
    @app.route("/clean-music-library", methods=["POST"])
    def clean_music_library():
        return _library_action_route_for("AudioLibrary.Clean")

    @app.route("/health")
    def health():
        return {"status": "healthy", "timestamp": datetime.now().isoformat()}

    @app.route("/ready")
    def ready():
        """Readiness: Flask up + at least one configured Kodi reachable (or no presets)."""
        if not preset_servers:
            return jsonify(
                {
                    "status": "ready",
                    "kodi": "no_presets",
                    "message": "Web UI ready; no preset Kodi servers configured",
                    "timestamp": datetime.now().isoformat(),
                }
            )
        errors = []
        timeout = _overview_probe_timeout()
        workers = min(len(preset_servers), 10)

        def _probe_ready(preset: Dict[str, Any]) -> Tuple[bool, str, str]:
            conn = {
                "host": preset["host"],
                "username": preset.get("username") or "",
                "password": preset.get("password") or "",
            }
            probe = KodiLibraryProbe(conn["host"], None, conn["username"], conn["password"])
            ok, detail = probe.ping(timeout=timeout)
            label = preset.get("label") or preset["host"]
            return ok, label, detail

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_probe_ready, p) for p in preset_servers]
            for future in as_completed(futures):
                try:
                    ok, label, detail = future.result()
                except Exception as exc:
                    errors.append(f"probe error: {exc}")
                    continue
                if ok:
                    return jsonify(
                        {
                            "status": "ready",
                            "kodi": "ok",
                            "server": label,
                            "detail": detail,
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                errors.append(f"{label}: {detail}")
        return (
            jsonify(
                {
                    "status": "degraded",
                    "kodi": "unreachable",
                    "errors": errors,
                    "timestamp": datetime.now().isoformat(),
                }
            ),
            503,
        )

    @app.route("/favicon.ico")
    def favicon():
        path = BASE_DIR / "favicon.ico"
        if path.exists():
            return send_file(path, mimetype="image/x-icon")
        return "Favicon not found", 404

    def _serve_asset(name: str, mime: str):
        path = BASE_DIR / name
        if path.exists():
            return send_file(path, mimetype=mime)
        # Docker layout sometimes uses /app/
        alt = Path("/app") / name
        if alt.exists():
            return send_file(alt, mimetype=mime)
        return f"{name} not found", 404

    @app.route("/kodi.png")
    def kodi_png():
        return _serve_asset("kodi.png", "image/png")

    @app.route("/movies.png")
    def movies_png():
        return _serve_asset("movies.png", "image/png")

    @app.route("/tv.png")
    def tv_png():
        return _serve_asset("tv.png", "image/png")

    @app.route("/music.png")
    def music_png():
        return _serve_asset("music.png", "image/png")

    @app.route("/new.png")
    def new_png():
        return _serve_asset("new.png", "image/png")

    @app.route("/refresh.png")
    def refresh_png():
        return _serve_asset("refresh.png", "image/png")

    @app.route("/background.jpg")
    def background_jpg():
        return _serve_asset("background.jpg", "image/jpeg")

    @app.route("/artwork/<filename>")
    def artwork(filename):
        for base in (Path("/app/output/artwork"), BASE_DIR / "output" / "artwork"):
            path = base / filename
            if path.exists():
                return send_file(path, mimetype="image/jpeg")
        return "Artwork not found", 404

    # Legacy content route — redirect clients to SPA
    @app.route("/content/<job_id>")
    def content_legacy(job_id):
        return (
            "<!DOCTYPE html><html><head><meta http-equiv='refresh' content='0;url=/'>"
            "<script>location.replace('/')</script></head>"
            "<body>Redirecting…</body></html>"
        )

    @app.route("/session-reload")
    def session_reload_legacy():
        return (
            "<!DOCTYPE html><html><head>"
            "<script>location.replace('/#reload')</script></head>"
            "<body>Redirecting…</body></html>"
        )

    if preset_servers:
        logger.info(
            "Preset Kodi servers (%s): %s",
            len(preset_servers),
            "; ".join(f"{p.get('label') or p.get('host')} [{p.get('host')}]" for p in preset_servers),
        )
    else:
        logger.info("No preset Kodi servers configured (custom host entry only)")
    _resume_in_progress_operations()
    logger.info("Web app ready on port %s (container host hint: %s)", web_port, container_host)
    return app


def create_web_server(web_port: int = 5005, container_host: str = "localhost"):
    app = create_app(web_port=web_port, container_host=container_host)
    logger.info("Starting web server on port %s (http://%s:%s)", web_port, container_host, web_port)
    try:
        from waitress import serve
        serve(app, host="0.0.0.0", port=web_port, threads=8)
    except ImportError:
        logger.warning("Waitress unavailable; falling back to Flask development server")
        app.run(host="0.0.0.0", port=web_port, debug=False)
