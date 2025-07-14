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
        """Search using provided credentials with pagination and grouping - mimics orpheus.py CLI behavior"""
        try:
            # Normalize platform name
            platform_name = platform.lower()
            if platform_name == 'apple':
                platform_name = 'applemusic'

            module = self.orpheus.load_module(platform_name)

            # For Apple Music, check cookie authentication
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

            print(f"About to call search with: query_type=DownloadTypeEnum.track, query='{query}', limit={limit * 2}")

            # Perform search exactly like orpheus.py CLI does
            try:
                # Use the same search limit as CLI (but get more results for pagination)
                search_limit = limit * 2  # Get more results for pagination

                # This is exactly what orpheus.py does:
                items = module.search(query_type=DownloadTypeEnum.track, query=query, limit=search_limit)

                print(f"Search completed successfully")
                print(f"Search results type: {type(items)}")
                print(f"Search results length: {len(items) if hasattr(items, '__len__') else 'N/A'}")

                if len(items) == 0:
                    print(f'No search results for track: {query}')
                    return {
                        "tracks": [],
                        "pagination": {
                            "current_page": page,
                            "total_pages": 0,
                            "total_results": 0,
                            "has_next": False,
                            "has_previous": False,
                            "limit": limit
                        }
                    }

            except Exception as search_error:
                print(f"Search method failed: {search_error}")
                print(f"Search traceback: {traceback.format_exc()}")
                raise search_error

            # Convert results to expected format - mimic what orpheus.py does
            tracks = []

            if isinstance(items, list):
                print(f"Processing {len(items)} total search results")

                for index, item in enumerate(items):
                    try:
                        # This mimics exactly what orpheus.py does with SearchResult objects
                        if hasattr(item, 'result_id') and hasattr(item, 'name'):
                            print(f"Processing SearchResult {index}: {item.name}")

                            # Extract artist information - same logic as orpheus.py display
                            if hasattr(item, 'artists') and item.artists:
                                if isinstance(item.artists, list):
                                    artists_str = ', '.join(item.artists)
                                else:
                                    artists_str = str(item.artists)
                            else:
                                artists_str = "Unknown Artist"

                            # Get album info if available
                            album_name = "Unknown Album"
                            if hasattr(item, 'extra_kwargs') and item.extra_kwargs:
                                raw_result = item.extra_kwargs.get('raw_result', {})
                                if raw_result and 'attributes' in raw_result:
                                    album_name = raw_result['attributes'].get('albumName', 'Unknown Album')

                            # Build additional details string like orpheus.py does
                            additional_details = []
                            if hasattr(item, 'explicit') and item.explicit:
                                additional_details.append('[E]')
                            if hasattr(item, 'duration') and item.duration:
                                # Convert duration to mm:ss format like orpheus.py
                                minutes = item.duration // 60
                                seconds = item.duration % 60
                                additional_details.append(f'[{minutes:02d}m:{seconds:02d}s]')
                            if hasattr(item, 'year') and item.year:
                                additional_details.append(f'[{item.year}]')
                            if hasattr(item, 'additional') and item.additional:
                                additional_details.extend([f'[{i}]' for i in item.additional])

                            additional_info = ' '.join(additional_details)

                            # Generate platform-specific URL using the result_id (this is the key!)
                            track_url = self.get_platform_url(platform_name, 'track', item.result_id)

                            # Create track data structure
                            track_data = {
                                "id": item.result_id,  # This is the key - the actual ID for downloading
                                "name": item.name,
                                "artist": artists_str,
                                "album": album_name,
                                "duration": item.duration or 0,
                                "year": item.year if hasattr(item, 'year') else None,
                                "explicit": item.explicit if hasattr(item, 'explicit') else False,
                                "additional_info": additional_info,
                                "url": track_url,
                                # Include extra_kwargs for download compatibility
                                "extra_kwargs": item.extra_kwargs if hasattr(item, 'extra_kwargs') else {}
                            }

                            tracks.append(track_data)
                            print(
                                f"  Added track: {track_data['name']} by {track_data['artist']} (ID: {item.result_id})")

                        else:
                            print(f"  Result {index} missing required SearchResult attributes")

                    except Exception as parse_error:
                        print(f"Error parsing result {index}: {parse_error}")
                        print(f"Parse error traceback: {traceback.format_exc()}")

            else:
                print(f"Unexpected search result format: {type(items)}")
                raise Exception(f"Unexpected search result format: {type(items)}")

            print(f"Final tracks count: {len(tracks)}")

            # Apply pagination AFTER processing all tracks
            total_results = len(tracks)
            total_pages = (total_results + limit - 1) // limit if total_results > 0 else 0

            # Calculate offset for this page
            offset = (page - 1) * limit
            paginated_tracks = tracks[offset:offset + limit]

            print(
                f"Pagination: page {page}, offset {offset}, showing {len(paginated_tracks)} of {total_results} tracks")

            response = {
                "tracks": paginated_tracks,
                "pagination": {
                    "current_page": page,
                    "total_pages": total_pages,
                    "total_results": total_results,
                    "has_next": page < total_pages,
                    "has_previous": page > 1,
                    "limit": limit
                }
            }

            # Add album grouping if requested
            if group_by_album:
                organized = self.group_tracks_by_album(paginated_tracks)
                response["organized"] = organized

            print(f"Final response: {len(response['tracks'])} tracks in response")
            return response

        except Exception as e:
            print(f"Search error details: {e}")
            print(f"Full traceback: {traceback.format_exc()}")
            raise Exception(f"Search failed on {platform}: {e}")

    async def search_albums(self, platform: str, query: str, username: str, password: str, limit: int = 10):
        """Search for albums specifically WITHOUT loading tracklists"""
        try:
            module = self.orpheus.load_module(platform.lower())

            if not hasattr(module, 'session') or not module.session:
                raise Exception("No authenticated session found. Please authenticate manually first.")

            print(f"Searching albums for: {query}")

            # Search for albums
            album_results = module.search(query_type=DownloadTypeEnum.album, query=query, limit=limit)

            albums = []
            for result in album_results:
                if hasattr(result, 'result_id'):
                    album_data = {
                        "id": result.result_id,
                        "name": result.name,
                        "artist": ", ".join(result.artists) if hasattr(result,
                                                                       'artists') and result.artists else "Unknown Artist",
                        "year": result.year if hasattr(result, 'year') else None,
                        "type": "album",
                        "url": f"https://tidal.com/browse/album/{result.result_id}",
                        "tracks_loaded": False  # Indicate tracks are not loaded yet
                    }

                    albums.append(album_data)
                    print(f"Added album: {album_data['name']} (tracks not loaded)")

            # Return simple albums structure (no organized grouping for album search)
            return {"albums": albums}

        except Exception as e:
            print(f"Album search error: {e}")
            raise Exception(f"Album search failed on {platform}: {e}")

    async def get_album_tracks(self, platform: str, album_id: str, username: str, password: str):
        """Load tracks for a specific album on demand"""
        try:
            module = self.orpheus.load_module(platform.lower())

            if not hasattr(module, 'session') or not module.session:
                raise Exception("No authenticated session found. Please authenticate manually first.")

            print(f"Loading tracks for album: {album_id}")

            # Get detailed album info with tracklist
            album_info = module.get_album_info(album_id)
            tracks = []

            if hasattr(album_info, 'tracks') and album_info.tracks:
                print(f"Album has {len(album_info.tracks)} tracks")

                # Set up quality and codec options for track info calls
                quality_tier = QualityEnum.HIGH
                codec_options = CodecOptions(
                    proprietary_codecs=True,
                    spatial_codecs=True
                )

                for idx, track_id in enumerate(album_info.tracks, 1):
                    try:
                        # Get detailed track info to get real track names
                        track_info = module.get_track_info(track_id, quality_tier, codec_options)

                        # Extract real track name and info
                        track_name = f"Track {idx}"  # Default fallback
                        track_artist = "Unknown Artist"
                        track_duration = 0
                        track_explicit = False

                        if track_info:
                            if hasattr(track_info, 'name') and track_info.name:
                                track_name = track_info.name

                            if hasattr(track_info, 'artists') and track_info.artists:
                                if isinstance(track_info.artists, list):
                                    track_artist = ", ".join(track_info.artists)
                                else:
                                    track_artist = str(track_info.artists)

                            if hasattr(track_info, 'duration') and track_info.duration:
                                track_duration = track_info.duration

                            if hasattr(track_info, 'explicit'):
                                track_explicit = track_info.explicit

                        track_data = {
                            "track_number": idx,
                            "id": track_id,
                            "name": track_name,
                            "artist": track_artist,
                            "duration": track_duration,
                            "explicit": track_explicit,
                            "url": f"https://tidal.com/browse/track/{track_id}"
                        }

                        tracks.append(track_data)
                        print(f"  Track {idx}: {track_name} by {track_artist}")

                    except Exception as track_error:
                        print(f"Error getting track info for {track_id}: {track_error}")
                        # Add placeholder track with basic info
                        tracks.append({
                            "track_number": idx,
                            "id": track_id,
                            "name": f"Track {idx}",
                            "artist": "Unknown Artist",
                            "duration": 0,
                            "explicit": False,
                            "url": f"https://tidal.com/browse/track/{track_id}"
                        })

            return {"tracks": tracks}

        except Exception as e:
            print(f"Error loading album tracks: {e}")
            raise Exception(f"Failed to load album tracks: {e}")

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