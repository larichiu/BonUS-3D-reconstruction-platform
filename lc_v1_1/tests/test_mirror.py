import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
import numpy as np
import pandas as pd
from PIL import Image
from core.models import PatientData, ReconstructionSettings
from core.mirror import mirror,sha256,anatomy_label
from core.reconstruct import reconstruct
from core.calibration_export import v1_coordinate_export


class MirrorTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root=Path(self.directory.name)/'originals'/'sawbone'/'right'/'sequence_000'
        root.mkdir(parents=True)
        self.image=np.arange(3*5*3,dtype=np.uint8).reshape(3,5,3)
        self.mask=np.zeros((3,5,4),dtype=np.uint8)
        self.mask[1,0]=[220,10,20,255]
        self.mask[2,3]=[40,50,60,255]
        image_path=root/'frame_000000.png'; mask_path=root/'mask_000000.png'
        Image.fromarray(self.image).save(image_path)
        Image.fromarray(self.mask).save(mask_path)
        self.hashes={p:sha256(p) for p in [image_path,mask_path]}
        row=dict(FrameIndex=0,has_frame=True,has_mask=True,has_pose=True,frame_path=image_path,mask_path=mask_path,mask_status='accepted')
        for prefix in ['Prob','Ref']:
            for index,value in enumerate([0,0,0,1,0,0,0],1):row[f'{prefix}_{index}']=value
        table=pd.DataFrame([row])
        self.data=PatientData(root,root,root,root/'tracking.xlsx',table.copy(),table,(5,3))
        self.output=Path(self.directory.name)/'derived'

    def test_both_files_mirrored_losslessly_and_sources_preserved(self):
        data=mirror(self.data,self.output)
        row=data.matches.iloc[0]
        with Image.open(row.frame_path) as im:np.testing.assert_array_equal(np.asarray(im),self.image[:,::-1])
        with Image.open(row.mask_path) as im:np.testing.assert_array_equal(np.asarray(im),self.mask[:,::-1])
        for path,digest in self.hashes.items():self.assertEqual(sha256(path),digest)
        self.assertEqual(row.frame_path.name,'frame_000000_for3Drecon.png')
        self.assertEqual(row.mask_path.name,'mask_000000_for3Drecon.png')
        self.assertEqual(data.frames_dir.parent.name,'sequence_000_for3Drecon')
        pd.testing.assert_frame_equal(data.poses,self.data.poses)
        self.assertTrue((data.frames_dir.parent/'mirror_manifest.csv').exists())

    def test_repeat_does_not_flip_twice_and_changed_sources_refresh(self):
        first=mirror(self.data,self.output)
        target=first.matches.iloc[0].frame_path
        before=target.stat().st_mtime_ns
        second=mirror(self.data,self.output)
        self.assertEqual(second.matches.iloc[0].frame_path.stat().st_mtime_ns,before)
        with self.assertRaisesRegex(ValueError,'already mirrored'):
            mirror(first,self.output)
        changed=self.image.copy();changed[0,0]=[90,80,70]
        Image.fromarray(changed).save(self.data.matches.iloc[0].frame_path)
        updated=mirror(self.data,self.output)
        with Image.open(updated.matches.iloc[0].frame_path) as im:np.testing.assert_array_equal(np.asarray(im),changed[:,::-1])

    def test_mirrored_reconstruction_and_export_matrix_use_copies(self):
        data=mirror(self.data,self.output)
        settings=ReconstructionSettings(spacing_x_mm=1,spacing_y_mm=1,tip_offset_mm=(0,0,0),flip_horizontal=False,flip_depth=False,sample_step_px=1)
        cloud=reconstruct(data,settings)
        np.testing.assert_array_equal(cloud[['u','v']],[[1,2],[4,1]])
        np.testing.assert_allclose(cloud[['x','y','z']],[[1,0,2],[4,0,1]])
        exported,matrices=v1_coordinate_export(cloud,data,settings)
        np.testing.assert_array_equal(exported[['source_u','source_v']],[[3,2],[0,1]])
        transform=matrices.iloc[0][[f'SourcePixel_T_{i}{j}' for i in range(4) for j in range(4)]].to_numpy(float).reshape(4,4)
        for _,row in exported.iterrows():
            np.testing.assert_allclose(transform@[row.source_u,row.source_v,0,1],[row.x,row.y,row.z,1])

    def test_anatomical_mapping_only_applies_to_right_side(self):
        self.assertEqual(anatomy_label('right','sequence_000'),'Medial · left')
        self.assertEqual(anatomy_label('right','sequence_001'),'Apex · middle')
        self.assertEqual(anatomy_label('right','sequence_002'),'Lateral · right')
        self.assertEqual(anatomy_label('left','sequence_000'),'Unspecified')
