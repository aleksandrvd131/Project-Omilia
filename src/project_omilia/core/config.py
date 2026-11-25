"""
Модуль конфигурации и констант Голос рук.
"""

from pathlib import Path

# Основные пути файловой системы
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
INDEX_PATH = FRONTEND_DIR / "index.html"
DEBUG_PATH = BASE_DIR / "debug.html"
DB_PATH = BASE_DIR / "omilia.db"

# Пороги динамических жестов для DTW (название, число рук -> максимальная дистанция)
DYNAMIC_DTW_THRESHOLDS: dict[tuple[str, int], float] = {
    ("нет", 1): 4.3,
}
