"""
Сервис классификации и записи статических жестов (StaticGestureServer).
"""

import json
import sqlite3
from pathlib import Path
from typing import Any

import numpy as np

from project_omilia import db
from project_omilia.body import Pose
from project_omilia.core.config import (
    DATASET_PATH_1H,
    DATASET_PATH_2H,
    LEGACY_DATASET_PATH,
)
from project_omilia.gestures import StaticGesture
from project_omilia.ml.augmentation import augment_static_samples
from project_omilia.ml.diagnostics import diagnose_static_gesture
from project_omilia.services.pose_service import make_pose


def import_static_datasets(db_path: Path) -> None:
    """Импортирует начальные эталоны статических жестов из JSON в SQLite при первом старте."""
    if db.static_samples_imported(db_path):
        return

    def read_dataset(path: Path) -> dict:
        if not path.is_file() or path.stat().st_size == 0:
            return {}
        dataset = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(dataset, dict):
            raise ValueError(f"Некорректный набор статических жестов: {path.name}")
        return dataset

    split = {1: read_dataset(DATASET_PATH_1H), 2: read_dataset(DATASET_PATH_2H)}
    missing = {hands for hands, dataset in split.items() if not dataset}
    legacy = read_dataset(LEGACY_DATASET_PATH) if missing else {}

    samples = []
    for hands, dataset in split.items():
        width = 141 * hands
        for label, vectors in (dataset or legacy).items():
            name = label.strip().lower()
            if not name or not isinstance(vectors, list):
                raise ValueError("Некорректная запись в старом наборе статических жестов.")
            for values in vectors:
                vector = np.asarray(values, dtype=np.float32)
                if not dataset and vector.shape == (141 * (3 - hands),):
                    continue
                if vector.shape != (width,) or not np.isfinite(vector).all():
                    raise ValueError(f"Некорректный эталон статического жеста «{name}».")
                samples.append(
                    (
                        name,
                        hands,
                        json.dumps(vector.tolist(), allow_nan=False),
                        vector.tobytes(),
                    )
                )

    db.import_static_samples(db_path, samples)


class StaticGestureServer:
    """Управляет классификаторами статических жестов для 1 и 2 рук."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.engine_1h = StaticGesture(db_path, 1)
        self.engine_2h = StaticGesture(db_path, 2)
        self._cached_stats: dict[str, int] = {}
        self._cached_info: dict[str, dict[str, Any]] = {}
        self._refresh_stats()

    def _refresh_stats(self) -> None:
        stats: dict[str, int] = {}
        info: dict[str, dict[str, Any]] = {}
        for engine in (self.engine_1h, self.engine_2h):
            for name, count in engine.get_dataset_stats().items():
                stats[name] = stats.get(name, 0) + count
                item = info.setdefault(name, {"count": 0, "hands": engine.hands_count, "hand_counts": {}})
                item["count"] += count
                item["hand_counts"][engine.hands_count] = count
        self._cached_stats = stats
        self._cached_info = info

    def get_combined_stats(self) -> dict[str, int]:
        return self._cached_stats

    def get_combined_info(self) -> dict[str, dict[str, Any]]:
        return self._cached_info

    def _record_frame(
        self,
        payload: dict[str, Any],
        pose: Pose | None,
        recording: list[tuple[str, int, np.ndarray]],
    ) -> dict[str, Any]:
        raw_label = payload["record_label"]
        label = raw_label.strip().lower() if isinstance(raw_label, str) else ""
        finished = bool(payload.get("record_finished"))
        hands = payload.get("hands_count")
        if hands not in (1, 2):
            hands = 1 if pose is None or pose.left_hand is None else 2

        if recording and recording[0][:2] != (label, hands):
            recording.clear()
        engine = self.engine_1h if hands == 1 else self.engine_2h
        result = None
        try:
            if not label or pose is None:
                raise ValueError("Кисть не обнаружена.")
            vector = engine.extract_vector(pose)
            if vector.shape != (141 * hands,) or not np.isfinite(vector).all():
                raise ValueError("Кадр не подходит для выбранного режима рук.")
            if len(recording) >= 15:
                recording.clear()
                raise ValueError("Слишком много кадров в серии.")
            recording.append((label, hands, vector))

            if finished:
                raw_samples = [sample for _, _, sample in recording]
                # Физическая аугментация: поворот, масштабирование и микро-шум
                augmented_samples = augment_static_samples(raw_samples, num_augmented_per_sample=2)
                engine.add_samples(label, augmented_samples)
                self._refresh_stats()
                result = {"status": "saved", "label": label, "count": len(augmented_samples)}
            message = f"Запись: {label}"
        except (ValueError, ArithmeticError, sqlite3.Error) as error:
            print(f"[Статическая запись] {error}")
            message = "Не удалось обработать кадр."
            if finished:
                result = {"status": "retry", "reason": "Не удалось сохранить статический жест. Повторите запись."}
        finally:
            if finished:
                recording.clear()

        response = {
            "detected": pose is not None,
            "gesture": message,
            "name": message,
            "dataset_stats": self.get_combined_stats(),
            "dataset_info": self.get_combined_info(),
        }
        if result is not None:
            response["static_record"] = result
        return response

    def process_frame(
        self,
        payload: dict[str, Any],
        recording: list[tuple[str, int, np.ndarray]],
    ) -> dict[str, Any]:
        hands_data = payload.get("hands_data") or payload.get("hands") or []
        pose_landmarks = payload.get("pose_landmarks")
        record_label = payload.get("record_label")
        hands_count = payload.get("hands_count")  # 1 или 2 из тумблера

        # ЖЁСТКИЙ ТУМБЛЕР РЕЖИМА 1 РУКА:
        # Если тумблер в режиме 1 рука (hands_count == 1), отсекаем вторую руку
        if hands_count == 1 and len(hands_data) > 1:
            hands_data = hands_data[:1]

        try:
            pose = make_pose(hands_data, pose_landmarks)
        except (KeyError, TypeError, ValueError):
            pose = None

        if record_label:
            return self._record_frame(payload, pose, recording)

        include_stats = bool(payload.get("include_stats"))

        if pose is None:
            res: dict[str, Any] = {
                "detected": False,
                "gesture": None,
                "name": None,
                "score": None,
                "distance": None,
            }
            if include_stats:
                res["dataset_stats"] = self.get_combined_stats()
                res["dataset_info"] = self.get_combined_info()
            return res

        # Выбор движка классификации:
        if hands_count == 1:
            engine = self.engine_1h
        elif hands_count == 2:
            engine = self.engine_2h
        else:
            engine = self.engine_1h if pose.left_hand is None else self.engine_2h

        # Если тумблер установлен на 2 руки, а в кадре только 1 рука:
        if hands_count == 2 and pose.left_hand is None:
            res = {
                "detected": True,
                "gesture": "Покажите 2 руки",
                "name": "Покажите 2 руки",
                "score": 0.0,
                "distance": 0.0,
                "confidence": 0.0,
            }
            if include_stats:
                res["dataset_stats"] = self.get_combined_stats()
                res["dataset_info"] = self.get_combined_info()
            return res

        code, score, prediction, confidence = engine.predict(pose)

        total_samples = sum(len(v) for v in engine.dataset.values())
        if code == 0:
            gesture_name = prediction
        elif code == -1:
            dim = 141 if pose.left_hand is None else 282
            hands_num = 1 if dim == 141 else 2
            if engine.model is None:
                gesture_name = f"Нет модели для {hands_num} рук(и)"
            elif total_samples < 3:
                gesture_name = f"Мало данных ({total_samples}/3)"
            else:
                gesture_name = "Не совпадает число рук"
        elif code == -2:
            gesture_name = "Неизвестный жест"
        else:
            gesture_name = "—"

        res = {
            "detected": True,
            "gesture": gesture_name,
            "name": gesture_name,
            "score": score,
            "distance": score,
            "confidence": confidence,
        }

        # Биометрическая диагностика при наличии целевого жеста (режимы практики и блица)
        target_gesture = payload.get("target_gesture")
        if target_gesture and isinstance(target_gesture, str):
            target_name = target_gesture.strip().lower()
            if target_name in engine.dataset and engine.dataset[target_name]:
                target_centroid = np.mean(engine.dataset[target_name], axis=0).astype(np.float32)
                user_vec = engine.extract_vector(pose)
                active_hands = 1 if engine.hands_count == 1 else 2
                res["diagnostics"] = diagnose_static_gesture(user_vec, target_centroid, hands_count=active_hands)

        if include_stats:
            res["dataset_stats"] = self.get_combined_stats()
            res["dataset_info"] = self.get_combined_info()
        return res

    def augment_existing_dataset(self, min_samples_target: int = 25) -> int:
        """Пополняет существующие эталоны в SQLite аугментированными вариациями."""
        added_total = 0
        for engine in (self.engine_1h, self.engine_2h):
            for name, vectors in list(engine.dataset.items()):
                if len(vectors) < min_samples_target:
                    needed = min_samples_target - len(vectors)
                    num_per = max(1, (needed + len(vectors) - 1) // len(vectors))
                    augmented = augment_static_samples(vectors, num_augmented_per_sample=num_per)
                    new_only = augmented[len(vectors) : len(vectors) + needed]
                    if new_only:
                        engine.add_samples(name, new_only)
                        added_total += len(new_only)
        if added_total > 0:
            self._refresh_stats()
        return added_total

    def reload(self) -> None:
        """Перезагружает эталоны из базы данных SQLite и переобучает классификаторы для 1 и 2 рук."""
        self.engine_1h.reload()
        self.engine_2h.reload()
        self._refresh_stats()

    def delete_gesture(self, gesture_name: str) -> None:
        db.delete_gesture(self.db_path, gesture_name.strip().lower())
        self.reload()

    def handle_action(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        match action:
            case "train_dataset":
                self.reload()
                return {
                    "detected": False,
                    "dataset_stats": self.get_combined_stats(),
                    "dataset_info": self.get_combined_info(),
                }
            case "augment_dataset":
                self.augment_existing_dataset()
                return {
                    "detected": False,
                    "dataset_stats": self.get_combined_stats(),
                    "dataset_info": self.get_combined_info(),
                }
            case "delete_gesture":
                gesture_name = payload.get("gesture_name", "").strip().lower()
                self.delete_gesture(gesture_name)
                return {
                    "detected": False,
                    "dataset_stats": self.get_combined_stats(),
                    "dataset_info": self.get_combined_info(),
                }
            case "get_dataset_stats":
                return {
                    "detected": False,
                    "dataset_stats": self.get_combined_stats(),
                    "dataset_info": self.get_combined_info(),
                }
            case _:
                return {
                    "detected": False,
                    "dataset_stats": self.get_combined_stats(),
                    "dataset_info": self.get_combined_info(),
                }
