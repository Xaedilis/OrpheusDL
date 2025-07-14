from orpheus.core import Orpheus
import traceback
import subprocess
import os
from utils.models import DownloadTypeEnum, QualityEnum, CodecOptions, CodecEnum
from collections import defaultdict


class OrpheusManager:
    def __init__(self):
        self.orpheus = Orpheus()
        self.active_sessions = {}

    async def test_login(self, platform: str, username: str, password: str) -> bool:
        """Test if credentials are valid for a platform"""
        try:
            module = self.orpheus.load_module(platform.lower())

            # Check if module has existing valid sessions
            if hasattr(module, 'session') and module.session:
                # Module is already authenticated, return True
                session_key = f"{platform}_{username}"
                self.active_sessions[session_key] = module
                return True

            return False

        except Exception as e:
            print(f"Login failed for {platform}: {e}")
            return False

    async def get_track_album_info(self, module, track_id: str):
        """Get album name for a track by fetching track info"""
        try:
            # Get track info with proper parameters
            quality_tier = QualityEnum.HIGH  # Default quality
            codec_options = CodecOptions(
                proprietary_codecs=True,
                spatial_codecs=True
            )

            track_info = module.get_track_info(track_id, quality_tier, codec_options)
            if hasattr(track_info, 'album') and track_info.album:
                return track_info.album
            elif hasattr(track_info, 'album_name') and track_info.album_name:
                return track_info.album_name
            return None
        except Exception as e:
            print(f"Error getting track album info for {track_id}: {e}")
            return None

    def group_tracks_by_album(self, tracks):
        """Group tracks by actual album names"""
        albums = defaultdict(list)
        singles = []

        for track in tracks:
            # Group by actual album name
            album_name = track.get('album', 'Unknown Album')

            # Skip singles/unknown albums
            if album_name and album_name not in ['Single', 'Unknown Album', 'Unknown']:
                albums[album_name].append(track)
            else:
                singles.append(track)

        # Separate singles from multi-track albums
        organized = {
            'albums': {},
            'singles': singles
        }

        # Only show as album if it has multiple tracks
        for album_name, track_list in albums.items():
            if len(track_list) > 1:
                organized['albums'][album_name] = track_list
            else:
                organized['singles'].extend(track_list)

        return organized

    def get_platform_url(self, platform: str, media_type: str, media_id: str) -> str:
        """Generate platform-specific URLs that match what orpheus.py expects"""
        url_patterns = {
            'tidal': {
                'track': f"https://tidal.com/browse/track/{media_id}",
                'album': f"https://tidal.com/browse/album/{media_id}",
                'playlist': f"https://tidal.com/browse/playlist/{media_id}"
            },
            'applemusic': {
                # Apple Music URLs should include the full path structure
                'track': f"https://music.apple.com/us/song/{media_id}",
                'album': f"https://music.apple.com/us/album/{media_id}",
                'playlist': f"https://music.apple.com/us/playlist/{media_id}"
            },
            'spotify': {
                'track': f"https://open.spotify.com/track/{media_id}",
                'album': f"https://open.spotify.com/album/{media_id}",
                'playlist': f"https://open.spotify.com/playlist/{media_id}"
            }
        }

        return url_patterns.get(platform, {}).get(media_type, f"#{media_id}")

    async def search_with_credentials(self, platform: str, query: str, username: str, password: str,
                                      page: int = 1, limit: int = 20, group_by_album: bool = False):
        """Search with username/password credentials and optional album grouping with pagination support"""
        try:
            # Normalize platform name
            platform_name = platform.lower()
            if platform_name == 'apple':
                platform_name = 'applemusic'

            print(f"Searching on platform {platform_name} with query: {query}")
            print(f"Group by album: {group_by_album}, Limit: {limit}")

            module = self.orpheus.load_module(platform_name)

            if platform_name == 'applemusic':
                print("Using Apple Music with cookie authentication")

                # Check if the module is properly authenticated
                if not hasattr(module, 'is_authenticated') or not module.is_authenticated:
                    raise Exception(
                        "Apple Music module not authenticated. Please check your cookies.txt file in the /config folder.")

                print("Apple Music authentication verified successfully")

                # Apple Music API has a 50 result limit per request, so we need to paginate
                all_tracks = []
                total_fetched = 0
                offset = 0
                page_size = 50  # Apple Music's max limit

                while total_fetched < limit:
                    # Calculate how many results to fetch in this request
                    current_limit = min(page_size, limit - total_fetched)

                    print(f"Fetching page with offset {offset}, limit {current_limit}")

                    # Use the Apple Music API directly for pagination
                    try:
                        # Access the Apple Music API from the module
                        apple_api = module.apple_music_api
                        search_results = apple_api.search(
                            term=query,
                            types="songs",
                            limit=current_limit,
                            offset=offset
                        )

                        print(f"Search results type: {type(search_results)}")
                        print(f"Search results content: {search_results}")

                        # Validate search results structure
                        if not isinstance(search_results, dict):
                            print(f"Error: Expected dict, got {type(search_results)}")
                            break

                        # Extract songs from search results
                        songs_data = search_results.get('songs', {})
                        if not isinstance(songs_data, dict):
                            print(f"Error: songs data is not a dict: {type(songs_data)}")
                            break

                        songs = songs_data.get('data', [])
                        if not isinstance(songs, list):
                            print(f"Error: songs.data is not a list: {type(songs)}")
                            break

                        if not songs:
                            print("No more results available")
                            break

                        print(f"Found {len(songs)} songs in this page")

                        # Convert Apple Music API results to our format
                        for song_data in songs:
                            try:
                                # Validate song data structure
                                if not isinstance(song_data, dict):
                                    print(f"Warning: song_data is not a dict: {type(song_data)}")
                                    continue

                                attributes = song_data.get('attributes', {})
                                if not isinstance(attributes, dict):
                                    print(f"Warning: attributes is not a dict: {type(attributes)}")
                                    continue

                                # Extract basic info
                                song_id = song_data.get('id')
                                song_name = attributes.get('name')
                                artist_name = attributes.get('artistName', 'Unknown Artist')
                                album_name = attributes.get('albumName', 'Unknown Album')
                                release_date = attributes.get('releaseDate', '')
                                duration_ms = attributes.get('durationInMillis', 0)
                                track_number = attributes.get('trackNumber')
                                is_explicit = attributes.get('contentRating') == 'explicit'

                                # Convert duration from milliseconds to seconds
                                duration_seconds = duration_ms // 1000 if duration_ms else None

                                # Extract year from release date
                                year = release_date[:4] if release_date and len(release_date) >= 4 else None

                                # Split artist name into list
                                artists = [artist.strip() for artist in artist_name.split(',') if artist.strip()]
                                if not artists:
                                    artists = [artist_name]

                                print(f"Processing song: {song_name} by {artist_name} from {album_name}")

                                # Try to get more detailed track info for better album information
                                detailed_album_name = album_name
                                detailed_album_artist = artist_name
                                detailed_track_number = track_number

                                try:
                                    if song_id:
                                        track_info = module.get_track_info(song_id)
                                        if hasattr(track_info, 'album') and track_info.album:
                                            detailed_album_name = track_info.album.name if hasattr(track_info.album,
                                                                                                   'name') else album_name
                                            detailed_album_artist = track_info.album.artist if hasattr(track_info.album,
                                                                                                       'artist') else artist_name
                                        if hasattr(track_info, 'track_number'):
                                            detailed_track_number = track_info.track_number

                                        print(f"Enhanced album info: {detailed_album_name} by {detailed_album_artist}")

                                except Exception as e:
                                    print(f"Could not get detailed track info for {song_name}: {e}")
                                    # Use the basic info we already have
                                    pass

                                track_data = {
                                    "id": song_id,
                                    "name": song_name,
                                    "artist": ', '.join(artists),
                                    "album": detailed_album_name,
                                    "album_artist": detailed_album_artist,
                                    "duration": duration_seconds,
                                    "track_number": detailed_track_number,
                                    "year": year,
                                    "explicit": is_explicit,
                                    "url": self.get_platform_url(platform_name, 'track', song_id) if song_id else None,
                                    "additional_info": None
                                }

                                all_tracks.append(track_data)
                                print(f"Added track: {track_data['name']} - {track_data['album']}")

                            except Exception as e:
                                print(f"Error processing song data: {e}")
                                print(f"Song data: {song_data}")
                                continue

                        total_fetched += len(songs)
                        offset += len(songs)

                        # If we got fewer results than requested, we've reached the end
                        if len(songs) < current_limit:
                            print("Reached end of results")
                            break

                    except Exception as e:
                        print(f"Error fetching page at offset {offset}: {e}")
                        import traceback
                        traceback.print_exc()
                        break

                print(f"Total tracks fetched: {len(all_tracks)}")

                # If group_by_album is True, we still return individual tracks
                # but the frontend will group them by album
                result_data = {
                    "tracks": all_tracks,
                    "pagination": {
                        "current_page": page,
                        "total_pages": 1,  # We don't have pagination info from Apple Music
                        "total_results": len(all_tracks),
                        "has_more": len(all_tracks) == limit  # Indicate if there might be more results
                    },
                    "grouped_by_album": group_by_album
                }

                return result_data

            else:
                # For Tidal and other platforms
                print("Using Tidal with username/password authentication")

                # Check if we already have an authenticated session
                if not hasattr(module, 'session') or not module.session:
                    print("No existing session found, attempting to authenticate...")

                    # Try to authenticate
                    success = await self.test_login(platform_name, username, password)
                    if not success:
                        raise Exception("Authentication failed. Please check your credentials.")

                    # Reload the module to get the authenticated session
                    module = self.orpheus.load_module(platform_name)

                # Search for tracks
                from utils.models import DownloadTypeEnum
                search_results = module.search(
                    query_type=DownloadTypeEnum.track,
                    query=query,
                    limit=limit
                )

                print(f"Found {len(search_results)} search results")

                # Convert to our format
                tracks = []
                for result in search_results:
                    track_data = {
                        "id": result.result_id,
                        "name": result.name,
                        "artist": ', '.join(result.artists) if result.artists else 'Unknown Artist',
                        "album": getattr(result, 'album', 'Unknown Album'),
                        "duration": result.duration,
                        "track_number": getattr(result, 'track_number', None),
                        "year": result.year,
                        "explicit": result.explicit,
                        "url": self.get_platform_url(platform_name, 'track', result.result_id),
                        "additional_info": result.additional[0] if result.additional else None
                    }
                    tracks.append(track_data)

                # Group by album if requested
                if group_by_album:
                    tracks = self.group_tracks_by_album(tracks)

                result_data = {
                    "tracks": tracks,
                    "pagination": {
                        "current_page": page,
                        "total_pages": 1,
                        "total_results": len(tracks)
                    },
                    "grouped_by_album": group_by_album
                }

                return result_data

        except Exception as e:
            print(f"Search error: {e}")
            import traceback
            traceback.print_exc()
            raise Exception(f"Search failed: {e}")

    async def search_albums(self, platform: str, query: str, username: str, password: str, limit: int = 10):
        """Search for albums specifically WITHOUT loading tracklists"""
        try:
            # Normalize platform name
            platform_name = platform.lower()
            if platform_name == 'apple':
                platform_name = 'applemusic'

            module = self.orpheus.load_module(platform_name)

            # Use the same authentication check as the track search
            if platform_name == 'applemusic':
                print("Using Apple Music with cookie authentication")

                # Check if the module is properly authenticated
                if not hasattr(module, 'is_authenticated') or not module.is_authenticated:
                    raise Exception(
                        "Apple Music module not authenticated. Please check your cookies.txt file in the /config folder.")

                print("Apple Music authentication verified successfully")
            else:
                # Check if module has an active session for other platforms
                if not hasattr(module, 'session') or not module.session:
                    raise Exception("No authenticated session found. Please authenticate manually first.")

            print(f"Searching albums for: {query}")

            # Search for albums
            album_results = module.search(query_type=DownloadTypeEnum.album, query=query, limit=limit)

            albums = []
            for result in album_results:
                if hasattr(result, 'result_id'):
                    # Extract artist information - same logic as track search
                    if hasattr(result, 'artists') and result.artists:
                        if isinstance(result.artists, list):
                            artists_str = ', '.join(result.artists)
                        else:
                            artists_str = str(result.artists)
                    else:
                        artists_str = "Unknown Artist"

                    # Generate platform-specific URL
                    album_url = self.get_platform_url(platform_name, 'album', result.result_id)

                    album_data = {
                        "id": result.result_id,
                        "name": result.name,
                        "artist": artists_str,
                        "year": result.year if hasattr(result, 'year') else None,
                        "type": "album",
                        "url": album_url,
                        "tracks_loaded": False  # Indicate tracks are not loaded yet
                    }

                    albums.append(album_data)
                    print(f"Added album: {album_data['name']} by {album_data['artist']} (tracks not loaded)")

            # Return simple albums structure (no organized grouping for album search)
            return {"albums": albums}

        except Exception as e:
            print(f"Album search error: {e}")
            raise Exception(f"Album search failed on {platform}: {e}")

    async def get_album_tracks(self, platform: str, album_id: str, username: str, password: str):
        """Get tracks for a specific album"""
        try:
            # Normalize platform name
            platform_name = platform.lower()
            if platform_name == 'apple':
                platform_name = 'applemusic'

            print(f"Loading tracks for album {album_id} on platform {platform_name}")
            module = self.orpheus.load_module(platform_name)

            if platform_name == 'applemusic':
                print("Using Apple Music with cookie authentication")

                # Check if the module is properly authenticated
                if not hasattr(module, 'is_authenticated') or not module.is_authenticated:
                    raise Exception(
                        "Apple Music module not authenticated. Please check your cookies.txt file in the /config folder.")

                print("Apple Music authentication verified successfully")

                # First, try to get album info
                try:
                    album_info = module.get_album_info(album_id)
                    print(f"Got album info: {type(album_info)}")
                    print(f"Album info attributes: {dir(album_info) if album_info else 'None'}")

                    if not album_info:
                        raise Exception("Album not found")

                    tracks = []

                    # Check if album_info has tracks and they're populated
                    if hasattr(album_info, 'tracks') and album_info.tracks:
                        print(f"Found {len(album_info.tracks)} tracks in album info")

                        # Check if the first track is a string (placeholder) or an object
                        first_track = album_info.tracks[0]
                        print(f"First track type: {type(first_track)}")
                        print(f"First track value: {first_track}")

                        if isinstance(first_track, str):
                            print("Tracks are just placeholders (strings), not actual track objects")
                            print("Apple Music cookie authentication doesn't provide individual track details")

                            # Create placeholder tracks with basic info
                            for i, track_placeholder in enumerate(album_info.tracks):
                                track_data = {
                                    "id": f"{album_id}_{i}",  # Create a pseudo-ID
                                    "name": f"Track {i + 1}",  # Generic name since we don't have real names
                                    "artist": album_info.artist if hasattr(album_info, 'artist') else "Unknown Artist",
                                    "album": album_info.name if hasattr(album_info, 'name') else "Unknown Album",
                                    "duration": None,
                                    "track_number": i + 1,
                                    "year": album_info.release_year if hasattr(album_info, 'release_year') else None,
                                    "explicit": False,  # We don't know this with cookie auth
                                    "url": self.get_platform_url(platform_name, 'album', album_id)
                                    # Use album URL since we don't have individual track URLs
                                }
                                tracks.append(track_data)
                                print(f"Added placeholder track: {track_data['name']}")

                            # Return tracks with a message explaining the limitation
                            return {
                                "tracks": tracks,
                                "message": "Individual track names not available with cookie authentication. Track numbers are shown instead. You can download the full album to get all tracks with proper names."
                            }

                        else:
                            # If tracks are actual objects, process them normally
                            for i, track in enumerate(album_info.tracks):
                                print(f"Track {i + 1}: {type(track)} - {dir(track) if track else 'None'}")

                                # Extract track information
                                track_data = {
                                    "id": track.id if hasattr(track, 'id') else str(i),
                                    "name": track.name if hasattr(track, 'name') else f"Track {i + 1}",
                                    "artist": track.artist if hasattr(track, 'artist') else album_info.artist,
                                    "album": album_info.name if hasattr(album_info, 'name') else "Unknown Album",
                                    "duration": track.duration if hasattr(track, 'duration') else None,
                                    "track_number": track.track_number if hasattr(track, 'track_number') else (i + 1),
                                    "year": album_info.release_year if hasattr(album_info, 'release_year') else None,
                                    "explicit": track.explicit if hasattr(track, 'explicit') else False,
                                    "url": self.get_platform_url(platform_name, 'track',
                                                                 track.id if hasattr(track, 'id') else str(i))
                                }
                                tracks.append(track_data)
                                print(f"Added track: {track_data['name']}")

                            return {"tracks": tracks}

                    else:
                        print("No tracks found in album info, trying search fallback...")

                        # Try searching for tracks with the album name as fallback
                        from utils.models import DownloadTypeEnum

                        try:
                            search_query = f"{album_info.name} {album_info.artist}"
                            print(f"Searching for tracks with query: {search_query}")

                            search_results = module.search(
                                query_type=DownloadTypeEnum.track,
                                query=search_query,
                                limit=100
                            )

                            print(f"Search returned {len(search_results)} results")

                            # Filter results to only include tracks from this album
                            for result in search_results:
                                print(f"Search result: {result.name} - Album: {getattr(result, 'album', 'N/A')}")
                                # Check if this track belongs to our album
                                if hasattr(result, 'album') and result.album and album_info.name in result.album:
                                    track_data = {
                                        "id": result.result_id,
                                        "name": result.name,
                                        "artist": result.artist if hasattr(result, 'artist') else album_info.artist,
                                        "album": result.album,
                                        "duration": result.duration if hasattr(result, 'duration') else None,
                                        "track_number": result.track_number if hasattr(result,
                                                                                       'track_number') else None,
                                        "year": album_info.release_year if hasattr(album_info,
                                                                                   'release_year') else None,
                                        "explicit": result.explicit if hasattr(result, 'explicit') else False,
                                        "url": self.get_platform_url(platform_name, 'track', result.result_id)
                                    }
                                    tracks.append(track_data)
                                    print(f"Added track from search: {track_data['name']}")

                            if tracks:
                                return {"tracks": tracks}
                            else:
                                # If no tracks found via search, return message
                                return {
                                    "tracks": [],
                                    "message": "Individual track listing not available with cookie authentication. You can download the full album instead."
                                }

                        except Exception as search_error:
                            print(f"Search fallback failed: {search_error}")
                            # If search fails, create a message explaining the limitation
                            return {
                                "tracks": [],
                                "message": "Individual track listing not available with cookie authentication. You can download the full album instead."
                            }

                except Exception as e:
                    print(f"Error getting album info: {e}")
                    import traceback
                    traceback.print_exc()
                    raise Exception(f"Failed to get album tracks: {e}")

            else:
                # For other platforms like Tidal, use existing implementation
                print("Using Tidal implementation")
                if not hasattr(module, 'session') or not module.session:
                    raise Exception("No authenticated session found. Please authenticate manually first.")

                # Get tracks for the album
                album_tracks = module.tidal_api.get_album_tracks(album_id)

                tracks = []
                for track in album_tracks.get('items', []):
                    track_data = {
                        "id": track['id'],
                        "name": track['title'],
                        "artist": ', '.join([artist['name'] for artist in track.get('artists', [])]),
                        "album": track.get('album', {}).get('title', 'Unknown Album'),
                        "duration": track.get('duration'),
                        "track_number": track.get('trackNumber'),
                        "year": track.get('album', {}).get('releaseDate', '').split('-')[0] if track.get('album',
                                                                                                         {}).get(
                            'releaseDate') else None,
                        "explicit": track.get('explicit', False),
                        "url": self.get_platform_url(platform_name, 'track', track['id'])
                    }
                    tracks.append(track_data)

                return {"tracks": tracks}

        except Exception as e:
            print(f"Album tracks loading error: {e}")
            import traceback
            traceback.print_exc()
            raise Exception(f"Failed to load album tracks from {platform}: {e}")

    async def download_track(self, platform: str, track_url: str):
        """Download track using orpheus.py script"""
        try:
            # Path to the orpheus.py script
            orpheus_script_path = os.path.join(os.getcwd(), "orpheus.py")

            if not os.path.exists(orpheus_script_path):
                raise Exception(f"orpheus.py script not found at {orpheus_script_path}")

            print(f"Starting download for track: {track_url}")

            # Run orpheus.py with the track URL
            cmd = ["python", orpheus_script_path, track_url]

            # Start the process with proper encoding handling
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,  # Handle as bytes to avoid encoding issues
                cwd=os.getcwd(),
                env=os.environ.copy()  # Preserve environment variables
            )

            # Get the process ID for tracking
            pid = process.pid

            print(f"Download process started with PID: {pid}")
            print(f"Command: {' '.join(cmd)}")

            return {
                "success": True,
                "message": f"Download started for {track_url}",
                "pid": pid,
                "command": ' '.join(cmd)
            }

        except Exception as e:
            print(f"Download error: {e}")
            raise Exception(f"Download failed: {e}")

    async def download_album(self, platform: str, album_url: str):
        """Download album using orpheus.py script"""
        try:
            # Path to the orpheus.py script
            orpheus_script_path = os.path.join(os.getcwd(), "orpheus.py")

            if not os.path.exists(orpheus_script_path):
                raise Exception(f"orpheus.py script not found at {orpheus_script_path}")

            print(f"Starting download for album: {album_url}")

            # Run orpheus.py with the album URL
            cmd = ["python", orpheus_script_path, album_url]

            # Start the process with proper encoding handling
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,  # Handle as bytes to avoid encoding issues
                cwd=os.getcwd(),
                env=os.environ.copy()  # Preserve environment variables
            )

            # Get the process ID for tracking
            pid = process.pid

            print(f"Download process started with PID: {pid}")
            print(f"Command: {' '.join(cmd)}")

            return {
                "success": True,
                "message": f"Album download started for {album_url}",
                "pid": pid,
                "command": ' '.join(cmd)
            }

        except Exception as e:
            print(f"Album download error: {e}")
            raise Exception(f"Album download failed: {e}")

    def get_available_platforms(self):
        """Get list of available platforms"""
        return list(self.orpheus.module_list)

    def safe_decode_output(self, output_bytes):
        """Safely decode subprocess output with fallback handling"""
        if not output_bytes:
            return ""

        # Try UTF-8 first
        try:
            return output_bytes.decode('utf-8')
        except UnicodeDecodeError:
            pass

        # Try UTF-8 with error replacement
        try:
            return output_bytes.decode('utf-8', errors='replace')
        except UnicodeDecodeError:
            pass

        # Try system default encoding with error replacement
        try:
            return output_bytes.decode(errors='replace')
        except UnicodeDecodeError:
            # Last resort: latin1 can decode any byte sequence
            return output_bytes.decode('latin1', errors='replace')