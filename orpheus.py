#!/usr/bin/env python3
import os
os.environ['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION'] = 'python'

import argparse
import re
import json
from urllib.parse import urlparse
from orpheus.core import *
from orpheus.music_downloader import beauty_format_seconds
# try:
#     from modules.spotify.spotify_api import SpotifyAuthError, SpotifyRateLimitDetectedError
# except ModuleNotFoundError:
#     SpotifyAuthError = None  # type: ignore
#     SpotifyRateLimitDetectedError = None  # type: ignore

def setup_ffmpeg_path():
    """Setup FFmpeg path from settings.json to match GUI behavior"""
    try:
        # Try to load settings.json from config folder
        settings_path = os.path.join("config", "settings.json")
        if os.path.exists(settings_path):
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            
            # Get FFmpeg path setting
            ffmpeg_path_setting = settings.get("global", {}).get("advanced", {}).get("ffmpeg_path", "ffmpeg")
            
            if isinstance(ffmpeg_path_setting, str):
                ffmpeg_path_setting = ffmpeg_path_setting.strip()
                
                # If it's a custom path (not just "ffmpeg"), add directory to PATH
                if ffmpeg_path_setting and ffmpeg_path_setting.lower() != "ffmpeg":
                    if os.path.isfile(ffmpeg_path_setting):
                        ffmpeg_dir = os.path.dirname(ffmpeg_path_setting)
                        if ffmpeg_dir:
                            current_path = os.environ.get("PATH", "")
                            if ffmpeg_dir not in current_path.split(os.pathsep):
                                os.environ["PATH"] = ffmpeg_dir + os.pathsep + current_path
        else:
            pass  # Settings file not found, using defaults
    except Exception as e:
        # Don't fail if we can't setup FFmpeg path, just continue
        print(f"Warning: Could not setup FFmpeg path: {e}")

def main():
    # Setup FFmpeg path from settings.json (same as GUI)
    setup_ffmpeg_path()
    
    print(r'''
   ____             _                    _____  _      
  / __ \           | |                  |  __ \| |     
 | |  | |_ __ _ __ | |__   ___ _   _ ___| |  | | |     
 | |  | | '__| '_ \| '_ \ / _ \ | | / __| |  | | |     
 | |__| | |  | |_) | | | |  __/ |_| \__ \ |__| | |____ 
  \____/|_|  | .__/|_| |_|\___|\__,_|___/_____/|______|
             | |                                       
             |_|                                       
             
            ''')
    
    help_ = 'Use "settings [option]" for orpheus controls (coreupdate, fullupdate, modinstall), "settings [module]' \
           '[option]" for module specific options (update, test, setup), searching by "[search/luckysearch] [module]' \
           '[track/artist/playlist/album] [query]", or just putting in urls. (you may need to wrap the URLs in double' \
           'quotes if you have issues downloading)'
    parser = argparse.ArgumentParser(description='Orpheus: modular music archival')
    parser.add_argument('-p', '--private', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('-o', '--output', help='Select a download output path. Default is the provided download path in config/settings.py')
    parser.add_argument('-lr', '--lyrics', default='default', help='Set module to get lyrics from')
    parser.add_argument('-cv', '--covers', default='default', help='Override module to get covers from')
    parser.add_argument('-cr', '--credits', default='default', help='Override module to get credits from')
    parser.add_argument('-sd', '--separatedownload', default='default', help='Select a different module that will download the playlist instead of the main module. Only for playlists.')
    parser.add_argument('arguments', nargs='*', help=help_)
    args = parser.parse_args()

    orpheus = Orpheus(args.private)
    
    # Set global progress bar setting for the CLI
    from utils.utils import set_progress_bars_enabled
    progress_bar_setting = orpheus.settings.get('global', {}).get('general', {}).get('progress_bar', False)
    set_progress_bars_enabled(progress_bar_setting)
    if not args.arguments:
        parser.print_help()
        exit()

    orpheus_mode = args.arguments[0].lower()
    if orpheus_mode == 'settings': # These should call functions in a separate py file, that does not yet exist
        setting = args.arguments[1].lower()
        if setting == 'refresh':
            print('settings.json has been refreshed successfully.')
            return # Actually the only one that should genuinely return here after doing nothing
        elif setting == 'core_update':  # Updates only Orpheus
            return  # TODO
        elif setting == 'full_update':  # Updates Orpheus and all modules
            return  # TODO
            orpheus.update_setting_storage()
        elif setting == 'module_install':  # Installs a module with git
            return  # TODO
            orpheus.update_setting_storage()
        elif setting == 'test_modules':
            return # TODO
        elif setting in orpheus.module_list:
            orpheus.load_module(setting)
            modulesetting = args.arguments[2].lower()
            if modulesetting == 'update':
                return  # TODO
                orpheus.update_setting_storage()
            elif modulesetting == 'setup':
                return  # TODO
            elif modulesetting == 'adjust_setting':
                return  # TODO
            #elif modulesetting in [custom settings function list] TODO (here so test can be replaced)
            elif modulesetting == 'test': # Almost equivalent to sessions test
                return  # TODO
            else:
                raise Exception(f'Unknown setting "{modulesetting}" for module "{setting}"')
        else:
            raise Exception(f'Unknown setting: "{setting}"')
    elif orpheus_mode == 'sessions':
        module = args.arguments[1].lower()
        if module in orpheus.module_list:
            option = args.arguments[2].lower()
            if option == 'add':
                return  # TODO
            elif option == 'delete':
                return  # TODO
            elif option == 'list':
                return  # TODO
            elif option == 'test':
                session_name = args.arguments[3].lower()
                if session_name == 'all':
                    return  # TODO
                else:
                    return  # TODO, will also have a check for if the requested session actually exists, obviously
            else:
                raise Exception(f'Unknown option {option}, choose add/delete/list/test')
        else:
            raise Exception(f'Unknown module {module}') # TODO: replace with InvalidModuleError
    else:
        path = args.output if args.output else orpheus.settings['global']['general']['download_path']
        if path[-1] == '/': path = path[:-1]  # removes '/' from end if it exists
        os.makedirs(path, exist_ok=True)

        media_types = '/'.join(i.name for i in DownloadTypeEnum)

        if orpheus_mode == 'search' or orpheus_mode == 'luckysearch':
            if len(args.arguments) > 3:
                modulename = args.arguments[1].lower()
                if modulename in orpheus.module_list:
                    try:
                        query_type = DownloadTypeEnum[args.arguments[2].lower()]
                    except KeyError:
                        raise Exception(f'{args.arguments[2].lower()} is not a valid search type! Choose {media_types}')
                    lucky_mode = True if orpheus_mode == 'luckysearch' else False
                    
                    query = ' '.join(args.arguments[3:])
                    module = orpheus.load_module(modulename)
                    print("Searching... Please wait.")
                    items = module.search(query_type, query, limit = (1 if lucky_mode else orpheus.settings['global']['general']['search_limit']))
                    if len(items) == 0:
                        raise Exception(f'No search results for {query_type.name}: {query}')

                    if lucky_mode:
                        selection = 0
                    else:
                        for index, item in enumerate(items, start=1):
                            additional_details = '[E] ' if item.explicit else ''
                            additional_details += f'[{beauty_format_seconds(item.duration)}] ' if item.duration else ''
                            additional_details += f'[{item.year}] ' if item.year else ''
                            additional_details += ' '.join([f'[{i}]' for i in item.additional]) if item.additional else ''
                            if query_type is not DownloadTypeEnum.artist:
                                artists = ', '.join(item.artists) if item.artists is list else item.artists
                                print(f'{str(index)}. {item.name} - {", ".join(artists)} {additional_details}')
                            else:
                                print(f'{str(index)}. {item.name} {additional_details}')
                        
                        selection_input = input('Selection: ').strip('\r\n ')
                        if selection_input.lower() in ['e', 'q', 'x', 'exit', 'quit']: exit()
                        if not selection_input.isdigit(): raise Exception('Input a number')
                        selection = int(selection_input)-1
                        if selection < 0 or selection >= len(items): raise Exception('Invalid selection')
                        print()
                    selected_item: SearchResult = items[selection]
                    media_to_download = {modulename: [MediaIdentification(media_type=query_type, media_id=selected_item.result_id, extra_kwargs=selected_item.extra_kwargs or {})]}
                elif modulename == 'multi':
                    return  # TODO
                else:
                    modules = [i for i in orpheus.module_list if ModuleFlags.hidden not in orpheus.module_settings[i].flags]
                    raise Exception(f'Unknown module name "{modulename}". Must select from: {", ".join(modules)}') # TODO: replace with InvalidModuleError
            else:
                print(f'Search must be done as orpheus.py [search/luckysearch] [module] [{media_types}] [query]')
                exit() # TODO: replace with InvalidInput
        elif orpheus_mode == 'download':
            if len(args.arguments) > 3:
                modulename = args.arguments[1].lower()
                if modulename in orpheus.module_list:
                    try:
                        media_type = DownloadTypeEnum[args.arguments[2].lower()]
                    except KeyError:
                        raise Exception(f'{args.arguments[2].lower()} is not a valid download type! Choose {media_types}')
                    media_to_download = {modulename: [MediaIdentification(media_type=media_type, media_id=i) for i in args.arguments[3:]]}
                else:
                    modules = [i for i in orpheus.module_list if ModuleFlags.hidden not in orpheus.module_settings[i].flags]
                    raise Exception(f'Unknown module name "{modulename}". Must select from: {", ".join(modules)}') # TODO: replace with InvalidModuleError
            else:
                print(f'Download must be done as orpheus.py [download] [module] [{media_types}] [media ID 1] [media ID 2] ...')
                exit() # TODO: replace with InvalidInput
        else:  # if no specific modes are detected, parse as urls, but first try loading as a list of URLs
            arguments = tuple(open(args.arguments[0], 'r')) if len(args.arguments) == 1 and os.path.exists(args.arguments[0]) else args.arguments
            # Strip whitespace from lines read from file
            if isinstance(arguments, tuple) and len(args.arguments) == 1 and os.path.exists(args.arguments[0]):
                arguments = tuple(line.strip() for line in arguments if line.strip()) # Also filter out empty lines
            
            media_to_download = {}
            for link in arguments:
                link = link.strip() # Ensure individual link is also stripped if coming from args
                if not link: # Skip empty lines that might still be present if not from file
                    continue

                if link.startswith('http'):
                    url = urlparse(link)
                    components = url.path.split('/')

                    service_name = None
                    for i in orpheus.module_netloc_constants:
                        if re.findall(i, url.netloc): service_name = orpheus.module_netloc_constants[i]
                    if not service_name:
                        raise Exception(f'URL location "{url.netloc}" is not found in modules!')
                    if service_name not in media_to_download: media_to_download[service_name] = []

                    if orpheus.module_settings[service_name].url_decoding is ManualEnum.manual:
                        module = orpheus.load_module(service_name)
                        media_to_download[service_name].append(module.custom_url_parse(link))
                    else:
                        if not components or len(components) <= 2:
                            print(f'\tInvalid URL: "{link}"')
                            exit() # TODO: replace with InvalidInput
                        
                        url_constants = orpheus.module_settings[service_name].url_constants
                        if not url_constants:
                            url_constants = {
                                'track': DownloadTypeEnum.track,
                                'album': DownloadTypeEnum.album,
                                'playlist': DownloadTypeEnum.playlist,
                                'artist': DownloadTypeEnum.artist
                            }

                        type_matches = [media_type for url_check, media_type in url_constants.items() if url_check in components]

                        if not type_matches:
                            print(f'Invalid URL: "{link}"')
                            exit()

                        media_to_download[service_name].append(MediaIdentification(media_type=type_matches[-1], media_id=components[-1]))
                else:
                    raise Exception(f'Invalid argument: "{link}"')

        # Prepare the third-party modules similar to above
        tpm = {ModuleModes.covers: '', ModuleModes.lyrics: '', ModuleModes.credits: ''}
        for i in tpm:
            moduleselected = getattr(args, i.name).lower()
            if moduleselected == 'default':
                moduleselected = orpheus.settings['global']['module_defaults'][i.name]
            if moduleselected == 'default':
                moduleselected = None
            tpm[i] = moduleselected
        sdm = args.separatedownload.lower()

        if not media_to_download:
            print('No links given')

        # Beatport quality workaround: high and low quality fail, fallback to lossless FLAC
        original_quality = None
        beatport_quality_override = False
        if 'beatport' in media_to_download and orpheus.settings['global']['general']['download_quality'] in ['high', 'low']:
            original_quality = orpheus.settings['global']['general']['download_quality']
            orpheus.settings['global']['general']['download_quality'] = 'lossless'
            beatport_quality_override = True
            print(f' Beatport: Automatically switching from "{original_quality}" to "lossless" quality')

        try:
            orpheus_core_download(orpheus, media_to_download, tpm, sdm, path)
        finally:
            # Restore original quality setting if we overrode it
            if beatport_quality_override and original_quality:
                orpheus.settings['global']['general']['download_quality'] = original_quality


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print('\n\t^C pressed - abort')
        exit()
    # Specific handling for SpotifyAuthError, only if it was successfully imported
    except Exception as e:
        #if SpotifyAuthError is not None and isinstance(e, SpotifyAuthError):
        #   print(f'\nSpotify Authentication Error: {e}')
        #   print('Please try the command again. If the issue persists, you may need to check your Spotify credentials or network connection.')
        #    exit(1) # Exit with a non-zero code to indicate an error
        # Catch-all for other exceptions
        # For general exceptions, print the traceback if it's useful for debugging.
        # For a cleaner user experience for non-dev users, you might choose to print a simpler message.
        # For now, let's keep the traceback for general errors.
        import traceback
        print("\nAn unexpected error occurred:")
        traceback.print_exc()
