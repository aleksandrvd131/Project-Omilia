"""
Сервис обработки динамических жестов с использованием Dynamic Time Warping (DTW).
"""

from math import isfinite
from pathlib import Path
import sqlite3
from typing import Any

import numpy as np

from project_omilia.core.config import DYNAMIC_DTW_THRESHOLDS
from project_omilia import db
from project_omilia.gestures import COUNT_OF_GESTURES, COUNT_OF_SAMPLES, DynamicGestures
from project_omilia.services.pose_service import make_pose


class DynamicGestureServer:
    def __init__(self, db_path: Path) -> None:
        self.engine = DynamicGestures(db_path)

    def get_ready_gestures(self) -> dict[str, int]:
        ready = {}
        for row in db.list_dynamic_samples(self.engine.db_path):
            name = row.get("gesture_name") or row.get("name")
            hands_count = row.get("hands_count") if row.get("hands_count") is not None else row.get("hands")
            samples_count = row.get("samples_count") if row.get("samples_count") is not None else row.get("count", 0)
            if name and name not in ready and samples_count >= 3:
                ready[name] = hands_count
        return ready

    def prepare_dynamic_clip(self, frames: list, hands_count: int) -> np.ndarray:
        if len(frames) < 4:
            raise ValueError("Слишком мало кадров для анализа движения (требуется минимум 4 кадра).")

        expected_shape = (141 * hands_count,)
        vectors = []

        for number, frame in enumerate(frames, start=1):
            if not isinstance(frame, dict):
                raise ValueError(f"Кадр {number}: ожидался объект с точками.")
            hands_data = frame.get("hands_data")
            pose_landmarks = frame.get("pose_landmarks")
            if not isinstance(hands_data, list) or len(hands_data) != hands_count:
                raise ValueError(f"Кадр {number}: ожидалось кистей: {hands_count}.")
            if any(not isinstance(hand, list) or len(hand) != 21 for hand in hands_data):
                raise ValueError(f"Кадр {number}: ожидалось 21 точка на кисть.")
            if not isinstance(pose_landmarks, list) or len(pose_landmarks) != 33:
                raise ValueError(f"Кадр {number}: ожидалось 33 точки тела.")

            try:
                pose = make_pose(hands_data, pose_landmarks)
                if pose is None:
                    raise ValueError("Не удалось построить позу.")
                vector = self.engine.extract_vector(pose)
            except (KeyError, TypeError, ValueError, ArithmeticError) as error:
                raise ValueError(f"Кадр {number}: некорректные координаты.") from error

            if vector.shape != expected_shape or not np.isfinite(vector).all():
                raise ValueError(f"Кадр {number}: некорректные признаки.")
            vectors.append(vector)

        return np.stack(vectors)

    def process_dynamic_clip(self, payload: dict[str, Any]) -> dict[str, Any]:
        response: dict[str, Any] = {"type": "dynamic_clip"}
        if type(payload.get("attempt_id")) is int:
            response["attempt_id"] = payload["attempt_id"]
        try:
            hands_count = payload.get("hands_count")
            if type(hands_count) is not int or hands_count not in (1, 2):
                raise ValueError("Выбери режим одной или двух рук.")
            frames = payload.get("frames")
            if not isinstance(frames, list):
                raise ValueError("В пакете нет списка кадров.")

            mode = payload.get("mode")
            if mode not in (None, "record", "verify", "practice"):
                raise ValueError("Неизвестный режим динамического клипа.")
            if mode in ("record", "verify", "practice"):
                label = payload.get("label")
                if not isinstance(label, str) or not label.strip():
                    raise ValueError("Укажи название жеста.")
                label = label.strip().lower()

            if mode in ("verify", "practice"):
                references = self.engine.get_samples(label, hands_count)
                if len(references) < 3:
                    raise ValueError(
                        f"Для жеста «{label}» в этом режиме рук записано "
                        f"{len(references)} из 3 минимально необходимых эталонов."
                    )

                raw_threshold = payload.get("max_distance") if mode == "verify" else None
                if raw_threshold is None:
                    raw_threshold = DYNAMIC_DTW_THRESHOLDS.get((label, hands_count))
                    if raw_threshold is None:
                        # Автоматический расчёт адаптивного порога
                        raw_threshold = self.engine.calculate_adaptive_threshold(references)

                try:
                    if type(raw_threshold) not in (int, float):
                        raise ValueError
                    threshold = float(raw_threshold)
                    if not isfinite(threshold) or threshold < 0:
                        raise ValueError
                except (ValueError, OverflowError):
                    raise ValueError("Порог DTW должен быть конечным числом от 0.") from None

            sequence = self.prepare_dynamic_clip(frames, hands_count)
            if mode == "record":
                count = self.engine.add_sample(label, sequence)
                return {
                    **response, "status": "recorded", "label": label, "count": count,
                    "dynamic_dataset": db.list_dynamic_samples(self.engine.db_path),
                }
            if mode in ("verify", "practice"):
                accepted, distances = self.engine.evaluate(sequence, references, max_distance=threshold)
                if mode == "verify":
                    response["distances"] = distances
                return {
                    **response,
                    "status": "verified",
                    "label": label,
                    "accepted": accepted,
                    "distance": distances["mean_nearest_three"],
                    "confidence": distances.get("confidence", 0.0),
                    "max_distance": distances.get("threshold", threshold),
                }
        except ValueError as error:
            return {**response, "status": "retry", "reason": str(error)}
        except sqlite3.Error as error:
            print(f"[Динамические жесты] Ошибка SQLite: {error}")
            return {**response, "status": "retry", "reason": "Не удалось обратиться к эталонам."}

        return {**response, "status": "ok", "shape": list(sequence.shape)}
