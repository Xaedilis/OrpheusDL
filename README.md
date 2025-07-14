<!-- PROJECT INTRO -->

<img src='https://github.com/bascurtiz/OrpheusDL/blob/master/icon.svg' title='OrpheusDL icon' height="150">
OrpheusDL
=========

This fork enables downloading from Spotify & Apple Music

[Report Bug](https://github.com/bascurtiz/OrpheusDL/issues)
·
[Request Feature](https://github.com/bascurtiz/OrpheusDL/issues)

## Table of content

- [About OrpheusDL](#about-orpheusdl)
- [Getting Started](#getting-started)
    - [Prerequisites](#prerequisites)
    - [Installation](#installation)
- [Usage](#usage)
    - [Command Line](#command-line)
    - [Web Interface](#web-interface)
- [Web GUI Features](#web-gui-features)
    - [Running the Web Interface](#running-the-web-interface)
    - [Job Management](#job-management)
- [Configuration](#configuration)
    - [Global/Formatting](#globalformatting)
        - [Format variables](#format-variables)
- [Contact](#contact)
- [Acknowledgements](#acknowledgements)

<!-- ABOUT ORPHEUS -->

## About OrpheusDL
OrpheusDL is a modular music archival tool written in Python which allows archiving from multiple different services.


<!-- GETTING STARTED -->

## Getting Started

Follow these steps to get a local copy of Orpheus up and running:

### Prerequisites

* Python 3.7+ (due to the requirement of dataclasses), though Python 3.9 is highly recommended

### Installation

[![Watch how to install](https://i.imgur.com/pNqYcYh.png)](https://youtu.be/AGsYTQuO7nk)

1. Clone the repo
    ```shell
    git clone https://github.com/bascurtiz/OrpheusDL && cd OrpheusDL
    ```
2. Install all requirements
   ```shell
   pip install --upgrade --ignore-installed -r requirements.txt
   ```
3. For web interface support, install additional dependencies
   ```shell
   pip install fastapi uvicorn pydantic
   ```
4. Run the program at least once, or use this command to create the settings file
   ```shell
   python orpheus.py settings refresh
   ```
5. Enter your credentials in `config/settings.json`

<!-- USAGE EXAMPLES -->

## Usage

### Command Line

Just call `orpheus.py` with any link you want to archive, for example Qobuz:

```shell 
python orpheus.py [https://open.qobuz.com/album/c9wsrrjh49ftb](https://open.qobuz.com/album/c9wsrrjh49ftb)
``` 

Alternatively do a search (luckysearch to automatically select the first option):

```shell
python orpheus.py search qobuz track darkside alan walker
``` 

Or if you have the ID of what you want to download, use:

```shell
python orpheus.py download qobuz track 52151405
``` 

### Web Interface

OrpheusDL now includes a modern web interface for easier searching and downloading:

```shell
python3 orpheus_web_app.py
``` 

Then open your browser to: http://localhost:8000

## Web GUI Features

The web interface provides:

- 🔍 **Search Interface** - Search for tracks and albums across supported platforms
- 🎵 **One-Click Downloads** - Download tracks and albums with a single click
- 📊 **Job Management** - Monitor download progress with real-time status updates
- 🌐 **Modern UI** - Clean, responsive interface that works on desktop and mobile
- ⚡ **Background Processing** - Downloads run in the background with detailed logging

### Running the Web Interface

1. **Start the web server**
   ```shell
   python3 orpheus_web_app.py
   ```

2. **Access the interface**
    - Open your browser to: http://localhost:8000
    - API documentation available at: http://localhost:8000/docs

3. **Using the interface**
    - Enter search queries for tracks or albums
    - Provide platform credentials when prompted
    - Click download buttons to start downloads
    - Monitor progress in the "Download Jobs" section

### Job Management

The web interface includes a comprehensive job management system:

- **Real-time Status** - See download progress as it happens
- **Job Queue** - Multiple downloads can run simultaneously
- **Detailed Logs** - View complete download logs for troubleshooting
- **Auto-refresh** - Job status updates automatically every 10 seconds
- **Error Handling** - Failed downloads show detailed error messages

**Job Statuses:**

- `queued` - Job is waiting to start
- `running` - Download is in progress
- `completed` - Download finished successfully
- `failed` - Download encountered an error

<!-- CONFIGURATION -->

## Configuration

You can customize every module from Orpheus individually and also set general/global settings which are active in every
loaded module. You'll find the configuration file here: `config/settings.json`

### Global/General

```json5
{
  "download_path": "./downloads/",
  "download_quality": "hifi",
  "search_limit": 10
}
``` 

`download_path`: Set the absolute or relative output path with `/` as the delimiter

`download_quality`: Choose one of the following settings:

* "hifi": FLAC higher than 44.1/16 if available
* "lossless": FLAC with 44.1/16 if available
* "high": lossy codecs such as MP3, AAC, ... in a higher bitrate
* "medium": lossy codecs such as MP3, AAC, ... in a medium bitrate
* "low": lossy codecs such as MP3, AAC, ... in a lower bitrate

**NOTE: The `download_quality` really depends on the used modules, so check out the modules README.md**

`search_limit`: How many search results are shown

### Global/Formatting:

```json5
{
  "album_format": "{name}{explicit}",
  "playlist_format": "{name}{explicit}",
  "track_filename_format": "{track_number}. {name}",
  "single_full_path_format": "{name}",
  "enable_zfill": true,
  "force_album_format": false
}
``` 

`track_filename_format`: How tracks are formatted in albums and playlists. The relevant extension is appended to the
end.

`album_format`, `playlist_format`, `artist_format`: Base directories for their respective formats - tracks and cover
art are stored here. May have slashes in it, for instance {artist}/{album}.

`single_full_path_format`: How singles are handled, which is separate to how the above work.
Instead, this has both the folder's name and the track's name.

`enable_zfill`: Enables zero padding for `track_number`, `total_tracks`, `disc_number`, `total_discs` if the
corresponding number has more than 2 digits

`force_album_format`: Forces the `album_format` for tracks instead of the `single_full_path_format` and also
uses `album_format` in the `playlist_format` folder

#### Format variables

`track_filename_format` variables are `{name}`, `{album}`, `{album_artist}`, `{album_id}`, `{track_number}`,
`{total_tracks}`, `{disc_number}`, `{total_discs}`, `{release_date}`, `{release_year}`, `{artist_id}`, `{isrc}`,
`{upc}`, `{explicit}`, `{copyright}`, `{codec}`, `{sample_rate}`, `{bit_depth}`.

`album_format` variables are `{name}`, `{id}`, `{artist}`, `{artist_id}`, `{release_year}`, `{upc}`, `{explicit}`,
`{quality}`, `{artist_initials}`.

`playlist_format` variables are `{name}`, `{creator}`, `{tracks}`, `{release_year}`, `{explicit}`, `{creator_id}`

* `{quality}` will add
    ```
     [Dolby Atmos]
     [96kHz 24bit]
     [M]
    ```

to the corresponding path (depending on the module)

* `{explicit}` will add
    ```
     [E]
    ```
  to the corresponding path

### Global/Covers

```json5
{ "embed_cover": true, "main_compression": "high", "main_resolution": 1400, "save_external": false, "external_format": "png", "external_compression": "low", "external_resolution": 3000, "save_animated_cover": true }
``` 

| Option               | Info                                                                                     |
|----------------------|------------------------------------------------------------------------------------------|
| embed_cover          | Enable it to embed the album cover inside every track                                    |
| main_compression     | Compression of the main cover                                                            |
| main_resolution      | Resolution (in pixels) of the cover of the module used                                   |
| save_external        | Enable it to save the cover from a third party cover module                              |
| external_format      | Format of the third party cover, supported values: `jpg`, `png`, `webp`                  |
| external_compression | Compression of the third party cover, supported values: `low`, `high`                    |
| external_resolution  | Resolution (in pixels) of the third party cover                                          |
| save_animated_cover  | Enable saving the animated cover when supported from the module (often in MPEG-4 format) |

### Global/Codecs

```json5
{ "proprietary_codecs": false, "spatial_codecs": true }
``` 

`proprietary_codecs`: Enable it to allow `MQA`, `E-AC-3 JOC` or `AC-4 IMS`

`spatial_codecs`: Enable it to allow `MPEG-H 3D`, `E-AC-3 JOC` or `AC-4 IMS`

**Note: `spatial_codecs` has priority over `proprietary_codecs` when deciding if a codec is enabled**

### Global/Module_defaults

```json5
{ "lyrics": "default", "covers": "default", "credits": "default" }
``` 

Change `default` to the module name under `/modules` in order to retrieve `lyrics`, `covers` or `credits` from the
selected module

### Global/Lyrics

```json5
{
  "embed_lyrics": true,
  "embed_synced_lyrics": false,
  "save_synced_lyrics": true
}
```

| Option | Info |
| --- | --- |
| embed_lyrics | Embeds the (unsynced) lyrics inside every track |
| embed_synced_lyrics | Embeds the synced lyrics inside every track (needs to be enabled) (required for [Roon](https://community.roonlabs.com/t/1-7-lyrics-tag-guide/85182)) `embed_lyrics` |
| save_synced_lyrics | Saves the synced lyrics inside a file in the same directory as the track with the same variables `.lrc``track_format` |
## Contact
OrfiDev (Project Lead) - [@OrfiDev](https://github.com/OrfiDev)
Dniel97 (Current Lead Developer) - [@Dniel97](https://github.com/Dniel97)
Original Project Link: [Orpheus Public GitHub Repository](https://github.com/OrfiTeam/OrpheusDL)



## Acknowledgements
- Chimera by Aesir - the inspiration to the project
- [Icon modified from a freepik image](https://www.freepik.com/)