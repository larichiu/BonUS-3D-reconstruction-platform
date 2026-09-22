import numpy as np

from core.geometry import point_in_reference, rotation_from_wxyz
from core.reconstruct import upper_boundary
from core.models import PatientData, ReconstructionSettings
from core.reconstruct import probe_pathway


def test_identity_quaternion_wxyz():
    np.testing.assert_allclose(rotation_from_wxyz([1, 0, 0, 0]), np.eye(3), atol=1e-12)


def test_reference_translation_is_removed():
    point = point_in_reference(
        np.array([1.0, 2.0, 3.0]),
        np.array([10.0, 0.0, 0.0]),
        np.eye(3),
        np.array([4.0, 0.0, 0.0]),
        np.eye(3),
    )
    np.testing.assert_allclose(point, [7.0, 2.0, 3.0])


def test_upper_boundary_returns_first_foreground_row():
    mask = np.zeros((5, 4), dtype=bool)
    mask[3, 0] = True
    mask[1:4, 2] = True
    np.testing.assert_array_equal(upper_boundary(mask), [[0, 3], [2, 1]])


def test_probe_pathway_uses_tip_offset_and_all_valid_pose_rows(tmp_path):
    import pandas as pd

    poses = pd.DataFrame([
        {"FrameIndex": 0, "Prob_1": 10, "Prob_2": 20, "Prob_3": 30,
         "Prob_4": 1, "Prob_5": 0, "Prob_6": 0, "Prob_7": 0,
         "Ref_1": 1, "Ref_2": 2, "Ref_3": 3,
         "Ref_4": 1, "Ref_5": 0, "Ref_6": 0, "Ref_7": 0},
        {"FrameIndex": 4, "Prob_1": 11, "Prob_2": 20, "Prob_3": 30,
         "Prob_4": 1, "Prob_5": 0, "Prob_6": 0, "Prob_7": 0,
         "Ref_1": 1, "Ref_2": 2, "Ref_3": 3,
         "Ref_4": 1, "Ref_5": 0, "Ref_6": 0, "Ref_7": 0},
    ])
    data = PatientData(tmp_path, tmp_path, tmp_path, tmp_path / "poses.xlsx", poses, pd.DataFrame(), (10, 10))
    result = probe_pathway(data, ReconstructionSettings(tip_offset_mm=(1, 2, 3)))
    np.testing.assert_allclose(result[["x", "y", "z"]], [[10, 20, 30], [11, 20, 30]])
