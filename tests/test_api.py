"""
Интеграционные тесты REST API эндпоинтов Project Omilia.
"""

from fastapi.testclient import TestClient

from project_omilia.app import create_app


def test_api_endpoints():
    app = create_app()
    with TestClient(app) as client:
        # 1. Проверка корневой страницы
        res_root = client.get("/")
        assert res_root.status_code in (200, 404)  # 200 если файл index.html найден

        # 2. Каталог доступных жестов
        res_gestures = client.get("/api/gestures")
        assert res_gestures.status_code == 200
        data_gestures = res_gestures.json()
        assert data_gestures["status"] == "ok"
        assert "gestures" in data_gestures
        assert isinstance(data_gestures["gestures"], list)

        # 3. Метаданные клиентского классификатора
        res_clf = client.get("/api/models/static-classifier?hands=1")
        assert res_clf.status_code == 200
        data_clf = res_clf.json()
        assert data_clf["status"] == "ok"
        assert data_clf["hands_count"] == 1
        assert "centroids" in data_clf

        # 4. Бинарный экспорт модели ONNX
        res_onnx = client.get("/api/models/static-onnx?hands=1")
        assert res_onnx.status_code == 200
        assert res_onnx.headers["content-type"] == "application/octet-stream"
        assert len(res_onnx.content) > 100

        # 5. Регистрация нового пользователя
        username = "ci_test_user"
        res_reg = client.post(
            "/api/auth/register",
            json={"username": username, "password": "secure_password_123"},
        )
        assert res_reg.status_code in (200, 400)  # 200 если новый, 400 если уже существует
