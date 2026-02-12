"""
JWT token creation, verification, and refresh logic.
Uses PyJWT with HS256 algorithm.
"""
import jwt
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any


class JWTHandler:
    """Handles JWT token creation and verification."""

    def __init__(self, secret: str, algorithm: str = "HS256",
                 access_expiry_minutes: int = 30,
                 refresh_expiry_days: int = 7):
        if not secret:
            raise ValueError("API_JWT_SECRET must be set when API is enabled")
        self.secret = secret
        self.algorithm = algorithm
        self.access_expiry_minutes = access_expiry_minutes
        self.refresh_expiry_days = refresh_expiry_days

    def create_access_token(self, user_id: str, email: str, role: str) -> str:
        """Create a short-lived access token."""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": user_id,
            "email": email,
            "role": role,
            "type": "access",
            "iat": now,
            "exp": now + timedelta(minutes=self.access_expiry_minutes),
            "jti": str(uuid.uuid4()),
        }
        return jwt.encode(payload, self.secret, algorithm=self.algorithm)

    def create_refresh_token(self, user_id: str, email: str, role: str) -> str:
        """Create a long-lived refresh token."""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": user_id,
            "email": email,
            "role": role,
            "type": "refresh",
            "iat": now,
            "exp": now + timedelta(days=self.refresh_expiry_days),
            "jti": str(uuid.uuid4()),
        }
        return jwt.encode(payload, self.secret, algorithm=self.algorithm)

    def create_token_pair(self, user_id: str, email: str, role: str) -> Dict[str, Any]:
        """Create both access and refresh tokens."""
        return {
            "access_token": self.create_access_token(user_id, email, role),
            "refresh_token": self.create_refresh_token(user_id, email, role),
            "token_type": "bearer",
            "expires_in": self.access_expiry_minutes * 60,
            "role": role,
        }

    def verify_token(self, token: str, expected_type: str = "access") -> Optional[Dict[str, Any]]:
        """
        Verify and decode a JWT token.
        
        Returns:
            Decoded payload dict if valid, None if invalid/expired.
        """
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
            if payload.get("type") != expected_type:
                return None
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def refresh_access_token(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """
        Verify a refresh token and issue a new access token.
        
        Returns:
            New token pair dict if refresh token is valid, None otherwise.
        """
        payload = self.verify_token(refresh_token, expected_type="refresh")
        if not payload:
            return None
        return self.create_token_pair(
            user_id=payload["sub"],
            email=payload["email"],
            role=payload["role"],
        )
