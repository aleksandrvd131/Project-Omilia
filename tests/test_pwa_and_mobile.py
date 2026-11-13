"""
Тесты PWA, манифеста, Service Worker и мобильной адаптации.
"""

from fastapi.testclient import TestClient

from project_omilia.app import create_app


def test_manifest_endpoint():
    """Проверка отдачи manifest.json с правильным MIME-типом и заголовками."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/manifest.json")
        assert response.status_code == 200
        assert "application/manifest+json" in response.headers.get("content-type", "")
        assert "Cache-Control" in response.headers
        assert "max-age" in response.headers["Cache-Control"]

        data = response.json()
        assert data["name"] == "Omiλia - Тренажер РЖЯ"
        assert data["short_name"] == "Omiλia"
        assert data["display"] == "standalone"
        assert "theme_color" in data
        assert "background_color" in data
        assert "icons" in data
        assert len(data["icons"]) >= 2

        # Проверка иконок в манифесте
        icon_sizes = [icon.get("sizes") for icon in data["icons"]]
        assert "192x192" in icon_sizes
        assert "512x512" in icon_sizes


def test_service_worker_endpoint():
    """Проверка отдачи sw.js с MIME-типом application/javascript и no-cache."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/sw.js")
        assert response.status_code == 200
        content_type = response.headers.get("content-type", "").lower()
        assert "application/javascript" in content_type
        assert "charset=utf-8" in content_type
        assert "Cache-Control" in response.headers
        cache_control = response.headers["Cache-Control"].lower()
        assert "no-cache" in cache_control

        # Проверка логики кеширования
        body = response.text
        assert "CACHE_NAME" in body
        assert "install" in body
        assert "activate" in body
        assert "fetch" in body
        assert "caches.match" in body


def test_index_html_pwa_meta_and_sw():
    """Проверка наличия PWA метатегов, манифеста и скрипта регистрации Service Worker."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        # Метатеги и манифест
        assert 'rel="manifest"' in html
        assert 'href="/manifest.json"' in html
        assert "apple-mobile-web-app-capable" in html
        assert "viewport-fit=cover" in html
        assert "theme-color" in html

        # Регистрация Service Worker
        assert "serviceWorker" in html
        assert "navigator.serviceWorker.register('/sw.js')" in html

        # Кнопка переключения камеры
        assert "btn-switch-camera" in html
        assert "btn-floating-camera-switch" in html


def test_static_pwa_icons_served():
    """Проверка доступности файлов иконок PWA."""
    app = create_app()
    with TestClient(app) as client:
        res_192 = client.get("/static/icons/icon-192.png")
        assert res_192.status_code == 200
        assert res_192.headers["content-type"] == "image/png"
        assert len(res_192.content) > 100

        res_512 = client.get("/static/icons/icon-512.png")
        assert res_512.status_code == 200
        assert res_512.headers["content-type"] == "image/png"
        assert len(res_512.content) > 100

        res_svg = client.get("/static/icons/icon.svg")
        assert res_svg.status_code == 200
        assert "image/svg+xml" in res_svg.headers["content-type"]
        assert len(res_svg.content) > 100
