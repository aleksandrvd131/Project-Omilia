"""
Тесты для модуля интервального повторения (SM-2 SRS) и ежедневной разминки (Daily Warmup).
Проверяют алгоритм SM-2, схему и миграции SQLite, расчёт серий (streak),
сервисы review_gesture / get_daily_warmup и REST API эндпоинты.
"""

from __future__ import annotations

import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from project_omilia import db
from project_omilia.app import create_app

# ============================================================================
# 1. Тесты алгоритма SM-2 (calculate_sm2)
# ============================================================================


def test_calculate_sm2_validation():
    """Проверка валидации входных параметров качества quality."""
    with pytest.raises(ValueError):
        db.calculate_sm2(2.5, 1, 0, -1)

    with pytest.raises(ValueError):
        db.calculate_sm2(2.5, 1, 0, 6)

    with pytest.raises(ValueError):
        db.calculate_sm2(2.5, 1, 0, "не_число")  # type: ignore


def test_calculate_sm2_progression():
    """Проверка классической прогрессии SM-2 при успешных повторениях (q >= 3)."""
    # Первое успешное повторение (repetitions=0 -> 1, interval=1)
    res1 = db.calculate_sm2(ease_factor=2.5, interval_days=1, repetitions=0, quality=5)
    assert res1.ease_factor == 2.6  # 2.5 + (0.1 - 0) = 2.6
    assert res1.interval_days == 1
    assert res1.repetitions == 1

    # Второе успешное повторение (repetitions=1 -> 2, interval=6)
    res2 = db.calculate_sm2(
        ease_factor=res1.ease_factor, interval_days=res1.interval_days, repetitions=res1.repetitions, quality=4
    )
    assert res2.ease_factor == 2.6  # 2.6 + (0.1 - 0.1) = 2.6
    assert res2.interval_days == 6
    assert res2.repetitions == 2

    # Третье успешное повторение (repetitions=2 -> 3, interval=round(6 * 2.7)=16)
    res3 = db.calculate_sm2(
        ease_factor=res2.ease_factor, interval_days=res2.interval_days, repetitions=res2.repetitions, quality=5
    )
    assert res3.ease_factor == 2.7  # 2.6 + 0.1 = 2.7
    assert res3.interval_days == int(round(6 * 2.7))
    assert res3.repetitions == 3


def test_calculate_sm2_failure_and_clamp():
    """Проверка сброса интервала и повторений при ошибке (q < 3) и ограничения EF >= 1.3."""
    # Неудачное повторение сбрасывает interval=1 и repetitions=0
    res_fail = db.calculate_sm2(ease_factor=2.7, interval_days=16, repetitions=3, quality=2)
    assert res_fail.repetitions == 0
    assert res_fail.interval_days == 1
    assert res_fail.ease_factor < 2.7

    # Проверка клампинга ease_factor (не может опуститься ниже 1.3)
    ef = 1.4
    for _ in range(5):
        res_low = db.calculate_sm2(ease_factor=ef, interval_days=1, repetitions=0, quality=0)
        ef = res_low.ease_factor
    assert ef == 1.3


def test_calculate_sm2_return_types():
    """Проверка совместимости возвращаемого SM2Result: распаковка кортежа, атрибуты, индексация."""
    res = db.calculate_sm2(2.5, 1, 0, 5)

    # Распаковка кортежа
    ef, interval, reps = res
    assert ef == 2.6
    assert interval == 1
    assert reps == 1

    # Доступ по индексу
    assert res[0] == 2.6
    assert res[1] == 1
    assert res[2] == 1

    # Доступ по атрибутам
    assert res.ease_factor == 2.6
    assert res.interval_days == 1
    assert res.repetitions == 1

    # Доступ по строковым ключам
    assert res["ease_factor"] == 2.6
    assert res["interval_days"] == 1
    assert res["repetitions"] == 1

    # to_dict
    d = res.to_dict()
    assert d == {"ease_factor": 2.6, "interval_days": 1, "repetitions": 1}


# ============================================================================
# 2. Тесты схемы базы данных и миграции
# ============================================================================


def test_db_schema_learned_gestures():
    """Проверка наличия всех SRS-полей в таблице learned_gestures при первичной инициализации."""
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        db_path = Path(tmp.name)
        db.init_db(db_path)

        with db.get_connection(db_path) as conn:
            cols = {c[1]: c[2] for c in conn.execute("PRAGMA table_info(learned_gestures)").fetchall()}
            assert "ease_factor" in cols
            assert "interval_days" in cols
            assert "repetitions" in cols
            assert "next_review_at" in cols
            assert "last_reviewed_at" in cols
            assert "streak" in cols


def test_db_migration_from_legacy_learned_gestures():
    """Проверка безопасной миграции устаревшей таблицы learned_gestures без SRS-колонок."""
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        db_path = Path(tmp.name)
        # Создаём старую схему вручную
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE learned_gestures (
                    user_id INTEGER NOT NULL,
                    gesture_name TEXT NOT NULL,
                    learned_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, gesture_name)
                )
                """
            )
            conn.execute(
                "INSERT INTO users (id, username, password_hash, created_at) VALUES (1, 'legacy_user', 'hash', '2026-01-01')"
            )
            conn.execute(
                "INSERT INTO learned_gestures (user_id, gesture_name, learned_at) VALUES (1, 'привет', '2026-01-01')"
            )
            conn.commit()

        # Запускаем init_db, выполняющий автомиграцию
        db.init_db(db_path)

        with db.get_connection(db_path) as conn:
            cols = [c[1] for c in conn.execute("PRAGMA table_info(learned_gestures)").fetchall()]
            for expected_col in (
                "ease_factor",
                "interval_days",
                "repetitions",
                "next_review_at",
                "last_reviewed_at",
                "streak",
            ):
                assert expected_col in cols

            # Существующая запись сохранилась и получила значения по умолчанию
            row = conn.execute("SELECT * FROM learned_gestures WHERE user_id = 1").fetchone()
            assert row["gesture_name"] == "привет"
            assert row["ease_factor"] == 2.5
            assert row["interval_days"] == 1
            assert row["repetitions"] == 0
            assert row["streak"] == 0


# ============================================================================
# 3. Тесты review_gesture и сохранения прогресса
# ============================================================================


def test_review_gesture_lifecycle():
    """Проверка жизненного цикла повторения жеста: от первого изучения до роста интервала."""
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        db_path = Path(tmp.name)
        db.init_db(db_path)

        user, _ = db.register_user(db_path, "tester", "secret_pass123")
        username = user["username"]

        # Первое повторение жеста
        r1 = db.review_gesture(username, "привет", 5, db_path=db_path)
        assert r1["username"] == username
        assert r1["gesture_name"] == "привет"
        assert r1["quality"] == 5
        assert r1["ease_factor"] == 2.6
        assert r1["interval_days"] == 1
        assert r1["repetitions"] == 1
        assert r1["streak"] == 1
        assert r1["next_review_at"] is not None

        # Второе повторение (q=5)
        r2 = db.review_gesture(username, "привет", 5, db_path=db_path)
        assert r2["repetitions"] == 2
        assert r2["interval_days"] == 6
        assert r2["streak"] == 2

        # Третье повторение с ошибкой (q=1)
        r3 = db.review_gesture(username, "привет", 1, db_path=db_path)
        assert r3["repetitions"] == 0
        assert r3["interval_days"] == 1
        assert r3["streak"] == 0  # Сброс серии для жеста


# ============================================================================
# 4. Тесты get_daily_warmup
# ============================================================================


def test_daily_warmup():
    """Проверка формирования очереди разминки: только жесты, требующие повторения."""
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        db_path = Path(tmp.name)
        db.init_db(db_path)

        user, _ = db.register_user(db_path, "warmup_user", "password_123")
        uid = user["id"]
        uname = user["username"]

        # Изучаем 3 жеста
        db.mark_gesture_learned(db_path, uid, "привет")
        db.mark_gesture_learned(db_path, uid, "дом")
        db.mark_gesture_learned(db_path, uid, "спасибо")

        # Новые жесты сразу попадают в очередь разминки
        warmup = db.get_daily_warmup(db_path, uname, limit=5)
        assert len(warmup) == 3
        warmup_names = [w["name"] for w in warmup]
        assert "привет" in warmup_names
        assert "дом" in warmup_names
        assert "спасибо" in warmup_names

        # Проверяем ограничение limit
        limited = db.get_daily_warmup(db_path, uname, limit=2)
        assert len(limited) == 2

        # Повторяем один жест с успешной оценкой
        db.review_gesture(uname, "привет", 5, db_path=db_path)

        # Теперь "привет" запланирован на будущее и больше не должен попадать в разминку сегодня
        warmup_after = db.get_daily_warmup(db_path, uname, limit=5)
        assert len(warmup_after) == 2
        remaining_names = [w["name"] for w in warmup_after]
        assert "привет" not in remaining_names
        assert "дом" in remaining_names
        assert "спасибо" in remaining_names


# ============================================================================
# 5. Тесты расчёта серий пользователя (get_user_streak)
# ============================================================================


def test_user_streak_calculation():
    """Проверка непрерывных серий дней активности (streak)."""
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        db_path = Path(tmp.name)
        db.init_db(db_path)

        user, _ = db.register_user(db_path, "streak_user", "password_123")
        uname = user["username"]

        # 0 дней активности
        assert db.get_user_streak(db_path, uname) == 0

        today = datetime.now(timezone.utc)
        today_iso = today.isoformat()
        yesterday_iso = (today - timedelta(days=1)).isoformat()
        two_days_ago_iso = (today - timedelta(days=2)).isoformat()

        # Активность сегодня -> streak = 1
        db.review_gesture(uname, "привет", 5, db_path=db_path, reviewed_at=today_iso)
        assert db.get_user_streak(db_path, uname) == 1

        # Повторная активность в тот же день не завышает streak
        db.review_gesture(uname, "дом", 4, db_path=db_path, reviewed_at=today_iso)
        assert db.get_user_streak(db_path, uname) == 1

        # Активность вчера + сегодня -> streak = 2
        db.review_gesture(uname, "спасибо", 5, db_path=db_path, reviewed_at=yesterday_iso)
        assert db.get_user_streak(db_path, uname) == 2

        # Активность 2 дня назад + вчера + сегодня -> streak = 3
        db.review_gesture(uname, "да", 5, db_path=db_path, reviewed_at=two_days_ago_iso)
        assert db.get_user_streak(db_path, uname) == 3


def test_user_streak_gap_and_break():
    """Проверка обрыва серии при пропуске дней."""
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        db_path = Path(tmp.name)
        db.init_db(db_path)

        user, _ = db.register_user(db_path, "broken_streak_user", "password_123")
        uname = user["username"]

        today = datetime.now(timezone.utc)
        three_days_ago_iso = (today - timedelta(days=3)).isoformat()
        four_days_ago_iso = (today - timedelta(days=4)).isoformat()

        # Активность была 3 и 4 дня назад, но вчера и сегодня не было
        db.review_gesture(uname, "привет", 5, db_path=db_path, reviewed_at=four_days_ago_iso)
        db.review_gesture(uname, "дом", 5, db_path=db_path, reviewed_at=three_days_ago_iso)

        # Серия прервана -> streak = 0
        assert db.get_user_streak(db_path, uname) == 0


# ============================================================================
# 6. Интеграционные тесты API (/api/gestures/warmup, /api/gestures/review)
# ============================================================================


def test_api_warmup_and_review():
    """Интеграционное тестирование эндпоинтов GET /api/gestures/warmup и POST /api/gestures/review."""
    app = create_app()
    with TestClient(app) as client:
        # Регистрация и авторизация пользователя
        username = f"api_srs_user_{int(datetime.now().timestamp())}"
        reg_res = client.post(
            "/api/auth/register",
            json={"username": username, "password": "password_srs_123"},
        )
        assert reg_res.status_code == 200
        token = reg_res.json()["user"]["token"]
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 1. Попытка запроса разминки без авторизации -> 401
        unauth_warmup = client.get("/api/gestures/warmup")
        assert unauth_warmup.status_code == 401

        # 2. Изучаем жест
        learn_res = client.post(
            "/api/gestures/learn",
            headers=auth_headers,
            json={"gesture_name": "привет"},
        )
        assert learn_res.status_code == 200

        # 3. Получение ежедневной разминки через токен
        warmup_res = client.get("/api/gestures/warmup", headers=auth_headers)
        assert warmup_res.status_code == 200
        w_data = warmup_res.json()
        assert w_data["status"] == "ok"
        assert w_data["count"] >= 1
        warmup_names = [g["name"] for g in w_data["gestures"]]
        assert "привет" in warmup_names

        # 4. Отправка оценки повторения через POST /api/gestures/review
        review_res = client.post(
            "/api/gestures/review",
            headers=auth_headers,
            json={"gesture_name": "привет", "quality": 5},
        )
        assert review_res.status_code == 200
        rev_data = review_res.json()
        assert rev_data["status"] == "ok"
        assert rev_data["ease_factor"] >= 2.5
        assert rev_data["repetitions"] == 1
        assert rev_data["streak"] >= 1

        # 5. Проверка валидации: некорректная оценка (например, 7)
        invalid_res = client.post(
            "/api/gestures/review",
            headers=auth_headers,
            json={"gesture_name": "привет", "quality": 7},
        )
        assert invalid_res.status_code == 422  # Pydantic validation error
