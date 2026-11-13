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


def test_gesture_silhouette_endpoints():
    """Тестирование анатомического силуэта-призрака (GET /api/gestures/{name}/silhouette)."""
    app = create_app()
    with TestClient(app) as client:
        # 1. Статический 1-ручный жест Slovo ('мир')
        res_mir = client.get("/api/gestures/мир/silhouette")
        assert res_mir.status_code == 200
        data_mir = res_mir.json()
        assert data_mir["status"] == "ok"
        assert data_mir["name"] == "мир"
        assert data_mir["is_dynamic"] is False
        assert data_mir["hands_count"] == 1
        assert isinstance(data_mir["silhouette"], list)
        assert len(data_mir["silhouette"]) == 1
        assert len(data_mir["silhouette"][0]) == 21
        for pt in data_mir["silhouette"][0]:
            assert "x" in pt and "y" in pt and "z" in pt

        # 2. Статический 2-ручный жест Slovo ('книга')
        res_book = client.get("/api/gestures/книга/silhouette")
        assert res_book.status_code == 200
        data_book = res_book.json()
        assert data_book["status"] == "ok"
        assert data_book["name"] == "книга"
        assert data_book["is_dynamic"] is False
        assert data_book["hands_count"] == 2
        assert len(data_book["silhouette"]) == 2
        assert len(data_book["silhouette"][0]) == 21
        assert len(data_book["silhouette"][1]) == 21

        # 3. Статический жест вне Slovo ('а')
        res_a = client.get("/api/gestures/а/silhouette")
        assert res_a.status_code == 200
        data_a = res_a.json()
        assert data_a["status"] == "ok"
        assert data_a["name"] == "а"
        assert data_a["is_dynamic"] is False
        assert data_a["hands_count"] == 1
        assert len(data_a["silhouette"][0]) == 21

        # 4. Статический 2-ручный жест вне Slovo ('10' и 'дом')
        res_10 = client.get("/api/gestures/10/silhouette")
        assert res_10.status_code == 200
        data_10 = res_10.json()
        assert data_10["is_dynamic"] is False
        assert data_10["hands_count"] == 2
        assert len(data_10["silhouette"]) == 2

        # 5. Динамический жест ('нет'): силуэт ВСЕГДА None
        res_net = client.get("/api/gestures/нет/silhouette")
        assert res_net.status_code == 200
        data_net = res_net.json()
        assert data_net["status"] == "ok"
        assert data_net["name"] == "нет"
        assert data_net["is_dynamic"] is True
        assert data_net["silhouette"] is None
        assert data_net["landmarks"] is None

        # 6. Несуществующий жест: 404 Not Found
        res_unknown = client.get("/api/gestures/несуществующий_жест_xyz/silhouette")
        assert res_unknown.status_code == 404
