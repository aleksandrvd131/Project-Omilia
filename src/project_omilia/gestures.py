"""
Модуль классификации жестов:
- StaticGesture: классификация формы кисти на основе взвешенного k-NN
- DynamicGestures: сопоставление траекторий жестов через векторизованный DTW
- Curriculum Levels: формальная структура учебной программы (Уровни 1-4)
"""

import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

import joblib
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


def _dump_joblib_atomic(model_path: Path, payload: dict[str, Any]) -> None:
    """Атомарно сохраняет словарь модели/кэша в файл .joblib."""
    model_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_name = tempfile.mkstemp(
        dir=model_path.parent,
        prefix=f".{model_path.stem}_",
        suffix=".tmp",
    )
    os.close(tmp_fd)
    tmp_path = Path(tmp_name)
    try:
        joblib.dump(payload, tmp_path, compress=3)
        os.replace(tmp_path, model_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def _load_joblib_dict(model_path: Path) -> dict[str, Any] | None:
    """Безопасно загружает словарь из .joblib файла."""
    if not model_path.exists():
        return None
    try:
        payload = joblib.load(model_path)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def get_static_model_path(db_path: Path, hands_count: int) -> Path:
    """Возвращает путь к файлу .joblib сохранённой статической модели рядом с БД."""
    db_file = Path(db_path)
    return db_file.with_name(f"{db_file.stem}_static_{hands_count}h.joblib")


def get_dynamic_model_path(db_path: Path) -> Path:
    """Возвращает путь к файлу .joblib кэша эталонов и порогов динамических жестов."""
    db_file = Path(db_path)
    return db_file.with_name(f"{db_file.stem}_dynamic.joblib")


class StaticGesture:
    """Классификатор статических жестов (форма ладони и пальцев)."""

    MODEL_FORMAT_VERSION = 1

    def __init__(self, db_path: Path, hands_count: int, model_path: Path | None = None) -> None:
        self.db_path = Path(db_path)
        self.hands_count = hands_count
        self.model_path = Path(model_path) if model_path is not None else get_static_model_path(self.db_path, hands_count)
        self.dataset: dict[str, list[np.ndarray]] = {}
        self.labels: list[str] = []
        self.vectors: np.ndarray | None = None
        self.model: KNeighborsClassifier | None = None
        if not self.load_model():
            self.reload()

    def save_model(self, fingerprint: str | None = None) -> bool:
        """Сохраняет обученную модель статических жестов в .joblib (или удаляет устаревший файл)."""
        if self.model is None or self.vectors is None or not self.labels:
            if self.model_path.exists():
                self.model_path.unlink(missing_ok=True)
            return False

        fp = fingerprint or db.get_static_samples_fingerprint(self.db_path, self.hands_count)
        payload = {
            "version": self.MODEL_FORMAT_VERSION,
            "hands_count": self.hands_count,
            "fingerprint": fp,
            "model": self.model,
            "labels": self.labels,
            "vectors": self.vectors,
        }
        _dump_joblib_atomic(self.model_path, payload)
        return True

    def load_model(self) -> bool:
        """Загружает сохранённую статическую модель из .joblib, если она актуальна для текущей БД."""
        payload = _load_joblib_dict(self.model_path)
        if payload is None:
            return False
        if payload.get("version") != self.MODEL_FORMAT_VERSION:
            return False
        if payload.get("hands_count") != self.hands_count:
            return False

        expected_fp = db.get_static_samples_fingerprint(self.db_path, self.hands_count)
        if payload.get("fingerprint") != expected_fp:
            return False

        model = payload.get("model")
        labels = payload.get("labels")
        vectors = payload.get("vectors")
        if not isinstance(model, KNeighborsClassifier):
            return False
        if not isinstance(labels, list) or len(labels) < 3:
            return False
        if not isinstance(vectors, np.ndarray) or vectors.ndim != 2 or len(vectors) != len(labels):
            return False

        dataset: dict[str, list[np.ndarray]] = {}
        for name, vec in zip(labels, vectors, strict=True):
            dataset.setdefault(name, []).append(vec)

        self.dataset = dataset
        self.labels = labels
        self.vectors = vectors
        self.model = model
        return True

    def reload(self) -> None:
        dataset: dict[str, list[np.ndarray]] = {}
        for row in db.get_static_samples(self.db_path, self.hands_count):
            blob = row["features_blob"] if "features_blob" in row.keys() else None
            if blob:
                vector = np.frombuffer(blob, dtype=np.float32)
            else:
                vector = np.asarray(json.loads(row["features_json"]), dtype=np.float32)
            dataset.setdefault(row["gesture_name"], []).append(vector)

        vectors = [vector for samples in dataset.values() for vector in samples]
        labels = [name for name, samples in dataset.items() for _ in samples]
        vectors_arr = np.asarray(vectors, dtype=np.float32) if vectors else None
        model = None
        if len(labels) >= 3 and vectors_arr is not None:
            # weights='distance' взвешивает соседей обратно пропорционально расстоянию
            # algorithm='auto' использует BallTree/KDTree для быстрого O(log N) поиска
            model = KNeighborsClassifier(
                n_neighbors=min(len(labels), 3),
                weights="distance",
                metric="euclidean",
                algorithm="brute",
            )
            model.fit(vectors_arr, np.asarray(labels))

        self.dataset = dataset
        self.labels = labels
        self.vectors = vectors_arr
        self.model = model
        self.save_model()

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
    """Движок распознавания динамических жестов на основе DTW с кэшем эталонов и порогов в .joblib."""

    MODEL_FORMAT_VERSION = 1

    def __init__(self, db_path: Path, model_path: Path | None = None) -> None:
        self.db_path = Path(db_path).resolve()
        self.model_path = Path(model_path) if model_path is not None else get_dynamic_model_path(self.db_path)
        self.samples: dict[tuple[str, int], list[np.ndarray]] = {}
        self.adaptive_thresholds: dict[tuple[str, int], float] = {}
        self._fingerprint: str | None = None
        if not self.load_model():
            self.reload()

    def _get_db_fingerprint(self) -> str | None:
        try:
            return db.get_dynamic_samples_fingerprint(self.db_path)
        except sqlite3.OperationalError:
            return None

    def save_model(self, fingerprint: str | None = None) -> bool:
        """Сохраняет кэш динамических эталонов и предвычисленных порогов в .joblib."""
        if not self.samples:
            if self.model_path.exists():
                self.model_path.unlink(missing_ok=True)
            return False

        fp = fingerprint or self._get_db_fingerprint()
        if fp is None:
            return False

        payload = {
            "version": self.MODEL_FORMAT_VERSION,
            "fingerprint": fp,
            "samples": self.samples,
            "adaptive_thresholds": self.adaptive_thresholds,
        }
        _dump_joblib_atomic(self.model_path, payload)
        return True

    def load_model(self) -> bool:
        """Загружает кэш эталонов и порогов DTW из .joblib, если он актуален для текущей БД."""
        expected_fp = self._get_db_fingerprint()
        if expected_fp is None:
            return False

        payload = _load_joblib_dict(self.model_path)
        if payload is None:
            return False
        if payload.get("version") != self.MODEL_FORMAT_VERSION:
            return False
        if payload.get("fingerprint") != expected_fp:
            return False

        samples = payload.get("samples")
        thresholds = payload.get("adaptive_thresholds")
        if not isinstance(samples, dict) or not isinstance(thresholds, dict):
            return False

        self.samples = samples
        self.adaptive_thresholds = thresholds
        self._fingerprint = expected_fp
        return True

    def reload(self) -> None:
        """Перечитывает эталоны из SQLite, пересчитывает адаптивные пороги DTW и сохраняет .joblib."""
        try:
            rows = db.get_all_dynamic_samples(self.db_path)
        except sqlite3.OperationalError:
            self.samples = {}
            self.adaptive_thresholds = {}
            self._fingerprint = None
            if self.model_path.exists():
                self.model_path.unlink(missing_ok=True)
            return

        samples: dict[tuple[str, int], list[np.ndarray]] = {}
        for row in rows:
            key = (row["gesture_name"].strip().lower(), int(row["hands_count"]))
            samples.setdefault(key, []).append(np.asarray(json.loads(row["sequence_json"]), dtype=float))

        thresholds: dict[tuple[str, int], float] = {}
        for key, refs in samples.items():
            if len(refs) >= 2:
                thresholds[key] = self.calculate_adaptive_threshold(refs)

        fp = self._get_db_fingerprint()
        self.samples = samples
        self.adaptive_thresholds = thresholds
        self._fingerprint = fp
        self.save_model(fp)

    def _ensure_fresh(self) -> None:
        current_fp = self._get_db_fingerprint()
        if current_fp is None or current_fp == self._fingerprint:
            return
        if not self.load_model():
            self.reload()

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

    def get_adaptive_threshold(
        self,
        label: str,
        hands_count: int,
        references: list[np.ndarray] | None = None,
        default_threshold: float = 4.5,
    ) -> float:
        """Возвращает предвычисленный адаптивный порог из кэша или рассчитывает его по эталонам."""
        self._ensure_fresh()
        key = (label.strip().lower(), hands_count)
        if key in self.adaptive_thresholds:
            return self.adaptive_thresholds[key]
        if references:
            return self.calculate_adaptive_threshold(references, default_threshold=default_threshold)
        return default_threshold

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
        self._ensure_fresh()
        new_count = db.insert_dynamic_sample(
            self.db_path,
            label,
            hands_count,
            json.dumps(features.tolist(), allow_nan=False),
            limit=COUNT_OF_SAMPLES,
            metadata=metadata,
        )
        key = (label, hands_count)
        refs = self.samples.setdefault(key, [])
        if len(refs) < new_count:
            refs.append(np.array(features, dtype=float, copy=True))
        if len(refs) >= 2:
            self.adaptive_thresholds[key] = self.calculate_adaptive_threshold(refs)
        fp = self._get_db_fingerprint()
        self._fingerprint = fp
        self.save_model(fp)
        return new_count

    def get_samples(self, label: str, hands_count: int) -> list[np.ndarray]:
        self._ensure_fresh()
        return list(self.samples.get((label.strip().lower(), hands_count), []))

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
