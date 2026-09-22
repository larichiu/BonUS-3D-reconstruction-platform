import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from PIL import Image
from core.models import PatientData, ReconstructionSettings
from core.anatomical_view import scan_start_view,plotly_camera


class AnatomicalViewTests(unittest.TestCase):
    def test_start_camera_preserves_motion_and_left_right_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            mask=root/'mask.png'
            Image.fromarray(np.ones((2,3),dtype=np.uint8)*255).save(mask)
            records=[]
            for index,x in enumerate([0,10,20]):
                for frame in [0,1]:
                    row=dict(sequence=f'right/sequence_{index:03d}',FrameIndex=index*2+frame,
                        frame_path=mask,mask_path=mask,has_frame=True,has_mask=True,has_pose=True)
                    for prefix,values in [('Prob',[x,0,100*frame,1,0,0,0]),('Ref',[0,0,0,1,0,0,0])]:
                        row.update({f'{prefix}_{i}':value for i,value in enumerate(values,1)})
                    records.append(row)
            rows=pd.DataFrame(records)
            data=PatientData(root,root,root,mask,rows.copy(),rows,(3,2))
            settings=ReconstructionSettings(tip_offset_mm=(0,0,0),flip_horizontal=False,flip_depth=False)
            view,note=scan_start_view(data,settings)
            np.testing.assert_allclose(view['eye'],[0,0,-2.5])
            np.testing.assert_allclose(np.cross([0,0,1],view['up']),[1,0,0])
            self.assertNotIn('mismatch',note)
            self.assertEqual(plotly_camera(view)['projection']['type'],'orthographic')
            original=rows.copy()
            scan_start_view(data,settings)
            pd.testing.assert_frame_equal(rows,original)
            data.matches.loc[data.matches.sequence=='right/sequence_001','Prob_1']=40
            _,note=scan_start_view(data,settings)
            self.assertIn('calibration/alignment mismatch',note)
