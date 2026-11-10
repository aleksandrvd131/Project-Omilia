from pathlib import Path
from typing import Any
import json
import numpy as np
from sklearn.neighbors import KNeighborsClassifier

from project_omilia import db
from project_omilia.body import Pose
from project_omilia.errors import IncorrectDataError

COUNT_OF_GESTURES = 8
COUNT_OF_SAMPLES = 10

class Gesture:
    pass


class StaticGesture(Gesture):
    def __init__(self, db_path: Path, hands_count: int) -> None:
        self.db_path = db_path
        self.hands_count = hands_count
        self.reload()

    def reload(self) -> None:
        dataset: dict[str, list[np.ndarray]] = {}
        for row in db.get_static_samples(self.db_path, self.hands_count):
            vector = np.asarray(json.loads(row["features_json"]), dtype=float)
            dataset.setdefault(row["gesture_name"], []).append(vector)

        vectors = [vector for samples in dataset.values() for vector in samples]
        labels = [name for name, samples in dataset.items() for _ in samples]
        model = None
        if len(labels) >= 3:
            model = KNeighborsClassifier(n_neighbors=min(len(labels), 5), metric="euclidean")
            model.fit(np.asarray(vectors, dtype=float), np.asarray(labels))

        self.dataset = dataset
        self.model = model

    def add_samples(self, name: str, vectors: list[np.ndarray]) -> None:
        samples = [
            (name, self.hands_count, json.dumps(vector.tolist(), allow_nan=False))
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

        return np.round(data, 8)

    """
    Code -255 - Unknown
    Code -2 - Gesture is unknown (distance exceeded threshold)
    Code -1 - Not trained / hand count mismatch
    Code 0 - Success
    Code 1 - Waiting for calibration
    """

    def predict(self, target: Pose, debug_flag: bool = False) -> tuple[int, float, str]:
        if not self.dataset:
            return -1, 0.0, ""

        if isinstance(target, Pose):
            vector = self.extract_vector(target)
        else:
            if debug_flag:
                vector = target
            else:
                raise IncorrectDataError("ERROR: Trying to predict non Pose object.\n")

        if vector is None or len(vector) == 0:
            return -1, 0.0, ""

        model = self.model
        if model is None:
            return -1, 0.0, ""

        try:
            x_arr = np.array([vector], dtype=float)
            if x_arr.shape[1] != model.n_features_in_:
                return -1, 0.0, ""

            distances, _ = model.kneighbors(x_arr)
            score = round(float(np.mean(distances)), 2)
            max_distance = 2.0
            if score > max_distance:
                return -2, score, ""

            prediction = str(model.predict(x_arr)[0])
            return 0, score, prediction

        except (ValueError, KeyError, IndexError, TypeError):
            return -255, 0.0, ""


def dtw_distance(attempt: np.ndarray, reference: np.ndarray) -> float:
    n = len(attempt)
    m = len(reference)
    accumulated = np.full((n+1, m+1), np.inf)
    accumulated[0][0] = 0

    for i in range(1, n+1):
        for j in range(1, m+1):
            delta = attempt[i-1] - reference[j-1]
            frame_cost = np.sum(delta ** 2)
            accumulated[i][j] = frame_cost + min(
                accumulated[i-1][j],
                accumulated[i][j-1],
                accumulated[i-1][j-1],
            )

    return float(np.sqrt(accumulated[n][m]))



class DynamicGestures:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path).resolve()

    def add_sample(self, label: str, sequence: np.ndarray) -> int:
        label = label.strip().lower()
        if not label:
            raise ValueError("Укажи название жеста.")

        features = np.asarray(sequence, dtype=float)
        if features.shape not in ((COUNT_OF_GESTURES, 141), (COUNT_OF_GESTURES, 282)):
            raise ValueError("Ожидается клип из восьми кадров по 141 или 282 признака.")
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
        max_distance: float,
    ) -> tuple[bool, dict[str, float]]:
        """Вычисляет три оценки DTW и засчитывает жест по среднему трёх ближайших."""
        if len(references) != COUNT_OF_SAMPLES:
            raise ValueError("There are no enough data to check gesture")
        if attempt.shape not in ((COUNT_OF_GESTURES, 141), (COUNT_OF_GESTURES, 282)):
            raise ValueError("Wrong format of attempt")

        distances = []
        for sample in references:
            if sample.shape != attempt.shape:
                raise ValueError("Wrong format of sample")
            distances.append(dtw_distance(sample, attempt))

        mean_all = sum(distances) / COUNT_OF_SAMPLES
        nearest_three = sorted(distances)[:3]
        mean_nearest_three = sum(nearest_three) / len(nearest_three)
        return mean_nearest_three <= max_distance, {
            "mean_all": mean_all,
            "minimum": nearest_three[0],
            "mean_nearest_three": mean_nearest_three,
        }

    def verify(
        self,
        attempt: np.ndarray,
        references: list[np.ndarray],
        *,
        max_distance: float,
    ) -> tuple[bool, float]:
        """Возвращает результат проверки и среднее DTW трёх ближайших эталонов."""
        accepted, distances = self.evaluate(attempt, references, max_distance=max_distance)
        return accepted, distances["mean_nearest_three"]
