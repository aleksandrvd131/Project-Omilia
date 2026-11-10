"""
Тесты безопасности и аутентификации (Scrypt, RFC 7914, миграция хэшей, сессии).
"""

import hashlib
import tempfile
from pathlib import Path

from project_omilia import db


def test_password_hashing_scrypt_format():
    pwd = "secret_password_123"
    hashed = db.hash_password(pwd)
    assert hashed.startswith("scrypt$16384$8$1$")
    assert db.verify_password(pwd, hashed) is True
    assert db.verify_password("wrong_password", hashed) is False


def test_legacy_sha256_password_migration():
    pwd = "legacy_user_pass"
    legacy_salt = "omilia_salt_2026"
    legacy_hash = hashlib.sha256((pwd + legacy_salt).encode("utf-8")).hexdigest()

    assert not legacy_hash.startswith("scrypt$")
    assert db.verify_password(pwd, legacy_hash) is True
    assert db.verify_password("wrong_pwd", legacy_hash) is False


def test_user_registration_and_login_flow():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        db_path = Path(tmp.name)
        db.init_db(db_path)

        # Регистрация первого пользователя (становится admin)
        user_data, err = db.register_user(db_path, "admin_user", "super_secret_123")
        assert err is None
        assert user_data is not None
        assert user_data["username"] == "admin_user"
        assert user_data["role"] == "admin"
        assert len(user_data["token"]) == 64

        # Проверка получения пользователя по токену
        fetched = db.get_user_by_token(db_path, user_data["token"])
        assert fetched is not None
        assert fetched["username"] == "admin_user"
        assert fetched["role"] == "admin"

        # Проверка успешного логина
        logged_in, err = db.login_user(db_path, "admin_user", "super_secret_123")
        assert err is None
        assert logged_in is not None
        assert logged_in["username"] == "admin_user"

        # Неверный пароль
        failed_login, err = db.login_user(db_path, "admin_user", "wrong_pass")
        assert logged_in is not None
        assert err == "Неверный логин или пароль"
        assert failed_login is None

        # Выход из системы
        db.logout_user(db_path, user_data["token"])
        assert db.get_user_by_token(db_path, user_data["token"]) is None
