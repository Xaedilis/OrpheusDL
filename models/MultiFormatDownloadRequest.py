from typing import List, Optional

from pydantic import BaseModel


class MultiFormatDownloadRequest(BaseModel):
    url: str
    platform: str
    type: str  # "track" or "album"
    formats: List[str] = ["configured"]  # Placeholder - formats come from config
    user_id: Optional[str] = None