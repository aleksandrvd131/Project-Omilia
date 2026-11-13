"""
Модуль классификации жестов:
- StaticGesture: классификация формы кисти на основе взвешенного k-NN
- DynamicGestures: сопоставление траекторий жестов через векторизованный DTW
"""

import json
from pathlib import Path

import numpy as np
from sklearn.neighbors import KNeighborsClassifier
from tslearn.metrics import dtw

from project_omilia import db
from project_omilia.body import Pose
from project_omilia.errors import IncorrectDataError

COUNT_OF_GESTURES = 8
COUNT_OF_SAMPLES = 10


class Gesture:
    pass


class StaticGesture(Gesture):
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

    def add_samples(self, name: str, vectors: list[np.ndarray]) -> None:
        samples = [
            (
                name,
                self.hands_count,
                json.dumps(vector.tolist(), allow_nan=False),
                vector.astype(np.float32).tobytes(),
            )
            for vector in vectors
        ]
        db.insert_static_samples(self.db_path, samples)
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

def dtw_distance(attempt: np.ndarray, reference: np.ndarray) -> float:
    """Вычисляет расстояние DTW между последовательностями через tslearn."""
    return float(dtw(attempt, reference))


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
                pairwise.append(dtw(references[i], references[j]))
        if not pairwise:
            return default_threshold
        return round(float(np.mean(pairwise) * 1.35), 2)

    def add_sample(self, label: str, sequence: np.ndarray) -> int:
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
            distances.append(dtw(sample, attempt))

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
