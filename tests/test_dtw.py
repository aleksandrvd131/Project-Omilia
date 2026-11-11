import numpy as np

from project_omilia import gestures


def test_dtw():
    a = np.array([[0.0], [1.0], [2.0]])
    b = np.array([[0.0], [0.0], [1.0], [2.0]])
    c = np.array([[2.0], [1.0], [0.0]])
    assert gestures.dtw_distance(a, b) == 0
    assert gestures.dtw_distance(b, b) == 0
    assert gestures.dtw_distance(a, c) > 0
