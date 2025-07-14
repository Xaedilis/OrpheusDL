# Update your search request model
from typing import List, Optional

from pydantic import BaseModel


class SearchRequest(BaseModel):
    query: str
    platforms: List[str]
    limit: int = 20
    page: int = 1
    group_by_album: bool = False
    username: str
    password: str
    verification_code: Optional[str] = None  # Add 2FA support