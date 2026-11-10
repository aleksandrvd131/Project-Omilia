"""
Модуль базы данных SQLite для Project Omilia:
пользователи, сессии, прогресс и эталоны жестов.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np

SCRYPT_N = 16384
SCRYPT_R = 8
SCRYPT_P = 1
STATIC_SAMPLE_IMPORT = "static_json_v1"


def hash_password(password: str) -> str:
    """Генерация криптостойкого хэша пароля с индивидуальной случайной солью (Scrypt, RFC 7914)."""
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Безопасная проверка пароля с защитой от атак по времени (timing attacks).
    Поддерживает современный формат Scrypt и плавную миграцию устаревших хэшей SHA-256."""
    if not stored_hash or not password:
        return False

    if stored_hash.startswith("scrypt$"):
        try:
            parts = stored_hash.split("$")
            if len(parts) != 6:
                return False
            n, r, p = int(parts[1]), int(parts[2]), int(parts[3])
            salt = bytes.fromhex(parts[4])
            expected_hash = parts[5]
            derived = hashlib.scrypt(
                password.encode("utf-8"),
                salt=salt,
                n=n,
                r=r,
                p=p,
            ).hex()
            return secrets.compare_digest(derived, expected_hash)
        except Exception:
            return False

    # Обратная совместимость с устаревшими хэшами SHA-256
    legacy_salt = "omilia_salt_2026"
    legacy_hash = hashlib.sha256((password + legacy_salt).encode("utf-8")).hexdigest()
    return secrets.compare_digest(legacy_hash, stored_hash)


def _hash_password(password: str) -> str:
    """Псевдоним для обратной совместимости."""
    return hash_password(password)


def get_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path) -> None:
    """Инициализация таблиц базы данных и безопасные миграции схемы."""
    with closing(get_connection(db_path)) as conn, conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TEXT NOT NULL
            )
            """
        )
        # Миграция: добавление колонки role, если таблица users уже существовала
        cols_users = [c[1] for c in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "role" not in cols_users:
            conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
            # Назначаем первого пользователя администратором
            conn.execute(
                """
                UPDATE users SET role = 'admin'
                WHERE id = (SELECT id FROM users ORDER BY id ASC LIMIT 1)
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
                expires_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        # Миграция: добавление колонки expires_at, если таблица sessions уже существовала
        cols_sessions = [c[1] for c in conn.execute("PRAGMA table_info(sessions)").fetchall()]
        if "expires_at" not in cols_sessions:
            conn.execute("ALTER TABLE sessions ADD COLUMN expires_at TEXT")
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
                features_json TEXT NOT NULL,
                features_blob BLOB
            )
            """
        )
        # Миграция: добавление бинарной колонки features_blob BLOB, если таблица уже существовала
        cols_static = [c[1] for c in conn.execute("PRAGMA table_info(static_gesture_samples)").fetchall()]
        if "features_blob" not in cols_static:
            conn.execute("ALTER TABLE static_gesture_samples ADD COLUMN features_blob BLOB")

        # Миграция существующих записей features_json -> features_blob для максимальной скорости чтения
        null_blob_rows = conn.execute(
            "SELECT id, features_json FROM static_gesture_samples WHERE features_blob IS NULL"
        ).fetchall()
        for row in null_blob_rows:
            try:
                vec = np.asarray(json.loads(row["features_json"]), dtype=np.float32)
                conn.execute(
                    "UPDATE static_gesture_samples SET features_blob = ? WHERE id = ?",
                    (vec.tobytes(), row["id"]),
                )
            except Exception:
                pass

        # Таблица каталога жестов (заменяет статические JSON и словари в коде)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS gestures (
                name TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                tip TEXT NOT NULL,
                hands_count INTEGER NOT NULL DEFAULT 1,
                is_dynamic INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )

        # Автоматическая миграция базовых метаданных жестов в SQLite при первом запуске
        gesture_count = conn.execute("SELECT COUNT(*) FROM gestures").fetchone()[0]
        if gesture_count == 0:
            now_iso = datetime.now(timezone.utc).isoformat()
            from project_omilia.core.config import GESTURE_METADATA
            for gname, meta in GESTURE_METADATA.items():
                conn.execute(
                    """
                    INSERT OR IGNORE INTO gestures (name, title, category, description, tip, hands_count, is_dynamic, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        gname.strip().lower(),
                        meta.get("title", gname.capitalize()),
                        meta.get("category", "Общие жесты"),
                        meta.get("description", ""),
                        meta.get("tip", ""),
                        1,
                        0,
                        now_iso,
                    ),
                )
            # Добавляем жесты из static_gesture_samples, которых могло не быть в словаре
            static_names = [
                r[0] for r in conn.execute("SELECT DISTINCT gesture_name FROM static_gesture_samples").fetchall()
            ]
            for sname in static_names:
                sname_clean = sname.strip().lower()
                conn.execute(
                    """
                    INSERT OR IGNORE INTO gestures (name, title, category, description, tip, hands_count, is_dynamic, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sname_clean,
                        sname_clean.capitalize(),
                        "Общие жесты",
                        f"Статический жест «{sname_clean}».",
                        "Повторите положение кисти перед камерой.",
                        1,
                        0,
                        now_iso,
                    ),
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


def import_static_samples(db_path: Path, samples: list[tuple]) -> None:
    with closing(get_connection(db_path)) as conn, conn:
        claimed = conn.execute(
            "INSERT OR IGNORE INTO gesture_data_migrations (name) VALUES (?)",
            (STATIC_SAMPLE_IMPORT,),
        )
        if claimed.rowcount:
            _insert_static_samples(conn, samples)


def _insert_static_samples(conn: sqlite3.Connection, samples: list[tuple]) -> None:
    prepared = []
    for item in samples:
        name = item[0]
        hands = item[1]
        f_json = item[2]
        f_blob = item[3] if len(item) > 3 else None

        if f_blob is None and f_json:
            try:
                vec = np.asarray(json.loads(f_json), dtype=np.float32)
                f_blob = vec.tobytes()
            except Exception:
                f_blob = None
        elif f_blob is not None and not f_json:
            arr = np.frombuffer(f_blob, dtype=np.float32)
            f_json = json.dumps(arr.tolist(), allow_nan=False)

        prepared.append((name, hands, f_json, f_blob))

    conn.executemany(
        """
        INSERT INTO static_gesture_samples (gesture_name, hands_count, features_json, features_blob)
        VALUES (?, ?, ?, ?)
        """,
        prepared,
    )


def insert_static_samples(db_path: Path, samples: list[tuple]) -> None:
    with closing(get_connection(db_path)) as conn, conn:
        _insert_static_samples(conn, samples)


def get_static_samples(db_path: Path, hands_count: int) -> list[sqlite3.Row]:
    """Возвращает эталоны статических жестов (с бинарным blob и json)."""
    with closing(get_connection(db_path)) as conn:
        return conn.execute(
            """
            SELECT gesture_name, features_blob, features_json FROM static_gesture_samples
            WHERE hands_count = ? ORDER BY id
            """,
            (hands_count,),
        ).fetchall()


def get_all_gestures(db_path: Path) -> list[dict[str, Any]]:
    """Возвращает каталог всех жестов из SQLite таблицы gestures."""
    with closing(get_connection(db_path)) as conn:
        rows = conn.execute("SELECT * FROM gestures ORDER BY is_dynamic ASC, name ASC").fetchall()
        return [dict(row) for row in rows]


def get_gesture(db_path: Path, name: str) -> dict[str, Any] | None:
    """Возвращает метаданные жеста по его имени."""
    with closing(get_connection(db_path)) as conn:
        row = conn.execute("SELECT * FROM gestures WHERE LOWER(name) = LOWER(?)", (name.strip(),)).fetchone()
        return dict(row) if row else None


def upsert_gesture(db_path: Path, data: dict[str, Any]) -> None:
    """Создаёт или обновляет жест в базе данных."""
    now_iso = datetime.now(timezone.utc).isoformat()
    name = data["name"].strip().lower()
    with closing(get_connection(db_path)) as conn, conn:
        conn.execute(
            """
            INSERT INTO gestures (name, title, category, description, tip, hands_count, is_dynamic, created_at)
            VALUES (:name, :title, :category, :description, :tip, :hands_count, :is_dynamic, :created_at)
            ON CONFLICT(name) DO UPDATE SET
                title = excluded.title,
                category = excluded.category,
                description = excluded.description,
                tip = excluded.tip,
                hands_count = excluded.hands_count,
                is_dynamic = excluded.is_dynamic
            """,
            {
                "name": name,
                "title": data.get("title", name.capitalize()),
                "category": data.get("category", "Общие жесты"),
                "description": data.get("description", ""),
                "tip": data.get("tip", ""),
                "hands_count": int(data.get("hands_count", 1)),
                "is_dynamic": int(bool(data.get("is_dynamic", False))),
                "created_at": data.get("created_at", now_iso),
            },
        )


def delete_gesture(db_path: Path, gesture_name: str) -> None:
    """Полное удаление жеста из каталога, эталонов и прогресса пользователей."""
    norm_name = gesture_name.strip().lower()
    with closing(get_connection(db_path)) as conn, conn:
        conn.execute("DELETE FROM gestures WHERE LOWER(name) = ?", (norm_name,))
        conn.execute("DELETE FROM static_gesture_samples WHERE LOWER(gesture_name) = ?", (norm_name,))
        conn.execute("DELETE FROM dynamic_gesture_samples WHERE LOWER(gesture_name) = ?", (norm_name,))
        conn.execute("DELETE FROM learned_gestures WHERE LOWER(TRIM(gesture_name)) = ?", (norm_name,))


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
            SELECT
                gesture_name AS name,
                gesture_name,
                hands_count AS hands,
                hands_count,
                COUNT(*) AS count,
                COUNT(*) AS samples_count
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
    """Регистрация нового пользователя с безопасным хэшированием Scrypt."""
    username = username.strip()
    if len(username) < 3:
        return None, "Логин должен быть не короче 3 символов"
    if len(password) < 6:
        return None, "Пароль должен содержать минимум 6 символов для безопасности"

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    pwd_hash = hash_password(password)

    try:
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            # Назначаем первого зарегистрированного пользователя администратором
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            role = "admin" if user_count == 0 or username.lower() == "admin" else "user"

            cursor.execute(
                "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                (username, pwd_hash, role, now_iso),
            )
            user_id = cursor.lastrowid
            token = secrets.token_hex(32)
            expires_at = (now + timedelta(days=14)).isoformat()
            cursor.execute(
                "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (token, user_id, now_iso, expires_at),
            )
            conn.commit()
            return {
                "id": user_id,
                "username": username,
                "role": role,
                "token": token,
                "expires_at": expires_at,
            }, None
    except sqlite3.IntegrityError:
        return None, "Пользователь с таким логином уже существует"
    except Exception as e:
        return None, f"Ошибка базы данных: {e}"


def login_user(db_path: Path, username: str, password: str) -> tuple[dict[str, Any] | None, str | None]:
    """Аутентификация пользователя по логину и паролю с поддержкой плавного апгрейда хэша."""
    username = username.strip()

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, password_hash, role FROM users WHERE username = ?",
            (username,),
        )
        row = cursor.fetchone()
        if not row or not verify_password(password, row["password_hash"]):
            return None, "Неверный логин или пароль"

        user_id = row["id"]
        # Автоматический апгрейд устаревшего хэша пароля SHA-256 до Scrypt
        if not row["password_hash"].startswith("scrypt$"):
            new_hash = hash_password(password)
            cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id))

        token = secrets.token_hex(32)
        now = datetime.now(timezone.utc)
        expires_at = (now + timedelta(days=14)).isoformat()
        cursor.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, user_id, now.isoformat(), expires_at),
        )
        conn.commit()
        return {
            "id": user_id,
            "username": row["username"],
            "role": row["role"] if "role" in row.keys() else "user",
            "token": token,
            "expires_at": expires_at,
        }, None


def get_user_by_token(db_path: Path, token: str) -> dict[str, Any] | None:
    """Получение данных пользователя по токену сессии с проверкой срока действия (14 дней)."""
    if not token:
        return None
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT u.id, u.username, u.role, u.created_at, s.expires_at
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token = ?
            """,
            (token,),
        )
        row = cursor.fetchone()
        if row:
            if row["expires_at"] and row["expires_at"] < now_iso:
                # Сессия истекла — удаляем её
                cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
                conn.commit()
                return None
            return {
                "id": row["id"],
                "username": row["username"],
                "role": row["role"] if "role" in row.keys() else "user",
                "created_at": row["created_at"],
            }
    return None


def has_admin_access(db_path: Path, token: str | None) -> bool:
    """Проверяет права администратора.
    Если в БД ещё нет зарегистрированных пользователей (первичный запуск), доступ разрешён."""
    with get_connection(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count == 0:
            return True
    if not token:
        return False
    user = get_user_by_token(db_path, token)
    return bool(user and user.get("role") == "admin")


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
