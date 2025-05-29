from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

# Import our custom modules
from OrpheusManager import OrpheusManager
from job_manager import job_manager, JobType, JobStatus

# Initialize FastAPI app
app = FastAPI(title="Orpheus Music Downloader API", version="1.0.0")

# Initialize OrpheusManager
orpheus_manager = OrpheusManager()


# Pydantic models for request/response validation
class AuthRequest(BaseModel):
    platform: str
    username: str
    password: str


class SearchRequest(BaseModel):
    query: str
    platforms: List[str]
    limit: int = 20
    page: int = 1
    group_by_album: bool = False
    username: str
    password: str


class AlbumSearchRequest(BaseModel):
    query: str
    platforms: List[str]
    limit: int = 10
    username: str
    password: str


class AlbumTracksRequest(BaseModel):
    album_id: str
    platform: str
    username: str
    password: str


class DownloadRequest(BaseModel):
    url: str
    platform: str
    type: str


class MultiFormatDownloadRequest(BaseModel):
    url: str
    platform: str
    type: str  # "track" or "album"
    formats: List[str] = ["configured"]  # Placeholder - formats come from config
    user_id: Optional[str] = None


class JobResponse(BaseModel):
    job_id: str
    status: str
    message: str


# Root endpoint with basic HTML interface
@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint with a simple HTML interface for testing"""
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Orpheus Music Downloader</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .container { max-width: 1200px; margin: 0 auto; }
            .section { margin: 30px 0; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }
            .form-group { margin: 15px 0; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input, select, button { padding: 8px; margin: 5px; }
            input[type="text"], input[type="password"], select { width: 300px; }
            button { background-color: #007bff; color: white; border: none; padding: 10px 20px; cursor: pointer; border-radius: 3px; }
            button:hover { background-color: #0056b3; }
            button:disabled { background-color: #6c757d; cursor: not-allowed; }
            .results { margin-top: 20px; }
            .album-item, .track-item { border: 1px solid #eee; padding: 15px; margin: 10px 0; border-radius: 5px; }
            .album-item { background-color: #f8f9fa; }
            .track-item { background-color: #ffffff; margin-left: 20px; }
            .tracks-container { display: none; margin-top: 10px; }
            .button-group { margin: 10px 0; }
            .download-btn { background-color: #28a745; margin-right: 10px; }
            .download-btn:hover { background-color: #218838; }
            .load-tracks-btn { background-color: #17a2b8; }
            .load-tracks-btn:hover { background-color: #138496; }
            .job-item { background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 10px; margin: 5px 0; border-radius: 3px; }
            .job-completed { background-color: #d4edda; border-color: #c3e6cb; }
            .job-failed { background-color: #f8d7da; border-color: #f5c6cb; }
            .job-running { background-color: #cce5ff; border-color: #b3d9ff; }
            .info-note { background-color: #e7f3ff; border: 1px solid #b3d9ff; padding: 10px; margin: 10px 0; border-radius: 3px; font-size: 0.9em; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Orpheus Music Downloader</h1>

            <div class="info-note">
                <strong>Note:</strong> Download formats are configured in the OrpheusManager config folder. 
                The system will use the configured quality and codec settings for all downloads.
            </div>

            <!-- Search Section -->
            <div class="section">
                <h2>Search Music</h2>
                <form id="searchForm">
                    <div class="form-group">
                        <label>Search Query:</label>
                        <input type="text" id="searchQuery" placeholder="Enter artist, album, or track name" required>
                    </div>
                    <div class="form-group">
                        <label>Platform:</label>
                        <select id="platform" required>
                            <option value="tidal">Tidal</option>
                            <option value="spotify">Spotify</option>
                            <option value="apple">Apple Music</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Username:</label>
                        <input type="text" id="username" required>
                    </div>
                    <div class="form-group">
                        <label>Password:</label>
                        <input type="password" id="password" required>
                    </div>
                    <div class="form-group">
                        <label>Search Type:</label>
                        <select id="searchType">
                            <option value="tracks">Tracks</option>
                            <option value="albums">Albums</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Limit:</label>
                        <input type="number" id="limit" value="10" min="1" max="50">
                    </div>
                    <button type="submit">Search</button>
                </form>

                <div id="searchResults" class="results"></div>
            </div>

            <!-- Jobs Section -->
            <div class="section">
                <h2>Download Jobs</h2>
                <button onclick="refreshJobs()">Refresh Jobs</button>
                <div id="jobsResults" class="results"></div>
            </div>
        </div>

        <script>
            // Search functionality
            document.getElementById('searchForm').addEventListener('submit', async function(e) {
                e.preventDefault();

                const query = document.getElementById('searchQuery').value;
                const platform = document.getElementById('platform').value;
                const username = document.getElementById('username').value;
                const password = document.getElementById('password').value;
                const searchType = document.getElementById('searchType').value;
                const limit = parseInt(document.getElementById('limit').value);

                const resultsDiv = document.getElementById('searchResults');
                resultsDiv.innerHTML = '<p>Searching...</p>';

                try {
                    let endpoint, requestData;

                    if (searchType === 'albums') {
                        endpoint = '/api/search/albums';
                        requestData = {
                            query: query,
                            platforms: [platform],
                            limit: limit,
                            username: username,
                            password: password
                        };
                    } else {
                        endpoint = '/api/search/tracks';
                        requestData = {
                            query: query,
                            platforms: [platform],
                            limit: limit,
                            page: 1,
                            group_by_album: false,
                            username: username,
                            password: password
                        };
                    }

                    const response = await fetch(endpoint, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(requestData)
                    });

                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }

                    const data = await response.json();
                    displayResults(data, searchType, platform, username, password);

                } catch (error) {
                    console.error('Search error:', error);
                    resultsDiv.innerHTML = `<p style="color: red;">Error: ${error.message}</p>`;
                }
            });

            function displayResults(data, searchType, platform, username, password) {
                const resultsDiv = document.getElementById('searchResults');
                let html = '';

                if (searchType === 'albums' && data.albums) {
                    html += `<h3>Albums (${data.albums.length})</h3>`;
                    data.albums.forEach(album => {
                        html += `
                            <div class="album-item">
                                <h4>${album.name}</h4>
                                <p><strong>Artist:</strong> ${album.artist}</p>
                                <p><strong>Year:</strong> ${album.year || 'Unknown'}</p>
                                <div class="button-group">
                                    <button class="load-tracks-btn" onclick="loadAlbumTracks('${album.id}', '${platform}', '${username}', '${password}', this)">
                                        Load Tracks
                                    </button>
                                    <button class="download-btn" onclick="downloadAlbum('${album.url}', '${platform}')">
                                        Download Album
                                    </button>
                                </div>
                                <div class="tracks-container"></div>
                            </div>
                        `;
                    });
                } else if (searchType === 'tracks' && data.tracks) {
                    html += `<h3>Tracks (${data.tracks.length})</h3>`;
                    if (data.pagination) {
                        html += `<p>Page ${data.pagination.current_page} of ${data.pagination.total_pages} (${data.pagination.total_results} total)</p>`;
                    }
                    data.tracks.forEach(track => {
                        html += `
                            <div class="track-item">
                                <h4>${track.name}</h4>
                                <p><strong>Artist:</strong> ${track.artist}</p>
                                <p><strong>Album:</strong> ${track.album}</p>
                                <p><strong>Duration:</strong> ${track.duration || 'Unknown'}</p>
                                <button class="download-btn" onclick="downloadTrack('${track.url}', '${platform}')">
                                    Download Track
                                </button>
                            </div>
                        `;
                    });
                }

                resultsDiv.innerHTML = html || '<p>No results found.</p>';
            }

            // Load album tracks on demand
            async function loadAlbumTracks(albumId, platform, username, password, button) {
                const tracksContainer = button.parentElement.nextElementSibling;

                if (tracksContainer.style.display === 'block') {
                    tracksContainer.style.display = 'none';
                    button.textContent = 'Load Tracks';
                    return;
                }

                button.disabled = true;
                button.textContent = 'Loading...';

                try {
                    const response = await fetch(`/api/albums/${albumId}/tracks`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            album_id: albumId,
                            platform: platform,
                            username: username,
                            password: password
                        })
                    });

                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }

                    const data = await response.json();

                    let tracksHtml = '<div class="tracks-list"><h5>Tracks:</h5>';
                    data.tracks.forEach(track => {
                        tracksHtml += `
                            <div class="track-item">
                                <span><strong>${track.track_number}.</strong> ${track.name}</span>
                                <span style="margin-left: 20px;"><em>${track.artist}</em></span>
                                <button class="download-btn" onclick="downloadTrack('${track.url}', '${platform}')" style="margin-left: 20px;">
                                    Download
                                </button>
                            </div>
                        `;
                    });
                    tracksHtml += '</div>';

                    tracksContainer.innerHTML = tracksHtml;
                    tracksContainer.style.display = 'block';
                    button.textContent = 'Hide Tracks';

                } catch (error) {
                    console.error('Error loading tracks:', error);
                    alert('Error loading tracks: ' + error.message);
                    button.textContent = 'Load Tracks';
                } finally {
                    button.disabled = false;
                }
            }

            // Download functions - simplified without format selection
            async function downloadTrack(url, platform) {
                try {
                    const response = await fetch('/api/download', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            url: url,
                            platform: platform,
                            type: 'track'
                        })
                    });

                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }

                    const data = await response.json();
                    alert(`Track download job started! Job ID: ${data.job_id}`);
                    refreshJobs();

                } catch (error) {
                    console.error('Error starting download:', error);
                    alert('Error starting download: ' + error.message);
                }
            }

            async function downloadAlbum(url, platform) {
                try {
                    const response = await fetch('/api/download', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            url: url,
                            platform: platform,
                            type: 'album'
                        })
                    });

                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }

                    const data = await response.json();
                    alert(`Album download job started! Job ID: ${data.job_id}`);
                    refreshJobs();

                } catch (error) {
                    console.error('Error starting album download:', error);
                    alert('Error starting album download: ' + error.message);
                }
            }

            // Job management
            async function refreshJobs() {
                try {
                    const response = await fetch('/api/jobs');
                    const data = await response.json();

                    const jobsDiv = document.getElementById('jobsResults');
                    let html = '';

                    if (data.jobs && data.jobs.length > 0) {
                        html += `<h3>Download Jobs (${data.jobs.length})</h3>`;
                        data.jobs.forEach(job => {
                            const statusClass = `job-${job.status}`;
                            html += `
                                <div class="job-item ${statusClass}">
                                    <h4>Job ${job.job_id.substring(0, 8)}...</h4>
                                    <p><strong>Type:</strong> ${job.job_type}</p>
                                    <p><strong>Status:</strong> ${job.status}</p>
                                    <p><strong>URL:</strong> ${job.url}</p>
                                    <p><strong>Created:</strong> ${new Date(job.created_at).toLocaleString()}</p>
                                    ${job.error_message ? `<p style="color: red;"><strong>Error:</strong> ${job.error_message}</p>` : ''}
                                    <button onclick="viewJobLogs('${job.job_id}')">View Logs</button>
                                </div>
                            `;
                        });
                    } else {
                        html = '<p>No jobs found.</p>';
                    }

                    jobsDiv.innerHTML = html;

                } catch (error) {
                    console.error('Error refreshing jobs:', error);
                    document.getElementById('jobsResults').innerHTML = `<p style="color: red;">Error loading jobs: ${error.message}</p>`;
                }
            }

            async function viewJobLogs(jobId) {
                try {
                    const response = await fetch(`/api/jobs/${jobId}/logs`);
                    const data = await response.json();

                    let logsText = `Logs for Job ${jobId}:\\n\\n`;
                    data.logs.forEach(log => {
                        logsText += `[${log.timestamp}] ${log.level}: ${log.message}\\n`;
                    });

                    alert(logsText);

                } catch (error) {
                    console.error('Error getting job logs:', error);
                    alert('Error getting job logs: ' + error.message);
                }
            }

            // Auto-refresh jobs every 10 seconds
            setInterval(refreshJobs, 10000);

            // Load jobs on page load
            refreshJobs();
        </script>
    </body>
    </html>
    """)


# API endpoints
@app.post("/api/search/tracks")
async def search_tracks(request: SearchRequest):
    """Search for tracks with pagination and grouping"""
    try:
        if not request.platforms or len(request.platforms) == 0:
            raise HTTPException(status_code=400, detail="At least one platform must be specified")

        # For now, use the first platform (can be extended for multi-platform search)
        platform = request.platforms[0]

        results = await orpheus_manager.search_with_credentials(
            platform=platform,
            query=request.query,
            username=request.username,
            password=request.password,
            page=request.page,
            limit=request.limit,
            group_by_album=request.group_by_album
        )

        return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/search/albums")
async def search_albums_endpoint(request: AlbumSearchRequest):
    """Search for albums without loading track lists"""
    try:
        if not request.platforms or len(request.platforms) == 0:
            raise HTTPException(status_code=400, detail="At least one platform must be specified")

        # For now, use the first platform
        platform = request.platforms[0]

        results = await orpheus_manager.search_albums(
            platform=platform,
            query=request.query,
            username=request.username,
            password=request.password,
            limit=request.limit
        )

        return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/albums/{album_id}/tracks")
async def get_album_tracks_endpoint(album_id: str, request: AlbumTracksRequest):
    """Load tracks for a specific album on demand"""
    try:
        tracks_data = await orpheus_manager.get_album_tracks(
            request.platform,
            album_id,
            request.username,
            request.password
        )
        return tracks_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/download/multi-format", response_model=JobResponse)
async def download_multi_format_endpoint(request: MultiFormatDownloadRequest):
    """Start a download job using configured formats"""
    try:
        # Determine job type
        job_type = JobType.TRACK_DOWNLOAD if request.type == "track" else JobType.ALBUM_DOWNLOAD

        # Create job - formats are just for display, actual formats come from config
        job_id = job_manager.create_job(
            job_type=job_type,
            url=request.url,
            platform=request.platform,
            formats=["configured"],  # Placeholder since formats come from config
            user_id=request.user_id
        )

        # Start the job in background
        job_manager.start_download_job(job_id)

        return JSONResponse(
            status_code=202,  # Accepted
            content={
                "job_id": job_id,
                "status": "accepted",
                "message": f"Download job started for {request.type}: {request.url}"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jobs")
async def get_all_jobs(user_id: Optional[str] = None):
    """Get all jobs, optionally filtered by user_id"""
    try:
        jobs = job_manager.get_all_jobs(user_id)
        return {"jobs": jobs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get status and details of a specific job"""
    try:
        job = job_manager.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        return job.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jobs/{job_id}/logs")
async def get_job_logs(job_id: str):
    """Get logs for a specific job"""
    try:
        logs = job_manager.get_job_logs(job_id)
        if logs is None:
            raise HTTPException(status_code=404, detail="Job not found")

        return {"job_id": job_id, "logs": logs}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Main download endpoint - uses configured formats
@app.post("/api/download")
async def download_endpoint(request: DownloadRequest):
    """Download endpoint that uses configured formats from OrpheusManager"""
    try:
        # Convert to multi-format request using config
        multi_format_request = MultiFormatDownloadRequest(
            url=request.url,
            platform=request.platform,
            type=request.type,
            formats=["configured"]  # Formats come from config
        )

        return await download_multi_format_endpoint(multi_format_request)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/platforms")
async def get_platforms():
    """Get list of available platforms"""
    try:
        platforms = orpheus_manager.get_available_platforms()
        return {"platforms": platforms}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Run the application
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)