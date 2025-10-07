# Kodi Library Information Script

A Python script that connects to a Kodi device via JSON-RPC to retrieve comprehensive library statistics. Now with Docker support and HTML output for Homarr dashboard integration!

## Features

- **Movie Statistics**: Total movies and watched count
- **TV Show Statistics**: Total shows, episodes, and watched episodes
- **Music Statistics**: Total artists, albums, and songs
- **HTML Output**: Beautiful web interface perfect for Homarr iframe integration
- **Docker Support**: Easy deployment with Docker and Docker Compose
- **Web Server**: Built-in Flask web server for real-time statistics
- **Auto-refresh**: Statistics automatically refresh every 5 minutes
- **JSON Export**: Save statistics to JSON file
- **Error Handling**: Robust connection and data handling
- **Command Line Interface**: Easy configuration via command line arguments

## Prerequisites

 **Kodi Setup**: Enable JSON-RPC in Kodi
   - Go to `System` > `Settings` > `Network` > `Services`
   - Enable `Allow control of Kodi via HTTP`
   - Set port (default: 8080)
   - Optionally set username/password for authentication


## Quick Start with Docker (Recommended)

### 1. Configure Environment
**IMPORTANT**: You must create a `.env` file with your Kodi settings (no defaults provided):

```bash
# Kodi Connection Settings (REQUIRED)
KODI_HOST=ip_address:port
KODI_USERNAME=your_kodi_http_user
KODI_PASSWORD=your_kodi_http_password

# Web Server Settings
WEB_PORT=5005

# IMPORTANT: Update KODI_HOST and USER and PASS with your actual Kodi device URL
```


### 2. Docker Commands

#### Build and Docker Run
```bash
# Build the image
docker build -t kodi-info

# Run with environment variables - replace with your Kodi device user, password, IP and port.
docker run -d \
  --name kodi-info \
  -p 5005:5005 \
  -e KODI_HOST=http://user:pass:192.168.xxx.xxx:555 \
  kodi-info
```

#### Using Docker Compose
```bash
# Make sure you have a .env file first!
cp env.example .env
# Edit .env with your settings

# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Rebuild and restart
docker-compose up -d --build
```

### 3. Access the Dashboard
Open your browser to `http://localhost:5005` or use your container host's IP. 

## Command Line Options

- `--host`: Kodi device URL (e.g., http://ip_address:port) or IP address (required)
- `--port`: Kodi HTTP port (optional, extracted from host URL if provided)
- `--username`: Kodi username (optional)
- `--password`: Kodi password (optional)
- `--web-server`: Start web server for Homarr integration
- `--web-port`: Web server port (default: 5005)
- `--save-html`: Save statistics to HTML file
- `--html-file`: HTML output filename (default: kodi_stats.html)
- `--save-json`: Save statistics to JSON file
- `--json-file`: JSON output filename (default: kodi_library_stats.json)

## Homarr Integration

### Adding to Homarr Dashboard

1. **Start the web server** (using Docker or manually):
   ```bash
   docker-compose up -d
   ```

2. **In Homarr**:
   - Go to Settings → Widgets
   - Add a new "Iframe" widget
   - Set the URL to: `http://your-server:5005`
   - Configure the widget size and position
   - Save the configuration

3. **The widget will display**:
   - Real-time Kodi library statistics
   - Beautiful responsive design
   - Auto-refreshing every 5 minutes
   - Connection status and last update time

## Output

### Web Interface
The web interface provides a beautiful, responsive dashboard showing:

- **Movies**: Total, watched, unwatched, and watch percentage
- **TV Shows**: Total shows, episodes, watched episodes, and watch percentage  
- **Music**: Total artists, albums, and songs
- **Connection Info**: Kodi host and last update time
- **Auto-refresh**: Updates every 5 minutes

### Console Output
The script also provides formatted console output:

```
🎬 KODI LIBRARY STATISTICS
============================================================

📽️  MOVIES:
   Total Movies:        1,234
   Watched Movies:      567
   Watch Percentage:    46.0%

📺  TV SHOWS:
   Total TV Shows:      89
   Total Episodes:      12,345
   Watched Episodes:    8,901
   Watch Percentage:    72.1%

🎵  MUSIC:
   Total Artists:       456
   Total Albums:        234
   Total Songs:         7,890
```

## JSON Output Format

When using `--save-json`, the output file contains:

```json
{
  "movies": {
    "total": 1234,
    "watched": 567,
    "unwatched": 667
  },
  "tv_shows": {
    "total_shows": 89,
    "total_episodes": 12345,
    "watched_episodes": 8901,
    "unwatched_episodes": 3444
  },
  "music": {
    "total_artists": 456,
    "total_albums": 234,
    "total_songs": 7890
  }
}
```

## Troubleshooting

### Connection Issues
- Verify Kodi is running and accessible on the network
- Check that JSON-RPC is enabled in Kodi settings
- Ensure firewall allows connections to the specified port
- Verify IP address and port are correct

### Authentication Issues
- Check username/password if authentication is enabled
- Ensure credentials match Kodi configuration

### Library Issues
- Make sure Kodi has scanned your media library
- Verify media sources are properly configured
- Check that library is not empty

## Dependencies

- `kodipydent`: Python client for Kodi JSON-RPC API
- `requests`: HTTP library for web requests
- `flask`: Web framework for the built-in server

## License

This script is provided as-is for educational and personal use.





