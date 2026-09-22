"""Display-only camera orientation; never changes reconstruction coordinates."""
import numpy as np


def horizontal_scan_camera(xyz):
    points = np.asarray(xyz, dtype=float)
    points = points[np.isfinite(points).all(axis=1)]
    if len(points) < 2:
        return None
    right = points[-1] - points[0]
    if np.linalg.norm(right) < 1e-6:
        return None
    right /= np.linalg.norm(right)
    up = np.array([0., 0., 1.])
    if abs(np.dot(up, right)) > .95:
        up = np.array([0., 1., 0.])
    up -= np.dot(up, right) * right
    up /= np.linalg.norm(up)
    eye = np.cross(right, up) * 2.0
    return dict(eye=dict(zip('xyz', eye)), up=dict(zip('xyz', up)),
                center=dict(x=0,y=0,z=0), projection=dict(type='orthographic'))
