"""
Standalone tests for the FastAPI auth layer.
Tests JWT handler, user database, and auth endpoints.
All test artifacts use temp directories and are cleaned up after.
"""
import os
import sys
import tempfile
import shutil
import unittest
from pathlib import Path

# Ensure src/ is on path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'src'))


class TestJWTHandler(unittest.TestCase):
    """Test JWT token creation and verification."""

    def setUp(self):
        from api.auth.jwt_handler import JWTHandler
        self.handler = JWTHandler(
            secret="test-secret-key-for-jwt-testing-only",
            algorithm="HS256",
            access_expiry_minutes=1,
            refresh_expiry_days=1,
        )

    def test_create_access_token(self):
        token = self.handler.create_access_token("user-1", "test@test.com", "user")
        self.assertIsInstance(token, str)
        self.assertTrue(len(token) > 0)

    def test_verify_access_token(self):
        token = self.handler.create_access_token("user-1", "test@test.com", "user")
        payload = self.handler.verify_token(token, expected_type="access")
        self.assertIsNotNone(payload)
        self.assertEqual(payload["sub"], "user-1")
        self.assertEqual(payload["email"], "test@test.com")
        self.assertEqual(payload["role"], "user")
        self.assertEqual(payload["type"], "access")

    def test_verify_refresh_token(self):
        token = self.handler.create_refresh_token("user-1", "test@test.com", "admin")
        payload = self.handler.verify_token(token, expected_type="refresh")
        self.assertIsNotNone(payload)
        self.assertEqual(payload["sub"], "user-1")
        self.assertEqual(payload["role"], "admin")
        self.assertEqual(payload["type"], "refresh")

    def test_wrong_type_rejected(self):
        access = self.handler.create_access_token("user-1", "test@test.com", "user")
        result = self.handler.verify_token(access, expected_type="refresh")
        self.assertIsNone(result)

    def test_invalid_token_rejected(self):
        result = self.handler.verify_token("not-a-real-token", expected_type="access")
        self.assertIsNone(result)

    def test_token_pair(self):
        pair = self.handler.create_token_pair("user-1", "test@test.com", "user")
        self.assertIn("access_token", pair)
        self.assertIn("refresh_token", pair)
        self.assertEqual(pair["token_type"], "bearer")
        self.assertEqual(pair["role"], "user")
        self.assertEqual(pair["expires_in"], 60)  # 1 min * 60 sec

    def test_refresh_access_token(self):
        pair = self.handler.create_token_pair("user-1", "test@test.com", "user")
        new_pair = self.handler.refresh_access_token(pair["refresh_token"])
        self.assertIsNotNone(new_pair)
        self.assertIn("access_token", new_pair)

    def test_empty_secret_raises(self):
        from api.auth.jwt_handler import JWTHandler
        with self.assertRaises(ValueError):
            JWTHandler(secret="")


class TestUserDB(unittest.TestCase):
    """Test SQLite user database."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="gst_api_test_userdb_")
        self.db_path = os.path.join(self.temp_dir, "test_users.db")
        from api.auth.user_db import UserDB
        self.db = UserDB(db_path=self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_user(self):
        user = self.db.create_user("test@test.com", "password123", "Test User")
        self.assertIsNotNone(user)
        self.assertEqual(user["email"], "test@test.com")
        self.assertEqual(user["full_name"], "Test User")
        self.assertEqual(user["role"], "user")

    def test_duplicate_email_rejected(self):
        self.db.create_user("test@test.com", "password123", "Test User")
        duplicate = self.db.create_user("test@test.com", "other_pass", "Other Name")
        self.assertIsNone(duplicate)

    def test_authenticate_success(self):
        self.db.create_user("test@test.com", "password123", "Test User")
        user = self.db.authenticate("test@test.com", "password123")
        self.assertIsNotNone(user)
        self.assertEqual(user["email"], "test@test.com")

    def test_authenticate_wrong_password(self):
        self.db.create_user("test@test.com", "password123", "Test User")
        user = self.db.authenticate("test@test.com", "wrong_password")
        self.assertIsNone(user)

    def test_authenticate_unknown_email(self):
        user = self.db.authenticate("nobody@test.com", "password123")
        self.assertIsNone(user)

    def test_get_user_by_id(self):
        created = self.db.create_user("test@test.com", "password123", "Test User")
        user = self.db.get_user_by_id(created["id"])
        self.assertIsNotNone(user)
        self.assertEqual(user["email"], "test@test.com")

    def test_get_user_by_email(self):
        self.db.create_user("test@test.com", "password123", "Test User")
        user = self.db.get_user_by_email("test@test.com")
        self.assertIsNotNone(user)
        self.assertEqual(user["full_name"], "Test User")

    def test_email_case_insensitive(self):
        self.db.create_user("Test@Test.com", "password123", "Test User")
        user = self.db.authenticate("test@test.com", "password123")
        self.assertIsNotNone(user)

    def test_increment_invoice_count(self):
        created = self.db.create_user("test@test.com", "password123", "Test User")
        self.db.increment_invoice_count(created["id"])
        user = self.db.get_user_by_id(created["id"])
        self.assertEqual(user["invoice_count"], 1)

    def test_increment_order_count(self):
        created = self.db.create_user("test@test.com", "password123", "Test User")
        self.db.increment_order_count(created["id"])
        self.db.increment_order_count(created["id"])
        user = self.db.get_user_by_id(created["id"])
        self.assertEqual(user["order_count"], 2)

    def test_password_is_hashed(self):
        """Ensure password is not stored in plaintext."""
        import sqlite3
        self.db.create_user("test@test.com", "password123", "Test User")
        conn = sqlite3.connect(self.db_path)
        row = conn.execute("SELECT password_hash FROM api_users WHERE email = 'test@test.com'").fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertNotEqual(row[0], "password123")
        self.assertTrue(row[0].startswith("$2b$"))  # bcrypt prefix


class TestAuthEndpoints(unittest.TestCase):
    """Test FastAPI auth endpoints using TestClient."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="gst_api_test_endpoints_")

        # Set config before importing
        os.environ["FEATURE_API_ENABLED"] = "true"
        os.environ["API_JWT_SECRET"] = "test-secret-for-endpoint-testing"
        os.environ["API_USER_DB_PATH"] = os.path.join(self.temp_dir, "test_users.db")
        os.environ["API_JWT_EXPIRY_MINUTES"] = "5"

        # Reset auth dependencies (they may have been initialized by a previous test)
        import api.auth.dependencies as deps
        deps._jwt_handler = None
        deps._user_db = None

        # Reload config so it picks up the new env vars
        import importlib
        import config
        importlib.reload(config)

        # Import after env is set
        from api.main import create_app
        from fastapi.testclient import TestClient
        self.app = create_app()
        self.client = TestClient(self.app)

    def tearDown(self):
        # Reset auth dependencies
        import api.auth.dependencies as deps
        deps._jwt_handler = None
        deps._user_db = None

        shutil.rmtree(self.temp_dir, ignore_errors=True)
        # Clean up env
        for key in ["FEATURE_API_ENABLED", "API_JWT_SECRET", "API_USER_DB_PATH", "API_JWT_EXPIRY_MINUTES"]:
            os.environ.pop(key, None)

    def test_root(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["service"], "GST Scanner API")

    def test_register_success(self):
        res = self.client.post("/auth/register", json={
            "email": "new@test.com",
            "password": "SecurePass1",
            "full_name": "New User",
        })
        self.assertEqual(res.status_code, 201)
        self.assertIn("message", res.json())

    def test_register_duplicate(self):
        self.client.post("/auth/register", json={
            "email": "dup@test.com", "password": "SecurePass1", "full_name": "User",
        })
        res = self.client.post("/auth/register", json={
            "email": "dup@test.com", "password": "SecurePass1", "full_name": "User",
        })
        self.assertEqual(res.status_code, 409)

    def test_login_success(self):
        self.client.post("/auth/register", json={
            "email": "login@test.com", "password": "SecurePass1", "full_name": "User",
        })
        res = self.client.post("/auth/login", json={
            "email": "login@test.com", "password": "SecurePass1",
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("access_token", data)
        self.assertIn("refresh_token", data)
        self.assertEqual(data["token_type"], "bearer")

    def test_login_wrong_password(self):
        self.client.post("/auth/register", json={
            "email": "login@test.com", "password": "SecurePass1", "full_name": "User",
        })
        res = self.client.post("/auth/login", json={
            "email": "login@test.com", "password": "WrongPass1",
        })
        self.assertEqual(res.status_code, 401)

    def test_me_with_token(self):
        self.client.post("/auth/register", json={
            "email": "me@test.com", "password": "SecurePass1", "full_name": "Me User",
        })
        login = self.client.post("/auth/login", json={
            "email": "me@test.com", "password": "SecurePass1",
        })
        token = login.json()["access_token"]
        res = self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["email"], "me@test.com")
        self.assertEqual(data["full_name"], "Me User")

    def test_me_without_token(self):
        res = self.client.get("/auth/me")
        # FastAPI HTTPBearer returns 403 when header is missing entirely
        self.assertIn(res.status_code, [401, 403])

    def test_refresh_token(self):
        self.client.post("/auth/register", json={
            "email": "ref@test.com", "password": "SecurePass1", "full_name": "User",
        })
        login = self.client.post("/auth/login", json={
            "email": "ref@test.com", "password": "SecurePass1",
        })
        refresh = login.json()["refresh_token"]
        res = self.client.post("/auth/refresh", json={"refresh_token": refresh})
        self.assertEqual(res.status_code, 200)
        self.assertIn("access_token", res.json())

    def test_health_no_auth(self):
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "healthy")

    def test_swagger_docs(self):
        res = self.client.get("/docs")
        self.assertEqual(res.status_code, 200)

    def test_openapi_json(self):
        res = self.client.get("/openapi.json")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["info"]["title"], "GST Scanner API")
        # Verify key paths exist
        self.assertIn("/auth/login", data["paths"])
        self.assertIn("/auth/register", data["paths"])
        self.assertIn("/invoices/upload", data["paths"])
        self.assertIn("/orders", data["paths"])
        self.assertIn("/health", data["paths"])


if __name__ == "__main__":
    unittest.main()
