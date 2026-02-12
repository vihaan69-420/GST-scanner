"""
FastAPI dependencies for authentication.
Provides get_current_user dependency that validates JWT tokens on protected routes.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any

# Will be initialized in main.py when the app starts
_jwt_handler = None
_user_db = None

security = HTTPBearer()


def init_auth(jwt_handler, user_db):
    """Initialize auth dependencies with actual instances. Called from main.py."""
    global _jwt_handler, _user_db
    _jwt_handler = jwt_handler
    _user_db = user_db


def _lazy_init():
    """Lazy-initialize auth from config if not already done."""
    global _jwt_handler, _user_db
    if _jwt_handler is not None and _user_db is not None:
        return
    try:
        import config
        from api.auth.jwt_handler import JWTHandler
        from api.auth.user_db import UserDB
        _jwt_handler = JWTHandler(
            secret=config.API_JWT_SECRET,
            algorithm=config.API_JWT_ALGORITHM,
            access_expiry_minutes=config.API_JWT_EXPIRY_MINUTES,
            refresh_expiry_days=config.API_JWT_REFRESH_EXPIRY_DAYS,
        )
        _user_db = UserDB(db_path=config.API_USER_DB_PATH)
    except Exception:
        pass


def get_jwt_handler():
    """Get the JWT handler instance."""
    _lazy_init()
    if _jwt_handler is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth system not initialized"
        )
    return _jwt_handler


def get_user_db():
    """Get the user database instance."""
    _lazy_init()
    if _user_db is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth system not initialized"
        )
    return _user_db


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """
    FastAPI dependency that validates the Bearer token and returns the current user.
    Use this on any route that requires authentication:
    
        @router.get("/protected")
        async def protected_route(user: dict = Depends(get_current_user)):
            return {"user_id": user["id"]}
    """
    jwt_handler = get_jwt_handler()
    user_db = get_user_db()

    token = credentials.credentials
    payload = jwt_handler.verify_token(token, expected_type="access")

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify user still exists and is active
    user = user_db.get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_admin(
    user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    FastAPI dependency that requires admin role.
    Use on admin-only routes:
    
        @router.get("/admin-only")
        async def admin_route(user: dict = Depends(get_current_admin)):
            ...
    """
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user
