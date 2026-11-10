from pathlib import Path
import tempfile
import time
from datetime import datetime, timedelta, timezone

from project_omilia import db


def test_password_hashing_and_verification():
    raw_pwd = "SuperSecretPassword123"
    pwd_hash = db.hash_password(raw_pwd)
    assert pwd_hash.startswith("scrypt$")
    assert db.verify_password(raw_pwd, pwd_hash) is True
    assert db.verify_password("WrongPassword", pwd_hash) is False
    assert db.verify_password("", pwd_hash) is False


def test_legacy_password_compatibility():
    # Legacy SHA-256 hash using legacy salt "omilia_salt_2026"
    import hashlib
    raw_pwd = "OldPassword2026"
    legacy_salt = "omilia_salt_2026"
    legacy_hash = hashlib.sha256((raw_pwd + legacy_salt).encode("utf-8")).hexdigest()

    # Must verify legacy hash successfully
    assert db.verify_password(raw_pwd, legacy_hash) is True
    assert db.verify_password("WrongOldPassword", legacy_hash) is False


def test_user_registration_roles_and_sessions():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = Path(tmpdir) / "test_omilia.db"
        db.init_db(test_db)

        # 1. First user should become admin
        admin_user, err = db.register_user(test_db, "alice_admin", "AdminPass123")
        assert err is None
        assert admin_user is not None
        assert admin_user["role"] == "admin"
        assert "token" in admin_user
        assert db.has_admin_access(test_db, admin_user["token"]) is True

        # 2. Second user should become regular user
        bob_user, err = db.register_user(test_db, "bob_user", "BobPass123")
        assert err is None
        assert bob_user is not None
        assert bob_user["role"] == "user"
        assert db.has_admin_access(test_db, bob_user["token"]) is False

        # 3. Password length validation
        short_user, err = db.register_user(test_db, "short_pwd", "123")
        assert short_user is None
        assert "минимум 6 символов" in err

        # 4. Login and verify token
        logged_user, err = db.login_user(test_db, "alice_admin", "AdminPass123")
        assert err is None
        assert logged_user["role"] == "admin"

        # Verify get_user_by_token
        verified = db.get_user_by_token(test_db, logged_user["token"])
        assert verified is not None
        assert verified["username"] == "alice_admin"
        assert verified["role"] == "admin"


def test_session_expiration():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = Path(tmpdir) / "test_omilia.db"
        db.init_db(test_db)

        user, _ = db.register_user(test_db, "test_exp", "ExpPass123")
        token = user["token"]

        # Manually expire the session in the DB
        expired_time = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        with db.get_connection(test_db) as conn:
            conn.execute("UPDATE sessions SET expires_at = ? WHERE token = ?", (expired_time, token))
            conn.commit()

        # Should return None because session expired
        assert db.get_user_by_token(test_db, token) is None
        assert db.has_admin_access(test_db, token) is False
