from typing import List

from pydantic import BaseModel


class AlbumSearchRequest(BaseModel):
    query: str
    platforms: List[str]
    limit: int = 10
    username: str
    password: str