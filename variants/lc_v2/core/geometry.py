from __future__ import annotations

import numpy as np


def rotation_from_wxyz(values) -> np.ndarray:
    """Return a 3x3 rotation matrix from NDI quaternion fields w,x,y,z."""
    q = np.asarray(values, dtype=np.float64)
    if q.shape != (4,) or not np.all(np.isfinite(q)):
        raise ValueError("Quaternion must contain four finite values.")
    norm = np.linalg.norm(q)
    if norm < 1e-12:
        raise ValueError("Quaternion has zero magnitude.")
    w, x, y, z = q / norm
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ], dtype=np.float64)


def point_in_reference(
    local_probe_point: np.ndarray,
    probe_position: np.ndarray,
    probe_rotation: np.ndarray,
    reference_position: np.ndarray,
    reference_rotation: np.ndarray,
) -> np.ndarray:
    """Transform a probe-local point to the leg-attached reference frame."""
    tracker_point = probe_position + probe_rotation @ local_probe_point
    return reference_rotation.T @ (tracker_point - reference_position)


def points_in_reference(
    local_probe_points: np.ndarray,
    probe_position: np.ndarray,
    probe_rotation: np.ndarray,
    reference_position: np.ndarray,
    reference_rotation: np.ndarray,
) -> np.ndarray:
    tracker_points = probe_position[None, :] + local_probe_points @ probe_rotation.T
    return (tracker_points - reference_position[None, :]) @ reference_rotation
