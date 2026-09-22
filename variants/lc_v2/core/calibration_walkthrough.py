"""Inspect the existing calibration with actual frames and tracking samples."""
from dataclasses import replace
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from PIL import Image
from pathlib import Path
import streamlit as st
from .calibration_export import frame_transform, transform_pixels
from .frame_view import add_frame_plane
from .geometry import rotation_from_wxyz
from .navigation import render_navigable_scene
from .reconstruct import probe_pathway, load_binary_mask, upper_boundary


def render_calibration_walkthrough(data, settings):
    st.subheader('Ultrasound and mask · mirror comparison')
    if st.button('Reload original ultrasound and masks', key='cal_reload_original'):
        st.session_state.pop('loaded_path', None)
        st.session_state.pop('points', None)
        st.rerun()
    mirror_preview = st.toggle('Mirror ultrasound and mask left–right', value=True, key='cal_mirror_preview')
    st.caption('Preview only: reflect the image and mask about their vertical centreline. The calibrated tip, plane footprint, tracking poses, and trajectory stay fixed. Original files and reconstruction settings are unchanged.')
    rows = data.matches.loc[data.matches.has_frame & data.matches.has_pose].copy()
    if rows.empty:
        st.info('No ultrasound frames with tracking are available.')
        return
    if 'sequence' in rows:
        sequence = st.selectbox('Inspect sequence', sorted(rows.sequence.unique()), key='cal_sequence')
        rows = rows.loc[rows.sequence == sequence]
    rows = rows.sort_values('FrameIndex')
    frame_id = st.select_slider('Calibration frame', options=rows.FrameIndex.astype(int).tolist(),
                                key='cal_frame')
    row = rows.loc[rows.FrameIndex == frame_id].iloc[0]
    image_path = Path(row.get('source_frame_path', row['frame_path']))
    mask_path = row.get('source_mask_path', row.get('mask_path'))
    if '_for3Drecon' in image_path.stem or (bool(row.get('has_mask', False)) and '_for3Drecon' in Path(mask_path).stem):
        st.error('An original source file is required; a mirrored reconstruction copy was found.')
        return
    with Image.open(image_path) as original:
        original_image = original.convert('RGB')
    source_image = original_image.transpose(Image.Transpose.FLIP_LEFT_RIGHT) if mirror_preview else original_image
    orientation_label = 'Mirrored' if mirror_preview else 'Original'
    image_col, mask_col = st.columns(2)
    image_col.image(source_image, caption=orientation_label+' ultrasound', width='stretch')
    image_col.caption(str(image_path))
    if bool(row.get('has_mask', False)):
        with Image.open(mask_path) as original_mask:
            original_mask_copy = original_mask.copy()
        source_mask = original_mask_copy.transpose(Image.Transpose.FLIP_LEFT_RIGHT) if mirror_preview else original_mask_copy
        mask_col.image(source_mask, caption=orientation_label+' mask', width='stretch')
        mask_col.caption(str(mask_path))
        preview_mask = load_binary_mask(mask_path, settings.mask_threshold)
        if mirror_preview:
            preview_mask = preview_mask[:, ::-1]
        boundary = upper_boundary(preview_mask, 1)
        overlay = px.imshow(source_image)
        overlay.add_scatter(x=boundary[:,0],y=boundary[:,1],mode='lines',line=dict(color='#ff8c42',width=2),name=orientation_label+' upper boundary')
        overlay.update_layout(height=550,xaxis_title='Displayed column u (pixels)',yaxis_title='Displayed row v (pixels)',margin=dict(l=0,r=0,t=20,b=0))
        render_navigable_scene(overlay, 550, str(data.root), view_id='calibration-original', is_3d=False)
        st.caption('Orange is the matching mask boundary. Mirroring maps u to width − 1 − u; v stays unchanged. The calibration anchor remains at displayed pixel (0, 0), exactly as before.')
        if mirror_preview:
            with st.expander('Compare with the original ultrasound and mask'):
                before_columns = st.columns(2)
                before_columns[0].image(original_image, caption='Before · original ultrasound', width='stretch')
                before_columns[1].image(original_mask_copy, caption='Before · original mask', width='stretch')
    else:
        mask_col.info('No saved mask for this frame.')
    if not st.checkbox('Show calibrated 3D placement and path for comparison', value=False, key='cal_show_transformed'):
        st.info('Enable the 3D comparison below to see this image orientation on the same fixed calibration point and trajectory.')
        return
    st.subheader('After calibration · 3D placement and path')
    st.caption('Mirroring changes image content and mask locations inside the existing plane. The calibration transformation, tip position, and path are identical with the mirror toggle on or off.')
    space = st.radio('Inspect coordinates in', ['NDI tracker XYZ', 'Leg-reference XYZ'], horizontal=True, key='cal_space')
    inspection = replace(settings, use_reference=space.startswith('Leg'))
    width, height = data.frame_size
    c1, c2 = st.columns(2)
    pixel_u = c1.number_input('Pixel column u (from left)', min_value=0, max_value=width-1, value=(width-1)//2, key='cal_pixel_u')
    pixel_v = c2.number_input('Pixel row v (from top)', min_value=0, max_value=height-1, value=(height-1)//2, key='cal_pixel_v')
    try:
        transform, marker = frame_transform(row, inspection)
        pp = row[[f'Prob_{i}' for i in range(1,4)]].to_numpy(float)
        pr = rotation_from_wxyz(row[[f'Prob_{i}' for i in range(4,8)]].to_numpy(float))
        rr = rotation_from_wxyz(row[[f'Ref_{i}' for i in range(4,8)]].to_numpy(float)) if inspection.use_reference else np.eye(3)
        local = settings.image_points(np.array([pixel_u]), np.array([pixel_v]))[0]
        tracker_pixel = pp + pr @ local
        output_pixel = transform_pixels(np.array([[pixel_u,pixel_v]]), transform, inspection)[0]
        path = probe_pathway(data, inspection)
    except ValueError as exc:
        st.error(f'This tracking sample cannot be transformed: {exc}')
        return
    if 'sequence' in rows and 'sequence' in path:
        path = path.loc[path.sequence == sequence]
    path = path.sort_values('frame_index')
    fig = go.Figure()
    add_frame_plane(fig, row, inspection, mirror_horizontal=mirror_preview)
    if bool(row.get('has_mask', False)):
        mask_for_3d = load_binary_mask(mask_path, settings.mask_threshold)
        if mirror_preview:
            mask_for_3d = mask_for_3d[:, ::-1]
        boundary = upper_boundary(mask_for_3d, 2)
        xyz = transform_pixels(boundary, transform, inspection)
        fig.add_trace(go.Scatter3d(x=xyz[:,0],y=xyz[:,1],z=xyz[:,2],mode='lines',line=dict(color='#ff8c42',width=5),name='Annotated upper boundary'))
    fig.add_trace(go.Scatter3d(x=path.x,y=path.y,z=path.z,mode='lines',line=dict(color='#21a6a0',width=5),name='Calibrated tip path',customdata=path.frame_index,hovertemplate='Frame %{customdata}<br>(%{x:.3f}, %{y:.3f}, %{z:.3f}) mm<extra></extra>'))
    for point, label, color in [(transform[:3,3],'Calibrated tip / image top-left','#ff8c42'),(output_pixel,'Selected image pixel','#ec4899')]:
        fig.add_trace(go.Scatter3d(x=[point[0]],y=[point[1]],z=[point[2]],mode='markers',marker=dict(size=7,color=color),name=label))
    if st.checkbox('Show coordinate origin and XYZ axes', value=True, key='cal_origin'):
        for axis, color in enumerate(['#ef4444','#22c55e','#3b82f6']):
            endpoint = np.eye(3)[axis]*30
            fig.add_trace(go.Scatter3d(x=[0,endpoint[0]],y=[0,endpoint[1]],z=[0,endpoint[2]],mode='lines+text',text=['','XYZ'[axis]],line=dict(color=color,width=6),name=space+' · '+'XYZ'[axis]))
    fig.update_layout(height=650,scene=dict(aspectmode='data',xaxis_title='X (mm)',yaxis_title='Y (mm)',zaxis_title='Z (mm)'),margin=dict(l=0,r=0,t=10,b=0),uirevision='calibration-'+space)
    render_navigable_scene(fig, 650, str(data.root)+'-'+space, view_id='calibration-path')
    st.caption('Grey plane = actual ultrasound frame; orange curve = mask boundary. The teal path connects calibrated tip positions in frame order, within this sequence. Snap to trajectory start looks forward along the first part of the scan. Hide the origin to inspect the image more closely.')
    st.markdown('**1. Convert pixel distances into the probe-marker coordinate system**')
    st.latex(r'p_{probe}=c+(u\,s_u)b_u+(v\,s_v)b_v')
    st.write(f'Pixel spacing: {settings.spacing_x_mm:.5f} × {settings.spacing_y_mm:.5f} mm/pixel. Marker-to-tip offset c: {tuple(settings.tip_offset_mm)} mm.')
    st.caption(f'Image basis uses orientation {settings.orientation_deg} degrees, horizontal reversal={settings.flip_horizontal}, depth reversal={settings.flip_depth}. The tip offset calibrates position; it does not independently determine image orientation. The current mapping assumes cropped pixel (0, 0) lies at the tip.')
    st.markdown('**2. Apply the measured probe pose**')
    st.latex(r'p_{tracker}=t_{probe}+R_{probe}p_{probe}')
    st.caption('Prob_1…Prob_3 give translation in mm. Prob_4…Prob_7 give the quaternion in w, x, y, z order; it is normalized and converted to R_probe. The offset is rotated before it is added to the tracked position.')
    st.markdown('**3. Optionally express the result relative to the leg marker**')
    st.latex(r'p_{reference}=R_{reference}^{T}(p_{tracker}-t_{reference})')
    st.caption('This subtracts the reference marker position and applies its inverse rotation at the same frame. Tracker mode skips this step.')
    st.dataframe(pd.DataFrame([settings.tip_offset,local,pp,pp+pr@settings.tip_offset,tracker_pixel,output_pixel],index=['Calibration offset · probe axes','Selected pixel · probe axes','Tracked marker · tracker axes','Calibrated tip · tracker axes','Selected pixel · tracker axes','Selected pixel · displayed axes'],columns=['X (mm)','Y (mm)','Z (mm)']),width='stretch')
    st.markdown('**4. Repeat the calibrated tip calculation to form the path**')
    st.latex(r'tip_i=t_i+R_i c')
    st.caption('Every valid tracking sample contributes a tip position, including frames without a mask. Reference mode applies step 3 to each tip. Connecting samples shows motion; it does not infer a bone boundary.')
    st.dataframe(path.rename(columns={'x':'tip_x_mm','y':'tip_y_mm','z':'tip_z_mm'}),hide_index=True,width='stretch')
    with st.expander('Current 4 × 4 image-to-display transformation'):
        st.latex(r'[x,y,z,1]^T=T[u s_u,v s_v,0,1]^T')
        st.dataframe(pd.DataFrame(transform,index=['X','Y','Z','homogeneous'],columns=['image u','image v','normal','translation']),width='stretch')
        st.write('Measured probe quaternion (w, x, y, z)')
        st.dataframe(pd.DataFrame([row[[f'Prob_{i}' for i in range(4,8)]].to_numpy(float)],columns=['w','x','y','z']),hide_index=True)
        st.write('Probe rotation into tracker axes')
        st.dataframe(pd.DataFrame(pr,index=['tracker X','tracker Y','tracker Z'],columns=['probe X','probe Y','probe Z']))
        st.write('Image basis vectors in probe axes')
        st.dataframe(pd.DataFrame(settings.image_basis,index=['b_u · image right','b_v · image depth'],columns=['X','Y','Z']))
