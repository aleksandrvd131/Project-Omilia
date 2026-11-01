"""
Модуль базы данных SQLite для Project Omilia:
хранение пользователей, авторизация и отслеживание выученных жестов.
"""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SALT = "omilia_salt_2026"


def _hash_password(password: str) -> str:
    return hashlib.sha256((password + SALT).encode("utf-8")).hexdigest()


def get_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path) -> None:
    """Инициализация таблиц базы данных."""
    with get_connection(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS learned_gestures (
                user_id INTEGER NOT NULL,
                gesture_name TEXT NOT NULL,
                learned_at TEXT NOT NULL,
                PRIMARY KEY (user_id, gesture_name),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        conn.commit()


def register_user(db_path: Path, username: str, password: str) -> tuple[dict[str, Any] | None, str | None]:
    """Регистрация нового пользователя."""
    username = username.strip()
    if len(username) < 3:
        return None, "Логин должен быть не короче 3 символов"
    if len(password) < 4:
        return None, "Пароль должен быть не короче 4 символов"

    now = datetime.now(timezone.utc).isoformat()
    pwd_hash = _hash_password(password)

    try:
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                (username, pwd_hash, now),
            )
            user_id = cursor.lastrowid
            token = secrets.token_hex(24)
            cursor.execute(
                "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
                (token, user_id, now),
            )
            conn.commit()
            return {"id": user_id, "username": username, "token": token}, None
    except sqlite3.IntegrityError:
        return None, "Пользователь с таким логином уже существует"
    except Exception as e:
        return None, f"Ошибка базы данных: {e}"


def login_user(db_path: Path, username: str, password: str) -> tuple[dict[str, Any] | None, str | None]:
    """Аутентификация пользователя по логину и паролю."""
    username = username.strip()
    pwd_hash = _hash_password(password)

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        )
        row = cursor.fetchone()
        if not row or row["password_hash"] != pwd_hash:
            return None, "Неверный логин или пароль"

        user_id = row["id"]
        token = secrets.token_hex(24)
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
            (token, user_id, now),
        )
        conn.commit()
        return {"id": user_id, "username": row["username"], "token": token}, None


def get_user_by_token(db_path: Path, token: str) -> dict[str, Any] | None:
    """Получение данных пользователя по токену сессии."""
    if not token:
        return None
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT u.id, u.username, u.created_at
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token = ?
            """,
            (token,),
        )
        row = cursor.fetchone()
        if row:
            return {"id": row["id"], "username": row["username"], "created_at": row["created_at"]}
    return None


def logout_user(db_path: Path, token: str) -> None:
    """Удаление сессии при выходе."""
    if not token:
        return
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()


def mark_gesture_learned(db_path: Path, user_id: int, gesture_name: str) -> bool:
    """Фиксация жеста как успешно выученного пользователем."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        with get_connection(db_path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO learned_gestures (user_id, gesture_name, learned_at)
                VALUES (?, ?, ?)
                """,
                (user_id, gesture_name.strip(), now),
            )
            conn.commit()
            return True
    except Exception:
        return False


def get_learned_gestures(db_path: Path, user_id: int) -> list[str]:
    """Возвращает список всех выученных пользователем жестов."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT gesture_name FROM learned_gestures WHERE user_id = ? ORDER BY learned_at ASC",
            (user_id,),
        )
        return [row["gesture_name"] for row in cursor.fetchall()]
