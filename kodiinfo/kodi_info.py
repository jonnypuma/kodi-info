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
import sys
import os
import time
import threading
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

try:
    import requests
    from flask import Flask, send_file, render_template_string, request, jsonify
except ImportError:
    print("Error: Required packages not found. Please install with: pip install -r requirements.txt")
    sys.exit(1)


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
        if host.startswith('http://') or host.startswith('https://'):
            from urllib.parse import urlparse
            parsed = urlparse(host)
            self.host = parsed.hostname
            self.port = parsed.port or (8080 if parsed.scheme == 'http' else 443)
            self.scheme = parsed.scheme
        else:
            self.host = host
            self.port = port or 8080
            self.scheme = 'http'
        
        # Ensure we're using IP address directly (no DNS resolution)
# Debug logging removed for security
        
        self.username = username
        self.password = password
        self.base_url = f"{self.scheme}://{self.host}:{self.port}/jsonrpc"
        self.auth = (self.username, self.password) if self.username and self.password else None
        self.headers = {"Content-Type": "application/json"}
        
    def connect(self) -> bool:
        """
        Establish connection to Kodi device
        
        Returns:
            True if connection successful, False otherwise
        """
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
                return False
            
        except Exception as e:
            print(f"✗ Failed to connect to Kodi at {self.base_url}")
            print(f"  Error: {str(e)}")
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
            
            # Try to use VideoLibrary.GetStatistics first (much faster)
            try:
                stats_result = self._make_request("VideoLibrary.GetStatistics", {}, timeout=30)
                if stats_result and "result" in stats_result:
                    stats = stats_result["result"].get("statistics", {})
                    total_episodes = stats.get("episode", 0)
                    watched_episodes = stats.get("episode.watched", 0)
                    print(f"📊 Using GetStatistics: {total_episodes} episodes, {watched_episodes} watched")
                else:
                    raise Exception("GetStatistics failed")
            except:
                print("📺 GetStatistics failed, falling back to GetEpisodes...")
                # Fallback: Get episodes with playcount (use longer timeout for large datasets)
                episodes_result = self._make_request("VideoLibrary.GetEpisodes", {
                    "properties": ["playcount"],
                    "limits": {"start": 0, "end": 100000}
                }, timeout=120)
                
                episodes = episodes_result.get("result", {}).get("episodes", [])
                total_episodes = episodes_result.get("result", {}).get("limits", {}).get("total", 0)
                watched_episodes = sum(1 for episode in episodes 
                                     if episode.get("playcount", 0) > 0)
            
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

def generate_html(stats: LibraryStats, kodi_host: str, last_updated: str, probe=None) -> str:
    """Generate HTML output for Homarr iframe integration"""
    
    # Calculate percentages
    movie_watch_percentage = (stats.watched_movies / stats.total_movies * 100) if stats.total_movies > 0 else 0
    episode_watch_percentage = (stats.watched_episodes / stats.total_episodes * 100) if stats.total_episodes > 0 else 0
    
    # Format recently added items
    recent_movies = [format_recent_item(movie, 'movie', kodi_host, probe) for movie in stats.recently_added.movies]
    recent_episodes = [format_recent_item(episode, 'episode', kodi_host, probe) for episode in stats.recently_added.episodes]
    recent_albums = [format_recent_item(album, 'album', kodi_host, probe) for album in stats.recently_added.albums]
    
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
    
    # Clean HTML template
    return f"""
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
        .buttons {{ text-align: center; margin-top: 30px; }}
        .btn {{ background: #007bff; color: white; border: none; padding: 10px 20px; margin: 0 10px; border-radius: 5px; cursor: pointer; }}
        .btn:hover {{ background: #0056b3; }}
        .btn:disabled {{ background: #6c757d; cursor: not-allowed; }}
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
        }}
        .image-overlay.visible img {{
            transform: scale(1);
        }}
        .zoomable {{
            cursor: zoom-in;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <img src="/kodi.png" alt="Kodi Logo" style="height: 120px; margin-bottom: 10px;">
            <h1>Library Statistics</h1>
            <p>Connected to: {kodi_host}</p>
            <p>Last updated: {last_updated}</p>
        </div>
        
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
        
        <div class="buttons">
            <button id="update-video-btn" class="btn" onclick="updateLibrary('video')">Update Video Library</button>
            <button id="update-audio-btn" class="btn" onclick="updateLibrary('audio')">Update Audio Library</button>
            <button id="clean-video-btn" class="btn" onclick="cleanLibrary('video')">Clean Video Library</button>
            <button id="clean-music-btn" class="btn" onclick="cleanLibrary('music')">Clean Music Library</button>
            <img src="/refresh.png" alt="Refresh" onclick="location.reload()" style="width: 40px; height: 40px; margin-left: 10px; cursor: pointer; vertical-align: middle;" title="Refresh page">
        </div>
    </div>
    <div id="image-overlay" class="image-overlay">
        <img id="overlay-image" src="" alt="Artwork preview">
    </div>
    
    <script>
        function updateLibrary(type) {{
            const button = document.getElementById('update-' + type + '-btn');
            button.disabled = true;
            button.textContent = 'Updating...';
            
            fetch('/update-' + type + '-library', {{method: 'POST'}})
                .then(response => response.json())
                .then(data => {{
                    if (data.success) {{
                        button.textContent = 'Success!';
                        button.style.background = '#28a745';
                    }} else {{
                        button.textContent = 'Error: ' + data.message;
                        button.style.background = '#dc3545';
                    }}
                    
                    setTimeout(() => {{
                        button.disabled = false;
                        button.textContent = type === 'video' ? 'Update Video Library' : 'Update Audio Library';
                        button.style.background = '';
                    }}, 5000);
                }})
                .catch(error => {{
                    button.textContent = 'Error';
                    button.style.background = '#dc3545';
                    setTimeout(() => {{
                        button.disabled = false;
                        button.textContent = type === 'video' ? 'Update Video Library' : 'Update Audio Library';
                        button.style.background = '';
                    }}, 5000);
                }});
        }}
        
        function cleanLibrary(type) {{
            const button = document.getElementById('clean-' + type + '-btn');
            button.disabled = true;
            button.textContent = 'Cleaning...';
            
            const endpoint = type === 'video' ? '/clean-video-library' : '/clean-music-library';
            fetch(endpoint, {{method: 'POST'}})
                .then(response => response.json())
                .then(data => {{
                    if (data.success) {{
                        button.textContent = 'Success!';
                        button.style.background = '#28a745';
                    }} else {{
                        button.textContent = 'Error: ' + data.message;
                        button.style.background = '#dc3545';
                    }}
                    
                    setTimeout(() => {{
                        button.disabled = false;
                        button.textContent = type === 'video' ? 'Clean Video Library' : 'Clean Music Library';
                        button.style.background = '';
                    }}, 5000);
                }})
                .catch(error => {{
                    button.textContent = 'Error';
                    button.style.background = '#dc3545';
                    setTimeout(() => {{
                        button.disabled = false;
                        button.textContent = type === 'video' ? 'Clean Video Library' : 'Clean Music Library';
                        button.style.background = '';
                    }}, 5000);
                }});
        }}
        
            // Auto-refresh happens automatically on container startup
            console.log('Setting up 24-hour refresh cycle...');
            
            // Set up 24-hour refresh cycle
            setTimeout(() => {{
                console.log('Auto-reloading page after 24 hours...');
                window.location.reload();
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
                    overlayImg.src = img.src;
                    overlay.classList.add('visible');
                }});
            }});

            // Close overlay on any click
            overlay.addEventListener('click', () => {{
                overlay.classList.remove('visible');
                overlayImg.src = '';
            }});

            // Also close on Escape key
            document.addEventListener('keydown', event => {{
                if (event.key === 'Escape' && overlay.classList.contains('visible')) {{
                    overlay.classList.remove('visible');
                    overlayImg.src = '';
                }}
            }});
    </script>
</body>
</html>
    """


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

def create_web_server(web_port: int = 5005, container_host: str = "localhost"):
    """Create Flask web server to serve HTML statistics"""
    app = Flask(__name__)
    
    # Get Kodi connection details from environment variables - optionally input youur credenctials as fallcack below
    kodi_host = os.getenv("KODI_HOST", "http://192.168.1.10:555")
    kodi_username = os.getenv("KODI_USERNAME", "user")
    kodi_password = os.getenv("KODI_PASSWORD", "pass")
    
# Debug logging removed for security
    
    @app.route('/')
    def index():
        try:
            # Create probe instance
# Debug logging removed for security
            probe = KodiLibraryProbe(kodi_host, None, kodi_username, kodi_password)
            
            # Connect to Kodi
            if not probe.connect():
                return f"<h1>Error: Could not connect to Kodi at {kodi_host}</h1>", 500
            
            # Get statistics
            stats = probe.get_all_statistics()
            last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Generate HTML (page is already refreshed automatically on startup)
            html_content = generate_html(stats, kodi_host, last_updated, probe)
            return html_content
            
        except Exception as e:
            return f"<h1>Error: {str(e)}</h1>", 500
    
    
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
        try:
            import subprocess
            
            # Build curl command for video library scan
            curl_cmd = [
                'curl', '-X', 'POST',
                '-H', 'Content-Type: application/json',
                '-d', '{"jsonrpc": "2.0", "method": "VideoLibrary.Scan", "id": 1}'
            ]
            
            # Add authentication if provided
            if kodi_username and kodi_password:
                # kodi_host already includes http://, so we need to insert auth
                auth_url = kodi_host.replace('http://', f'http://{kodi_username}:{kodi_password}@')
                curl_cmd.append(f'{auth_url}/jsonrpc')
            else:
                curl_cmd.append(f'{kodi_host}/jsonrpc')
            
            # Execute curl command
            result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                # Check if response contains "OK"
                if '"result":"OK"' in result.stdout:
                    return jsonify({"success": True, "message": "Video library update started successfully"})
                else:
                    return jsonify({"success": False, "message": f"Unexpected response: {result.stdout}"})
            else:
                return jsonify({"success": False, "message": f"Error: {result.stderr}"})
                
        except subprocess.TimeoutExpired:
            return jsonify({"success": False, "message": "Request timed out"})
        except Exception as e:
            return jsonify({"success": False, "message": f"Error: {str(e)}"})
    
    @app.route('/update-audio-library', methods=['POST'])
    def update_audio_library():
        """Update audio library using Kodi JSON-RPC"""
        try:
            import subprocess
            
            # Build curl command for audio library scan
            curl_cmd = [
                'curl', '-X', 'POST',
                '-H', 'Content-Type: application/json',
                '-d', '{"jsonrpc": "2.0", "method": "AudioLibrary.Scan", "id": 1}'
            ]
            
            # Add authentication if provided
            if kodi_username and kodi_password:
                # kodi_host already includes http://, so we need to insert auth
                auth_url = kodi_host.replace('http://', f'http://{kodi_username}:{kodi_password}@')
                curl_cmd.append(f'{auth_url}/jsonrpc')
            else:
                curl_cmd.append(f'{kodi_host}/jsonrpc')
            
            # Execute curl command
            result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                # Check if response contains "OK"
                if '"result":"OK"' in result.stdout:
                    return jsonify({"success": True, "message": "Audio library update started successfully"})
                else:
                    return jsonify({"success": False, "message": f"Unexpected response: {result.stdout}"})
            else:
                return jsonify({"success": False, "message": f"Error: {result.stderr}"})
                
        except subprocess.TimeoutExpired:
            return jsonify({"success": False, "message": "Request timed out"})
        except Exception as e:
            return jsonify({"success": False, "message": f"Error: {str(e)}"})
    
    @app.route('/clean-video-library', methods=['POST'])
    def clean_video_library():
        """Clean video library using Kodi JSON-RPC"""
        try:
            import subprocess
            
            # Build curl command for video library clean
            curl_cmd = [
                'curl', '-X', 'POST',
                '-H', 'Content-Type: application/json',
                '-d', '{"jsonrpc": "2.0", "method": "VideoLibrary.Clean", "id": 1}'
            ]
            
            # Add authentication if provided
            if kodi_username and kodi_password:
                # kodi_host already includes http://, so we need to insert auth
                auth_url = kodi_host.replace('http://', f'http://{kodi_username}:{kodi_password}@')
                curl_cmd.append(f'{auth_url}/jsonrpc')
            else:
                curl_cmd.append(f'{kodi_host}/jsonrpc')
            
            # Execute curl command
            result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                # Check if response contains "OK"
                if '"result":"OK"' in result.stdout:
                    return jsonify({"success": True, "message": "Video library clean started successfully"})
                else:
                    return jsonify({"success": False, "message": f"Unexpected response: {result.stdout}"})
            else:
                return jsonify({"success": False, "message": f"Error: {result.stderr}"})
                
        except subprocess.TimeoutExpired:
            return jsonify({"success": False, "message": "Request timed out"})
        except Exception as e:
            return jsonify({"success": False, "message": f"Error: {str(e)}"})
    
    @app.route('/clean-music-library', methods=['POST'])
    def clean_music_library():
        """Clean music library using Kodi JSON-RPC"""
        try:
            import subprocess
            
            # Build curl command for audio library clean
            curl_cmd = [
                'curl', '-X', 'POST',
                '-H', 'Content-Type: application/json',
                '-d', '{"jsonrpc": "2.0", "method": "AudioLibrary.Clean", "id": 1}'
            ]
            
            # Add authentication if provided
            if kodi_username and kodi_password:
                # kodi_host already includes http://, so we need to insert auth
                auth_url = kodi_host.replace('http://', f'http://{kodi_username}:{kodi_password}@')
                curl_cmd.append(f'{auth_url}/jsonrpc')
            else:
                curl_cmd.append(f'{kodi_host}/jsonrpc')
            
            # Execute curl command
            result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                # Check if response contains "OK"
                if '"result":"OK"' in result.stdout:
                    return jsonify({"success": True, "message": "Music library clean started successfully"})
                else:
                    return jsonify({"success": False, "message": f"Unexpected response: {result.stdout}"})
            else:
                return jsonify({"success": False, "message": f"Error: {result.stderr}"})
                
        except subprocess.TimeoutExpired:
            return jsonify({"success": False, "message": "Request timed out"})
        except Exception as e:
            return jsonify({"success": False, "message": f"Error: {str(e)}"})
    
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
