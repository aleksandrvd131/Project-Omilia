"""
Модуль базы данных SQLite для Project Omilia:
пользователи, сессии, прогресс и эталоны жестов.
"""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SALT = "omilia_salt_2026"
STATIC_SAMPLE_IMPORT = "static_json_v1"


def _hash_password(password: str) -> str:
    return hashlib.sha256((password + SALT).encode("utf-8")).hexdigest()


def get_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path) -> None:
    """Инициализация таблиц базы данных."""
    with closing(get_connection(db_path)) as conn, conn:
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
                gesture_name TEXT COLLATE NOCASE NOT NULL,
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dynamic_gesture_samples (
                id INTEGER PRIMARY KEY,
                gesture_name TEXT NOT NULL,
                hands_count INTEGER NOT NULL CHECK (hands_count IN (1, 2)),
                sequence_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS dynamic_gesture_samples_by_gesture
            ON dynamic_gesture_samples (gesture_name, hands_count, id)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS static_gesture_samples (
                id INTEGER PRIMARY KEY,
                gesture_name TEXT NOT NULL,
                hands_count INTEGER NOT NULL CHECK (hands_count IN (1, 2)),
                features_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS gesture_data_migrations (
                name TEXT PRIMARY KEY
            )
            """
        )


def static_samples_imported(db_path: Path) -> bool:
    with closing(get_connection(db_path)) as conn:
        return conn.execute(
            "SELECT 1 FROM gesture_data_migrations WHERE name = ?",
            (STATIC_SAMPLE_IMPORT,),
        ).fetchone() is not None


def import_static_samples(db_path: Path, samples: list[tuple[str, int, str]]) -> None:
    with closing(get_connection(db_path)) as conn, conn:
        claimed = conn.execute(
            "INSERT OR IGNORE INTO gesture_data_migrations (name) VALUES (?)",
            (STATIC_SAMPLE_IMPORT,),
        )
        if claimed.rowcount:
            _insert_static_samples(conn, samples)


def _insert_static_samples(conn: sqlite3.Connection, samples: list[tuple[str, int, str]]) -> None:
    conn.executemany(
        """
        INSERT INTO static_gesture_samples (gesture_name, hands_count, features_json)
        VALUES (?, ?, ?)
        """,
        samples,
    )


def insert_static_samples(db_path: Path, samples: list[tuple[str, int, str]]) -> None:
    with closing(get_connection(db_path)) as conn, conn:
        _insert_static_samples(conn, samples)


def get_static_samples(db_path: Path, hands_count: int) -> list[sqlite3.Row]:
    with closing(get_connection(db_path)) as conn:
        return conn.execute(
            """
            SELECT gesture_name, features_json FROM static_gesture_samples
            WHERE hands_count = ? ORDER BY id
            """,
            (hands_count,),
        ).fetchall()


def delete_static_gesture(db_path: Path, gesture_name: str) -> None:
    with closing(get_connection(db_path)) as conn, conn:
        deleted = conn.execute("DELETE FROM static_gesture_samples WHERE gesture_name = ?", (gesture_name,))
        if deleted.rowcount:
            conn.execute(
                """
                DELETE FROM learned_gestures
                WHERE LOWER(TRIM(gesture_name)) = ? AND NOT EXISTS (
                    SELECT 1 FROM dynamic_gesture_samples WHERE gesture_name = ?
                )
                """,
                (gesture_name, gesture_name),
            )


def list_dynamic_samples(db_path: Path) -> list[dict[str, Any]]:
    with closing(get_connection(db_path)) as conn:
        rows = conn.execute(
            """
            SELECT gesture_name AS name, hands_count AS hands, COUNT(*) AS count
            FROM dynamic_gesture_samples
            GROUP BY gesture_name, hands_count
            ORDER BY gesture_name, hands_count
            """
        ).fetchall()
    return [dict(row) for row in rows]


def insert_dynamic_sample(
    db_path: Path,
    gesture_name: str,
    hands_count: int,
    sequence_json: str,
    *,
    limit: int,
) -> int:
    with closing(get_connection(db_path)) as conn, conn:
        # Проверка лимита и вставка должны пройти в одной транзакции.
        conn.execute("BEGIN IMMEDIATE")
        count = conn.execute(
            """
            SELECT COUNT(*) FROM dynamic_gesture_samples
            WHERE gesture_name = ? AND hands_count = ?
            """,
            (gesture_name, hands_count),
        ).fetchone()[0]
        if count >= limit:
            raise ValueError(f"Для жеста «{gesture_name}» уже записано {limit} эталонов.")

        conn.execute(
            """
            INSERT INTO dynamic_gesture_samples (gesture_name, hands_count, sequence_json)
            VALUES (?, ?, ?)
            """,
            (gesture_name, hands_count, sequence_json),
        )
        return count + 1


def get_dynamic_samples(db_path: Path, gesture_name: str, hands_count: int) -> list[str]:
    with closing(get_connection(db_path)) as conn:
        rows = conn.execute(
            """
            SELECT sequence_json FROM dynamic_gesture_samples
            WHERE gesture_name = ? AND hands_count = ?
            ORDER BY id
            """,
            (gesture_name, hands_count),
        ).fetchall()
    return [row["sequence_json"] for row in rows]


def count_dynamic_samples(db_path: Path, gesture_name: str, hands_count: int) -> int:
    with closing(get_connection(db_path)) as conn:
        return conn.execute(
            """
            SELECT COUNT(*) FROM dynamic_gesture_samples
            WHERE gesture_name = ? AND hands_count = ?
            """,
            (gesture_name, hands_count),
        ).fetchone()[0]


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
    norm_name = gesture_name.strip().lower()
    if not norm_name:
        return False
    now = datetime.now(timezone.utc).isoformat()
    try:
        with get_connection(db_path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO learned_gestures (user_id, gesture_name, learned_at)
                VALUES (?, ?, ?)
                """,
                (user_id, norm_name, now),
            )
            conn.commit()
            return True
    except Exception:
        return False


def get_learned_gestures(db_path: Path, user_id: int) -> list[str]:
    """Возвращает уникальный список всех выученных пользователем жестов."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT DISTINCT LOWER(gesture_name) AS gesture_name
            FROM learned_gestures
            WHERE user_id = ?
            ORDER BY learned_at ASC
            """,
            (user_id,),
        )
        return [row["gesture_name"] for row in cursor.fetchall()]
