import json
import time
from collections import deque
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.neighbors import KNeighborsClassifier

from project_omilia.body import Hand, Pose


class StaticSignEngine74:
    def __init__(self, dataset_path: str = "rsl_static_dataset_74.json"):
        self.dataset_path = Path(dataset_path)
        self.samples: list[list[float]] = []
        self.labels: list[str] = []
        self.model: KNeighborsClassifier | None = None
        self._load_dataset()

    def _load_dataset(self) -> None:
        if self.dataset_path.exists():
            try:
                with open(self.dataset_path, encoding="utf-8") as f:
                    data = json.load(f)
                    self.samples = data.get("X", [])
                    self.labels = data.get("y", [])
                self._train()
            except (OSError, json.JSONDecodeError, KeyError) as e:
                print(f"Ошибка загрузки датасета: {e}")

    def _save_dataset(self) -> None:
        try:
            with open(self.dataset_path, "w", encoding="utf-8") as f:
                json.dump({"X": self.samples, "y": self.labels}, f, ensure_ascii=False, indent=2)
        except OSError as e:
            print(f"Ошибка сохранения датасета: {e}")

    def _train(self) -> None:
        if len(self.samples) >= 3 and len(set(self.labels)) >= 2:
            n_neighbors = min(3, len(self.samples))
            self.model = KNeighborsClassifier(n_neighbors=n_neighbors)
            self.model.fit(self.samples, self.labels)
        else:
            self.model = None

    def add_sample(self, vector: list[float], label: str) -> None:
        self.samples.append(vector)
        self.labels.append(label)
        self._train()
        self._save_dataset()

    def delete_gesture(self, gesture_name: str) -> dict[str, Any]:
        indices_to_remove = [i for i, lbl in enumerate(self.labels) if lbl == gesture_name]
        for i in reversed(indices_to_remove):
            del self.samples[i]
            del self.labels[i]
        self._train()
        self._save_dataset()
        return self.get_dataset_stats()

    def get_dataset_stats(self) -> dict[str, Any]:
        stats: dict[str, Any] = {}
        for lbl in self.labels:
            if lbl not in stats:
                stats[lbl] = {"count": 0, "raw_name": lbl}
            stats[lbl]["count"] += 1
        return stats

    def extract_74_features(
        self,
        hands_data: list[dict],
        pose_lms: list[dict] | None,
    ) -> dict[str, Any]:
        if not hands_data:
            return {
                "active_count": 0,
                "vector_74": [],
                "active_hands": 0,
                "hands_summary": "Нет рук",
                "anchors": None,
                "telemetry": {},
            }

        if not pose_lms or len(pose_lms) < 17:
            pose_lms = [{"x": 0.5, "y": 0.3, "z": 0.0} for _ in range(33)]

        try:
            pose = Pose(pose_lms, hands_data)
            vec = pose.get_1d_array_two_hands() if len(hands_data) >= 2 else pose.get_1d_array_one_hand()
            vec_list = [round(float(x), 4) for x in vec]
        except (ValueError, KeyError, IndexError, TypeError):
            hand = Hand(hands_data[0], is_right=True)
            vec_list = [round(float(x), 4) for x in hand.get_1d_array()]

        return {
            "active_count": len(hands_data),
            "vector_74": vec_list,
            "active_hands": len(hands_data),
            "hands_summary": f"Рук в кадре: {len(hands_data)}",
            "anchors": {"nose": pose_lms[0] if pose_lms else {"x": 0.5, "y": 0.3, "z": 0.0}},
            "telemetry": {"features_count": len(vec_list)},
        }

    def predict(self, vector: list[float]) -> tuple[str, float, str]:
        if self.model is None or not self.samples:
            return "Не обучено", 0.0, "1H"
        try:
            x_arr = np.array([vector], dtype=np.float32)
            if x_arr.shape[1] != self.model.n_features_in_:
                return "Ожидание калибровки", 0.0, "1H"
            pred = str(self.model.predict(x_arr)[0])
            distances, _ = self.model.kneighbors(x_arr)
            score = round(float(np.mean(distances)), 2)
            return pred, score, "1H"
        except (ValueError, KeyError, IndexError, TypeError):
            return "Неизвестно", 0.0, "1H"

    def predict_shape_only(self, vector: list[float]) -> tuple[str, float]:
        label, score, _ = self.predict(vector)
        return label, score


class DynamicTracker74:
    def __init__(self, buffer_size: int = 14, cooldown_sec: float = 0.85):
        self.buffer_size = buffer_size
        self.cooldown_sec = cooldown_sec
        self.history: deque = deque(maxlen=buffer_size)
        self.last_trigger_time: float = 0.0

    def clear(self) -> None:
        self.history.clear()

    def update(self, extraction: dict[str, Any]) -> dict[str, Any]:
        now = time.time()
        anchors = extraction.get("anchors") or {}
        nose = anchors.get("nose", {"x": 0.5, "y": 0.5})

        self.history.append((now, float(nose.get("x", 0.5)), float(nose.get("y", 0.5))))

        motion = ""
        is_steady = True
        progress = {
            "dir": "ПОКОЙ",
            "arrow": "•",
            "percent": 0,
            "current": 0.0,
            "target": 0.15,
            "is_triggered": False,
        }

        if len(self.history) >= 4 and (now - self.last_trigger_time) > self.cooldown_sec:
            dx = self.history[-1][1] - self.history[0][1]
            dy = self.history[-1][2] - self.history[0][2]

            if abs(dx) > 0.15:
                motion = "Взмах ВЛЕВО" if dx > 0 else "Взмах ВПРАВО"
                progress["dir"] = "ВЛЕВО" if dx > 0 else "ВПРАВО"
                progress["arrow"] = "⟵" if dx > 0 else "⟶"
                progress["percent"] = 100
                progress["is_triggered"] = True
                self.last_trigger_time = now
                is_steady = False
            elif abs(dy) > 0.15:
                motion = "Взмах ВНИЗ" if dy > 0 else "Взмах ВВЕРХ"
                progress["dir"] = "ВНИЗ" if dy > 0 else "ВВЕРХ"
                progress["arrow"] = "↓" if dy > 0 else "↑"
                progress["percent"] = 100
                progress["is_triggered"] = True
                self.last_trigger_time = now
                is_steady = False

        return {
            "motion": motion,
            "motion_progress": progress,
            "trails": [[{"x": pt[1], "y": pt[2]} for pt in self.history]],
            "is_steady": is_steady,
        }


class RSLWordAssembler:
    def __init__(self, rules_path: str = "rsl_dynamic_rules.json"):
        self.rules_path = Path(rules_path)
        self.rules: dict[str, str] = {}
        self.spelled_text: str = ""
        self._load_rules()

    def _load_rules(self) -> None:
        if self.rules_path.exists():
            try:
                with open(self.rules_path, encoding="utf-8") as f:
                    self.rules = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                print(f"Ошибка загрузки правил: {e}")
        else:
            self.rules = {
                "1|Взмах ВЛЕВО": "НЕТ / НЕЛЬЗЯ",
                "1|Взмах ВПРАВО": "НЕТ / НЕЛЬЗЯ",
                "Кулак|Взмах ВНИЗ": "ДА",
            }

    def add_rule(self, base_shape: str, motion: str, target_word: str) -> dict[str, str]:
        key = f"{base_shape}|{motion}"
        self.rules[key] = target_word
        return self.rules

    def delete_rule(self, rule_key: str) -> dict[str, str]:
        self.rules.pop(rule_key, None)
        return self.rules

    def clear_text(self) -> str:
        self.spelled_text = ""
        return self.spelled_text

    def backspace_text(self) -> str:
        self.spelled_text = self.spelled_text[:-1]
        return self.spelled_text

    def space_text(self) -> str:
        self.spelled_text += " "
        return self.spelled_text

    def process(
        self,
        static_label: str,
        static_score: float,
        motion: str,
        is_steady: bool,
        shape_label: str,
        shape_score: float,
    ) -> dict[str, Any]:
        dynamic_word = None
        speak_event = None

        if motion:
            rule_key = f"{shape_label}|{motion}"
            wildcard_key = f"*|{motion}"

            matched_word = self.rules.get(rule_key) or self.rules.get(wildcard_key)
            if matched_word:
                dynamic_word = matched_word
                self.spelled_text += f"{matched_word} "
                speak_event = matched_word

        return {
            "dynamic_word": dynamic_word,
            "spelled_text": self.spelled_text,
            "hold_progress": 1.0 if is_steady else 0.0,
            "rules": self.rules,
            "speak_event": speak_event,
        }
