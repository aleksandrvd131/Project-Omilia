import numpy as np
from project_omilia.errors import IncorrectDataError
from project_omilia.math import (
    p_dist,
    vec_len,
    vec_angle,
    vec_normalize,
    vec_norm_angle
)

POINTS_IN_HAND: int = 21
POINTS_IN_BODY: int = 33

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
        if len(data) != POINTS_IN_HAND:
            raise IncorrectDataError(
                "Wrong amount of points in hand.\n"
            )
        self.is_right = is_right
        data = [np.array(i) for i in data]
        self.data = data
        wrist = data[0]
        self.palm_scale = p_dist(wrist, data[9])
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
        """
        Summary.
            Determines details of hand to
            make it easier to model to differentiate
            one shape from another one.
        Returns:
            np.ndarray: various parameters (check below)
        """

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
            result.append(p_dist(self.data[i], self.data[4]) / self.palm_scale)
        # Distance between index and middle fingertips
        result.append(p_dist(self.data[12], self.data[8]) / self.palm_scale)

        return np.array(result)

class Pose:

    nose: np.ndarray
    shoulder_width: float
    chest_center: np.ndarray
    left_nose_dist: float
    right_nose_dist: float
    left_hand: Hand | None
    right_hand: Hand | None

    def __init__(self, data: list, hands: tuple[list, list]):
        if len(data) != POINTS_IN_BODY:
            # TODO
            pass
        else:
            self.nose = np.array(data[0])
            self.shoulder_width = p_dist(np.array(data[12]), np.array(data[11]))
            self.chest_center = (np.array(data[12]) + np.array(data[11])) / 2
            self.left_nose_dist = p_dist(np.array(data[0]), np.array(data[15]))
            self.right_nose_dist = p_dist(np.array(data[0]), np.array(data[16]))

        # Distance from right hand wrist to hands' wrist
        is_right_hand = lambda hand_data: p_dist(hand_data[0], data[16]) < p_dist(hand_data[0], data[15])
        match len(hands):
            case 0:
                raise IncorrectDataError(
                    "No hands found in data.\n"
                )
            case 1:
                self.left_hand = None
                if is_right_hand(hands[0]):
                    self.right_hand = Hand(hands[0], True)
                else:
                    # TODO: Нужно зеркалить руку!
                    pass
            case 2:
                if is_right_hand(hands[0]):
                    self.left_hand = Hand(hands[1], False)
                    self.right_hand = Hand(hands[0], True)
                else:
                    self.left_hand = Hand(hands[0], False)
                    self.right_hand = Hand(hands[1], True)

"""
TODO:
Если жест одноручный, то нужно привести жест к правой руке, т.е. отзеркалить руку
Но здесь надо понимать, есть ли разница между правой и левой рукой.
"""
