import numpy as np


class Gesture:
    def __init__(self, name: str):
        self.name = name


class StaticGesture(Gesture):
    def __init__(
        self,
        name: str,
        features: np.ndarray | None = None,
        threshold: float = 0.65,
    ):
        super().__init__(name=name)
        self.features = features
        self.threshold = threshold

    def distance_to(self, sample_features: np.ndarray) -> float:
        if self.features is None:
            return float("inf")
        return float(np.linalg.norm(self.features - sample_features))

    def is_match(self, sample_features: np.ndarray) -> bool:
        return self.distance_to(sample_features) <= self.threshold


class DynamicGesture(Gesture):
    def __init__(self, base_shape: str, motion: str, target_word: str):
        super().__init__(name=f"{base_shape}|{motion}")
        self.base_shape = base_shape
        self.motion = motion
        self.target_word = target_word

    def matches(self, detected_shape: str, detected_motion: str) -> bool:
        shape_ok = (self.base_shape == "*") or (self.base_shape == detected_shape)
        motion_ok = self.motion == detected_motion
        return shape_ok and motion_ok
