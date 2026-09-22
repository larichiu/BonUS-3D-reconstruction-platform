import unittest
import numpy as np
import plotly.graph_objects as go
from variants.lc_v2.core.navigation import bone_view_ranges

class NavigationTests(unittest.TestCase):
    def test_focus_excludes_distant_tracker_and_keeps_equal_scale(self):
        fig=go.Figure([
            go.Scatter3d(x=[10,20],y=[30,35],z=[40,41],name='Accepted bone'),
            go.Scatter3d(x=[10000],y=[10000],z=[10000],name='NDI tracker origin'),
        ])
        ranges=bone_view_ranges(fig)
        np.testing.assert_allclose(ranges['x'],[9,21])
        self.assertEqual(len({round(v[1]-v[0],8) for v in ranges.values()}),1)

    def test_hidden_bone_does_not_set_focus(self):
        fig=go.Figure(go.Scatter3d(x=[1],y=[2],z=[3],name='Accepted bone',visible='legendonly'))
        self.assertIsNone(bone_view_ranges(fig))

    def test_combined_bone_has_finite_focus(self):
        fig=go.Figure(go.Scatter3d(x=[1,np.nan],y=[2,3],z=[3,4],name='right/sequence_000 · Accepted'))
        ranges=bone_view_ranges(fig)
        self.assertTrue(all(np.isfinite(v).all() for v in ranges.values()))
        self.assertTrue(all(v[1]>v[0] for v in ranges.values()))
