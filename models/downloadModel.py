from unittest.mock import Base

from sqlalchemy import Column, Integer, String, DateTime, JSON

class Download(Base):
    id = Column(Integer, primary_key=True)
    user_id = Column(String)
    track_id = Column(String)
    platform = Column(String)
    title = Column(String)
    artist = Column(String)
    status = Column(String)  # queued, downloading, completed, failed
    file_path = Column(String)
    metadata = Column(JSON)
    created_at = Column(DateTime)