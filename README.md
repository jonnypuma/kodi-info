# Kodi Library Information Script

A Python script that connects to a Kodi device via JSON-RPC to retrieve comprehensive library statistics. Docker-based with HTML output for web browser display or Homarr dashboard integration!

## Features

- **Movie Statistics**: Total movies and watched count
- **TV Show Statistics**: Total shows, episodes, and watched episodes
- **Music Statistics**: Total artists, albums, and songs
- **HTML Output**: Beautiful web interface perfect for Homarr iframe integration
- **Docker Support**: Easy deployment with Docker and Docker Compose
- **Web Server**: Built-in Flask web server for real-time statistics
- **Auto-refresh**: Statistics automatically refresh every 5 minutes
- **Manual Refresh**: Click the refresh button to instantly reload statistics
- **Library Update Buttons**: Update video and audio libraries directly from the web interface
- **Library Clean Buttons**: Clean video and music libraries directly from the web interface
- **JSON Export**: Save statistics to JSON file
- **Error Handling**: Robust connection and data handling
- **Command Line Interface**: Easy configuration via command line arguments
- **Artwork Zoom**: Click any movie cover, episode thumbnail, or album cover to open a large animated preview; click anywhere or press Escape to close

## Prerequisites

 **Kodi Setup**: Enable JSON-RPC in Kodi
   - Go to `System` > `Settings` > `Network` > `Services`
   - Enable `Allow control of Kodi via HTTP`
   - Set port (default: 8080)
   - Optionally set username/password for authentication


## Quick Start with Docker (Recommended)

### 1. Configure Environment
**IMPORTANT**: You must edit the supplied .env file or create a new `.env` file with your Kodi settings (no defaults provided):

```bash
# Kodi Connection Settings (REQUIRED)
KODI_HOST=http://ip_address:port
KODI_USERNAME=your_kodi_http_user
KODI_PASSWORD=your_kodi_http_password

# Web Server Settings
WEB_PORT=5005

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
# Edit .env with your settings

# Start services
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down

# Rebuild and restart
docker compose up -d --build
```

### 3. Access the Dashboard
Open your browser to `http://localhost:5005` or use your container host's IP:5005. 


## Homarr Integration

### Adding to Homarr Dashboard

   - Go to Settings → Widgets
   - Add a new "Iframe" widget
   - Set the URL to: `http://your-server:5005`
   - Configure the widget size and position
   - Save the configuration

## Output

### Web Interface
The web interface provides a beautiful, responsive dashboard showing:

- **Movies**: Total, watched, unwatched, and watch percentage
- **TV Shows**: Total shows, episodes, watched episodes, and watch percentage  
- **Music**: Total artists, albums, and songs
- **Connection Info**: Kodi host and last update time
- **Auto-refresh**: Updates every 5 minutes
- **Manual Refresh Button**: Click the refresh icon next to the buttons to instantly reload the page and fetch fresh statistics
- **Library Update Buttons**: Update Video Library and Update Audio Library buttons to trigger Kodi library scans
- **Library Clean Buttons**: Clean Video Library and Clean Music Library buttons to remove missing items from Kodi libraries

### Console Output
The script can output statistics directly to the console. Run the script without the `--web-server` flag:

**Basic command:**
```bash
python kodi_info.py --host http://192.168.1.10:555
```

**With IP and port separately:**
```bash
python kodi_info.py --host 192.168.1.100 --port 8080
```

**With authentication:**
```bash
python kodi_info.py --host 192.168.1.100 --port 8080 --username kodi --password mypass
```

**Save to HTML file (still prints to console):**
```bash
python kodi_info.py --host http://192.168.1.10:555 --save-html
```

**Save to JSON file (still prints to console):**
```bash
python kodi_info.py --host http://192.168.1.10:555 --save-json
```

**Save to both HTML and JSON:**
```bash
python kodi_info.py --host http://192.168.1.10:555 --save-html --save-json
```

**Example console output:**
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





