import unittest
import pandas as pd
import plotly.graph_objects as go
from core.bone_display import add_bone_traces


class BoneDisplayTests(unittest.TestCase):
    def test_cached_points_without_sequence(self):
        points = pd.DataFrame({'frame_index': [1,2,3,4], 'x': [1,2,3,4], 'y': [0]*4, 'z': [0]*4})
        matches = pd.DataFrame({'FrameIndex': [1,2,3,4], 'sequence': ['a','a','b','b'],
                                'mask_status': ['accepted','propagated']*2})
        fig = go.Figure()
        add_bone_traces(fig, points, matches, combined=True)
        self.assertEqual(len(fig.data), 4)
        self.assertEqual([t.marker.opacity for t in fig.data], [1,.05,1,.05])
        self.assertEqual(fig.data[0].marker.color, fig.data[1].marker.color)
        self.assertNotEqual(fig.data[0].marker.color, fig.data[2].marker.color)
        self.assertNotIn('sequence', points)  # Display does not mutate cached/export data.
        filtered = go.Figure()
        add_bone_traces(filtered, points.iloc[2:], matches, combined=True)
        self.assertEqual(filtered.data[0].marker.color, fig.data[2].marker.color)

    def test_single_sequence_unchanged(self):
        points = pd.DataFrame({'frame_index': [1,2], 'x': [1,2], 'y': [0,0], 'z': [0,0]})
        matches = pd.DataFrame({'FrameIndex': [1,2], 'mask_status': ['accepted','propagated']})
        fig = go.Figure()
        add_bone_traces(fig, points, matches)
        self.assertEqual([t.marker.color for t in fig.data], ['#16c775','#f59e42'])
        self.assertEqual([t.marker.opacity for t in fig.data], [1,.1])
