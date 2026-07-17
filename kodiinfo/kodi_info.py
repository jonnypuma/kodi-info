#!/usr/bin/env python3
"""
Kodi Library Information — CLI entry point.

Web UI lives in webapp.py (JSON API + SPA). Kodi JSON-RPC client is kodi_client.py.
"""

import argparse
import json
import sys
from datetime import datetime

from kodi_client import (
    KodiLibraryProbe,
    collect_preset_kodi_servers,
    recent_limit_from_env,
    stats_to_dict,
)


def print_statistics(stats):
    print("\n" + "=" * 60)
    print("KODI LIBRARY STATISTICS")
    print("=" * 60)
    print(f"\nMOVIES:")
    print(f"   Total Movies:        {stats.total_movies:,}")
    print(f"   Watched Movies:      {stats.watched_movies:,}")
    if stats.total_movies > 0:
        print(f"   Watch Percentage:    {(stats.watched_movies / stats.total_movies) * 100:.1f}%")
    print(f"\nTV SHOWS:")
    print(f"   Total TV Shows:      {stats.total_tv_shows:,}")
    print(f"   Total Episodes:      {stats.total_episodes:,}")
    print(f"   Watched Episodes:    {stats.watched_episodes:,}")
    print(f"\nMUSIC:")
    print(f"   Total Artists:       {stats.total_artists:,}")
    print(f"   Total Albums:        {stats.total_albums:,}")
    print(f"   Total Songs:         {stats.total_songs:,}")
    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Probe Kodi device for library statistics via JSON-RPC",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python kodi_info.py --web-server --web-port 5005
  python kodi_info.py --host http://192.168.1.10:8080
  python kodi_info.py --host 192.168.1.100 --port 8080 --username kodi --password mypass
        """,
    )
    parser.add_argument("--host", help="Kodi device URL or IP address")
    parser.add_argument("--port", type=int, default=None, help="Kodi HTTP port")
    parser.add_argument("--username", default="", help="Kodi username")
    parser.add_argument("--password", default="", help="Kodi password")
    parser.add_argument("--save-json", action="store_true", help="Save statistics to JSON file")
    parser.add_argument(
        "--json-file", default="kodi_library_stats.json", help="JSON output filename"
    )
    parser.add_argument("--web-server", action="store_true", help="Start web server")
    parser.add_argument("--web-port", type=int, default=5005, help="Web server port")
    parser.add_argument(
        "--container-host", default="localhost", help="Host hint printed for external access"
    )
    args = parser.parse_args()

    if args.web_server:
        from webapp import create_web_server

        create_web_server(args.web_port, args.container_host)
        return

    if not args.host:
        presets = collect_preset_kodi_servers()
        if presets:
            args.host = presets[0]["host"]
            args.username = args.username or presets[0].get("username") or ""
            args.password = args.password or presets[0].get("password") or ""
        else:
            parser.error("--host is required when not using --web-server mode")

    print("Kodi Library Information Probe")
    print("=" * 40)
    probe = KodiLibraryProbe(args.host, args.port, args.username, args.password)
    if not probe.connect():
        sys.exit(1)

    stats = probe.get_all_statistics()
    print_statistics(stats)

    if args.save_json:
        artwork_base = f"{probe.scheme}://{probe.host}:{probe.port}"
        payload = stats_to_dict(stats, probe, artwork_base, recent_limit_from_env())
        payload["generated_at"] = datetime.now().isoformat()
        with open(args.json_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"Statistics saved to {args.json_file}")


if __name__ == "__main__":
    main()
