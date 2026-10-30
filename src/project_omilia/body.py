import numpy as np

from project_omilia.errors import IncorrectDataError
from project_omilia.math import p_dist, scalar_to_vec, vec_norm_angle, vec_normalize

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
        data = [np.array((i.x, i.y, i.z)) for i in data]
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
        # Vectors between each phalanga in every finger
        for i in range(1, 20, 4):
            self.fingers[(i - 1) // 4].append(data[i] - wrist)
            for j in range(3):
                self.fingers[(i - 1) // 4].append(data[i + j + 1] - data[i + j])

    def get_shape_features(self) -> list:
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
            result.append(vec_normalize(scalar_to_vec(p_dist(self.data[i], self.data[4]) / self.palm_scale)))
        # Distance between index and middle fingertips
        result.append(vec_normalize(scalar_to_vec(p_dist(self.data[12], self.data[8]) / self.palm_scale)))

        return result

    def get_1d_array(self) -> list:
        """
        Summary.
            Makes from various data appropriate thing
        Returns:
            List of hand's 3D vectors (described before)
        """
        result: list = [(vec for vec in finger) for finger in self.fingers]
        result.append(self.normal)
        result += self.get_shape_features()
        return result

class Pose:

    nose: np.ndarray
    left_to_nose: np.ndarray
    right_to_nose: np.ndarray
    left_hand: Hand | None
    right_hand: Hand

    def __init__(self, data: list, hands: tuple[list, list]):
        if len(data) != POINTS_IN_BODY:
            raise IncorrectDataError(
                "Wrong amount of points in body.\n"
            )
        else:
            self.nose = np.array(data[0])
            # Vector from each hand to nose
            self.right_to_nose = np.array(data[15]) - np.array(data[0])
            self.left_to_nose = np.array(data[16]) - np.array(data[0])

        # Distance from right hand wrist to hands' wrist
        is_right_hand = lambda hand_data: p_dist(np.array((hand_data[0].x, hand_data[0].y, hand_data[0].z)), data[15]) \
            < p_dist(np.array((hand_data[0].x, hand_data[0].y, hand_data[0].z)), data[16])
        match len(hands):
            case 0:
                raise IncorrectDataError(
                    "No hands found in data.\n"
                )
            case 1:
                self.left_hand = None
                if not is_right_hand(hands[0]):
                    for point in hands[0]:
                        point.x = 2 * data[0][0] - point.x
                self.right_hand = Hand(hands[0], True)

            case 2:
                if is_right_hand(hands[0]):
                    self.left_hand = Hand(hands[1], False)
                    self.right_hand = Hand(hands[0], True)
                else:
                    self.left_hand = Hand(hands[0], False)
                    self.right_hand = Hand(hands[1], True)

    def get_1d_array_one_hand(self) -> np.ndarray:
        """
        Summary.
            For 1 hand case generates 1D np.array of 3D vectors
            for model use
        Returns:
            np.array of vectors
        """
        result: list = self.right_hand.get_1d_array()
        result.append(self.right_to_nose)
        return np.array(result)

    def get_1d_array_two_hands(self) -> np.ndarray:
        """
        Summary.
            For 2 hands case generates 1D np.array of 3D vectors
            for model use
        """
        result: list = self.right_hand.get_1d_array()
        result += self.left_hand.get_1d_array()
        result.append(self.right_to_nose)
        result.append(self.left_to_nose)
        return np.array(result)
