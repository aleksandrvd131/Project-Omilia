"""
Тесты базы данных SQLite: таблицы, BLOB-акселерация векторов, CRUD жестов и прогресс.
"""

import tempfile
from pathlib import Path

import numpy as np

from project_omilia import db


def test_sqlite_gestures_crud():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        db_path = Path(tmp.name)
        db.init_db(db_path)

        # Проверка начальной инициализации каталога
        all_gestures = db.get_all_gestures(db_path)
        assert len(all_gestures) > 0

        # Создание нового жеста через upsert
        new_gesture = {
            "name": "спасибо_тест",
            "title": "Тестовое Спасибо",
            "category": "Тесты",
            "description": "Описание тестового жеста.",
            "tip": "Подсказка для теста.",
            "hands_count": 1,
            "is_dynamic": 0,
        }
        db.upsert_gesture(db_path, new_gesture)

        fetched = db.get_gesture(db_path, "спасибо_тест")
        assert fetched is not None
        assert fetched["title"] == "Тестовое Спасибо"
        assert fetched["category"] == "Тесты"

        # Удаление жеста
        db.delete_gesture(db_path, "спасибо_тест")
        assert db.get_gesture(db_path, "спасибо_тест") is None


def test_static_samples_blob_serialization():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        db_path = Path(tmp.name)
        db.init_db(db_path)

        # Создаём тестовый вектор 141 признаков float32
        vec = np.random.randn(141).astype(np.float32)
        samples = [("тест_жест", 1, "[]", vec.tobytes())]
        db.insert_static_samples(db_path, samples)

        rows = db.get_static_samples(db_path, 1)
        matching = [r for r in rows if r["gesture_name"] == "тест_жест"]
        assert len(matching) == 1

        # Восстановление вектора из бинарного BLOB
        restored = np.frombuffer(matching[0]["features_blob"], dtype=np.float32)
        assert restored.shape == (141,)
        assert np.allclose(vec, restored)


def test_learned_gestures_persistence():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        db_path = Path(tmp.name)
        db.init_db(db_path)

        user, _ = db.register_user(db_path, "test_learner", "password_123")
        uid = user["id"]

        assert len(db.get_learned_gestures(db_path, uid)) == 0

        # Отмечаем жесты как выученные
        db.mark_gesture_learned(db_path, uid, "привет")
        db.mark_gesture_learned(db_path, uid, "помоги")

        learned = db.get_learned_gestures(db_path, uid)
        assert len(learned) == 2
        assert "привет" in learned
        assert "помоги" in learned
