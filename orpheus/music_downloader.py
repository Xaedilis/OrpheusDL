import logging, os, ffmpeg
import shutil
import unicodedata
from dataclasses import asdict
from time import strftime, gmtime
import json
from enum import Enum
import uuid
import time
import re

from ffmpeg import Error

from orpheus.tagging import tag_file
from utils.models import *
from utils.utils import *
from utils.exceptions import *

# --- Modular Spotify Import ---
try:
    from modules.spotify.spotify_api import SpotifyRateLimitDetectedError
except ModuleNotFoundError:
    # Define a dummy exception if Spotify module isn't found
    # This allows 'except SpotifyRateLimitDetectedError:' blocks elsewhere
    # in this file to still compile, though they will never be triggered.
    class SpotifyRateLimitDetectedError(Exception):
        pass


def beauty_format_seconds(seconds: int) -> str:
    time_data = gmtime(seconds)

    time_format = "%Mm:%Ss"
    # if seconds are higher than 3600s also add the hour format
    if time_data.tm_hour > 0:
        time_format = "%Hh:" + time_format
    # TODO: also add days to time_format if hours > 24?

    # return the formatted time string
    return strftime(time_format, time_data)


# Helper function to serialize Enums for JSON
def json_enum_serializer(obj):
    if isinstance(obj, Enum):
        return obj.name
    # Let the default encoder raise TypeError for other unserializable types
    raise TypeError(f'Object of type {obj.__class__.__name__} is not JSON serializable')


class Downloader:
    def __init__(self, settings, module_controls, oprinter, path):
        self.global_settings = settings
        self.module_controls = module_controls
        self.oprinter = oprinter
        self.path = path
        self.service = None
        self.service_name = None
        self.download_mode = None
        self.third_party_modules = None
        self.temp_dir = None  # Will be set by core.py
        self.indent_number = 0
        self.module_list = module_controls['module_list']
        self.module_settings = module_controls['module_settings']
        self.loaded_modules = module_controls['loaded_modules']
        self.load_module = module_controls['module_loader']

        self.print = self.oprinter.oprint
        self.set_indent_number = self.oprinter.set_indent_number

    def create_temp_filename(self):
        """Create a temporary filename in the temp directory"""
        if not self.temp_dir:
            # If temp_dir is not set, create it in the current directory
            self.temp_dir = os.path.join(os.getcwd(), 'temp')
        os.makedirs(self.temp_dir, exist_ok=True)
        return os.path.join(self.temp_dir, str(uuid.uuid4()))

    def search_by_tags(self, module_name, track_info: TrackInfo):
        return self.loaded_modules[module_name].search(DownloadTypeEnum.track, f'{track_info.name} {" ".join(track_info.artists)}', track_info=track_info)

    def _add_track_m3u_playlist(self, m3u_playlist: str, track_info: TrackInfo, track_location: str):
        if self.global_settings['playlist']['extended_m3u']:
            with open(m3u_playlist, 'a', encoding='utf-8') as f:
                # if no duration exists default to -1
                duration = track_info.duration if track_info.duration else -1
                # write the extended track header
                f.write(f'#EXTINF:{duration}, {track_info.artists[0]} - {track_info.name}\n')

        with open(m3u_playlist, 'a', encoding='utf-8') as f:
            if self.global_settings['playlist']['paths_m3u'] == "absolute":
                # add the absolute paths to the playlist
                f.write(f'{os.path.abspath(track_location)}\n')
            else:
                # add the relative paths to the playlist by subtracting the track_location with the m3u_path
                f.write(f'{os.path.relpath(track_location, os.path.dirname(m3u_playlist))}\n')

            # add an extra new line to the extended format
            f.write('\n') if self.global_settings['playlist']['extended_m3u'] else None

    def download_playlist(self, playlist_id, custom_module=None, extra_kwargs=None):
        self.set_indent_number(1)

        service_name_lower = ""
        if hasattr(self, 'service_name') and self.service_name:
            service_name_lower = self.service_name.lower()

        # Prepare kwargs for get_playlist_info, making a copy to modify
        kwargs_for_playlist_info = {}
        if extra_kwargs:
            kwargs_for_playlist_info.update(extra_kwargs)

        if service_name_lower in ['beatport', 'beatsource']:
            if 'data' in kwargs_for_playlist_info:
                logging.debug(f"Removing 'data' from extra_kwargs for {self.service_name}.get_playlist_info as it is unexpected.")
                kwargs_for_playlist_info.pop('data', None)

        playlist_info: PlaylistInfo = self.service.get_playlist_info(playlist_id, **kwargs_for_playlist_info)
        self.print(f'=== Downloading playlist {playlist_info.name} ({playlist_id}) ===', drop_level=1)
        self.print(f'Playlist creator: {playlist_info.creator}' + (f' ({playlist_info.creator_id})' if playlist_info.creator_id else ''))
        if playlist_info.release_year: self.print(f'Playlist creation year: {playlist_info.release_year}')
        if playlist_info.duration: self.print(f'Duration: {beauty_format_seconds(playlist_info.duration)}')
        number_of_tracks = len(playlist_info.tracks)
        self.print(f'Number of tracks: {number_of_tracks!s}')
        self.print(f'Platform: {self.module_settings[self.service_name].service_name}')
        
        # Sanitize and shorten playlist name for filesystem
        safe_playlist_name = sanitise_name(playlist_info.name)
        if len(safe_playlist_name) > 50: # Truncate long names
            safe_playlist_name = safe_playlist_name[:50]

        playlist_tags = {k: sanitise_name(v) for k, v in asdict(playlist_info).items()}
        playlist_tags['name'] = safe_playlist_name # Use the safe name for path formatting
        playlist_tags['explicit'] = ' [E]' if playlist_info.explicit else ''
        playlist_path_formatted_name = self.global_settings['formatting']['playlist_format'].format(**playlist_tags)
        playlist_path = os.path.join(self.path, playlist_path_formatted_name)
        # fix path byte limit
        playlist_path = fix_byte_limit(playlist_path) + '/'
        os.makedirs(playlist_path, exist_ok=True)
        
        if playlist_info.cover_url:
            self.print('Downloading playlist cover')
            download_file(playlist_info.cover_url, f'{playlist_path}cover.{playlist_info.cover_type.name}', artwork_settings=self._get_artwork_settings())
        
        if playlist_info.animated_cover_url and self.global_settings['covers']['save_animated_cover']:
            self.print('Downloading animated playlist cover')
            download_file(playlist_info.animated_cover_url, playlist_path + 'cover.mp4', enable_progress_bar=True)
        
        if playlist_info.description:
            with open(playlist_path + 'description.txt', 'w', encoding='utf-8') as f: f.write(playlist_info.description)

        m3u_playlist_path = None
        if self.global_settings['playlist']['save_m3u']:
            if self.global_settings['playlist']['paths_m3u'] not in {"absolute", "relative"}:
                raise ValueError(f'Invalid value for paths_m3u: "{self.global_settings["playlist"]["paths_m3u"]}",'
                                 f' must be either "absolute" or "relative"')

            m3u_playlist_path = os.path.join(playlist_path, f'{safe_playlist_name}.m3u')

            # create empty file
            with open(m3u_playlist_path, 'w', encoding='utf-8') as f:
                f.write('')

            # if extended format add the header
            if self.global_settings['playlist']['extended_m3u']:
                with open(m3u_playlist_path, 'a', encoding='utf-8') as f:
                    f.write('#EXTM3U\n\n')

        tracks_errored = set()
        rate_limited_tracks = [] # Initialize list for deferred tracks

        # --- First Pass --- 
        self.print("--- Starting initial playlist download pass ---")
        if custom_module:
            supported_modes = self.module_settings[custom_module].module_supported_modes 
            if ModuleModes.download not in supported_modes and ModuleModes.playlist not in supported_modes:
                raise Exception(f'Module "{custom_module}" cannot be used to download a playlist') # TODO: replace with ModuleDoesNotSupportAbility
            self.print(f'Service used for downloading: {self.module_settings[custom_module].service_name}')
            original_service = str(self.service_name)
            self.load_module(custom_module)
            for index, track_id in enumerate(playlist_info.tracks, start=1):
                self.set_indent_number(2)
                print()
                self.print(f'Track {index}/{number_of_tracks}', drop_level=1)
                quality_tier = QualityEnum[self.global_settings['general']['download_quality'].upper()]
                codec_options = CodecOptions(
                    spatial_codecs = self.global_settings['codecs']['spatial_codecs'],
                    proprietary_codecs = self.global_settings['codecs']['proprietary_codecs'],
                )
                track_info: TrackInfo = self.loaded_modules[original_service].get_track_info(track_id, quality_tier, codec_options, **playlist_info.track_extra_kwargs)
                
                self.service = self.loaded_modules[custom_module]
                self.service_name = custom_module
                results = self.search_by_tags(custom_module, track_info)
                track_id_new = results[0].result_id if len(results) else None
                
                if track_id_new:
                    self.download_track(track_id_new, album_location=playlist_path, track_index=index, number_of_tracks=number_of_tracks, indent_level=2, m3u_playlist=m3u_playlist_path, extra_kwargs=results[0].extra_kwargs)
                else:
                    tracks_errored.add(f'{track_info.name} - {track_info.artists[0]}')
                    if ModuleModes.download in self.module_settings[original_service].module_supported_modes:
                        self.service = self.loaded_modules[original_service]
                        self.service_name = original_service
                        self.print(f'Track {track_info.name} not found, using the original service as a fallback', drop_level=1)
                        self.download_track(track_id, album_location=playlist_path, track_index=index, number_of_tracks=number_of_tracks, indent_level=2, m3u_playlist=m3u_playlist_path, extra_kwargs=playlist_info.track_extra_kwargs)
                    else:
                        self.print(f'Track {track_info.name} not found, skipping')
        else:
            for index, track_id_or_info in enumerate(playlist_info.tracks, start=1):
                self.set_indent_number(2)
                print() # Add spacing between track attempts
                self.print(f'Track {index}/{number_of_tracks} (Pass 1)', drop_level=1)
                
                # Determine the actual track ID string to use for download_track
                actual_track_id_str_for_download = track_id_or_info.id if isinstance(track_id_or_info, TrackInfo) else str(track_id_or_info)
                
                download_result = self.download_track(
                    actual_track_id_str_for_download, 
                    album_location=playlist_path, 
                    track_index=index, 
                    number_of_tracks=number_of_tracks, 
                    indent_level=2, 
                    m3u_playlist=m3u_playlist_path, 
                    extra_kwargs=playlist_info.track_extra_kwargs
                )
                
                if download_result == "RATE_LIMITED":
                    logging.info(f"Deferring track {actual_track_id_str_for_download} due to rate limit.")
                    rate_limited_tracks.append({
                        'id': actual_track_id_str_for_download, # Store the string ID
                        'extra_kwargs': playlist_info.track_extra_kwargs,
                        'original_index': index
                    })
                elif m3u_playlist_path: # Add to M3U only if download didn't fail/get deferred
                    # Need to get track_info again or ensure download_track provides location
                    # This part needs refinement - how to get track_location if download succeeds?
                    # For now, assume download_track handles its own M3U addition upon success if needed.
                    pass 

        # --- Second Pass for Rate-Limited Tracks --- 
        if rate_limited_tracks:
            self.set_indent_number(1)
            print() # Spacing
            self.print(f"--- Retrying {len(rate_limited_tracks)} rate-limited tracks ---", drop_level=1)
            for retry_item in rate_limited_tracks:
                self.set_indent_number(2)
                print() # Spacing
                self.print(f'Track {retry_item["original_index"]}/{number_of_tracks} (Retry Pass)', drop_level=1)
                # retry_item['id'] is already a string ID
                self.download_track(
                    retry_item['id'],
                    album_location=playlist_path, 
                    track_index=retry_item["original_index"],
                    number_of_tracks=number_of_tracks, 
                    indent_level=2, 
                    m3u_playlist=m3u_playlist_path, # Pass M3U path again
                    extra_kwargs=retry_item['extra_kwargs']
                )
                # Note: M3U handling for retried tracks still needs consideration
        else:
             self.print("No tracks were deferred due to rate limiting.")

        # --- Final Summary --- 
        self.set_indent_number(1)
        self.print(f'=== Playlist {playlist_info.name} processing complete ===', drop_level=1)
        if tracks_errored: logging.debug('Permanently failed tracks (non-rate-limit): ' + ', '.join(tracks_errored))

    @staticmethod
    def _get_artist_initials_from_name(album_info: AlbumInfo) -> str:
        # Remove "the" from the inital string
        initial = album_info.artist.lower()
        if album_info.artist.lower().startswith('the'):
            initial = initial.replace('the ', '')[0].upper()

        # Unicode fix
        initial = unicodedata.normalize('NFKD', initial[0]).encode('ascii', 'ignore').decode('utf-8')

        # Make the initial upper if it's alpha
        initial = initial.upper() if initial.isalpha() else '#'

        return initial

    def _create_album_location(self, path: str, album_id: str, album_info: AlbumInfo) -> str:
        # Clean up album tags and add special explicit and additional formats
        album_tags = {k: sanitise_name(v) for k, v in asdict(album_info).items()}
        album_tags['id'] = str(album_id)
        album_tags['quality'] = f' [{album_info.quality}]' if album_info.quality else ''
        album_tags['explicit'] = ' [E]' if album_info.explicit else ''
        album_tags['artist_initials'] = self._get_artist_initials_from_name(album_info)

        # album_path = path + self.global_settings['formatting']['album_format'].format(**album_tags) # OLD
        album_path_formatted_name = self.global_settings['formatting']['album_format'].format(**album_tags)
        album_path = os.path.join(path, album_path_formatted_name)
        # fix path byte limit
        album_path = fix_byte_limit(album_path) + '/'
        os.makedirs(album_path, exist_ok=True)

        return album_path

    def _download_album_files(self, album_path: str, album_info: AlbumInfo):
        if album_info.cover_url and self.global_settings['covers']['save_external']:
            download_file(album_info.cover_url, f'{album_path}cover.{album_info.cover_type.name}', artwork_settings=self._get_artwork_settings())

        if album_info.animated_cover_url and self.global_settings['covers']['save_animated_cover']:
            self.print('Downloading animated album cover')
            download_file(album_info.animated_cover_url, album_path + 'cover.mp4', enable_progress_bar=True)

        if album_info.description:
            with open(album_path + 'description.txt', 'w', encoding='utf-8') as f:
                f.write(album_info.description)  # Also add support for this with singles maybe?

    def download_album(self, album_id, artist_name='', path=None, indent_level=1, extra_kwargs=None):
        self.set_indent_number(indent_level)

        service_name_lower = ""
        if hasattr(self, 'service_name') and self.service_name:
            service_name_lower = self.service_name.lower()

        if service_name_lower == 'spotify':
            spotify_kwargs = {}
            if extra_kwargs:
                spotify_kwargs.update(extra_kwargs)
            album_info: AlbumInfo = self.service.get_album_info(album_id, **spotify_kwargs)
        elif service_name_lower == 'soundcloud':
            soundcloud_data_payload = None
            if extra_kwargs and 'data' in extra_kwargs:
                soundcloud_data_payload = extra_kwargs['data']
                logging.debug(f"SoundCloud (album_id: {album_id}): Extracted 'data' from extra_kwargs to pass to get_album_info.")
            else:
                logging.warning(f"SoundCloud (album_id: {album_id}): extra_kwargs missing or malformed. Passing None as data to get_album_info, which may cause errors in the unmodified SoundCloud module.")
            album_info: AlbumInfo = self.service.get_album_info(album_id, data=soundcloud_data_payload)
        elif service_name_lower == 'qobuz':
            qobuz_kwargs = {}
            if extra_kwargs:
                qobuz_kwargs.update(extra_kwargs)
            album_info: AlbumInfo = self.service.get_album_info(album_id, **qobuz_kwargs)
        else:
            # For other non-Spotify, non-SoundCloud, non-Qobuz services
            album_info: AlbumInfo = self.service.get_album_info(album_id, data=extra_kwargs)

        if not album_info:
            logging.warning(f"Could not retrieve album info for {album_id} from {self.service_name}. Skipping album.")
            return []
        
        number_of_tracks = len(album_info.tracks)
        path = self.path if not path else path

        if number_of_tracks > 1 or self.global_settings['formatting']['force_album_format']:
            # Creates the album_location folders
            album_path = self._create_album_location(path, album_id, album_info)
        
            if self.download_mode is DownloadTypeEnum.album:
                self.set_indent_number(1)
            elif self.download_mode is DownloadTypeEnum.artist:
                self.set_indent_number(2)

            self.print(f'=== Downloading album {album_info.name} ({album_id}) ===', drop_level=1)
            self.print(f'Artist: {album_info.artist} ({album_info.artist_id})')
            if album_info.release_year: self.print(f'Year: {album_info.release_year}')
            if album_info.duration: self.print(f'Duration: {beauty_format_seconds(album_info.duration)}')
            self.print(f'Number of tracks: {number_of_tracks!s}')
            self.print(f'Platform: {self.module_settings[self.service_name].service_name}')

            if album_info.booklet_url and not os.path.exists(album_path + 'Booklet.pdf'):
                self.print('Downloading booklet')
                download_file(album_info.booklet_url, album_path + 'Booklet.pdf')
            
            cover_temp_location = download_to_temp(album_info.all_track_cover_jpg_url) if album_info.all_track_cover_jpg_url else ''

            # Download booklet, animated album cover and album cover if present
            self._download_album_files(album_path, album_info)

            for index, track_item in enumerate(album_info.tracks, start=1):
                self.set_indent_number(indent_level + 1)
                print()
                self.print(f'Track {index}/{number_of_tracks}', drop_level=1)
                track_id_to_download = track_item.id if hasattr(track_item, 'id') else track_item # Check for .id attribute
                self.download_track(track_id_to_download, album_location=album_path, track_index=index, number_of_tracks=number_of_tracks, main_artist=artist_name, cover_temp_location=cover_temp_location, indent_level=indent_level+1, extra_kwargs=album_info.track_extra_kwargs)

            self.set_indent_number(indent_level)
            self.print(f'=== Album {album_info.name} downloaded ===', drop_level=1)
            if cover_temp_location: silentremove(cover_temp_location)
        elif number_of_tracks == 1:
            single_track_item = album_info.tracks[0]
            track_id_to_download = single_track_item.id if hasattr(single_track_item, 'id') else single_track_item # Check for .id attribute
            self.download_track(track_id_to_download, album_location=path, number_of_tracks=1, main_artist=artist_name, indent_level=indent_level, extra_kwargs=album_info.track_extra_kwargs)

        return album_info.tracks

    def download_artist(self, artist_id, extra_kwargs=None):        
        # Start with a copy of extra_kwargs if provided, or an empty dict
        prepared_kwargs = {} 
        if extra_kwargs:
            prepared_kwargs.update(extra_kwargs)

        service_name_lower = ""
        if hasattr(self, 'service_name') and self.service_name:
            service_name_lower = self.service_name.lower()

        # Specific kwarg handling for Beatport/Beatsource for the 'data' key
        if service_name_lower in ['beatport', 'beatsource']:
            if 'data' in prepared_kwargs:
                logging.debug(f"Popping 'data' kwarg for {self.service_name}.get_artist_info as it is unexpected.")
                prepared_kwargs.pop('data', None)

        # Determine the value for fetching credited albums from global settings        
        fetch_credited_albums_value = False
        if (
            'artist_downloading' in self.global_settings and
            isinstance(self.global_settings['artist_downloading'], dict) and
            'return_credited_albums' in self.global_settings['artist_downloading']
        ):
            fetch_credited_albums_value = self.global_settings['artist_downloading']['return_credited_albums']

        # Call get_artist_info based on service-specific signature requirements
        try:
            if service_name_lower in ['deezer', 'qobuz', 'soundcloud', 'tidal', 'beatport', 'beatsource']:
                # These services require 'get_credited_albums' (the boolean value) as the second positional argument.            
                artist_info: ArtistInfo = self.service.get_artist_info(artist_id, fetch_credited_albums_value, **prepared_kwargs)
            elif service_name_lower == 'spotify':
                # Spotify handles 'return_credited_albums' as a keyword argument.
                prepared_kwargs['return_credited_albums'] = fetch_credited_albums_value
                artist_info: ArtistInfo = self.service.get_artist_info(artist_id, **prepared_kwargs)
            else:
                # For any other unhandled services.
                # Assume they don't need 'get_credited_albums' positionally or as a specific keyword.
                # This branch may need refinement if other services show different signature needs.
                artist_info: ArtistInfo = self.service.get_artist_info(artist_id, **prepared_kwargs)
        except Exception as e:
            self.print(f"Failed to retrieve artist info for ID {artist_id}: {e}", drop_level=1)
            self.print(f"=== Artist {artist_id} failed ===", drop_level=1)
            return

        artist_name = artist_info.name

        self.set_indent_number(1)

        number_of_albums = len(artist_info.albums)
        number_of_tracks = len(artist_info.tracks)

        self.print(f'=== Downloading artist {artist_name} ({artist_id}) ===', drop_level=1)
        if number_of_albums: self.print(f'Number of albums: {number_of_albums!s}')
        if number_of_tracks: self.print(f'Number of tracks: {number_of_tracks!s}')
        self.print(f'Platform: {self.module_settings[self.service_name].service_name}')
        artist_path = os.path.join(self.path, sanitise_name(artist_name)) + '/'

        self.set_indent_number(2)
        tracks_downloaded = []
        for index, album_item in enumerate(artist_info.albums, start=1):
            print()
            self.print(f'Album {index}/{number_of_albums}', drop_level=1)

            album_id_to_process = None
            # Check if album_item is a string (like for Tidal)
            if isinstance(album_item, str):
                album_id_to_process = album_item
            # Check if album_item is a dictionary with an 'id' key (like for Spotify)
            elif isinstance(album_item, dict) and 'id' in album_item and isinstance(album_item['id'], str):
                album_id_to_process = album_item['id']
            # Check if album_item is an object with an 'id' attribute (more generic)
            elif hasattr(album_item, 'id') and isinstance(getattr(album_item, 'id', None), str):
                 album_id_to_process = album_item.id # type: ignore
            else:
                self.print(f"Skipping unrecognized album item in artist_info.albums: {album_item}", drop_level=1)
                continue
            
            tracks_downloaded += self.download_album(
                album_id_to_process, # This is now guaranteed to be a string ID
                artist_name=artist_name,
                path=artist_path,
                indent_level=2,
                extra_kwargs=artist_info.album_extra_kwargs # General extra_kwargs from artist level
            )

        self.set_indent_number(2)
        skip_tracks = self.global_settings['artist_downloading']['separate_tracks_skip_downloaded']
        tracks_to_download = [i for i in artist_info.tracks if (i not in tracks_downloaded and skip_tracks) or not skip_tracks]
        number_of_tracks_new = len(tracks_to_download)
        for index, track_id in enumerate(tracks_to_download, start=1):
            print()
            self.print(f'Track {index}/{number_of_tracks_new}', drop_level=1)
            self.download_track(track_id, album_location=artist_path, main_artist=artist_name, number_of_tracks=1, indent_level=2, extra_kwargs=artist_info.track_extra_kwargs)

        self.set_indent_number(1)
        tracks_skipped = number_of_tracks - number_of_tracks_new
        if tracks_skipped > 0: self.print(f'Tracks skipped: {tracks_skipped!s}', drop_level=1)
        self.print(f'=== Artist {artist_name} downloaded ===', drop_level=1)

    def download_track(self, track_id, album_location='', main_artist='', track_index=0, number_of_tracks=0, cover_temp_location='', indent_level=1, m3u_playlist=None, extra_kwargs={}):
        quality_tier = QualityEnum[self.global_settings['general']['download_quality'].upper()]
        codec_options = CodecOptions(
            spatial_codecs = self.global_settings['codecs']['spatial_codecs'],
            proprietary_codecs = self.global_settings['codecs']['proprietary_codecs'],
        )
        
        if self.service_name.lower() == 'tidal':
            try:
                track_info: TrackInfo = self.service.get_track_info(track_id, quality_tier, codec_options, data=extra_kwargs)
            except Exception as e:
                if 'TidalError' in e.__class__.__name__ or 'region' in str(e).lower():
                    self.print(f"\nError: Could not retrieve information for Tidal track {track_id}", drop_level=1)
                    self.print(f"Cause: {e}", drop_level=1)
                    self.print(f'=== ❌ Track failed ===\n', drop_level=1)
                    return
                else:
                    raise
        else:
            track_info: TrackInfo = self.service.get_track_info(track_id, quality_tier, codec_options, **extra_kwargs)
        
        if track_info is None:
            # Determine the simple string ID from the input argument
            failed_id_str = None
            if isinstance(track_id, str): # If the input was already a string ID
                failed_id_str = track_id 
            elif hasattr(track_id, 'download_extra_kwargs') and 'track_id' in track_id.download_extra_kwargs:
                # If input was TrackInfo object, get ID from its kwargs
                failed_id_str = track_id.download_extra_kwargs['track_id']
            else:
                # Fallback: convert the original input to string (might still be TrackInfo obj)
                failed_id_str = str(track_id) 
                
            self.oprinter.oprint(f"Skipping track ID {failed_id_str}: Could not retrieve track information (likely unavailable).", drop_level=1)
            logging.warning(f"Skipping track ID {failed_id_str}: get_track_info returned None.")
            return

        if main_artist.lower() not in [i.lower() for i in track_info.artists] and self.global_settings['advanced']['ignore_different_artists'] and self.download_mode is DownloadTypeEnum.artist:
           self.print('Track is not from the correct artist, skipping', drop_level=1)
           return

        if not self.global_settings['formatting']['force_album_format']:
            if track_index:
                track_info.tags.track_number = track_index
            if number_of_tracks:
                track_info.tags.total_tracks = number_of_tracks
        zfill_number = len(str(track_info.tags.total_tracks)) if self.download_mode is not DownloadTypeEnum.track else 1
        zfill_lambda = lambda input : sanitise_name(str(input)).zfill(zfill_number) if input is not None else None

        # Separate copy of tags for formatting purposes
        zfill_enabled, zfill_list = self.global_settings['formatting']['enable_zfill'], ['track_number', 'total_tracks', 'disc_number', 'total_discs']
        track_tags = {k: (zfill_lambda(v) if zfill_enabled and k in zfill_list else sanitise_name(v)) for k, v in {**asdict(track_info.tags), **asdict(track_info)}.items()}
        track_tags['explicit'] = ' [E]' if track_info.explicit else ''
        track_tags['artist'] = sanitise_name(track_info.artists[0])  # if len(track_info.artists) == 1 else 'Various Artists'
        codec = track_info.codec

        self.set_indent_number(indent_level)
        # Extract the string ID reliably from track_info if possible
        actual_id_str = track_info.download_extra_kwargs.get('track_id', str(track_id)) 
        self.oprinter.oprint("")  # Add blank line before track download message
        self.print(f'=== Downloading track {track_info.name} ({actual_id_str}) ===', drop_level=1)

        if self.download_mode is not DownloadTypeEnum.album and track_info.album: self.print(f'Album: {track_info.album} ({track_info.album_id})')
        if self.download_mode is not DownloadTypeEnum.artist: self.print(f'Artists: {", ".join(track_info.artists)} ({track_info.artist_id})')
        if track_info.release_year: self.print(f'Release year: {track_info.release_year!s}')
        if track_info.duration: self.print(f'Duration: {beauty_format_seconds(track_info.duration)}')
        self.print(f'Platform: {self.module_settings[self.service_name].service_name}')

        to_print = 'Codec: ' + codec_data[codec].pretty_name
        if track_info.bitrate: 
            to_print += f', bitrate: {track_info.bitrate!s}kbps'
        elif self.service_name.lower() == 'spotify' and codec.name.lower() == 'vorbis':
            # Fallback for Spotify Vorbis when bitrate isn't provided
            high_quality_tiers = ['VERY_HIGH', 'LOSSLESS', 'HIFI', 'HIGH']
            spotify_bitrate = 320 if quality_tier.name in high_quality_tiers else 160
            to_print += f', bitrate: {spotify_bitrate}kbps'
        if track_info.bit_depth: to_print += f', bit depth: {track_info.bit_depth!s}bit'
        if track_info.sample_rate: to_print += f', sample rate: {track_info.sample_rate!s}kHz'
        self.print(to_print)

        # Check if track_info returns error, display it and return this function to not download the track
        if track_info.error:
            self.print(track_info.error)
            self.print(f'=== Track {track_id} failed ===', drop_level=1)
            return

        album_location = album_location.replace('\\', '/')

        # Ignores "single_full_path_format" and just downloads every track as an album
        if self.global_settings['formatting']['force_album_format'] and self.download_mode in {
            DownloadTypeEnum.track, DownloadTypeEnum.playlist}:
            # Fetch every needed album_info tag and create an album_location
            album_info: AlbumInfo
            if self.service_name in ['soundcloud', 'deezer']: # Check if it's SoundCloud or Deezer
                album_info = self.service.get_album_info(track_info.album_id, data={}) # Pass data={}
            else:
                album_info = self.service.get_album_info(track_info.album_id)
            
            if album_info: # Only proceed if album_info was successfully fetched
                # Save the playlist path to save all the albums in the playlist path
                path_for_album = self.path if album_location == '' else album_location
                new_album_location = self._create_album_location(path_for_album, track_info.album_id, album_info)
                new_album_location = new_album_location.replace('\\', '/')
                # Download booklet, animated album cover and album cover if present
                self._download_album_files(new_album_location, album_info)
                # Update album_location to the new path if it was created
                album_location = new_album_location 
            else:
                # If album_info is None, use the existing album_location (which might be just self.path or a playlist path)
                # or ensure album_location is set to a sensible default if it was empty.
                if not album_location: # If album_location was empty (e.g. direct track download, not part of playlist)
                    album_location = self.path
                self.oprinter.oprint(f"[Music Downloader] force_album_format is ON, but no valid album_info found for track {track_id} (album_id: '{track_info.album_id}'). Using path: {album_location}", drop_level=1)

        if self.download_mode is DownloadTypeEnum.track and not self.global_settings['formatting']['force_album_format']:  # Python 3.10 can't become popular sooner, ugh
            track_location_name = os.path.join(self.path, self.global_settings['formatting']['single_full_path_format'].format(**track_tags))
        elif track_info.tags.total_tracks == 1 and not self.global_settings['formatting']['force_album_format']:
            track_location_name = os.path.join(album_location, self.global_settings['formatting']['single_full_path_format'].format(**track_tags))
        else:
            if track_info.tags.total_discs and track_info.tags.total_discs > 1: 
                album_location = os.path.join(album_location, f'CD {track_info.tags.disc_number!s}')
            track_location_name = os.path.join(album_location, self.global_settings['formatting']['track_filename_format'].format(**track_tags))
        # fix file byte limit
        track_location_name = fix_byte_limit(track_location_name)
        track_directory = os.path.dirname(track_location_name)
        if track_directory:
            os.makedirs(track_directory, exist_ok=True)

        try:
            conversions = {CodecEnum[k.upper()]: CodecEnum[v.upper()] for k, v in self.global_settings['advanced']['codec_conversions'].items()}
        except:
            conversions = {}
            self.print('Warning: codec_conversions setting is invalid!')
        
        container = codec_data[codec].container
        track_location = f'{track_location_name}.{container.name}'

        check_codec = conversions[track_info.codec] if track_info.codec in conversions else track_info.codec
        check_location = f'{track_location_name}.{codec_data[check_codec].container.name}'

        if os.path.isfile(check_location) and not self.global_settings['advanced']['ignore_existing_files']:
            self.print('Track file already exists')

            # also make sure to add already existing tracks to the m3u playlist
            if m3u_playlist:
                self._add_track_m3u_playlist(m3u_playlist, track_info, track_location)

            self.print(f'=== Track {actual_id_str} skipped ===', drop_level=1)
            return

        if track_info.description:
            with open(track_location_name + '.txt', 'w', encoding='utf-8') as f: f.write(track_info.description)

        # Begin process
        self.print("Downloading audio...")
        max_retries = 3  # Number of retries for non-rate-limit errors
        retry_delay = 2  # Delay between retries in seconds
        
        download_info = None
        for attempt in range(max_retries):
            try:
                id_to_pass_to_module = actual_id_str
                if self.service_name.lower() == 'spotify':
                    if hasattr(track_info, 'gid_hex') and track_info.gid_hex:
                        id_to_pass_to_module = track_info.gid_hex
                    else:
                        # This case should ideally not be hit if get_track_info populates gid_hex correctly
                        self.oprinter.oprint(f"Warning: Spotify track_info for {actual_id_str} is missing gid_hex. Attempting to use original ID. Download may fail.", drop_level=1)
                        # If gid_hex is critical and missing, an error might be preferable here
                        # For now, it will proceed with actual_id_str which might be Base62

                kwargs_for_download = {
                    "track_id_str": id_to_pass_to_module, # Use the potentially adjusted ID
                    "track_info_obj": track_info, # The full TrackInfo object
                    "quality_tier": quality_tier,
                    "codec_options": codec_options,
                    **extra_kwargs, # from download_track's parameters
                    **track_info.download_extra_kwargs # from track_info itself
                }

                service_name_lower = self.service_name.lower()
                if service_name_lower == 'tidal':
                    tidal_args = {}
                    if 'file_url' in kwargs_for_download:
                        tidal_args['file_url'] = kwargs_for_download['file_url']
                    if 'audio_track' in kwargs_for_download:
                        tidal_args['audio_track'] = kwargs_for_download['audio_track']
                    # Tidal might also need quality_tier, ensure it's passed if its interface uses it.
                    # For now, assuming only file_url or audio_track as per previous fixes.
                    download_info: TrackDownloadInfo = self.service.get_track_download(**tidal_args)
                elif service_name_lower in ('beatport', 'beatsource'):
                    # Beatport and Beatsource expect track_id and quality_tier positionally or as named args
                    download_info: TrackDownloadInfo = self.service.get_track_download(
                        track_id=kwargs_for_download["track_id_str"],
                        quality_tier=kwargs_for_download["quality_tier"]
                    )
                elif service_name_lower == 'deezer':
                    # Deezer expects id, track_token, track_token_expiry, format
                    # These are in track_info_obj.download_extra_kwargs
                    track_info_obj = kwargs_for_download.get("track_info_obj")
                    if track_info_obj and hasattr(track_info_obj, 'download_extra_kwargs') and isinstance(track_info_obj.download_extra_kwargs, dict):
                        deezer_args = track_info_obj.download_extra_kwargs
                        # Ensure all required keys are present before calling
                        if all(k in deezer_args for k in ['id', 'track_token', 'track_token_expiry', 'format']):
                            download_info: TrackDownloadInfo = self.service.get_track_download(
                                id=deezer_args['id'],
                                track_token=deezer_args['track_token'],
                                track_token_expiry=deezer_args['track_token_expiry'],
                                format=deezer_args['format']
                            )
                        else:
                            logging.error(f"Deezer: Missing required arguments in download_extra_kwargs for track {kwargs_for_download.get('track_id_str')}. Args: {deezer_args}")
                            download_info = None # Ensure download_info is None if call fails
                    else:
                        logging.error(f"Deezer: track_info_obj or its download_extra_kwargs are missing/invalid for track {kwargs_for_download.get('track_id_str')}.")
                        download_info = None # Ensure download_info is None
                elif service_name_lower == 'qobuz':
                    # Qobuz expects only the 'url'
                    track_info_obj = kwargs_for_download.get("track_info_obj")
                    if track_info_obj and hasattr(track_info_obj, 'download_extra_kwargs') and isinstance(track_info_obj.download_extra_kwargs, dict):
                        qobuz_dl_url = track_info_obj.download_extra_kwargs.get('url')
                        if qobuz_dl_url:
                            download_info: TrackDownloadInfo = self.service.get_track_download(url=qobuz_dl_url)
                        else:
                            logging.error(f"Qobuz: Missing 'url' in download_extra_kwargs for track {kwargs_for_download.get('track_id_str')}. Args: {track_info_obj.download_extra_kwargs}")
                            download_info = None
                    else:
                        logging.error(f"Qobuz: track_info_obj or its download_extra_kwargs are missing/invalid for track {kwargs_for_download.get('track_id_str')}.")
                        download_info = None
                elif service_name_lower == 'soundcloud':
                    # SoundCloud expects track_url, download_url, codec, track_authorization
                    track_info_obj = kwargs_for_download.get("track_info_obj")
                    if track_info_obj and hasattr(track_info_obj, 'download_extra_kwargs') and isinstance(track_info_obj.download_extra_kwargs, dict):
                        soundcloud_args = track_info_obj.download_extra_kwargs
                        # Ensure all required keys are present before calling
                        required_soundcloud_keys = ['track_url', 'download_url', 'codec', 'track_authorization']
                        if all(k in soundcloud_args for k in required_soundcloud_keys):
                            download_info: TrackDownloadInfo = self.service.get_track_download(
                                track_url=soundcloud_args['track_url'],
                                download_url=soundcloud_args['download_url'],
                                codec=soundcloud_args['codec'],
                                track_authorization=soundcloud_args['track_authorization']
                            )
                        else:
                            # It's possible that download_url is None for streamable tracks, module should handle it
                            if all(k in soundcloud_args for k in ['track_url', 'codec', 'track_authorization']):
                                download_info: TrackDownloadInfo = self.service.get_track_download(
                                    track_url=soundcloud_args['track_url'],
                                    download_url=soundcloud_args.get('download_url'), # Can be None
                                    codec=soundcloud_args['codec'],
                                    track_authorization=soundcloud_args['track_authorization']
                                )
                            else:
                                logging.error(f"SoundCloud: Missing required arguments in download_extra_kwargs for track {kwargs_for_download.get('track_id_str')}. Args: {soundcloud_args}")
                                download_info = None # Ensure download_info is None if call fails
                    else:
                        logging.error(f"SoundCloud: track_info_obj or its download_extra_kwargs are missing/invalid for track {kwargs_for_download.get('track_id_str')}.")
                        download_info = None # Ensure download_info is None
                elif service_name_lower == 'jiosaavn':
                    track_info_obj = kwargs_for_download.get("track_info_obj")
                    if track_info_obj and hasattr(track_info_obj, 'download_extra_kwargs') and isinstance(track_info_obj.download_extra_kwargs, dict):
                        file_url = track_info_obj.download_extra_kwargs.get('file_url')
                        codec = track_info_obj.download_extra_kwargs.get('codec') # Jiosaavn module expects this
                        if file_url and codec:
                            download_info: TrackDownloadInfo = self.service.get_track_download(file_url=file_url, codec=codec)
                        else:
                            logging.error(f"Jiosaavn: Missing 'file_url' or 'codec' in download_extra_kwargs for track {kwargs_for_download.get('track_id_str')}. Args: {track_info_obj.download_extra_kwargs}")
                            download_info = None
                    else:
                        logging.error(f"Jiosaavn: track_info_obj or its download_extra_kwargs are missing/invalid for track {kwargs_for_download.get('track_id_str')}.")
                        download_info = None
                elif service_name_lower == 'applemusic': # Added Apple Music specific handling
                    download_info: TrackDownloadInfo = self.service.get_track_download(
                        track_id=kwargs_for_download["track_id_str"],
                        quality_tier=kwargs_for_download["quality_tier"],
                        # Pass other relevant kwargs if Apple Music module uses them via **kwargs
                        # For now, only explicit ones. The rest of kwargs_for_download 
                        # are implicitly ignored by this specific call if not in AM's **kwargs.
                        # If AM module needs more from kwargs_for_download, they should be added here or AM's **kwargs used.
                    )
                else: # For Spotify and other modules that might accept **kwargs or the specific new ones
                    download_info: TrackDownloadInfo = self.service.get_track_download(
                        **kwargs_for_download
                    )

                if download_info is not None:
                    break
                else:
                    if attempt < max_retries - 1:
                        logging.warning(f"Track download attempt {attempt + 1} failed for {actual_id_str}. Retrying in {retry_delay} seconds...")
                        self.print(f"Download attempt {attempt + 1} failed. Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
            except SpotifyRateLimitDetectedError:
                self.print("Track deferred due to detected rate limit.")
                logging.warning(f"Track {actual_id_str} deferred due to Spotify rate limit.")
                return "RATE_LIMITED"
            except TrackUnavailableError as e:
                self.print(f"{e}", drop_level=1)
                self.print(f'=== Track {actual_id_str} failed (Unavailable) ===', drop_level=1)
                return # Exit the function to prevent further processing
            except Exception as e:
                if attempt < max_retries - 1:
                    logging.warning(f"Track download attempt {attempt + 1} failed for {actual_id_str} with error: {str(e)}. Retrying in {retry_delay} seconds...")
                    self.print(f"Download attempt {attempt + 1} failed. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
        
        # CRITICAL FIX: Check download_info AFTER the loop and before proceeding
        if download_info is None:
            logging.error(f"Track download failed for {actual_id_str}: Module get_track_download returned None after {max_retries} attempts or due to an unhandled exception during retries.")
            self.print(f'=== Track {actual_id_str} failed (Could not retrieve download data) ===', drop_level=1)
            return

        download_file(download_info.file_url, track_location, headers=download_info.file_url_headers, enable_progress_bar=True, indent_level=self.oprinter.indent_number) \
            if download_info.download_type is DownloadEnum.URL else shutil.move(download_info.temp_file_path, track_location)

        # check if get_track_download returns a different codec, for example ffmpeg failed
        if download_info.different_codec:
            # overwrite the old known codec with the new
            codec = download_info.different_codec
            container = codec_data[codec].container
            old_track_location = track_location
            # create the new track_location and move the old file to the new location
            track_location = f'{track_location_name}.{container.name}'
            shutil.move(old_track_location, track_location)

        delete_cover = False
        if not cover_temp_location:
            cover_temp_location = self.create_temp_filename()
            delete_cover = True
            covers_module_name = self.third_party_modules[ModuleModes.covers]
            covers_module_name = covers_module_name if covers_module_name != self.service_name else None
            if covers_module_name: print()
            self.print('Downloading artwork...' + ((' with ' + covers_module_name) if covers_module_name else ''))
            
            jpg_cover_options = CoverOptions(file_type=ImageFileTypeEnum.jpg, resolution=self.global_settings['covers']['main_resolution'], \
                compression=CoverCompressionEnum[self.global_settings['covers']['main_compression'].lower()])
            ext_cover_options = CoverOptions(file_type=ImageFileTypeEnum[self.global_settings['covers']['external_format']], \
                resolution=self.global_settings['covers']['external_resolution'], \
                compression=CoverCompressionEnum[self.global_settings['covers']['external_compression'].lower()])
            
            if covers_module_name:
                default_temp = download_to_temp(track_info.cover_url)
                test_cover_options = CoverOptions(file_type=ImageFileTypeEnum.jpg, resolution=get_image_resolution(default_temp), compression=CoverCompressionEnum.high)
                cover_module = self.loaded_modules[covers_module_name]
                rms_threshold = self.global_settings['advanced']['cover_variance_threshold']

                results: list[SearchResult] = self.search_by_tags(covers_module_name, track_info)
                self.print('Covers to test: ' + str(len(results)))
                attempted_urls = []
                for i, r in enumerate(results, start=1):
                    test_cover_info: CoverInfo = cover_module.get_track_cover(r.result_id, test_cover_options, **r.extra_kwargs)
                    if test_cover_info.url not in attempted_urls:
                        attempted_urls.append(test_cover_info.url)
                        test_temp = download_to_temp(test_cover_info.url)
                        rms = compare_images(default_temp, test_temp)
                        silentremove(test_temp)
                        self.print(f'Attempt {i} RMS: {rms!s}')
                        if rms < rms_threshold:
                            self.print('Match found below threshold ' + str(rms_threshold))
                            jpg_cover_info: CoverInfo = cover_module.get_track_cover(r.result_id, jpg_cover_options, **r.extra_kwargs)
                            if jpg_cover_info:
                                download_file(jpg_cover_info.url, cover_temp_location, artwork_settings=self._get_artwork_settings(covers_module_name))
                                silentremove(default_temp)
                                if self.global_settings['covers']['save_external']:
                                    ext_cover_info: CoverInfo = cover_module.get_track_cover(r.result_id, ext_cover_options, **r.extra_kwargs)
                                    if ext_cover_info:
                                        download_file(ext_cover_info.url, f'{track_location_name}.{ext_cover_info.file_type.name}', artwork_settings=self._get_artwork_settings(covers_module_name, is_external=True))
                            break
                else:
                    self.print('Third-party module could not find cover, using fallback')
                    shutil.move(default_temp, cover_temp_location)
            else:
                download_file(track_info.cover_url, cover_temp_location, artwork_settings=self._get_artwork_settings())
                if self.global_settings['covers']['save_external'] and ModuleModes.covers in self.module_settings[self.service_name].module_supported_modes:
                    ext_cover_info: CoverInfo = self.service.get_track_cover(track_id, ext_cover_options, **track_info.cover_extra_kwargs)
                    if ext_cover_info:
                        download_file(ext_cover_info.url, f'{track_location_name}.{ext_cover_info.file_type.name}', artwork_settings=self._get_artwork_settings(is_external=True))

        if track_info.animated_cover_url and self.global_settings['covers']['save_animated_cover']:
            self.print('Downloading animated cover')
            download_file(track_info.animated_cover_url, track_location_name + '_cover.mp4', enable_progress_bar=True)

        # Get lyrics
        embedded_lyrics = ''
        if self.global_settings['lyrics']['embed_lyrics'] or self.global_settings['lyrics']['save_synced_lyrics']:
            lyrics_info = LyricsInfo()
            if self.third_party_modules[ModuleModes.lyrics] and self.third_party_modules[ModuleModes.lyrics] != self.service_name:
                lyrics_module_name = self.third_party_modules[ModuleModes.lyrics]
                self.print('Retrieving lyrics with ' + lyrics_module_name)
                lyrics_module = self.loaded_modules[lyrics_module_name]

                if lyrics_module_name != self.service_name:
                    results: list[SearchResult] = self.search_by_tags(lyrics_module_name, track_info)
                    lyrics_track_id = results[0].result_id if len(results) else None
                    extra_kwargs = results[0].extra_kwargs if len(results) else None
                else:
                    lyrics_track_id = track_id
                    extra_kwargs = {}
                
                if lyrics_track_id:
                    lyrics_info: LyricsInfo = lyrics_module.get_track_lyrics(lyrics_track_id, **extra_kwargs)
                else:
                    self.print('Lyrics module could not find any lyrics.')
            elif ModuleModes.lyrics in self.module_settings[self.service_name].module_supported_modes:
                lyrics_info: LyricsInfo = self.service.get_track_lyrics(track_id, **track_info.lyrics_extra_kwargs)

            if lyrics_info.embedded and self.global_settings['lyrics']['embed_lyrics']:
                embedded_lyrics = lyrics_info.embedded
            # embed the synced lyrics (f.e. Roon) if they are available
            if lyrics_info.synced and self.global_settings['lyrics']['embed_lyrics'] and \
                    self.global_settings['lyrics']['embed_synced_lyrics']:
                embedded_lyrics = lyrics_info.synced
            if lyrics_info.synced and self.global_settings['lyrics']['save_synced_lyrics']:
                lrc_location = f'{track_location_name}.lrc'
                if not os.path.isfile(lrc_location):
                    with open(lrc_location, 'w', encoding='utf-8') as f:
                        f.write(lyrics_info.synced)

        # Get credits
        credits_list = []
        if self.third_party_modules[ModuleModes.credits] and self.third_party_modules[ModuleModes.credits] != self.service_name:
            credits_module_name = self.third_party_modules[ModuleModes.credits]
            self.print('Retrieving credits with ' + credits_module_name)
            credits_module = self.loaded_modules[credits_module_name]

            if credits_module_name != self.service_name:
                results: list[SearchResult] = self.search_by_tags(credits_module_name, track_info)
                credits_track_id = results[0].result_id if len(results) else None
                extra_kwargs = results[0].extra_kwargs if len(results) else None
            else:
                credits_track_id = track_id
                extra_kwargs = {}
            
            if credits_track_id:
                credits_list = credits_module.get_track_credits(credits_track_id, **extra_kwargs)

        elif ModuleModes.credits in self.module_settings[self.service_name].module_supported_modes:
            self.print('Retrieving credits')
            credits_list = self.service.get_track_credits(track_id, **track_info.credits_extra_kwargs)
        
        # Do conversions
        old_track_location, old_container = None, None
        if codec in conversions:
            old_codec_data = codec_data[codec]
            new_codec = conversions[codec]
            new_codec_data = codec_data[new_codec]

            if codec == new_codec:
                pass
            else:
                self.print(f'Converting to {new_codec_data.pretty_name}...')
                
                if old_codec_data.spatial or new_codec_data.spatial:
                    self.print('Warning: converting spacial formats is not allowed, skipping')
                elif not old_codec_data.lossless and new_codec_data.lossless and not self.global_settings['advanced']['enable_undesirable_conversions']:
                    self.print('Warning: Undesirable lossy-to-lossless conversion detected, skipping')
                elif not old_codec_data and not self.global_settings['advanced']['enable_undesirable_conversions']:
                    self.print('Warning: Undesirable lossy-to-lossy conversion detected, skipping')
                else:
                    if not old_codec_data.lossless and new_codec_data.lossless:
                        self.print('Warning: Undesirable lossy-to-lossless conversion')
                    elif not old_codec_data:
                        self.print('Warning: Undesirable lossy-to-lossy conversion')

                    try:
                        conversion_flags = {CodecEnum[k.upper()]:v for k,v in self.global_settings['advanced']['conversion_flags'].items()}
                    except:
                        conversion_flags = {}
                        self.print('Warning: conversion_flags setting is invalid, using defaults')
                    
                    conv_flags = conversion_flags[new_codec] if new_codec in conversion_flags else {}
                    temp_track_location = f'{self.create_temp_filename()}.{new_codec_data.container.name}'
                    new_track_location = f'{track_location_name}.{new_codec_data.container.name}'
                    
                    stream: ffmpeg = ffmpeg.input(track_location, hide_banner=None, y=None)
                    # capture_stderr is required for the error output to be captured
                    try:
                        # capture_stderr is required for the error output to be captured
                        stream.output(
                            temp_track_location,
                            acodec=new_codec.name.lower(),
                            vn=None,  # Ignore video stream
                            **conv_flags,
                            loglevel='error'
                        ).run(capture_stdout=True, capture_stderr=True)
                    except Error as e:
                        error_msg = e.stderr.decode('utf-8')
                        # get the error message from ffmpeg and search foe the non-experimental encoder
                        encoder = re.search(r"(?<=non experimental encoder ')\[^'\]+", error_msg)
                        if encoder:
                            self.print(f'Encoder {new_codec.name.lower()} is experimental, trying {encoder.group(0)}')
                            # try to use the non-experimental encoder
                            stream.output(
                                temp_track_location,
                                acodec=encoder.group(0),
                                vn=None,  # Ignore video stream here as well
                                **conv_flags,
                                loglevel='error'
                            ).run(capture_stdout=True, capture_stderr=True) # Added capture_stdout/stderr for consistency
                        else:
                            # raise any other occurring error
                            raise Exception(f'ffmpeg error converting to {new_codec.name.lower()}:\n{error_msg}')

                    # remove file if it requires an overwrite, maybe os.replace would work too?
                    if track_location == new_track_location:
                        silentremove(track_location)
                        # just needed so it won't get deleted
                        track_location = temp_track_location

                    # move temp_file to new_track_location and delete temp file
                    shutil.move(temp_track_location, new_track_location)
                    silentremove(temp_track_location)

                    if self.global_settings['advanced']['conversion_keep_original']:
                        old_track_location = track_location
                        old_container = container
                    else:
                        silentremove(track_location)

                    container = new_codec_data.container    
                    track_location = new_track_location

        # Tagging starts here
        self.print('Tagging file...')
        try:
            tag_file(track_location, cover_temp_location if self.global_settings['covers']['embed_cover'] else None,
                     track_info, credits_list, embedded_lyrics, container)
            if old_track_location:
                tag_file(old_track_location, cover_temp_location if self.global_settings['covers']['embed_cover'] else None,
                         track_info, credits_list, embedded_lyrics, old_container)
        except Exception as e:
            # Log the detailed exception
            logging.error(f"Tagging failed for {track_location}. Error: {e}", exc_info=True)
            self.oprinter.oprint("Tagging failed.", drop_level=1)
            self.oprinter.oprint("Saving tags to text file as fallback.", drop_level=1)
            try:
                # Convert track_info dataclass to dict
                track_info_dict = asdict(track_info)
                with open(track_location_name + '_tags.json', 'w', encoding='utf-8') as f:
                    # Use the custom serializer for Enums
                    f.write(json.dumps(track_info_dict, indent=4, default=json_enum_serializer))
            except Exception as log_e:
                 logging.error(f"Could not save fallback tags for {track_location_name}: {log_e}", exc_info=True)
                 self.oprinter.oprint("Failed to save fallback tag file.", drop_level=1)

        # m3u playlist stuff
        if m3u_playlist:
            self._add_track_m3u_playlist(m3u_playlist, track_info, track_location)

        self.print(f'=== Track {actual_id_str} downloaded ===', drop_level=1)
        
        # Pause AFTER track download is fully complete, if the module specifies a pause duration
        pause_seconds = 0
        # Check if self.service (the module interface instance) exists and has access to its settings
        if self.service and hasattr(self.service, 'settings') and isinstance(self.service.settings, dict):
            # Try to get module-specific pause setting
            pause_seconds = self.service.settings.get('download_pause_seconds', 0)
            # Ensure it's an integer
            try:
                pause_seconds = int(pause_seconds)
            except (ValueError, TypeError):
                logging.warning(f"Invalid non-integer value for download_pause_seconds in {self.service_name} settings: {pause_seconds}. Defaulting to 30.")
                pause_seconds = 30
        
        # Pause if service is spotify AND pause > 0 AND (part of multi-track download OR downloading artist tracks)
        if pause_seconds > 0 and self.service_name == 'spotify' and (number_of_tracks > 1 or self.download_mode is DownloadTypeEnum.artist):            
            self.oprinter.oprint(f"Pausing for {pause_seconds} seconds before next download attempt (to avoid rate limiting)...")
            time.sleep(pause_seconds)        

    def _get_artwork_settings(self, module_name = None, is_external = False):
        if not module_name:
            module_name = self.service_name
        return {
            'should_resize': ModuleFlags.needs_cover_resize in self.module_settings[module_name].flags,
            'resolution': self.global_settings['covers']['external_resolution'] if is_external else self.global_settings['covers']['main_resolution'],
            'compression': self.global_settings['covers']['external_compression'] if is_external else self.global_settings['covers']['main_compression'],
            'format': self.global_settings['covers']['external_format'] if is_external else 'jpg'
        }