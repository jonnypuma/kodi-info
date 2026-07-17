#!/usr/bin/env python3
"""Flask web application for Kodi library statistics (JSON API + SPA)."""

from __future__ import annotations

import logging
import os
import secrets
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests
from flask import Flask, jsonify, request, send_file, send_from_directory, session

import connection_tokens
import library_actions
from kodi_client import (
    KodiLibraryProbe,
    LibraryStats,
    RecentlyAdded,
    _watched_episodes_paginated,
    clamp_recent_limit,
    collect_preset_kodi_servers,
    recent_limit_from_env,
    resolve_start_load_connection,
    stats_to_dict,
)

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent


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

    load_jobs: Dict[str, Dict[str, Any]] = {}
    load_lock = threading.Lock()
    preset_servers = collect_preset_kodi_servers()

    if not logger.handlers:
        _h = logging.StreamHandler(sys.stderr)
        _h.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%dT%H:%M:%S")
        )
        logger.addHandler(_h)
        logger.setLevel(logging.INFO)
        logger.propagate = False

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

    def _dispatch_library_command(method: str, max_wait_s: float) -> Tuple[bool, str]:
        conn, err = _conn_from_token()
        if not conn:
            return False, err or "No connection"
        probe = KodiLibraryProbe(
            conn["host"], None, conn.get("username") or "", conn.get("password") or ""
        )
        state: Dict[str, Any] = {"err": None, "finished": False}

        def worker() -> None:
            _, e = _kodi_rpc_post(probe, method, read_timeout=None)
            state["err"] = e
            state["finished"] = True

        threading.Thread(target=worker, daemon=True).start()
        deadline = time.time() + max_wait_s
        while not state["finished"] and time.time() < deadline:
            time.sleep(0.05)
        if state["finished"]:
            if state["err"]:
                return False, state["err"]
            return True, ""
        return False, (
            f"Kodi did not return a response within {int(max_wait_s)} seconds. "
            "The library may be busy — check Kodi logs and try again."
        )

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
        try:
            update_job(job_id, 5, "Connecting")
            probe = KodiLibraryProbe(
                conn["host"], None, conn.get("username") or "", conn.get("password") or ""
            )
            if not probe.connect():
                update_job(
                    job_id,
                    100,
                    probe.last_error or f"Unable to connect to Kodi at {conn.get('host', '')}",
                    status="error",
                )
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
            host_key = conn.get("host") or artwork_base
            actions = library_actions.get_actions(host_key)
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
                        "recent_limit": recent_limit,
                        "default_recent_limit": recent_limit_from_env(),
                    }
            update_job(job_id, 100, "Done", status="done")
        except Exception as e:
            update_job(job_id, 100, f"Error: {str(e)}", status="error")

    @app.route("/")
    def index():
        return send_from_directory(app.template_folder, "index.html")

    @app.route("/api/config")
    def api_config():
        presets = [
            {"id": p["id"], "label": p["label"], "host": p["host"]} for p in preset_servers
        ]
        return jsonify(
            {
                "presets": presets,
                "default_recent_limit": recent_limit_from_env(),
                "recent_limit_options": [5, 10, 20, 50],
            }
        )

    @app.route("/api/servers")
    def api_servers():
        payload = [{"id": p["id"], "label": p["label"], "host": p["host"]} for p in preset_servers]
        return jsonify({"servers": payload})

    @app.route("/api/start-load", methods=["POST"])
    def api_start_load():
        data = request.get_json(silent=True) or {}

        # Refresh with existing opaque token (no credentials in browser)
        tok = (data.get("connection_token") or "").strip()
        if tok and not data.get("custom") and not data.get("preset") and not data.get("server_id"):
            conn = connection_tokens.get_connection(tok)
            if not conn:
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
        ok, err = _dispatch_library_command(method, max_wait_s=max_wait)
        if ok:
            conn, _ = _conn_from_token()
            if conn and conn.get("host"):
                try:
                    library_actions.record_action(conn["host"], action_key)
                except Exception:
                    logger.exception("Failed to record library action")
            actions = library_actions.get_actions(conn["host"]) if conn else {}
            return jsonify({"success": True, "message": ok_message, "library_actions": actions})
        return jsonify({"success": False, "message": err})

    @app.route("/api/update-video-library", methods=["POST"])
    @app.route("/update-video-library", methods=["POST"])
    def update_video_library():
        return _library_action_route(
            "VideoLibrary.Scan", "video_scan", "Kodi returned OK — video library scan accepted", 60.0
        )

    @app.route("/api/update-audio-library", methods=["POST"])
    @app.route("/update-audio-library", methods=["POST"])
    def update_audio_library():
        return _library_action_route(
            "AudioLibrary.Scan", "audio_scan", "Kodi returned OK — audio library scan accepted", 60.0
        )

    @app.route("/api/clean-video-library", methods=["POST"])
    @app.route("/clean-video-library", methods=["POST"])
    def clean_video_library():
        return _library_action_route(
            "VideoLibrary.Clean", "video_clean", "Kodi returned OK — video library clean accepted", 120.0
        )

    @app.route("/api/clean-music-library", methods=["POST"])
    @app.route("/clean-music-library", methods=["POST"])
    def clean_music_library():
        return _library_action_route(
            "AudioLibrary.Clean", "music_clean", "Kodi returned OK — music library clean accepted", 120.0
        )

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
        for p in preset_servers:
            conn = {
                "host": p["host"],
                "username": p.get("username") or "",
                "password": p.get("password") or "",
            }
            probe = KodiLibraryProbe(conn["host"], None, conn["username"], conn["password"])
            ok, detail = probe.ping()
            if ok:
                return jsonify(
                    {
                        "status": "ready",
                        "kodi": "ok",
                        "server": p.get("label") or p["host"],
                        "detail": detail,
                        "timestamp": datetime.now().isoformat(),
                    }
                )
            errors.append(f"{p.get('label') or p['host']}: {detail}")
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

    logger.info("Web app ready on port %s (container host hint: %s)", web_port, container_host)
    return app


def create_web_server(web_port: int = 5005, container_host: str = "localhost"):
    app = create_app(web_port=web_port, container_host=container_host)
    print(f"🌐 Starting web server on port {web_port}")
    print(f"📊 Access statistics at: http://localhost:{web_port} or http://{container_host}:{web_port}")
    app.run(host="0.0.0.0", port=web_port, debug=False)
