from project_omilia.body import Pose
from project_omilia.errors import DatasetNotFoundError, IncorrectDataError, JSONDatasetError
import json
import time
from collections import deque
from pathlib import Path
from typing import Any
import numpy as np
import os
from scipy.special import i0e
from sklearn.neighbors import KNeighborsClassifier

class Gesture:
    pass

class StaticGesture(Gesture):
    def __init__(self, dataset_path: str = "omilia_static.json") -> None:
        self.dataset_path = Path(dataset_path)
        self.dataset: dict[str, list[np.ndarray[float]]] = {}
        self.models: dict[int, KNeighborsClassifier] = {}
        self.model: KNeighborsClassifier | None = None
        self._load_dataset()

    def dataset_to_json(self) -> dict[str, list[list[float]]]:
        result: dict[str, list[list[float]]] = {}
        for name, poses in self.dataset.items():
            result[name] = [pose.tolist() for pose in poses]
        return result

    def make_dataset(self) -> None:
        dataset: dict[str, list[np.ndarray[float]]] = {}
        for name, poses in self.dataset.items():
            norm_name = name.strip().lower()
            converted_poses = [np.array(pose) for pose in poses]
            if norm_name not in dataset:
                dataset[norm_name] = converted_poses
            else:
                dataset[norm_name].extend(converted_poses)
        self.dataset = dataset

    def _save_dataset(self) -> None:
        try:
            with open(self.dataset_path, mode="w", encoding="utf-8") as f:
                data = self.dataset_to_json()
                json.dump(data, f, ensure_ascii = False, indent = 2)
        except OSError as err:
            raise JSONDatasetError(
                f"ERROR: Exception while saving dataset: {err}"
            )

    def _load_dataset(self) -> None:
        if not self.dataset_path.exists() or not os.path.getsize(self.dataset_path):
            self.dataset = {}
            return
        try:
            with open(self.dataset_path, mode="r", encoding="utf-8") as f:
                self.dataset = json.load(f)
                self.make_dataset()
            self._train()
        except (OSError, json.JSONDecodeError, KeyError, JSONDatasetError) as err:
            raise JSONDatasetError(f"ERROR: Exception while loading dataset: {err}")

    def _train(self) -> None:
        # Разделяем обучение для одноручных (141) и двуручных (282) жестов
        by_dim: dict[int, tuple[list[np.ndarray], list[str]]] = {}

        for gesture_name, vectors in self.dataset.items():
            for vec in vectors:
                dim = len(vec)
                if dim not in by_dim:
                    by_dim[dim] = ([], [])
                by_dim[dim][0].append(vec)
                by_dim[dim][1].append(gesture_name)

        self.models = {}
        for dim, (X_dim, y_dim) in by_dim.items():
            if len(y_dim) >= 3:
                k = min(len(y_dim), 5)
                knn = KNeighborsClassifier(n_neighbors=k, metric="euclidean")
                knn.fit(np.array(X_dim, dtype=float), np.array(y_dim))
                self.models[dim] = knn

        # Fallback для совместимости
        self.model = self.models.get(141) or (next(iter(self.models.values())) if self.models else None)

    def add_sample(
        self,
        name: str,
        pose: Pose,
        auto_train: bool = True,
        auto_save: bool = True,
    ) -> None:
        name = name.strip().lower()
        data = self.extract_vector(pose)
        if name not in self.dataset:
            self.dataset[name] = [data]
        else:
            # Если изменилась размерность (например, переобучили жест с 1 руки на 2 или наоборот)
            if self.dataset[name] and len(self.dataset[name][0]) != len(data):
                self.dataset[name] = [data]
            else:
                self.dataset[name].append(data)
        if auto_train:
            self._train()
        if auto_save:
            self._save_dataset()

    def save_and_train(self) -> None:
        self._train()
        self._save_dataset()

    def delete_gesture(self, gesture_name: str) -> dict[str, int]:
        gesture_name = gesture_name.strip().lower()
        if gesture_name in self.dataset:
            self.dataset.pop(gesture_name)
        self._train()
        self._save_dataset()
        return self.get_dataset_stats()

    def get_dataset_stats(self) -> dict[str, int]:
        stats: dict[str, int] = {}
        for name in self.dataset:
            stats[name] = len(self.dataset[name])
        return stats

    def get_dataset_info(self) -> dict[str, dict[str, Any]]:
        info: dict[str, dict[str, Any]] = {}
        for name, vectors in self.dataset.items():
            if not vectors:
                continue
            dim = len(vectors[0])
            hands_count = 2 if dim > 141 else 1
            info[name] = {
                "count": len(vectors),
                "hands": hands_count,
            }
        return info

    def extract_vector(self, pose: Pose) -> np.ndarray[float]:
        if not isinstance(pose, Pose):
            raise TypeError(
                "ERROR: No pose was given to gesture engine.\n"
            )
        if pose.left_hand is None:
            data = pose.get_1d_array_one_hand().flatten()
        else:
            data = pose.get_1d_array_two_hands().flatten()

        return np.round(data, 8)

    """
    Code -255 - Unknown
    Code -2 - Gesture is unknown
    Code -1 - Not trained
    Code 0 - Success
    Code 1 - Waiting for calibration
    """

    def predict(self, target: Pose, debug_flag = False) -> tuple[int, float, str]:
        if not self.dataset:
            return -1, 0.0, ""

        if isinstance(target, Pose):
            vector = self.extract_vector(target)
        else:
            if debug_flag:
                vector = target
            else:
                raise IncorrectDataError(
                    "ERROR: Trying to predict non Pose object.\n"
                )

        if vector is None or len(vector) == 0:
            return -1, 0.0, ""

        dim = len(vector)
        model = self.models.get(dim) if hasattr(self, "models") and self.models else (
            self.model if (self.model is not None and getattr(self.model, "n_features_in_", None) == dim) else None
        )

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
