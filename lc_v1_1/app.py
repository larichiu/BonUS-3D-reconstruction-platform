from __future__ import annotations

import io
import tempfile
from pathlib import Path

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from PIL import Image

from variants.lc_v1_1.core.calibration_export import v1_coordinate_export
from variants.lc_v1_1.core.sample_preview import sample_sequence_frames, sample_preview_figure
from variants.lc_v1_1.core.io import load_patient as load_original_patient, write_ply, platform_revision
from variants.lc_v1_1.core.collection import annotated_sequences, combine_data
from variants.lc_v1_1.core.mirror import mirror, anatomy_label
from variants.lc_v1_1.core.anatomical_view import scan_start_view, plotly_camera
from variants.lc_v1_1.core.bone_display import add_bone_traces, sequence_color
from variants.lc_v1_1.core.models import ReconstructionSettings
from variants.lc_v1_1.core.geometry import rotation_from_wxyz
from variants.lc_v1_1.core.view import horizontal_scan_camera
from variants.lc_v1_1.core.frame_view import add_frame_plane
from variants.lc_v1_1.core.navigation import render_navigable_scene
from variants.lc_v1_1.core.reconstruct import load_binary_mask, probe_marker_pose, probe_pathway, reconstruct, statistical_filter, upper_boundary


st.set_page_config(page_title="Bone Reconstruction_LCedit_v1.1", page_icon="🦴", layout="wide")
st.title("Bone Reconstruction_LCedit_v1.1")
st.caption("V1.1 · mirror ultrasound images and masks into separate _for3Drecon series. Built from V1.")

st.caption("Saved segmentation masks + synchronized NDI tracking → patient-relative 3D point cloud")

from bone_config import DATA_ROOT, DERIVED_ROOT
REDUCED_ROOT = Path(st.session_state.get("dataset_root", DATA_ROOT))
MIRROR_OUTPUT = Path(st.session_state.get("derived_root", DERIVED_ROOT))


def load_patient(folder):
    return mirror(load_original_patient(folder), MIRROR_OUTPUT)


def load_collection(folders, patient_folder):
    return combine_data([load_patient(folder) for folder in folders], patient_folder)



def child_folders(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted((path for path in folder.iterdir() if path.is_dir()), key=lambda path: path.name.lower())


def add_axis_triad(fig: go.Figure, origin, length: float, prefix: str) -> None:
    colors = ["#D62728", "#2CA02C", "#1F77B4"]
    labels = ["X", "Y", "Z"]
    for axis, (color, label) in enumerate(zip(colors, labels)):
        end = list(origin)
        end[axis] += length
        fig.add_trace(go.Scatter3d(
            x=[origin[0], end[0]], y=[origin[1], end[1]], z=[origin[2], end[2]],
            mode="lines+text", line={"color": color, "width": 6},
            text=["", f"{prefix} {label}"], textposition="top center",
            name=f"{prefix} {label} axis", showlegend=False, hoverinfo="skip",
        ))


def calibration_figure(settings: ReconstructionSettings, image_size: tuple[int, int]) -> go.Figure:
    tip = settings.tip_offset
    width_mm = (image_size[0] - 1) * settings.spacing_x_mm
    depth_mm = (image_size[1] - 1) * settings.spacing_y_mm
    horizontal_sign = -1.0 if settings.flip_horizontal else 1.0
    depth_sign = -1.0 if settings.flip_depth else 1.0
    left_x = tip[0]
    right_x = tip[0] + horizontal_sign * width_mm
    far_z = tip[2] + depth_sign * depth_mm

    fig = go.Figure()
    fig.add_trace(go.Scatter3d(
        x=[0, tip[0]], y=[0, tip[1]], z=[0, tip[2]], mode="lines",
        line={"color": "#7A5195", "width": 8}, name="Calibration offset",
        hovertemplate="Marker-to-tip calibration vector<extra></extra>",
    ))
    fig.add_trace(go.Scatter3d(
        x=[0], y=[0], z=[0], mode="markers+text", text=["PROBE TRACKER"],
        textposition="top center", marker={"size": 10, "color": "#333333", "symbol": "square"},
        name="Probe tracker marker",
    ))
    fig.add_trace(go.Scatter3d(
        x=[tip[0]], y=[tip[1]], z=[tip[2]], mode="markers+text", text=["PROBE TIP"],
        textposition="top center", marker={"size": 10, "color": "#FF7C43", "symbol": "diamond"},
        name="Ultrasound probe tip",
    ))
    corners=settings.image_points(np.array([0,image_size[0]-1,image_size[0]-1,0]),np.array([0,0,image_size[1]-1,image_size[1]-1]))
    fig.add_trace(go.Mesh3d(
        x=corners[:,0], y=corners[:,1], z=corners[:,2],
        i=[0, 0], j=[1, 2], k=[2, 3],
        color="#4C78A8", opacity=0.28, name="Ultrasound image plane",
        hovertemplate="Ultrasound image plane<extra></extra>",
    ))
    fig.add_trace(go.Scatter3d(
        x=corners[[0,1,2,3,0],0],
        y=corners[[0,1,2,3,0],1],
        z=corners[[0,1,2,3,0],2],
        mode="lines", line={"color": "#4C78A8", "width": 5},
        name="Image boundary", hoverinfo="skip",
    ))
    add_axis_triad(fig, [0.0, 0.0, 0.0], max(30.0, min(60.0, float(abs(tip).max()) / 3.0)), "Probe")
    fig.update_layout(
        height=620, scene_aspectmode="data", margin=dict(l=0, r=0, t=35, b=0),
        title="Probe-marker to ultrasound-image calibration",
        scene={"xaxis_title": "Probe X (mm)", "yaxis_title": "Probe Y (mm)", "zaxis_title": "Probe Z (mm)"},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.01, "x": 0},
    )
    return fig


def add_ndi_camera(fig: go.Figure, position, rotation, settings: ReconstructionSettings) -> None:
    """Schematic tracker-origin symbol, not calibrated camera housing geometry."""
    scale = 38.0
    local = pd.DataFrame([
        [0, 0, 0], [-0.55 * scale, -0.38 * scale, scale],
        [0.55 * scale, -0.38 * scale, scale], [0.55 * scale, 0.38 * scale, scale],
        [-0.55 * scale, 0.38 * scale, scale],
    ], columns=["x", "y", "z"]).to_numpy()
    world = position[None, :] + local @ rotation.T
    apex, c1, c2, c3, c4 = world
    line_indices = [0, 1, 2, 3, 4, 1, 0, 2, 0, 3, 0, 4]
    wire = world[line_indices]
    fig.add_trace(go.Scatter3d(
        x=wire[:, 0], y=wire[:, 1], z=wire[:, 2], mode="lines",
        line={"color": "#00A6A6", "width": 7}, name="NDI tracker origin (schematic)",
        hoverinfo="skip",
    ))
    fig.add_trace(go.Mesh3d(
        x=world[:, 0], y=world[:, 1], z=world[:, 2],
        i=[0, 0, 0, 0], j=[1, 2, 3, 4], k=[2, 3, 4, 1],
        color="#00A6A6", opacity=0.18, name="Schematic camera — not measured field of view", hoverinfo="skip",
    ))


def add_probe_marker(fig, position, rotation, settings):
    tip = position + rotation @ settings.tip_offset
    fig.add_trace(go.Scatter3d(
        x=[position[0], tip[0]], y=[position[1], tip[1]], z=[position[2], tip[2]],
        mode="lines", line={"color": "#7A5195", "width": 8},
        name="Marker-to-tip offset",
        hoverinfo="skip",
    ))
    for point, label, color, symbol in [
        (position, 'PROBE TRACKED POSITION · before calibration', '#00A6A6', 'square'),
        (tip, 'PROBE TIP · after calibration', '#FF7C43', 'diamond'),
    ]:
        fig.add_trace(go.Scatter3d(
            x=[point[0]], y=[point[1]], z=[point[2]], mode='markers+text',
            marker=dict(size=12, color=color, symbol=symbol, line=dict(color='white', width=2)),
            text=[label], textposition='top center', textfont=dict(size=15, color=color),
            name=label, hovertemplate=label+'<br>x=%{x:.2f} mm<br>y=%{y:.2f} mm<br>z=%{z:.2f} mm<extra></extra>',
        ))
    axis_length = 32.0
    axis_colors = ["#D62728", "#2CA02C", "#1F77B4"]
    for direction,label,color in zip(settings.image_basis,['IMAGE RIGHT · u','IMAGE DEPTH · v'],['#65baff','#56e0b1']):
        end=tip+rotation@direction*32
        fig.add_trace(go.Scatter3d(x=[tip[0],end[0]],y=[tip[1],end[1]],z=[tip[2],end[2]],mode='lines+markers+text',text=['',label],line=dict(color=color,width=9),marker=dict(size=4),name=label))
    axis_labels = ["MARKER X", "MARKER Y", "MARKER Z"]
    for axis, (color, label) in enumerate(zip(axis_colors, axis_labels)):
        end = position + rotation[:, axis] * axis_length
        fig.add_trace(go.Scatter3d(
            x=[position[0], end[0]], y=[position[1], end[1]], z=[position[2], end[2]],
            mode="lines+text", line={"color": color, "width": 7},
            text=["", label], textposition="top center", showlegend=False, hoverinfo="skip",
        ))

with st.sidebar:
    st.header("Patient data")
    patients = child_folders(REDUCED_ROOT)
    if not patients:
        st.error(f"No datasets were found in {REDUCED_ROOT}")
        st.stop()
    patient_names = [path.name for path in patients]
    default_patient = next((patient_names.index(name) for name in ("sawbone", "sawbone_001", "057") if name in patient_names), 0)
    patient_name = st.selectbox("Patient", patient_names, index=default_patient, key="variantwidget_lc_v1_1_183")
    patient_folder = REDUCED_ROOT / patient_name
    combine_sequences = st.checkbox('Combine patient sequences with masks', value=False, key="variantwidget_lc_v1_1_185")
    selected_collection = []
    alignment_confirmed = True
    if combine_sequences:
        candidates = annotated_sequences(patient_folder)
        options = [entry['label'] for entry in candidates]
        st.caption('Use the Selected column in the sequence table to include or exclude scans.')
        st.caption('Sequences with saved masks are listed. Uploaded masks have no annotation acceptance audit. Left and right sides are labeled separately.')
        alignment_confirmed = st.checkbox('Same fixed reference marker and calibration across these scans', value=False,
            key='alignment_'+patient_name+'|'.join(options),
            help='The marker must not have been detached or moved relative to the scanned bone. Combining does not perform automatic registration.')

    sides = child_folders(patient_folder)
    if not sides:
        st.error("This patient has no leg/side folders.")
        st.stop()
    side_names = [path.name for path in sides]
    side_name = st.selectbox("Leg / side", side_names, index=side_names.index("right") if "right" in side_names else 0, disabled=combine_sequences, key="variantwidget_lc_v1_1_202")
    side_folder = patient_folder / side_name

    sequences = [path for path in child_folders(side_folder) if path.name.lower().startswith("sequence_")]
    if not sequences:
        st.error("This leg/side has no sequence folders.")
        st.stop()
    sequence_name = st.selectbox("Sequence", [path.name for path in sequences], disabled=combine_sequences, key="variantwidget_lc_v1_1_209")
    selected_folder = side_folder / sequence_name
    has_tracking = any(not path.name.startswith("~$") for path in selected_folder.rglob('*.xlsx'))
    st.caption("Tracking workbook found" if has_tracking else "Tracking workbook missing")
    reload_clicked = st.button("Reload selected sequence", width="stretch", key="variantwidget_lc_v1_1_213")
    mirror_clicked = st.button('mirror', width='stretch', help='Create or refresh left-to-right mirrored image AND mask copies. Original files remain unchanged.', key="variantwidget_lc_v1_1_214")
    st.caption('mirror saves new _for3Drecon image/mask series and uses those copies for 3D reconstruction.')

if combine_sequences:
    st.subheader('Sequences')
    previous_selection = st.session_state.setdefault(
        'sequence_selection_defaults_'+patient_name,
        st.session_state.get('collection_'+patient_name, options),
    )
    import hashlib
    chosen = []
    headings = st.columns([3, 2, 1, 1, 1])
    for column, title in zip(headings, ['Sequence', 'Anatomical position', 'Selected', 'Accepted masks', 'Propagated masks']):
        column.markdown('**'+title+'**')
    for entry in candidates:
        label = entry['label']
        color = sequence_color(label)
        widget_key = 'sequence_pick_' + hashlib.sha256((patient_name+'|'+label).encode()).hexdigest()[:16]
        st.html(f"""<style>
        .st-key-{widget_key} label[data-rac] > div:first-of-type {{
            background-color: transparent !important; border-color: {color} !important;
        }}
        .st-key-{widget_key} label[data-rac] svg polyline {{stroke: {color} !important;}}
        </style>""")
        columns = st.columns([3, 2, 1, 1, 1], vertical_alignment='center')
        columns[0].markdown(label)
        columns[1].write(anatomy_label(entry['side'], entry['name']))
        if columns[2].checkbox('Selected · '+label, value=label in previous_selection, key=widget_key, label_visibility='collapsed'):
            chosen.append(label)
        columns[3].write(entry['accepted'])
        columns[4].write(entry['propagated'])
    st.session_state['sequence_selection_defaults_'+patient_name] = chosen
    selected_collection = [entry['folder'] for entry in candidates if entry['label'] in chosen]
    st.caption(f'{len(chosen)} of {len(options)} sequences selected. Changes update the reconstruction automatically.')
    if not selected_collection:
        for state_key in ('patient', 'loaded_path', 'points'):
            st.session_state.pop(state_key, None)
        st.info('Select at least one sequence to display its reconstruction.' if options else 'No sequences with saved masks are available for this patient.')
        st.stop()

selected_key = '|'.join(str(p.resolve()) for p in selected_collection) if combine_sequences else str(selected_folder.resolve())
selected_key = ('combined:' if combine_sequences else 'single:') + selected_key
revision = platform_revision()
if reload_clicked or mirror_clicked or st.session_state.get("loaded_path") != selected_key or st.session_state.get('platform_revision') != revision:
    try:
        st.session_state.patient = load_collection(selected_collection, patient_folder) if combine_sequences else load_patient(selected_folder)
        st.session_state.loaded_path = selected_key
        st.session_state.platform_revision = revision
        st.session_state.pop("points", None)
    except Exception as exc:
        st.session_state.pop("patient", None)
        st.session_state.pop("loaded_path", None)
        st.error(str(exc))

data = st.session_state.get("patient")
if data is None:
    st.info("Choose a patient, leg/side, and sequence. The selected sequence loads automatically.")
    st.stop()

st.info('mirror applied to both ultrasound images and masks: u_new = width − 1 − u_original. New _for3Drecon files are saved separately. The probe tracking, tip offset, and existing image-axis signs are unchanged.')
st.caption('Right tibia, looking from scan start down the probe path: sequence_000 = medial / left; sequence_001 = apex / middle; sequence_002 = lateral / right. These labels define the viewing convention; alignment still uses tracking and calibration.')
matches = data.matches
frame_labels = matches.set_index('FrameIndex')['frame_label'].to_dict() if combine_sequences else {}
pose_labels = data.poses.set_index('FrameIndex')['frame_label'].to_dict() if combine_sequences else {}
matched = matches["has_mask"] & matches["has_pose"]
cols = st.columns(5)
cols[0].metric("Reduced frames", f"{len(matches):,}")
cols[1].metric("Available masks", f"{matches['has_mask'].sum():,}")
cols[2].metric("Pose rows", f"{matches['has_pose'].sum():,}")
cols[3].metric("Ready frames", f"{matched.sum():,}")
cols[4].metric("Image size", f"{data.frame_size[0]} × {data.frame_size[1]}")
if combine_sequences:
    st.warning('Combined scans share leg-reference coordinates. If the marker was repositioned, or separate legs moved relative to it, the scans will not align correctly. No automatic alignment is applied.')
    if not alignment_confirmed:
        st.info('Confirm the shared reference and calibration in the sidebar to display the combined reconstruction.')
        st.stop()
if matches["has_mask"].any():
    st.success(f"Labels matched automatically — {data.label_source}")
else:
    st.info(f"Tracking loaded. No eligible saved annotation masks are available yet for {data.label_source}.")

if not matched.any():
    st.warning("Bone reconstruction needs saved accepted or propagated masks. The probe pathway can still be viewed from tracking data.")

tab_preview, tab_geometry, tab_reconstruct = st.tabs(["Data review", "Geometry", "Reconstruction"])

with tab_preview:
    st.subheader('Mirrored image and mask · _for3Drecon')
    ready_indices = matches.loc[matched, "FrameIndex"].astype(int).tolist()
    if ready_indices:
        selected = st.select_slider("Preview matched frame", options=ready_indices, format_func=lambda i: frame_labels.get(i,str(i)), key="variantwidget_lc_v1_1_304")
        row = matches[matches["FrameIndex"] == selected].iloc[0]
        frame = Image.open(row["frame_path"]).convert("RGB")
        mask = load_binary_mask(row["mask_path"])
        overlay = pd.DataFrame(upper_boundary(mask, max(1, mask.shape[1] // 100)), columns=["u", "v"])
        fig = px.imshow(frame)
        if not overlay.empty:
            fig.add_scatter(x=overlay["u"], y=overlay["v"], mode="markers", marker={"size": 4, "color": "#ff8c42"}, name="Upper boundary")
        fig.update_layout(height=620, margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig, width="stretch")
        st.caption(f"Mirrored image: {row['frame_path'].name} · mirrored mask: {row['mask_path'].name}")
        with st.expander('Compare with original image and mask'):
            original_frame = Image.open(row['source_frame_path']).convert('RGB')
            original_mask = load_binary_mask(row['source_mask_path'])
            original_boundary = upper_boundary(original_mask, max(1, original_mask.shape[1] // 100))
            original_fig = px.imshow(original_frame)
            original_fig.add_scatter(x=original_boundary[:,0], y=original_boundary[:,1], mode='markers', marker=dict(size=4,color='#ff8c42'), name='Original mask')
            original_fig.update_layout(height=500, margin=dict(l=0,r=0,t=10,b=0))
            st.plotly_chart(original_fig, width='stretch')
    review_table = matches[["FrameIndex", "has_mask", "has_pose", "frame_path", "mask_path"]].copy()
    review_table["frame_path"] = review_table["frame_path"].map(str)
    review_table["mask_path"] = review_table["mask_path"].map(lambda value: "" if pd.isna(value) else str(value))
    st.dataframe(review_table, width="stretch", hide_index=True)

with tab_geometry:
    with st.expander('Image spacing, probe offset, and baseline directions', expanded=False):
        st.subheader("Image and tracking geometry")
        c1, c2 = st.columns(2)
        with c1:
            spacing_x = st.number_input("Horizontal spacing (mm/pixel)", min_value=0.0001, value=0.05392, format="%.5f", key="variantwidget_lc_v1_1_333")
            spacing_y = st.number_input("Depth spacing (mm/pixel)", min_value=0.0001, value=0.05392, format="%.5f", key="variantwidget_lc_v1_1_334")
            sample_step = st.number_input("Boundary sample step (pixels)", min_value=1, value=2, step=1, key="variantwidget_lc_v1_1_335")
            frame_step = st.number_input("Use every Nth matched frame", min_value=1, value=1, step=1, key="variantwidget_lc_v1_1_336")
        with c2:
            st.caption("Probe marker → ultrasound tip offset (mm)")
            ox = st.number_input("Offset X", value=-163.326, key="variantwidget_lc_v1_1_339")
            oy = st.number_input("Offset Y", value=-19.6482, key="variantwidget_lc_v1_1_340")
            oz = st.number_input("Offset Z", value=-206.473, key="variantwidget_lc_v1_1_341")
            use_ref = st.checkbox("Reconstruct relative to the leg reference marker", value=True, disabled=combine_sequences, key='use_reference_combined' if combine_sequences else 'use_reference_single')
            if combine_sequences:
                use_ref = True
            flip_h = st.checkbox("Reverse image horizontal direction", value=True, key="reverse_image_horizontal_v3")
            flip_d = st.checkbox(
                "Reverse image depth direction (vertical flip)",
                value=True,
                key="reverse_image_depth_v3",
                help=(
                    "Reverses image and mask depth together during 3D mapping. On by default: "
                    "increasing image Y maps to negative probe-local Z. "
                    "The annotation files on disk are not modified."
                ),
            )
    st.subheader('Image-plane rotation')
    st.caption('Rotate the annotated image about the calibrated tip. u is the baseline lateral/image-right axis; v is the baseline longitudinal/image-depth axis. Positive angles follow the right-hand rule. Applied order: u, then v about the fixed baseline axes.')
    if st.button('Reset u and v to original orientation', key="variantwidget_lc_v1_1_358"):
        st.session_state['rotation_u_deg'] = 0.0
        st.session_state['rotation_v_deg'] = 0.0
    angle_columns = st.columns(2)
    rotation_u = angle_columns[0].slider('Rotation about u · lateral (degrees)', -180.0, 180.0, 0.0, 0.5, key='rotation_u_deg')
    rotation_v = angle_columns[1].slider('Rotation about v · longitudinal (degrees)', -180.0, 180.0, 0.0, 0.5, key='rotation_v_deg')
    st.caption('0° / 0° preserves the selected baseline orientation (development default: X=45°, Y=−90°, Z=0°). The probe marker, tip offset, and tracked pathway stay fixed while the image plane rotates. These are manual calibration adjustments.')
    physical_w = data.frame_size[0] * spacing_x
    physical_d = data.frame_size[1] * spacing_y
    depth_direction = "−Z (Unity vertical flip)" if flip_d else "+Z"
    st.info(
        f"Current cropped image footprint: **{physical_w:.2f} mm wide × {physical_d:.2f} mm deep**. "
        f"Baseline assumes the cropped top-left is at the calibrated tip and depth follows **{depth_direction}** before any experimental rotation."
    )

settings = ReconstructionSettings(
    spacing_x_mm=spacing_x,
    spacing_y_mm=spacing_y,
    tip_offset_mm=(ox, oy, oz),
    sample_step_px=int(sample_step),
    frame_step=int(frame_step),
    flip_horizontal=flip_h,
    flip_depth=flip_d,
    use_reference=use_ref,
    rotation_u_deg=rotation_u,
    rotation_v_deg=rotation_v,
    orientation_deg=tuple(st.session_state.get("baseline_angles", (45.,-90.,0.))),  # User-selected provisional mapping, not measured calibration.
)

with tab_geometry:
    st.subheader('Sample frames from each selected sequence')
    preview_columns = st.columns(2)
    frames_per_sequence = preview_columns[0].slider('Sample frames per sequence', 1, 5, 3, key='sample_frames_per_sequence')
    show_original_outline = preview_columns[1].checkbox('Show original plane outlines for comparison', value=True, key="variantwidget_lc_v1_1_391")
    samples = sample_sequence_frames(matches, frames_per_sequence)
    if samples:
        sample_fig = sample_preview_figure(samples, settings, data.frame_size, show_original_outline)
        sample_fig.update_layout(uirevision=selected_key+'-sample-preview', scene_uirevision=selected_key+'-sample-preview')
        anatomical_preview = st.checkbox('View from scan start · medial left, lateral right', value=True, key='anatomical_preview')
        if anatomical_preview:
            preview_view, preview_note = scan_start_view(data, settings)
            if preview_view is not None:
                sample_fig.update_layout(scene_camera=plotly_camera(preview_view))
            st.caption(preview_note)
        st.plotly_chart(sample_fig, width='stretch', key='sample_sequence_preview')
        st.caption(f'{len(samples)} mirrored image planes, sampled evenly within each selected sequence. Colored boundaries are the saved masks; blue u and green v arrows show the rotated image directions. Orange diamonds are the fixed tip pivots. Dashed outlines retain the original orientation. Coordinates use '+('leg-reference axes.' if settings.use_reference else 'NDI tracker axes.'))
        st.caption('Adjust the u/v sliders above to rotate these planes and masks together. The controls act around the baseline image axes; the preview keeps your camera angle as you adjust them.')
        with st.expander('Frames shown in this preview'):
            st.dataframe(pd.DataFrame([{'Sequence': label, 'Frame': row.get('frame_label', int(row['FrameIndex'])), 'Image': row['frame_path'].name} for label, row in samples]), hide_index=True, width='stretch')
    else:
        st.info('No frames with saved masks and synchronized tracking are available for preview.')
    st.subheader("Calibration visualization")
    st.plotly_chart(calibration_figure(settings, data.frame_size), width="stretch")
    st.caption(
        "The dark square is the probe's tracked marker origin. The purple vector is the calibration offset. "
        "Its endpoint is the ultrasound probe tip, where the blue image plane begins."
    )

with tab_reconstruct:
    display_mode = st.segmented_control(
        "Visualization",
        ["Bone reconstruction", "Probe pathway", "Both"],
        default="Both",
        help="The pathway is the calibrated probe-tip trajectory from every valid tracking sample, independent of segmentation masks.",
     key="variantwidget_lc_v1_1_417") or "Both"
    show_bone = display_mode in {"Bone reconstruction", "Both"}
    show_pathway = display_mode in {"Probe pathway", "Both"}
    view_axes = st.radio('Display coordinate axes', ['NDI axes · stabilized at scan start', 'Leg-reference axes'], horizontal=True, key="variantwidget_lc_v1_1_425")
    anatomical_view = st.checkbox('View from scan start · medial left, apex middle, lateral right', value=True, key="variantwidget_lc_v1_1_426")
    horizontal_view = st.checkbox('Default view · probe left, reference marker right', value=False, key="variantwidget_lc_v1_1_427")
    reverse_view = st.checkbox('View from opposite side (camera only)', value=False, key="variantwidget_lc_v1_1_428")
    view_height = st.slider('3D view height', 600, 1400, 1000, 100, key="variantwidget_lc_v1_1_429")
    frame_density = st.session_state.get('bone_frame_density', 100)
    show_scene_labels = st.checkbox('Show text labels in 3D', value=False,
        help='Off keeps the view uncluttered. Hover over markers to identify them.', key="variantwidget_lc_v1_1_431")
    visibility = st.columns(2)
    show_accepted = visibility[0].checkbox('Accepted bone · solid sequence colour' if combine_sequences else 'Accepted bone · solid green', value=True, key="variantwidget_lc_v1_1_434")
    show_propagated = visibility[1].checkbox('Propagated bone · 5% opacity' if combine_sequences else 'Propagated bone · transparent orange', value=True, key="variantwidget_lc_v1_1_435")
    st.caption(('Each sequence has its own colour. Accepted points are solid; propagated points use the same colour at 5% opacity. Opacity indicates review status, not model confidence. ' if combine_sequences else 'Green = reviewed/accepted. Orange = unreviewed prediction, not a confidence estimate. ') + 'Save annotations in the web platform before loading them here.')
    pose_columns = [
        "Prob_1", "Prob_2", "Prob_3", "Prob_4", "Prob_5", "Prob_6", "Prob_7",
        "Ref_1", "Ref_2", "Ref_3", "Ref_4", "Ref_5", "Ref_6", "Ref_7",
    ]
    valid_pose_indices = data.poses.dropna(subset=pose_columns)["FrameIndex"].astype(int).tolist()
    show_camera = st.checkbox(
        "Show probe marker and tip", value=True,
        help="Shows the tracked probe-marker position and quaternion orientation at one selected sample.",
     key="variantwidget_lc_v1_1_442")
    camera_frame = None
    if show_camera and valid_pose_indices:
        camera_frame = st.select_slider(
            "Probe tracking sample", options=valid_pose_indices, value=valid_pose_indices[0], format_func=lambda i: pose_labels.get(i,str(i)),
            help="Move this control through the scan to see the probe marker and local image-depth direction.",
         key="variantwidget_lc_v1_1_448")

    if matched.any():
        minimum = int(matches.loc[matched, "FrameIndex"].min())
        maximum = int(matches.loc[matched, "FrameIndex"].max())
        frame_range = st.slider("Frame range", minimum, maximum, (minimum, maximum), key="variantwidget_lc_v1_1_456")
        if combine_sequences:
            st.caption('The range uses unique combined frame IDs. Preview labels, point hover text and CSV exports retain each source sequence and original tracking frame number.')
    else:
        frame_range = (0, 0)
    outlier_limit = st.slider("Robust outlier limit", 0.0, 10.0, 4.0, 0.5, help="0 disables filtering; lower values remove more distant points.", key="variantwidget_lc_v1_1_461")
    mapping_key = ('top-left-v1', repr(settings))
    refresh_orientation = st.session_state.get('point_mapping_key') != mapping_key and st.session_state.get('points') is not None
    if st.session_state.get('point_mapping_key') != mapping_key:
        st.session_state.pop('points', None)
    st.caption('Assumed image origin: top-left pixel (0, 0) = calibrated tip. Image directions follow the configured u/v basis. Exports reflect the current orientation candidate; reset before exporting the original mapping.')
    if st.button("Create bone reconstruction", type="primary", disabled=not matched.any(), key="variantwidget_lc_v1_1_467") or ((refresh_orientation or st.session_state.get('points') is None) and matched.any()):
        bar = st.progress(0.0, text="Preparing reconstruction")
        def report(done, total):
            bar.progress(done / max(total, 1), text=f"Transforming frame {done:,} of {total:,}")
        try:
            raw = reconstruct(data, settings, frame_range[0], frame_range[1], report)
            st.session_state.points = statistical_filter(raw, outlier_limit)
            st.session_state.point_mapping_key = mapping_key
            st.session_state.raw_count = len(raw)
            bar.progress(1.0, text="Reconstruction complete")
        except Exception as exc:
            st.error(f"Reconstruction failed: {exc}")

    points = st.session_state.get("points") if show_bone else None
    full_points = points
    pathway = probe_pathway(data, settings) if show_pathway else None
    inspect_frames = st.checkbox('Inspect orientation · show a few original frames in 3D', value=False, key="variantwidget_lc_v1_1_483")
    inspection_rows = matches.iloc[0:0]
    if inspect_frames:
        eligible = matches.loc[matches['has_frame'] & matches['has_mask'] & matches['has_pose']]
        choices = eligible['FrameIndex'].astype(int).tolist()
        image_count = st.slider('Number of original image planes', 1, max(2, min(20, len(choices))), min(3, max(2, len(choices))),
            help='Samples evenly across the sequence, rather than removing frames from the end.', key="variantwidget_lc_v1_1_488")
        selected = [choices[i] for i in np.unique(np.linspace(0,len(choices)-1,min(image_count,len(choices))).astype(int))] if choices else []
        st.caption(f'{len(selected)} evenly spaced image planes selected. Fewer planes make overlapping anatomy easier to inspect.')
        inspection_rows = eligible.loc[eligible['FrameIndex'].isin(selected)]
        st.caption('Image planes use the same calibration as the masks. Left/right/deep labels refer to the original image, not anatomy. This checks overlay consistency; a known physical landmark is still needed to establish correct orientation.')
        if points is not None:
            points = points.loc[points['frame_index'].isin(selected)]

    if points is not None and not points.empty and not inspect_frames:
        frame_ids = np.sort(points['frame_index'].unique())
        count = min(len(frame_ids), max(2, int(np.ceil(len(frame_ids) * frame_density / 100))))
        visible_ids = frame_ids[np.linspace(0, len(frame_ids)-1, count).round().astype(int)]
        points = points.loc[points['frame_index'].isin(visible_ids)]
        st.caption(f'Showing {count} of {len(frame_ids)} reconstructed frames, evenly spaced across the scan. Full-resolution exports are unchanged.')

    if show_bone and points is None:
        st.info("Choose **Create bone reconstruction** to generate the segmented bone points.")
    if points is not None and points.empty:
        st.warning("The selected masks produced no boundary points.")

    has_bone_points = points is not None and not points.empty
    has_path_points = pathway is not None and not pathway.empty
    if has_bone_points or has_path_points or not inspection_rows.empty:
        metrics = st.columns(4)
        if has_bone_points:
            metrics[0].metric("Bone points", f"{len(points):,}")
            metrics[1].metric("Bone frames", f"{points['frame_index'].nunique():,}")
            metrics[2].metric("Removed outliers", f"{st.session_state.get('raw_count', len(full_points)) - len(full_points):,}")
        if has_path_points:
            metrics[3].metric("Pathway samples", f"{len(pathway):,}")

        fig = go.Figure()
        for _, inspection_row in inspection_rows.iterrows():
            add_frame_plane(fig, inspection_row, settings)
        if has_bone_points:
            add_bone_traces(fig, points, matches, combine_sequences, show_accepted, show_propagated)
        if has_path_points:
            pathway_groups = pathway.groupby("sequence", sort=False) if "sequence" in pathway else [("Selected sequence", pathway)]
            for group_index, (sequence_label, segment) in enumerate(pathway_groups):
                segment = segment.copy()
                segment["sample_order"] = np.arange(len(segment))
                progress_colors = [[0.0, "#FFD9D2"], [0.35, "#FF8C7A"], [0.7, "#D43D2B"], [1.0, "#6E0D05"]]
                fig.add_trace(go.Scatter3d(
                    x=segment["x"], y=segment["y"], z=segment["z"],
                    mode="lines+markers", name=f"Probe-tip pathway · {sequence_label}",
                    line={
                        "color": segment["sample_order"], "colorscale": progress_colors,
                        "cmin": 0, "cmax": max(len(segment) - 1, 1), "width": 7,
                    },
                    marker={
                        "color": segment["sample_order"], "colorscale": progress_colors,
                        "cmin": 0, "cmax": max(len(segment) - 1, 1), "size": 3,
                        "showscale": group_index == 0,
                        "colorbar": {"title": "Scan progress", "tickvals": [0, max(len(segment) - 1, 1)], "ticktext": ["Start", "End"]},
                    },
                    customdata=segment[["frame_label"]] if "frame_label" in segment else segment[["frame_index"]],
                    hovertemplate="Probe tip<br>x=%{x:.2f}<br>y=%{y:.2f}<br>z=%{z:.2f}<br>frame=%{customdata[0]}<extra></extra>",
                ))
                endpoints = segment.iloc[[0, -1]]
                fig.add_trace(go.Scatter3d(
                    x=endpoints["x"], y=endpoints["y"], z=endpoints["z"],
                    mode="markers+text", name=f"Pathway direction · {sequence_label}",
                    marker={
                        "size": [9, 11], "color": ["#FFD9D2", "#6E0D05"],
                        "symbol": ["circle", "diamond"],
                        "line": {"color": "#3A0905", "width": 2},
                    },
                    text=["START", "END"], textposition="top center",
                    textfont={"color": "#6E0D05", "size": 13},
                    hovertemplate=[
                        f"START<br>frame={int(endpoints.iloc[0]['frame_index'])}<extra></extra>",
                        f"END<br>frame={int(endpoints.iloc[1]['frame_index'])}<extra></extra>",
                    ],
                ))
        if settings.use_reference:
            fig.add_trace(go.Scatter3d(
                x=[0], y=[0], z=[0], mode="markers+text",
                marker={"size": 12, "color": "#111111", "symbol": "square",
                        "line": {"color": "#F2F2F2", "width": 2}},
                text=["LEG REFERENCE"], textposition="bottom center",
                name="Leg reference marker",
                hovertemplate="Leg reference marker<br>x=%{x:.2f}<br>y=%{y:.2f}<br>z=%{z:.2f}<extra></extra>",
            ))
            add_axis_triad(fig, [0.0, 0.0, 0.0], 35.0, "Reference")
        if show_camera and camera_frame is not None:
            camera_position, camera_rotation = probe_marker_pose(
                data, camera_frame, settings.use_reference
            )
            add_probe_marker(fig, camera_position, camera_rotation, settings)
        axis_prefix = 'Reference' if settings.use_reference else 'NDI'
        view_rotation = np.eye(3)
        if settings.use_reference and view_axes.startswith('NDI'):
            anchor = None
            for _, candidate in data.poses.iterrows():
                values = candidate[[f'Ref_{i}' for i in range(1,8)]].to_numpy(dtype=float)
                if np.isfinite(values).all() and np.linalg.norm(values[3:]) > 1e-12:
                    anchor = candidate
                    break
            if anchor is None:
                st.error('No valid reference pose is available for the NDI-oriented display.')
            else:
                rotation = rotation_from_wxyz(anchor[[f'Ref_{i}' for i in range(4,8)]].to_numpy(dtype=float))
                origin = anchor[[f'Ref_{i}' for i in range(1,4)]].to_numpy(dtype=float)
                # One rigid transform for ALL geometry: retain leg stabilization.
                for trace in fig.data:
                    if trace.x is None or trace.y is None or trace.z is None:
                        continue
                    xyz = np.stack((trace.x,trace.y,trace.z),axis=-1).astype(float)
                    transformed = xyz @ rotation.T + origin
                    trace.x, trace.y, trace.z = transformed[...,0], transformed[...,1], transformed[...,2]
                axis_prefix = 'NDI'
                view_rotation = rotation
                st.caption(f"Leg motion compensation stays ON. Display anchored to the first valid reference pose (tracking frame {int(anchor['FrameIndex'])}). This rotates/translates the entire scene; it does not mirror it.")
        if st.checkbox('Show NDI tracker camera origin', value=True, key="variantwidget_lc_v1_1_602"):
            tracker_position, tracker_rotation = np.zeros(3), np.eye(3)
            can_show_tracker = True
            if axis_prefix == 'Reference':
                can_show_tracker = False
                for _, candidate in data.poses.iterrows():
                    values = candidate[[f'Ref_{i}' for i in range(1,8)]].to_numpy(dtype=float)
                    if np.isfinite(values).all() and np.linalg.norm(values[3:]) > 1e-12:
                        tracker_rotation = rotation_from_wxyz(values[3:]).T
                        tracker_position = -tracker_rotation @ values[:3]
                        can_show_tracker = True
                        break
            if can_show_tracker:
                add_ndi_camera(fig, tracker_position, tracker_rotation, settings)
            st.caption('Camera symbol marks NDI coordinate origin, assuming the Excel poses are tracker-relative. Its shape/direction are schematic. In stabilized views it represents the scan-start tracker pose, not motion through the scan.')
        fig.update_layout(
            height=view_height, scene_aspectmode="data", margin=dict(l=0, r=0, t=20, b=0),
            legend={"orientation": "h", "yanchor": "top", "y": -0.08, "x": 0, "font": {"size": 11}},
            scene={"xaxis_title": f"{axis_prefix} X (mm)", "yaxis_title": f"{axis_prefix} Y (mm)", "zaxis_title": f"{axis_prefix} Z (mm)"},
        )
        if anatomical_view:
            anatomical_camera, anatomical_note = scan_start_view(data, settings)
            if anatomical_camera is not None:
                fig.update_layout(scene_camera=plotly_camera(anatomical_camera, view_rotation, reverse_view))
            st.caption(anatomical_note)
        if horizontal_view and not anatomical_view:
            camera = None
            if valid_pose_indices:
                first_frame = valid_pose_indices[0]
                probe_position, _ = probe_marker_pose(data, first_frame, settings.use_reference)
                reference_position = np.zeros(3)
                if not settings.use_reference:
                    first_pose = data.poses.loc[data.poses['FrameIndex'] == first_frame].iloc[0]
                    reference_position = first_pose[[f'Ref_{i}' for i in range(1,4)]].to_numpy(dtype=float)
                camera = horizontal_scan_camera(np.asarray([probe_position, reference_position]) @ view_rotation.T)
            if camera is not None:
                if reverse_view:
                    camera['eye'] = {axis: -value for axis, value in camera['eye'].items()}
                fig.update_layout(scene_camera=camera)
                st.caption('Default view: scan-start probe marker left, leg reference marker right. Only the viewing camera changes; XYZ coordinates remain unchanged. Drag to rotate.')
            else:
                st.info('Distinct valid probe and reference positions are needed to set this view.')
        if not show_scene_labels:
            for trace in fig.data:
                if isinstance(trace, go.Scatter3d) and trace.mode and 'text' in trace.mode:
                    trace.mode = '+'.join(part for part in trace.mode.split('+') if part != 'text') or 'markers'
                    if trace.hoverinfo == 'skip':
                        trace.hoverinfo = 'text'
        camera_revision = repr((str(data.root), view_axes, anatomical_view, horizontal_view, reverse_view, mapping_key))
        fig.update_layout(
            scene_dragmode='pan', uirevision=camera_revision,
            scene_uirevision=camera_revision,
            margin=dict(l=0, r=0, t=10, b=160),
            legend=dict(y=-0.17),
        )
        render_navigable_scene(fig, view_height, camera_revision)
        st.caption(f'Baseline X=45°, Y=−90° · lateral u rotation={rotation_u:g}° · longitudinal v rotation={rotation_v:g}°')
        st.slider('Bone frame density (%)', 1, 100, 100, key='bone_frame_density',
            help='Display evenly spaced frames across the entire reconstructed scan. Does not change reconstruction, tracking samples, or downloads.')
        st.caption('Left-drag moves the view. Right-drag near the center turns/tilts; near the edges it rolls. The cursor previews the action, locked when you start dragging. WASD moves, Shift moves faster, scroll zooms, R resets. Click the view to focus keyboard controls.')
        st.caption('Display axes do not change exports: downloaded coordinates remain leg-reference coordinates when reference compensation is enabled.')

        if has_path_points:
            st.caption(
                f"Pathway uses all {len(pathway):,} valid tracking samples in the workbook. "
                "It represents the calibrated ultrasound probe tip, expressed in the same coordinate system as the bone."
            )
            st.download_button(
                "Download pathway CSV", pathway.to_csv(index=False).encode(),
                "probe_pathway.csv", "text/csv",
             key="variantwidget_lc_v1_1_669")

    if full_points is not None and not full_points.empty:
            points = full_points  # Inspection is display-only; exports retain the full cloud.
            export_key = (selected_key, repr(settings), revision, id(st.session_state.get('points')))
            st.caption('CSV uses mirrored pixel u/v and includes source_u/source_v, unmirrored XYZ, original XYZ (u=v=0 on mirrored pixels), new XYZ, and T_00…T_33. T maps [pixel_u × spacing_u_mm, pixel_v × spacing_v_mm, 0, 1] to output XYZ in millimetres; matrix entries use row-major order and column vectors. x/y/z match new_x/y/z. Original and new positions use the same currently selected geometry and pixel samples; only the added rotations differ.')
            if st.button('Build calibrated CSV exports', key="variantwidget_lc_v1_1_678"):
                with st.spinner('Preparing coordinates and transformation matrices'):
                    coordinates, matrices = v1_coordinate_export(points, data, settings)
                    st.session_state['v1_csv_export'] = (export_key, coordinates.to_csv(index=False).encode(), matrices.to_csv(index=False).encode())
            csv_export = st.session_state.get('v1_csv_export')
            if csv_export is not None and csv_export[0] == export_key:
                st.download_button('Download bone CSV · original and new XYZ', csv_export[1], 'Bone_Reconstruction_LCedit_v1.1_coordinates.csv', 'text/csv', key="variantwidget_lc_v1_1_684")
                st.download_button('Download transformation matrices CSV · one per frame', csv_export[2], 'Bone_Reconstruction_LCedit_v1.1_matrices.csv', 'text/csv', key="variantwidget_lc_v1_1_685")
            # NamedTemporaryFile stays exclusively locked on Windows, so create
            # the PLY inside a temporary directory instead.
            with tempfile.TemporaryDirectory() as temp_dir:
                ply_path = Path(temp_dir) / "bone_point_cloud.ply"
                write_ply(points, ply_path)
                ply_bytes = ply_path.read_bytes()
            st.download_button("Download bone PLY", ply_bytes, "bone_point_cloud.ply", "application/octet-stream", key="variantwidget_lc_v1_1_692")
