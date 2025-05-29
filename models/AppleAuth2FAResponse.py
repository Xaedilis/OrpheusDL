from typing import Optional
from pydantic import BaseModel


class AppleAuth2FAResponse(BaseModel):
    requires_2fa: bool = False
    session_id: Optional[str] = None
    message: str
