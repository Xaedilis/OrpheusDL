// Search functionality
console.log('Search module loaded');

let currentSearchData = null;

document.addEventListener('DOMContentLoaded', function () {
    const platformSelect = document.getElementById('platform');
    const usernameGroup = document.getElementById('usernameGroup');
    const passwordGroup = document.getElementById('passwordGroup');
    const searchTypeGroup = document.getElementById('searchTypeGroup');
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');
    const searchTypeSelect = document.getElementById('searchType');
    const cookieNotice = document.getElementById('cookieNotice');
    const searchForm = document.getElementById('searchForm');

    // Set default limit to 200 for Apple Music (4 pages of 50 each)
    const limitInput = document.getElementById('limit');
    if (limitInput && !limitInput.value) {
        limitInput.value = '200';
    }

    // Handle platform selection changes
    platformSelect.addEventListener('change', function () {
        const selectedPlatform = this.value;

        if (selectedPlatform === 'applemusic') {
            // Hide username/password fields and search type for Apple Music
            usernameGroup.style.display = 'none';
            passwordGroup.style.display = 'none';
            searchTypeGroup.style.display = 'none';

            // Set default values for Apple Music
            usernameInput.value = 'cookies';
            passwordInput.value = 'cookies';
            searchTypeSelect.value = 'tracks'; // Force tracks search

            // Set higher limit for Apple Music since we're paginating
            if (limitInput) {
                limitInput.value = '200';
                limitInput.max = '500'; // Set a reasonable max limit
                limitInput.step = '50'; // Step by 50 since that's Apple's page size
            }

            // Remove required validation
            usernameInput.required = false;
            passwordInput.required = false;

            // Show cookie notice
            cookieNotice.style.display = 'block';
        } else {
            // Show username/password fields and search type for other platforms
            usernameGroup.style.display = 'block';
            passwordGroup.style.display = 'block';
            searchTypeGroup.style.display = 'block';

            // Reset values
            usernameInput.value = '';
            passwordInput.value = '';

            // Set default limit for other platforms
            if (limitInput) {
                limitInput.value = '50';
                limitInput.max = '100';
                limitInput.step = '10';
            }

            // Add required validation
            usernameInput.required = true;
            passwordInput.required = true;

            // Hide cookie notice
            cookieNotice.style.display = 'none';
        }
    });

    // Initialize the form based on the default platform
    platformSelect.dispatchEvent(new Event('change'));

    // Handle form submission
    searchForm.addEventListener('submit', function (e) {
        e.preventDefault();

        const selectedPlatform = platformSelect.value;
        const requestedLimit = parseInt(limitInput.value) || 200;

        // Show warning for large requests
        if (selectedPlatform === 'applemusic' && requestedLimit > 200) {
            const proceed = confirm(`You're requesting ${requestedLimit} results. This might take a while due to Apple Music's pagination. Continue?`);
            if (!proceed) {
                return;
            }
        }

        const formData = {
            query: document.getElementById('searchQuery').value,
            platforms: [selectedPlatform],
            username: usernameInput.value,
            password: passwordInput.value,
            page: 1,
            limit: requestedLimit,
            group_by_album: selectedPlatform === 'applemusic' // Group by album for Apple Music
        };

        const searchType = searchTypeSelect.value;

        // Clear previous results
        clearResults();

        // Show loading with pagination info for Apple Music
        if (selectedPlatform === 'applemusic') {
            showLoadingWithPagination(requestedLimit);
        } else {
            showLoading();
        }

        if (searchType === 'tracks' || selectedPlatform === 'applemusic') {
            searchTracks(formData);
        } else {
            searchAlbums(formData);
        }
    });

    // Search functions
    async function searchTracks(formData) {
        try {
            const response = await fetch('/api/search/tracks', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData)
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            // For Apple Music, display results grouped by album
            if (formData.platforms[0] === 'applemusic') {
                displayTrackResultsGroupedByAlbum(data);
            } else {
                displayTrackResults(data);
            }
        } catch (error) {
            showError('Search failed: ' + error.message);
        } finally {
            hideLoading();
        }
    }

    async function searchAlbums(formData) {
        try {
            const response = await fetch('/api/search/albums', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData)
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            displayAlbumResults(data);
        } catch (error) {
            showError('Search failed: ' + error.message);
        } finally {
            hideLoading();
        }
    }

    // Helper functions
    function showLoading() {
        const resultsDiv = document.getElementById('searchResults');
        if (resultsDiv) {
            resultsDiv.innerHTML = '<div class="loading">Searching...</div>';
        }
    }

    function showLoadingWithPagination(limit) {
        const resultsDiv = document.getElementById('searchResults');
        if (resultsDiv) {
            const pages = Math.ceil(limit / 50);
            resultsDiv.innerHTML = `
                <div class="loading">
                    <p>Searching Apple Music...</p>
                    <p>This may take a moment as we fetch up to ${limit} results across ${pages} pages.</p>
                    <div class="loading-spinner">⏳</div>
                </div>
            `;
        }
    }

    function hideLoading() {
        // Loading will be replaced by results or error
    }

    function clearResults() {
        const resultsDiv = document.getElementById('searchResults');
        if (resultsDiv) {
            resultsDiv.innerHTML = '';
        }
    }

    function showError(message) {
        const resultsDiv = document.getElementById('searchResults');
        if (resultsDiv) {
            resultsDiv.innerHTML = `<div class="error">${message}</div>`;
        }
    }

    function displayTrackResultsGroupedByAlbum(data) {
        const resultsDiv = document.getElementById('searchResults');
        if (!resultsDiv) {
            console.error('searchResults element not found');
            return;
        }

        console.log('Displaying track results grouped by album:', data);

        // Show the results div (it starts hidden)
        resultsDiv.style.display = 'block';

        if (!data.tracks || data.tracks.length === 0) {
            resultsDiv.innerHTML = '<div class="no-results">No tracks found</div>';
            return;
        }

        // Group tracks by album - use album_artist if available, otherwise use artist
        const albumGroups = {};
        data.tracks.forEach(track => {
            const albumArtist = track.album_artist || track.artist || 'Unknown Artist';
            const albumName = track.album || 'Unknown Album';
            const albumKey = `${albumName} - ${albumArtist}`;

            if (!albumGroups[albumKey]) {
                albumGroups[albumKey] = {
                    album: albumName,
                    artist: albumArtist,
                    tracks: []
                };
            }
            albumGroups[albumKey].tracks.push(track);
        });

        let html = '<div class="results-section"><h3>Search Results (Grouped by Album)</h3>';

        // Add pagination info
        const paginationInfo = data.pagination;
        if (paginationInfo) {
            html += `<div class="pagination-summary" style="background-color: #f0f8ff; padding: 15px; margin-bottom: 20px; border-radius: 5px; border-left: 4px solid #007bff;">`;
            html += `<p style="margin: 0;"><strong>📊 Search Results:</strong> Found ${data.tracks.length} tracks in ${Object.keys(albumGroups).length} albums</p>`;
            if (paginationInfo.has_more) {
                html += `<p style="margin: 5px 0 0 0; color: #666; font-style: italic;">💡 There may be more results available. Try increasing the limit if needed.</p>`;
            }
            html += `</div>`;
        }

        // Sort albums alphabetically
        const sortedAlbums = Object.keys(albumGroups).sort();

        sortedAlbums.forEach(albumKey => {
            const albumGroup = albumGroups[albumKey];

            html += `
                <div class="album-group" style="margin-bottom: 30px; border: 1px solid #ddd; border-radius: 8px; padding: 15px; background-color: #f9f9f9;">
                    <div class="album-header" style="margin-bottom: 15px; padding-bottom: 10px; border-bottom: 2px solid #007bff;">
                        <h4 style="margin: 0; color: #007bff; font-size: 1.2em;">${albumGroup.album}</h4>
                        <p style="margin: 5px 0 0 0; color: #666; font-style: italic;">by ${albumGroup.artist}</p>
                        <p style="margin: 5px 0 0 0; color: #999; font-size: 0.9em;">${albumGroup.tracks.length} tracks</p>
                        <button onclick="downloadAlbumFromFirstTrack('${albumGroup.tracks[0].url}', 'applemusic')" 
                                style="background-color: #28a745; color: white; border: none; padding: 8px 15px; border-radius: 4px; cursor: pointer; font-size: 0.9em; margin-top: 10px;">
                            Download Full Album
                        </button>
                    </div>
                    <div class="tracks-in-album">
            `;

            // Sort tracks by track number if available
            albumGroup.tracks.sort((a, b) => {
                const aNum = a.track_number || 999;
                const bNum = b.track_number || 999;
                return aNum - bNum;
            });

            albumGroup.tracks.forEach(track => {
                const safeName = track.name ? track.name.replace(/'/g, '&#39;').replace(/"/g, '&quot;') : 'Unknown';
                const safeUrl = track.url ? track.url.replace(/'/g, '&#39;').replace(/"/g, '&quot;') : '#';
                const trackNumber = track.track_number ? `${track.track_number}. ` : '';
                const duration = track.duration ? formatDuration(track.duration) : '';

                html += `
                    <div class="track-item" style="display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid #eee;">
                        <div class="track-info">
                            <span style="font-weight: 500;">${trackNumber}${safeName}</span>
                            ${duration ? `<span style="color: #666; margin-left: 10px; font-size: 0.9em;">${duration}</span>` : ''}
                            ${track.explicit ? '<span style="color: #dc3545; margin-left: 10px; font-size: 0.8em;">[EXPLICIT]</span>' : ''}
                        </div>
                        <div class="track-actions">
                            <button onclick="downloadTrack('${safeUrl}', 'applemusic')" 
                                    style="background-color: #007bff; color: white; border: none; padding: 5px 10px; border-radius: 3px; cursor: pointer; font-size: 0.9em;">
                                Download Track
                            </button>
                        </div>
                    </div>
                `;
            });

            html += `
                    </div>
                </div>
            `;
        });

        html += '</div>';
        resultsDiv.innerHTML = html;

        console.log('Track results grouped by album displayed successfully');
    }

    function displayTrackResults(data) {
        const resultsDiv = document.getElementById('searchResults');
        if (!resultsDiv) {
            console.error('searchResults element not found');
            return;
        }

        console.log('Displaying track results:', data);

        // Show the results div (it starts hidden)
        resultsDiv.style.display = 'block';

        if (!data.tracks || data.tracks.length === 0) {
            resultsDiv.innerHTML = '<div class="no-results">No tracks found</div>';
            return;
        }

        let html = '<div class="results-section"><h3>Track Results</h3>';

        data.tracks.forEach(track => {
            // Escape HTML to prevent XSS
            const safeName = track.name ? track.name.replace(/'/g, '&#39;').replace(/"/g, '&quot;') : 'Unknown';
            const safeArtist = track.artist ? track.artist.replace(/'/g, '&#39;').replace(/"/g, '&quot;') : 'Unknown Artist';
            const safeAlbum = track.album ? track.album.replace(/'/g, '&#39;').replace(/"/g, '&quot;') : 'Unknown Album';
            const safeUrl = track.url ? track.url.replace(/'/g, '&#39;').replace(/"/g, '&quot;') : '#';

            // Get the current platform from the form
            const currentPlatform = platformSelect ? platformSelect.value : 'tidal';

            html += `
            <div class="result-item">
                <div class="result-info">
                    <strong>${safeName}</strong><br>
                    by ${safeArtist}<br>
                    <small>Album: ${safeAlbum}</small>
                    ${track.additional_info ? `<br><small>${track.additional_info}</small>` : ''}
                </div>
                <div class="result-actions">
                    <button onclick="downloadTrack('${safeUrl}', '${currentPlatform}')" class="download-btn">
                        Download Track
                    </button>
                </div>
            </div>
        `;
        });

        // Add pagination info if available
        if (data.pagination) {
            html += `
            <div class="pagination-info">
                <p>Showing ${data.tracks.length} of ${data.pagination.total_results} results (Page ${data.pagination.current_page} of ${data.pagination.total_pages})</p>
            </div>
        `;
        }

        html += '</div>';
        resultsDiv.innerHTML = html;

        console.log('Track results displayed successfully');
    }

    function displayAlbumResults(data) {
        const resultsDiv = document.getElementById('searchResults');
        if (!resultsDiv) {
            console.error('searchResults element not found');
            return;
        }

        console.log('Displaying album results:', data);

        // Show the results div (it starts hidden)
        resultsDiv.style.display = 'block';

        if (!data.albums || data.albums.length === 0) {
            resultsDiv.innerHTML = '<div class="no-results">No albums found</div>';
            return;
        }

        let html = '<div class="results-section"><h3>Album Results</h3>';

        data.albums.forEach(album => {
            // Escape HTML to prevent XSS
            const safeName = album.name ? album.name.replace(/'/g, '&#39;').replace(/"/g, '&quot;') : 'Unknown';
            const safeArtist = album.artist ? album.artist.replace(/'/g, '&#39;').replace(/"/g, '&quot;') : 'Unknown Artist';
            const safeUrl = album.url ? album.url.replace(/'/g, '&#39;').replace(/"/g, '&quot;') : '#';

            // Get the current platform from the form
            const currentPlatform = platformSelect ? platformSelect.value : 'tidal';

            html += `
            <div class="result-item album-item">
                <div class="result-info">
                    <strong>${safeName}</strong><br>
                    by ${safeArtist}<br>
                    ${album.year ? `<small>Year: ${album.year}</small><br>` : ''}
                    ${album.track_count ? `<small>Tracks: ${album.track_count}</small>` : ''}
                </div>
                <div class="result-actions">
                    <button onclick="loadAlbumTracks('${album.id}', '${currentPlatform}')" class="load-tracks-btn">
                        Load Tracks
                    </button>
                    <button onclick="downloadAlbum('${safeUrl}', '${currentPlatform}')" class="download-btn">
                        Download Album
                    </button>
                </div>
            </div>
            <div id="tracks-${album.id}" class="tracks-container" style="display: none;"></div>
        `;
        });

        html += '</div>';
        resultsDiv.innerHTML = html;

        console.log('Album results displayed successfully');
    }
});

// Global functions that need to be available
window.downloadTrack = function(url, platform) {
    console.log('Downloading track:', url, 'from platform:', platform);

    const downloadData = {
        url: url,
        platform: platform,
        type: 'track'
    };

    fetch('/api/download', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(downloadData)
    })
    .then(response => response.json())
    .then(data => {
        console.log('Download started:', data);
        alert('Download started! Check the Downloads tab for progress.');
    })
    .catch(error => {
        console.error('Download error:', error);
        alert('Download failed: ' + error.message);
    });
};

window.downloadAlbum = function(url, platform) {
    console.log('Downloading album:', url, 'from platform:', platform);

    const downloadData = {
        url: url,
        platform: platform,
        type: 'album'
    };

    fetch('/api/download', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(downloadData)
    })
    .then(response => response.json())
    .then(data => {
        console.log('Download started:', data);
        alert('Download started! Check the Downloads tab for progress.');
    })
    .catch(error => {
        console.error('Download error:', error);
        alert('Download failed: ' + error.message);
    });
};

window.downloadAlbumFromFirstTrack = function(trackUrl, platform) {
    // Convert track URL to album URL for Apple Music
    const albumUrl = trackUrl.replace('/song/', '/album/');
    downloadAlbum(albumUrl, platform);
};

// Helper function to format duration
function formatDuration(seconds) {
    if (!seconds) return '';
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
}