import http.server
import socketserver
import subprocess
import urllib.parse
import urllib.request
import json
from pathlib import Path
from mutagen.flac import FLAC
from mutagen.id3 import ID3
from mutagen.mp4 import MP4

PORT = 8080
BLACKLIST_FILE = Path(__file__).parent / 'image_blacklist.json'

def load_blacklist():
    """Load blacklisted image URLs from file."""
    try:
        if BLACKLIST_FILE.exists():
            with open(BLACKLIST_FILE, 'r') as f:
                return set(json.load(f))
    except:
        pass
    return set()

def save_blacklist(blacklist):
    """Save blacklisted image URLs to file."""
    try:
        with open(BLACKLIST_FILE, 'w') as f:
            json.dump(list(blacklist), f)
    except:
        pass

IMAGE_BLACKLIST = load_blacklist()

# Whitelist of allowed mpc commands
ALLOWED_COMMANDS = {
    'status', 'current', 'play', 'pause', 'stop', 'next', 'prev', 'toggle',
    'volume', 'repeat', 'random', 'single', 'consume',
    'playlist', 'add', 'del', 'clear', 'shuffle', 'move',
    'search', 'find', 'findadd', 'searchadd', 'listall',
    'albumart', 'readpicture', 'update', 'stats'
}

def get_music_directory():
    """Get MPD's music directory from mpc config."""
    try:
        out = subprocess.check_output(['mpc', 'stats'], text=True, stderr=subprocess.DEVNULL)
        # Fallback: try common locations or use a safe default
    except:
        pass
    # Common default locations - adjust if needed
    for path in [Path.home() / 'Music', Path('/var/lib/mpd/music')]:
        if path.exists():
            return path.resolve()
    return Path.home() / 'Music'

MUSIC_DIR = get_music_directory()

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        p = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(p.query)
        cmd = q.get('cmd', [''])[0]
        fmt = q.get('format', [None])[0]
        binary = 'binary' in q
        args = q.get('args', [])

        # Serve HTML only if no cmd parameter
        if p.path in ('/', '/mpd-spiffy.html') and not cmd:
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            with open('mpd-spiffy.html', 'rb') as f:
                self.wfile.write(f.read())
            return

        if cmd == 'lyrics':
            self.handle_lyrics(args)
            return

        if cmd == 'artistart':
            self.handle_artistart(args)
            return

        if cmd == 'blacklistimg':
            self.handle_blacklist(args)
            return

        if cmd == 'list':
            self.handle_list(args)
            return

        if not cmd:
            self.send_error(400, "Missing cmd parameter")
            return

        if cmd not in ALLOWED_COMMANDS:
            self.send_error(403, f"Command not allowed: {cmd}")
            return

        mpc_args = ['mpc']
        if fmt:
            mpc_args += ['-f', fmt]
        mpc_args.append(cmd)
        mpc_args.extend(args)

        try:
            if binary:
                out = subprocess.check_output(mpc_args, stderr=subprocess.STDOUT)
                self.send_response(200)
                self.send_header('Content-type', 'image/jpeg')
                self.end_headers()
                self.wfile.write(out)
            else:
                out = subprocess.check_output(mpc_args, text=True, stderr=subprocess.STDOUT)
                self.send_response(200)
                self.send_header('Content-type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(out.encode('utf-8'))
        except subprocess.CalledProcessError as e:
            self.send_error(500, f"mpc error: {e.output if hasattr(e, 'output') else str(e)}")
        except Exception as e:
            self.send_error(500, f"Server error: {str(e)}")

    def handle_lyrics(self, args):
        """Fetch lyrics - first from file tags, then from web APIs"""
        if not args:
            self.send_error(400, "No file path provided")
            return
        file_path = args[0]
        artist = args[1] if len(args) > 1 else ''
        title = args[2] if len(args) > 2 else ''
        lyrics = None

        # Build full path - MPD returns relative paths from music directory
        full_path = None
        try:
            if Path(file_path).is_absolute():
                full_path = Path(file_path).resolve()
            else:
                full_path = (MUSIC_DIR / file_path).resolve()

            # Security: ensure path is within music directory
            if not str(full_path).startswith(str(MUSIC_DIR)):
                full_path = None
        except Exception:
            full_path = None

        # Try embedded lyrics first
        if full_path and full_path.exists():
            try:
                if file_path.lower().endswith('.mp3'):
                    audio = ID3(str(full_path))
                    for frame in audio.getall('USLT'):
                        if frame.text:
                            lyrics = frame.text
                            break
                elif file_path.lower().endswith('.flac'):
                    audio = FLAC(str(full_path))
                    lyrics = audio.get('LYRICS', audio.get('UNSYNCEDLYRICS', [None]))[0]
                elif file_path.lower().endswith(('.m4a', '.mp4')):
                    audio = MP4(str(full_path))
                    lyrics = audio.get('\xa9lyr', [None])[0]
            except Exception:
                pass

        # If no embedded lyrics, try web APIs
        if not lyrics and artist and title:
            # Try lrclib.net first (better structured)
            try:
                url = f"https://lrclib.net/api/get?artist_name={urllib.parse.quote(artist)}&track_name={urllib.parse.quote(title)}"
                with urllib.request.urlopen(url, timeout=5) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    lyrics = data.get('plainLyrics') or data.get('syncedLyrics')
            except:
                pass

            # Fallback to lyrics.ovh
            if not lyrics:
                try:
                    url = f"https://api.lyrics.ovh/v1/{urllib.parse.quote(artist)}/{urllib.parse.quote(title)}"
                    with urllib.request.urlopen(url, timeout=5) as resp:
                        data = json.loads(resp.read().decode('utf-8'))
                        lyrics = data.get('lyrics')
                except:
                    pass

        if not lyrics:
            lyrics = "No lyrics found"

        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(lyrics.encode('utf-8'))

    def handle_list(self, args):
        """Proxy for mpc list / find / search commands with formatting"""
        if not args:
            self.send_error(400, "Missing arguments for list command")
            return
        what = args[0]  # artist / album / ...
        rest = args[1:]
        try:
            out = subprocess.check_output(['mpc', 'list', what] + rest, text=True, stderr=subprocess.STDOUT)
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(out.encode('utf-8'))
        except subprocess.CalledProcessError as e:
            self.send_error(500, f"mpc list error: {e.output if hasattr(e, 'output') else str(e)}")
        except Exception as e:
            self.send_error(500, f"Server error: {str(e)}")

    # Class-level cache for images (stores actual image data per artist+album)
    image_cache = {}  # {cache_key: [(data, content_type, url), ...]}
    image_index = {}  # {cache_key: current_index}
    current_image_url = {}  # {cache_key: current_url} - track for blacklisting

    def handle_artistart(self, args):
        """Fetch and proxy images, cycling through cached images per artist+album"""
        if not args:
            self.send_error(400, "No artist name provided")
            return
        artist = args[0].strip()
        album = args[1].strip() if len(args) > 1 else ''

        # Cache key based on artist + album
        cache_key = f"{artist.lower()}|{album.lower()}"

        # Check if we need to fetch images for this combination
        if cache_key not in Handler.image_cache:
            image_urls = []
            is_soundtrack_search = album and album.lower() in ('soundtrack', 'ost', 'game', 'movie')

            # If album provided (and not just a soundtrack hint), search for album art first
            if album and not is_soundtrack_search:
                # Try Deezer album search
                try:
                    url = f"https://api.deezer.com/search/album?q={urllib.parse.quote(artist + ' ' + album)}&limit=1"
                    with urllib.request.urlopen(url, timeout=5) as resp:
                        data = json.loads(resp.read().decode('utf-8'))
                        if data.get('data') and len(data['data']) > 0:
                            cover = data['data'][0].get('cover_xl') or data['data'][0].get('cover_big')
                            if cover:
                                image_urls.append(cover)
                except:
                    pass

                # Try TheAudioDB album search
                try:
                    url = f"https://www.theaudiodb.com/api/v1/json/2/searchalbum.php?s={urllib.parse.quote(artist)}&a={urllib.parse.quote(album)}"
                    with urllib.request.urlopen(url, timeout=5) as resp:
                        data = json.loads(resp.read().decode('utf-8'))
                        if data.get('album') and len(data['album']) > 0:
                            alb = data['album'][0]
                            for key in ['strAlbumThumb', 'strAlbumThumbHQ', 'strAlbumCDart', 'strAlbumSpine']:
                                if alb.get(key):
                                    image_urls.append(alb[key])
                except:
                    pass

            # For soundtrack/filename searches, try multiple search variations
            search_terms = [artist]
            if is_soundtrack_search:
                search_terms.extend([
                    f"{artist} soundtrack",
                    f"{artist} ost",
                    f"{artist} game",
                    f"{artist} movie"
                ])

            # Collect artist images from Deezer (try multiple search terms)
            for term in search_terms[:2]:  # Limit API calls
                try:
                    url = f"https://api.deezer.com/search/artist?q={urllib.parse.quote(term)}&limit=1"
                    with urllib.request.urlopen(url, timeout=5) as resp:
                        data = json.loads(resp.read().decode('utf-8'))
                        if data.get('data') and len(data['data']) > 0:
                            art = data['data'][0]
                            for key in ['picture_xl', 'picture_big', 'picture_medium']:
                                if art.get(key) and art[key] not in image_urls:
                                    image_urls.append(art[key])
                                    break
                except:
                    pass

            # Try Deezer track search for soundtrack-style content
            if is_soundtrack_search or not image_urls:
                try:
                    url = f"https://api.deezer.com/search/track?q={urllib.parse.quote(artist)}&limit=3"
                    with urllib.request.urlopen(url, timeout=5) as resp:
                        data = json.loads(resp.read().decode('utf-8'))
                        for track in data.get('data', []):
                            album_cover = track.get('album', {}).get('cover_xl') or track.get('album', {}).get('cover_big')
                            if album_cover and album_cover not in image_urls:
                                image_urls.append(album_cover)
                except:
                    pass

            # Collect artist images from TheAudioDB
            try:
                url = f"https://www.theaudiodb.com/api/v1/json/2/search.php?s={urllib.parse.quote(artist)}"
                with urllib.request.urlopen(url, timeout=5) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    if data.get('artists') and len(data['artists']) > 0:
                        art = data['artists'][0]
                        for key in ['strArtistThumb', 'strArtistFanart', 'strArtistFanart2',
                                    'strArtistFanart3', 'strArtistFanart4', 'strArtistCutout',
                                    'strArtistClearart', 'strArtistWideThumb', 'strArtistBanner']:
                            if art.get(key) and art[key] not in image_urls:
                                image_urls.append(art[key])
            except:
                pass

            # Filter out blacklisted URLs
            image_urls = [u for u in image_urls if u not in IMAGE_BLACKLIST]

            # No fallback - let the UI show particle nebula instead
            if not image_urls:
                self.send_response(204)  # No Content
                self.end_headers()
                return

            # Download and cache all images (with URL for blacklist tracking)
            cached_images = []
            for img_url in image_urls:
                try:
                    req = urllib.request.Request(img_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        img_data = resp.read()
                        content_type = resp.headers.get('Content-Type', 'image/jpeg')
                        if len(img_data) > 500:
                            cached_images.append((img_data, content_type, img_url))
                except:
                    pass

            if not cached_images:
                self.send_error(404, "Could not fetch images")
                return

            Handler.image_cache[cache_key] = cached_images
            Handler.image_index[cache_key] = 0

        # Get current cached image and cycle to next
        images = Handler.image_cache[cache_key]
        idx = Handler.image_index[cache_key]
        img_data, content_type, img_url = images[idx]

        # Track current image URL for blacklisting
        Handler.current_image_url[cache_key] = img_url

        # Advance index for next request
        Handler.image_index[cache_key] = (idx + 1) % len(images)

        # Serve from cache
        self.send_response(200)
        self.send_header('Content-type', content_type)
        self.send_header('X-Image-Index', f"{idx + 1}/{len(images)}")
        self.send_header('X-Cache', 'HIT')
        self.send_header('X-Cache-Key', cache_key)
        self.send_header('Access-Control-Expose-Headers', 'X-Cache-Key, X-Image-Index')
        self.end_headers()
        self.wfile.write(img_data)

    def handle_blacklist(self, args):
        """Blacklist the current image for a given cache key."""
        global IMAGE_BLACKLIST
        if not args:
            self.send_error(400, "No cache key provided")
            return

        cache_key = args[0].lower()

        if cache_key not in Handler.current_image_url:
            self.send_error(404, "No current image for this key")
            return

        img_url = Handler.current_image_url[cache_key]

        # Don't blacklist placeholder images
        if 'ui-avatars.com' in img_url:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            remaining = len(Handler.image_cache.get(cache_key, []))
            self.wfile.write(json.dumps({'error': 'Cannot blacklist placeholder', 'remaining': remaining}).encode('utf-8'))
            return

        # Add to blacklist and save
        IMAGE_BLACKLIST.add(img_url)
        save_blacklist(IMAGE_BLACKLIST)

        # Remove from cache
        if cache_key in Handler.image_cache:
            Handler.image_cache[cache_key] = [
                img for img in Handler.image_cache[cache_key] if img[2] != img_url
            ]
            # If cache is now empty, remove it so it gets refetched
            if not Handler.image_cache[cache_key]:
                del Handler.image_cache[cache_key]
                if cache_key in Handler.image_index:
                    del Handler.image_index[cache_key]
            else:
                # Adjust index if needed
                Handler.image_index[cache_key] = Handler.image_index[cache_key] % len(Handler.image_cache[cache_key])

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        remaining = len(Handler.image_cache.get(cache_key, []))
        self.wfile.write(json.dumps({'blacklisted': img_url, 'remaining': remaining}).encode('utf-8'))

class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

with ReusableTCPServer(("127.0.0.1", PORT), Handler) as httpd:
    print(f"mpd-web → http://localhost:{PORT}")
    print(f"(bound to localhost only for security)")
    httpd.serve_forever()