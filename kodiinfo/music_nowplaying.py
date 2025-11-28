"""
Music-specific HTML generation for Kodi Now Playing application.
Handles music display with album poster, discart/cdart spinning animation, and music-specific layout.
"""

def generate_html(item, session_id, downloaded_art, progress_data, details):
    """
    Generate HTML for music display.
    
    Args:
        item (dict): Media item from Kodi API
        session_id (str): Session ID for file naming
        downloaded_art (dict): Downloaded artwork files
        progress_data (dict): Playback progress information
        details (dict): Detailed media information
        
    Returns:
        str: HTML content for music display
    """
    # Extract additional details from the enhanced API calls (define early to avoid variable scope issues)
    # Use safe fallbacks to prevent crashes
    if isinstance(details, dict):
        album_details = details.get("album", {})
        artist_details = details.get("artist", {})
    else:
        print(f"[WARNING] Details is not a dict: {type(details)}, value: {details}", flush=True)
        album_details = {}
        artist_details = {}
        # If details is not a dict, create a safe fallback
        if not isinstance(details, dict):
            details = {}
    
    # Extract URLs for artwork - use safe fallbacks
    try:
        # Ensure downloaded_art is a dict
        if not isinstance(downloaded_art, dict):
            print(f"[WARNING] Downloaded_art is not a dict: {type(downloaded_art)}", flush=True)
            downloaded_art = {}
        
        # For music, use thumbnail for album artwork, fallback to poster
        album_poster_url = f"/media/{downloaded_art.get('thumbnail')}" if downloaded_art.get("thumbnail") else f"/media/{downloaded_art.get('poster')}" if downloaded_art.get("poster") else ""
        # Collect all fanart variants for slideshow
        fanart_variants = []
        
        # First, check for extrafanart folder images (dynamic keys like extrafanart_main, extrafanart_fanart2, etc.)
        # Note: Files in extrafanart folder are named fanart.jpg, fanart2.jpg, etc.
        for key, value in downloaded_art.items():
            if key.startswith("extrafanart"):
                fanart_variants.append(f"/media/{value}")
        
        # If no extrafanart found, fall back to numbered fanart variants
        if not fanart_variants:
            fanart_keys = ["fanart", "fanart1", "fanart2", "fanart3", "fanart4", "fanart5", "fanart6", "fanart7", "fanart8", "fanart9"]
            for fanart_key in fanart_keys:
                if downloaded_art.get(fanart_key):
                    fanart_variants.append(f"/media/{downloaded_art.get(fanart_key)}")
        
        # If no downloaded fanarts, try to get from various sources
        if not fanart_variants:
            fallback_fanart = ""
            if isinstance(album_details, dict) and album_details.get("fanart"):
                fallback_fanart = album_details.get("fanart")
                print(f"[DEBUG] Using album fanart: {fallback_fanart}", flush=True)
            elif isinstance(artist_details, dict) and artist_details.get("fanart"):
                fallback_fanart = artist_details.get("fanart")
                print(f"[DEBUG] Using artist fanart: {fallback_fanart}", flush=True)
            elif item.get("art", {}).get("fanart"):
                fallback_fanart = item.get("art", {}).get("fanart")
                print(f"[DEBUG] Using item fanart: {fallback_fanart}", flush=True)
            elif item.get("art", {}).get("albumartist.fanart"):
                fallback_fanart = item.get("art", {}).get("albumartist.fanart")
                print(f"[DEBUG] Using albumartist.fanart: {fallback_fanart}", flush=True)
            elif item.get("art", {}).get("artist.fanart"):
                fallback_fanart = item.get("art", {}).get("artist.fanart")
                print(f"[DEBUG] Using artist.fanart: {fallback_fanart}", flush=True)
            
            if fallback_fanart:
                fanart_variants.append(fallback_fanart)
        
        print(f"[DEBUG] Fanart variants found: {len(fanart_variants)}", flush=True)
        print(f"[DEBUG] Fanart variants content: {fanart_variants}", flush=True)
        # For music, don't use fanart as primary background - only for slideshow
        # The slideshow will handle all fanart variants
        fanart_url = ""
    except Exception as e:
        print(f"[WARNING] Artwork URL generation failed: {e}", flush=True)
        print(f"[WARNING] Exception type: {type(e)}", flush=True)
        import traceback
        print(f"[WARNING] Traceback: {traceback.format_exc()}", flush=True)
        album_poster_url = ""
        fanart_url = ""
        fanart_variants = []
    # Look for both discart and cdart for music
    discart_url = f"/media/{downloaded_art.get('discart')}" if downloaded_art.get("discart") else ""
    cdart_url = f"/media/{downloaded_art.get('cdart')}" if downloaded_art.get("cdart") else ""
    # Use discart if available, otherwise use cdart
    discart_display_url = discart_url if discart_url else cdart_url
    back_cover_path = ""
    if isinstance(downloaded_art, dict):
        priority_back_keys = ["back", "backcover", "rear", "rearcover"]
        for back_key in priority_back_keys:
            if downloaded_art.get(back_key):
                back_cover_path = downloaded_art.get(back_key)
                break
        if not back_cover_path:
            for key, value in downloaded_art.items():
                if not value or not isinstance(value, str):
                    continue
                key_lower = str(key).lower()
                value_lower = value.lower()
                if "background" in key_lower or "background" in value_lower:
                    continue
                if "back" in key_lower or "backcover" in key_lower or "rear" in key_lower:
                    back_cover_path = value
                    break
                if "back" in value_lower or "rear" in value_lower:
                    back_cover_path = value
                    break
    back_cover_url = f"/media/{back_cover_path}" if back_cover_path else ""
    if back_cover_path:
        print(f"[DEBUG] Back cover detected: {back_cover_path}", flush=True)
    # Only use banner if it's not actually a fanart image
    banner_url = ""
    if downloaded_art.get("banner"):
        # Check if the banner is actually a fanart by looking at the filename
        banner_filename = downloaded_art.get("banner", "")
        print(f"[DEBUG] Banner filename: {banner_filename}", flush=True)
        if not any(fanart_name in banner_filename.lower() for fanart_name in ["fanart", "fanart1", "fanart2", "fanart3", "fanart4"]):
            banner_url = f"/media/{downloaded_art.get('banner')}"
            print(f"[DEBUG] Using banner: {banner_url}", flush=True)
        else:
            print(f"[DEBUG] Skipping banner as it appears to be a fanart image", flush=True)
    clearlogo_url = f"/media/{downloaded_art.get('clearlogo')}" if downloaded_art.get("clearlogo") else ""
    # For music, disable clearart completely to prevent fanart from showing underneath album cover
    # Clearart often gets confused with fanart in music libraries
    clearart_url = ""
    if downloaded_art.get("clearart"):
        clearart_filename = downloaded_art.get("clearart", "")
        print(f"[DEBUG] Clearart filename: {clearart_filename}", flush=True)
        print(f"[DEBUG] Skipping clearart for music to prevent fanart display underneath album cover", flush=True)
    
    # Extract music information
    title = item.get("title", "Untitled Track")
    album = item.get("album", "")
    artist = item.get("artist", [])
    artist_names = ", ".join(artist) if artist else "Unknown Artist"
    plot = item.get("plot", item.get("description", ""))
    
    # Additional details already extracted above
    
    # Get artist biography (use description field from official schema)
    artist_bio = artist_details.get("description", "") if isinstance(artist_details, dict) else ""
    
    # Get additional album info (fallback to item data if API failed)
    album_year = album_details.get("year", item.get("year", "")) if isinstance(album_details, dict) else item.get("year", "")
    album_rating = album_details.get("rating", item.get("rating", 0)) if isinstance(album_details, dict) else item.get("rating", 0)
    
    # Get additional song info - ensure details is a dict
    if not isinstance(details, dict):
        details = {}
    song_comment = details.get("comment", "")
    song_lyrics = details.get("lyrics", "")
    song_disc = details.get("disc", 0)
    song_votes = details.get("votes", 0)
    song_user_rating = details.get("userrating", 0)
    song_bpm = details.get("bpm", 0)
    song_samplerate = details.get("samplerate", 0)
    song_bitrate = details.get("bitrate", 0)
    song_channels = details.get("channels", 0)
    song_track = details.get("track", 0)
    record_label = album_details.get("albumlabel", "") if isinstance(album_details, dict) else ""
    song_release_date = details.get("releasedate", "")
    song_original_date = details.get("originaldate", "")
    
    # Get album details for totaldiscs
    album_details = details.get("album", {}) if isinstance(details, dict) else {}
    total_discs = album_details.get("totaldiscs", 1)
    
    # Create music badge components
    # Only show disc badge if album has 2 or more discs
    disc_badge = f"Disc {song_disc}" if song_disc > 0 and total_discs >= 2 else ""
    track_badge = f"Track {song_track:02d}" if song_track > 0 else ""
    title_badge = title if title else ""
    
    
    # Get additional artist info - ensure artist_details is a dict
    if not isinstance(artist_details, dict):
        artist_details = {}
    artist_born = artist_details.get("born", "")
    artist_formed = artist_details.get("formed", "")
    artist_years_active = artist_details.get("yearsactive", "")
    artist_genre = artist_details.get("genre", [])
    artist_mood = artist_details.get("mood", [])
    artist_style = artist_details.get("style", [])
    artist_gender = artist_details.get("gender", "")
    artist_instrument = artist_details.get("instrument", [])
    artist_type = artist_details.get("type", "")
    artist_sortname = artist_details.get("sortname", "")
    artist_disambiguation = artist_details.get("disambiguation", "")
    
    # If API calls failed, use basic item data
    if not isinstance(album_details, dict) and album:
        album_details = {"title": album, "year": item.get("year", "")}
    if not isinstance(artist_details, dict) and artist_names:
        artist_details = {"name": artist_names}
    
    # Debug logging
    print(f"[DEBUG] Album details: {album_details}", flush=True)
    print(f"[DEBUG] Artist details: {artist_details}", flush=True)
    print(f"[DEBUG] Fanart URL: {fanart_url}", flush=True)
    print(f"[DEBUG] Album year: {album_year}, Album rating: {album_rating}", flush=True)
    
    # Get rating from details or fallback - ensure details is a dict
    if not isinstance(details, dict):
        details = {}
    rating = round(details.get("rating", 0.0), 1)
    rating_html = f"<strong>⭐ {rating}</strong>" if rating > 0 else ""
    
    # Initialize defaults
    hdr_type = "SDR"
    audio_languages = "N/A"
    subtitle_languages = "N/A"
    
    # Extract streamdetails - ensure details is a dict
    if not isinstance(details, dict):
        details = {}
    streamdetails = details.get("streamdetails", {})
    if not isinstance(streamdetails, dict):
        streamdetails = {}
    video_info = streamdetails.get("video", [{}])[0] if isinstance(streamdetails.get("video"), list) and len(streamdetails.get("video", [])) > 0 else {}
    audio_info = streamdetails.get("audio", []) if isinstance(streamdetails.get("audio"), list) else []
    subtitle_info = streamdetails.get("subtitle", []) if isinstance(streamdetails.get("subtitle"), list) else []
    
    # HDR type (usually not applicable for music, but keeping for consistency)
    hdr_type = video_info.get("hdrtype", "").upper() or "SDR"
    
    # Get enhanced audio information using XBMC.GetInfoLabels for real-time data
    enhanced_audio_info = {}
    try:
        # Import the kodi_rpc function from the main module
        import sys
        import os
        import importlib.util
        
        # Load the kodi-nowplaying.py module (with hyphen)
        spec = importlib.util.spec_from_file_location("kodi_nowplaying", "kodi-nowplaying.py")
        kodi_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(kodi_module)
        kodi_rpc = kodi_module.kodi_rpc
        
        print(f"[DEBUG] Attempting to get enhanced audio info via XBMC.GetInfoLabels", flush=True)
        
        # Get real-time audio information
        infolabels_response = kodi_rpc("XBMC.GetInfoLabels", {
            "labels": [
                "VideoPlayer.AudioCodec",
                "VideoPlayer.Container",
                "MusicPlayer.BitsPerSample",
                "Player.Process(AudioSamplerate)",
                "Player.Process(AudioChannels)"
            ]
        })
        
        print(f"[DEBUG] XBMC.GetInfoLabels response: {infolabels_response}", flush=True)
        
        if infolabels_response and infolabels_response.get("result"):
            enhanced_audio_info = infolabels_response.get("result", {})
            print(f"[DEBUG] Enhanced audio info extracted: {enhanced_audio_info}", flush=True)
        else:
            print(f"[DEBUG] No result in XBMC.GetInfoLabels response", flush=True)
    except Exception as e:
        print(f"[DEBUG] Failed to get enhanced audio info: {e}", flush=True)
        import traceback
        print(f"[DEBUG] Traceback: {traceback.format_exc()}", flush=True)
        enhanced_audio_info = {}
    
    # Audio languages
    audio_languages = ", ".join(sorted(set(
        a.get("language", "")[:3].upper() for a in audio_info if a.get("language")
    ))) or "N/A"
    
    # Subtitle languages
    subtitle_languages = ", ".join(sorted(set(
        s.get("language", "")[:3].upper() for s in subtitle_info if s.get("language")
    ))) or "N/A"
    
    # Genre and formatting - ensure details is a dict
    if not isinstance(details, dict):
        details = {}
    genre_list = details.get("genre", [])
    if not isinstance(genre_list, list):
        genre_list = []
    genres = [g.capitalize() for g in genre_list]
    genre_badges = genres[:3]
    
    # Format media info
    resolution = "Audio"  # Music doesn't have video resolution
    
    # Enhanced audio codec information using real-time data
    audio_codec = enhanced_audio_info.get("VideoPlayer.AudioCodec", audio_info[0].get("codec", "Unknown") if audio_info else "Unknown").upper()
    channels = audio_info[0].get("channels", 0) if audio_info else 0
    
    # Get audio bits per sample from enhanced audio info
    audio_bits_per_sample = enhanced_audio_info.get("MusicPlayer.BitsPerSample", 0)
    try:
        audio_bits_per_sample = int(audio_bits_per_sample) if audio_bits_per_sample else 0
    except (ValueError, TypeError):
        audio_bits_per_sample = 0
    
    # If MusicPlayer.BitsPerSample doesn't work, try to get from streamdetails
    if audio_bits_per_sample == 0 and audio_info:
        # Try to estimate from bitrate and sample rate
        audio_samplerate = enhanced_audio_info.get("Player.Process(AudioSamplerate)", 0)
        audio_channels = enhanced_audio_info.get("Player.Process(AudioChannels)", 0)
        try:
            audio_samplerate = int(audio_samplerate) if audio_samplerate else 0
            audio_channels = int(audio_channels) if audio_channels else 0
            if audio_samplerate > 0 and audio_channels > 0:
                # Rough estimation: if sample rate is 96kHz or higher, likely 24-bit
                audio_bits_per_sample = 24 if audio_samplerate >= 96000 else 16
        except (ValueError, TypeError):
            pass
    
    # New enhanced audio information - use real-time data first, fallback to filename extension
    container_format = enhanced_audio_info.get("VideoPlayer.Container", "").upper()
    # Only use filename extension as fallback if container is empty from JSON
    if not container_format and item.get("file"):
        file_path = item.get("file", "")
        if file_path.lower().endswith('.flac'):
            container_format = "FLAC"
        elif file_path.lower().endswith('.mp3'):
            container_format = "MP3"
        elif file_path.lower().endswith('.m4a'):
            container_format = "M4A"
        elif file_path.lower().endswith('.wav'):
            container_format = "WAV"
        elif file_path.lower().endswith('.ogg'):
            container_format = "OGG"
        elif file_path.lower().endswith('.aac'):
            container_format = "AAC"
    
    # Playback progress
    elapsed = progress_data.get("elapsed", 0)
    duration = progress_data.get("duration", 0)
    percent = int((elapsed / duration) * 100) if duration else 0
    paused = progress_data.get("paused", False)
    
    # Debug: Check fanart_variants before HTML generation
    print(f"[DEBUG] Before HTML generation - fanart_variants length: {len(fanart_variants)}", flush=True)
    print(f"[DEBUG] Before HTML generation - fanart_variants content: {fanart_variants}", flush=True)
    
    # Generate HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <link rel="icon" type="image/x-icon" href="/static/favicon.ico">
      <style>
        body {{
          font-family: sans-serif;
          animation: fadeIn 1s;
          position: relative;
          margin: 0;
          padding: 0;
          opacity: 1;
          transition: opacity 1.5s ease;
          overflow-x: hidden;
        }}
        
        .fanart-container {{
          position: fixed;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          z-index: -1;
        }}
        
        .fanart-slide {{
          position: absolute;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          background-size: cover;
          background-position: center;
          background-repeat: no-repeat;
          opacity: 0;
          transition: opacity 2s ease-in-out;
        }}
        
        .fanart-slide.active {{
          opacity: 1;
        }}
        
        .fanart-slide.fade-out {{
          opacity: 0;
        }}
        body.fade-out {{
          opacity: 0;
        }}
        .content {{
          position: relative;
          background: rgba(0,0,0,0.5);
          border-radius: 12px;
          padding: 80px 40px 40px 40px;
          backdrop-filter: blur(5px);
          box-shadow: 0 8px 32px rgba(0,0,0,0.8);
          color: white;
          text-shadow: 0 2px 6px rgba(0,0,0,0.7), 0 0 8px rgba(0,0,0,0.5);
        }}
        .three-column-layout {{
          display: flex;
          gap: 40px;
          align-items: flex-start;
        }}
        .column-left {{
          flex: 0 0 auto;
        }}
        .column-middle {{
          flex: 0 0 828px;
          display: flex;
          flex-direction: column;
          gap: 15px;
        }}
        .column-right {{
          flex: 1;
          display: flex;
          flex-direction: column;
          gap: 20px;
        }}
        .album-description {{
          background: rgba(0,0,0,0.3);
          padding: 15px;
          border-radius: 8px;
          border-left: 4px solid #4caf50;
          font-size: 1.0em;
          line-height: 1.5;
          max-height: 200px;
          overflow-y: auto;
        }}
        /* Custom Scrollbar Styling */
        .album-description::-webkit-scrollbar {{
          width: 8px;
          height: 8px;
        }}
        .album-description::-webkit-scrollbar-track {{
          background: rgba(255, 255, 255, 0.1);
          border-radius: 4px;
          -webkit-box-shadow: inset 0 0 2px rgba(0,0,0,0.1);
        }}
        .album-description::-webkit-scrollbar-thumb {{
          background: rgba(255, 255, 255, 0.3);
          border-radius: 4px;
          border: 1px solid rgba(255, 255, 255, 0.2);
          -webkit-box-shadow: inset 0 0 2px rgba(0,0,0,0.1);
        }}
        .album-description::-webkit-scrollbar-thumb:hover {{
          background: linear-gradient(180deg, #4caf50 0%, #45a049 100%) !important;
          border: 1px solid rgba(255, 255, 255, 0.4) !important;
          -webkit-box-shadow: 0 0 8px rgba(76, 175, 80, 0.6), inset 0 0 2px rgba(0,0,0,0.1) !important;
        }}
        .album-description::-webkit-scrollbar-thumb:active {{
          background: linear-gradient(180deg, #45a049 0%, #3d8b40 100%) !important;
        }}
        .album-description::-webkit-scrollbar-corner {{
          background: rgba(255, 255, 255, 0.1);
        }}
        
        /* Firefox scrollbar styling */
        .album-description {{
          scrollbar-width: thin;
          scrollbar-color: rgba(255, 255, 255, 0.3) rgba(255, 255, 255, 0.1);
        }}
        
        /* Firefox hover effect using CSS custom properties */
        .album-description:hover {{
          scrollbar-color: #4caf50 rgba(255, 255, 255, 0.1);
        }}
        .poster-container {{
          position: relative;
          overflow: visible;
          height: 260px;
          width: 240px;
          margin-top: 60px;
          perspective: 1200px;
          box-sizing: border-box;
        }}
        .poster-container.flip-enabled .album-flip {{
          cursor: pointer;
        }}
        .poster-container.flip-enabled {{
          padding-top: 20px;
        }}
        .poster-container:not(.flip-enabled) .poster {{
          margin-top: 20px;
        }}
        .poster {{
          height: 240px;
          width: 240px;
          border-radius: 8px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.6);
          position: relative;
          z-index: 2;
          object-fit: cover;
          cursor: zoom-in !important;
        }}
        .poster-container.flip-enabled .poster {{
          position: absolute;
          top: 0;
          left: 0;
          z-index: 2;
          backface-visibility: hidden;
        }}
        .poster-container.flip-enabled .poster.back-face {{
          transform: rotateY(180deg);
        }}
        .album-flip {{
          position: relative;
          width: 100%;
          height: 100%;
          transform-style: preserve-3d;
          transition: transform 0.8s ease;
          z-index: 2;
        }}
        .poster-container.flip-enabled .album-flip {{
          margin-top: 20px;
        }}
        .poster-container.flip-enabled .album-flip:focus {{
          outline: none;
          box-shadow: 0 0 0 3px rgba(76,175,80,0.6);
          border-radius: 8px;
        }}
        .album-flip.flipped {{
          transform: rotateY(180deg);
        }}
        .flip-indicator {{
          position: absolute;
          bottom: 6px;
          right: 6px;
          background: rgba(0,0,0,0.6);
          color: white;
          font-size: 0.75em;
          padding: 4px 10px;
          border-radius: 12px;
          pointer-events: none;
          opacity: 0;
          transition: opacity 0.3s ease;
          z-index: 5;
        }}
        .poster-container.flip-enabled:hover .flip-indicator,
        .poster-container.flip-enabled:focus-within .flip-indicator {{
          opacity: 1;
        }}
        .discart-wrapper {{
          position: absolute;
          top: -95px;
          left: 50%;
          transform: translate(-50%, 0);
          z-index: 1;
          height: 220px;
          width: 220px;
          pointer-events: none;
          transition: transform 0.35s ease, opacity 0.35s ease;
        }}
        .discart {{
          width: 220px;
          animation: spin 6s linear infinite;
          animation-play-state: running;
          opacity: 1;
          filter: drop-shadow(0 0 4px rgba(0,0,0,0.6));
          pointer-events: none;
        }}
        .discart-wrapper.retracted {{
          transform: translate(-50%, 60px) scale(0.75);
          opacity: 0;
        }}
        .discart-wrapper.retracted .discart {{
          animation-play-state: paused;
        }}
        .discart.paused {{
          animation-play-state: paused;
        }}
        @keyframes spin {{
          from {{ transform: rotate(0deg); }}
          to  {{ transform: rotate(360deg); }}
        }}
        .progress-wrapper {{
          display: flex;
          align-items: center;
          gap: 12px;
          margin-top: 6px;
          width: 100%;
          max-width: 600px;
          box-sizing: border-box;
        }}
        .progress {{
          flex: 1;
          min-width: 0;
          background: #2a2a2a;
          border-radius: 15px;
          height: 20px;
          overflow: hidden;
          border: 1px solid rgba(0,0,0,0.75);
          box-shadow: 
            inset 0 1px 0 rgba(255,255,255,0.1),
            inset 0 0 5px rgba(0,0,0,0.3),
            0 2px 2px rgba(255,255,255,0.1),
            inset 0 5px 10px rgba(0,0,0,0.4);
          position: relative;
        }}
        .bar {{
          background: linear-gradient(135deg, #4caf50 0%, #45a049 50%, #4caf50 100%);
          height: 20px;
          border-radius: 15px 3px 3px 15px;
          width: {percent}%;
          transition: width 0.5s;
          position: relative;
          box-shadow: 
            inset 0 8px 0 rgba(255,255,255,0.2),
            inset 0 1px 1px rgba(0,0,0,0.125);
          border-right: 1px solid rgba(0,0,0,0.3);
        }}
        .small {{
          font-size: 0.9em;
          color: #ccc;
        }}
        .badges {{
          display: flex;
          gap: 8px;
          margin-top: 10px;
          flex-wrap: wrap;
          align-items: center;
        }}
        .badge {{
          background: #333;
          color: white;
          padding: 4px 10px;
          border-radius: 20px;
          font-size: 0.8em;
          box-shadow: 0 2px 6px rgba(0,0,0,0.4);
          text-shadow: none;
        }}
        .badge-imdb {{
          display: flex;
          align-items: center;
          gap: 4px;
          background: #f5c518;
          color: black;
          padding: 4px 10px;
          border-radius: 20px;
          font-size: 0.8em;
          box-shadow: 0 2px 6px rgba(0,0,0,0.4);
          text-decoration: none;
          font-weight: bold;
          text-shadow: none !important;
        }}
        .badge-imdb img {{
          height: 14px;
        }}
        
        #playback-button {{
          display: inline-block !important;
          vertical-align: middle;
          margin-right: 4px;
        }}
        .banner {{
          display: block;
          margin-bottom: 10px;
          max-width: 360px;
          width: auto;
          height: auto;
          object-fit: contain;
        }}
        .logo {{
          display: block;
          margin-bottom: 10px;
          max-height: 150px;
          width: auto;
          height: auto;
          object-fit: contain;
          text-align: left;
        }}
        .clearart {{
          display: block;
          margin-top: 10px;
          max-height: 80px;
        }}
        .music-info {{
          margin-bottom: 20px;
        }}
        .track-title {{
          font-size: 1.8em;
          font-weight: bold;
          margin-bottom: 5px;
          color: #4caf50;
          text-shadow: 0 2px 4px rgba(0,0,0,0.5);
          letter-spacing: 0.5px;
          display: inline;
        }}
        .track-number {{
          font-weight: bold;
          color: #4caf50;
          text-shadow: 0 2px 4px rgba(0,0,0,0.5);
          letter-spacing: 0.5px;
          margin-right: 8px;
        }}
        .music-badges {{
          display: flex;
          gap: 10px;
          margin: 10px 0;
          flex-wrap: wrap;
        }}
        .music-badge {{
          background: #4caf50;
          color: white;
          padding: 8px 15px;
          border-radius: 25px;
          font-size: 1.0em;
          font-weight: bold;
          box-shadow: 0 3px 8px rgba(0,0,0,0.4);
          text-shadow: 0 1px 3px rgba(0,0,0,0.6);
        }}
        .album-title {{
          font-size: 1.2em;
          font-weight: bold;
          margin-bottom: 10px;
          color: #ccc;
        }}
        .marquee {{
          position: fixed;
          top: 0;
          left: 0;
          width: 100%;
          height: 80px;
          background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 50%, #1a1a1a 100%);
          border: 3px solid #333;
          border-radius: 0 0 15px 15px;
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
          box-shadow: 0 4px 20px rgba(0,0,0,0.8);
          margin-bottom: 20px;
        }}
        .marquee-toggle {{
          position: absolute;
          bottom: -15px;
          left: 50%;
          transform: translateX(-50%);
          width: 50px;
          height: 15px;
          background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 50%, #1a1a1a 100%);
          border: none;
          border-radius: 0 0 25px 25px;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          transition: all 0.3s ease;
          z-index: 1001;
        }}
        .marquee-toggle::before {{
          content: "";
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: linear-gradient(45deg, #ff6b35, #f7931e, #ff6b35, #f7931e);
          border-radius: 0 0 25px 25px;
          z-index: -1;
          animation: marqueeGlow 2s ease-in-out infinite alternate;
        }}
        .marquee-toggle:hover {{
          transform: translateX(-50%) scale(1.05);
        }}
        .marquee-toggle.hidden {{
          background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 50%, #1a1a1a 100%);
        }}
        .marquee-toggle.hidden::before {{
          opacity: 0.5;
        }}
        .arrow {{
          width: 0;
          height: 0;
          border-left: 8px solid transparent;
          border-right: 8px solid transparent;
          border-bottom: 12px solid white;
          transition: transform 0.3s ease;
        }}
        .arrow.up {{
          border-bottom: none;
          border-top: 12px solid white;
        }}
        .marquee::before {{
          content: "";
          position: absolute;
          top: -8px;
          left: -8px;
          right: -8px;
          bottom: -8px;
          background: linear-gradient(45deg, #ff6b35, #f7931e, #ff6b35, #f7931e);
          border-radius: 0 0 20px 20px;
          z-index: -1;
          animation: marqueeGlow 2s ease-in-out infinite alternate;
        }}
        .marquee-text {{
          font-family: 'Arial Black', Arial, sans-serif;
          font-size: 2.2em;
          font-weight: 900;
          color: #fff;
          text-shadow: 
            0 0 10px #ff6b35,
            0 0 20px #ff6b35,
            0 0 30px #ff6b35,
            2px 2px 4px rgba(0,0,0,0.8);
          letter-spacing: 4px;
          text-transform: uppercase;
          animation: marqueePulse 1.5s ease-in-out infinite alternate;
        }}
        .marquee-text.shimmer {{
          animation: marqueePulse 1.5s ease-in-out infinite alternate;
        }}
        .marquee-text .letter {{
          margin-right: 4px;
        }}
        .marquee-text .letter:last-child {{
          margin-right: 0px;
        }}
        .marquee-text .letter:nth-child(4) {{
          margin-right: 0px;
        }}
        .marquee-text.shimmer .letter {{
          display: inline-block;
          color: #fff;
          text-shadow: 0 0 10px #ff6b35, 0 0 20px #ff6b35, 0 0 30px #ff6b35, 2px 2px 4px rgba(0,0,0,0.8);
          animation: letterDarkWave 0.2s ease-in-out forwards, letterShimmer 0.3s ease-in-out 1.0s forwards, letterFadeToWhite 0.3s ease-in-out 1.1s forwards;
          animation-fill-mode: forwards;
        }}
        .marquee-text.shimmer .letter:nth-child(1) {{ animation-delay: 0s, 1.0s, 1.1s; }}
        .marquee-text.shimmer .letter:nth-child(2) {{ animation-delay: 0.08s, 1.08s, 1.18s; }}
        .marquee-text.shimmer .letter:nth-child(3) {{ animation-delay: 0.16s, 1.16s, 1.26s; }}
        .marquee-text.shimmer .letter:nth-child(4) {{ animation-delay: 0.24s, 1.24s, 1.34s; }}
        .marquee-text.shimmer .letter:nth-child(5) {{ animation-delay: 0.32s, 1.32s, 1.42s; }}
        .marquee-text.shimmer .letter:nth-child(6) {{ animation-delay: 0.4s, 1.4s, 1.5s; }}
        .marquee-text.shimmer .letter:nth-child(7) {{ animation-delay: 0.48s, 1.48s, 1.58s; }}
        .marquee-text.shimmer .letter:nth-child(8) {{ animation-delay: 0.56s, 1.56s, 1.66s; }}
        .marquee-text.shimmer .letter:nth-child(9) {{ animation-delay: 0.64s, 1.64s, 1.74s; }}
        .marquee-text.shimmer .letter:nth-child(10) {{ animation-delay: 0.72s, 1.72s, 1.82s; }}
        .marquee-text.shimmer .letter:nth-child(11) {{ animation-delay: 0.8s, 1.8s, 1.9s; }}
        @keyframes letterDarkWave {{
          0% {{
            color: #fff;
            text-shadow: 0 0 10px #ff6b35, 0 0 20px #ff6b35, 0 0 30px #ff6b35, 2px 2px 4px rgba(0,0,0,0.8);
          }}
          100% {{
            color: #222;
            text-shadow: none;
          }}
        }}
        @keyframes letterShimmer {{
          0% {{
            color: #222;
            text-shadow: none;
          }}
          100% {{
            color: #222;
            text-shadow: none;
          }}
        }}
        @keyframes letterFadeToWhite {{
          0% {{
            color: #222;
            text-shadow: none;
          }}
          100% {{
            color: #fff;
            text-shadow: 0 0 10px #ff6b35, 0 0 20px #ff6b35, 0 0 30px #ff6b35, 2px 2px 4px rgba(0,0,0,0.8);
          }}
        }}
        @keyframes marqueeGlow {{
          0% {{ opacity: 0.7; }}
          100% {{ opacity: 1; }}
        }}
        @keyframes marqueePulse {{
          0% {{ 
            text-shadow: 
              0 0 10px #ff6b35,
              0 0 20px #ff6b35,
              0 0 30px #ff6b35,
              2px 2px 4px rgba(0,0,0,0.8);
          }}
          100% {{ 
            text-shadow: 
              0 0 15px #ff6b35,
              0 0 25px #ff6b35,
              0 0 35px #ff6b35,
              2px 2px 4px rgba(0,0,0,0.8);
          }}
        }}
        .content {{
          margin-top: 100px;
        }}
        .marquee {{
          transition: transform 0.5s ease-in-out;
        }}
        .marquee.hidden {{
          transform: translateY(-100%);
        }}
        .content.no-marquee {{
          margin-top: 20px;
        }}
        
        /* Blur Toggle Button */
        .blur-toggle {{
          position: absolute;
          top: 15px;
          right: 15px;
          width: 36px;
          height: 36px;
          border-radius: 50%;
          background: rgba(0,0,0,0.6);
          border: 1px solid rgba(255,255,255,0.2);
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.3s ease;
          box-shadow: 0 0 10px rgba(255,255,255,0.1);
          animation: subtleGlow 3s ease-in-out infinite;
          z-index: 10;
        }}
        
        .blur-toggle:hover {{
          transform: scale(1.1);
          box-shadow: 0 0 15px rgba(255,255,255,0.3);
          background: rgba(0,0,0,0.8);
        }}
        
        .blur-toggle:active {{
          transform: scale(0.95);
        }}
        
        .blur-toggle svg {{
          width: 20px;
          height: 20px;
          fill: rgba(255,255,255,0.8);
          transition: fill 0.3s ease;
        }}
        
        .blur-toggle:hover svg {{
          fill: rgba(255,255,255,1);
        }}
        
        @keyframes subtleGlow {{
          0%, 100% {{ box-shadow: 0 0 10px rgba(255,255,255,0.1); }}
          50% {{ box-shadow: 0 0 15px rgba(255,255,255,0.2); }}
        }}
        
        /* Blur state classes */
        .content.blurred {{
          backdrop-filter: blur(5px);
        }}
        
        .content.non-blurred {{
          backdrop-filter: none;
        }}

        /* Poster Zoom Overlay */
        .poster-zoom-overlay {{
          position: fixed;
          inset: 0;
          background: rgba(0,0,0,0.85);
          display: none;
          align-items: center;
          justify-content: center;
          z-index: 2000;
        }}
        .poster-zoom-overlay.visible {{
          display: flex;
        }}
        .poster-zoom-image {{
          max-width: 80vw;
          max-height: 80vh;
          border-radius: 10px;
          box-shadow: 0 20px 60px rgba(0,0,0,0.9);
          transform: scale(0.7);
          opacity: 0;
          transition: transform 0.25s ease-out, opacity 0.25s ease-out;
        }}
        .poster-zoom-overlay.visible .poster-zoom-image {{
          transform: scale(1);
          opacity: 1;
        }}
        .poster-zoom-overlay img {{
          object-fit: contain;
        }}
      </style>
      <script>
        let elapsed = {elapsed};
        let duration = {duration};
        let paused = {str(paused).lower()};
        let lastPlaybackState = null;

        function updateTime() {{
          if (!paused && elapsed < duration) {{
            elapsed++;
            let percent = Math.floor((elapsed / duration) * 100);
            document.querySelector('.bar').style.width = percent + '%';
            
            // Format time based on duration
            let elapsedTime, totalTime;
            
            if (duration < 3600) {{
              // Less than 1 hour: show mm:ss
              let elapsedMinutes = Math.floor(elapsed / 60);
              let elapsedSeconds = elapsed % 60;
              elapsedTime = elapsedMinutes.toString().padStart(2, '0') + ':' + elapsedSeconds.toString().padStart(2, '0');
              
              let totalMinutes = Math.floor(duration / 60);
              let totalSeconds = duration % 60;
              totalTime = totalMinutes.toString().padStart(2, '0') + ':' + totalSeconds.toString().padStart(2, '0');
            }} else {{
              // 1 hour or more: show hh:mm:ss
              let hours = Math.floor(elapsed / 3600);
              let minutes = Math.floor((elapsed % 3600) / 60);
              let seconds = elapsed % 60;
              elapsedTime = hours.toString().padStart(2, '0') + ':' + minutes.toString().padStart(2, '0') + ':' + seconds.toString().padStart(2, '0');
              
              let totalHours = Math.floor(duration / 3600);
              let totalMinutes = Math.floor((duration % 3600) / 60);
              let totalSeconds = duration % 60;
              totalTime = totalHours.toString().padStart(2, '0') + ':' + totalMinutes.toString().padStart(2, '0') + ':' + totalSeconds.toString().padStart(2, '0');
            }}
            
            // Update timer text, preserving the button
            const timeDisplay = document.getElementById('time-display');
            const button = timeDisplay.querySelector('#playback-button');
            const timeText = elapsedTime + ' / ' + totalTime;
            
            if (button) {{
              // If button exists, find or create a text node after the button
              let textNode = button.nextSibling;
              
              // Check if next sibling is a text node
              if (textNode && textNode.nodeType === Node.TEXT_NODE) {{
                // Update existing text node
                textNode.textContent = ' ' + timeText;
              }} else {{
                // Remove any non-text nodes after the button
                while (textNode && textNode.id !== 'playback-button') {{
                  const next = textNode.nextSibling;
                  if (textNode.nodeType !== Node.TEXT_NODE) {{
                    timeDisplay.removeChild(textNode);
                  }}
                  textNode = next;
                }}
                
                // Create and append new text node after button
                textNode = document.createTextNode(' ' + timeText);
                timeDisplay.appendChild(textNode);
              }}
            }} else {{
              // If no button, just update text
              timeDisplay.textContent = timeText;
            }}
          }}
        }}

        function resyncTime() {{
          fetch('/nowplaying?json=1')
            .then(res => res.json())
            .then(data => {{
              elapsed = data.elapsed;
              duration = data.duration;
              paused = data.paused;
            }});
        }}

        let lastItemId = null;
        let lastPausedState = null;
        let cachedButton = null;
        
        function getOrCreateButton() {{
          // Get time-display element
          const timeDisplay = document.getElementById('time-display');
          if (!timeDisplay) {{
            console.log('[ERROR] time-display element not found, cannot recreate button');
            return null;
          }}
          
          // Try to get cached button first
          if (cachedButton && document.contains(cachedButton)) {{
            return cachedButton;
          }}
          
          // Try to find existing button
          let button = document.getElementById('playback-button');
          if (button) {{
            cachedButton = button;
            return button;
          }}
          
          // Button not found, try to recreate it
          console.log('[DEBUG] Button not found, attempting to recreate...');
          if (timeDisplay) {{
            // Create new button element
            button = document.createElement('img');
            button.id = 'playback-button';
            button.src = '/play-button.png';
            button.alt = 'Play';
            button.style.cssText = 'width: 20px; height: 20px; opacity: 1; transition: opacity 0.5s ease; display: inline-block; vertical-align: middle; margin-right: 4px;';
            
            // Add error handling for failed image loads
            button.onerror = function() {{
              console.log('[DEBUG] Button image failed to load, trying to reload...');
              this.style.opacity = '0.5';
              // Retry loading the image after a short delay
              setTimeout(() => {{
                this.src = this.src + '?retry=' + Date.now();
              }}, 1000);
            }};
            
            button.onload = function() {{
              console.log('[DEBUG] Button image loaded successfully');
              this.style.opacity = '1';
            }};
            
            // Insert at the beginning of time-display
            timeDisplay.insertBefore(button, timeDisplay.firstChild);
            cachedButton = button;
            console.log('[DEBUG] Button recreated successfully');
            return button;
          }} else {{
            console.log('[ERROR] time-display element not found, cannot recreate button');
            return null;
          }}
        }}

        function updatePlaybackButton(paused) {{
          const button = getOrCreateButton();
          console.log(`[DEBUG] updatePlaybackButton called: paused=${{paused}}, button found=${{!!button}}`);
          if (button) {{
            console.log(`[DEBUG] Button current src: ${{button.src}}`);
            
            // Determine new image source
            const newSrc = paused ? '/pause-button.png' : '/play-button.png';
            const newAlt = paused ? 'Pause' : 'Play';
            
            // If the image is already correct, no need to change
            if (button.src.endsWith(newSrc.split('/').pop())) {{
              console.log('[DEBUG] Button image already correct, no change needed');
              // Still update discart animation even if button doesn't change
              updateDiscartAnimation(paused);
              return;
            }}
            
            // Fade out → change image → fade in
            button.style.opacity = '0';
            
            setTimeout(() => {{
              button.src = newSrc;
              button.alt = newAlt;
              console.log(`[DEBUG] Button new src: ${{button.src}}`);
              
              // Fade back in
              setTimeout(() => {{
                button.style.opacity = '1';
              }}, 50); // Small delay to ensure image loads
            }}, 250); // Half of transition duration for smooth effect
            
            // Ensure button is visible
            button.style.display = 'inline-block';
          }} else {{
            console.log('[ERROR] Could not get or create playback button!');
          }}
          
          // Update discart animation based on playback state
          updateDiscartAnimation(paused);
        }}
        
        function updateDiscartAnimation(paused) {{
          const discart = document.querySelector('.discart');
          if (discart) {{
            if (paused) {{
              discart.classList.add('paused');
              console.log('[DEBUG] Discart animation paused');
            }} else {{
              discart.classList.remove('paused');
              console.log('[DEBUG] Discart animation resumed');
            }}
          }}
        }}
        
        function checkPlaybackChange() {{
          fetch('/poll_playback')
            .then(res => {{
              if (!res.ok) {{
                throw new Error(`HTTP ${{res.status}}`);
              }}
              return res.json();
            }})
            .then(data => {{
              const currentState = data.playing;
              const currentItemId = data.item_id;
              const currentPaused = data.paused;
              
              // Update playback button based on pause state
              if (currentPaused !== lastPausedState) {{
                updatePlaybackButton(currentPaused);
                lastPausedState = currentPaused;
              }}
              
              // Check for playback state change (start/stop)
              if (lastPlaybackState === null) {{
                lastPlaybackState = currentState;
                lastItemId = currentItemId;
                lastPausedState = currentPaused; // Initialize lastPausedState
                updatePlaybackButton(currentPaused);
              }} else if (currentState !== lastPlaybackState) {{
                document.body.classList.add('fade-out');
                setTimeout(() => {{
                  window.location.href = '/'; // Redirect to root when playback stops
                }}, 1500);
              }}
              // Check for item change (new track/episode while playing)
              else if (currentState && currentItemId && lastItemId && currentItemId !== lastItemId) {{
                console.log(`[DEBUG] Item changed from ${{lastItemId}} to ${{currentItemId}}`);
                document.body.classList.add('fade-out');
                setTimeout(() => {{
                  location.reload(true); // Reload to show new track/episode
                }}, 800);
              }}
              
              lastPlaybackState = currentState;
              lastItemId = currentItemId;
            }})
            .catch(error => {{
              console.error('Polling error:', error);
              // Retry after shorter interval on error
              setTimeout(checkPlaybackChange, 2000);
            }});
        }}

        function toggleMarquee() {{
          const marquee = document.querySelector('.marquee');
          const toggle = document.querySelector('.marquee-toggle');
          const content = document.querySelector('.content');
          
          marquee.classList.toggle('hidden');
          toggle.classList.toggle('hidden');
          
          if (marquee.classList.contains('hidden')) {{
            content.classList.add('no-marquee');
            toggle.innerHTML = '<div class="arrow up"></div>';
            toggle.title = 'Show Marquee';
          }} else {{
            content.classList.remove('no-marquee');
            toggle.innerHTML = '<div class="arrow"></div>';
            toggle.title = 'Hide Marquee';
          }}
        }}

        // Fanart slideshow functionality - wait for DOM to be ready
        setTimeout(function() {{
          let currentFanartIndex = 0;
          const fanartSlides = document.querySelectorAll('.fanart-slide');
          const totalFanarts = fanartSlides.length;
          
          console.log(`[DEBUG] Fanart slideshow: Found ${{totalFanarts}} fanart slides`);
          
          function cycleFanarts() {{
            console.log(`[DEBUG] cycleFanarts called, totalFanarts: ${{totalFanarts}}`);
            if (totalFanarts <= 1) {{
              console.log('[DEBUG] Only 1 or no fanarts, skipping slideshow');
              return;
            }}
            
            console.log(`[DEBUG] Cycling from fanart ${{currentFanartIndex}} to next`);
            
            // Fade out current slide
            const currentSlide = fanartSlides[currentFanartIndex];
            currentSlide.classList.remove('active');
            currentSlide.classList.add('fade-out');
            
            // Move to next slide
            currentFanartIndex = (currentFanartIndex + 1) % totalFanarts;
            
            // Fade in next slide
            const nextSlide = fanartSlides[currentFanartIndex];
            nextSlide.classList.remove('fade-out');
            nextSlide.classList.add('active');
            
            console.log(`[DEBUG] Now showing fanart ${{currentFanartIndex}}`);
          }}
          
          // Start slideshow if we have multiple fanarts
          if (totalFanarts > 1) {{
            console.log('[DEBUG] Starting fanart slideshow with 20 second intervals');
            setInterval(cycleFanarts, 20000); // Change every 20 seconds
          }} else {{
            console.log('[DEBUG] Not enough fanarts for slideshow');
          }}
        }}, 100); // Wait 100ms for DOM to be ready

        // Initialize button immediately and on DOM ready
        function initializeButton() {{
          console.log('[DEBUG] Initializing playback button');
          updatePlaybackButton(false); // Initialize as playing
          
          // Ensure discart starts spinning (in case updatePlaybackButton doesn't find the discart yet)
          setTimeout(() => {{
            const discart = document.querySelector('.discart');
            if (discart && !discart.classList.contains('paused')) {{
              discart.classList.remove('paused');
              console.log('[DEBUG] Discart animation initialized as spinning');
            }}
          }}, 200);
        }}
        
        // Shimmer effect timer - trigger every 60 seconds
        function startShimmerTimer() {{
          setInterval(() => {{
            const marqueeText = document.querySelector('.marquee-text');
            if (marqueeText && !marqueeText.classList.contains('hidden')) {{
              console.log('[DEBUG] Triggering shimmer effect');
              
              // Remove any existing shimmer class first
              marqueeText.classList.remove('shimmer');
              
              // Reset all letter animations by temporarily removing and re-adding the class
              const letters = marqueeText.querySelectorAll('.letter');
              letters.forEach(letter => {{
                letter.style.animation = 'none';
              }});
              
              // Force a reflow to ensure the reset takes effect
              marqueeText.offsetHeight;
              
              // Clear the inline styles to let CSS take over
              letters.forEach(letter => {{
                letter.style.animation = '';
              }});
              
              // Add shimmer class
              marqueeText.classList.add('shimmer');
              
              // Remove shimmer class after animation completes
              setTimeout(() => {{
                marqueeText.classList.remove('shimmer');
                // Reset all letters to normal state
                letters.forEach(letter => {{
                  letter.style.animation = 'none';
                  letter.style.color = '';
                  letter.style.textShadow = '';
                }});
              }}, 6000); // Match animation duration (5s total)
            }}
          }}, 10000); // 10 seconds for testing
        }}

        function initializeAlbumFlip() {{
          const flipContainer = document.querySelector('.album-flip');
          if (!flipContainer) {{
            return;
          }}

          let flipped = false;
          let isAnimating = false;
          const container = flipContainer.closest('.poster-container');
          const indicator = container ? container.querySelector('.flip-indicator') : null;
          const discartWrapper = document.querySelector('.discart-wrapper');
          const retractDuration = 280;
          const flipDuration = 800;

          const updateIndicator = () => {{
            if (indicator) {{
              indicator.textContent = flipped ? 'Show Front' : 'Show Back';
            }}
            flipContainer.setAttribute('aria-pressed', flipped ? 'true' : 'false');
          }};

          const toggleFlip = (event) => {{
            if (isAnimating) {{
              return;
            }}
            isAnimating = true;

            if (discartWrapper) {{
              discartWrapper.classList.add('retracted');
            }}

            setTimeout(() => {{
              flipped = !flipped;
              flipContainer.classList.toggle('flipped', flipped);
              updateIndicator();
            }}, retractDuration);

            if (discartWrapper) {{
              setTimeout(() => {{
                discartWrapper.classList.remove('retracted');
              }}, retractDuration + flipDuration);
            }}

            setTimeout(() => {{
              isAnimating = false;
              if (event && event.type === 'click') {{
                flipContainer.blur();
              }}
            }}, retractDuration + flipDuration + 100);
          }};

          updateIndicator();

          // Use double-click for flip to avoid conflict with zoom (single-click)
          flipContainer.addEventListener('dblclick', (event) => {{
            event.preventDefault();
            event.stopPropagation();
            toggleFlip(event);
          }});

          flipContainer.addEventListener('keydown', (event) => {{
            if (event.key === 'Enter' || event.key === ' ' || event.key === 'Spacebar' || event.key === 'Space') {{
              event.preventDefault();
              toggleFlip(event);
            }}
          }});
        }}
        
        // Wait for DOM to be ready before initializing
        function waitForDOM() {{
          if (document.readyState === 'loading') {{
            document.addEventListener('DOMContentLoaded', initializeAll);
          }} else {{
            initializeAll();
          }}
        }}
        
        function initializeAll() {{
          // Wait a bit more for all elements to be rendered
          setTimeout(() => {{
            initializeButton();
            startShimmerTimer();
            initializeAlbumFlip();
          }}, 200);
        }}
        
        waitForDOM();
        
        setInterval(updateTime, 1000);
        setInterval(resyncTime, 5000);
        setInterval(checkPlaybackChange, 2000);
        
        // Blur Toggle Functionality
        function toggleBlur() {{
          const content = document.querySelector('.content');
          const isBlurred = content.classList.contains('blurred');
          
          if (isBlurred) {{
            content.classList.remove('blurred');
            content.classList.add('non-blurred');
            localStorage.setItem('blurPreference', 'non-blurred');
            console.log('[DEBUG] Blur disabled');
          }} else {{
            content.classList.remove('non-blurred');
            content.classList.add('blurred');
            localStorage.setItem('blurPreference', 'blurred');
            console.log('[DEBUG] Blur enabled');
          }}
        }}
        
        function initializeBlurToggle() {{
          const content = document.querySelector('.content');
          const savedPreference = localStorage.getItem('blurPreference');
          
          // For music, default to blurred (current behavior)
          if (savedPreference === 'non-blurred') {{
            content.classList.add('non-blurred');
            content.classList.remove('blurred');
          }} else {{
            content.classList.add('blurred');
            content.classList.remove('non-blurred');
          }}
          
          console.log('[DEBUG] Blur toggle initialized with preference:', savedPreference || 'blurred (default)');
        }}
        
        // Initialize blur toggle on page load
        setTimeout(initializeBlurToggle, 100);

        // Poster Zoom Logic
        (function() {{
          function setupPosterZoom() {{
            const posters = document.querySelectorAll('img.poster, img.show-poster, img.season-poster');
            if (!posters.length) return;

            let overlay = document.querySelector('.poster-zoom-overlay');
            if (!overlay) {{
              overlay = document.createElement('div');
              overlay.className = 'poster-zoom-overlay';
              overlay.innerHTML = '<img class="poster-zoom-image" src="" alt="Expanded artwork">';
              document.body.appendChild(overlay);
            }}

            const overlayImg = overlay.querySelector('.poster-zoom-image');

            function openOverlay(src, alt) {{
              if (!src) return;
              overlayImg.src = src;
              overlayImg.alt = alt || 'Expanded artwork';
              overlay.classList.add('visible');
            }}

            function closeOverlay() {{
              overlay.classList.remove('visible');
              overlayImg.src = '';
            }}

            posters.forEach(poster => {{
              // Skip non-image fallback icons if any are marked with .no-image
              if (poster.classList.contains('no-image')) return;
              
              // Track click timing to prevent zoom on double-click
              let lastClickTime = 0;
              let clickTimeout = null;
              
              poster.addEventListener('click', (e) => {{
                const currentTime = Date.now();
                const timeSinceLastClick = currentTime - lastClickTime;
                
                // If this is a double-click (within 300ms), don't zoom
                if (timeSinceLastClick < 300) {{
                  clearTimeout(clickTimeout);
                  lastClickTime = 0;
                  return;
                }}
                
                // Otherwise, wait a bit to see if a second click comes
                lastClickTime = currentTime;
                clearTimeout(clickTimeout);
                
                clickTimeout = setTimeout(() => {{
                  // Single-click confirmed - zoom
                  e.stopPropagation();
                  openOverlay(poster.src, poster.alt);
                  lastClickTime = 0;
                }}, 300);
              }});
            }});

            overlay.addEventListener('click', () => {{
              closeOverlay();
            }});

            document.addEventListener('keydown', (e) => {{
              if (e.key === 'Escape') {{
                closeOverlay();
              }}
            }});
          }}

          if (document.readyState === 'loading') {{
            document.addEventListener('DOMContentLoaded', setupPosterZoom);
          }} else {{
            setupPosterZoom();
          }}
        }})();
      </script>
    </head>
    <body>
      <!-- Fanart Slideshow Container -->
      <div class="fanart-container">
        {f'<!-- DEBUG: fanart_variants length: {len(fanart_variants)}, content: {fanart_variants} -->' if True else ''}
        {''.join([f'<div class="fanart-slide{" active" if i == 0 else ""}" style="background-image: url(\'{fanart}\')"></div>' for i, fanart in enumerate(fanart_variants)]) if fanart_variants else '<!-- No fanart variants available -->'}
      </div>
      
      <div class="marquee">
        <div class="marquee-text"><span class="letter">N</span><span class="letter">O</span><span class="letter">W</span><span class="letter">&nbsp;</span><span class="letter">P</span><span class="letter">L</span><span class="letter">A</span><span class="letter">Y</span><span class="letter">I</span><span class="letter">N</span><span class="letter">G</span></div>
        <div class="marquee-toggle" onclick="toggleMarquee()" title="Hide Marquee">
          <div style="color: white; font-size: 16px; font-weight: bold;">▲</div>
        </div>
      </div>
      <div class="content">
        <!-- Blur Toggle Button -->
        <div class="blur-toggle" onclick="toggleBlur()" title="Toggle Blur Effect">
          <svg viewBox="0 0 24 24">
            <path d="M3 8c0-1.1.9-2 2-2h14c1.1 0 2 .9 2 2v8c0 1.1-.9 2-2 2H5c-1.1 0-2-.9-2-2V8z" opacity="0.3"/>
            <path d="M4 9h16v6H4V9z" opacity="0.6"/>
            <path d="M6 11h12v2H6v-2z" opacity="0.8"/>
          </svg>
        </div>
        <div class="three-column-layout">
          <!-- Left Column: Album Cover and Discart -->
          <div class="column-left">
            <div class="poster-container{' flip-enabled' if back_cover_url else ''}">
              {"<div class='discart-wrapper'><img class='discart' src='" + discart_display_url + "' /></div>" if discart_display_url else ""}
              {(
                f"<div class='album-flip' role='button' tabindex='0' aria-pressed='false' aria-label='Flip album cover'>"
                f"<img class='poster front-face' src='{album_poster_url}' alt='Album front cover' />"
                f"<img class='poster back-face' src='{back_cover_url}' alt='Album back cover' />"
                "</div>"
                "<div class='flip-indicator'>Show Back</div>"
              ) if album_poster_url and back_cover_url else (f"<img class='poster' src='{album_poster_url}' alt='Album front cover' />" if album_poster_url else "")}
              {f"<img class='clearart' src='{clearart_url}' />" if clearart_url else ""}
            </div>
          </div>
          
          <!-- Middle Column: Clearlogo, Song Info, Rating, Badges, Progress -->
          <div class="column-middle">
            {f"<img class='logo' src='{clearlogo_url}' />" if clearlogo_url else (f"<img class='banner' src='{banner_url}' />" if banner_url else f"<h2 style='margin-bottom: 4px;'>🎵 {artist_names}</h2>")}
            
            <div class="music-info">
              <div class="music-badges">
                {f"<span class='music-badge'>{album}" + (f" ({album_year})" if album_year else "") + "</span>" if album else ""}
                {f"<span class='music-badge'>{disc_badge}</span>" if disc_badge else ""}
                {f"<span class='music-badge'>{track_badge}</span>" if track_badge else ""}
                {f"<span class='music-badge'>{title_badge}</span>" if title_badge else ""}
              </div>
              {f"<div class='album-title'>Album Rating: ⭐ {album_rating:.1f}</div>" if album_rating > 0 else ""}
            </div>
            
            <div class="badges">
              {rating_html}
              <span class="badge">{audio_codec}</span>
              {f"<span class='badge'>{container_format}</span>" if container_format and container_format != audio_codec else ""}
              {f"<span class='badge'>Discs: {total_discs}</span>" if total_discs > 0 else ""}
              {f"<span class='badge'>{song_channels}ch</span>" if song_channels > 0 else ""}
              {f"<span class='badge'>{song_bitrate} kbps</span>" if song_bitrate > 0 else ""}
              {f"<span class='badge'>{song_samplerate / 1000:.1f} kHz</span>" if song_samplerate > 0 else ""}
              {f"<span class='badge'>{audio_bits_per_sample}-bit</span>" if audio_bits_per_sample > 0 else ""}
              {f"<span class='badge'>{record_label}</span>" if record_label else ""}
              {"".join(f"<span class='badge'>{g}</span>" for g in genre_badges)}
            </div>
            <div class="progress-wrapper">
              <span class="badge" id="time-display" style="display: flex; align-items: center; gap: 8px; flex-shrink: 0;">
                <img id="playback-button" src="/play-button.png" alt="Play" style="width: 20px; height: 20px; opacity: 1; transition: opacity 0.5s ease;">
                {f"{elapsed//60:02d}:{elapsed%60:02d}" if duration < 3600 else f"{elapsed//3600:02d}:{(elapsed//60)%60:02d}:{elapsed%60:02d}"} / {f"{duration//60:02d}:{duration%60:02d}" if duration < 3600 else f"{duration//3600:02d}:{(duration//60)%60:02d}:{duration%60:02d}"}
              </span>
              <div class="progress">
                <div class="bar"></div>
              </div>
            </div>
          </div>
          
          <!-- Right Column: Artist Bio and Album Description -->
          <div class="column-right">
            {f"<div class='album-description'><div class='music-badges'><span class='music-badge'>Album Description</span></div><p>{album_details.get('description', '')}</p></div>" if isinstance(album_details, dict) and album_details.get('description') else f"<!-- No album description: album_details={album_details}, type={type(album_details)} -->"}
            {f"<div class='album-description'><div class='music-badges'><span class='music-badge'>Artist Biography</span></div>" + (f"<p><strong>Born:</strong> {artist_born}</p>" if artist_born else "") + (f"<p><strong>Genre:</strong> {', '.join(artist_genre)}</p>" if artist_genre else "") + (f"<p><strong>Style:</strong> {', '.join(artist_style)}</p>" if artist_style else "") + f"<p>{artist_details.get('description', '')}</p></div>" if isinstance(artist_details, dict) and artist_details.get('description') else f"<!-- No artist description: artist_details={artist_details}, type={type(artist_details)} -->"}
          </div>
        </div>
      </div>
    </body>
    </html>
    """
    return html
