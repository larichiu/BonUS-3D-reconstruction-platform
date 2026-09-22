import importlib
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
from streamlit.testing.v1 import AppTest
from bone_config import ROOT
from dataset_upload import extract_dataset, validate_dataset

class ReleaseTests(unittest.TestCase):
    def test_sample_upload(self):
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)/'dataset'
            summary=extract_dataset(ROOT/'sample_data'/'sawbone_sample.zip', target)
            self.assertEqual(sum(x['frames'] for x in summary), 36)
            self.assertEqual(sum(x['masks'] for x in summary), 36)

    def test_reject_traversal(self):
        archive=io.BytesIO()
        with zipfile.ZipFile(archive,'w') as z:
            z.writestr('../outside.png', b'bad')
        archive.seek(0)
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)/'dataset'
            with self.assertRaises(ValueError): extract_dataset(archive,target)
            self.assertFalse(target.exists())
            self.assertFalse((Path(temp)/'outside.png').exists())

    def test_reject_misaligned_mask(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'dataset'
            extract_dataset(ROOT/'sample_data'/'sawbone_sample.zip',root)
            mask=next(root.glob('*/*/sequence_000/masks/*.png'))
            Image.new('L',(3,3),255).save(mask)
            with self.assertRaisesRegex(ValueError,'dimensions'): validate_dataset(root)

    def test_all_variants_reconstruct(self):
        for version in ('original','lc_v1','lc_v1_1','lc_v2'):
            with self.subTest(version=version):
                io_module=importlib.import_module(f'variants.{version}.core.io')
                models=importlib.import_module(f'variants.{version}.core.models')
                recon=importlib.import_module(f'variants.{version}.core.reconstruct')
                data=io_module.load_patient(ROOT/'sample_data/sawbone/right/sequence_000')
                points=recon.reconstruct(data,models.ReconstructionSettings(orientation_deg=(45,-90,0)))
                self.assertGreater(len(points),0)
                self.assertTrue(np.isfinite(points[['x','y','z']]).all().all())

    def test_pixel_export_consistency(self):
        from variants.lc_v2.core.io import load_patient
        from variants.lc_v2.core.models import ReconstructionSettings
        from variants.lc_v2.core.calibration_export import boundary_pixel_export, frame_transform, transform_pixels
        data=load_patient(ROOT/'sample_data/sawbone/right/sequence_000')
        row=data.matches.iloc[0]
        settings=ReconstructionSettings(orientation_deg=(45,-90,0))
        pixels=boundary_pixel_export(row,data,settings)
        transform,_=frame_transform(row,settings)
        xyz=transform_pixels(pixels[['pixel_u','pixel_v']].to_numpy(),transform,settings)
        np.testing.assert_allclose(xyz,pixels[['x_mm','y_mm','z_mm']])

    def test_app_versions_and_about(self):
        app=AppTest.from_file(str(ROOT/'streamlit_app.py'), default_timeout=90).run()
        self.assertFalse(app.exception, str(app.exception))
        for version in ['Original','LCedit v1 — rotations','LCedit v1.1 — mirror + rotations','LCedit v2 — pixel analysis']:
            app.selectbox(key='release_variant').select(version).run()
            self.assertFalse(app.exception, str(app.exception))
            self.assertEqual(len(app.session_state['patient'].matches),12)
            self.assertGreater(len(app.session_state['points']),0)
            next(x for x in app.checkbox if x.label == 'Combine patient sequences with masks').check().run()
            next(x for x in app.checkbox if x.label == 'Same fixed reference marker and calibration across these scans').check().run()
            self.assertFalse(app.exception, str(app.exception))
            self.assertEqual(len(app.session_state['patient'].matches),36)
            self.assertGreater(len(app.session_state['points']),0)
        app.radio(key='release_page').set_value('About & development').run()
        self.assertFalse(app.exception, str(app.exception))
        self.assertTrue(any('Development brief' in x.value for x in app.markdown))

    def test_upload_app_flow(self):
        app=AppTest.from_file(str(ROOT/'streamlit_app.py'), default_timeout=90).run()
        data=io.BytesIO((ROOT/'sample_data'/'sawbone_sample.zip').read_bytes())
        with patch('streamlit.file_uploader', return_value=data):
            app.radio(key='release_source').set_value('Upload dataset ZIP').run()
        self.assertFalse(app.exception, str(app.exception))
        self.assertEqual(sum(row['frames'] for row in app.session_state['release_upload_summary']),36)
        self.assertGreater(len(app.session_state['points']),0)
        app.session_state['release_workspace'].cleanup()

if __name__ == '__main__': unittest.main()
