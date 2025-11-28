"""
Movie-specific HTML generation for Kodi Now Playing application.
Handles movie display with discart spinning animation and movie-specific layout.
"""

def generate_html(item, session_id, downloaded_art, progress_data, details):
    """
    Generate HTML for movie display.
    
    Args:
        item (dict): Media item from Kodi API
        session_id (str): Session ID for file naming
        downloaded_art (dict): Downloaded artwork files
        progress_data (dict): Playback progress information
        details (dict): Detailed media information
        
    Returns:
        str: HTML content for movie display
    """
    # Extract URLs for artwork
    poster_url = f"/media/{downloaded_art.get('poster')}" if downloaded_art.get("poster") else ""
    
    # Collect all fanart variants for slideshow
    fanart_variants = []
    
    # Check for all possible fanart variants in order of preference
    fanart_keys = ["fanart", "fanart1", "fanart2", "fanart3", "fanart4", "fanart5", "fanart6", "fanart7", "fanart8", "fanart9"]
    for fanart_key in fanart_keys:
        if downloaded_art.get(fanart_key):
            fanart_variants.append(f"/media/{downloaded_art.get(fanart_key)}")
    
    # Also check for extrafanart folder images (dynamic keys like extrafanart_main, extrafanart_fanart2, etc.)
    for key, value in downloaded_art.items():
        if key.startswith("extrafanart"):
            fanart_variants.append(f"/media/{value}")
    
    # Use first fanart as primary, or empty string if none
    fanart_url = fanart_variants[0] if fanart_variants else ""
    
    # Debug logging for fanart variants
    print(f"[DEBUG] Movie fanart variants found: {len(fanart_variants)}", flush=True)
    print(f"[DEBUG] Movie fanart variants: {fanart_variants}", flush=True)
    
    discart_url = f"/media/{downloaded_art.get('discart')}" if downloaded_art.get("discart") else ""
    banner_url = f"/media/{downloaded_art.get('banner')}" if downloaded_art.get("banner") else ""
    clearlogo_url = f"/media/{downloaded_art.get('clearlogo')}" if downloaded_art.get("clearlogo") else ""
    clearart_url = f"/media/{downloaded_art.get('clearart')}" if downloaded_art.get("clearart") else ""
    
    # Extract movie information
    title = item.get("title", "Untitled")
    plot = item.get("plot", item.get("description", ""))
    
    # Extract IMDb ID and construct URL - ensure details is a dict
    if not isinstance(details, dict):
        details = {}
    imdb_id = details.get("uniqueid", {}).get("imdb", "")
    imdb_url = f"https://www.imdb.com/title/{imdb_id}" if imdb_id else ""
    
    # Get rating from details or fallback
    rating = round(details.get("rating", 0.0), 1)
    rating_html = f"<strong>⭐ {rating}</strong>" if rating > 0 else ""
    
    # Initialize defaults
    director_names = "N/A"
    cast_names = "N/A"
    hdr_type = "SDR"
    audio_languages = "N/A"
    subtitle_languages = "N/A"
    
    # Extract streamdetails - ensure details is a dict
    if not isinstance(details, dict):
        details = {}
    streamdetails = details.get("streamdetails", {})
    if not isinstance(streamdetails, dict):
        streamdetails = {}
    
    # If streamdetails is empty in details, try to get it from item
    if not streamdetails and item.get("streamdetails"):
        streamdetails = item.get("streamdetails", {})
        print(f"[DEBUG] Using streamdetails from item: {streamdetails}", flush=True)
    
    video_info = streamdetails.get("video", [{}])[0] if isinstance(streamdetails.get("video"), list) and len(streamdetails.get("video", [])) > 0 else {}
    audio_info = streamdetails.get("audio", []) if isinstance(streamdetails.get("audio"), list) else []
    subtitle_info = streamdetails.get("subtitle", []) if isinstance(streamdetails.get("subtitle"), list) else []
    
    # HDR type
    hdr_type = video_info.get("hdrtype", "").upper() or "SDR"
    
    # Get enhanced video information using XBMC.GetInfoLabels for real-time data
    enhanced_video_info = {}
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
        
        print(f"[DEBUG] Attempting to get enhanced video info via XBMC.GetInfoLabels", flush=True)
        
        # Get real-time video information
        infolabels_response = kodi_rpc("XBMC.GetInfoLabels", {
            "labels": [
                "VideoPlayer.VideoAspect",
                "VideoPlayer.VideoAspectLabel", 
                "VideoPlayer.VideoCodec",
                "VideoPlayer.Container",
                "VideoPlayer.AudioCodec",
                "Player.Process(VideoHeight)",
                "Player.Process(VideoWidth)",
                "VideoPlayer.AudioLanguage",
                "VideoPlayer.SubtitlesLanguage",
                "VideoPlayer.Year"
            ]
        })
        
        print(f"[DEBUG] XBMC.GetInfoLabels response: {infolabels_response}", flush=True)
        
        if infolabels_response and infolabels_response.get("result"):
            enhanced_video_info = infolabels_response.get("result", {})
            print(f"[DEBUG] Enhanced video info extracted: {enhanced_video_info}", flush=True)
        else:
            print(f"[DEBUG] No result in XBMC.GetInfoLabels response", flush=True)
    except Exception as e:
        print(f"[DEBUG] Failed to get enhanced video info: {e}", flush=True)
        import traceback
        print(f"[DEBUG] Traceback: {traceback.format_exc()}", flush=True)
        enhanced_video_info = {}
    
    # Debug audio and subtitle info
    print(f"[DEBUG] Movie audio_info: {audio_info}", flush=True)
    print(f"[DEBUG] Movie subtitle_info: {subtitle_info}", flush=True)
    
    # Get current playing languages from InfoLabels
    audio_language_infolabel = enhanced_video_info.get("VideoPlayer.AudioLanguage", "")
    subtitle_language_infolabel = enhanced_video_info.get("VideoPlayer.SubtitlesLanguage", "")
    
    # Language code normalization mapping
    language_normalization = {
        'GER': 'DEU',  # German: ger -> deu
        'ENG': 'ENG',  # English: eng -> eng
        'FRE': 'FRA',  # French: fre -> fra
        'SPA': 'SPA',  # Spanish: spa -> spa
        'ITA': 'ITA',  # Italian: ita -> ita
        'POR': 'POR',  # Portuguese: por -> por
        'RUS': 'RUS',  # Russian: rus -> rus
        'JPN': 'JPN',  # Japanese: jpn -> jpn
        'KOR': 'KOR',  # Korean: kor -> kor
        'CHI': 'CHI',  # Chinese: chi -> chi
    }
    
    # Get all available languages from streamdetails and normalize them
    all_audio_languages = sorted(set(
        language_normalization.get(a.get("language", "")[:3].upper(), a.get("language", "")[:3].upper()) 
        for a in audio_info if a.get("language")
    ))
    all_subtitle_languages = sorted(set(
        language_normalization.get(s.get("language", "")[:3].upper(), s.get("language", "")[:3].upper()) 
        for s in subtitle_info if s.get("language")
    ))
    
    # Current playing languages (for default display) - normalize immediately
    current_audio = audio_language_infolabel[:3].upper() if audio_language_infolabel else (all_audio_languages[0] if all_audio_languages else "N/A")
    current_subtitle = subtitle_language_infolabel[:3].upper() if subtitle_language_infolabel else (all_subtitle_languages[0] if all_subtitle_languages else "N/A")
    
    # Normalize current language codes to match streamdetails format
    current_audio = language_normalization.get(current_audio, current_audio)
    current_subtitle = language_normalization.get(current_subtitle, current_subtitle)
    
    print(f"[DEBUG] Movie current audio: {current_audio}, all audio: {all_audio_languages}", flush=True)
    print(f"[DEBUG] Movie current subtitle: {current_subtitle}, all subtitle: {all_subtitle_languages}", flush=True)
    
    # Release year - try InfoLabels first, then fallback to item
    release_year = enhanced_video_info.get("VideoPlayer.Year", "")
    if not release_year:
        release_year = item.get("year", "")
    
    # Director - ensure details is a dict
    if not isinstance(details, dict):
        details = {}
    if "director" in details:
        director_list = details.get("director", [])
        if isinstance(director_list, list):
            director_names = ", ".join(director_list) or "N/A"
    
    # Studio and tagline
    studio_list = details.get("studio", [])
    if isinstance(studio_list, list) and studio_list:
        studio_names = ", ".join(studio_list)
    else:
        studio_names = ""
    
    tagline = details.get("tagline", "")
    
    # Cast - limit to top 10 actors
    cast_list = details.get("cast", [])
    if isinstance(cast_list, list) and cast_list:
        cast_names = ", ".join([c.get("name") for c in cast_list[:10] if isinstance(c, dict) and c.get("name")]) or "N/A"
    
    # Genre and formatting
    genre_list = details.get("genre", [])
    if not isinstance(genre_list, list):
        genre_list = []
    genres = [g.capitalize() for g in genre_list]
    genre_badges = genres[:3]
    
    # Format media info - use enhanced video info first, fallback to streamdetails
    resolution = ""
    height = enhanced_video_info.get("Player.Process(VideoHeight)", 0)
    width = enhanced_video_info.get("Player.Process(VideoWidth)", 0)
    
    # Convert to int if they're strings, handle comma formatting
    try:
        if height:
            height = int(str(height).replace(',', ''))
        else:
            height = 0
        if width:
            width = int(str(width).replace(',', ''))
        else:
            width = 0
    except (ValueError, TypeError):
        height = 0
        width = 0
    
    if not height:
        height = video_info.get("height", 0)
    if not width:
        width = video_info.get("width", 0)
    
    # Use width for 4K detection as it's more reliable
    if width >= 3840 or height >= 2160:
        resolution = "4K"
    elif height >= 1080:
        resolution = "1080p"
    elif height >= 720:
        resolution = "720p"
    
    # Enhanced codec information using real-time data
    video_codec = enhanced_video_info.get("VideoPlayer.VideoCodec", video_info.get("codec", "Unknown")).upper()
    audio_codec = enhanced_video_info.get("VideoPlayer.AudioCodec", audio_info[0].get("codec", "Unknown") if audio_info else "Unknown").upper()
    channels = audio_info[0].get("channels", 0) if audio_info else 0
    
    # New enhanced video information
    aspect_ratio = enhanced_video_info.get("VideoPlayer.VideoAspectLabel", "")
    # If VideoAspectLabel is empty, convert numeric aspect ratio to label
    if not aspect_ratio and enhanced_video_info.get("VideoPlayer.VideoAspect"):
        aspect_numeric = float(enhanced_video_info.get("VideoPlayer.VideoAspect", "0"))
        if aspect_numeric > 0:
            # Convert numeric aspect ratio to common labels
            if 1.77 <= aspect_numeric <= 1.78:
                aspect_ratio = "16:9"
            elif 2.35 <= aspect_numeric <= 2.40:
                aspect_ratio = "21:9"
            elif 1.33 <= aspect_numeric <= 1.37:
                aspect_ratio = "4:3"
            elif 1.85 <= aspect_numeric <= 1.90:
                aspect_ratio = "1.85:1"
            elif 2.20 <= aspect_numeric <= 2.25:
                aspect_ratio = "2.20:1"
            else:
                aspect_ratio = f"{aspect_numeric:.2f}:1"
    
    container_format = enhanced_video_info.get("VideoPlayer.Container", "").upper()
    # If container is empty, try to extract from file path
    if not container_format and item.get("file"):
        file_path = item.get("file", "")
        if file_path.lower().endswith('.mkv'):
            container_format = "MKV"
        elif file_path.lower().endswith('.mp4'):
            container_format = "MP4"
        elif file_path.lower().endswith('.avi'):
            container_format = "AVI"
        elif file_path.lower().endswith('.m4v'):
            container_format = "M4V"
        elif file_path.lower().endswith('.mov'):
            container_format = "MOV"
    
    # Playback progress
    elapsed = progress_data.get("elapsed", 0)
    duration = progress_data.get("duration", 0)
    percent = int((elapsed / duration) * 100) if duration else 0
    paused = progress_data.get("paused", False)
    
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
          transition: opacity 0.8s ease;
        }}
        
        /* Fanart Slideshow Styles */
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
        body::before {{
          content: "";
          position: absolute;
          top: 0; left: 0;
          width: 100%; height: 100%;
          background: rgba(0,0,0,0.4);
          z-index: 0;
        }}
        .content {{
          position: relative;
          z-index: 1;
          padding: 80px 40px 40px 40px;
          display: flex;
          gap: 40px;
          color: white;
          text-shadow: 0 2px 6px rgba(0,0,0,0.7), 0 0 8px rgba(0,0,0,0.5);
        }}
        .poster-container {{
          position: relative;
          overflow: visible;
          height: 420px;
          width: auto;
          margin-top: 80px;
        }}
        .poster {{
          height: 420px;
          border-radius: 8px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.6);
          position: relative;
          z-index: 2;
          cursor: zoom-in;
        }}
        .discart-wrapper {{
          position: absolute;
          top: -155px;
          left: 50%;
          transform: translateX(-50%);
          z-index: 1;
          height: 210px;
          width: 280px;
        }}
        .discart {{
          width: 280px;
          animation: spin 6s linear infinite;
          animation-play-state: running;
          opacity: 1;
          filter: drop-shadow(0 0 4px rgba(0,0,0,0.6));
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
        .progress-container {{
          flex: 1;
          min-width: 0;
          overflow: hidden;
          position: relative;
          flex-shrink: 1;
        }}
        .progress {{
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
          width: 100%;
          box-sizing: border-box;
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
          max-width: 100%;
          overflow: hidden;
          width: 100%;
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
        
        .expandable-language {{
          cursor: pointer;
          transition: all 0.3s ease;
          position: relative;
        }}
        
        .expandable-language:hover {{
          background: #444;
          transform: scale(1.05);
        }}
        
        .expandable-language.expanded {{
          background: #333;
          border: 1px solid rgba(255, 255, 255, 0.2);
        }}
        
        .current-lang {{
          font-weight: bold;
        }}
        
        .all-langs {{
          transition: opacity 0.3s ease;
        }}
        
        .active-language {{
          background: rgba(76, 175, 80, 0.6);
          color: white;
          font-weight: bold;
          padding: 2px 4px;
          border-radius: 3px;
          margin: 0 1px;
          text-shadow: 0 1px 3px rgba(0,0,0,0.6);
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
          width: 100%;
        }}
        .logo {{
          display: block;
          margin-bottom: 10px;
          max-height: 90px;
        }}
        .clearart {{
          display: block;
          margin-top: 10px;
          max-height: 80px;
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
        
        // Expandable language badges functionality
        document.addEventListener('DOMContentLoaded', function() {{
          const languageBadges = document.querySelectorAll('.expandable-language');
          
          languageBadges.forEach(badge => {{
            badge.addEventListener('click', function() {{
              const isExpanded = this.classList.contains('expanded');
              const currentLang = this.querySelector('.current-lang');
              const allLangs = this.querySelector('.all-langs');
              const currentLangText = this.dataset.current;
              const allLangsText = this.dataset.all;
              
              if (isExpanded) {{
                // Collapse: show only current language
                this.classList.remove('expanded');
                currentLang.style.display = 'inline';
                allLangs.style.display = 'none';
                // Store preference
                localStorage.setItem('language-badge-expanded-' + this.dataset.type, 'false');
              }} else {{
                // Expand: show all languages with active language highlighted
                this.classList.add('expanded');
                currentLang.style.display = 'none';
                
                // Create highlighted language list
                const languages = allLangsText.split(', ');
                const highlightedLangs = languages.map(lang => {{
                  const isActive = lang.trim() === currentLangText.trim();
                  return isActive ? `<span class="active-language">${{lang}}</span>` : lang;
                }}).join(', ');
                
                allLangs.innerHTML = highlightedLangs;
                allLangs.style.display = 'inline';
                // Store preference
                localStorage.setItem('language-badge-expanded-' + this.dataset.type, 'true');
              }}
            }});
            
            // Restore saved preference
            const savedState = localStorage.getItem('language-badge-expanded-' + badge.dataset.type);
            if (savedState === 'true') {{
              badge.classList.add('expanded');
              badge.querySelector('.current-lang').style.display = 'none';
              
              // Create highlighted language list for restored state
              const currentLangText = badge.dataset.current;
              const allLangsText = badge.dataset.all;
              const languages = allLangsText.split(', ');
              const highlightedLangs = languages.map(lang => {{
                const isActive = lang.trim() === currentLangText.trim();
                return isActive ? `<span class="active-language">${{lang}}</span>` : lang;
              }}).join(', ');
              
              badge.querySelector('.all-langs').innerHTML = highlightedLangs;
              badge.querySelector('.all-langs').style.display = 'inline';
            }}
          }});
        }});

        function updateTime() {{
          console.log(`[DEBUG] updateTime called: paused=${{paused}}, elapsed=${{elapsed}}, duration=${{duration}}`);
          if (!paused && elapsed < duration) {{
            elapsed++;
            let percent = Math.floor((elapsed / duration) * 100);
            document.querySelector('.bar').style.width = percent + '%';
            console.log(`[DEBUG] Timer updated: elapsed=${{elapsed}}, percent=${{percent}}%`);
            
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
        let lastAudioLang = null;
        let lastSubtitleLang = null;
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
              console.log('[DEBUG] Movie discart animation paused');
            }} else {{
              discart.classList.remove('paused');
              console.log('[DEBUG] Movie discart animation resumed');
            }}
          }}
        }}
        
        function updateLanguageBadge(type, newLanguage) {{
          const badge = document.querySelector(`.badge[data-type="${{type}}"]`);
          if (badge) {{
            const currentLangSpan = badge.querySelector('.current-lang');
            if (currentLangSpan) {{
              currentLangSpan.textContent = newLanguage;
              console.log(`[DEBUG] Updated ${{type}} badge to ${{newLanguage}}`);
            }}
            
            // Update the data-current attribute
            badge.dataset.current = newLanguage;
            
            // If the badge is expanded, update the highlighted language
            if (badge.classList.contains('expanded')) {{
              const allLangsSpan = badge.querySelector('.all-langs');
              if (allLangsSpan) {{
                const allLangsText = badge.dataset.all;
                const languages = allLangsText.split(', ');
                const highlightedLangs = languages.map(lang => {{
                  const isActive = lang.trim() === newLanguage.trim();
                  return isActive ? `<span class="active-language">${{lang}}</span>` : lang;
                }}).join(', ');
                
                allLangsSpan.innerHTML = highlightedLangs;
                console.log(`[DEBUG] Updated expanded ${{type}} badge highlighting`);
              }}
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
              const currentAudioLang = data.current_audio_lang || '';
              const currentSubtitleLang = data.current_subtitle_lang || '';
              
              console.log(`[DEBUG] Poll result: playing=${{currentState}}, item_id=${{currentItemId}}, lastItemId=${{lastItemId}}, paused=${{currentPaused}}, audio=${{currentAudioLang}}, subtitle=${{currentSubtitleLang}}`);
              
              // Update playback button based on pause state
              if (currentPaused !== lastPausedState) {{
                updatePlaybackButton(currentPaused);
                lastPausedState = currentPaused;
              }}
              
              // Check for language changes and update badges
              if (currentAudioLang && currentAudioLang !== lastAudioLang) {{
                console.log(`[DEBUG] Audio language changed from ${{lastAudioLang}} to ${{currentAudioLang}}`);
                updateLanguageBadge('audio', currentAudioLang);
                lastAudioLang = currentAudioLang;
              }}
              
              if (currentSubtitleLang && currentSubtitleLang !== lastSubtitleLang) {{
                console.log(`[DEBUG] Subtitle language changed from ${{lastSubtitleLang}} to ${{currentSubtitleLang}}`);
                updateLanguageBadge('subtitle', currentSubtitleLang);
                lastSubtitleLang = currentSubtitleLang;
              }}
              
              // Check for playback state change (start/stop)
              if (lastPlaybackState === null) {{
                lastPlaybackState = currentState;
                lastItemId = currentItemId;
                lastPausedState = currentPaused;
                lastAudioLang = currentAudioLang;
                lastSubtitleLang = currentSubtitleLang;
                updatePlaybackButton(currentPaused);
                console.log(`[DEBUG] Initial state set: lastPlaybackState=${{lastPlaybackState}}, lastItemId=${{lastItemId}}, lastPausedState=${{lastPausedState}}, audio=${{lastAudioLang}}, subtitle=${{lastSubtitleLang}}`);
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

        // Initialize button immediately and on DOM ready
        function initializeButton() {{
          console.log('[DEBUG] Initializing playback button');
          updatePlaybackButton(false); // Initialize as playing
          
          // Ensure discart starts spinning (in case updatePlaybackButton doesn't find the discart yet)
          setTimeout(() => {{
            const discart = document.querySelector('.discart');
            if (discart && !discart.classList.contains('paused')) {{
              discart.classList.remove('paused');
              console.log('[DEBUG] Movie discart animation initialized as spinning');
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
          }}, 200);
        }}
        
        waitForDOM();
        
        setInterval(updateTime, 1000);
        setInterval(resyncTime, 5000);
        setInterval(checkPlaybackChange, 2000);
        
        // Fanart slideshow functionality
        setTimeout(function() {{
          let currentFanartIndex = 0;
          const fanartSlides = document.querySelectorAll('.fanart-slide');
          const totalFanarts = fanartSlides.length;
          
          console.log(`[DEBUG] Found ${{totalFanarts}} fanart slides`);
          
          function cycleFanarts() {{
            if (totalFanarts <= 1) return;
            
            console.log(`[DEBUG] Cycling fanarts - current: ${{currentFanartIndex}}, next: ${{(currentFanartIndex + 1) % totalFanarts}}`);
            
            const currentSlide = fanartSlides[currentFanartIndex];
            currentSlide.classList.remove('active');
            currentSlide.classList.add('fade-out');
            
            currentFanartIndex = (currentFanartIndex + 1) % totalFanarts;
            
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
          
          // For movies, default to non-blurred (current behavior)
          if (savedPreference === 'blurred') {{
            content.classList.add('blurred');
            content.classList.remove('non-blurred');
          }} else {{
            content.classList.add('non-blurred');
            content.classList.remove('blurred');
          }}
          
          console.log('[DEBUG] Blur toggle initialized with preference:', savedPreference || 'non-blurred (default)');
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
              poster.style.cursor = 'zoom-in';
              poster.addEventListener('click', (e) => {{
                // Skip non-image fallback icons if any are marked with .no-image
                if (poster.classList.contains('no-image')) return;
                e.stopPropagation();
                openOverlay(poster.src, poster.alt);
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
        {''.join([f'<div class="fanart-slide{" active" if i == 0 else ""}" style="background-image: url(\'{fanart}\')"></div>' for i, fanart in enumerate(fanart_variants)]) if fanart_variants else ''}
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
        <div class="poster-container">
          {"<div class='discart-wrapper'><img class='discart' src='" + discart_url + "' /></div>" if discart_url else ""}
          {f"<img class='poster' src='{poster_url}' />" if poster_url else ""}
          <!-- Clearart removed as requested -->
        </div>
        <div>
          {f"<img class='logo' src='{clearlogo_url}' />" if clearlogo_url else (f"<img class='banner' src='{banner_url}' />" if banner_url else f"<h2 style='margin-bottom: 4px;'>🎬 {title}</h2>")}
          {f"<p style='font-style: italic; color: #ccc; margin-top: 8px;'>{tagline}</p>" if tagline else ""}
          {f"<p><strong>Release year:</strong> {release_year}</p>" if release_year else ""}
          {f"<p><strong>Director:</strong> {director_names}</p>" if director_names and director_names != "N/A" else ""}
          {f"<p><strong>Cast:</strong> {cast_names}</p>" if cast_names and cast_names != "N/A" else ""}
          {f"<h3 style='margin-top:20px;'>Plot</h3><p style='max-width:600px;'>{plot}</p>" if plot and plot.strip() else ""}
          <div class="badges">
            {rating_html}
            {f'<a href="{imdb_url}" target="_blank" class="badge-imdb"><span>IMDb</span></a>' if imdb_url else ''}
            {f"<span class='badge'>{resolution}</span>" if resolution else ""}
            {f"<span class='badge'>{aspect_ratio}</span>" if aspect_ratio else ""}
            <span class="badge">{video_codec}</span>
            {f"<span class='badge'>{container_format}</span>" if container_format else ""}
            <span class="badge">{audio_codec} {channels}ch</span>
            <span class="badge">{hdr_type}</span>
            {f"<span class='badge'>{studio_names}</span>" if studio_names else ""}
            <span class="badge {'expandable-language' if len(all_audio_languages) > 1 else ''}" data-current="{current_audio}" data-all="{', '.join(all_audio_languages)}" data-type="audio">
              Audio: <span class="current-lang">{current_audio}</span>
              <span class="all-langs" style="display: none;">{', '.join(all_audio_languages)}</span>
            </span>
            <span class="badge {'expandable-language' if len(all_subtitle_languages) > 1 else ''}" data-current="{current_subtitle}" data-all="{', '.join(all_subtitle_languages)}" data-type="subtitle">
              Subs: <span class="current-lang">{current_subtitle}</span>
              <span class="all-langs" style="display: none;">{', '.join(all_subtitle_languages)}</span>
            </span>
            {"".join(f"<span class='badge'>{g}</span>" for g in genre_badges)}
          </div>
          <div class="progress-wrapper">
            <span class="badge" id="time-display" style="display: flex; align-items: center; gap: 8px; flex-shrink: 0;">
              <img id="playback-button" src="/play-button.png" alt="Play" style="width: 20px; height: 20px; opacity: 1; transition: opacity 0.5s ease;">
              {f"{elapsed//60:02d}:{elapsed%60:02d}" if duration < 3600 else f"{elapsed//3600:02d}:{(elapsed//60)%60:02d}:{elapsed%60:02d}"} / {f"{duration//60:02d}:{duration%60:02d}" if duration < 3600 else f"{duration//3600:02d}:{(duration//60)%60:02d}:{duration%60:02d}"}
            </span>
            <div class="progress-container">
              <div class="progress">
                <div class="bar"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </body>
    </html>
    """
    return html
