import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from PIL import Image
from core.collection import combine_data
from core.models import PatientData, ReconstructionSettings
from core.reconstruct import reconstruct, probe_pathway


class CollectionTests(unittest.TestCase):
    def test_repeated_frame_numbers_share_reference_not_tracker_origin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            mask=root/'mask.png';Image.new('L',(2,2),255).save(mask)
            scans=[]
            for name,offset in [('sequence_000',100),('sequence_001',500)]:
                row={'FrameIndex':1,'Prob_1':offset+10,'Prob_2':0,'Prob_3':0,
                    'Ref_1':offset,'Ref_2':0,'Ref_3':0,'frame_path':mask,'mask_path':mask,
                    'has_mask':True,'has_pose':True,'has_frame':True,'mask_status':'accepted'}
                for prefix in ('Prob','Ref'):
                    for i,value in zip(range(4,8),(1,0,0,0)):row[f'{prefix}_{i}']=value
                table=pd.DataFrame([row])
                scans.append(PatientData(root/'right'/name,root,root,root/'tracking.xlsx',table.copy(),table,(2,2)))
            combined=combine_data(scans,root)
            self.assertEqual(combined.matches.FrameIndex.tolist(),[1,2])
            self.assertEqual(combined.matches.source_frame_index.tolist(),[1,1])
            settings=ReconstructionSettings(tip_offset_mm=(0,0,0),sample_step_px=1)
            points=reconstruct(combined,settings)
            groups=list(points.groupby('sequence',sort=False))
            np.testing.assert_allclose(groups[0][1][['x','y','z']],groups[1][1][['x','y','z']])
            for scan,(_,group) in zip(scans,groups):
                np.testing.assert_allclose(reconstruct(scan,settings)[['x','y','z']],group[['x','y','z']])
            self.assertEqual(probe_pathway(combined,settings).sequence.nunique(),2)

    def test_empty_collection_rejected(self):
        with self.assertRaises(ValueError):combine_data([],Path('.'))


if __name__=='__main__':unittest.main()
