"""Каталог и силуэты используют записанные данные, без встроенных эталонов."""

import asyncio

import numpy as np

from project_omilia import db
from project_omilia.api import blitz
from project_omilia.services.silhouette_service import get_gesture_silhouette


def test_restart_preserves_cards_and_empty_database(tmp_path):
    path = tmp_path / "gestures.db"
    db.init_db(path)
    assert db.get_all_gestures(path) == []
    db.upsert_gesture(
        path,
        {"name": "привет", "title": "Моё название", "description": "Моё описание", "tip": "Моя подсказка", "level": 4},
    )
    before = db.get_gesture(path, "привет")
    db.init_db(path)
    assert db.get_gesture(path, "привет") == before


def test_silhouette_uses_recorded_bones_and_skips_invalid_sample(tmp_path):
    path = tmp_path / "gestures.db"
    db.init_db(path)
    db.upsert_gesture(path, {"name": "привет", "hands_count": 2})
    vector = np.zeros(282, dtype=np.float32)
    vector[:60] = 0.01
    vector[135:195] = 0.02
    db.insert_static_samples(path, [("привет", 2, "[]", b"bad"), ("привет", 2, "[]", vector.tobytes())])
    result = get_gesture_silhouette("привет", path)
    assert len(result["landmarks"]) == 2
    for hand, step in zip(result["landmarks"], [0.01, 0.02], strict=True):
        points = np.array([[p["x"], p["y"], p["z"]] for p in hand])
        assert points.shape == (21, 3)
        np.testing.assert_allclose(points[4] - points[0], step * 4)
    assert get_gesture_silhouette("несуществующий", path) is None


def test_blitz_uses_sqlite_card(tmp_path, monkeypatch):
    path = tmp_path / "gestures.db"
    db.init_db(path)
    db.upsert_gesture(path, {"name": "привет", "title": "Из базы", "tip": "Своя подсказка"})
    user, _ = db.register_user(path, "learner", "password123")
    db.mark_gesture_learned(path, user["id"], "привет")
    monkeypatch.setattr(blitz, "DB_PATH", path)

    class Static:
        def get_combined_stats(self):
            return {"привет": 3}

        def get_combined_info(self):
            return {"привет": {"hands": 1}}

    class Dynamic:
        def get_ready_gestures(self):
            return {}

    result = asyncio.run(blitz.api_blitz_questions(5, user, Static(), Dynamic()))
    assert result["questions"][0]["title"] == "Из базы"
    assert result["questions"][0]["tip"] == "Своя подсказка"


def test_application_lifespan_empty_and_existing_database(tmp_path, monkeypatch):
    from project_omilia import app as app_module
    path = tmp_path / 'gestures.db'
    monkeypatch.setattr(app_module, 'DB_PATH', path)
    async def start():
        app = app_module.create_app()
        async with app_module.lifespan(app):
            assert app.state.static_server.get_combined_stats() == {}
            assert app.state.dynamic_server.get_ready_gestures() == {}
    asyncio.run(start())
    db.upsert_gesture(path, {'name': 'привет', 'description': 'Не перезаписывать'})
    asyncio.run(start())
    assert db.get_gesture(path, 'привет')['description'] == 'Не перезаписывать'
