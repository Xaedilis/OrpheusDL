// Search functionality
console.log('Search module loaded');

let currentSearchData = null;

document.addEventListener('DOMContentLoaded', function() {
    const searchForm = document.getElementById('searchForm');
    if (searchForm) {
        searchForm.addEventListener('submit', handleSearch);
    }
});

async function handleSearch(e) {
    e.preventDefault();

    const query = document.getElementById('searchQuery').value;
    const platform = document.getElementById('platform').value;
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const searchType = document.getElementById('searchType').value;
    const limit = parseInt(document.getElementById('limit').value);

    const resultsDiv = document.getElementById('searchResults');
    resultsDiv.innerHTML = '<p>Searching...</p>';
    resultsDiv.style.display = 'block';

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

        if (response.status === 428) {
            // Handle 2FA requirement
            const data = await response.json();
            if (data.detail && data.detail.requires_2fa) {
                currentSessionId = data.detail.session_id;
                show2FAModal();
                return;
            }
        }

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        displayResults(data, searchType, platform, username, password);

    } catch (error) {
        console.error('Search error:', error);
        resultsDiv.innerHTML = `<p style="color: red;">Error: ${error.message}</p>`;
    }
}

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