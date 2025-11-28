"""
Media type parser for Kodi Now Playing application.
Determines whether the current media is a movie or TV episode and routes to appropriate handler.
"""

def infer_playback_type(item):
    """
    Determine the type of media being played.
    
    Args:
        item (dict): Media item from Kodi API
        
    Returns:
        str: 'movie', 'episode', 'song', or 'unknown'
    """
    if item.get("type") in ["movie", "episode", "song"]:
        return item["type"]
    if item.get("showtitle") and item.get("episode") is not None:
        return "episode"
    if item.get("album") and item.get("artist"):
        return "song"
    if item.get("title") and not item.get("showtitle") and item.get("type") != "unknown":
        return "movie"
    return "unknown"

def get_media_handler(playback_type):
    """
    Get the appropriate handler module for the media type.
    
    Args:
        playback_type (str): Type of media ('movie', 'episode', or 'song')
        
    Returns:
        module: The appropriate handler module
    """
    if playback_type == "movie":
        import movie_nowplaying
        return movie_nowplaying
    elif playback_type == "episode":
        import episode_nowplaying
        return episode_nowplaying
    elif playback_type == "song":
        import music_nowplaying
        return music_nowplaying
    else:
        raise ValueError(f"Unknown playback type: {playback_type}")

def route_media_display(item, session_id, downloaded_art, progress_data, details):
    """
    Route media display to the appropriate handler based on media type.
    
    Args:
        item (dict): Media item from Kodi API
        session_id (str): Session ID for file naming
        downloaded_art (dict): Downloaded artwork files
        progress_data (dict): Playback progress information
        details (dict): Detailed media information
        
    Returns:
        str: HTML content for the media display
    """
    playback_type = infer_playback_type(item)
    print(f"[DEBUG] Parser - Playback type: {playback_type}", flush=True)
    handler = get_media_handler(playback_type)
    print(f"[DEBUG] Parser - Handler: {handler}", flush=True)
    
    return handler.generate_html(item, session_id, downloaded_art, progress_data, details)
