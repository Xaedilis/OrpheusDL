from pydantic import BaseModel

class AlbumTracksRequest(BaseModel):
    album_id: str
    platform: str
    username: str
    password: str