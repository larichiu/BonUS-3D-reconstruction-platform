"""Original image planes using the same pixel-to-tracker mapping as masks."""
import numpy as np
import plotly.graph_objects as go
from PIL import Image
from .geometry import rotation_from_wxyz, points_in_reference


def add_frame_plane(fig, row, settings, mirror_horizontal=False):
    with Image.open(row['frame_path']) as image:
        image = image.convert('L')
        if mirror_horizontal:
            image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        w,h = image.size
        # Sample real pixel coordinates, avoiding a second resize/crop convention.
        u=np.unique(np.linspace(0,w-1,min(w,120)).astype(int))
        v=np.unique(np.linspace(0,h-1,min(h,140)).astype(int))
        gray=np.asarray(image)[np.ix_(v,u)]
    uu,vv=np.meshgrid(u,v)
    def transform(u,v):
        local=np.zeros((len(u),3))
        local[:,0]=u*settings.spacing_x_mm*(-1 if settings.flip_horizontal else 1)
        local[:,2]=v*settings.spacing_y_mm*(-1 if settings.flip_depth else 1)
        local=settings.image_points(u,v)
        pp=row[[f'Prob_{i}' for i in range(1,4)]].to_numpy(dtype=float)
        pr=rotation_from_wxyz(row[[f'Prob_{i}' for i in range(4,8)]].to_numpy(dtype=float))
        rp=row[[f'Ref_{i}' for i in range(1,4)]].to_numpy(dtype=float) if settings.use_reference else np.zeros(3)
        rr=rotation_from_wxyz(row[[f'Ref_{i}' for i in range(4,8)]].to_numpy(dtype=float)) if settings.use_reference else np.eye(3)
        return points_in_reference(local,pp,pr,rp,rr)
    xyz=transform(uu.ravel(),vv.ravel()).reshape(*uu.shape,3)
    frame=int(row['FrameIndex'])
    frame_label=row.get('frame_label',f'frame {frame}')
    fig.add_trace(go.Surface(x=xyz[:,:,0],y=xyz[:,:,1],z=xyz[:,:,2],surfacecolor=gray,
        colorscale='Gray',cmin=0,cmax=255,showscale=False,opacity=.75,
        name=f'Ultrasound {frame_label}',hovertemplate=f'Original {frame_label}<extra></extra>',
        lighting=dict(ambient=1,diffuse=0,specular=0)))
    marks=transform(np.array([0,w-1,w/2]),np.array([0,0,h-1]))
    fig.add_trace(go.Scatter3d(x=marks[:,0],y=marks[:,1],z=marks[:,2],mode='markers+text',
        text=[f'{frame}: TIP / TOP-LEFT','IMAGE RIGHT','DEEP EDGE'],
        marker=dict(size=4,color='#57cfff'),textfont=dict(size=11),showlegend=False))
