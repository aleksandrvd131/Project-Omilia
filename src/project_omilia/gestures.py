"""
Модуль классификации жестов:
- StaticGesture: классификация формы кисти на основе взвешенного k-NN
- DynamicGestures: сопоставление траекторий жестов через векторизованный DTW
- Curriculum Levels: формальная структура учебной программы (Уровни 1-4)
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.neighbors import KNeighborsClassifier

from project_omilia import db
from project_omilia.body import Pose
from project_omilia.errors import IncorrectDataError
from project_omilia.ml.dtw import dtw_distance

COUNT_OF_SAMPLES = 10


# ============================================================================
# Структура учебной программы (Curriculum Levels)
# ============================================================================

CURRICULUM_LEVELS: dict[int, dict[str, Any]] = {
    1: {
        "level": 1,
        "level_title": "Дактильный алфавит",
        "title": "Дактильный алфавит",
        "description": "Буквы дактильного алфавита русского жестового языка (А, Б, В, ...)",
        "badge": "🔤",
        "unlock_threshold": 0.0,
    },
    2: {
        "level": 2,
        "level_title": "Числительные и счёт",
        "title": "Числительные и счёт",
        "description": "Базовые числа и счёт на пальцах (1, 2, 3, ...)",
        "badge": "🔢",
        "unlock_threshold": 0.7,
    },
    3: {
        "level": 3,
        "level_title": "Базовый этикет",
        "title": "Базовый этикет",
        "description": "Приветствия, формулы вежливости и базовый контакт (Привет, Спасибо, Да, Нет, ...)",
        "badge": "🤝",
        "unlock_threshold": 0.7,
    },
    4: {
        "level": 4,
        "level_title": "Семья и окружение",
        "title": "Семья и окружение",
        "description": "Семья, дом, близкие и окружающий мир (Дом, Мама, Папа, Я, Ты, ...)",
        "badge": "🏡",
        "unlock_threshold": 0.7,
    },
}


def get_curriculum_level(gesture_name: str, category: str = "") -> tuple[int, str]:
    """Возвращает (level: int, level_title: str) для жеста согласно учебной программе.

    - Level 1: «Дактильный алфавит» (буквы А, Б, В, ...);
    - Level 2: «Числительные и счёт» (числа 1, 2, ...);
    - Level 3: «Базовый этикет» (Привет, Спасибо, и т.д.);
    - Level 4: «Семья и окружение» (Дом, Мама, Папа, и т.д.).
    """
    norm = gesture_name.strip().lower()
    cat_norm = category.strip().lower()
    if "алфавит" in cat_norm or "дактиль" in cat_norm:
        return 1, "Дактильный алфавит"
    if "числительн" in cat_norm or "счёт" in cat_norm or "счет" in cat_norm or "цифр" in cat_norm:
        return 2, "Числительные и счёт"
    if "привет" in cat_norm or "вежливост" in cat_norm or "этикет" in cat_norm or "базов" in cat_norm:
        return 3, "Базовый этикет"
    if "семь" in cat_norm or "дом" in cat_norm or "окружен" in cat_norm:
        return 4, "Семья и окружение"

    # Эвристическое сопоставление по имени
    if len(norm) == 1 and norm.isalpha():
        return 1, "Дактильный алфавит"
    if norm.startswith("буква_") or norm.startswith("буква "):
        return 1, "Дактильный алфавит"
    if norm.isdigit() or norm.startswith("число "):
        return 2, "Числительные и счёт"
    return 3, "Базовый этикет"


def get_curriculum_info(gesture_name: str, category: str = "") -> dict[str, Any]:
    """Возвращает метаданные уровня учебной программы: {'level': int, 'level_title': str}."""
    level, level_title = get_curriculum_level(gesture_name, category)
    return {
        "level": level,
        "level_title": level_title,
    }


class StaticGesture:
    """Классификатор статических жестов (форма ладони и пальцев)."""

    def __init__(self, db_path: Path, hands_count: int) -> None:
        self.db_path = db_path
        self.hands_count = hands_count
        self.labels: list[str] = []
        self.vectors: np.ndarray | None = None
        self.model: KNeighborsClassifier | None = None
        self.reload()

    def reload(self) -> None:
        dataset: dict[str, list[np.ndarray]] = {}
        for row in db.get_static_samples(self.db_path, self.hands_count):
            blob = row["features_blob"] if "features_blob" in row else None
            if blob:
                vector = np.frombuffer(blob, dtype=np.float32)
            else:
                vector = np.asarray(json.loads(row["features_json"]), dtype=np.float32)
            dataset.setdefault(row["gesture_name"], []).append(vector)

        vectors = [vector for samples in dataset.values() for vector in samples]
        labels = [name for name, samples in dataset.items() for _ in samples]
        model = None
        if len(labels) >= 3:
            # weights='distance' взвешивает соседей обратно пропорционально расстоянию
            # algorithm='auto' использует BallTree/KDTree для быстрого O(log N) поиска
            model = KNeighborsClassifier(
                n_neighbors=min(len(labels), 3),
                weights="distance",
                metric="euclidean",
                algorithm="brute",
            )
            model.fit(np.asarray(vectors, dtype=np.float32), np.asarray(labels))

        self.dataset = dataset
        self.labels = labels
        self.vectors = np.asarray(vectors, dtype=np.float32) if vectors else None
        self.model = model

    def add_samples(self, name: str, vectors: list[np.ndarray], metadata: dict | None = None) -> None:
        samples = [
            (
                name,
                self.hands_count,
                json.dumps(vector.tolist(), allow_nan=False),
                vector.astype(np.float32).tobytes(),
            )
            for vector in vectors
        ]
        db.insert_static_samples(self.db_path, samples, metadata=metadata)
        self.reload()

    def get_dataset_stats(self) -> dict[str, int]:
        return {name: len(vectors) for name, vectors in self.dataset.items()}

    def extract_vector(self, pose: Pose) -> np.ndarray:
        if not isinstance(pose, Pose):
            raise TypeError("ERROR: No pose was given to gesture engine.\n")
        if pose.left_hand is None:
            data = pose.get_1d_array_one_hand().flatten()
        else:
            data = pose.get_1d_array_two_hands().flatten()

        return data.astype(np.float32)

    """
    Code -255 - Unknown error
    Code -2 - Gesture is unknown (distance exceeded threshold)
    Code -1 - Not trained / hand count mismatch
    Code 0 - Success
    Code 1 - Waiting for calibration
    """

    def predict(self, target: Pose, debug_flag: bool = False) -> tuple[int, float, str, float]:
        """Предсказывает статический жест по ключевым точкам позы.
        Возвращает: (код_статуса, евклидово_расстояние, предсказанное_имя, уверенность_0_100)."""
        if not self.dataset:
            return -1, 0.0, "", 0.0

        if isinstance(target, Pose):
            vector = self.extract_vector(target)
        else:
            if debug_flag:
                vector = target
            else:
                raise IncorrectDataError("ERROR: Trying to predict non Pose object.\n")

        if vector is None or len(vector) == 0:
            return -1, 0.0, "", 0.0

        model = self.model
        if model is None or not self.labels:
            return -1, 0.0, "", 0.0

        try:
            x_arr = vector.reshape(1, -1)
            if x_arr.shape[1] != model.n_features_in_:
                return -1, 0.0, "", 0.0

            # Однократный поиск k-ближайших соседей без повторного вычисления
            distances, indices = model.kneighbors(x_arr)
            score = round(float(np.mean(distances[0][:3])), 2)
            max_distance = 2.0

            # Расчёт уверенности в процентах от 0 до 100%
            confidence = max(0.0, min(100.0, round((1.0 - (score / max_distance)) * 100, 1)))

            if score > max_distance:
                return -2, score, "", confidence

            neighbor_labels = [self.labels[idx] for idx in indices[0]]
            prediction = max(set(neighbor_labels), key=neighbor_labels.count)
            return 0, score, prediction, confidence

        except (ValueError, KeyError, IndexError, TypeError):
            return -255, 0.0, "", 0.0


class DynamicGestures:
    """Движок распознавания динамических жестов на основе DTW."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path).resolve()

    def calculate_adaptive_threshold(self, references: list[np.ndarray], default_threshold: float = 4.5) -> float:
        """Автоматически вычисляет адаптивный порог DTW на основе эталонов."""
        if len(references) < 2:
            return default_threshold
        pairwise = []
        for i in range(len(references)):
            for j in range(i + 1, len(references)):
                pairwise.append(dtw_distance(references[i], references[j]))
        if not pairwise:
            return default_threshold
        return round(float(np.mean(pairwise) * 1.35), 2)

    def add_sample(self, label: str, sequence: np.ndarray, metadata: dict | None = None) -> int:
        label = label.strip().lower()
        if not label:
            raise ValueError("Укажи название жеста.")

        features = np.asarray(sequence, dtype=float)
        if features.ndim != 2 or features.shape[1] not in (141, 282):
            raise ValueError("Ожидается последовательность кадров по 141 или 282 признака.")
        if not np.isfinite(features).all():
            raise ValueError("Клип содержит некорректные значения.")

        hands_count = 1 if features.shape[1] == 141 else 2
        return db.insert_dynamic_sample(
            self.db_path,
            label,
            hands_count,
            json.dumps(features.tolist(), allow_nan=False),
            limit=COUNT_OF_SAMPLES,
            metadata=metadata,
        )

    def get_samples(self, label: str, hands_count: int) -> list[np.ndarray]:
        rows = db.get_dynamic_samples(self.db_path, label.strip().lower(), hands_count)
        return [np.asarray(json.loads(row), dtype=float) for row in rows]

    def extract_vector(self, pose: Pose) -> np.ndarray:
        if not isinstance(pose, Pose):
            raise TypeError("ERROR: No pose was given to gesture engine.\n")
        if pose.left_hand is None:
            data = pose.get_1d_array_one_hand().flatten()
        else:
            data = pose.get_1d_array_two_hands().flatten()

        return np.round(data, 8)

    def evaluate(
        self,
        attempt: np.ndarray,
        references: list[np.ndarray],
        *,
        max_distance: float | None = None,
    ) -> tuple[bool, dict[str, float]]:
        """Вычисляет оценки DTW и засчитывает жест по среднему k ближайших эталонов."""
        if len(references) < 3:
            raise ValueError(f"Недостаточно эталонов жеста (записано {len(references)}, требуется минимум 3).")
        if attempt.ndim != 2 or attempt.shape[1] not in (141, 282):
            raise ValueError("Некорректный формат попытки.")

        if max_distance is None or max_distance <= 0:
            max_distance = self.calculate_adaptive_threshold(references)

        attempt_shape = attempt.shape[1]
        distances = []
        for sample in references:
            if sample.shape[1] != attempt_shape:
                raise ValueError("Число рук в попытке не совпадает с эталоном.")
            distances.append(dtw_distance(sample, attempt))

        k_nearest = min(3, len(distances))
        nearest = np.partition(distances, k_nearest - 1)[:k_nearest]
        mean_nearest = float(np.mean(nearest))
        mean_all = float(np.mean(distances))
        confidence = max(0.0, min(100.0, round((1.0 - (mean_nearest / max_distance)) * 100, 1)))

        return bool(mean_nearest <= max_distance), {
            "mean_all": round(mean_all, 2),
            "minimum": round(float(np.min(distances)), 2),
            "mean_nearest_three": round(mean_nearest, 2),
            "confidence": confidence,
            "threshold": round(max_distance, 2),
        }

    def verify(
        self,
        attempt: np.ndarray,
        references: list[np.ndarray],
        *,
        max_distance: float | None = None,
    ) -> tuple[bool, float]:
        """Возвращает результат проверки и среднее DTW трёх ближайших эталонов."""
        accepted, distances = self.evaluate(attempt, references, max_distance=max_distance)
        return accepted, distances["mean_nearest_three"]
