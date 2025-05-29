from typing import Optional
from pydantic import BaseModel


class AppleAuthRequest(BaseModel):
    username: str
    password: str
    verification_code: Optional[str] = None  # For 2FA
    session_id: Optional[str] = None  # To track auth sessions
