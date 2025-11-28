This is a script to be run as a Docker container.

It provides a html page showing what a Kodi device is playing and displays artwork, progress bar, media information, plot etc with background slideshow if more than one fanart is found. 

## Features

- **Real-time Playback Detection**: Automatically detects when Kodi starts/stops playing media
- **Playback State Monitoring**: Shows current play/pause state with visual indicators
- **Interactive Playback Controls**: Play/pause icons with smooth fade transitions
- **Smart Timer Management**: Timer stops when paused and resyncs on resume
- **Comprehensive Media Support**: Episodes, movies, and music with appropriate artwork
- **Background Slideshow**: Multiple fanart images for enhanced visual experience
- **Responsive Design**: Clean, modern interface that works on various screen sizes
- **Blur Toggle Control**: Discreet button to switch between blurred and non-blurred overlay modes
- **Cross-Browser Scrollbar Styling**: Custom scrollbars with green hover effects
- **Smart Episode Title Detection**: Automatically hides generic episode titles to prevent duplication
- **Enhanced HDR Badge Display**: Clean HDR type indicators (SDR, HDR, HDR10, HDR10+, HLG, Dolby Vision)
- **Enhanced Video/Audio Information**: Real-time aspect ratio, container format, and accurate codec detection
- **Studio/Tagline Display**: Production studio badges and movie/episode taglines
- **Music Sample Rate/Record Label**: Enhanced audio information with kHz formatting and record label display
- **Album Back Cover Flip**: Smooth front/back cover toggle for music albums
- **Expandable Language Badges**: Interactive audio/subtitle language display with smart highlighting

## Playback Indicators

The HTML webpage includes:
- **Play/Pause Icon**: Visual indicator that changes based on playback state in real-time
- **Smooth Transitions**: 500ms fade in/out effects when switching between play/pause states
- **Timer Integration**: Icon positioned to the left of the playback timer
- **Interactive Discart Animation**: Discart (CD/DVD/Bluray artwork) spins during playback and pauses when media is paused

## Theater-Style Marquee Banner

The interface features a hideable marquee banner that displays the current media title in a theater sign style:
- **Auto-hide Toggle**: Click the half-circle arrow tab to hide/show the marquee banner
- **Dynamic Color Shifting**: Smooth color transitions that cycle through different hues
- **Smooth Animations**: Fade in/out effects when toggling visibility
- **Responsive Design**: Banner adapts to different screen sizes
- **Clean Integration**: Seamlessly integrated with the overall design

### Text Shimmer Effect

The marquee banner includes an elegant text shimmer effect that adds visual interest:
- **Automatic Triggering**: Effect runs every 10 seconds when media is playing
- **Letter-by-Letter Animation**: Each letter of "NOW PLAYING" animates individually
- **Two-Stage Effect**: 
  1. **Dark Wave**: Letters fade to dark gray in sequence (80ms stagger between letters)
  2. **Shimmer Wave**: Bright orange glow sweeps across, leading the white fade
- **Perfect Timing**: Shimmer arrives first, then letters fade back to white with proper delay
- **Consistent Spacing**: Letter spacing remains identical whether effect is active or not
- **Smooth Transitions**: All animations use CSS transitions for fluid motion
- **Non-Intrusive**: Effect is subtle enough to not distract from content viewing

## Blur Toggle Control
A sleek, discreet toggle button that allows you to switch between blurred and non-blurred overlay modes:
- **Top-Right Placement**: Small circular button positioned in the top-right corner of the content overlay
- **Custom SVG Icon**: Inline SVG icon representing the blur effect with layered rectangles
- **Smooth Animations**: Subtle pulsing glow animation and hover effects
- **Persistent Preferences**: Your blur preference is saved in localStorage and restored across sessions
- **Smart Defaults**: 
  - Movies: Default to non-blurred (shows more fanart detail)
  - Episodes & Music: Default to blurred (better text readability)
- **Instant Toggle**: Pure CSS/JavaScript implementation with no page reload required

## Enhanced Scrollbar Styling
Custom scrollbars during music playback for artist and album info sections with improved visual design and cross-browser support:
- **WebKit Browsers** (Chrome, Safari, Edge, Brave): Full custom styling with sleek appearance
- **Firefox**: Thin scrollbars with color changes on hover
- **Green Hover Effect**: Scrollbars turn the same green color used throughout the UI when hovered
- **Smooth Transitions**: CSS transitions for polished interactions
- **Consistent Design**: Maintains sleek appearance across all browsers

## Smart Episode Title Detection
Intelligent detection of generic episode titles to prevent visual duplication:
- **Pattern Recognition**: Automatically detects titles like "Episode 6", "Episode #6", "episode 6"
- **Case Insensitive**: Works with any capitalization
- **Flexible Matching**: Handles variations with spaces, hash symbols, and extra whitespace
- **Real Title Preservation**: Keeps meaningful episode titles like "The Pilot" or "Winter is Coming"
- **Clean Display**: Eliminates duplicate badges when episode title matches episode number

## HDR Badge Display
HDR type indicators for better clarity:
- **Clean Format**: Shows just the HDR type (SDR, HDR, HDR10, HDR10+, HLG, Dolby Vision)
- **Automatic Detection**: Uses Kodi's stream information to determine the correct HDR type
- **Consistent Styling**: Matches the design of other media information badges

## Enhanced Video/Audio Information
Real-time media format detection with comprehensive badge system:
- **Aspect Ratio Detection**: Real-time aspect ratio from Kodi's video player (16:9, 21:9, etc.)
- **Container Format**: Video/audio container detection (MKV, MP4, AVI, FLAC, MP3, etc.)
- **Accurate Codec Detection**: Enhanced video/audio codec information from active playback
- **Smart Fallbacks**: Filename extension fallback when API data is unavailable
- **Numeric Conversion**: Automatic conversion of aspect ratios (1.78 → 16:9, 2.35 → 21:9)
- **Duplicate Prevention**: Container format only shows when different from codec

## Studio/Tagline Display
Enhanced movie and episode information:
- **Studio Badges**: Production studio information displayed as badges
- **Tagline Display**: Movie/episode taglines shown in italic text under clearlogo
- **API Integration**: Uses Kodi's VideoLibrary API with proper field requests
- **Conditional Display**: Only shows when information is available
- **Clean Formatting**: Studio names joined with commas, taglines without prefixes

## Music Sample Rate/Record Label
Enhanced audio information with improved formatting:
- **Sample Rate Display**: Clean kHz formatting (44.1 kHz, 48.0 kHz, 22.5 kHz)
- **Record Label Badges**: Album record label information from Kodi's database
- **Precision Formatting**: Proper decimal handling for common sample rates
- **Clean Badge Design**: Removed unnecessary prefixes for streamlined display
- **Smart Extraction**: Properly extracts from album details API response

## Album Back Cover Flip
Interactive album artwork that reveals additional details when back cover art is available:
- **Back Cover Detection**: Automatically loads back cover assets supplied by Kodi (e.g., `back`, `backcover`, `rear`)
- **3D Flip Animation**: Smooth 180° horizontal flip between front and back covers
- **Double-Click Trigger**: Toggle between front and back covers by double-clicking the album artwork
- **Keyboard Accessible**: Toggle with Enter or Space when focused; focus outlines help when navigating via keyboard
- **Contextual Indicator**: Subtle overlay text updates to show whether the front or back cover is currently displayed
- **Zoom Compatibility**: Single-click zooms the cover; double-click flips between front/back without triggering zoom

## Poster/Cover Zoom Functionality
Interactive zoom feature for all media artwork that provides a detailed view:
- **Universal Support**: Works with movie posters, TV show posters, TV season posters, and album covers
- **Single-Click Zoom**: Click any poster or cover to view it in a larger, centered overlay
- **Smooth Animation**: Elegant scale-up animation with fade effects when opening/closing
- **Responsive Sizing**: Zoomed images scale up to ~4× original size (up to 80% of viewport) depending on screen size
- **Visual Feedback**: Magnifying glass cursor (zoom-in) appears when hovering over clickable artwork
- **Easy Dismissal**: Click anywhere on the dark overlay or press Escape to close the zoom view
- **Album Cover Integration**: Single-click zooms album covers; double-click flips between front/back (when back cover available)
- **Non-Image Exclusion**: Fallback icons (`.no-image`) are excluded from zoom functionality

## Expandable Language Badges
Interactive audio and subtitle language display with intelligent highlighting and real-time updates:
- **Smart Clickability**: Only clickable when multiple languages are available
- **Default View**: Shows currently playing language (e.g., "Audio: ENG")
- **Expanded View**: Reveals all available languages with active language highlighted
- **Visual Highlighting**: Green highlight box around the currently playing language
- **Real-Time Updates**: Language badges automatically update when you switch audio/subtitle tracks in Kodi
- **No Page Reload**: Seamless updates without refreshing the page
- **Persistent Preferences**: Remembers your expansion preferences across sessions
- **Smooth Animations**: Hover effects and transition animations
- **Clean Readability**: Dark badge background with white text for optimal contrast
- **Dual Source Detection**: Uses both InfoLabels (current) and streamdetails (all available)
- **Smart Fallbacks**: Graceful handling when language data is incomplete
- **Language Normalization**: Consistent language codes across different data sources

## Media Type Display Features

The application provides specialized displays and artwork for different media types, each optimized for the unique characteristics of TV shows, movies, and music:

### TV Shows
**Artwork Display:**
- **Show Poster**: Main TV show poster displayed prominently
- **Season Artwork**: Season-specific poster when available (shows season number and artwork)
- **ClearArt**: High-quality transparent show artwork (preferred for overlay)
- **Banner**: Wide banner artwork for show identification
- **Fanart Slideshow**: Multiple background images including show fanart and extrafanart

**Information Displayed:**
- Show title and episode title
- Season and episode numbers
- Episode plot/synopsis
- Show genre and rating
- Cast information (when available)
- Video quality (resolution, codec, HDR type, aspect ratio, container format)
- Audio information (channels, codec, container format)
- Interactive language badges (audio/subtitle with expandable view)
- Studio information and tagline
- Release year and director information
- Playback progress and time remaining

### Movies
**Artwork Display:**
- **Movie Poster**: Primary movie poster with cinematic styling
- **Discart**: Spinning disc/DVD/Blu-ray artwork that rotates during playback
- **ClearArt**: Transparent movie artwork for clean overlay
- **Banner**: Movie banner artwork for identification
- **Fanart Slideshow**: Cinematic background images from movie fanart and extrafanart

**Information Displayed:**
- Movie title and year
- Director and cast information
- Genre and rating
- Plot summary
- Video quality (resolution, codec, HDR type, aspect ratio, container format)
- Audio information (channels, codec, container format)
- Interactive language badges (audio/subtitle with expandable view)
- Studio information and tagline
- Release year and director information
- Playback progress and total runtime

### Music
**Artwork Display:**
- **Album Artwork**: Album cover displayed prominently (thumbnail or poster)
- **Artist ClearArt**: High-quality transparent artist artwork
- **Artist Banner**: Wide banner artwork for artist identification
- **Fanart Slideshow**: Artist fanart and concert/live performance images

**Information Displayed:**
- Artist name and song title
- Album name and release year
- Genre and music quality information
- Audio codec and container format
- Sample rate (kHz) and bitrate information
- Record label and channel information
- Artist biography (when available from metadata)
- Album information and track details
- Playback progress and song duration

### Artwork Fallback System
Each media type follows a sophisticated fallback hierarchy to ensure optimal visual presentation:

**TV Shows:**
1. **ClearArt** → **Banner** → **Text Fallback**
2. **Season Poster** (when available) → **Show Poster** → **Default**
3. **Fanart Collection**: Main fanart + extrafanart folder images

**Movies:**
1. **ClearArt** → **Banner** → **Text Fallback**  
2. **Discart** (spinning disc artwork) for visual appeal
3. **Fanart Collection**: Movie fanart + extrafanart folder images

**Music:**
1. **ClearArt** → **Banner** → **Text Fallback**
2. **Album Artwork** (thumbnail/poster) as primary display
3. **Fanart Collection**: Artist fanart + concert/performance images

### Artwork Sources
- **Kodi's Artwork Database**: Primary source for all artwork types
- **Local Media Folders**: Scans movie/TV/music directories for additional artwork
- **Extrafanart Folders**: Automatically discovers fanart in `extrafanart/` subdirectories
- **Automatic Detection**: Script automatically detects available artwork types
- **Seamless Fallbacks**: Transitions between artwork types are smooth and automatic
- **Quality Priority**: Always displays the highest quality artwork available
- **Responsive Scaling**: All artwork types scale appropriately for different screen sizes

### Background Slideshow
When multiple fanart images are available:
- **Automatic Rotation**: Cycles through all available fanart images
- **20-Second Intervals**: Each image displays for 20 seconds
- **Smooth Transitions**: Fade effects between background changes
- **Dynamic Detection**: Automatically detects and uses all available fanart images
- **Extrafanart Support**: Scans `extrafanart/` subdirectories to find additional background images
- **Comprehensive Collection**: Includes fanart from both main directory and extrafanart folders for maximum variety

## Setup

Make sure Kodi has web control enabled

Unzip script.kodi-nowplaying.zip 

Edit the .env file and input the ip to your Kodi device, HTTP port and user/pass.

_________________________
OPTIONAL: Create fallback and edit the kodi-nowplaying.py file and enter Kodi IP and user/pass there:
# Kodi connection details
```
KODI_HOST = os.getenv("KODI_HOST", "http://insert_ip:insert_port")

KODI_USER = os.getenv("KODI_USER", "insert_user")

KODI_PASS = os.getenv("KODI_PASS", "insert_pass")
```
_________________________

Build and start container:
```docker compose build --no-cache kodi-nowplaying```
```docker compose up -d kodi-nowplaying```

Start playing media on your Kodi device

Test locally by visiting http://localhost:5001/nowplaying <- or replace localhost with the IP of the container host

Mount it as a custom Homarr iframe tile pointing to http://localhost:5001/nowplaying <- or replace localhost with the IP of the container host


