"""
Pydantic models for authentication requests and responses.
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from enum import Enum


class UserRole(str, Enum):
    user = "user"
    admin = "admin"


class UserCreate(BaseModel):
    """Registration request body."""
    email: str = Field(..., min_length=3, max_length=255, description="User email address")
    password: str = Field(..., min_length=6, max_length=128, description="Password (min 6 chars)")
    full_name: str = Field(..., min_length=1, max_length=255, description="Full name")


class UserLogin(BaseModel):
    """Login request body."""
    email: str = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class TokenResponse(BaseModel):
    """Login/refresh response with JWT tokens."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Access token expiry in seconds")
    role: UserRole


class RefreshRequest(BaseModel):
    """Token refresh request body."""
    refresh_token: str = Field(..., description="Refresh token from login")


class UserProfile(BaseModel):
    """User profile response."""
    id: str
    email: str
    full_name: str
    role: UserRole
    created_at: str
    invoice_count: int = 0
    order_count: int = 0


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
    detail: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    detail: Optional[str] = None
