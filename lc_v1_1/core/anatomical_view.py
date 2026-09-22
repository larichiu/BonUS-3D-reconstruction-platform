"""Scan-start camera from tracking and the user's right-tibia sequence labels."""
import numpy as np
from .calibration_export import frame_transform, transform_pixels
from .reconstruct import load_binary_mask, upper_boundary


def scan_start_view(data, settings):
    rows=data.matches.loc[data.matches.has_frame & data.matches.has_mask & data.matches.has_pose].copy()
    if 'sequence' not in rows:
        return None, 'Select right-side sequences 000 and 002 together to establish medial-to-lateral screen direction.'
    starts={}
    for name,group in rows.groupby('sequence',sort=True):
        if not str(name).startswith('right/'):
            continue
        sequence=str(name).split('/')[-1]
        row=group.sort_values('FrameIndex').iloc[0]
        matrix,_=frame_transform(row,settings)
        pixels=upper_boundary(load_binary_mask(row.mask_path,settings.mask_threshold),1)
        if len(pixels):
            starts[sequence]=transform_pixels(pixels,matrix,settings).mean(axis=0)
    if not {'sequence_000','sequence_002'}.issubset(starts):
        return None, 'Select right-side sequences 000 and 002 together to establish medial-to-lateral screen direction.'
    poses=data.poses.loc[data.poses['sequence']=='right/sequence_000'].sort_values('FrameIndex')
    tips=[]
    for _,row in poses.iterrows():
        try:
            matrix,_=frame_transform(row,settings)
            tips.append(matrix[:3,3])
        except ValueError:
            continue
    if len(tips)<2:
        return None,'Two valid probe poses are needed to determine the scan direction.'
    tips=np.asarray(tips)
    n=max(1,min(10,len(tips)//4))
    forward=tips[-n:].mean(axis=0)-tips[:n].mean(axis=0)
    if np.linalg.norm(forward)<1e-6:
        return None,'Probe motion is too small to determine the scan-start viewing direction.'
    forward/=np.linalg.norm(forward)
    right=starts['sequence_002']-starts['sequence_000']
    right-=np.dot(right,forward)*forward
    if np.linalg.norm(right)<1e-6:
        return None,'The medial and lateral starts overlap in this viewing plane; adjust calibration to distinguish them.'
    right/=np.linalg.norm(right)
    up=np.cross(right,forward)
    up/=np.linalg.norm(up)
    view={'eye':-2.5*forward,'up':up}
    note='Looking from the start along sequence_000 probe travel. Medial sequence_000 is screen-left; lateral sequence_002 is screen-right. Tracking coordinates are unchanged.'
    if 'sequence_001' in starts:
        position=float(np.dot(starts['sequence_001']-starts['sequence_000'],right))
        width=float(np.dot(starts['sequence_002']-starts['sequence_000'],right))
        if not 0<=position<=width:
            note+=' The apex start currently falls outside those two starts: this indicates a calibration/alignment mismatch, not an automatic anatomical correction.'
    return view,note


def plotly_camera(view, rotation=None, reverse=False):
    rotation=np.eye(3) if rotation is None else rotation
    eye=rotation@view['eye']*(-1 if reverse else 1)
    up=rotation@view['up']
    return dict(eye=dict(zip('xyz',eye)),up=dict(zip('xyz',up)),center=dict(x=0,y=0,z=0),projection=dict(type='orthographic'))
