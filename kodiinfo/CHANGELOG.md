# Changelog

## Unreleased

- Server overview probes all configured Kodi servers in parallel with a shorter default timeout, so unreachable hosts no longer block the page for tens of seconds.

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
