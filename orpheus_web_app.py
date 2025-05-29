from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import json
from OrpheusManager import OrpheusManager

app = FastAPI(title="Orpheus Web Interface")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Orpheus Manager
orpheus_manager = OrpheusManager()


class AuthRequest(BaseModel):
    platform: str
    username: str
    password: str


class SearchRequest(BaseModel):
    query: str
    platforms: List[str] = ["tidal"]
    limit: Optional[int] = 20
    page: Optional[int] = 1
    group_by_album: Optional[bool] = False
    username: Optional[str] = None
    password: Optional[str] = None


class AlbumSearchRequest(BaseModel):
    query: str
    platforms: List[str] = ["tidal"]
    limit: Optional[int] = 10
    username: Optional[str] = None
    password: Optional[str] = None


class DownloadRequest(BaseModel):
    url: str
    platform: str
    type: str  # 'track' or 'album'


@app.get("/")
async def root():
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Orpheus Web Interface</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .container { max-width: 1200px; margin: 0 auto; }
            .search-box { margin: 20px 0; }
            .search-box input { padding: 10px; width: 300px; margin-right: 10px; }
            .search-box button { padding: 10px 20px; }
            .controls { margin: 20px 0; }
            .controls label { margin-right: 15px; }
            .results { margin-top: 20px; }
            .track { 
                border: 1px solid #ddd; 
                padding: 15px; 
                margin: 10px 0; 
                border-radius: 5px;
                background: #f9f9f9;
            }
            .album-group {
                border: 2px solid #007bff;
                margin: 20px 0;
                border-radius: 8px;
                background: #f8f9fa;
            }
            .album-header {
                background: #007bff;
                color: white;
                padding: 15px;
                font-weight: bold;
                border-radius: 6px 6px 0 0;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .album-tracks {
                padding: 10px;
            }
            .singles-section {
                border: 2px solid #28a745;
                margin: 20px 0;
                border-radius: 8px;
                background: #f8fff8;
            }
            .singles-header {
                background: #28a745;
                color: white;
                padding: 15px;
                font-weight: bold;
                border-radius: 6px 6px 0 0;
            }
            .album-result {
                border: 2px solid #6f42c1;
                margin: 20px 0;
                border-radius: 8px;
                background: #f8f9ff;
            }
            .album-result-header {
                background: #6f42c1;
                color: white;
                padding: 15px;
                font-weight: bold;
                border-radius: 6px 6px 0 0;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .album-result-info {
                background: #e9ecef;
                padding: 10px 15px;
                font-size: 0.9em;
                color: #495057;
            }
            .tracklist {
                padding: 15px;
            }
            .tracklist-item {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 8px 10px;
                margin: 5px 0;
                background: white;
                border-radius: 4px;
                border-left: 3px solid #6f42c1;
            }
            .tracklist-item:hover {
                background: #f8f9fa;
            }
            .track-number {
                width: 30px;
                font-weight: bold;
                color: #6c757d;
            }
            .track-info {
                flex: 1;
                margin-left: 10px;
            }
            .track-name {
                font-weight: 500;
                color: #212529;
            }
            .track-artist {
                font-size: 0.85em;
                color: #6c757d;
            }
            .track-duration {
                color: #6c757d;
                font-size: 0.85em;
                margin-right: 10px;
            }
            .pagination {
                margin: 20px 0;
                text-align: center;
            }
            .pagination button {
                margin: 0 5px;
                padding: 8px 16px;
                border: 1px solid #dee2e6;
                background: white;
                cursor: pointer;
                border-radius: 4px;
            }
            .pagination button:hover {
                background: #f8f9fa;
            }
            .pagination .current {
                background: #007bff;
                color: white;
                border-color: #007bff;
            }
            .pagination .current:hover {
                background: #0056b3;
            }
            .track-quality { 
                background: #007bff; 
                color: white; 
                padding: 2px 6px; 
                border-radius: 3px; 
                font-size: 0.8em; 
            }
            .explicit { 
                background: #dc3545; 
                color: white; 
                padding: 2px 6px; 
                border-radius: 3px; 
                font-size: 0.8em; 
                margin-left: 5px;
            }
            .debug { 
                background: #f8f9fa; 
                border: 1px solid #dee2e6; 
                padding: 10px; 
                margin: 10px 0; 
                border-radius: 3px; 
                font-family: monospace; 
                font-size: 0.8em; 
            }
            .download-btn {
                background: #28a745;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                cursor: pointer;
                margin-left: 5px;
                font-size: 0.8em;
            }
            .download-btn:hover {
                background: #218838;
            }
            .download-album-btn {
                background: #007bff;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                cursor: pointer;
            }
            .download-album-btn:hover {
                background: #0056b3;
            }
            .group-controls {
                display: none; /* Hide by default, show only for track search */
            }
            .group-controls.show {
                display: inline;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎵 Orpheus Web Interface</h1>

            <div class="search-box">
                <input type="text" id="searchQuery" placeholder="Search for tracks..." value="">
                <button onclick="searchTracks()">Search Tracks</button>
                <button onclick="searchAlbums()">Search Albums</button>
            </div>

            <div class="controls">
                <span class="group-controls" id="groupControls">
                    <label><input type="checkbox" id="groupByAlbum"> Group by Album</label>
                </span>
                <label>Page Size: 
                    <select id="pageSize">
                        <option value="10">10</option>
                        <option value="20" selected>20</option>
                        <option value="50">50</option>
                        <option value="100">100</option>
                    </select>
                </label>
                <label><input type="checkbox" id="showDebug"> Show Debug Info</label>
            </div>

            <div id="pagination" class="pagination" style="display:none;"></div>
            <div id="debug-info" class="debug" style="display:none;"></div>
            <div id="results" class="results"></div>
            <div id="pagination-bottom" class="pagination" style="display:none;"></div>
        </div>

        <script>
            let currentPage = 1;
            let totalPages = 1;
            let currentQuery = '';
            let currentSearchType = 'tracks';

            function formatDuration(seconds) {
                if (!seconds) return '';
                const mins = Math.floor(seconds / 60);
                const secs = seconds % 60;
                return `${mins}:${secs.toString().padStart(2, '0')}`;
            }

            function showDebug(data) {
                const debugDiv = document.getElementById('debug-info');
                const showDebug = document.getElementById('showDebug').checked;

                if (showDebug) {
                    debugDiv.style.display = 'block';
                    debugDiv.innerHTML = '<strong>Debug Info:</strong><br>' + JSON.stringify(data, null, 2);
                } else {
                    debugDiv.style.display = 'none';
                }
            }

            function renderPagination(containerId) {
                const container = document.getElementById(containerId);
                if (totalPages <= 1) {
                    container.style.display = 'none';
                    return;
                }

                container.style.display = 'block';
                let html = '';

                if (currentPage > 1) {
                    html += `<button onclick="goToPage(${currentPage - 1})">Previous</button>`;
                }

                for (let i = Math.max(1, currentPage - 2); i <= Math.min(totalPages, currentPage + 2); i++) {
                    const current = i === currentPage ? 'current' : '';
                    html += `<button class="${current}" onclick="goToPage(${i})">${i}</button>`;
                }

                if (currentPage < totalPages) {
                    html += `<button onclick="goToPage(${currentPage + 1})">Next</button>`;
                }

                html += `<span style="margin-left: 20px;">Page ${currentPage} of ${totalPages} (${document.getElementById('totalResults') ? document.getElementById('totalResults').textContent : 'unknown'} total results)</span>`;
                container.innerHTML = html;
            }

            function goToPage(page) {
                currentPage = page;
                if (currentSearchType === 'tracks') {
                    searchTracks();
                } else {
                    searchAlbums();
                }
            }

            async function searchTracks() {
                const query = document.getElementById('searchQuery').value;
                const groupByAlbum = document.getElementById('groupByAlbum').checked;
                const pageSize = parseInt(document.getElementById('pageSize').value);

                if (!query) return;

                currentQuery = query;
                currentSearchType = 'tracks';

                // Show group controls for track search
                document.getElementById('groupControls').classList.add('show');

                // Reset to page 1 if this is a new search
                if (currentPage === 1) {
                    currentPage = 1;
                }

                try {
                    const response = await fetch('/api/search', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            query: query,
                            platforms: ['tidal'],
                            limit: pageSize,
                            page: currentPage,
                            group_by_album: groupByAlbum
                        })
                    });

                    const data = await response.json();
                    console.log('Search response:', data);
                    showDebug(data);

                    if (data.results && data.results.tidal) {
                        const result = data.results.tidal;
                        console.log('TIDAL result:', result);

                        if (result.pagination) {
                            totalPages = result.pagination.total_pages;
                            currentPage = result.pagination.current_page;

                            // Update total results display
                            let totalResultsElement = document.getElementById('totalResults');
                            if (!totalResultsElement) {
                                totalResultsElement = document.createElement('span');
                                totalResultsElement.id = 'totalResults';
                                totalResultsElement.style.display = 'none';
                                document.body.appendChild(totalResultsElement);
                            }
                            totalResultsElement.textContent = result.pagination.total_results;
                        }

                        displayResults(result, groupByAlbum);
                        renderPagination('pagination');
                        renderPagination('pagination-bottom');
                    } else {
                        console.error('No TIDAL results found in response:', data);
                        document.getElementById('results').innerHTML = '<p>No results structure found in response.</p>';
                    }
                } catch (error) {
                    console.error('Search error:', error);
                    document.getElementById('results').innerHTML = `<p>Error: ${error.message}</p>`;
                }
            }

            async function searchAlbums() {
                const query = document.getElementById('searchQuery').value;
                const pageSize = parseInt(document.getElementById('pageSize').value);

                if (!query) return;

                currentQuery = query;
                currentSearchType = 'albums';

                // Hide group controls for album search
                document.getElementById('groupControls').classList.remove('show');

                try {
                    const response = await fetch('/api/search-albums', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            query: query,
                            platforms: ['tidal'],
                            limit: pageSize
                        })
                    });

                    const data = await response.json();
                    console.log('Album search response:', data);
                    showDebug(data);
                    displayAlbumResults(data.results.tidal);
                } catch (error) {
                    console.error('Album search error:', error);
                    document.getElementById('results').innerHTML = `<p>Error: ${error.message}</p>`;
                }
            }

            function displayResults(result, groupByAlbum) {
                const resultsDiv = document.getElementById('results');

                console.log('Displaying results:', result);
                console.log('Tracks array:', result.tracks);
                console.log('Tracks length:', result.tracks ? result.tracks.length : 'undefined');

                if (!result.tracks || result.tracks.length === 0) {
                    resultsDiv.innerHTML = '<p>No tracks found.</p>';
                    return;
                }

                let html = '';

                if (groupByAlbum && result.organized) {
                    // Display albums
                    for (const [albumName, tracks] of Object.entries(result.organized.albums)) {
                        // Get album URL from first track (assuming same album)
                        const albumUrl = tracks[0] ? getAlbumUrlFromTrack(tracks[0].url) : '';

                        html += `
                            <div class="album-group">
                                <div class="album-header">
                                    <span>${albumName} (${tracks.length} tracks)</span>
                                    ${albumUrl ? `<button class="download-album-btn" onclick="downloadAlbum('${albumUrl}', 'tidal')">Download Album</button>` : ''}
                                </div>
                                <div class="album-tracks">`;

                        for (const track of tracks) {
                            html += formatTrack(track);
                        }

                        html += `</div></div>`;
                    }

                    // Display singles
                    if (result.organized.singles.length > 0) {
                        html += `
                            <div class="singles-section">
                                <div class="singles-header">Singles (${result.organized.singles.length} tracks)</div>
                                <div class="album-tracks">`;

                        for (const track of result.organized.singles) {
                            html += formatTrack(track);
                        }

                        html += `</div></div>`;
                    }
                } else {
                    // Display as simple list
                    for (const track of result.tracks) {
                        html += formatTrack(track);
                    }
                }

                resultsDiv.innerHTML = html;
            }

            function formatTrack(track) {
                const duration = formatDuration(track.duration);
                const quality = track.quality ? `<span class="track-quality">${track.quality}</span>` : '';
                const explicit = track.explicit ? '<span class="explicit">E</span>' : '';

                return `
                    <div class="track">
                        <strong>${track.name}</strong> by ${track.artist}
                        <br>
                        <small>
                            Album: ${track.album} • ${duration} • ${track.year || 'Unknown Year'} ${quality} ${explicit}
                        </small>
                        <br>
                        <button class="download-btn" onclick="downloadTrack('${track.url}', 'tidal')">Download Track</button>
                    </div>
                `;
            }

            function getAlbumUrlFromTrack(trackUrl) {
                // Convert track URL to album URL
                // https://tidal.com/browse/track/123456 -> https://tidal.com/browse/album/123456
                return trackUrl.replace('/track/', '/album/');
            }

            function displayAlbumResults(result) {
                const resultsDiv = document.getElementById('results');

                if (!result.albums || result.albums.length === 0) {
                    resultsDiv.innerHTML = '<p>No albums found.</p>';
                    return;
                }

                let html = '<h3>Albums Found:</h3>';

                for (const album of result.albums) {
                    const albumDuration = album.duration ? ` • ${formatDuration(album.duration)}` : '';

                    html += `
                        <div class="album-result">
                            <div class="album-result-header">
                                <span>${album.name} by ${album.artist}</span>
                                <button class="download-album-btn" onclick="downloadAlbum('${album.url}', 'tidal')">Download Album</button>
                            </div>
                            <div class="album-result-info">
                                ${album.year || 'Unknown Year'}${albumDuration} • ${album.tracks.length} tracks
                            </div>`;

                    if (album.tracks && album.tracks.length > 0) {
                        html += '<div class="tracklist">';

                        for (const track of album.tracks) {
                            const trackDuration = formatDuration(track.duration);
                            const explicit = track.explicit ? '<span class="explicit">E</span>' : '';

                            html += `
                                <div class="tracklist-item">
                                    <span class="track-number">${track.track_number}</span>
                                    <div class="track-info">
                                        <div class="track-name">${track.name}${explicit}</div>
                                        <div class="track-artist">${track.artist}</div>
                                    </div>
                                    <span class="track-duration">${trackDuration}</span>
                                    <button class="download-btn" onclick="downloadTrack('${track.url}', 'tidal')">Download</button>
                                </div>
                            `;
                        }

                        html += '</div>';
                    } else {
                        html += '<div style="padding: 15px; color: #6c757d; font-style: italic;">No tracklist available</div>';
                    }

                    html += '</div>';
                }

                resultsDiv.innerHTML = html;

                // Hide pagination for album search
                document.getElementById('pagination').style.display = 'none';
                document.getElementById('pagination-bottom').style.display = 'none';
            }

            async function downloadTrack(trackUrl, platform) {
                try {
                    console.log('Downloading track:', trackUrl);

                    const response = await fetch('/api/download', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            url: trackUrl,
                            platform: platform,
                            type: 'track'
                        })
                    });

                    const data = await response.json();

                    if (data.success) {
                        alert(`Track download started!\\nPID: ${data.pid}\\nCommand: ${data.command}`);
                    } else {
                        alert(`Download failed: ${data.error}`);
                    }
                } catch (error) {
                    console.error('Download error:', error);
                    alert(`Download error: ${error.message}`);
                }
            }

            async function downloadAlbum(albumUrl, platform) {
                try {
                    console.log('Downloading album:', albumUrl);

                    const response = await fetch('/api/download', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            url: albumUrl,
                            platform: platform,
                            type: 'album'
                        })
                    });

                    const data = await response.json();

                    if (data.success) {
                        alert(`Album download started!\\nPID: ${data.pid}\\nCommand: ${data.command}`);
                    } else {
                        alert(`Download failed: ${data.error}`);
                    }
                } catch (error) {
                    console.error('Download error:', error);
                    alert(`Download error: ${error.message}`);
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.post("/api/search")
async def search_tracks(request: SearchRequest):
    results = {}

    for platform in request.platforms:
        try:
            result = await orpheus_manager.search_with_credentials(
                platform=platform,
                query=request.query,
                username=request.username or "",
                password=request.password or "",
                page=request.page,
                limit=request.limit,
                group_by_album=request.group_by_album
            )
            results[platform] = result

            # Debug logging
            print(f"API sending result for {platform}:")
            print(f"  Result type: {type(result)}")
            print(f"  Result keys: {list(result.keys()) if isinstance(result, dict) else 'not dict'}")
            print(f"  Tracks count: {len(result.get('tracks', [])) if isinstance(result, dict) else 'unknown'}")

        except Exception as e:
            print(f"API error for {platform}: {e}")
            results[platform] = {"error": str(e)}

    print(f"Final API response structure: {list(results.keys())}")
    return {"results": results}


@app.post("/api/search-albums")
async def search_albums_endpoint(request: AlbumSearchRequest):
    results = {}

    for platform in request.platforms:
        try:
            result = await orpheus_manager.search_albums(
                platform=platform,
                query=request.query,
                username=request.username or "",
                password=request.password or "",
                limit=request.limit
            )
            results[platform] = result
        except Exception as e:
            results[platform] = {"error": str(e)}

    return {"results": results}


@app.post("/api/download")
async def download_endpoint(request: DownloadRequest):
    try:
        if request.type == 'track':
            result = await orpheus_manager.download_track(
                platform=request.platform,
                track_url=request.url
            )
        elif request.type == 'album':
            result = await orpheus_manager.download_album(
                platform=request.platform,
                album_url=request.url
            )
        else:
            return {"success": False, "error": "Invalid download type"}

        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/platforms")
async def get_platforms():
    return {"platforms": orpheus_manager.get_available_platforms()}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)