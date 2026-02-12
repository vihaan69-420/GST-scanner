"""
SQLite-based user store for API authentication.
Stores users with bcrypt-hashed passwords.
Separate from the Next.js better-sqlite3 DB - this is Python-side only.
"""
import sqlite3
import uuid
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pathlib import Path

import bcrypt as _bcrypt


class UserDB:
    """SQLite user database for API authentication."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        # Ensure parent directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get a new connection (sqlite3 connections are not thread-safe)."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        """Create the users table if it doesn't exist."""
        conn = self._get_conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS api_users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    invoice_count INTEGER DEFAULT 0,
                    order_count INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def create_user(self, email: str, password: str, full_name: str,
                    role: str = "user") -> Optional[Dict[str, Any]]:
        """
        Register a new user.
        
        Returns:
            User dict if created, None if email already exists.
        """
        conn = self._get_conn()
        try:
            now = datetime.now(timezone.utc).isoformat()
            user_id = str(uuid.uuid4())
            password_hash = _bcrypt.hashpw(
                password.encode("utf-8"), _bcrypt.gensalt()
            ).decode("utf-8")

            conn.execute(
                """INSERT INTO api_users (id, email, password_hash, full_name, role, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, email.lower().strip(), password_hash, full_name.strip(), role, now, now)
            )
            conn.commit()
            return {
                "id": user_id,
                "email": email.lower().strip(),
                "full_name": full_name.strip(),
                "role": role,
                "created_at": now,
                "invoice_count": 0,
                "order_count": 0,
            }
        except sqlite3.IntegrityError:
            # Email already exists
            return None
        finally:
            conn.close()

    def authenticate(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Verify email + password.
        
        Returns:
            User dict if credentials are valid, None otherwise.
        """
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM api_users WHERE email = ? AND is_active = 1",
                (email.lower().strip(),)
            ).fetchone()

            if not row:
                return None

            if not _bcrypt.checkpw(
                password.encode("utf-8"),
                row["password_hash"].encode("utf-8"),
            ):
                return None

            return {
                "id": row["id"],
                "email": row["email"],
                "full_name": row["full_name"],
                "role": row["role"],
                "created_at": row["created_at"],
                "invoice_count": row["invoice_count"],
                "order_count": row["order_count"],
            }
        finally:
            conn.close()

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Look up a user by ID."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM api_users WHERE id = ? AND is_active = 1",
                (user_id,)
            ).fetchone()

            if not row:
                return None

            return {
                "id": row["id"],
                "email": row["email"],
                "full_name": row["full_name"],
                "role": row["role"],
                "created_at": row["created_at"],
                "invoice_count": row["invoice_count"],
                "order_count": row["order_count"],
            }
        finally:
            conn.close()

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Look up a user by email."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM api_users WHERE email = ? AND is_active = 1",
                (email.lower().strip(),)
            ).fetchone()

            if not row:
                return None

            return {
                "id": row["id"],
                "email": row["email"],
                "full_name": row["full_name"],
                "role": row["role"],
                "created_at": row["created_at"],
                "invoice_count": row["invoice_count"],
                "order_count": row["order_count"],
            }
        finally:
            conn.close()

    def increment_invoice_count(self, user_id: str) -> None:
        """Increment a user's invoice count."""
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE api_users SET invoice_count = invoice_count + 1, updated_at = ? WHERE id = ?",
                (datetime.now(timezone.utc).isoformat(), user_id)
            )
            conn.commit()
        finally:
            conn.close()

    def increment_order_count(self, user_id: str) -> None:
        """Increment a user's order count."""
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE api_users SET order_count = order_count + 1, updated_at = ? WHERE id = ?",
                (datetime.now(timezone.utc).isoformat(), user_id)
            )
            conn.commit()
        finally:
            conn.close()
