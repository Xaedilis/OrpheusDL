// Job management functionality
console.log('Jobs module loaded');

let currentJobId = null;
let autoRefreshEnabled = true;
let autoRefreshInterval = null;

document.addEventListener('DOMContentLoaded', function() {
    // Initialize auto-refresh checkbox
    const autoRefreshCheckbox = document.getElementById('autoRefresh');
    if (autoRefreshCheckbox) {
        autoRefreshCheckbox.addEventListener('change', function() {
            autoRefreshEnabled = this.checked;
            if (autoRefreshEnabled) {
                startAutoRefresh();
            } else {
                stopAutoRefresh();
            }
        });
    }

    // Load jobs on page load
    refreshJobs();
    startAutoRefresh();
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

async function refreshJobs() {
    try {
        const response = await fetch('/api/jobs');
        const data = await response.json();

        const jobsDiv = document.getElementById('jobsResults');
        
        if (data.jobs && data.jobs.length > 0) {
            renderJobsList(data.jobs);
        } else {
            jobsDiv.innerHTML = '<p class="no-jobs">No jobs found.</p>';
        }

    } catch (error) {
        console.error('Error refreshing jobs:', error);
        document.getElementById('jobsResults').innerHTML = 
            `<p style="color: red;">Error loading jobs: ${error.message}</p>`;
    }
}

function renderJobsList(jobs) {
    const jobsDiv = document.getElementById('jobsResults');
    
    // Group jobs by status
    const groupedJobs = {
        running: jobs.filter(job => job.status === 'running' || job.status === 'pending'),
        completed: jobs.filter(job => job.status === 'completed'),
        failed: jobs.filter(job => job.status === 'failed' || job.status === 'cancelled')
    };

    let html = `<h3>Download Jobs (${jobs.length})</h3>`;

    // Render running jobs first
    if (groupedJobs.running.length > 0) {
        html += '<h4>Active Jobs</h4>';
        groupedJobs.running.forEach(job => {
            html += renderJobItem(job);
        });
    }

    // Then completed jobs
    if (groupedJobs.completed.length > 0) {
        html += '<h4>Completed Jobs</h4>';
        groupedJobs.completed.forEach(job => {
            html += renderJobItem(job);
        });
    }

    // Finally failed jobs
    if (groupedJobs.failed.length > 0) {
        html += '<h4>Failed Jobs</h4>';
        groupedJobs.failed.forEach(job => {
            html += renderJobItem(job);
        });
    }

    jobsDiv.innerHTML = html;
}

function renderJobItem(job) {
    const statusClasses = {
        'pending': 'job-pending',
        'running': 'job-running', 
        'completed': 'job-completed',
        'failed': 'job-failed',
        'cancelled': 'job-cancelled'
    };

    const statusClass = statusClasses[job.status] || 'job-unknown';
    const jobIdShort = job.job_id.substring(0, 8);
    const urlDisplay = job.url.length > 50 ? job.url.substring(0, 50) + '...' : job.url;
    const createdAt = new Date(job.created_at).toLocaleString();

    // Determine which buttons to show
    const isRunning = job.status === 'running' || job.status === 'pending';
    const isFailed = job.status === 'failed' || job.status === 'cancelled';
    const isCompleted = job.status === 'completed';

    let progressHtml = '';
    if (job.progress !== undefined && isRunning) {
        progressHtml = `
            <div class="job-progress">
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${job.progress || 0}%"></div>
                </div>
                <span class="progress-text">${job.progress || 0}%</span>
            </div>
        `;
    }

    let errorHtml = '';
    if (job.error_message) {
        errorHtml = `
            <div class="job-error">
                <p style="color: red;"><strong>Error:</strong> ${job.error_message}</p>
            </div>
        `;
    }

    return `
        <div class="job-item ${statusClass}" data-job-id="${job.job_id}">
            <div class="job-header">
                <h4>Job ${jobIdShort}...</h4>
                <span class="job-status-badge status-${job.status}">${job.status.toUpperCase()}</span>
            </div>
            <div class="job-details">
                <p><strong>Type:</strong> ${job.job_type}</p>
                <p><strong>Platform:</strong> ${job.platform || 'Unknown'}</p>
                <p><strong>URL:</strong> <span title="${job.url}">${urlDisplay}</span></p>
                <p><strong>Created:</strong> ${createdAt}</p>
                ${progressHtml}
                ${errorHtml}
            </div>
            <div class="job-actions">
                <button onclick="viewJobLogs('${job.job_id}')" class="logs-btn">View Logs</button>
                ${isRunning ? `<button onclick="cancelJob('${job.job_id}')" class="cancel-btn">Cancel</button>` : ''}
                ${isFailed ? `<button onclick="retryJob('${job.job_id}')" class="retry-btn">Retry</button>` : ''}
                ${isCompleted || isFailed ? `<button onclick="removeJob('${job.job_id}')" class="remove-btn">Remove</button>` : ''}
            </div>
        </div>
    `;
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

async function clearCompletedJobs() {
    if (confirm('Are you sure you want to clear all completed jobs?')) {
        try {
            const response = await fetch('/api/jobs/clear-completed', {
                method: 'POST'
            });
            
            if (response.ok) {
                refreshJobs();
            } else {
                throw new Error('Failed to clear completed jobs');
            }
        } catch (error) {
            console.error('Error clearing completed jobs:', error);
            alert('Error clearing completed jobs: ' + error.message);
        }
    }
}

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('jobLogsModal');
    if (event.target === modal) {
        closeJobLogsModal();
    }
}