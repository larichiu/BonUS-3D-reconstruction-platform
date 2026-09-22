import unittest
import pandas as pd
from core.sample_preview import sample_sequence_frames


class SamplePreviewTests(unittest.TestCase):
    def test_samples_every_sequence_independently(self):
        rows = pd.DataFrame([dict(sequence=sequence, FrameIndex=offset+i,
            has_frame=True, has_mask=True, has_pose=True)
            for sequence, offset, count in [('right/sequence_000',0,101),('right/sequence_001',200,3)]
            for i in range(count)])
        samples = sample_sequence_frames(rows, 3)
        self.assertEqual([(label,int(row.FrameIndex)) for label,row in samples],
            [('right/sequence_000',0),('right/sequence_000',50),('right/sequence_000',100),
             ('right/sequence_001',200),('right/sequence_001',201),('right/sequence_001',202)])

    def test_small_sequence_and_missing_masks(self):
        rows = pd.DataFrame([dict(FrameIndex=i,has_frame=True,has_pose=True,has_mask=i!=1) for i in range(3)])
        samples = sample_sequence_frames(rows, 5)
        self.assertEqual([int(row.FrameIndex) for _,row in samples],[0,2])
        self.assertEqual(sample_sequence_frames(rows.iloc[0:0],3),[])
