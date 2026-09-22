"""Display-only bone styles; never alter reconstruction coordinates or exports."""
import plotly.graph_objects as go
import hashlib
import re

PALETTE = ('#4C9AFF', '#E879F9', '#FBBF24', '#2DD4BF', '#FB7185',
           '#A78BFA', '#A3E635', '#38BDF8', '#FDBA74', '#F472B6')


def sequence_color(name):
    """Stable across filtering, mirrored series names, and display-label spacing."""
    canonical = str(name).replace(' ', '').replace('_for3Drecon', '').lower()
    match = re.search(r'sequence_(\d+)', canonical)
    index = int(match.group(1)) if match else int(hashlib.sha256(canonical.encode()).hexdigest()[:8], 16)
    if canonical.startswith('left/'):
        index += 3
    return PALETTE[index % len(PALETTE)]


def add_bone_traces(fig, points, matches, combined=False,
                    show_accepted=True, show_propagated=True):
    lookup = matches.set_index('FrameIndex')['mask_status'].to_dict() if 'mask_status' in matches else {}
    categories = points['frame_index'].map(lookup).fillna('accepted')
    colors = {}
    if combined:
        # Older cached reconstructions contain XYZ/frame IDs but no provenance.
        # Recover display metadata through the collection's unique frame IDs.
        points = points.copy()
        metadata = matches.set_index('FrameIndex')
        for column in ('sequence', 'frame_label'):
            if column in metadata:
                points[column] = points['frame_index'].map(metadata[column])
        if 'sequence' not in points or points['sequence'].isna().any():
            raise ValueError('Sequence mapping is unavailable. Create the bone reconstruction again for the selected collection.')
        # Derive colors from all loaded sequences, not the currently visible frames.
        names = sorted(matches['sequence'].dropna().unique())
        colors = {name: sequence_color(name) for name in names}
    groups = points.groupby('sequence', sort=True) if combined else [(None, points)]
    for sequence, group in groups:
        for status, visible, single_color, size, opacity in [
            ('accepted', show_accepted, '#16c775', 3.5, 1.0),
            ('propagated', show_propagated, '#f59e42', 2.0, 0.05 if combined else 0.1),
        ]:
            subset = group.loc[categories.reindex(group.index) == status]
            if not visible or subset.empty:
                continue
            color = colors[sequence] if combined else single_color
            name = f'{sequence} · {status.title()}' if combined else f'{status.title()} bone'
            fig.add_trace(go.Scatter3d(
                x=subset['x'], y=subset['y'], z=subset['z'], mode='markers',
                name=name, legendgroup=str(sequence) if combined else status,
                marker={'size': size, 'color': color, 'opacity': opacity},
                customdata=subset[['frame_label']] if 'frame_label' in subset else subset[['frame_index']],
                hovertemplate=name+'<br>frame=%{customdata[0]}<br>x=%{x:.2f}<br>y=%{y:.2f}<br>z=%{z:.2f}<extra></extra>',
            ))
