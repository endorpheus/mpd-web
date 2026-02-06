# mpd-web

(mpd-spiffy)<br>
version: 1.0
<p>
System status: $   {\color{#238636} ONLINE}   $ <br>
   A spiffy cyberpunk-style web interface for controlling Music Player Daemon (MPD).
</p>


## Features

### Playback Control
- Play, pause, stop, next, previous
- Volume control with slider
- Progress bar with elapsed/total time
- Playback modes: Random, Repeat, Single, Consume

### Queue Management
- View current playlist with full track names (word-wrap)
- Drag-and-drop reordering
- Remove individual tracks
- Clear or shuffle entire queue
- Click to play any track
- Duplicate detection

### Library Browser
- Browse by Artist → Album → Track
- "All Files" view for untagged music
- Search across artist, title, album
- Update DB button to rescan music directory

### Album Art & Artist Images
- Displays embedded album art (FLAC, MP3, M4A)
- Falls back to online sources (Deezer, TheAudioDB)
- Image cycling every 15 seconds
- Smart caching per artist+album
- Filename-based search for untagged files
- Image blacklisting (persists across restarts)
- Pauses cycling when playback is stopped

### Particle Nebula Animation
- Procedural animation when no artwork is available
- 60 glowing particles with drift and pulse effects
- Connection lines between nearby particles

### Lyrics
- Reads embedded lyrics from file tags
- Falls back to lrclib.net and lyrics.ovh
- Modal popup display

## Requirements

- Python 3.6+
- MPD running and configured
- `mpc` command-line client
- `mutagen` Python package

## Installation

```bash
git clone https://github.com/endorpheus/mpd-web.git
cd mpd-web
pip install mutagen
python server.py
```

Open http://localhost:8080 in your browser.

## Configuration

### Music Directory
Auto-detects from `~/Music` or `/var/lib/mpd/music`. To customize:
```python
MUSIC_DIR = Path('/your/music/path')
```

### Port
Default is 8080. Change `PORT` in `server.py`.

### Security
Binds to localhost only by default.

## API Endpoints

### MPD Commands
```
/?cmd=<command>&args=<arg>&format=<format>
```

Allowed: `status`, `current`, `play`, `pause`, `stop`, `next`, `prev`, `toggle`, `volume`, `repeat`, `random`, `single`, `consume`, `playlist`, `add`, `del`, `clear`, `shuffle`, `move`, `search`, `find`, `findadd`, `searchadd`, `listall`, `albumart`, `readpicture`, `update`, `stats`

### Custom Endpoints

- `/?cmd=lyrics&args=<file>&args=<artist>&args=<title>` - Fetch lyrics
- `/?cmd=artistart&args=<artist>&args=<album>` - Fetch artwork (cycles through cached images)
- `/?cmd=blacklistimg&args=<cache_key>` - Blacklist current image
- `/?cmd=list&args=<type>&args=<filter>` - List library items

## File Structure

```
mpd-web/
├── server.py              # Python HTTP server
├── mpd-spiffy.html        # Web interface
├── image_blacklist.json   # Blacklisted image URLs (auto-created)
└── README.md
```

## Troubleshooting

**Port in use**: `pkill -f "python.*server.py"` then restart

**No music in library**: Click "Update DB" or run `mpc update`

**Images not loading**: Check network access to Deezer/TheAudioDB

**All images blacklisted**: Delete `image_blacklist.json` and restart

**Images not cycling**: Ensure playback is active (pauses when stopped)

## Author

mpd-web<br>
Ryon Shane Hall<br>
Updated: 202602042035

## Thanks

This app is just a *spiffy* controller for some great software, **MPD** and **MPC**. They are great and you should check them out if you haven't yet.

   man mpd
   man mpc 


