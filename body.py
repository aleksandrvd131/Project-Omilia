import numpy as np

from project_omilia.errors import IncorrectDataError
from project_omilia.math import p_dist, vec_norm_angle, vec_normalize

POINTS_IN_HAND: int = 21
POINTS_IN_BODY: int = 33


class Hand:
    data: list[np.ndarray]
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
        pts: list[np.ndarray] = []
        for p in data:
            if hasattr(p, "x"):
                pts.append(np.array([p.x, p.y, p.z], dtype=np.float32))
            elif isinstance(p, dict):
                pts.append(np.array([p["x"], p["y"], p.get("z", 0.0)], dtype=np.float32))
            else:
                pts.append(np.array([p[0], p[1], p[2]], dtype=np.float32))
        self.data = pts

        wrist = self.data[0]
        self.palm_scale = max(p_dist(wrist, self.data[9]), 0.01)

        v1 = self.data[5] - wrist
        v2 = self.data[17] - wrist
        if self.is_right:
            self.normal = np.cross(v1, v2)
        else:
            self.normal = np.cross(v2, v1)
        self.normal = vec_normalize(self.normal)

        self.fingers = [[] for _ in range(5)]
        # Vectors between each phalanga in every finger
        for i in range(1, 20, 4):
            self.fingers[(i - 1) // 4].append(self.data[i] - wrist)
            for j in range(3):
                self.fingers[(i - 1) // 4].append(self.data[i + j + 1] - self.data[i + j])

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
            result.append(float(np.clip(p_dist(self.data[i], self.data[4]) / (self.palm_scale * 2.2), 0.0, 1.0)))
        # Distance between index and middle fingertips
        result.append(float(np.clip(p_dist(self.data[12], self.data[8]) / (self.palm_scale * 1.5), 0.0, 1.0)))

        palm_dir = self.data[9] - self.data[0]
        angle_rad = np.arctan2(-palm_dir[1], palm_dir[0])
        result.append(float(np.cos(angle_rad) * 0.4))
        result.append(float(np.sin(angle_rad) * 0.4))

        return result

    def get_1d_array(self) -> list:
        """
        Summary.
            Makes from various data appropriate thing
        Returns:
            List of hand's 3D vectors (described before)
        """
        result: list[float] = [float(coord) for finger in self.fingers for vec in finger for coord in vec]
        result.extend(self.normal.tolist())
        result += self.get_shape_features()
        return result


class Pose:
    nose: np.ndarray
    left_to_nose: np.ndarray
    right_to_nose: np.ndarray
    left_hand: Hand | None
    right_hand: Hand

    def __init__(self, data: list, hands: tuple[list, ...] | list[list]):
        if len(data) != POINTS_IN_BODY:
            raise IncorrectDataError(
                "Wrong amount of points in body.\n"
            )
        else:
            body_pts: list[np.ndarray] = []
            for p in data:
                if hasattr(p, "x"):
                    body_pts.append(np.array([p.x, p.y, p.z], dtype=np.float32))
                elif isinstance(p, dict):
                    body_pts.append(np.array([p["x"], p["y"], p.get("z", 0.0)], dtype=np.float32))
                else:
                    body_pts.append(np.array([p[0], p[1], p[2]], dtype=np.float32))

            self.nose = body_pts[0]
            # Vector from each hand to nose
            self.left_to_nose = body_pts[15] - self.nose
            self.right_to_nose = body_pts[16] - self.nose

        def get_wrist(h_pts: list) -> np.ndarray:
            p0 = h_pts[0]
            if hasattr(p0, "x"):
                return np.array([p0.x, p0.y, p0.z], dtype=np.float32)
            if isinstance(p0, dict):
                return np.array([p0["x"], p0["y"], p0.get("z", 0.0)], dtype=np.float32)
            return np.array([p0[0], p0[1], p0[2]], dtype=np.float32)

        # Distance from right hand wrist to hands' wrist
        is_right_hand = lambda hand_data: p_dist(get_wrist(hand_data), body_pts[16]) \
            < p_dist(get_wrist(hand_data), body_pts[15])

        match len(hands):
            case 0:
                raise IncorrectDataError(
                    "No hands found in data.\n"
                )
            case 1:
                self.left_hand = None
                if not is_right_hand(hands[0]):
                    mirrored: list = []
                    nose_x = float(self.nose[0])
                    for point in hands[0]:
                        if hasattr(point, "x"):
                            class MirroredPoint:
                                def __init__(self, x: float, y: float, z: float):
                                    self.x, self.y, self.z = x, y, z
                            mirrored.append(MirroredPoint(2.0 * nose_x - point.x, point.y, point.z))
                        elif isinstance(point, dict):
                            mirrored.append({"x": 2.0 * nose_x - point["x"], "y": point["y"], "z": point.get("z", 0.0)})
                        else:
                            mirrored.append([2.0 * nose_x - point[0], point[1], point[2]])
                    self.right_hand = Hand(mirrored, True)
                else:
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
        result.extend(self.right_to_nose.tolist())
        return np.array(result, dtype=np.float32)

    def get_1d_array_two_hands(self) -> np.ndarray:
        """
        Summary.
            For 2 hands case generates 1D np.array of 3D vectors
            for model use
        """
        result: list = self.right_hand.get_1d_array()
        if self.left_hand is not None:
            result.extend(self.left_hand.get_1d_array())
        else:
            result.extend([0.0] * len(self.right_hand.get_1d_array()))

        result.extend(self.right_to_nose.tolist())
        result.extend(self.left_to_nose.tolist())
        return np.array(result, dtype=np.float32)
