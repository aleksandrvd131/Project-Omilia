"""
Тесты экспорта и импорта базы данных жестов (API, SQLite и UI).
"""

import base64
import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from project_omilia import db
from project_omilia.app import create_app
from project_omilia.core.config import BASE_DIR, DEBUG_PATH, FRONTEND_DIR
from project_omilia.gestures import StaticGesture


@pytest.fixture
def client():
    """Тестовый клиент FastAPI приложения."""
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_export_endpoint(client):
    """Проверка GET /api/gestures/export: возвращает валидный JSON и заголовок скачивания."""
    response = client.get("/api/gestures/export")
    assert response.status_code == 200
    assert "application/json" in response.headers.get("content-type", "")
    assert 'filename="omilia_dataset_export.json"' in response.headers.get("content-disposition", "")

    data = response.json()
    assert data["version"] == "1.0"
    assert "exported_at" in data
    assert "gestures" in data
    assert "static_gesture_samples" in data
    assert isinstance(data["gestures"], list)
    assert isinstance(data["static_gesture_samples"], list)
    assert len(data["gestures"]) > 0
    assert len(data["static_gesture_samples"]) > 0

    # Проверка структуры записей gestures
    sample_gesture = data["gestures"][0]
    for key in ("name", "title", "category", "description", "tip", "hands_count", "is_dynamic"):
        assert key in sample_gesture

    # Проверка структуры записей static_gesture_samples
    sample_data = data["static_gesture_samples"][0]
    for key in ("gesture_name", "hands_count", "features_json", "features_blob"):
        assert key in sample_data

    # Проверка base64 кодирования blob
    blob_b64 = sample_data["features_blob"]
    if blob_b64 is not None:
        raw_bytes = base64.b64decode(blob_b64)
        expected_size = 141 * 4 if sample_data["hands_count"] == 1 else 282 * 4
        assert len(raw_bytes) == expected_size


def test_import_endpoint_validation(client):
    """Проверка валидации схемы POST /api/gestures/import."""
    # 1. Пустой пейлоад
    res_empty = client.post("/api/gestures/import", json={"gestures": [], "static_gesture_samples": []})
    assert res_empty.status_code == 400
    assert "пуст" in res_empty.json()["detail"].lower()

    # 2. Некорректный сэмпл без признаков
    res_no_features = client.post(
        "/api/gestures/import",
        json={
            "gestures": [{"name": "invalid_sample_gesture"}],
            "static_gesture_samples": [{"gesture_name": "invalid_sample_gesture", "hands_count": 1}],
        },
    )
    assert res_no_features.status_code == 422


def test_import_endpoint_and_model_reload(client):
    """Проверка успешного импорта через API и автоматической перезагрузки активных моделей."""
    test_gesture_name = "test_api_import_gesture"
    test_vector = [0.05] * 141
    test_vector_b64 = base64.b64encode(np.asarray(test_vector, dtype=np.float32).tobytes()).decode("ascii")

    payload = {
        "gestures": [
            {
                "name": test_gesture_name,
                "title": "Тестовый Импорт",
                "category": "Тестовая категория",
                "description": "Описание жеста для интеграционного теста",
                "tip": "Подсказка для теста",
                "hands_count": 1,
                "is_dynamic": 0,
            }
        ],
        "static_gesture_samples": [
            {
                "gesture_name": test_gesture_name,
                "hands_count": 1,
                "features_blob": test_vector_b64,
            },
            {
                "gesture_name": test_gesture_name,
                "hands_count": 1,
                "features_blob": test_vector,  # Проверка поддержки float list
            },
        ],
    }

    try:
        res = client.post("/api/gestures/import", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["imported_gestures"] == 1
        assert data["imported_samples"] == 2
        assert "dataset_stats" in data
        assert test_gesture_name in data["dataset_stats"]
        assert data["dataset_stats"][test_gesture_name] >= 2

        # Проверяем, что жест теперь доступен в общем каталоге жестов
        res_catalog = client.get("/api/gestures")
        assert res_catalog.status_code == 200
        catalog_names = [g["name"] for g in res_catalog.json()["gestures"]]
        assert test_gesture_name in catalog_names
    finally:
        # Очистка базы данных от тестового жеста
        client.delete(f"/api/gestures/{test_gesture_name}")


def test_full_round_trip_export_import(tmp_path: Path):
    """Полный сквозной тест: экспорт -> импорт в изолированную базу -> повторный экспорт."""
    source_db = tmp_path / "source.db"
    dest_db = tmp_path / "dest.db"

    db.init_db(source_db)
    db.init_db(dest_db)

    # 1. Создаём исходные данные в source_db
    g1 = {
        "name": "жест_один",
        "title": "Жест Один",
        "category": "Тест",
        "description": "Тестовый жест 1",
        "tip": "Совет 1",
        "hands_count": 1,
        "is_dynamic": 0,
    }
    g2 = {
        "name": "жест_два",
        "title": "Жест Два",
        "category": "Тест",
        "description": "Тестовый жест 2",
        "tip": "Совет 2",
        "hands_count": 2,
        "is_dynamic": 0,
    }
    db.upsert_gesture(source_db, g1)
    db.upsert_gesture(source_db, g2)

    vec1 = np.ones(141, dtype=np.float32) * 0.1
    vec2 = np.ones(282, dtype=np.float32) * 0.2
    db.insert_static_samples(
        source_db,
        [
            ("жест_один", 1, json.dumps(vec1.tolist()), vec1.tobytes()),
            ("жест_один", 1, json.dumps((vec1 * 1.1).tolist()), (vec1 * 1.1).tobytes()),
            ("жест_два", 2, json.dumps(vec2.tolist()), vec2.tobytes()),
        ],
    )

    # 2. Экспорт из source_db
    exported = db.export_dataset(source_db)
    assert exported["total_gestures"] >= 2
    assert exported["total_samples"] >= 3

    # 3. Импорт в dest_db с заменой существующих сэмплов для импортируемых жестов
    import_result = db.import_dataset(dest_db, exported, clear_existing_samples=True)
    assert import_result["status"] == "ok"
    assert import_result["imported_gestures"] == exported["total_gestures"]
    assert import_result["imported_samples"] == exported["total_samples"]

    # 4. Повторный экспорт из dest_db и сверка целостности
    reexported = db.export_dataset(dest_db)
    assert reexported["total_gestures"] == exported["total_gestures"]
    assert reexported["total_samples"] == exported["total_samples"]

    source_names = {g["name"] for g in exported["gestures"]}
    dest_names = {g["name"] for g in reexported["gestures"]}
    assert source_names == dest_names

    # 5. Проверка обучения и перезагрузки моделей StaticGesture на импортированной базе
    clf_1h = StaticGesture(dest_db, 1)
    clf_2h = StaticGesture(dest_db, 2)
    assert "жест_один" in clf_1h.dataset
    assert len(clf_1h.dataset["жест_один"]) == 2
    assert "жест_два" in clf_2h.dataset
    assert len(clf_2h.dataset["жест_два"]) == 1


def test_ui_debug_html_export_import():
    """Проверка наличия компонентов экспорта/импорта в debug.html."""
    assert DEBUG_PATH.exists(), f"Файл {DEBUG_PATH} должен существовать"
    content = DEBUG_PATH.read_text(encoding="utf-8")

    # Проверка кнопок интерфейса
    assert "Экспорт базы" in content
    assert "Импорт базы" in content
    assert "omilia_dataset_export.json" in content

    # Проверка обработчиков и эндпоинтов
    assert "/api/gestures/export" in content
    assert "/api/gestures/import" in content
    assert "exportDatabase" in content
    assert "handleFileImport" in content
