#!/usr/bin/env python3
"""
Kodi Client Module

Provides classes and functions for connecting to and querying Kodi servers via JSON-RPC.
"""

import logging
import os
import requests
import hashlib
from typing import Dict, Any, Optional, List, Tuple, Callable
from dataclasses import dataclass
from urllib.parse import urlparse, unquote

logger = logging.getLogger(__name__)


@dataclass
class RecentlyAdded:
    """Data class to hold recently added content"""
    episodes: list = None
    movies: list = None
    albums: list = None
    
    def __post_init__(self):
        if self.episodes is None:
            self.episodes = []
        if self.movies is None:
            self.movies = []
        if self.albums is None:
            self.albums = []


@dataclass
class LibraryStats:
    """Data class to hold library statistics"""
    total_movies: int = 0
    watched_movies: int = 0
    total_tv_shows: int = 0
    total_episodes: int = 0
    watched_episodes: int = 0
    total_artists: int = 0
    total_albums: int = 0
    total_songs: int = 0
    recently_added: RecentlyAdded = None
    
    def __post_init__(self):
        if self.recently_added is None:
            self.recently_added = RecentlyAdded()


class KodiLibraryProbe:
    """Class to handle Kodi JSON-RPC connections and library queries"""
    
    def __init__(self, host: str, port: int = None, username: str = "", password: str = ""):
        """
        Initialize Kodi connection
        
        Args:
            host: Kodi device URL (e.g., http://192.168.1.10:555) or IP address
            port: Kodi HTTP port (optional, extracted from host if URL format)
            username: Kodi username (optional)
            password: Kodi password (optional)
        """
        # Parse host - if it's a URL, extract host and port (and optional userinfo)
        if host.startswith("http://") or host.startswith("https://"):
            parsed = urlparse(host)
            self.host = parsed.hostname
            self.port = parsed.port or (8080 if parsed.scheme == "http" else 443)
            self.scheme = parsed.scheme
            if not username and parsed.username:
                username = unquote(parsed.username)
            if not password and parsed.password:
                password = unquote(parsed.password)
        else:
            # Bare hostname or IPv4 — may embed :port (common in env: "192.168.1.5:9090").
            explicit_port = port
            raw = host.strip()
            embedded_port: Optional[int] = None
            h = raw
            if raw.startswith("[") and "]:" in raw:
                bracket_end = raw.rfind("]:")
                port_bit = raw[bracket_end + 2 :]
                if port_bit.isdigit():
                    embedded_port = int(port_bit)
                    h = raw[1:bracket_end]
            elif ":" in raw:
                cand, suf = raw.rsplit(":", 1)
                if cand and suf.isdigit():
                    h = cand.strip()
                    embedded_port = int(suf)
            self.host = h or raw
            self.scheme = "http"
            self.port = (
                explicit_port
                if explicit_port is not None
                else (
                    embedded_port
                    if embedded_port is not None
                    else 8080
                )
            )
        
        self.username = username
        self.password = password
        self.base_url = f"{self.scheme}://{self.host}:{self.port}/jsonrpc"
        self.auth = (self.username, self.password) if self.username and self.password else None
        self.headers = {"Content-Type": "application/json"}
        self.last_error = ""
        self.kodi_version = ""
        
    def connect(self) -> bool:
        """
        Establish connection to Kodi device
        
        Returns:
            True if connection successful, False otherwise
        """
        self.last_error = ""
        try:
            # Test connection by getting Kodi version using requests
            payload = {
                "jsonrpc": "2.0",
                "method": "Application.GetProperties",
                "params": {"properties": ["version"]},
                "id": 1
            }
            
            response = requests.post(self.base_url, headers=self.headers, json=payload, 
                                   auth=self.auth, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            if "result" in result and "version" in result["result"]:
                version = result["result"]["version"]
                self.kodi_version = ".".join(
                    str(version.get(key)) for key in ("major", "minor", "tag")
                    if version.get(key) not in (None, "")
                )
                logger.info(
                    "Connected to Kodi %s.%s at %s",
                    version.get("major"),
                    version.get("minor"),
                    self.base_url,
                )
                return True
            else:
                logger.warning("Unexpected Kodi connect response from %s: %s", self.base_url, result)
                self.last_error = f"Unexpected response from Kodi at {self.base_url}"
                return False
            
        except Exception as e:
            logger.warning("Failed to connect to Kodi at %s: %s", self.base_url, e)
            err_text = str(e)
            if "401" in err_text and self.auth is None:
                self.last_error = (
                    f"401 Unauthorized at {self.base_url} — no HTTP username/password "
                    "configured for this preset (set KODI_USERNAME / KODI_PASSWORD or "
                    f"KODI_USERNAME_N / KODI_PASSWORD_N in env)"
                )
            elif "401" in err_text:
                self.last_error = (
                    f"401 Unauthorized at {self.base_url} — check Kodi HTTP username/password"
                )
            else:
                self.last_error = f"Unable to reach {self.base_url}: {err_text}"
            return False
    
    def ping(self) -> Tuple[bool, str]:
        """
        Ping the Kodi server to check if it's reachable
        
        Returns:
            Tuple of (success, version_string_or_error)
        """
        try:
            payload = {
                "jsonrpc": "2.0",
                "method": "Application.GetProperties",
                "params": {"properties": ["version"]},
                "id": 1
            }
            
            response = requests.post(self.base_url, headers=self.headers, json=payload,
                                   auth=self.auth, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            if "result" in result and "version" in result["result"]:
                version = result["result"]["version"]
                self.kodi_version = ".".join(
                    str(version.get(key)) for key in ("major", "minor", "tag")
                    if version.get(key) not in (None, "")
                )
                version_str = f"Kodi {version['major']}.{version['minor']}"
                return True, version_str
            else:
                return False, f"Unexpected response from Kodi"
        except Exception as e:
            return False, str(e)
    
    def _make_request(self, method: str, params: dict = None, timeout: int = 10) -> dict:
        """Make a JSON-RPC request to Kodi"""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": 1
        }
        
        try:
            response = requests.post(self.base_url, headers=self.headers, json=payload,
                                   auth=self.auth, timeout=timeout)
            response.raise_for_status()
            result = response.json()
            return result
        except Exception as e:
            logger.warning("RPC request failed for %s at %s: %s", method, self.base_url, e)
            return {}
    
    def get_movie_statistics(self) -> tuple[int, int]:
        """
        Get movie statistics from Kodi library
        
        Returns:
            Tuple of (total_movies, watched_movies)
        """
        try:
            logger.debug("Fetching movie statistics from %s", self.base_url)
            result = self._make_request("VideoLibrary.GetMovies", {
                "properties": ["playcount"],
                "limits": {"start": 0, "end": 100000}
            })
            
            if "result" not in result:
                return 0, 0
                
            movies = result["result"].get("movies", [])
            limits = result["result"].get("limits", {})
            
            total_movies = limits.get("total", 0)
            watched_movies = sum(1 for movie in movies 
                               if movie.get("playcount", 0) > 0)
            
            return total_movies, watched_movies
            
        except Exception as e:
            logger.warning("Error fetching movie statistics from %s: %s", self.base_url, e)
            return 0, 0
    
    def get_tv_statistics(self) -> tuple[int, int, int]:
        """
        Get TV show and episode statistics from Kodi library
        
        Returns:
            Tuple of (total_tv_shows, total_episodes, watched_episodes)
        """
        try:
            logger.debug("Fetching TV show statistics from %s", self.base_url)
            
            # Get TV shows
            tv_shows_result = self._make_request("VideoLibrary.GetTVShows", {
                "limits": {"start": 0, "end": 100000}
            })
            total_tv_shows = tv_shows_result.get("result", {}).get("limits", {}).get("total", 0)

            # Global library episode count (matches JSON-RPC catalog; may differ from Kodi UI/DB — Kodi-side).
            ep_quick = self._make_request(
                "VideoLibrary.GetEpisodes",
                {"limits": {"start": 0, "end": 1}},
                timeout=60,
            )
            total_episodes = int(
                (ep_quick.get("result") or {}).get("limits", {}).get("total") or 0
            )

            watched_episodes = 0
            stats_result = self._make_request("VideoLibrary.GetStatistics", {}, timeout=30)
            if stats_result and "result" in stats_result:
                statistics = stats_result["result"].get("statistics", {})
                watched_episodes = int(statistics.get("episode.watched", 0) or 0)
                if total_episodes <= 0:
                    total_episodes = int(statistics.get("episode", 0) or 0)
                logger.debug(
                    "TV stats via GetStatistics: episodes=%s watched=%s",
                    total_episodes,
                    watched_episodes,
                )
            elif total_episodes > 0:
                logger.debug("GetStatistics missing — paginating playcounts for watched episodes")
                watched_episodes, scan_total = _watched_episodes_paginated(self)
                if total_episodes <= 0 and scan_total > 0:
                    total_episodes = scan_total
            else:
                episodes_result = self._make_request(
                    "VideoLibrary.GetEpisodes",
                    {
                        "properties": ["playcount"],
                        "limits": {"start": 0, "end": 100000},
                    },
                    timeout=120,
                )
                episodes = episodes_result.get("result", {}).get("episodes", [])
                total_episodes = episodes_result.get("result", {}).get("limits", {}).get("total", 0)
                watched_episodes = sum(
                    1 for episode in episodes if episode.get("playcount", 0) > 0
                )
                logger.debug(
                    "TV stats via GetEpisodes batch: total=%s watched=%s",
                    total_episodes,
                    watched_episodes,
                )

            if total_episodes > 0 and watched_episodes > total_episodes:
                watched_episodes = total_episodes

            logger.debug("TV shows: %s", total_tv_shows)

            return total_tv_shows, total_episodes, watched_episodes
            
        except Exception as e:
            logger.warning("Error fetching TV show statistics from %s: %s", self.base_url, e)
            return 0, 0, 0
    
    def get_music_statistics(self) -> tuple[int, int, int]:
        """
        Get music statistics from Kodi library
        
        Returns:
            Tuple of (total_artists, total_albums, total_songs)
        """
        try:
            logger.debug("Fetching music statistics from %s", self.base_url)
            
            # Get artists
            artists_result = self._make_request("AudioLibrary.GetArtists", {
                "limits": {"start": 0, "end": 100000}
            })
            total_artists = artists_result.get("result", {}).get("limits", {}).get("total", 0)
            
            # Get albums
            albums_result = self._make_request("AudioLibrary.GetAlbums", {
                "limits": {"start": 0, "end": 100000}
            })
            total_albums = albums_result.get("result", {}).get("limits", {}).get("total", 0)
            
            # Get songs
            songs_result = self._make_request("AudioLibrary.GetSongs", {
                "limits": {"start": 0, "end": 100000}
            })
            total_songs = songs_result.get("result", {}).get("limits", {}).get("total", 0)
            
            return total_artists, total_albums, total_songs
            
        except Exception as e:
            logger.warning("Error fetching music statistics from %s: %s", self.base_url, e)
            return 0, 0, 0
    
    def get_recently_added_content(self, limit: int = None) -> RecentlyAdded:
        """
        Get recently added content from Kodi library
        
        Args:
            limit: Number of items to fetch (default from RECENT_LIMIT env or 10, clamped 1-50)
        
        Returns:
            RecentlyAdded object with episodes, movies, and albums
        """
        if limit is None:
            limit = int(os.getenv("RECENT_LIMIT", "10"))
        limit = max(1, min(50, limit))
        
        recently_added = RecentlyAdded()
        
        try:
            logger.debug("Fetching recently added content from %s (limit=%s)", self.base_url, limit)
            
            # Get recently added episodes
            episodes_result = self._make_request("VideoLibrary.GetRecentlyAddedEpisodes", {
                "properties": ["title", "showtitle", "season", "episode", "dateadded", "art"],
                "limits": {"start": 0, "end": limit}
            })
            recently_added.episodes = episodes_result.get("result", {}).get("episodes", [])
            
            # Get recently added movies
            movies_result = self._make_request("VideoLibrary.GetRecentlyAddedMovies", {
                "properties": ["title", "year", "dateadded", "art", "rating"],
                "limits": {"start": 0, "end": limit}
            })
            recently_added.movies = movies_result.get("result", {}).get("movies", [])
            
            # Get recently added albums
            albums_result = self._make_request("AudioLibrary.GetRecentlyAddedAlbums", {
                "properties": ["title", "artist", "year", "dateadded", "art"],
                "limits": {"start": 0, "end": limit}
            })
            recently_added.albums = albums_result.get("result", {}).get("albums", [])
            
            return recently_added
            
        except Exception as e:
            logger.warning("Error fetching recently added content from %s: %s", self.base_url, e)
            return recently_added

    def get_all_statistics(self) -> LibraryStats:
        """
        Get all library statistics
        
        Returns:
            LibraryStats object containing all statistics
        """
        stats = LibraryStats()
        
        # Get movie statistics
        stats.total_movies, stats.watched_movies = self.get_movie_statistics()
        
        # Get TV statistics
        stats.total_tv_shows, stats.total_episodes, stats.watched_episodes = self.get_tv_statistics()
        
        # Get music statistics
        stats.total_artists, stats.total_albums, stats.total_songs = self.get_music_statistics()
        
        # Get recently added content
        stats.recently_added = self.get_recently_added_content()

        return stats


def _watched_episodes_paginated(
    probe: KodiLibraryProbe,
    page_size: int = 2500,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> tuple[int, int]:
    """
    Count watched by scanning playcount in pages (GetEpisodes can truncate large lists).
    Returns (watched_count, global_total_from_first_response).
    """
    watched = 0
    global_total: Optional[int] = None
    start = 0
    page_size = max(250, page_size)

    while True:
        episodes_result = probe._make_request(
            "VideoLibrary.GetEpisodes",
            {
                "properties": ["playcount"],
                "limits": {"start": start, "end": start + page_size},
            },
            timeout=180,
        )
        res_block = episodes_result.get("result") or {}
        batch = res_block.get("episodes") or []
        if global_total is None:
            global_total = int((res_block.get("limits") or {}).get("total") or 0)

        for ep in batch:
            if ep.get("playcount", 0) > 0:
                watched += 1

        if not batch:
            break
        start += len(batch)
        if (
            on_progress is not None
            and global_total is not None
            and global_total > 0
        ):
            try:
                on_progress(min(start, global_total), global_total)
            except Exception:
                pass
        if global_total is not None and global_total > 0 and start >= global_total:
            break
        if len(batch) < page_size:
            break

    return watched, global_total if global_total is not None else start


def format_recent_item(item, item_type, kodi_host=None, probe=None):
    """Format a recently added item for display"""
    
    def get_image_url(art_path):
        """Download and serve Kodi image locally"""
        if not art_path:
            return ''
        
        # If it's already a full URL, return it
        if art_path.startswith('http'):
            return art_path
            
        # If it's a Kodi image path, download and serve locally
        if art_path.startswith('image://') and probe:
            try:
                # Create a safe filename from the artwork path
                safe_filename = hashlib.md5(art_path.encode()).hexdigest() + '.jpg'
                local_path = f"/app/output/artwork/{safe_filename}"
                
                # Create artwork directory if it doesn't exist
                os.makedirs("/app/output/artwork", exist_ok=True)
                
                # Check if we already have this image
                if os.path.exists(local_path):
                    logger.debug("Using cached artwork: %s", safe_filename)
                    return f"/artwork/{safe_filename}"
                
                # Try to download the image using Kodi's Files.PrepareDownload
                result = probe._make_request("Files.PrepareDownload", {"path": art_path})
                
                if result.get("result", {}).get("details", {}).get("path"):
                    # Get the download URL
                    download_path = result["result"]["details"]["path"]
                    host_part = kodi_host.replace('http://', '').replace('https://', '')
                    
                    # Try different URL formats
                    download_urls = [
                        f"http://{host_part}/{download_path}",
                        f"http://{host_part}/vfs/{download_path}",
                        f"http://{host_part}/image/{download_path}"
                    ]
                    
                    # Get authentication from probe
                    auth = probe.auth if hasattr(probe, 'auth') else None
                    
                    for download_url in download_urls:
                        try:
                            logger.debug("Trying artwork download from: %s", download_url[:80])
                            
                            # Add authentication to the download request
                            if auth:
                                response = requests.get(download_url, timeout=10, stream=True, auth=auth)
                            else:
                                response = requests.get(download_url, timeout=10, stream=True)
                            
                            if response.status_code == 200:
                                # Save the image
                                with open(local_path, 'wb') as f:
                                    for chunk in response.iter_content(chunk_size=8192):
                                        f.write(chunk)
                                
                                logger.debug("Downloaded artwork: %s", safe_filename)
                                return f"/artwork/{safe_filename}"
                            else:
                                logger.debug(
                                    "Artwork download failed with status %s from %s",
                                    response.status_code,
                                    download_url[:80],
                                )
                                
                        except Exception as e:
                            logger.debug("Artwork download attempt failed: %s", str(e)[:80])
                            continue
                    
                    logger.warning("All artwork download attempts failed for: %s", art_path[:80])
                    
                else:
                    logger.debug("No PrepareDownload path in result for artwork")
                    
            except Exception as e:
                logger.warning("Failed to download artwork: %s", e)
        
        return ''
    
    if item_type == 'movie':
        art_path = item.get('art', {}).get('poster', '') if item.get('art') else ''
        if art_path:
            logger.debug("Movie '%s' has artwork: %s", item.get('title', 'Unknown'), art_path[:50])
        return {
            'title': item.get('title', 'Unknown Movie'),
            'subtitle': str(item.get('year', '')) if item.get('year') else '',
            'date': (item.get('dateadded') or item.get('lastplayed', ''))[:10],
            'image': get_image_url(art_path),
            'icon': '🎬'
        }
    elif item_type == 'episode':
        art_path = item.get('art', {}).get('thumb', '') if item.get('art') else ''
        if art_path:
            logger.debug("Episode '%s' has artwork: %s", item.get('title', 'Unknown'), art_path[:50])
        return {
            'title': item.get('title', 'Unknown Episode'),
            'subtitle': f"{item.get('showtitle', 'Unknown Show')} S{str(item.get('season', 0)).zfill(2)}E{str(item.get('episode', 0)).zfill(2)}",
            'date': (item.get('dateadded') or item.get('lastplayed', ''))[:10],
            'image': get_image_url(art_path),
            'icon': '📺'
        }
    elif item_type == 'album':
        artists = item.get('artist', [])
        artist_name = artists[0] if artists else 'Unknown Artist'
        art_path = item.get('art', {}).get('thumb', '') if item.get('art') else ''
        if art_path:
            logger.debug("Album '%s' has artwork: %s", item.get('title', 'Unknown'), art_path[:50])
        return {
            'title': item.get('title', 'Unknown Album'),
            'subtitle': artist_name,
            'date': (item.get('dateadded') or item.get('lastplayed', ''))[:10],
            'image': get_image_url(art_path),
            'icon': '🎵'
        }
    return {}


def _global_kodi_credentials() -> Tuple[str, str]:
    """Shared fallback username/password from unnumbered env vars."""
    return (
        (os.getenv("KODI_USERNAME") or "").strip(),
        (os.getenv("KODI_PASSWORD") or "").strip(),
    )


def _slot_kodi_credentials(slot_index: Optional[int]) -> Tuple[str, str]:
    """
    Credentials for a numbered slot (1–10), falling back to KODI_USERNAME / KODI_PASSWORD
    when KODI_USERNAME_N / KODI_PASSWORD_N are unset or empty.
    """
    global_user, global_pass = _global_kodi_credentials()
    if slot_index is None:
        return global_user, global_pass
    user = (os.getenv(f"KODI_USERNAME_{slot_index}") or "").strip()
    pwd = (os.getenv(f"KODI_PASSWORD_{slot_index}") or "").strip()
    if not user:
        user = global_user
    if not pwd:
        pwd = global_pass
    return user, pwd


def collect_preset_kodi_servers() -> List[Dict[str, str]]:
    """
    Each non-empty Kodi target is its own preset (dropdown row). No merging.

    Order: ``KODI_HOST`` (+ unnumbered username/password + ``KODI_LABEL``), then
    ``KODI_HOST_1`` … ``KODI_HOST_10`` with matching ``*_N`` creds and labels.

    Preset IDs are sequential ``"1"``, ``"2"``, … in that order (not the env suffix `_N`).
    """
    raw_slots: List[Dict[str, str]] = []

    legacy_host = (os.getenv("KODI_HOST") or "").strip()
    if legacy_host:
        lbl = (os.getenv("KODI_LABEL") or "").strip()
        legacy_user, legacy_pass = _global_kodi_credentials()
        raw_slots.append(
            {
                "host": legacy_host,
                "username": legacy_user,
                "password": legacy_pass,
                "label": lbl if lbl else "Primary",
            }
        )

    for i in range(1, 11):
        h = (os.getenv(f"KODI_HOST_{i}") or "").strip()
        if not h:
            continue
        lbl = (os.getenv(f"KODI_LABEL_{i}") or "").strip()
        slot_user, slot_pass = _slot_kodi_credentials(i)
        raw_slots.append(
            {
                "host": h,
                "username": slot_user,
                "password": slot_pass,
                "label": lbl if lbl else f"Server {i}",
            }
        )

    out: List[Dict[str, str]] = []
    for idx, row in enumerate(raw_slots, start=1):
        out.append(
            {
                "id": str(idx),
                "label": row["label"],
                "host": row["host"],
                "username": row["username"],
                "password": row["password"],
            }
        )
    return out


def _normalize_manual_url(host: str, port: Any, scheme: str = "http") -> Tuple[Optional[str], Optional[str]]:
    host = (host or "").strip()
    if not host:
        return None, "Host / IP is required"
    try:
        port_int = int(port)
    except (TypeError, ValueError):
        return None, "Port must be a number"
    if port_int < 1 or port_int > 65535:
        return None, "Port must be between 1 and 65535"
    sch = (scheme or "http").strip().lower()
    if sch not in ("http", "https"):
        sch = "http"
    url = f"{sch}://{host}:{port_int}"
    return url, None


def connection_dict_for_preset(slot: Dict[str, str]) -> Dict[str, Any]:
    return {
        "host": slot["host"],
        "username": slot.get("username") or "",
        "password": slot.get("password") or "",
        "label": slot.get("label") or f"Server {slot.get('id', '')}",
        "preset_id": slot.get("id"),
    }


def resolve_start_load_connection(
    data: Optional[Dict[str, Any]], presets: List[Dict[str, str]]
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Build a connection dict from JSON body or return an error message."""
    if data is None:
        data = {}
    if not isinstance(data, dict):
        return None, "Invalid JSON body"

    preset_hint = data.get("preset") or data.get("server_id") or data.get("id")
    is_custom = bool(data.get("custom")) or str(preset_hint or "").strip().lower() in (
        "custom",
        "manual",
    )

    if is_custom:
        url, err = _normalize_manual_url(
            data.get("host", ""),
            data.get("port", 8080),
            data.get("scheme", "http"),
        )
        if err or not url:
            return None, err or "Invalid address"
        custom_label = (data.get("label") or "").strip()
        lbl = custom_label if custom_label else f"Custom ({data.get('host', '').strip()})"
        return (
            {
                "host": url,
                "username": (data.get("username") or "") or "",
                "password": (data.get("password") or "") or "",
                "label": lbl,
                "preset_id": None,
            },
            None,
        )

    sid = str(preset_hint).strip() if preset_hint is not None else ""
    chosen: Optional[Dict[str, str]] = None
    if sid.isdigit():
        for p in presets:
            if p["id"] == sid:
                chosen = p
                break
    if chosen is None and not sid and presets:
        chosen = presets[0]
    if chosen is None:
        return None, "Select a configured server or use custom host/port"
    return connection_dict_for_preset(chosen), None


def recent_limit_from_env() -> int:
    try:
        n = int(os.getenv("RECENT_LIMIT", "10"))
    except (TypeError, ValueError):
        n = 10
    return max(1, min(50, n))


def clamp_recent_limit(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return recent_limit_from_env()
    return max(1, min(50, n))


def stats_to_dict(stats: LibraryStats, probe: KodiLibraryProbe, artwork_base_url: str, recent_limit: int) -> Dict[str, Any]:
    """
    Convert LibraryStats to a JSON-serializable dictionary
    
    Args:
        stats: LibraryStats object
        probe: KodiLibraryProbe instance
        artwork_base_url: Base URL for Kodi artwork
        recent_limit: Number of recent items that were fetched
    
    Returns:
        Dictionary with all statistics and formatted recent items
    """
    movie_watch_pct = (
        (stats.watched_movies / stats.total_movies * 100) 
        if stats.total_movies > 0 else 0
    )
    episode_watch_pct = (
        (stats.watched_episodes / stats.total_episodes * 100) 
        if stats.total_episodes > 0 else 0
    )
    
    return {
        "total_movies": stats.total_movies,
        "watched_movies": stats.watched_movies,
        "movie_watch_pct": round(movie_watch_pct, 1),
        "total_tv_shows": stats.total_tv_shows,
        "total_episodes": stats.total_episodes,
        "watched_episodes": stats.watched_episodes,
        "episode_watch_pct": round(episode_watch_pct, 1),
        "total_artists": stats.total_artists,
        "total_albums": stats.total_albums,
        "total_songs": stats.total_songs,
        "recently_added": {
            "movies": [
                format_recent_item(m, "movie", artwork_base_url, probe) 
                for m in stats.recently_added.movies
            ],
            "episodes": [
                format_recent_item(e, "episode", artwork_base_url, probe) 
                for e in stats.recently_added.episodes
            ],
            "albums": [
                format_recent_item(a, "album", artwork_base_url, probe) 
                for a in stats.recently_added.albums
            ],
        },
        "recent_limit": recent_limit,
    }
