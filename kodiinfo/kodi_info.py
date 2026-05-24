#!/usr/bin/env python3
"""
Kodi Library Information Script

This script connects to a Kodi device via JSON-RPC and retrieves comprehensive
library statistics including movies, TV shows, episodes, artists, and songs.
Outputs to HTML format suitable for Homarr iframe integration.

Requirements:
- Kodi must have JSON-RPC enabled
- Network access to the Kodi device
- Python packages: kodipydent, requests, flask

Usage:
    python kodi_info.py --host 192.168.1.100 --port 8080
    python kodi_info.py --host 192.168.1.100 --web-server --web-port 5000
"""

import argparse
import json
import logging
import secrets
import sys
import os
import time
import threading
import uuid
from typing import Dict, Any, Optional, List, Tuple, Callable
from dataclasses import dataclass
from datetime import datetime

try:
    import requests
    from flask import Flask, send_file, request, jsonify, session
except ImportError:
    print("Error: Required packages not found. Please install with: pip install -r requirements.txt")
    sys.exit(1)

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
        # Parse host - if it's a URL, extract host and port
        if host.startswith("http://") or host.startswith("https://"):
            from urllib.parse import urlparse

            parsed = urlparse(host)
            self.host = parsed.hostname
            self.port = parsed.port or (8080 if parsed.scheme == "http" else 443)
            self.scheme = parsed.scheme
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

        # Ensure we're using IP address directly (no DNS resolution)
# Debug logging removed for security
        
        self.username = username
        self.password = password
        self.base_url = f"{self.scheme}://{self.host}:{self.port}/jsonrpc"
        self.auth = (self.username, self.password) if self.username and self.password else None
        self.headers = {"Content-Type": "application/json"}
        self.last_error = ""
        
    def connect(self) -> bool:
        """
        Establish connection to Kodi device
        
        Returns:
            True if connection successful, False otherwise
        """
        self.last_error = ""
        try:
# Debug logging removed for security
            
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
                print(f"✓ Connected to Kodi {version['major']}.{version['minor']}")
                return True
            else:
                print(f"✗ Unexpected response format: {result}")
                self.last_error = f"Unexpected response from Kodi at {self.base_url}"
                return False
            
        except Exception as e:
            print(f"✗ Failed to connect to Kodi at {self.base_url}")
            print(f"  Error: {str(e)}")
            self.last_error = f"Unable to reach {self.base_url}: {str(e)}"
            return False
    
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
            print(f"✗ RPC request failed for {method}: {str(e)}")
            return {}
    
    def get_movie_statistics(self) -> tuple[int, int]:
        """
        Get movie statistics from Kodi library
        
        Returns:
            Tuple of (total_movies, watched_movies)
        """
        try:
            print("📽️  Fetching movie statistics...")
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
            print(f"  ⚠️  Error fetching movie statistics: {str(e)}")
            return 0, 0
    
    def get_tv_statistics(self) -> tuple[int, int, int]:
        """
        Get TV show and episode statistics from Kodi library
        
        Returns:
            Tuple of (total_tv_shows, total_episodes, watched_episodes)
        """
        try:
            print("📺  Fetching TV show statistics...")
            
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
                print(f"📺 Global episodes: {total_episodes}; watched (GetStatistics): {watched_episodes}")
            elif total_episodes > 0:
                print("📺 GetStatistics missing — paginating playcounts for watched…")
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
                print(f"📺 Fallback GetEpisodes batch: total={total_episodes} watched={watched_episodes}")

            if total_episodes > 0 and watched_episodes > total_episodes:
                watched_episodes = total_episodes

            print(f"📺 Shows: {total_tv_shows}")

            return total_tv_shows, total_episodes, watched_episodes

        except Exception as e:
            print(f"  ⚠️  Error fetching TV statistics: {str(e)}")
            return 0, 0, 0
    
    def get_music_statistics(self) -> tuple[int, int, int]:
        """
        Get music statistics from Kodi library
        
        Returns:
            Tuple of (total_artists, total_albums, total_songs)
        """
        try:
            print("🎵  Fetching music statistics...")
            
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
            print(f"  ⚠️  Error fetching music statistics: {str(e)}")
            return 0, 0, 0
    
    def get_recently_added_content(self) -> RecentlyAdded:
        """
        Get recently added content from Kodi library
        
        Returns:
            RecentlyAdded object with episodes, movies, and albums
        """
        recently_added = RecentlyAdded()
        
        try:
            print("🆕  Fetching recently added content...")
            
            # Get recently added episodes (limit to 10)
            episodes_result = self._make_request("VideoLibrary.GetRecentlyAddedEpisodes", {
                "properties": ["title", "showtitle", "season", "episode", "dateadded", "art"],
                "limits": {"start": 0, "end": 10}
            })
            recently_added.episodes = episodes_result.get("result", {}).get("episodes", [])
            
            # Get recently added movies (limit to 10)
            movies_result = self._make_request("VideoLibrary.GetRecentlyAddedMovies", {
                "properties": ["title", "year", "dateadded", "art", "rating"],
                "limits": {"start": 0, "end": 10}
            })
            recently_added.movies = movies_result.get("result", {}).get("movies", [])
            
            # Get recently added albums (limit to 10)
            albums_result = self._make_request("AudioLibrary.GetRecentlyAddedAlbums", {
                "properties": ["title", "artist", "year", "dateadded", "art"],
                "limits": {"start": 0, "end": 10}
            })
            recently_added.albums = albums_result.get("result", {}).get("albums", [])
            
            return recently_added
            
        except Exception as e:
            print(f"  ⚠️  Error fetching recently added content: {str(e)}")
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
                import urllib.parse
                import os
                import hashlib
                
                # Create a safe filename from the artwork path
                safe_filename = hashlib.md5(art_path.encode()).hexdigest() + '.jpg'
                local_path = f"/app/output/artwork/{safe_filename}"
                
                # Create artwork directory if it doesn't exist
                os.makedirs("/app/output/artwork", exist_ok=True)
                
                # Check if we already have this image
                if os.path.exists(local_path):
                    print(f"✅ Using cached artwork: {safe_filename}")
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
                            print(f"🔍 Trying to download from: {download_url[:80]}...")
                            
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
                                
                                print(f"✅ Downloaded artwork: {safe_filename}")
                                return f"/artwork/{safe_filename}"
                            else:
                                print(f"❌ Download failed with status: {response.status_code}")
                                
                        except Exception as e:
                            print(f"❌ Download attempt failed: {str(e)[:50]}...")
                            continue
                    
                    print(f"⚠️  All download attempts failed for: {art_path[:50]}...")
                    
                else:
                    print(f"⚠️  No download path in result: {result}")
                    
            except Exception as e:
                print(f"⚠️  Failed to download artwork: {str(e)}")
        
        return ''
    
    if item_type == 'movie':
        art_path = item.get('art', {}).get('poster', '') if item.get('art') else ''
        if art_path:
            print(f"🎬 Movie '{item.get('title', 'Unknown')}' has artwork: {art_path[:50]}...")
        return {
            'title': item.get('title', 'Unknown Movie'),
            'subtitle': str(item.get('year', '')) if item.get('year') else '',
            'date': item.get('dateadded', '')[:10] if item.get('dateadded') else '',
            'image': get_image_url(art_path),
            'icon': '🎬'
        }
    elif item_type == 'episode':
        art_path = item.get('art', {}).get('thumb', '') if item.get('art') else ''
        if art_path:
            print(f"📺 Episode '{item.get('title', 'Unknown')}' has artwork: {art_path[:50]}...")
        return {
            'title': item.get('title', 'Unknown Episode'),
            'subtitle': f"{item.get('showtitle', 'Unknown Show')} S{str(item.get('season', 0)).zfill(2)}E{str(item.get('episode', 0)).zfill(2)}",
            'date': item.get('dateadded', '')[:10] if item.get('dateadded') else '',
            'image': get_image_url(art_path),
            'icon': '📺'
        }
    elif item_type == 'album':
        artists = item.get('artist', [])
        artist_name = artists[0] if artists else 'Unknown Artist'
        art_path = item.get('art', {}).get('thumb', '') if item.get('art') else ''
        if art_path:
            print(f"🎵 Album '{item.get('title', 'Unknown')}' has artwork: {art_path[:50]}...")
        return {
            'title': item.get('title', 'Unknown Album'),
            'subtitle': artist_name,
            'date': item.get('dateadded', '')[:10] if item.get('dateadded') else '',
            'image': get_image_url(art_path),
            'icon': '🎵'
        }
    return {}

def generate_html(stats: LibraryStats, kodi_display: str, last_updated: str, probe=None, show_loading_overlay: bool = True) -> str:
    """Generate HTML output for Homarr iframe integration"""

    artwork_base_url = kodi_display
    if probe is not None:
        artwork_base_url = f"{probe.scheme}://{probe.host}:{probe.port}"

    # Calculate percentages
    movie_watch_percentage = (stats.watched_movies / stats.total_movies * 100) if stats.total_movies > 0 else 0
    episode_watch_percentage = (stats.watched_episodes / stats.total_episodes * 100) if stats.total_episodes > 0 else 0
    
    # Format recently added items
    recent_movies = [format_recent_item(movie, 'movie', artwork_base_url, probe) for movie in stats.recently_added.movies]
    recent_episodes = [format_recent_item(episode, 'episode', artwork_base_url, probe) for episode in stats.recently_added.episodes]
    recent_albums = [format_recent_item(album, 'album', artwork_base_url, probe) for album in stats.recently_added.albums]
    
    # Generate HTML for recently added items
    def generate_recent_items_html(items, content_type):
        html = ""
        for item in items:
            image_url = item.get('image', '')
            title = item.get('title', '')
            subtitle = item.get('subtitle', '')
            date = item.get('date', '')
            icon = item.get('icon', '')
            
            # Determine CSS class based on content type
            if content_type == 'movies':
                css_class = 'movie-poster'
            elif content_type == 'episodes':
                css_class = 'episode-thumb'
            elif content_type == 'albums':
                css_class = 'album-cover'
            else:
                css_class = 'album-cover'  # fallback
            
            if image_url:
                image_html = f'<img src="{image_url}" alt="{title}" class="{css_class}" onerror="this.style.display=\'none\'; this.nextElementSibling.style.display=\'flex\';"><div class="no-image" style="display: none;">{icon}</div>'
            else:
                image_html = f'<div class="no-image">{icon}</div>'
            
            subtitle_html = f'<div class="subtitle">{subtitle}</div>' if subtitle else ''
            date_html = f'<div class="date">{date}</div>' if date else ''
            
            html += f'''
            <div class="recent-entry">
                {image_html}
                <div class="content">
                    <div class="title">{title}</div>
                    {subtitle_html}
                    {date_html}
                </div>
            </div>
            '''
        return html
    
    overlay_html = ""
    overlay_script = ""
    if show_loading_overlay:
        overlay_html = """<div id="loading-overlay" class="loading-overlay" aria-live="polite">
        <div class="loading-card">
            <div class="loader" aria-label="Loading">
                <span>L</span>
                <span>O</span>
                <span>A</span>
                <span>D</span>
                <span>I</span>
                <span>N</span>
                <span>G</span>
            </div>
            <div class="loading-bar">
                <div id="loading-progress" class="loading-progress"></div>
            </div>
            <div id="loading-text" class="loading-text">Loading 0%</div>
        </div>
    </div>"""
        overlay_script = """(function setupLoadingOverlay() {
            const overlay = document.getElementById('loading-overlay');
            const bar = document.getElementById('loading-progress');
            const text = document.getElementById('loading-text');
            if (!overlay || !bar || !text) return;

            let totalAssets = 0;
            let loadedAssets = 0;
            let done = false;

            function updateProgress() {
                if (done) return;
                const percent = totalAssets > 0 ? Math.min(100, Math.round((loadedAssets / totalAssets) * 100)) : 100;
                bar.style.width = percent + '%';
                text.textContent = 'Loading ' + percent + '%';
                if (loadedAssets >= totalAssets) {
                    done = true;
                    overlay.classList.add('hidden');
                    setTimeout(() => {
                        overlay.style.display = 'none';
                    }, 450);
                }
            }

            function trackElement(el) {
                totalAssets += 1;
                if (el.complete) {
                    loadedAssets += 1;
                    updateProgress();
                    return;
                }
                const finalize = () => {
                    loadedAssets += 1;
                    updateProgress();
                };
                el.addEventListener('load', finalize, { once: true });
                el.addEventListener('error', finalize, { once: true });
            }

            const images = Array.from(document.images);
            images.forEach(trackElement);

            const bgImage = getComputedStyle(document.body).backgroundImage;
            const bgMatch = bgImage && bgImage !== 'none' ? bgImage.match(/url\\(["']?(.*?)["']?\\)/) : null;
            if (bgMatch && bgMatch[1]) {
                totalAssets += 1;
                const bgLoader = new Image();
                const finalize = () => {
                    loadedAssets += 1;
                    updateProgress();
                };
                bgLoader.onload = finalize;
                bgLoader.onerror = finalize;
                bgLoader.src = bgMatch[1];
            }

            if (totalAssets === 0) {
                updateProgress();
            } else {
                updateProgress();
            }
        })();"""

    # Clean HTML template
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Kodi Library Statistics</title>
    <link rel="icon" type="image/x-icon" href="/favicon.ico">
    <link rel="shortcut icon" type="image/x-icon" href="/favicon.ico">
    <link rel="icon" href="/favicon.ico" sizes="16x16" type="image/x-icon">
    <link rel="icon" href="/favicon.ico" sizes="32x32" type="image/x-icon">
        <style>
            body {{ 
                font-family: Arial, sans-serif; 
                margin: 0; 
                padding: 20px;
                background-image: url('/background.jpg');
                background-size: cover;
                background-position: center;
                background-attachment: fixed;
                min-height: 100vh;
            }}
            .container {{ 
                max-width: 1200px; 
                margin: 0 auto; 
                background: rgba(0, 0, 0, 0.7);
                backdrop-filter: blur(15px);
                padding: 20px; 
                border-radius: 15px;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
                border: 1px solid rgba(255, 255, 255, 0.1);
                color: white;
            }}
        .header {{ text-align: center; margin-bottom: 30px; color: white; }}
        .stats {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; margin-bottom: 30px; }}
        .stat-column {{ display: flex; flex-direction: column; gap: 15px; }}
        .stat-column h2 {{ margin: 0 0 10px 0; color: white; text-align: center; font-size: 1.5em; display: flex; align-items: center; justify-content: center; gap: 10px; }}
        .stat-column h2 img {{ width: 32px; height: 32px; }}
        .stat-card {{ background: rgba(255, 255, 255, 0.1); padding: 20px; border-radius: 8px; text-align: center; color: white; }}
        .stat-number {{ font-size: 2em; font-weight: bold; color: white; }}
        .stat-label {{ color: rgba(255, 255, 255, 0.8); margin-top: 5px; }}
        .recent {{ margin-top: 30px; }}
        .recent-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }}
        .recent-item {{ background: rgba(255, 255, 255, 0.1); padding: 15px; border-radius: 8px; color: white; }}
        .recent-item h3 {{ margin-top: 0; color: white; display: flex; align-items: center; }}
        .recent-entry {{ display: flex; align-items: center; margin-bottom: 10px; padding: 10px; background: rgba(255, 255, 255, 0.1); border-radius: 5px; color: white; }}
            .recent-entry img {{ margin-right: 10px; border-radius: 8px; }}
            .recent-entry .movie-poster {{ width: 40px; height: 60px; object-fit: cover; }}
            .recent-entry .episode-thumb {{ width: 70px; height: 40px; object-fit: cover; }}
            .recent-entry .album-cover {{ width: 50px; height: 50px; object-fit: cover; }}
            .no-image {{ width: 50px; height: 50px; background: rgba(255, 255, 255, 0.2); margin-right: 10px; display: flex; align-items: center; justify-content: center; border-radius: 8px; color: white; }}
        .buttons {{ text-align: center; margin-top: 30px; margin-bottom: 30px; }}
        .btn {{ background: #007bff; color: white; border: none; padding: 10px 20px; margin: 0 10px; border-radius: 5px; cursor: pointer; min-width: 190px; display: inline-flex; align-items: center; justify-content: center; }}
        .btn:hover {{ background: #0056b3; }}
        .btn:disabled {{ background: #6c757d; cursor: not-allowed; }}
        .action-status {{
            display: none;
            margin-top: 14px;
            margin-bottom: 4px;
            padding: 12px 14px;
            border-radius: 8px;
            font-size: 0.92em;
            white-space: pre-wrap;
            word-break: break-word;
            text-align: left;
            max-height: 240px;
            overflow-y: auto;
            color: rgba(255, 255, 255, 0.95);
        }}
        .action-status.visible {{
            display: block;
        }}
        .action-status.ok {{
            background: rgba(40, 167, 69, 0.28);
            border: 1px solid rgba(40, 167, 69, 0.55);
        }}
        .action-status.err {{
            background: rgba(220, 53, 69, 0.28);
            border: 1px solid rgba(220, 53, 69, 0.55);
        }}
        /* Image overlay for zoomed artwork */
        .image-overlay {{
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.85);
            display: flex;
            align-items: center;
            justify-content: center;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.25s ease;
            z-index: 9999;
            overflow: hidden;
        }}
        .image-overlay.visible {{
            opacity: 1;
            pointer-events: auto;
        }}
        .image-overlay img {{
            max-width: 80vw;
            max-height: 80vh;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.8);
            transform: scale(0.25);
            transition: transform 0.25s ease;
            object-fit: contain;
        }}
        .image-overlay.visible img {{
            transform: scale(1);
        }}
        /* Episode thumbnails: double drawn size vs poster/album overlay (handles low-res Kodi thumbs) */
        .image-overlay.visible.episode-zoom img {{
            transform: scale(2);
        }}
        .zoomable {{
            cursor: zoom-in;
        }}
        @import url("https://fonts.googleapis.com/css?family=Montserrat:900");
        .loading-overlay {{
            position: fixed;
            inset: 0;
            background-color: #141414;
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10000;
            opacity: 0;
            animation: fadeIn 0.5s ease forwards;
            transition: opacity 0.4s ease;
            font-family: "Montserrat", sans-serif;
        }}
        .loading-overlay.hidden {{
            opacity: 0;
            pointer-events: none;
        }}
        @keyframes fadeIn {{
            from {{ opacity: 0; }}
            to {{ opacity: 1; }}
        }}
        .loading-card {{
            text-align: center;
            color: white;
            min-width: 320px;
        }}
        .loader {{
            -webkit-perspective: 700px;
            perspective: 700px;
        }}
        .loader > span {{
            font-size: 96px;
            display: inline-block;
            animation: flip 2.6s infinite linear;
            transform-origin: 0 70%;
            transform-style: preserve-3d;
            -webkit-transform-style: preserve-3d;
            color: #4caf50;
        }}
        @keyframes flip {{
            35% {{ transform: rotateX(360deg); }}
            100% {{ transform: rotateX(360deg); }}
        }}
        .loader > span:nth-child(even) {{
            color: white;
        }}
        .loader > span:nth-child(2) {{ animation-delay: 0.3s; }}
        .loader > span:nth-child(3) {{ animation-delay: 0.6s; }}
        .loader > span:nth-child(4) {{ animation-delay: 0.9s; }}
        .loader > span:nth-child(5) {{ animation-delay: 1.2s; }}
        .loader > span:nth-child(6) {{ animation-delay: 1.5s; }}
        .loader > span:nth-child(7) {{ animation-delay: 1.8s; }}
        .loading-bar {{
            width: 100%;
            height: 10px;
            background: rgba(255, 255, 255, 0.18);
            border-radius: 999px;
            overflow: hidden;
            margin-top: 33px;
        }}
        .loading-progress {{
            height: 100%;
            width: 0%;
            background: linear-gradient(90deg, #4caf50, #7dd3fc);
            transition: width 0.2s ease;
        }}
        .loading-text {{
            margin-top: 10px;
            font-size: 0.9em;
            color: rgba(255, 255, 255, 0.8);
            letter-spacing: 0.5px;
        }}
    </style>
</head>
<body>
    __LOADING_OVERLAY__
    <div class="container">
        <div class="header">
            <img src="/kodi.png" alt="Kodi Logo" style="height: 120px; margin-bottom: 10px;">
            <h1>Library Statistics</h1>
            <p>Connected to: {kodi_display}</p>
            <p style="margin-top: -6px;"><a href="/" style="color: #90caf9;">Switch Kodi server…</a></p>
            <p>Last updated: {last_updated}</p>
        </div>
        
        <div class="buttons">
            <button id="update-video-btn" class="btn" onclick="updateLibrary('video')">Update Video Library</button>
            <button id="update-audio-btn" class="btn" onclick="updateLibrary('audio')">Update Audio Library</button>
            <button id="clean-video-btn" class="btn" onclick="cleanLibrary('video')">Clean Video Library</button>
            <button id="clean-music-btn" class="btn" onclick="cleanLibrary('music')">Clean Music Library</button>
            <img src="/refresh.png" alt="Refresh" onclick="window.location.href='/session-reload'" style="width: 40px; height: 40px; margin-left: 10px; cursor: pointer; vertical-align: middle;" title="Refresh library (same server)">
        </div>
        <div id="library-action-status" class="action-status" role="status" aria-live="polite" aria-atomic="true" hidden></div>
        
        <div class="stats">
            <div class="stat-column">
                <h2><img src="/movies.png" alt="Movies"> Movies</h2>
                <div class="stat-card">
                    <div class="stat-number">{stats.total_movies:,}</div>
                    <div class="stat-label">Total Movies</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{stats.watched_movies:,}</div>
                    <div class="stat-label">Watched Movies</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{stats.total_movies - stats.watched_movies:,}</div>
                    <div class="stat-label">Unwatched Movies</div>
                </div>
            </div>
            
            <div class="stat-column">
                <h2><img src="/tv.png" alt="TV Shows"> TV Shows</h2>
                <div class="stat-card">
                    <div class="stat-number">{stats.total_tv_shows:,}</div>
                    <div class="stat-label">Total TV Shows</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{stats.total_episodes:,}</div>
                    <div class="stat-label">Total Episodes</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{stats.watched_episodes:,}</div>
                    <div class="stat-label">Watched Episodes</div>
                </div>
            </div>
            
            <div class="stat-column">
                <h2><img src="/music.png" alt="Music"> Music</h2>
                <div class="stat-card">
                    <div class="stat-number">{stats.total_artists:,}</div>
                    <div class="stat-label">Total Artists</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{stats.total_albums:,}</div>
                    <div class="stat-label">Total Albums</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{stats.total_songs:,}</div>
                    <div class="stat-label">Total Songs</div>
                </div>
            </div>
        </div>
        
            <div class="recent">
                <h2><img src="/new.png" alt="New" style="width: 28px; height: 28px; margin-right: 8px;"> Recently Added Content</h2>
                <div class="recent-grid">
                    <div class="recent-item">
                        <h3><img src="/movies.png" alt="Movies" style="width: 24px; height: 24px; margin-right: 8px;"> Recent Movies</h3>
                        {generate_recent_items_html(recent_movies, 'movies')}
                    </div>
                    <div class="recent-item">
                        <h3><img src="/tv.png" alt="TV Shows" style="width: 24px; height: 24px; margin-right: 8px;"> Recent Episodes</h3>
                        {generate_recent_items_html(recent_episodes, 'episodes')}
                    </div>
                    <div class="recent-item">
                        <h3><img src="/music.png" alt="Music" style="width: 24px; height: 24px; margin-right: 8px;"> Recent Albums</h3>
                        {generate_recent_items_html(recent_albums, 'albums')}
                    </div>
                </div>
            </div>
    </div>
    <div id="image-overlay" class="image-overlay">
        <img id="overlay-image" src="" alt="Artwork preview">
    </div>
    
    <script>
        __LOADING_SCRIPT__

        const LIB_BTN_RESET_OK_MS = 4000;
        const LIB_BTN_RESET_ERR_MS = 12000;

        function showLibraryActionStatus(level, summary, detail) {{
            const box = document.getElementById('library-action-status');
            if (!box) return;
            const ts = '[' + new Date().toLocaleTimeString() + '] ';
            box.hidden = false;
            box.textContent = ts + summary + (detail ? ('\\n' + detail) : '');
            box.className = 'action-status visible ' + (level === 'ok' ? 'ok' : 'err');
        }}

        function clearLibraryActionStatus() {{
            const box = document.getElementById('library-action-status');
            if (!box) return;
            box.hidden = true;
            box.textContent = '';
            box.className = 'action-status';
        }}

        function scheduleButtonReset(button, label, ms) {{
            window.setTimeout(() => {{
                button.disabled = false;
                button.textContent = label;
                button.style.background = '';
            }}, ms);
        }}

        function fetchLibraryActionJson(url) {{
            return fetch(url, {{ method: 'POST' }}).then(async (response) => {{
                const text = await response.text();
                let data = {{}};
                if (text) {{
                    try {{
                        data = JSON.parse(text);
                    }} catch (e) {{
                        throw new Error('Invalid JSON (HTTP ' + response.status + '): ' + text.slice(0, 600));
                    }}
                }}
                if (!response.ok) {{
                    const msg = (data && data.message) ? String(data.message) : ('HTTP ' + response.status);
                    throw new Error(msg);
                }}
                return data;
            }});
        }}

        function updateLibrary(type) {{
            clearLibraryActionStatus();
            const label = type === 'video' ? 'Update Video Library' : 'Update Audio Library';
            const button = document.getElementById('update-' + type + '-btn');
            button.disabled = true;
            button.textContent = 'Updating...';

            fetchLibraryActionJson('/update-' + type + '-library')
                .then((data) => {{
                    if (data.success) {{
                        button.textContent = 'Success!';
                        button.style.background = '#28a745';
                        showLibraryActionStatus('ok', label + ' succeeded', data.message || '');
                        scheduleButtonReset(button, label, LIB_BTN_RESET_OK_MS);
                    }} else {{
                        const msg = data.message ? String(data.message) : 'Unknown error';
                        button.textContent = 'Failed — details below';
                        button.style.background = '#dc3545';
                        showLibraryActionStatus('err', label + ' failed', msg);
                        scheduleButtonReset(button, label, LIB_BTN_RESET_ERR_MS);
                    }}
                }})
                .catch((error) => {{
                    const msg = (error && error.message) ? String(error.message) : String(error);
                    button.textContent = 'Failed — details below';
                    button.style.background = '#dc3545';
                    showLibraryActionStatus('err', label + ' failed', msg);
                    console.error('updateLibrary:', error);
                    scheduleButtonReset(button, label, LIB_BTN_RESET_ERR_MS);
                }});
        }}

        function cleanLibrary(type) {{
            clearLibraryActionStatus();
            const label = type === 'video' ? 'Clean Video Library' : 'Clean Music Library';
            const button = document.getElementById('clean-' + type + '-btn');
            button.disabled = true;
            button.textContent = 'Cleaning...';

            const endpoint = type === 'video' ? '/clean-video-library' : '/clean-music-library';
            fetchLibraryActionJson(endpoint)
                .then((data) => {{
                    if (data.success) {{
                        button.textContent = 'Success!';
                        button.style.background = '#28a745';
                        showLibraryActionStatus('ok', label + ' succeeded', data.message || '');
                        scheduleButtonReset(button, label, LIB_BTN_RESET_OK_MS);
                    }} else {{
                        const msg = data.message ? String(data.message) : 'Unknown error';
                        button.textContent = 'Failed — details below';
                        button.style.background = '#dc3545';
                        showLibraryActionStatus('err', label + ' failed', msg);
                        scheduleButtonReset(button, label, LIB_BTN_RESET_ERR_MS);
                    }}
                }})
                .catch((error) => {{
                    const msg = (error && error.message) ? String(error.message) : String(error);
                    button.textContent = 'Failed — details below';
                    button.style.background = '#dc3545';
                    showLibraryActionStatus('err', label + ' failed', msg);
                    console.error('cleanLibrary:', error);
                    scheduleButtonReset(button, label, LIB_BTN_RESET_ERR_MS);
                }});
        }}
        
            // Auto-refresh happens automatically on container startup
            console.log('Setting up 24-hour refresh cycle...');
            
            // Set up 24-hour refresh cycle
            setTimeout(() => {{
                console.log('Auto-reloading page after 24 hours...');
                window.location.href = '/session-reload';
            }}, 24 * 60 * 60 * 1000);
            
            // Show next reload time in console for debugging
            const nextReload = new Date(Date.now() + 24 * 60 * 60 * 1000);
            console.log('Page will auto-reload at:', nextReload.toLocaleString());

            // Click-to-zoom for artwork images
            const overlay = document.getElementById('image-overlay');
            const overlayImg = document.getElementById('overlay-image');
            const zoomableImages = document.querySelectorAll('.movie-poster, .episode-thumb, .album-cover');

            zoomableImages.forEach(img => {{
                img.classList.add('zoomable');
                img.addEventListener('click', event => {{
                    event.stopPropagation();
                    overlay.classList.toggle('episode-zoom', img.classList.contains('episode-thumb'));
                    overlayImg.src = img.src;
                    overlay.classList.add('visible');
                }});
            }});

            // Close overlay on any click
            overlay.addEventListener('click', () => {{
                overlay.classList.remove('visible');
                overlay.classList.remove('episode-zoom');
                overlayImg.src = '';
            }});

            // Also close on Escape key
            document.addEventListener('keydown', event => {{
                if (event.key === 'Escape' && overlay.classList.contains('visible')) {{
                    overlay.classList.remove('visible');
                    overlay.classList.remove('episode-zoom');
                    overlayImg.src = '';
                }}
            }});
    </script>
</body>
</html>
    """
    html_content = html_content.replace("__LOADING_OVERLAY__", overlay_html)
    html_content = html_content.replace("__LOADING_SCRIPT__", overlay_script)
    return html_content


def print_statistics(stats: LibraryStats):
    """Print formatted library statistics to console"""
    print("\n" + "="*60)
    print("🎬 KODI LIBRARY STATISTICS")
    print("="*60)
    
    print(f"\n📽️  MOVIES:")
    print(f"   Total Movies:        {stats.total_movies:,}")
    print(f"   Watched Movies:      {stats.watched_movies:,}")
    if stats.total_movies > 0:
        watch_percentage = (stats.watched_movies / stats.total_movies) * 100
        print(f"   Watch Percentage:    {watch_percentage:.1f}%")
    
    print(f"\n📺  TV SHOWS:")
    print(f"   Total TV Shows:      {stats.total_tv_shows:,}")
    print(f"   Total Episodes:      {stats.total_episodes:,}")
    print(f"   Watched Episodes:    {stats.watched_episodes:,}")
    if stats.total_episodes > 0:
        watch_percentage = (stats.watched_episodes / stats.total_episodes) * 100
        print(f"   Watch Percentage:    {watch_percentage:.1f}%")
    
    print(f"\n🎵  MUSIC:")
    print(f"   Total Artists:       {stats.total_artists:,}")
    print(f"   Total Albums:        {stats.total_albums:,}")
    print(f"   Total Songs:         {stats.total_songs:,}")
    
    print("\n" + "="*60)


def save_statistics_to_html(stats: LibraryStats, kodi_host: str, filename: str = "kodi_stats.html", probe=None):
    """Save statistics to HTML file"""
    last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html_content = generate_html(stats, kodi_host, last_updated, probe)
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"📄 HTML statistics saved to {filename}")
    except Exception as e:
        print(f"⚠️  Error saving HTML file: {str(e)}")

def save_statistics_to_json(stats: LibraryStats, filename: str = "kodi_library_stats.json"):
    """Save statistics to JSON file"""
    stats_dict = {
        "movies": {
            "total": stats.total_movies,
            "watched": stats.watched_movies,
            "unwatched": stats.total_movies - stats.watched_movies
        },
        "tv_shows": {
            "total_shows": stats.total_tv_shows,
            "total_episodes": stats.total_episodes,
            "watched_episodes": stats.watched_episodes,
            "unwatched_episodes": stats.total_episodes - stats.watched_episodes
        },
        "music": {
            "total_artists": stats.total_artists,
            "total_albums": stats.total_albums,
            "total_songs": stats.total_songs
        }
    }
    
    try:
        with open(filename, 'w') as f:
            json.dump(stats_dict, f, indent=2)
        print(f"📄 Statistics saved to {filename}")
    except Exception as e:
        print(f"⚠️  Error saving to file: {str(e)}")


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
        raw_slots.append(
            {
                "host": legacy_host,
                "username": (os.getenv("KODI_USERNAME") or "").strip(),
                "password": (os.getenv("KODI_PASSWORD") or "").strip(),
                "label": lbl if lbl else "Primary",
            }
        )

    for i in range(1, 11):
        h = (os.getenv(f"KODI_HOST_{i}") or "").strip()
        if not h:
            continue
        lbl = (os.getenv(f"KODI_LABEL_{i}") or "").strip()
        raw_slots.append(
            {
                "host": h,
                "username": (os.getenv(f"KODI_USERNAME_{i}") or "").strip(),
                "password": (os.getenv(f"KODI_PASSWORD_{i}") or "").strip(),
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
    """
    Build a connection dict from JSON body or return an error message.
    """
    if data is None:
        data = {}
    if not isinstance(data, dict):
        return None, "Invalid JSON body"

    if data.get("use_session") is True:
        sc = session.get("kodi_connection")
        if isinstance(sc, dict) and (sc.get("host") or "").strip():
            return dict(sc), None
        return None, "Session has no Kodi connection — open the home page and pick a server."

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

    # When no preset id given, default to first preset in list order
    if chosen is None and not sid and presets:
        chosen = presets[0]

    if chosen is None:
        return None, "Select a configured server or use custom host/port"

    return connection_dict_for_preset(chosen), None


def default_connection_for_get(presets: List[Dict[str, str]]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Backward-compatible GET /start-load: first configured preset."""
    if not presets:
        return None, "No preset Kodi servers in environment. Use the form to enter host and port."
    return connection_dict_for_preset(presets[0]), None


def create_web_server(web_port: int = 5005, container_host: str = "localhost"):
    """Create Flask web server to serve HTML statistics"""
    app = Flask(__name__)
    app.secret_key = os.getenv("WEB_SECRET_KEY") or secrets.token_hex(32)
    load_jobs = {}
    load_lock = threading.Lock()

    preset_servers = collect_preset_kodi_servers()
    presets_json_list = [{"id": p["id"], "label": p["label"], "host": p["host"]} for p in preset_servers]
    presets_json = json.dumps(presets_json_list)

    if not logger.handlers:
        _h = logging.StreamHandler(sys.stderr)
        _h.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%dT%H:%M:%S")
        )
        logger.addHandler(_h)
        logger.setLevel(logging.INFO)
        logger.propagate = False

    def _get_session_connection() -> Optional[Dict[str, Any]]:
        conn = session.get("kodi_connection")
        return conn if isinstance(conn, dict) and conn.get("host") else None

    def _run_kodi_rpc(method: str, conn: Optional[Dict[str, Any]] = None) -> tuple[bool, str]:
        """POST JSON-RPC to Kodi using the same endpoint resolution as KodiLibraryProbe."""
        active = conn or _get_session_connection()
        if not active or not active.get("host"):
            return False, "No Kodi connection selected — open the homepage and choose a server"
        probe = KodiLibraryProbe(
            active["host"], None, active.get("username") or "", active.get("password") or ""
        )
        endpoint = probe.base_url
        payload = {"jsonrpc": "2.0", "method": method, "id": 1}
        response_obj = None
        try:
            response_obj = requests.post(
                endpoint,
                headers={"Content-Type": "application/json"},
                json=payload,
                auth=probe.auth,
                timeout=30,
            )
            response_obj.raise_for_status()
            body = response_obj.json()
        except requests.Timeout:
            logger.error("Kodi JSON-RPC timed out method=%s endpoint=%s", method, endpoint)
            return False, "Request timed out"
        except requests.RequestException as e:
            logger.error(
                "Kodi JSON-RPC request failed method=%s endpoint=%s: %s",
                method,
                endpoint,
                e,
                exc_info=True,
            )
            return False, f"Request error: {str(e)}"
        except ValueError:
            snippet = (response_obj.text or "")[:500] if response_obj is not None else ""
            logger.error(
                "Invalid JSON from Kodi method=%s endpoint=%s snippet=%s",
                method,
                endpoint,
                snippet,
                exc_info=True,
            )
            return False, "Invalid response from Kodi (not JSON)"
        except Exception as e:
            logger.exception("Unexpected error calling Kodi method=%s endpoint=%s", method, endpoint)
            return False, f"Error: {str(e)}"

        rpc_err = body.get("error")
        if rpc_err:
            logger.warning("Kodi JSON-RPC error method=%s endpoint=%s error=%s", method, endpoint, rpc_err)
            return False, f"Kodi error: {rpc_err}"

        if body.get("result") == "OK":
            logger.info("Kodi JSON-RPC OK method=%s endpoint=%s", method, endpoint)
            return True, ""

        logger.warning("Kodi unexpected response method=%s endpoint=%s body=%s", method, endpoint, body)
        return False, f"Unexpected response: {body}"

    def build_content_html(
        stats: LibraryStats,
        last_updated: str,
        conn: Dict[str, Any],
        show_loading_overlay: bool = True,
    ):
        host_display = conn.get("host", "")
        label = conn.get("label") or host_display
        kodi_display = f"{label} — {host_display}" if label and label != host_display else host_display

        probe = KodiLibraryProbe(
            conn["host"], None, conn.get("username") or "", conn.get("password") or ""
        )
        html_content = generate_html(
            stats,
            kodi_display,
            last_updated,
            probe,
            show_loading_overlay=show_loading_overlay,
        )
        return html_content

    def generate_loading_html(reload_from_session: bool = False):
        reload_lit = "true" if reload_from_session else "false"
        return f"""
<!DOCTYPE html>
<html>
<head>
    <title>Loading...</title>
    <link rel="icon" type="image/x-icon" href="/favicon.ico">
    <style>
        @import url("https://fonts.googleapis.com/css?family=Montserrat:900");
        body {{
            background-color: #141414;
            padding: 0;
            margin: 0;
            min-height: 100vh;
            width: 100vw;
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: "Montserrat", sans-serif;
            opacity: 0;
            animation: fadeIn 0.5s ease forwards;
        }}
        @keyframes fadeIn {{
            from {{ opacity: 0; }}
            to {{ opacity: 1; }}
        }}
        .panel {{
            max-width: 520px;
            width: 92%;
            color: #fff;
            text-align: center;
        }}
        .server-form {{
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 14px;
            padding: 16px;
            margin-bottom: 22px;
            text-align: left;
        }}
        .server-form label {{
            display: block;
            font-size: 0.75em;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: rgba(255,255,255,0.7);
            margin: 10px 0 4px;
        }}
        .server-form select, .server-form input {{
            width: 100%;
            box-sizing: border-box;
            padding: 10px;
            border-radius: 8px;
            border: 1px solid rgba(255,255,255,0.22);
            background: rgba(0,0,0,0.35);
            color: #fff;
            font-family: Arial, sans-serif;
            font-size: 14px;
        }}
        .row2 {{
            display: grid;
            grid-template-columns: 1fr 120px;
            gap: 10px;
            align-items: end;
        }}
        .form-actions {{
            margin-top: 14px;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}
        .btn {{
            flex: 1;
            min-width: 120px;
            padding: 10px 14px;
            border-radius: 8px;
            border: none;
            cursor: pointer;
            font-weight: 700;
            font-size: 14px;
        }}
        .btn-primary {{
            background: #2196f3;
            color: #fff;
        }}
        .btn-primary:hover {{
            background: #1976d2;
        }}
        .btn-muted {{
            background: rgba(255,255,255,0.14);
            color: #fff;
        }}
        .loader {{
            -webkit-perspective: 700px;
            perspective: 700px;
            text-align: center;
        }}
        .loader > span {{
            font-size: 96px;
            display: inline-block;
            animation: flip 2.6s infinite linear;
            transform-origin: 0 70%;
            transform-style: preserve-3d;
            -webkit-transform-style: preserve-3d;
            color: #4caf50;
        }}
        @keyframes flip {{
            35% {{ transform: rotateX(360deg); }}
            100% {{ transform: rotateX(360deg); }}
        }}
        .loader > span:nth-child(even) {{
            color: white;
        }}
        .loader > span:nth-child(2) {{ animation-delay: 0.3s; }}
        .loader > span:nth-child(3) {{ animation-delay: 0.6s; }}
        .loader > span:nth-child(4) {{ animation-delay: 0.9s; }}
        .loader > span:nth-child(5) {{ animation-delay: 1.2s; }}
        .loader > span:nth-child(6) {{ animation-delay: 1.5s; }}
        .loader > span:nth-child(7) {{ animation-delay: 1.8s; }}
        .loading-bar {{
            width: 100%;
            max-width: 320px;
            height: 10px;
            background: rgba(255, 255, 255, 0.18);
            border-radius: 999px;
            overflow: hidden;
            margin: 33px auto 0;
        }}
        .loading-progress {{
            height: 100%;
            width: 0%;
            background: linear-gradient(90deg, #4caf50, #7dd3fc);
            transition: width 0.2s ease;
        }}
        .loading-text {{
            margin-top: 10px;
            font-size: 0.9em;
            color: rgba(255, 255, 255, 0.8);
            letter-spacing: 0.5px;
            text-align: center;
        }}
        .hidden-ui {{
            display: none !important;
        }}
        .muted {{
            margin-top: 8px;
            font-size: 0.82em;
            color: rgba(255,255,255,0.65);
            line-height: 1.35;
        }}
        body.reload-direct #server-panel {{ display: none !important; }}
        body.reload-direct #loading-ui.hidden-ui {{
            display: flex !important;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 40vh;
        }}
    </style>
</head>
<body{("" if not reload_from_session else ' class="reload-direct"')}>
    <div class="panel">
        <div id="server-panel" class="server-form">
            <div style="font-size:14px;margin-bottom:6px;text-align:center;">Choose Kodi JSON-RPC endpoint</div>
            <label for="preset-select">Saved servers (from compose / env)</label>
            <select id="preset-select" aria-label="Preset Kodi server">
                <option value="__loading__">Loading list…</option>
            </select>
            <p class="muted" id="preset-empty-hint" style="display:none;">No preset servers in environment. Use custom host and port below.</p>
            <label for="custom-host">Custom host or IP</label>
            <input id="custom-host" type="text" placeholder="e.g. 192.168.1.50" autocomplete="off">
            <div class="row2">
                <div>
                    <label for="custom-port">Port</label>
                    <input id="custom-port" type="number" min="1" max="65535" value="8080">
                </div>
                <div>
                    <label for="custom-scheme">Scheme</label>
                    <select id="custom-scheme">
                        <option value="http" selected>http</option>
                        <option value="https">https</option>
                    </select>
                </div>
            </div>
            <label for="custom-user">Username (optional)</label>
            <input id="custom-user" type="text" autocomplete="username">
            <label for="custom-pass">Password (optional)</label>
            <input id="custom-pass" type="password" autocomplete="current-password">
            <div class="form-actions">
                <button type="button" class="btn btn-primary" id="load-btn">Load library</button>
            </div>
        </div>
        <div id="loading-ui" class="hidden-ui">
            <div class="loader">
                <span>L</span>
                <span>O</span>
                <span>A</span>
                <span>D</span>
                <span>I</span>
                <span>N</span>
                <span>G</span>
                <div class="loading-bar">
                    <div id="loading-progress" class="loading-progress"></div>
                </div>
                <div id="loading-text" class="loading-text">Loading 0%</div>
            </div>
        </div>
    </div>
    <script>
        window.__KODI_PRESETS__ = __PRESETS_JSON__;
    </script>
    <script>
        const RELOAD_SESSION_ONLY = {reload_lit};
        const POLL_MS = 2000;
        let bar = null;
        let text = null;
        let jobId = null;
        let pollTimer = null;
        let loadFinished = false;
        let reconnectInProgress = false;
        /** Consecutive transport/poll failures — stop hammering after a few. */
        let pollFailures = 0;

        function stopPolling() {{
            if (pollTimer) {{
                clearInterval(pollTimer);
                pollTimer = null;
            }}
        }}

        function switchToLoadingUI() {{
            const sp = document.getElementById('server-panel');
            const lu = document.getElementById('loading-ui');
            if (sp) sp.style.display = 'none';
            if (lu) lu.classList.remove('hidden-ui');
            bar = document.getElementById('loading-progress');
            text = document.getElementById('loading-text');
        }}

        function updateProgress(value, message) {{
            const percent = Math.min(100, Math.max(0, Math.round(value)));
            const b = bar || document.getElementById('loading-progress');
            const t = text || document.getElementById('loading-text');
            if (b) b.style.width = percent + '%';
            if (t) t.textContent = message ? message + ' ' + percent + '%' : 'Loading ' + percent + '%';
        }}

        function buildStartPayload() {{
            if (RELOAD_SESSION_ONLY) {{
                return {{ use_session: true }};
            }}
            const sel = document.getElementById('preset-select');
            const val = sel ? sel.value : 'custom';
            if (val === 'custom') {{
                return {{
                    custom: true,
                    host: (document.getElementById('custom-host') || {{}}).value || '',
                    port: (document.getElementById('custom-port') || {{}}).value,
                    scheme: (document.getElementById('custom-scheme') || {{}}).value || 'http',
                    username: (document.getElementById('custom-user') || {{}}).value || '',
                    password: (document.getElementById('custom-pass') || {{}}).value || ''
                }};
            }}
            return {{ preset: val }};
        }}

        function restartLoad(reason) {{
            if (reconnectInProgress) return;
            reconnectInProgress = true;
            stopPolling();
            updateProgress(0, reason || 'Starting over');
            jobId = null;
            pollFailures = 0;
            const body = buildStartPayload();
            fetch('/start-load', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify(body)
            }})
                .then(response => {{
                    if (!response.ok) return response.text().then(t => {{ throw new Error(t || ('HTTP ' + response.status)); }});
                    return response.json();
                }})
                .then(data => {{
                    reconnectInProgress = false;
                    jobId = data.job_id;
                    beginPollingIfVisible();
                    pollStatus();
                }})
                .catch(() => {{
                    reconnectInProgress = false;
                    window.location.href = '/';
                }});
        }}

        function pollStatus() {{
            if (!jobId || loadFinished || reconnectInProgress || document.hidden) return;
            fetch('/load-status/' + jobId)
                .then(response => {{
                    if (response.status === 404) {{
                        stopPolling();
                        pollFailures = 0;
                        restartLoad('Session expired — reconnecting');
                        return null;
                    }}
                    if (!response.ok) throw new Error('HTTP ' + response.status);
                    return response.json();
                }})
                .then(data => {{
                    if (!data) return;
                    pollFailures = 0;
                    if (data.status === 'missing') {{
                        stopPolling();
                        restartLoad('Loading job missing — restarting');
                        return;
                    }}
                    updateProgress(data.progress || 0, data.message || 'Loading');
                    if (data.status === 'done') {{
                        loadFinished = true;
                        stopPolling();
                        fetch('/content/' + jobId)
                            .then(response => response.text())
                            .then(html => {{
                                document.body.style.opacity = '0';
                                document.body.style.transition = 'opacity 0.4s ease';
                                setTimeout(() => {{
                                    document.open();
                                    document.write(html);
                                    document.close();
                                }}, 400);
                            }})
                            .catch(() => {{
                                window.location.href = '/content/fallback';
                            }});
                    }} else if (data.status === 'error') {{
                        loadFinished = true;
                        stopPolling();
                        text.textContent = data.message || 'Error loading';
                    }}
                }})
                .catch(() => {{
                    pollFailures += 1;
                    if (pollFailures >= 8) {{
                        stopPolling();
                        text.textContent = 'Lost connection — refresh the page.';
                    }}
                }});
        }}

        function beginPollingIfVisible() {{
            stopPolling();
            if (!jobId || loadFinished || reconnectInProgress) return;
            if (!document.hidden) {{
                pollTimer = setInterval(pollStatus, POLL_MS);
            }}
        }}

        document.addEventListener('visibilitychange', () => {{
            if (document.hidden) {{
                stopPolling();
            }} else if (jobId && !loadFinished && !reconnectInProgress) {{
                pollStatus();
                beginPollingIfVisible();
            }}
        }});

        function populatePresets() {{
            const sel = document.getElementById('preset-select');
            const emptyHint = document.getElementById('preset-empty-hint');
            const presets = Array.isArray(window.__KODI_PRESETS__) ? window.__KODI_PRESETS__ : [];
            if (!sel) return;
            sel.innerHTML = '';
            if (!presets.length) {{
                if (emptyHint) emptyHint.style.display = 'block';
                const opt = document.createElement('option');
                opt.value = 'custom';
                opt.textContent = 'Custom (manual host / port)';
                sel.appendChild(opt);
                sel.value = 'custom';
                return;
            }}
            if (emptyHint) emptyHint.style.display = 'none';
            presets.forEach(p => {{
                const opt = document.createElement('option');
                opt.value = String(p.id);
                const label = p.label || ('Server ' + p.id);
                const host = p.host || '';
                opt.textContent = label + (host ? (' — ' + host) : '');
                sel.appendChild(opt);
            }});
            const custom = document.createElement('option');
            custom.value = 'custom';
            custom.textContent = 'Custom (manual host / port)';
            sel.appendChild(custom);
            sel.value = String(presets[0].id);
        }}

        function startLoadFromUser() {{
            switchToLoadingUI();
            loadFinished = false;
            stopPolling();
            pollFailures = 0;
            jobId = null;
            const body = buildStartPayload();
            fetch('/start-load', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify(body)
            }})
                .then(response => {{
                    if (!response.ok) {{
                        return response.text().then(t => {{
                            let msg = t || ('HTTP ' + response.status);
                            try {{
                                const j = JSON.parse(t);
                                if (j && j.message) msg = j.message;
                            }} catch (e) {{}}
                            throw new Error(msg);
                        }});
                    }}
                    return response.json();
                }})
                .then(data => {{
                    jobId = data.job_id;
                    beginPollingIfVisible();
                    pollStatus();
                }})
                .catch(err => {{
                    const msg = (err && err.message) ? String(err.message) : String(err);
                    alert(msg);
                    window.location.href = '/';
                }});
        }}

        const lb = document.getElementById('load-btn');
        if (lb) {{
            lb.addEventListener('click', () => startLoadFromUser());
        }}
        if (RELOAD_SESSION_ONLY) {{
            startLoadFromUser();
        }} else {{
            populatePresets();
        }}
    </script>
</body>
</html>
        """.replace("__PRESETS_JSON__", presets_json)
    
    @app.route('/')
    def index():
        return generate_loading_html(False)

    @app.route('/session-reload')
    def session_reload():
        """Reload dashboard using Kodi connection stored in Flask session."""
        return generate_loading_html(True)


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

    def run_load_job(job_id: str, conn: Dict[str, Any]):
        try:
            update_job(job_id, 5, "Connecting")
            probe = KodiLibraryProbe(
                conn["host"], None, conn.get("username") or "", conn.get("password") or ""
            )
            if not probe.connect():
                host_display = conn.get("host", "")
                error_message = probe.last_error or f"Unable to connect to Kodi at {host_display}"
                update_job(job_id, 100, error_message, status="error")
                return
            stats = LibraryStats()

            # Movies (fine-grained progress)
            update_job(job_id, 10, "Movies")
            movies_result = probe._make_request("VideoLibrary.GetMovies", {
                "properties": ["playcount"],
                "limits": {"start": 0, "end": 100000}
            })
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
                        progress = 10 + int(15 * (idx / movie_count))
                        update_job(job_id, progress, "Movies")
            stats.watched_movies = watched_movies

            # TV shows + episodes (global totals — fast)
            update_job(job_id, 30, "TV shows")
            tv_shows_result = probe._make_request(
                "VideoLibrary.GetTVShows", {"limits": {"start": 0, "end": 100000}}
            )
            stats.total_tv_shows = tv_shows_result.get("result", {}).get("limits", {}).get("total", 0)
            update_job(job_id, 35, "TV stats")

            ep_quick = probe._make_request(
                "VideoLibrary.GetEpisodes",
                {"limits": {"start": 0, "end": 1}},
                timeout=60,
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
                    {
                        "properties": ["playcount"],
                        "limits": {"start": 0, "end": 100000},
                    },
                    timeout=120,
                )
                episodes = episodes_result.get("result", {}).get("episodes", [])
                stats.total_episodes = episodes_result.get("result", {}).get("limits", {}).get(
                    "total", 0
                )
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
                            progress = 36 + int(19 * (idx / episode_count))
                            update_job(job_id, progress, "Episodes")
                stats.watched_episodes = watched_episodes

            if stats.total_episodes > 0 and stats.watched_episodes > stats.total_episodes:
                stats.watched_episodes = stats.total_episodes
            update_job(job_id, 58, "Artists")
            artists_result = probe._make_request("AudioLibrary.GetArtists", {
                "limits": {"start": 0, "end": 100000}
            })
            stats.total_artists = artists_result.get("result", {}).get("limits", {}).get("total", 0)
            update_job(job_id, 65, "Albums")
            albums_result = probe._make_request("AudioLibrary.GetAlbums", {
                "limits": {"start": 0, "end": 100000}
            })
            stats.total_albums = albums_result.get("result", {}).get("limits", {}).get("total", 0)
            update_job(job_id, 72, "Songs")
            songs_result = probe._make_request("AudioLibrary.GetSongs", {
                "limits": {"start": 0, "end": 100000}
            })
            stats.total_songs = songs_result.get("result", {}).get("limits", {}).get("total", 0)

            # Recently added (per-section progress)
            update_job(job_id, 78, "Recent episodes")
            recent = RecentlyAdded()
            episodes_result = probe._make_request("VideoLibrary.GetRecentlyAddedEpisodes", {
                "properties": ["title", "showtitle", "season", "episode", "dateadded", "art"],
                "limits": {"start": 0, "end": 10}
            })
            recent.episodes = episodes_result.get("result", {}).get("episodes", [])
            update_job(job_id, 84, "Recent movies")
            movies_result = probe._make_request("VideoLibrary.GetRecentlyAddedMovies", {
                "properties": ["title", "year", "dateadded", "art", "rating"],
                "limits": {"start": 0, "end": 10}
            })
            recent.movies = movies_result.get("result", {}).get("movies", [])
            update_job(job_id, 90, "Recent albums")
            albums_result = probe._make_request("AudioLibrary.GetRecentlyAddedAlbums", {
                "properties": ["title", "artist", "year", "dateadded", "art"],
                "limits": {"start": 0, "end": 10}
            })
            recent.albums = albums_result.get("result", {}).get("albums", [])
            stats.recently_added = recent

            update_job(job_id, 95, "Rendering")
            last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            html_content = build_content_html(stats, last_updated, conn, show_loading_overlay=False)
            with load_lock:
                job = load_jobs.get(job_id)
                if job is not None:
                    job["html"] = html_content
            update_job(job_id, 100, "Done", status="done")
        except Exception as e:
            update_job(job_id, 100, f"Error: {str(e)}", status="error")

    @app.route('/start-load', methods=['GET', 'POST'])
    def start_load():
        conn = None
        err = None
        if request.method == 'POST':
            data = request.get_json(silent=True) or {}
            conn, err = resolve_start_load_connection(data, preset_servers)
        else:
            conn, err = default_connection_for_get(preset_servers)

        if err or not conn:
            msg = err or "Unable to resolve Kodi connection"
            return jsonify({"success": False, "message": msg}), 400

        session["kodi_connection"] = dict(conn)
        session.permanent = True
        session.modified = True

        job_id = uuid.uuid4().hex
        with load_lock:
            load_jobs[job_id] = {
                "status": "pending",
                "progress": 0,
                "message": "Starting",
                "created_at": time.time(),
                "updated_at": time.time(),
                "html": None,
            }
        conn_copy = dict(conn)
        thread = threading.Thread(target=run_load_job, args=(job_id, conn_copy), daemon=True)
        thread.start()
        return jsonify({"job_id": job_id})

    @app.route('/api/servers')
    def api_servers():
        """Preset servers only (safe to expose — no passwords)."""
        payload = [{"id": p["id"], "label": p["label"], "host": p["host"]} for p in preset_servers]
        return jsonify({"servers": payload})

    @app.route('/load-status/<job_id>')
    def load_status(job_id):
        with load_lock:
            job = load_jobs.get(job_id)
            if not job:
                return jsonify({"status": "missing", "progress": 0, "message": "Not found"}), 404
            return jsonify({
                "status": job["status"],
                "progress": job["progress"],
                "message": job.get("message", "")
            })

    @app.route('/content/<job_id>')
    def content(job_id):
        if job_id == "fallback":
            return "<h1>Loading failed. Please refresh.</h1>", 503
        with load_lock:
            job = load_jobs.get(job_id)
            if not job:
                return "<h1>Loading job not found.</h1>", 404
            if job["status"] != "done" or not job.get("html"):
                return "<h1>Still loading...</h1>", 202
            html_content = job["html"]
        return html_content
    
    
    @app.route('/favicon.ico')
    def favicon():
        try:
            favicon_path = os.path.join(os.path.dirname(__file__), "favicon.ico")
            print(f"[DEBUG] Favicon path: {favicon_path}", flush=True)
            print(f"[DEBUG] Favicon exists: {os.path.exists(favicon_path)}", flush=True)
            if os.path.exists(favicon_path):
                return send_file(favicon_path, mimetype="image/x-icon")
            else:
                print(f"[ERROR] Favicon file not found at: {favicon_path}", flush=True)
                return "Favicon not found", 404
        except Exception as e:
            print(f"[ERROR] Favicon route error: {e}", flush=True)
            return "Favicon error", 500
    
    @app.route('/kodi.png')
    def serve_kodi_logo():
        """Serve Kodi logo image"""
        try:
            return send_file('kodi.png', mimetype='image/png')
        except Exception as e:
            return f"Kodi logo not found: {str(e)}", 404
    
    @app.route('/artwork/<filename>')
    def serve_artwork(filename):
        """Serve downloaded artwork files"""
        try:
            artwork_path = f"/app/output/artwork/{filename}"
            if os.path.exists(artwork_path):
                return send_file(artwork_path, mimetype='image/jpeg')
            else:
                return "Artwork not found", 404
        except Exception as e:
            return f"Error serving artwork: {str(e)}", 500
    
    @app.route('/background.jpg')
    def serve_background():
        """Serve background image"""
        try:
            background_path = "/app/background.jpg"
            if os.path.exists(background_path):
                return send_file(background_path, mimetype='image/jpeg')
            else:
                return "Background not found", 404
        except Exception as e:
            return f"Error serving background: {str(e)}", 500
    
    @app.route('/movies.png')
    def serve_movies_icon():
        """Serve movies icon"""
        try:
            return send_file('movies.png', mimetype='image/png')
        except Exception as e:
            return f"Movies icon not found: {str(e)}", 404
    
    @app.route('/tv.png')
    def serve_tv_icon():
        """Serve TV shows icon"""
        try:
            return send_file('tv.png', mimetype='image/png')
        except Exception as e:
            return f"TV icon not found: {str(e)}", 404
    
    @app.route('/music.png')
    def serve_music_icon():
        """Serve music icon"""
        try:
            return send_file('music.png', mimetype='image/png')
        except Exception as e:
            return f"Music icon not found: {str(e)}", 404
    
    @app.route('/new.png')
    def serve_new_icon():
        """Serve new icon"""
        try:
            return send_file('new.png', mimetype='image/png')
        except Exception as e:
            return f"New icon not found: {str(e)}", 404
    
    @app.route('/refresh.png')
    def serve_refresh_icon():
        """Serve refresh icon"""
        try:
            refresh_path = "/app/refresh.png"
            if os.path.exists(refresh_path):
                return send_file(refresh_path, mimetype='image/png')
            else:
                return "Refresh icon not found", 404
        except Exception as e:
            return f"Error serving refresh icon: {str(e)}", 500
    
    @app.route('/health')
    def health():
        return {"status": "healthy", "timestamp": datetime.now().isoformat()}
    
    @app.route('/update-video-library', methods=['POST'])
    def update_video_library():
        """Update video library using Kodi JSON-RPC"""
        ok, err = _run_kodi_rpc("VideoLibrary.Scan")
        if ok:
            return jsonify({"success": True, "message": "Video library update started successfully"})
        return jsonify({"success": False, "message": err})
    
    @app.route('/update-audio-library', methods=['POST'])
    def update_audio_library():
        """Update audio library using Kodi JSON-RPC"""
        ok, err = _run_kodi_rpc("AudioLibrary.Scan")
        if ok:
            return jsonify({"success": True, "message": "Audio library update started successfully"})
        return jsonify({"success": False, "message": err})
    
    @app.route('/clean-video-library', methods=['POST'])
    def clean_video_library():
        """Clean video library using Kodi JSON-RPC"""
        ok, err = _run_kodi_rpc("VideoLibrary.Clean")
        if ok:
            return jsonify({"success": True, "message": "Video library clean started successfully"})
        return jsonify({"success": False, "message": err})
    
    @app.route('/clean-music-library', methods=['POST'])
    def clean_music_library():
        """Clean music library using Kodi JSON-RPC"""
        ok, err = _run_kodi_rpc("AudioLibrary.Clean")
        if ok:
            return jsonify({"success": True, "message": "Music library clean started successfully"})
        return jsonify({"success": False, "message": err})
    
    print(f"🌐 Starting web server on port {web_port}")
    print(f"📊 Access statistics at: http://localhost:{web_port} or container host IP: http://{container_host}:{web_port}")
    print(f"🔗 Use this URL in Homarr iframe: http://localhost:{web_port} or container host IP: http://{container_host}:{web_port}")
    
    app.run(host='0.0.0.0', port=web_port, debug=False)


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Probe Kodi device for library statistics via JSON-RPC",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python kodi_info.py --host http://192.168.1.10:555
  python kodi_info.py --host 192.168.1.100 --port 8080 --username kodi --password mypass
  python kodi_info.py --host http://192.168.1.10:555 --save-html
  python kodi_info.py --host http://192.168.1.10:555 --web-server --web-port 5005
        """
    )
    
    parser.add_argument('--host', help='Kodi device URL (e.g., http://192.168.1.10:555) or IP address')
    parser.add_argument('--port', type=int, default=None, help='Kodi HTTP port (optional, extracted from host URL if provided)')
    parser.add_argument('--username', default='', help='Kodi username (optional)')
    parser.add_argument('--password', default='', help='Kodi password (optional)')
    parser.add_argument('--save-html', action='store_true', help='Save statistics to HTML file')
    parser.add_argument('--html-file', default='kodi_stats.html', 
                       help='HTML output filename (default: kodi_stats.html)')
    parser.add_argument('--save-json', action='store_true', help='Save statistics to JSON file')
    parser.add_argument('--json-file', default='kodi_library_stats.json', 
                       help='JSON output filename (default: kodi_library_stats.json)')
    parser.add_argument('--web-server', action='store_true', help='Start web server for Homarr integration')
    parser.add_argument('--web-port', type=int, default=5005, help='Web server port (default: 5005)')
    parser.add_argument('--container-host', default='localhost', help='Container host IP for external access (default: localhost)')
    
    args = parser.parse_args()
    
    # If web server mode, start the server
    if args.web_server:
        create_web_server(args.web_port, args.container_host)
        return
    
    # For non-web-server mode, host is required
    if not args.host:
        parser.error("--host is required when not using --web-server mode")
    
    print("🔍 Kodi Library Information Probe")
    print("=" * 40)
    print(f"Target: {args.host}:{args.port}")
    
    # Initialize probe
    probe = KodiLibraryProbe(args.host, args.port, args.username, args.password)
    
    # Connect to Kodi
    if not probe.connect():
        sys.exit(1)
    
    # Get all statistics
    stats = probe.get_all_statistics()
    
    # Print statistics
    print_statistics(stats)
    
    # Save to HTML if requested
    if args.save_html:
        save_statistics_to_html(stats, args.host, args.html_file)
    
    # Save to JSON if requested
    if args.save_json:
        save_statistics_to_json(stats, args.json_file)


if __name__ == "__main__":
    main()
