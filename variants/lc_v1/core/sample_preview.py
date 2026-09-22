"""Evenly spaced original frames from every selected sequence."""
from dataclasses import replace
import numpy as np
import plotly.graph_objects as go

from .calibration_export import frame_transform, transform_pixels
from .frame_view import add_frame_plane
from .reconstruct import load_binary_mask, upper_boundary


def sample_sequence_frames(matches, count):
    eligible = matches.loc[matches.has_frame & matches.has_mask & matches.has_pose]
    groups = eligible.groupby('sequence', sort=False) if 'sequence' in eligible else [('Selected sequence', eligible)]
    samples = []
    for label, rows in groups:
        rows = rows.sort_values('FrameIndex')
        indices = np.unique(np.linspace(0, len(rows)-1, min(count, len(rows))).round().astype(int))
        for index in indices:
            samples.append((label, rows.iloc[index]))
    return samples


def sample_preview_figure(samples, settings, image_size, original_outline=True):
    fig = go.Figure()
    colors = ['#ef853b', '#ac77ed', '#eb5286', '#e2b628', '#278ae1', '#2faa86']
    labels = list(dict.fromkeys(label for label, _ in samples))
    baseline = replace(settings, rotation_u_deg=0., rotation_v_deg=0.)
    seen = set()
    for index, (label, row) in enumerate(samples):
        color = colors[labels.index(label) % len(colors)]
        frame_label = row.get('frame_label', f"{label} · frame {int(row['FrameIndex'])}")
        # Use the same image-plane mapping as reconstruction, with real saved pixels.
        before = len(fig.data)
        add_frame_plane(fig, row, settings)
        for trace in fig.data[before:]:
            trace.showlegend = False
            if isinstance(trace, go.Surface):
                trace.opacity = .72
                trace.name = frame_label
            elif isinstance(trace, go.Scatter3d):
                trace.mode = 'markers'
        transform, _ = frame_transform(row, settings)
        pixels = upper_boundary(load_binary_mask(row['mask_path'], settings.mask_threshold), 1)
        xyz = transform_pixels(pixels, transform, settings)
        fig.add_trace(go.Scatter3d(x=xyz[:,0], y=xyz[:,1], z=xyz[:,2], mode='lines',
            line=dict(color=color, width=5), name=f'{label} · mask boundary',
            legendgroup=label, showlegend=label not in seen,
            hovertemplate=f'{frame_label}<br>x=%{{x:.2f}}<br>y=%{{y:.2f}}<br>z=%{{z:.2f}}<extra></extra>'))
        seen.add(label)
        tip = transform[:3,3]
        for axis_index, axis_label, axis_color in [(0,'u','#2489ef'),(1,'v','#19ae83')]:
            end = tip + transform[:3,axis_index]*15
            fig.add_trace(go.Scatter3d(x=[tip[0],end[0]], y=[tip[1],end[1]], z=[tip[2],end[2]],
                mode='lines+text', text=['',axis_label], line=dict(color=axis_color,width=6),
                name=f'{axis_label} · rotated image direction', showlegend=index==0,
                hovertemplate=f'{frame_label} · {axis_label}<extra></extra>'))
        fig.add_trace(go.Scatter3d(x=[tip[0]],y=[tip[1]],z=[tip[2]],mode='markers',
            marker=dict(size=5,color='#ffb14e',symbol='diamond'),name='Calibrated tip · rotation pivot',
            showlegend=index==0,hovertemplate=f'{frame_label} · tip<extra></extra>'))
        if original_outline:
            original, _ = frame_transform(row, baseline)
            w,h = image_size
            corners = np.array([[0,0],[w-1,0],[w-1,h-1],[0,h-1],[0,0]])
            outline = transform_pixels(corners, original, settings)
            fig.add_trace(go.Scatter3d(x=outline[:,0],y=outline[:,1],z=outline[:,2],mode='lines',
                line=dict(color='#83919e',width=3,dash='dash'), name='Original plane · u=0°, v=0°',
                showlegend=index==0,hovertemplate=f'{frame_label} · original orientation<extra></extra>'))
    fig.update_layout(height=610, scene_aspectmode='data',
        margin=dict(l=0,r=0,t=10,b=60),legend=dict(orientation='h',y=-.05),
        scene=dict(xaxis_title='X (mm)',yaxis_title='Y (mm)',zaxis_title='Z (mm)'))
    return fig
