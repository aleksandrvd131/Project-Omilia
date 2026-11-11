"""
Точка входа сервера Project Omilia.
Делегирует запуск и маршруты в модульное приложение project_omilia.app.
"""

import sys
from pathlib import Path

import uvicorn

from project_omilia.app import app

__all__ = ["app"]

if __name__ == "__main__":
    src_dir = str(Path(__file__).resolve().parent.parent)
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    uvicorn.run("project_omilia.serv:app", host="0.0.0.0", port=8000, reload=False)
