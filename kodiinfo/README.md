# Kodi Library Information

Python + Flask app that connects to Kodi via JSON-RPC and shows library statistics in a browser (Homarr-friendly).

## Architecture

| Module | Role |
|--------|------|
| `kodi_info.py` | CLI / `--web-server` entry |
| `webapp.py` | Flask JSON API + SPA shell |
| `kodi_client.py` | Kodi JSON-RPC client + presets |
| `connection_tokens.py` | Opaque server-side connection tokens (no passwords in HTML) |
| `library_actions.py` | Persisted last scan / last clean timestamps |
| `operation_store.py` | Persisted per-server operation state and history |
| `templates/` + `static/` | Single-page UI |

The UI stays at `/` and loads data via `/api/*` — no `document.write` dashboard injection.

## Features (1.0.0)

- Movie / TV / music totals and watched counts
- Watch-progress bars for movies and episodes
- Recently added (movies, episodes, albums) with a **Show 5/10/20/50** dropdown; default from `RECENT_LIMIT`
- Multi-server presets (`KODI_HOST`, `KODI_HOST_1`…`_10`) + custom host/port + recent custom list in the browser
- Scan / Clean video & audio (success = Kodi JSON-RPC `result: OK`)
- Last video/audio scan and clean times (recorded when kodi-info successfully triggers them)
- Manual refresh and 24h auto-refresh using the same connection token
- **Per-server dashboard cache** (browser IndexedDB, 3-day TTL): switching servers reuses last loaded stats instantly; **Refresh** forces a live reload
- `/health` (liveness) and `/ready` (tries configured Kodi presets)
- Server overview with reachability, Kodi version, active operation, and recent operation history
- Parallel server reachability probes with a short configurable timeout (`OVERVIEW_PROBE_TIMEOUT_SECONDS`, default 3s)
- Durable per-server operation state in `output/library_operations.json`
- Optional web login using `BASIC_AUTH=username:password`
- Configurable `LOG_LEVEL=INFO|DEBUG|TRACE`; routine Werkzeug access logs are hidden at INFO

## Prerequisites

Enable JSON-RPC in Kodi: **Settings → Services → Control** — Allow remote control via HTTP, set port/user/password.

## Configure

Create `.env` next to compose:

```bash
KODI_HOST=http://192.168.1.50:8080
KODI_USERNAME=kodi
KODI_PASSWORD=your_password
KODI_LABEL=Living room

# Optional extra servers (empty KODI_USERNAME_N inherits KODI_USERNAME / KODI_PASSWORD)
# KODI_HOST_1=http://192.168.1.51:8080
# KODI_LABEL_1=Bedroom

# Strongly recommended — keep the same across restarts
WEB_SECRET_KEY=paste_a_long_random_hex_here

# Default recently-added count (1–50). UI can still change it.
RECENT_LIMIT=10

# Optional web login. Leave empty to disable authentication.
BASIC_AUTH=admin:change-me

# INFO (default), DEBUG, or TRACE
LOG_LEVEL=INFO

# Server overview reachability probe timeout in seconds (default 3).
OVERVIEW_PROBE_TIMEOUT_SECONDS=3

WEB_PORT=5005
```

Generate a secret:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Without `WEB_SECRET_KEY`, Flask uses a random key each process start (sessions won’t survive restarts).

## Run

```bash
docker compose build
docker compose up -d
```

Open `http://host:5005/`.

### Health

- `GET /health` — process up  
- `GET /ready` — at least one preset Kodi responds to ping (503 if all fail)

## Development

```bash
pip install -r requirements.txt
python kodi_info.py --web-server --web-port 5005
python -m unittest discover -s tests -v
```

## Notes

- Connection credentials stay on the server behind an opaque `connection_token` (sessionStorage holds only the token).
- Dashboard stats are cached **in the browser** per server for **3 days** (IndexedDB, with localStorage fallback). Choosing a server again shows the cache immediately; use the refresh icon for a fresh Kodi pull. Passwords are never stored in the cache.
- Last scan/clean times are what **this app** recorded after a successful Scan/Clean RPC — not historical Kodi DB events from before kodi-info existed.
- Scan/Clean can take a long time on Kodi; the UI tracks the operation and probes `Library.IsScanningVideo` or `Library.IsScanningMusic` when available.
- Scan/Clean operation state and history survive server switching and container restarts through the `output` volume.
- Kodi HTTP JSON-RPC confirms that a Scan/Clean request was accepted, but does not reliably report scanner completion. If Kodi exposes its scan boolean, the UI changes to `running` and then `completed`; the hard timeout is reset every time Kodi still reports scanning, so long scans can run for hours. If Kodi never exposes a scan state, the accepted state expires after `LIBRARY_STATUS_GRACE_SECONDS` (default 300 seconds).
- The container uses Waitress in production. `BASIC_AUTH` protects operational routes while `/health` and `/ready` remain available for Docker health checks.
