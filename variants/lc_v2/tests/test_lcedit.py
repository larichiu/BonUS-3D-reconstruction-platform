import tempfile
import unittest
import zipfile
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from core.models import PatientData, ReconstructionSettings
from core.calibration_export import boundary_pixel_export, frame_transform, transform_pixels, v1_coordinate_export, write_boundary_archive
from core.geometry import points_in_reference, rotation_from_wxyz
from core.reconstruct import reconstruct


class LCeditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name) / 'patient' / 'right' / 'sequence_000'
        root.mkdir(parents=True)
        mask = np.zeros((5, 4), dtype=np.uint8)
        mask[3:, 0] = 255
        mask[1:4, 2] = 255
        path = root / 'mask.png'
        Image.fromarray(mask).save(path)
        row = {'FrameIndex': 7, 'has_mask': True, 'has_pose': True, 'has_frame': True,
               'mask_path': path, 'frame_path': path, 'mask_status': 'accepted',
               'Prob_1': 10, 'Prob_2': 20, 'Prob_3': 30, 'Prob_4': 1, 'Prob_5': 0, 'Prob_6': 0, 'Prob_7': 0,
               'Ref_1': 4, 'Ref_2': 5, 'Ref_3': 6, 'Ref_4': 1, 'Ref_5': 0, 'Ref_6': 0, 'Ref_7': 0,
               'SourceIndex': 99}
        self.row = pd.Series(row)
        self.data = PatientData(root, root, root, root / 'poses.xlsx', pd.DataFrame([row]), pd.DataFrame([row]), (4, 5))
        self.settings = ReconstructionSettings(spacing_x_mm=2, spacing_y_mm=3, tip_offset_mm=(1, 2, 3),
                                               flip_horizontal=False, flip_depth=False, sample_step_px=20, frame_step=20)

    def test_all_upper_boundary_pixels_ignore_reconstruction_sampling(self):
        exported = boundary_pixel_export(self.row, self.data, self.settings)
        np.testing.assert_array_equal(exported[['pixel_u', 'pixel_v']], [[0, 3], [2, 1]])
        np.testing.assert_allclose(exported[['x_mm', 'y_mm', 'z_mm']], [[7, 17, 36], [11, 17, 30]])
        np.testing.assert_allclose(exported['distance_from_probe_tip_mm'], [9, 5])
        np.testing.assert_allclose(exported[['probe_tip_x_mm', 'probe_tip_y_mm', 'probe_tip_z_mm']], [[7, 17, 27]] * 2)
        self.assertTrue((exported.SourceIndex == 99).all())

    def test_matrix_matches_existing_geometry_with_nontrivial_tracking(self):
        row = self.row.copy()
        row[['Prob_4', 'Prob_5', 'Prob_6', 'Prob_7']] = [0.7, 0.2, -0.1, 0.6]
        row[['Ref_4', 'Ref_5', 'Ref_6', 'Ref_7']] = [0.4, 0.6, 0.2, -0.3]
        settings = replace(self.settings, orientation_deg=(45, -90, 0), flip_horizontal=True, flip_depth=True)
        pixels = np.array([[0, 0], [10, 30], [3, 4]])
        expected = points_in_reference(settings.image_points(pixels[:, 0], pixels[:, 1]),
            row[['Prob_1','Prob_2','Prob_3']].to_numpy(float), rotation_from_wxyz(row[['Prob_4','Prob_5','Prob_6','Prob_7']]),
            row[['Ref_1','Ref_2','Ref_3']].to_numpy(float), rotation_from_wxyz(row[['Ref_4','Ref_5','Ref_6','Ref_7']]))
        matrix, _ = frame_transform(row, settings)
        np.testing.assert_allclose(transform_pixels(pixels, matrix, settings), expected, atol=1e-12)
        np.testing.assert_allclose(matrix[:3,:3].T @ matrix[:3,:3], np.eye(3), atol=1e-12)
        self.assertAlmostEqual(np.linalg.det(matrix[:3,:3]), 1)

    def test_tracker_coordinates_when_reference_disabled(self):
        settings = replace(self.settings, use_reference=False)
        exported = boundary_pixel_export(self.row, self.data, settings)
        np.testing.assert_allclose(exported[['x_mm','y_mm','z_mm']], [[11,22,42], [15,22,36]])
        np.testing.assert_allclose(exported.distance_from_probe_tip_mm, [9,5])

    def test_archive_has_separate_frames_and_explicit_skipped_reason(self):
        rows = self.data.matches.copy()
        bad = rows.iloc[0].copy()
        bad['FrameIndex'] = 8
        bad['Prob_4'] = 0
        rows = pd.concat([rows, pd.DataFrame([bad])], ignore_index=True)
        output = Path(self.temp.name) / 'export.zip'
        report, count = write_boundary_archive(output, rows, self.data, self.settings)
        self.assertEqual(count, 2)
        self.assertEqual(report.status.tolist(), ['exported', 'skipped'])
        self.assertIn('zero magnitude', report.iloc[1].reason)
        with zipfile.ZipFile(output) as archive:
            self.assertIn('frame_manifest.csv', archive.namelist())
            exported = pd.read_csv(archive.open('frames/frame_00000007.csv'))
            self.assertEqual(len(exported), 2)
            self.assertEqual(len(pd.read_csv(archive.open('frame_manifest.csv'))), 2)

    def test_nonfinite_positions_and_wrong_mask_shape_rejected(self):
        row = self.row.copy()
        row['Prob_1'] = float('nan')
        with self.assertRaisesRegex(ValueError, 'Non-finite'):
            boundary_pixel_export(row, self.data, self.settings)
        with self.assertRaisesRegex(ValueError, 'dimensions'):
            boundary_pixel_export(self.row, replace(self.data, frame_size=(10,10)), self.settings)

    @unittest.skipUnless(hasattr(ReconstructionSettings, 'rotation_u_deg'), 'V1-only rotation')
    def test_u_v_rotations_and_order(self):
        u_settings = replace(self.settings, rotation_u_deg=90)
        v_settings = replace(self.settings, rotation_v_deg=90)
        both = replace(self.settings, rotation_u_deg=90, rotation_v_deg=90)
        np.testing.assert_allclose(u_settings.image_points(np.array([1]), np.array([1])) - u_settings.tip_offset, [[2,-3,0]], atol=1e-12)
        np.testing.assert_allclose(v_settings.image_points(np.array([1]), np.array([1])) - v_settings.tip_offset, [[0,2,3]], atol=1e-12)
        np.testing.assert_allclose(both.image_points(np.array([1]), np.array([1])) - both.tip_offset, [[3,2,0]], atol=1e-12)
        for settings in [u_settings, v_settings, both]:
            np.testing.assert_allclose(settings.image_points(np.array([0]), np.array([0])), [self.settings.tip_offset])
            exported = boundary_pixel_export(self.row, self.data, settings)
            np.testing.assert_allclose(exported.distance_from_probe_tip_mm, [9,5], atol=1e-12)

    @unittest.skipUnless(hasattr(ReconstructionSettings, 'rotation_u_deg'), 'V1-only rotation')
    def test_zero_adjustments_preserve_original_basis(self):
        settings = replace(self.settings, orientation_deg=(45,-90,0), flip_horizontal=True, flip_depth=True)
        np.testing.assert_allclose(settings.image_basis, settings.baseline_image_basis, atol=1e-12)

    @unittest.skipUnless(hasattr(ReconstructionSettings, 'rotation_u_deg'), 'V1-only export')
    def test_v1_csv_xyz_and_matrix_reproduce_reconstruction(self):
        settings = replace(self.settings, rotation_u_deg=30, rotation_v_deg=-40, sample_step_px=1)
        cloud = reconstruct(self.data, settings)
        csv, matrices = v1_coordinate_export(cloud, self.data, settings)
        self.assertEqual(len(matrices), 1)
        np.testing.assert_allclose(csv[['new_x_mm','new_y_mm','new_z_mm']], cloud[['x','y','z']])
        np.testing.assert_allclose(csv[['original_x_mm','original_y_mm','original_z_mm']], [[7,17,36], [11,17,30]])
        matrix = csv.iloc[0][[f'T_{i}{j}' for i in range(4) for j in range(4)]].to_numpy(float).reshape(4,4)
        np.testing.assert_allclose(matrix @ [0,9,0,1], [*cloud.iloc[0][['x','y','z']],1], atol=1e-12)


if __name__ == '__main__':
    unittest.main()
