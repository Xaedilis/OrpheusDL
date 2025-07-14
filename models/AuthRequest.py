# Pydantic models for request/response validation
from pydantic import BaseModel


class AuthRequest(BaseModel):
    platform: str
    username: str
    password: str