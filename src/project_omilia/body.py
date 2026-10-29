import numpy as np
from project_omilia.errors import IncorrectDataError
from project_omilia.math import (
    dot_dist,
    vec_len,
    vec_angle,
    vec_normalize,
    vec_norm_angle
)

DOTS_IN_HAND: int = 21

class Hand:
    data: list
    is_right: bool
    palm_scale: float
    fingers: list[list[np.ndarray]]
    normal: np.ndarray

    """
    0 - Thumb
    1 - Index
    2 - Midlle
    3 - Ring
    4 - Pinky
    """

    def __init__(self, data: list, is_right: bool):
        if len(data) != DOTS_IN_HAND:
            raise IncorrectDataError(
                "Wrong amount of dots in hand.\n"
            )
        self.is_right = is_right
        data = [np.array(i) for i in data]
        self.data = data
        wrist = data[0]
        self.palm_scale = dot_dist(wrist, data[9])
        v1 = data[5] - wrist
        v2 = data[17] - wrist
        if self.is_right:
            self.normal = np.cross(v1, v2)
        else:
            self.normal = np.cross(v2, v1)
        self.normal = vec_normalize(self.normal)
        self.fingers = [[] for _ in range(5)]
        for i in range(1, 20, 4):
            self.fingers[(i - 1) // 4].append(data[i] - wrist)
            for j in range(3):
                self.fingers[(i - 1) // 4].append(data[i + j + 1] - data[i + j])

    def get_shape_features(self) -> np.ndarray:
        result: list = []
        """
        0..14 - phalangeal angles
        15..18 - spread angles
        19..23 - pinches angles
        """
        for i in range(5):
            for j in range(3):
                # Angles between every two phalangas in every finger
                result.append(vec_norm_angle(self.fingers[i][j], self.fingers[i][j + 1]))
        fingers_vecs: list = [self.data[i + 3] - self.data[i] for i in range(1, 20, 4)]
        for i in range(4):
            # Normalized angles between finger vectors
            result.append(vec_norm_angle(fingers_vecs[i], fingers_vecs[i + 1]))
        for i in range(8, 21, 4):
            # Distance between fingertips 1..4 and thumb fingertip
            result.append(dot_dist(self.data[i], self.data[4]) / self.palm_scale)
        # Distance between index and middle fingertips
        result.append(dot_dist(self.data[12], self.data[8]) / self.palm_scale)

        return np.array(result)
