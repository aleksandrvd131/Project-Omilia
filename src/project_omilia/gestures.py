from pathlib import Path
from typing import Any
import json
import os
import joblib
import numpy as np
from sklearn.neighbors import KNeighborsClassifier

from project_omilia.body import Pose
from project_omilia.errors import IncorrectDataError, JSONDatasetError


def format_dataset_json_inline(data: dict[str, list[list[float]]]) -> str:
    """Форматирует датасет так, чтобы каждый сэмпл (вектор координат) записывался в одну строчку."""
    lines = ["{"]
    items = list(data.items())
    for i, (name, samples) in enumerate(items):
        escaped_name = json.dumps(name, ensure_ascii=False)
        lines.append(f"  {escaped_name}: [")
        for j, sample in enumerate(samples):
            sample_str = json.dumps(sample, ensure_ascii=False)
            comma = "," if j < len(samples) - 1 else ""
            lines.append(f"    {sample_str}{comma}")
        comma_item = "," if i < len(items) - 1 else ""
        lines.append(f"  ]{comma_item}")
    lines.append("}\n")
    return "\n".join(lines)


class Gesture:
    pass


class StaticGesture(Gesture):
    def __init__(self, dataset_path: str = "omilia_static_1h.json") -> None:
        self.dataset_path = Path(dataset_path).resolve()
        self.model_path = self.dataset_path.with_suffix(".joblib")
        self.dataset: dict[str, list[np.ndarray]] = {}
        self.models: dict[int, KNeighborsClassifier] = {}
        self.model: KNeighborsClassifier | None = None
        self._load_dataset()

    def dataset_to_json(self) -> dict[str, list[list[float]]]:
        result: dict[str, list[list[float]]] = {}
        for name, poses in self.dataset.items():
            result[name] = [pose.tolist() for pose in poses]
        return result

    def make_dataset(self) -> None:
        dataset: dict[str, list[np.ndarray]] = {}
        for name, poses in self.dataset.items():
            norm_name = name.strip().lower()
            converted_poses = [np.array(pose, dtype=float) for pose in poses]
            if norm_name not in dataset:
                dataset[norm_name] = converted_poses
            else:
                dataset[norm_name].extend(converted_poses)
        self.dataset = dataset

    def _save_dataset(self) -> None:
        try:
            with open(self.dataset_path, mode="w", encoding="utf-8") as f:
                data = self.dataset_to_json()
                f.write(format_dataset_json_inline(data))
        except OSError as err:
            raise JSONDatasetError(f"ERROR: Exception while saving dataset: {err}")

    def _save_models(self) -> None:
        try:
            payload = {
                "models": self.models,
                "model": self.model,
                "sample_counts": {k: len(v) for k, v in self.dataset.items()},
            }
            joblib.dump(payload, self.model_path)
        except Exception as err:
            print(f"[Model Cache] Предупреждение: ошибка сохранения в {self.model_path.name}: {err}")

    def _try_load_cached_models(self) -> bool:
        if not self.model_path.exists() or os.path.getsize(self.model_path) < 32:
            return False
        try:
            cache = joblib.load(self.model_path)
            if not isinstance(cache, dict) or "models" not in cache:
                return False

            cached_counts = cache.get("sample_counts", {})
            current_counts = {k: len(v) for k, v in self.dataset.items()}

            if cached_counts == current_counts:
                self.models = cache["models"]
                self.model = cache.get("model") or self.models.get(141) or (
                    next(iter(self.models.values())) if self.models else None
                )
                print(f"[Model Cache] Загружены предварительно обученные модели из {self.model_path.name}")
                return True
        except Exception as err:
            print(f"[Model Cache] Не удалось загрузить кэш {self.model_path.name}: {err}")
        return False

    def _load_dataset(self) -> None:
        if not self.dataset_path.exists() or not os.path.getsize(self.dataset_path):
            self.dataset = {}
            self.models = {}
            self.model = None
            return
        try:
            with open(self.dataset_path, mode="r", encoding="utf-8") as f:
                self.dataset = json.load(f)
                self.make_dataset()

            if not self._try_load_cached_models():
                self._train()
        except (OSError, json.JSONDecodeError, KeyError, JSONDatasetError) as err:
            raise JSONDatasetError(f"ERROR: Exception while loading dataset: {err}")

    def _train(self) -> None:
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

        self.model = self.models.get(141) or (next(iter(self.models.values())) if self.models else None)
        self._save_models()

    def _train_dim(self, dim: int) -> None:
        X_dim: list[np.ndarray] = []
        y_dim: list[str] = []

        for gesture_name, vectors in self.dataset.items():
            for vec in vectors:
                if len(vec) == dim:
                    X_dim.append(vec)
                    y_dim.append(gesture_name)

        if len(y_dim) >= 3:
            k = min(len(y_dim), 5)
            knn = KNeighborsClassifier(n_neighbors=k, metric="euclidean")
            knn.fit(np.array(X_dim, dtype=float), np.array(y_dim))
            self.models[dim] = knn
        elif dim in self.models:
            self.models.pop(dim)

        self.model = self.models.get(141) or (next(iter(self.models.values())) if self.models else None)
        self._save_models()

    def add_sample(
        self,
        name: str,
        pose: Pose,
        auto_train: bool = True,
        auto_save: bool = True,
    ) -> None:
        name = name.strip().lower()
        data = self.extract_vector(pose)
        dim = len(data)

        if name not in self.dataset:
            self.dataset[name] = [data]
        else:
            if self.dataset[name] and len(self.dataset[name][0]) != dim:
                self.dataset[name] = [data]
            else:
                self.dataset[name].append(data)

        if auto_train:
            self._train_dim(dim)
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
