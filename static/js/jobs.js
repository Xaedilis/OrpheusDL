// Job management functionality
console.log('Jobs module loaded');

let currentJobId = null;
let autoRefreshEnabled = true;
let autoRefreshInterval = null;

// Initialize when page loads
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, starting jobs auto-refresh');
    startJobsAutoRefresh();
});

// Stop auto-refresh when page is hidden/closed
document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
        stopJobsAutoRefresh();
    } else {
        startJobsAutoRefresh();
    }
});


function startAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
    }
    if (autoRefreshEnabled) {
        autoRefreshInterval = setInterval(refreshJobs, 10000);
    }
}

function stopAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
    }
}

// Global variable to store the refresh interval
let jobsRefreshInterval = null;

// Function to fetch and display jobs
async function refreshJobs() {
    try {
        console.log('Fetching jobs...');
        const response = await fetch('/api/jobs');

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        console.log('Jobs data received:', data);

        renderJobsList(data.jobs || []);

    } catch (error) {
        console.error('Failed to fetch jobs:', error);
        document.getElementById('jobsResults').innerHTML =
            `<h3>Download Jobs</h3><p style="color: red;">Error loading jobs: ${error.message}</p>`;
    }
}



// Function to render the jobs list
function renderJobsList(jobs) {
    const jobsDiv = document.getElementById('jobsResults');

    if (!jobsDiv) {
        console.error('jobsResults element not found');
        return;
    }

    // Group jobs by status
    const groupedJobs = {
        running: jobs.filter(job => job.status === 'running' || job.status === 'queued'),
        completed: jobs.filter(job => job.status === 'completed'),
        failed: jobs.filter(job => job.status === 'failed')
    };

    let html = `<h3>Download Jobs (${jobs.length})</h3>`;

    // Add clear completed jobs button if there are completed or failed jobs
    if (groupedJobs.completed.length > 0 || groupedJobs.failed.length > 0) {
        html += `
            <div style="margin-bottom: 15px;">
                <button onclick="clearCompletedJobs()" class="btn btn-warning btn-sm">
                    Clear Completed Jobs
                </button>
            </div>
        `;
    }

    // Render running jobs first
    if (groupedJobs.running.length > 0) {
        html += '<h4>🔄 Active Jobs</h4>';
        groupedJobs.running.forEach(job => {
            html += renderJobItem(job);
        });
    }

    // Then completed jobs
    if (groupedJobs.completed.length > 0) {
        html += '<h4>✅ Completed Jobs</h4>';
        groupedJobs.completed.forEach(job => {
            html += renderJobItem(job);
        });
    }

    // Finally failed jobs
    if (groupedJobs.failed.length > 0) {
        html += '<h4>❌ Failed Jobs</h4>';
        groupedJobs.failed.forEach(job => {
            html += renderJobItem(job);
        });
    }

    // Show message if no jobs
    if (jobs.length === 0) {
        html += '<p>No download jobs found.</p>';
    }

    jobsDiv.innerHTML = html;
}


// Function to render individual job item
function renderJobItem(job) {
    const statusBadge = getStatusBadge(job.status);
    const timeInfo = getTimeInfo(job);

    return `
        <div class="job-item" style="border: 1px solid #ddd; padding: 10px; margin: 10px 0; border-radius: 5px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <strong>${job.job_type.replace('_', ' ').toUpperCase()}</strong>
                    ${statusBadge}
                </div>
                <div style="text-align: right;">
                    <small style="color: #666;">${timeInfo}</small>
                </div>
            </div>
            
            <div style="margin-top: 5px;">
                <small><strong>URL:</strong> ${job.url}</small><br>
                <small><strong>Platform:</strong> ${job.platform}</small>
            </div>
            
            ${job.error_message ? `
                <div style="margin-top: 5px; color: red;">
                    <small><strong>Error:</strong> ${job.error_message}</small>
                </div>
            ` : ''}
            
            ${job.file_paths && job.file_paths.length > 0 ? `
                <div style="margin-top: 5px;">
                    <small><strong>Files:</strong></small>
                    <ul style="margin: 0; padding-left: 20px;">
                        ${job.file_paths.map(path => `<li><small>${path}</small></li>`).join('')}
                    </ul>
                </div>
            ` : ''}
            
            <div style="margin-top: 10px;">
                <button onclick="viewJobLogs('${job.job_id}')" class="btn btn-info btn-sm">
                    View Logs (${job.logs_count || 0})
                </button>
            </div>
        </div>
    `;
}

// Function to get status badge
function getStatusBadge(status) {
    const badges = {
        'queued': '<span style="background: #ffc107; color: black; padding: 2px 6px; border-radius: 3px; font-size: 0.8em;">QUEUED</span>',
        'running': '<span style="background: #007bff; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8em;">RUNNING</span>',
        'completed': '<span style="background: #28a745; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8em;">COMPLETED</span>',
        'failed': '<span style="background: #dc3545; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8em;">FAILED</span>'
    };
    return badges[status] || `<span style="background: #6c757d; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8em;">${status.toUpperCase()}</span>`;
}

// Function to get time information
function getTimeInfo(job) {
    const created = new Date(job.created_at);
    const now = new Date();
    const elapsed = Math.floor((now - created) / 1000 / 60); // minutes

    if (job.completed_at) {
        const completed = new Date(job.completed_at);
        const duration = Math.floor((completed - created) / 1000 / 60);
        return `Completed in ${duration}m`;
    } else if (job.started_at) {
        return `Running for ${elapsed}m`;
    } else {
        return `Queued ${elapsed}m ago`;
    }
}


async function viewJobLogs(jobId) {
    currentJobId = jobId;

    try {
        const response = await fetch(`/api/jobs/${jobId}/logs`);
        const data = await response.json();

        document.getElementById('logsJobId').textContent = jobId.substring(0, 8) + '...';

        // Get job status
        const jobResponse = await fetch(`/api/jobs/${jobId}`);
        const jobData = await jobResponse.json();
        document.getElementById('logsJobStatus').textContent = jobData.status.toUpperCase();

        displayJobLogs(data.logs);
        document.getElementById('jobLogsModal').style.display = 'block';

    } catch (error) {
        console.error('Error getting job logs:', error);
        alert('Error getting job logs: ' + error.message);
    }
}

function displayJobLogs(logs) {
    const logsContent = document.getElementById('jobLogsContent');

    if (!logs || logs.length === 0) {
        logsContent.innerHTML = '<p>No logs available.</p>';
        return;
    }

    let logsHtml = '<div class="logs-list">';
    logs.forEach(log => {
        const timestamp = new Date(log.timestamp).toLocaleTimeString();
        const levelClass = `log-${log.level.toLowerCase()}`;
        logsHtml += `
            <div class="log-entry ${levelClass}">
                <span class="log-timestamp">${timestamp}</span>
                <span class="log-level">[${log.level}]</span>
                <span class="log-message">${log.message}</span>
            </div>
        `;
    });
    logsHtml += '</div>';

    logsContent.innerHTML = logsHtml;

    // Auto-scroll to bottom if enabled
    if (document.getElementById('autoScrollLogs').checked) {
        logsContent.scrollTop = logsContent.scrollHeight;
    }
}

async function refreshJobLogs() {
    if (currentJobId) {
        try {
            const response = await fetch(`/api/jobs/${currentJobId}/logs`);
            const data = await response.json();
            displayJobLogs(data.logs);
        } catch (error) {
            console.error('Error refreshing logs:', error);
        }
    }
}

function downloadJobLogs() {
    if (currentJobId) {
        const logsContent = document.getElementById('jobLogsContent').textContent;
        const blob = new Blob([logsContent], { type: 'text/plain' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `job-${currentJobId}-logs.txt`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    }
}

function closeJobLogsModal() {
    document.getElementById('jobLogsModal').style.display = 'none';
    currentJobId = null;
}

async function cancelJob(jobId) {
    if (confirm('Are you sure you want to cancel this job?')) {
        try {
            const response = await fetch(`/api/jobs/${jobId}/cancel`, {
                method: 'POST'
            });

            if (response.ok) {
                refreshJobs();
            } else {
                throw new Error('Failed to cancel job');
            }
        } catch (error) {
            console.error('Error cancelling job:', error);
            alert('Error cancelling job: ' + error.message);
        }
    }
}

async function retryJob(jobId) {
    try {
        const response = await fetch(`/api/jobs/${jobId}/retry`, {
            method: 'POST'
        });

        if (response.ok) {
            refreshJobs();
        } else {
            throw new Error('Failed to retry job');
        }
    } catch (error) {
        console.error('Error retrying job:', error);
        alert('Error retrying job: ' + error.message);
    }
}

async function removeJob(jobId) {
    if (confirm('Are you sure you want to remove this job?')) {
        try {
            const response = await fetch(`/api/jobs/${jobId}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                refreshJobs();
            } else {
                throw new Error('Failed to remove job');
            }
        } catch (error) {
            console.error('Error removing job:', error);
            alert('Error removing job: ' + error.message);
        }
    }
}

// Function to clear completed jobs
async function clearCompletedJobs() {
    if (confirm('Are you sure you want to clear all completed jobs?')) {
        try {
            const response = await fetch('/api/jobs/clear-completed', {
                method: 'POST'
            });

            if (response.ok) {
                const result = await response.json();
                console.log('Jobs cleared:', result);
                await refreshJobs(); // Refresh the job list
            } else {
                throw new Error('Failed to clear completed jobs');
            }
        } catch (error) {
            console.error('Error clearing completed jobs:', error);
            alert('Error clearing completed jobs: ' + error.message);
        }
    }
}

// Function to start auto-refresh
function startJobsAutoRefresh() {
    // Clear existing interval if any
    if (jobsRefreshInterval) {
        clearInterval(jobsRefreshInterval);
    }

    // Initial load
    refreshJobs();

    // Set up auto-refresh every 5 seconds
    jobsRefreshInterval = setInterval(refreshJobs, 5000);
    console.log('Jobs auto-refresh started');
}
// Function to stop auto-refresh
function stopJobsAutoRefresh() {
    if (jobsRefreshInterval) {
        clearInterval(jobsRefreshInterval);
        jobsRefreshInterval = null;
        console.log('Jobs auto-refresh stopped');
    }
}


// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('jobLogsModal');
    if (event.target === modal) {
        closeJobLogsModal();
    }
}