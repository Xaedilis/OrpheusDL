from pydantic import BaseModel


class DownloadRequest(BaseModel):
    url: str
    platform: str
    type: str