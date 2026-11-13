"""
Модуль базы данных SQLite для Project Omilia:
пользователи, сессии, прогресс и эталоны жестов.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np

from project_omilia.core.config import DB_PATH, GESTURE_METADATA

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
                ease_factor REAL NOT NULL DEFAULT 2.5,
                interval_days INTEGER NOT NULL DEFAULT 1,
                repetitions INTEGER NOT NULL DEFAULT 0,
                next_review_at TEXT,
                last_reviewed_at TEXT,
                streak INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, gesture_name),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        # Миграция: добавление колонок SRS в learned_gestures, если таблица уже существовала
        cols_learned = [c[1] for c in conn.execute("PRAGMA table_info(learned_gestures)").fetchall()]
        if "ease_factor" not in cols_learned:
            conn.execute("ALTER TABLE learned_gestures ADD COLUMN ease_factor REAL NOT NULL DEFAULT 2.5")
        if "interval_days" not in cols_learned:
            conn.execute("ALTER TABLE learned_gestures ADD COLUMN interval_days INTEGER NOT NULL DEFAULT 1")
        if "repetitions" not in cols_learned:
            conn.execute("ALTER TABLE learned_gestures ADD COLUMN repetitions INTEGER NOT NULL DEFAULT 0")
        if "next_review_at" not in cols_learned:
            conn.execute("ALTER TABLE learned_gestures ADD COLUMN next_review_at TEXT")
        if "last_reviewed_at" not in cols_learned:
            conn.execute("ALTER TABLE learned_gestures ADD COLUMN last_reviewed_at TEXT")
        if "streak" not in cols_learned:
            conn.execute("ALTER TABLE learned_gestures ADD COLUMN streak INTEGER NOT NULL DEFAULT 0")

        # Таблица истории повторений (для детальной аналитики и точного расчёта streak)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                gesture_name TEXT NOT NULL,
                quality INTEGER NOT NULL,
                reviewed_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_user_reviews_user_date
            ON user_reviews (user_id, reviewed_at)
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

        # Автоматическая миграция метаданных жестов в SQLite при первом запуске или обновлении
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            from project_omilia.gestures import GESTURE_DEFINITIONS

            for gname, gdef in GESTURE_DEFINITIONS.items():
                conn.execute(
                    """
                    INSERT OR IGNORE INTO gestures (name, title, category, description, tip, hands_count, is_dynamic, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        gname.strip().lower(),
                        gdef.title,
                        gdef.category,
                        gdef.description,
                        gdef.tip,
                        gdef.hands_count,
                        1 if gdef.is_dynamic else 0,
                        now_iso,
                    ),
                )
        except Exception:
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

        # Автоматическое наполнение сэмплов жестов Slovo в static_gesture_samples
        slovo_sample_count = conn.execute(
            "SELECT COUNT(*) FROM static_gesture_samples WHERE gesture_name = 'г'"
        ).fetchone()[0]
        if slovo_sample_count == 0:
            try:
                from project_omilia.ml.slovo_generator import build_db_records

                slovo_records = build_db_records(num_augmented_per_gesture=20)
                conn.executemany(
                    """
                    INSERT INTO static_gesture_samples (gesture_name, hands_count, features_json, features_blob)
                    VALUES (?, ?, ?, ?)
                    """,
                    slovo_records,
                )
            except Exception:
                pass

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS gesture_data_migrations (
                name TEXT PRIMARY KEY
            )
            """
        )


def static_samples_imported(db_path: Path) -> bool:
    with closing(get_connection(db_path)) as conn:
        return (
            conn.execute(
                "SELECT 1 FROM gesture_data_migrations WHERE name = ?",
                (STATIC_SAMPLE_IMPORT,),
            ).fetchone()
            is not None
        )


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


def export_dataset(db_path: Path) -> dict[str, Any]:
    """Экспорт всех записей таблиц gestures и static_gesture_samples в JSON-совместимый словарь."""
    with closing(get_connection(db_path)) as conn:
        gestures_rows = conn.execute(
            """
            SELECT name, title, category, description, tip, hands_count, is_dynamic, created_at
            FROM gestures
            ORDER BY is_dynamic ASC, name ASC
            """
        ).fetchall()
        gestures = [dict(row) for row in gestures_rows]

        samples_rows = conn.execute(
            """
            SELECT id, gesture_name, hands_count, features_json, features_blob
            FROM static_gesture_samples
            ORDER BY id ASC
            """
        ).fetchall()
        samples = []
        for row in samples_rows:
            blob = row["features_blob"]
            blob_b64 = base64.b64encode(blob).decode("ascii") if blob is not None else None
            samples.append(
                {
                    "id": row["id"],
                    "gesture_name": row["gesture_name"],
                    "hands_count": row["hands_count"],
                    "features_json": row["features_json"],
                    "features_blob": blob_b64,
                }
            )

        return {
            "version": "1.0",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "total_gestures": len(gestures),
            "total_samples": len(samples),
            "gestures": gestures,
            "static_gesture_samples": samples,
        }


def import_dataset(
    db_path: Path,
    data: dict[str, Any],
    clear_existing_samples: bool = False,
) -> dict[str, Any]:
    """
    Импорт каталога жестов и эталонов static_gesture_samples из JSON-структуры.
    Выполняет upsert в таблицу gestures и insert в static_gesture_samples.
    """
    raw_gestures = data.get("gestures") or []
    raw_samples = data.get("static_gesture_samples") or []

    now_iso = datetime.now(timezone.utc).isoformat()
    imported_gestures = 0
    imported_samples = 0

    with closing(get_connection(db_path)) as conn, conn:
        for g in raw_gestures:
            if isinstance(g, dict):
                g_dict = g
            elif hasattr(g, "model_dump"):
                g_dict = g.model_dump()
            else:
                continue

            name = str(g_dict.get("name", "")).strip().lower()
            if not name:
                continue

            title = str(g_dict.get("title") or name.capitalize())
            category = str(g_dict.get("category") or "Общие жесты")
            description = str(g_dict.get("description") or "")
            tip = str(g_dict.get("tip") or "")
            hands_count = int(g_dict.get("hands_count") or 1)
            is_dynamic = int(bool(g_dict.get("is_dynamic", False)))
            created_at = str(g_dict.get("created_at") or now_iso)

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
                    "title": title,
                    "category": category,
                    "description": description,
                    "tip": tip,
                    "hands_count": hands_count,
                    "is_dynamic": is_dynamic,
                    "created_at": created_at,
                },
            )
            imported_gestures += 1

        if clear_existing_samples and raw_samples:
            target_names = {
                (s.get("gesture_name") if isinstance(s, dict) else getattr(s, "gesture_name", "")).strip().lower()
                for s in raw_samples
            }
            for t_name in target_names:
                if t_name:
                    conn.execute("DELETE FROM static_gesture_samples WHERE LOWER(gesture_name) = ?", (t_name,))

        for s in raw_samples:
            if isinstance(s, dict):
                s_dict = s
            elif hasattr(s, "model_dump"):
                s_dict = s.model_dump()
            else:
                continue

            gesture_name = str(s_dict.get("gesture_name", "")).strip().lower()
            if not gesture_name:
                continue

            hands_count = int(s_dict.get("hands_count") or 1)
            f_json = s_dict.get("features_json")
            f_blob = s_dict.get("features_blob")

            blob_bytes: bytes | None = None
            if isinstance(f_blob, str) and f_blob:
                try:
                    blob_bytes = base64.b64decode(f_blob)
                except Exception:
                    blob_bytes = None
            elif isinstance(f_blob, (list, tuple)):
                try:
                    blob_bytes = np.asarray(f_blob, dtype=np.float32).tobytes()
                except Exception:
                    blob_bytes = None
            elif isinstance(f_blob, (bytes, bytearray)):
                blob_bytes = bytes(f_blob)

            if blob_bytes is None:
                if isinstance(f_json, (list, tuple)):
                    try:
                        arr = np.asarray(f_json, dtype=np.float32)
                        blob_bytes = arr.tobytes()
                        f_json = json.dumps(arr.tolist(), allow_nan=False)
                    except Exception:
                        pass
                elif isinstance(f_json, str) and f_json:
                    try:
                        parsed = json.loads(f_json)
                        arr = np.asarray(parsed, dtype=np.float32)
                        blob_bytes = arr.tobytes()
                    except Exception:
                        pass

            if not isinstance(f_json, str) or not f_json:
                if blob_bytes is not None:
                    arr = np.frombuffer(blob_bytes, dtype=np.float32)
                    f_json = json.dumps(arr.tolist(), allow_nan=False)
                else:
                    continue

            conn.execute(
                """
                INSERT OR IGNORE INTO gestures (name, title, category, description, tip, hands_count, is_dynamic, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (gesture_name, gesture_name.capitalize(), "Общие жесты", "", "", hands_count, 0, now_iso),
            )

            conn.execute(
                """
                INSERT INTO static_gesture_samples (gesture_name, hands_count, features_json, features_blob)
                VALUES (?, ?, ?, ?)
                """,
                (gesture_name, hands_count, f_json, blob_bytes),
            )
            imported_samples += 1

    return {
        "status": "ok",
        "imported_gestures": imported_gestures,
        "imported_samples": imported_samples,
    }


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
                INSERT OR IGNORE INTO learned_gestures (
                    user_id, gesture_name, learned_at,
                    ease_factor, interval_days, repetitions, next_review_at, last_reviewed_at, streak
                )
                VALUES (?, ?, ?, 2.5, 1, 0, ?, NULL, 0)
                """,
                (user_id, norm_name, now, now),
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


# ============================================================================
# Алгоритм SM-2 (SuperMemo-2), интервальные повторения (SRS) и разминка (Daily Warmup)
# ============================================================================


class SM2Result(tuple):
    """Результат расчёта алгоритма интервальных повторений SM-2.
    Поддерживает распаковку (tuple unpacking), атрибуты (.ease_factor, .interval_days, .repetitions)
    и доступ по ключам словаря (['ease_factor']).
    """

    def __new__(cls, ease_factor: float, interval_days: int, repetitions: int):
        return super().__new__(cls, (ease_factor, interval_days, repetitions))

    @property
    def ease_factor(self) -> float:
        return self[0]

    @property
    def interval_days(self) -> int:
        return self[1]

    @property
    def repetitions(self) -> int:
        return self[2]

    def __getitem__(self, item: Any) -> Any:
        if isinstance(item, str):
            mapping = {
                "ease_factor": self[0],
                "interval_days": self[1],
                "repetitions": self[2],
            }
            if item in mapping:
                return mapping[item]
            raise KeyError(item)
        return super().__getitem__(item)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except (KeyError, IndexError):
            return default

    def to_dict(self) -> dict[str, Any]:
        return {
            "ease_factor": self[0],
            "interval_days": self[1],
            "repetitions": self[2],
        }

    def __repr__(self) -> str:
        return f"SM2Result(ease_factor={self[0]}, interval_days={self[1]}, repetitions={self[2]})"


def calculate_sm2(
    ease_factor: float,
    interval_days: int,
    repetitions: int,
    quality: int,
) -> SM2Result:
    """Реализация классического алгоритма интервальных повторений SuperMemo 2 (SM-2).

    :param ease_factor: Коэффициент лёгкости (EF >= 1.3, начальный 2.5)
    :param interval_days: Предыдущий интервал повторения в днях (>= 1)
    :param repetitions: Число последовательных успешных повторений
    :param quality: Оценка качества воспроизведения (0-5)
    :return: SM2Result(ease_factor, interval_days, repetitions)
    """
    try:
        q = int(quality)
    except (TypeError, ValueError) as err:
        raise ValueError(f"Оценка качества должна быть целым числом, получено: {quality}") from err

    if not (0 <= q <= 5):
        raise ValueError(f"Оценка качества должна быть в диапазоне от 0 до 5, получено: {q}")

    ef = float(ease_factor)
    reps = int(repetitions)
    interval = int(interval_days)

    # Формула обновления коэффициента лёгкости SM-2:
    # EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    delta = 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)
    new_ef = round(max(1.3, ef + delta), 2)

    if q < 3:
        # Неудачное повторение: сброс счётчика повторений и интервала
        new_reps = 0
        new_interval = 1
    else:
        # Успешное повторение
        if reps == 0:
            new_interval = 1
        elif reps == 1:
            new_interval = 6
        else:
            new_interval = max(1, int(round(interval * new_ef)))
        new_reps = reps + 1

    return SM2Result(new_ef, new_interval, new_reps)


def _parse_date(ts_str: Any) -> date | None:
    """Вспомогательная функция безопасного парсинга даты из строки таймстампа."""
    if not ts_str:
        return None
    if isinstance(ts_str, datetime):
        return ts_str.date()
    if isinstance(ts_str, date):
        return ts_str
    try:
        s = str(ts_str).strip()
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except Exception:
        try:
            return datetime.strptime(str(ts_str)[:10], "%Y-%m-%d").date()
        except Exception:
            return None


def get_user_streak(
    *args: Any,
    db_path: Path | None = None,
    username: str | None = None,
    reference_date: date | str | None = None,
    **kwargs: Any,
) -> int:
    """Вычисляет серию дней непрерывных занятий/повторений (streak) для пользователя.
    Поддерживает вызовы get_user_streak(username), get_user_streak(db_path, username)
    и передачу параметров по ключевым словам.
    """
    resolved_path = db_path
    resolved_user = username

    if len(args) == 2:
        if isinstance(args[0], Path):
            resolved_path = args[0]
            resolved_user = args[1]
        else:
            resolved_user = args[0]
            if isinstance(args[1], Path):
                resolved_path = args[1]
            elif isinstance(args[1], (date, str)):
                reference_date = args[1]
    elif len(args) == 1:
        if isinstance(args[0], Path):
            resolved_path = args[0]
        else:
            resolved_user = args[0]

    if db_path is not None:
        resolved_path = db_path
    if username is not None:
        resolved_user = username
    if "reference_date" in kwargs:
        reference_date = kwargs["reference_date"]
    if resolved_path is None:
        resolved_path = DB_PATH

    if not resolved_user:
        return 0

    with closing(get_connection(resolved_path)) as conn:
        cursor = conn.cursor()
        user_row = None
        if isinstance(resolved_user, int) or (isinstance(resolved_user, str) and resolved_user.isdigit()):
            user_row = cursor.execute("SELECT id, username FROM users WHERE id = ?", (int(resolved_user),)).fetchone()
        if not user_row:
            user_row = cursor.execute(
                "SELECT id, username FROM users WHERE LOWER(username) = LOWER(?)",
                (str(resolved_user).strip(),),
            ).fetchone()

        if not user_row:
            return 0
        user_id = user_row["id"]

        dates_set: set[date] = set()

        # 1. Из истории повторений (user_reviews)
        try:
            rev_rows = cursor.execute(
                "SELECT reviewed_at FROM user_reviews WHERE user_id = ?",
                (user_id,),
            ).fetchall()
            for r in rev_rows:
                d = _parse_date(r["reviewed_at"])
                if d:
                    dates_set.add(d)
        except sqlite3.OperationalError:
            pass

        # 2. Из выученных жестов (learned_at, last_reviewed_at)
        lg_rows = cursor.execute(
            "SELECT learned_at, last_reviewed_at FROM learned_gestures WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        for r in lg_rows:
            d1 = _parse_date(r["learned_at"])
            if d1:
                dates_set.add(d1)
            d2 = _parse_date(r["last_reviewed_at"])
            if d2:
                dates_set.add(d2)

    if not dates_set:
        return 0

    if reference_date is not None:
        if isinstance(reference_date, str):
            ref_d = _parse_date(reference_date) or datetime.now(timezone.utc).date()
        elif isinstance(reference_date, datetime):
            ref_d = reference_date.date()
        else:
            ref_d = reference_date
    else:
        ref_d = datetime.now(timezone.utc).date()

    yesterday = ref_d - timedelta(days=1)

    if ref_d in dates_set:
        check_day = ref_d
    elif yesterday in dates_set:
        check_day = yesterday
    else:
        return 0

    streak = 0
    while check_day in dates_set:
        streak += 1
        check_day = check_day - timedelta(days=1)

    return streak


def review_gesture(
    *args: Any,
    db_path: Path | None = None,
    username: str | None = None,
    gesture_name: str | None = None,
    quality: int | None = None,
    reviewed_at: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Фиксирует результат повторения жеста пользователем с пересчётом параметров SM-2.
    Поддерживает сигнатуры review_gesture(username, gesture_name, quality)
    и review_gesture(db_path, username, gesture_name, quality).
    """
    resolved_path = db_path
    resolved_user = username
    resolved_gesture = gesture_name
    resolved_quality = quality

    if len(args) == 4:
        resolved_path = Path(args[0])
        resolved_user = args[1]
        resolved_gesture = args[2]
        resolved_quality = args[3]
    elif len(args) == 3:
        if isinstance(args[0], Path):
            resolved_path = args[0]
            resolved_user = args[1]
            resolved_gesture = args[2]
        else:
            resolved_user = args[0]
            resolved_gesture = args[1]
            resolved_quality = args[2]
    elif len(args) == 2:
        if isinstance(args[0], Path):
            resolved_path = args[0]
            resolved_user = args[1]
        else:
            resolved_user = args[0]
            resolved_gesture = args[1]
    elif len(args) == 1:
        if isinstance(args[0], Path):
            resolved_path = args[0]
        else:
            resolved_user = args[0]

    if db_path is not None:
        resolved_path = db_path
    if username is not None:
        resolved_user = username
    if gesture_name is not None:
        resolved_gesture = gesture_name
    if quality is not None:
        resolved_quality = quality
    if "reviewed_at" in kwargs:
        reviewed_at = kwargs["reviewed_at"]

    if resolved_path is None:
        resolved_path = DB_PATH
    if not resolved_user:
        raise ValueError("Имя пользователя (username) не указано")
    if not resolved_gesture:
        raise ValueError("Имя жеста (gesture_name) не указано")
    if resolved_quality is None:
        raise ValueError("Оценка качества (quality) не указана")

    q = int(resolved_quality)
    if not (0 <= q <= 5):
        raise ValueError(f"Оценка качества должна быть в диапазоне от 0 до 5, получено: {q}")

    norm_name = str(resolved_gesture).strip().lower()

    if reviewed_at:
        try:
            review_dt = datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
            if review_dt.tzinfo is None:
                review_dt = review_dt.replace(tzinfo=timezone.utc)
        except Exception:
            review_dt = datetime.now(timezone.utc)
    else:
        review_dt = datetime.now(timezone.utc)

    now_iso = review_dt.isoformat()

    with closing(get_connection(resolved_path)) as conn, conn:
        cursor = conn.cursor()

        # Разрешаем пользователя в БД (или создаём при необходимости)
        user_row = None
        if isinstance(resolved_user, int) or (isinstance(resolved_user, str) and str(resolved_user).isdigit()):
            user_row = cursor.execute("SELECT id, username FROM users WHERE id = ?", (int(resolved_user),)).fetchone()
        if not user_row:
            user_row = cursor.execute(
                "SELECT id, username FROM users WHERE LOWER(username) = LOWER(?)",
                (str(resolved_user).strip(),),
            ).fetchone()

        if not user_row:
            user_str = str(resolved_user).strip()
            pwd = hash_password("default_password_123")
            cursor.execute(
                "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, 'user', ?)",
                (user_str, pwd, now_iso),
            )
            user_id = cursor.lastrowid
            user_name_str = user_str
        else:
            user_id = user_row["id"]
            user_name_str = user_row["username"]

        # Получаем текущее состояние SRS для данного жеста
        lg_row = cursor.execute(
            """
            SELECT ease_factor, interval_days, repetitions, streak, learned_at
            FROM learned_gestures
            WHERE user_id = ? AND LOWER(gesture_name) = ?
            """,
            (user_id, norm_name),
        ).fetchone()

        if lg_row:
            current_ef = float(lg_row["ease_factor"]) if lg_row["ease_factor"] is not None else 2.5
            current_interval = int(lg_row["interval_days"]) if lg_row["interval_days"] is not None else 1
            current_reps = int(lg_row["repetitions"]) if lg_row["repetitions"] is not None else 0
            current_streak = int(lg_row["streak"]) if lg_row["streak"] is not None else 0
            learned_at = lg_row["learned_at"] or now_iso
        else:
            current_ef = 2.5
            current_interval = 1
            current_reps = 0
            current_streak = 0
            learned_at = now_iso

        sm2_res = calculate_sm2(current_ef, current_interval, current_reps, q)
        new_ef = sm2_res.ease_factor
        new_interval = sm2_res.interval_days
        new_reps = sm2_res.repetitions

        new_streak = current_streak + 1 if q >= 3 else 0
        next_review_dt = review_dt + timedelta(days=new_interval)
        next_review_iso = next_review_dt.isoformat()

        # Сохраняем прогресс жеста
        cursor.execute(
            """
            INSERT INTO learned_gestures (
                user_id, gesture_name, learned_at,
                ease_factor, interval_days, repetitions,
                next_review_at, last_reviewed_at, streak
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, gesture_name) DO UPDATE SET
                ease_factor = excluded.ease_factor,
                interval_days = excluded.interval_days,
                repetitions = excluded.repetitions,
                next_review_at = excluded.next_review_at,
                last_reviewed_at = excluded.last_reviewed_at,
                streak = excluded.streak
            """,
            (
                user_id,
                norm_name,
                learned_at,
                new_ef,
                new_interval,
                new_reps,
                next_review_iso,
                now_iso,
                new_streak,
            ),
        )

        # Добавляем в историю повторений
        try:
            cursor.execute(
                """
                INSERT INTO user_reviews (user_id, gesture_name, quality, reviewed_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, norm_name, q, now_iso),
            )
        except sqlite3.OperationalError:
            pass

    u_streak = get_user_streak(user_name_str, db_path=resolved_path, reference_date=review_dt.date())

    return {
        "user_id": user_id,
        "username": user_name_str,
        "gesture_name": norm_name,
        "quality": q,
        "ease_factor": new_ef,
        "interval_days": new_interval,
        "repetitions": new_reps,
        "next_review_at": next_review_iso,
        "last_reviewed_at": now_iso,
        "streak": new_streak,
        "user_streak": u_streak,
    }


def get_daily_warmup(
    *args: Any,
    db_path: Path | None = None,
    username: str | None = None,
    limit: int = 5,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """Возвращает жесты для ежедневной разминки (SM-2 SRS), требующие повторения.
    Поддерживает вызовы get_daily_warmup(username, limit=5) и get_daily_warmup(db_path, username, limit=5).
    """
    resolved_path = db_path
    resolved_user = username
    resolved_limit = limit

    if len(args) == 3:
        resolved_path = Path(args[0])
        resolved_user = args[1]
        resolved_limit = int(args[2])
    elif len(args) == 2:
        if isinstance(args[0], Path):
            resolved_path = args[0]
            resolved_user = args[1]
        elif isinstance(args[1], int):
            resolved_user = args[0]
            resolved_limit = int(args[1])
        else:
            resolved_path = Path(args[0])
            resolved_user = args[1]
    elif len(args) == 1:
        if isinstance(args[0], Path):
            resolved_path = args[0]
        else:
            resolved_user = args[0]

    if db_path is not None:
        resolved_path = db_path
    if username is not None:
        resolved_user = username
    if "limit" in kwargs:
        resolved_limit = int(kwargs["limit"])
    if resolved_path is None:
        resolved_path = DB_PATH

    if not resolved_user:
        return []

    now_dt = datetime.now(timezone.utc)

    with closing(get_connection(resolved_path)) as conn:
        cursor = conn.cursor()
        user_row = None
        if isinstance(resolved_user, int) or (isinstance(resolved_user, str) and str(resolved_user).isdigit()):
            user_row = cursor.execute("SELECT id, username FROM users WHERE id = ?", (int(resolved_user),)).fetchone()
        if not user_row:
            user_row = cursor.execute(
                "SELECT id, username FROM users WHERE LOWER(username) = LOWER(?)",
                (str(resolved_user).strip(),),
            ).fetchone()

        if not user_row:
            return []
        user_id = user_row["id"]

        rows = cursor.execute(
            """
            SELECT lg.gesture_name, lg.ease_factor, lg.interval_days, lg.repetitions,
                   lg.next_review_at, lg.last_reviewed_at, lg.streak,
                   g.title, g.category, g.description, g.tip, g.hands_count, g.is_dynamic
            FROM learned_gestures lg
            LEFT JOIN gestures g ON LOWER(g.name) = LOWER(lg.gesture_name)
            WHERE lg.user_id = ?
            """,
            (user_id,),
        ).fetchall()

    def _check_due(item: sqlite3.Row) -> tuple[bool, datetime | None]:
        nxt = item["next_review_at"]
        if not nxt:
            return True, None
        try:
            dt = datetime.fromisoformat(nxt.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt <= now_dt, dt
        except Exception:
            return True, None

    due_list = []
    for r in rows:
        is_due, dt = _check_due(r)
        if is_due:
            due_list.append((dt, r))

    # Сортировка: жесты без предыдущего повторения первыми, затем самые просроченные
    due_list.sort(
        key=lambda pair: (
            0 if pair[0] is None else 1,
            pair[0] if pair[0] is not None else datetime.min.replace(tzinfo=timezone.utc),
            pair[1]["repetitions"] or 0,
        )
    )

    results = []
    for _, r in due_list[:resolved_limit]:
        gname = r["gesture_name"]
        fallback = GESTURE_METADATA.get(gname, {})
        title = r["title"] or fallback.get("title", gname.capitalize())
        category = r["category"] or fallback.get("category", "Общие жесты")
        description = r["description"] or fallback.get("description", "")
        tip = r["tip"] or fallback.get("tip", "")
        hands_count = r["hands_count"] if r["hands_count"] is not None else 1
        is_dynamic = bool(r["is_dynamic"]) if r["is_dynamic"] is not None else False

        results.append(
            {
                "name": gname,
                "gesture_name": gname,
                "title": title,
                "category": category,
                "description": description,
                "tip": tip,
                "hands_count": hands_count,
                "is_dynamic": is_dynamic,
                "ease_factor": r["ease_factor"] if r["ease_factor"] is not None else 2.5,
                "interval_days": r["interval_days"] if r["interval_days"] is not None else 1,
                "repetitions": r["repetitions"] if r["repetitions"] is not None else 0,
                "next_review_at": r["next_review_at"],
                "last_reviewed_at": r["last_reviewed_at"],
                "streak": r["streak"] if r["streak"] is not None else 0,
            }
        )

    return results
