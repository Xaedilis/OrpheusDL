// Search functionality
console.log('Search module loaded');

let currentSearchData = null;

document.addEventListener('DOMContentLoaded', function () {
    const platformSelect = document.getElementById('platform');
    const usernameGroup = document.getElementById('usernameGroup');
    const passwordGroup = document.getElementById('passwordGroup');
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');
    const cookieNotice = document.getElementById('cookieNotice');
    const searchForm = document.getElementById('searchForm');

    // Handle platform selection changes
    platformSelect.addEventListener('change', function () {
        const selectedPlatform = this.value;

        if (selectedPlatform === 'applemusic') {
            // Gray out and disable username/password fields for Apple Music
            usernameGroup.style.opacity = '0.5';
            passwordGroup.style.opacity = '0.5';
            usernameInput.disabled = true;
            passwordInput.disabled = true;
            usernameInput.required = false;
            passwordInput.required = false;
            usernameInput.value = 'cookies'; // Placeholder value
            passwordInput.value = 'cookies'; // Placeholder value
            cookieNotice.style.display = 'block';
        } else {
            // Enable username/password fields for other platforms
            usernameGroup.style.opacity = '1';
            passwordGroup.style.opacity = '1';
            usernameInput.disabled = false;
            passwordInput.disabled = false;
            usernameInput.required = true;
            passwordInput.required = true;
            usernameInput.value = '';
            passwordInput.value = '';
            cookieNotice.style.display = 'none';
        }
    });

    // Initialize the form based on the default platform
    platformSelect.dispatchEvent(new Event('change'));

    // Handle form submission
    searchForm.addEventListener('submit', function (e) {
        e.preventDefault();

        const formData = {
            query: document.getElementById('searchQuery').value,
            platforms: [platformSelect.value],
            username: usernameInput.value,
            password: passwordInput.value,
            page: 1,
            limit: parseInt(document.getElementById('limit').value),
            group_by_album: false
        };

        const searchType = document.getElementById('searchType').value;

        // Clear previous results
        clearResults();

        // Show loading
        showLoading();

        if (searchType === 'tracks') {
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
            displayTrackResults(data);
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
            const platformSelect = document.getElementById('platform');
            const currentPlatform = platformSelect ? platformSelect.value : 'applemusic';

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
        if (!resultsDiv) return;

        if (!data.albums || data.albums.length === 0) {
            resultsDiv.innerHTML = '<div class="no-results">No albums found</div>';
            return;
        }

        let html = '<div class="results-section"><h3>Album Results</h3>';

        data.albums.forEach(album => {
            html += `
                <div class="result-item">
                    <div class="result-info">
                        <strong>${album.name}</strong><br>
                        by ${album.artist}<br>
                        <small>Year: ${album.year || 'Unknown'}</small>
                    </div>
                    <div class="result-actions">
                        <button onclick="downloadAlbum('${album.url}', '${platformSelect.value}')" class="download-btn">
                            Download Album
                        </button>
                    </div>
                </div>
            `;
        });

        html += '</div>';
        resultsDiv.innerHTML = html;
    }

    // Make download functions global
    window.downloadTrack = function (url, platform) {
        downloadContent(url, platform, 'track');
    };

    window.downloadAlbum = function (url, platform) {
        downloadContent(url, platform, 'album');
    };

    async function downloadContent(url, platform, type) {
        try {
            const response = await fetch('/api/download/multi-format', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    url: url,
                    platform: platform,
                    type: type,
                    formats: ['configured'],
                    user_id: 'web_user'
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            showSuccess(`Download started! Job ID: ${data.job_id}`);

            // Refresh jobs list if available
            if (typeof refreshJobs === 'function') {
                refreshJobs();
            }
        } catch (error) {
            showError('Download failed: ' + error.message);
        }
    }

    function showSuccess(message) {
        // You can implement a success notification here
        alert(message);
    }
});