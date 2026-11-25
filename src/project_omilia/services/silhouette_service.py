"""Силуэт кисти восстанавливается из первого пригодного эталона SQLite, без встроенных жестов."""

import json
from pathlib import Path
from typing import Any

import numpy as np

from project_omilia import db
from project_omilia.core.config import DB_PATH


def get_gesture_silhouette(
    name: str, db_path: Path | None = None, static_server: Any = None, dynamic_server: Any = None
) -> dict | None:
    name = name.strip().lower()
    path = db_path or DB_PATH
    card = db.get_gesture(path, name)
    dynamic = dynamic_server.get_ready_gestures() if dynamic_server else {}
    static_info = static_server.get_combined_info().get(name) if static_server else None
    if not card and name not in dynamic and not static_info:
        return None
    hands = (card or {}).get("hands_count") or dynamic.get(name) or (static_info or {}).get("hands", 1)
    result = dict(
        name=name,
        is_dynamic=bool((card or {}).get("is_dynamic") or name in dynamic),
        hands_count=hands,
        silhouette=None,
        landmarks=None,
    )
    if result["is_dynamic"]:
        return {**result, "message": "Силуэт-призрак доступен только для статических жестов"}
    for row in db.get_static_samples(path, hands):
        if row["gesture_name"] != name:
            continue
        try:
            vector = (
                np.frombuffer(row["features_blob"], dtype=np.float32)
                if row["features_blob"]
                else np.asarray(json.loads(row["features_json"]))
            )
            if vector.shape != (141 * hands,) or not np.isfinite(vector).all():
                continue
            landmarks = []
            for hand in range(hands):
                # Каждая кисть: 20 векторов фаланг, нормаль и 24 признака формы = 135 чисел.
                bones = vector[hand * 135 : hand * 135 + 60].reshape(5, 4, 3)
                wrist = np.array([0.5 if hands == 1 else 0.35 + hand * 0.3, 0.65, 0.0])
                points = [wrist]
                for finger in bones:
                    points.extend(wrist + np.cumsum(finger, axis=0))
                landmarks.append([dict(zip(("x", "y", "z"), map(float, point), strict=True)) for point in points])
            return {**result, "silhouette": landmarks, "landmarks": landmarks}
        except (ValueError, TypeError):
            continue
    return {**result, "message": "Для силуэта нет пригодного статического эталона в базе."}
