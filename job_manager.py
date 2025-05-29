import asyncio
import uuid
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum
import subprocess
import threading
import os
import json


class JobStatus(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobType(Enum):
    TRACK_DOWNLOAD = "track_download"
    ALBUM_DOWNLOAD = "album_download"


class DownloadJob:
    def __init__(self, job_id: str, job_type: JobType, url: str, platform: str, formats: List[str],
                 user_id: str = None):
        self.job_id = job_id
        self.job_type = job_type
        self.url = url
        self.platform = platform
        self.formats = formats  # Keep this for display purposes but won't use in download
        self.user_id = user_id
        self.status = JobStatus.QUEUED
        self.created_at = datetime.now()
        self.started_at = None
        self.completed_at = None
        self.error_message = None
        self.progress = 0
        self.logs = []
        self.process = None
        self.file_paths = []

    def add_log(self, message: str, level: str = "INFO"):
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message
        }
        self.logs.append(log_entry)

    def to_dict(self):
        return {
            "job_id": self.job_id,
            "job_type": self.job_type.value,
            "url": self.url,
            "platform": self.platform,
            "formats": self.formats,
            "user_id": self.user_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "progress": self.progress,
            "file_paths": self.file_paths,
            "logs_count": len(self.logs)
        }


class JobManager:
    def __init__(self):
        self.jobs: Dict[str, DownloadJob] = {}
        self.job_lock = threading.Lock()

    def create_job(self, job_type: JobType, url: str, platform: str, formats: List[str], user_id: str = None) -> str:
        job_id = str(uuid.uuid4())
        job = DownloadJob(job_id, job_type, url, platform, formats, user_id)

        with self.job_lock:
            self.jobs[job_id] = job

        job.add_log(f"Job created for {job_type.value}: {url}")
        return job_id

    def get_job(self, job_id: str) -> Optional[DownloadJob]:
        with self.job_lock:
            return self.jobs.get(job_id)

    def get_all_jobs(self, user_id: str = None) -> List[Dict]:
        with self.job_lock:
            jobs = list(self.jobs.values())
            if user_id:
                jobs = [job for job in jobs if job.user_id == user_id]
            return [job.to_dict() for job in jobs]

    def get_job_logs(self, job_id: str) -> List[Dict]:
        job = self.get_job(job_id)
        return job.logs if job else []

    def start_download_job(self, job_id: str):
        """Start a download job in the background"""

        def run_download():
            job = self.get_job(job_id)
            if not job:
                return

            try:
                job.status = JobStatus.RUNNING
                job.started_at = datetime.now()
                job.add_log("Starting download...")

                # Path to the orpheus.py script
                orpheus_script_path = os.path.join(os.getcwd(), "orpheus.py")

                if not os.path.exists(orpheus_script_path):
                    raise Exception(f"orpheus.py script not found at {orpheus_script_path}")

                # Simply run orpheus.py with the URL - formats are configured in OrpheusManager config
                job.add_log(f"Starting download for {job.job_type.value}")
                job.add_log(f"URL: {job.url}")
                job.add_log("Note: Formats are configured in OrpheusManager config folder")

                # Build simple command with just the URL
                cmd = ["python", orpheus_script_path, job.url]

                job.add_log(f"Running command: {' '.join(cmd)}")

                # Start the process
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=os.getcwd()
                )

                job.process = process

                # Monitor the process
                stdout, stderr = process.communicate()

                if process.returncode == 0:
                    job.add_log("Download completed successfully")
                    job.add_log(f"Output: {stdout}")

                    # Try to extract file path from output
                    if "Downloaded to:" in stdout:
                        file_path = stdout.split("Downloaded to:")[-1].strip()
                        job.file_paths.append(file_path)
                        job.add_log(f"File saved to: {file_path}")

                    # Look for other common output patterns that indicate successful download
                    if "Download completed" in stdout or "Successfully downloaded" in stdout:
                        job.add_log("Download verification: Success indicators found in output")

                else:
                    job.add_log("Download failed", "ERROR")
                    job.add_log(f"Error output: {stderr}", "ERROR")
                    job.add_log(f"Return code: {process.returncode}", "ERROR")
                    raise Exception(f"Download process failed with return code {process.returncode}: {stderr}")

                job.status = JobStatus.COMPLETED
                job.completed_at = datetime.now()
                job.progress = 100
                job.add_log("Job completed successfully")

            except Exception as e:
                job.status = JobStatus.FAILED
                job.completed_at = datetime.now()
                job.error_message = str(e)
                job.add_log(f"Job failed: {str(e)}", "ERROR")

        # Start the download in a separate thread
        thread = threading.Thread(target=run_download)
        thread.daemon = True
        thread.start()


# Global job manager instance
job_manager = JobManager()