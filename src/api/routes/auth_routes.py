"""
Authentication routes - register, login, refresh, profile.
"""
from fastapi import APIRouter, HTTPException, status, Depends

from api.auth.models import (
    UserCreate, UserLogin, TokenResponse, RefreshRequest,
    UserProfile, MessageResponse, ErrorResponse,
)
from api.auth.dependencies import get_jwt_handler, get_user_db, get_current_user

router = APIRouter()


@router.post(
    "/register",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}},
    summary="Register a new user",
)
async def register(body: UserCreate):
    """
    Register a new user account.
    
    - **email**: Must be unique
    - **password**: Minimum 6 characters
    - **full_name**: User's display name
    """
    user_db = get_user_db()
    user = user_db.create_user(
        email=body.email,
        password=body.password,
        full_name=body.full_name,
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )
    return MessageResponse(
        message="Registration successful",
        detail=f"User {user['email']} created. You can now login.",
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={401: {"model": ErrorResponse}},
    summary="Login and get JWT tokens",
)
async def login(body: UserLogin):
    """
    Authenticate with email and password.
    
    Returns:
    - **access_token**: Short-lived token for API calls (30 min default)
    - **refresh_token**: Long-lived token to get new access tokens (7 days default)
    - **role**: User role (user or admin)
    
    Use the access_token as `Authorization: Bearer <token>` header.
    """
    user_db = get_user_db()
    jwt_handler = get_jwt_handler()

    user = user_db.authenticate(email=body.email, password=body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token_data = jwt_handler.create_token_pair(
        user_id=user["id"],
        email=user["email"],
        role=user["role"],
    )
    return TokenResponse(**token_data)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    responses={401: {"model": ErrorResponse}},
    summary="Refresh an expired access token",
)
async def refresh(body: RefreshRequest):
    """
    Use a valid refresh token to get a new access token.
    
    Call this when your access_token expires (HTTP 401).
    """
    jwt_handler = get_jwt_handler()

    token_data = jwt_handler.refresh_access_token(body.refresh_token)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token. Please login again.",
        )
    return TokenResponse(**token_data)


@router.get(
    "/me",
    response_model=UserProfile,
    summary="Get current user profile",
)
async def get_profile(user: dict = Depends(get_current_user)):
    """
    Get the authenticated user's profile.
    
    Requires a valid access token in the Authorization header.
    """
    return UserProfile(**user)
