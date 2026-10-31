from project_omilia.body import Pose
from project_omilia.errors import DatasetNotFoundError, IncorrectDataError
import json
import time
from collections import deque
from pathlib import Path
from typing import Any
import numpy as np
from sklearn.neighbors import KNeighborsClassifier

class Gesture:
    pass

class StaticGesture(Gesture):
    def __init__(self, dataset_path: str = "omilia_static.json") -> None:
        self.dataset_path = Path(dataset_path)
        self.dataset: dict[str, list[np.array[float]]] = {}
        self.model: KNeighborsClassifier | None = None
        self._load_dataset()

    def dataset_to_json(self) -> list[tuple]:
        result: list[list[tuple]] = []
        for pose in self.dataset:
            result.append([tuple(vec) for vec in pose])
        return result
    
    def make_dataset(self):
        dataset = []
        for pose in self.dataset:
            dataset.append(np.array([np.array(vec) for vec in pose]))
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
        if not self.dataset_path.exists():
            return
        try:
            with open(self.dataset_path, mode="r", encoding="utf-8") as f:
                self.dataset = json.load(f)
                self.make_dataset()
            self._train()
        except (OSError, json.JSONDecodeError, json.JSONLoadError, KeyError, JSONDatasetError) as err:
            raise (f"ERROR: Exception while loading dataset:i {err}")
    
    def _train(self) -> None:

        X: list[list[float]] = []
        y: list[str] = []

        for gesture_name, vector in self.dataset.items():
            for vec in vector:
                X.append(vec)
                y.append(gesture_name)

        if len(y) >= 3:
            self.model = KNeighborsClassifier(n_neighbors=min(len(y), 5), metric="euclidean")
            self.model.fit(np.array(X), np.array(y))
        else:
            self.model = None

    def add_sample(self, name: str, pose: Pose) -> None:
        data = self.extract_vector(pose)
        if name not in self.dataset:
            self.dataset[name] = [data]
        else:
            self.dataset[name].append(data)
        self._train()
        self._save_dataset()

    def delete_gesture(self, gesture_name: str) -> dict[str, int]:
        self.dataset.pop(gesture_name)
        self._train()
        self._save_dataset()
        return self.get_dataset_stats()
    
    def get_dataset_stats(self) -> dict[str, int]:
        stats: dict[str, int] = {}
        for name in self.dataset:
            stats[name] = len(self.dataset[name])
        return stats
    
    def extract_vector(self, pose: Pose) -> list[float]:
        if not isinstance(pose, Pose):
            raise TypeError(
                "ERROR: No pose was given to gesture engine.\n"
            )
        if pose.left_hand is None:
            data = pose.get_1d_array_one_hand().flatten()
        else:
            data = pose.get_1d_array_two_hands().flatten()

        return [np.round(float(x), 8) for x in data]

    """
    Code -255 - Unknown
    Code -2 - Gesture is unknown
    Code -1 - Not trained
    Code 0 - Success
    Code 1 - Waiting for calibration
    """

    def predict(self, target: Pose, debug_flag = False) -> tuple[int, float, str]:
        if self.model is None or not self.dataset:
            return 0, 0.0, ""

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
        
        try:
            x_arr = np.array([vector], dtype = float) #??????????????????

            if x_arr.shape[1] != self.model.n_features_in_:
                return -1, 0.0, ""

            distances, _ = self.model.kneighbors(x_arr)
            score = round(float(np.mean(distances)), 2)
            max_distance = 2.0
            if score > max_distance:
                return -2, score, ""

            prediction = str(self.model.predict(x_arr)[0])
            return 0, score, prediction
        
        except (ValueError, KeyError, IndexError, TypeError):
            return -255, 0.0, ""


            



