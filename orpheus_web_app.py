
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import os

# Import our custom modules
from OrpheusManager import OrpheusManager
from job_manager import job_manager, JobType, JobStatus
from models.AlbumSearchRequest import AlbumSearchRequest
from models.AlbumTracksRequest import AlbumTracksRequest
from models.AppleAuth2FAResponse import AppleAuth2FAResponse
from models.AppleAuthRequest import AppleAuthRequest
from models.DownloadRequest import DownloadRequest
from models.JobResponse import JobResponse
from models.MultiFormatDownloadRequest import MultiFormatDownloadRequest
from models.Searchrequest import SearchRequest
from modules.applemusic.AppleAuthHandler import apple_2fa_handler

# Initialize FastAPI app
app = FastAPI(title="Orpheus Music Downloader API", version="1.0.0")

# Create directories if they don't exist
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)
os.makedirs("templates", exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize templates
templates = Jinja2Templates(directory="templates")

# Initialize OrpheusManager
orpheus_manager = OrpheusManager()


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Root endpoint with templated HTML interface"""
    return templates.TemplateResponse(
        "index.html", 
        {"request": request}
    )


# API endpoints
@app.post("/api/search/tracks")
async def search_tracks(request: SearchRequest):
    """Search for tracks with 2FA support for Apple Music"""
    try:
        platform = request.platforms[0]

        if platform == "apple":
            # For Apple Music, check if we need 2FA
            auth_request = AppleAuthRequest(
                username=request.username,
                password=request.password,
                verification_code=request.verification_code
            )

            # This will handle the 2FA flow if needed
            auth_result = await authenticate_apple(auth_request)

            if auth_result.requires_2fa:
                raise HTTPException(
                    status_code=428,  # Precondition Required
                    detail={
                        "message": "2FA verification required",
                        "session_id": auth_result.session_id,
                        "requires_2fa": True
                    }
                )

        # Continue with normal search if auth is complete
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

    except HTTPException:
        raise
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


@app.post("/api/auth/apple", response_model=AppleAuth2FAResponse)
async def authenticate_apple(request: AppleAuthRequest):
    """Handle Apple Music authentication with 2FA support"""
    try:
        if request.verification_code and request.session_id:
            # Complete 2FA authentication
            success = apple_2fa_handler.complete_2fa_auth(
                request.session_id,
                request.verification_code
            )

            if success:
                return AppleAuth2FAResponse(
                    requires_2fa=False,
                    message="Authentication successful!"
                )
            else:
                raise HTTPException(status_code=400, detail="Invalid verification code")

        else:
            # Start initial authentication
            session_id, requires_2fa = apple_2fa_handler.start_auth_session(
                request.username,
                request.password
            )

            if requires_2fa:
                return AppleAuth2FAResponse(
                    requires_2fa=True,
                    session_id=session_id,
                    message="Please enter the verification code sent to your device"
                )
            else:
                return AppleAuth2FAResponse(
                    requires_2fa=False,
                    message="Authentication successful!"
                )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Additional job management endpoints
@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancel a running job"""
    try:
        success = job_manager.cancel_job(job_id)
        if success:
            return {"message": "Job cancelled successfully"}
        else:
            raise HTTPException(status_code=404, detail="Job not found or cannot be cancelled")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/jobs/{job_id}/retry")
async def retry_job(job_id: str):
    """Retry a failed job"""
    try:
        new_job_id = job_manager.retry_job(job_id)
        if new_job_id:
            return {"message": "Job retry started", "new_job_id": new_job_id}
        else:
            raise HTTPException(status_code=404, detail="Job not found or cannot be retried")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/jobs/{job_id}")
async def remove_job(job_id: str):
    """Remove a job from the list"""
    try:
        success = job_manager.remove_job(job_id)
        if success:
            return {"message": "Job removed successfully"}
        else:
            raise HTTPException(status_code=404, detail="Job not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/jobs/clear-completed")
async def clear_completed_jobs():
    """Clear all completed and failed jobs"""
    try:
        count = job_manager.clear_completed_jobs()
        return {"message": f"Cleared {count} completed jobs"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Run the application
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)