# Changelog

## Unreleased

- Server overview probes all configured Kodi servers in parallel with a shorter default timeout, so unreachable hosts no longer block the page for tens of seconds.
- Server overview now refreshes reachability every 30 seconds and when the browser tab becomes visible again.
- Operation status cards keep long error messages contained within the server column; the dismiss button stays visible.
- Library action timestamps now use a canonical server key so scan/clean history survives host-format differences and container rebuilds.
- In-progress library operations resume automatically after container restarts.
- Dashboard operation timers and last-scan metadata refresh correctly when reopening a cached server.
- Dashboard operation status now resolves active scans using the connection token, preset id, and migrated server keys.
- Scan monitoring defaults raised for slow devices (2h grace, 24h idle timeout) and scans without Kodi status reporting stay active for the full run.
- App version badge (`v1.1.0`) in the upper-left corner of the server overview and library dashboard.

## 1.0.0 - 2026-08-02

- Added a server overview with reachability, Kodi version, active operation, and recent history.
- Added durable per-server scan/clean operation state and history.
- Added live elapsed operation timing that survives switching between servers.
- Added automatic dashboard reload after Kodi accepts a scan or clean request.
- Added optional `BASIC_AUTH=username:password` web authentication and a Kodi-themed login page.
- Added configurable `INFO`, `DEBUG`, and `TRACE` logging levels with quieter routine access logs.
- Added Waitress for production web serving.
- Added startup validation warnings for invalid and duplicate preset endpoints.
- Added operational status and diagnostics APIs.
- Added Kodi scan-status probing with bounded accepted-state expiry.
- Added tests and documentation for the 1.0.0 configuration and operation semantics.
