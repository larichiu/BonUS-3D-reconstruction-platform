"""One deployable entry point for all four preserved reconstruction variants."""
import hashlib
import io
import os
import runpy
import tempfile
from pathlib import Path
import streamlit as st
from bone_config import ROOT, DATA_ROOT
from dataset_upload import extract_dataset

st.set_page_config(page_title='3D Bone Reconstruction', page_icon='🦴', layout='wide')
VERSIONS = {'Original': 'original', 'LCedit v1 — rotations': 'lc_v1',
            'LCedit v1.1 — mirror + rotations': 'lc_v1_1', 'LCedit v2 — pixel analysis': 'lc_v2'}
default = os.environ.get('BONE_VARIANT', 'lc_v2')
labels = list(VERSIONS)
index = list(VERSIONS.values()).index(default) if default in VERSIONS.values() else 3
def reset_variant_state():
    # A callback runs before widget registration, including frontend widget restoration.
    for key in list(st.session_state):
        if not key.startswith('release_'):
            del st.session_state[key]

selected = st.sidebar.selectbox('Platform version', labels, index=index, key='release_variant', on_change=reset_variant_state)
page = st.sidebar.radio('Page', ['Platform', 'About & development', 'Upload guide'], key='release_page')

if page != 'Platform':
    filename = 'ABOUT.md' if page == 'About & development' else 'DATA_GUIDE.md'
    st.markdown((ROOT/'docs'/filename).read_text(encoding='utf-8'))
    st.stop()

def choose_uploaded_data():
    reset_variant_state()
    st.session_state.release_source = 'Upload dataset ZIP' if st.session_state.get('release_zip') is not None else 'Bundled sawbone sample'

source = st.sidebar.radio('Data source', ['Bundled sawbone sample', 'Upload dataset ZIP', 'Configured local data'], key='release_source', on_change=reset_variant_state)
with st.container(border=True):
    st.subheader('Upload your ultrasound dataset')
    st.caption('Drag a ZIP into the box or click Upload / Browse files. Include ultrasound PNGs, matching binary masks and synchronized tracking XLSX files. Maximum ZIP size: 100 MB.')
    uploaded = st.file_uploader('Dataset ZIP', type=['zip'], key='release_zip', on_change=choose_uploaded_data)
    with st.expander('Required folder structure and example'):
        st.code('MY_DATASET/right/sequence_000/\n  frames/frame_000000.png\n  masks/frame_000000.png\n  sequence_000.xlsx', language=None)
        st.caption('Use the Upload guide in the sidebar for tracking columns and calibration conventions.')
        st.download_button('Download example ZIP', (ROOT/'sample_data'/'sawbone_sample.zip').read_bytes(), 'sawbone_sample.zip', key='release_example_zip')
dataset = ROOT/'sample_data'
if source == 'Upload dataset ZIP':
    st.info('Upload cropped ultrasound images, matching binary masks and synchronized NDI poses. See Upload guide for the exact ZIP structure.')
    if uploaded is None:
        st.stop()
    content = uploaded.getvalue()
    if len(content) > 100*1024*1024:
        st.error('ZIP exceeds 100 MB. Upload a smaller subset or configure local data.')
        st.stop()
    digest = hashlib.sha256(content).hexdigest()
    if st.session_state.get('release_upload_hash') != digest:
        workspace = tempfile.TemporaryDirectory(prefix='bone-upload-')
        try:
            result = extract_dataset(io.BytesIO(content), Path(workspace.name)/'dataset')
        except Exception as exc:
            workspace.cleanup()
            st.error(f'Dataset rejected: {exc}')
            st.stop()
        old = st.session_state.get('release_workspace')
        st.session_state.release_workspace = workspace
        st.session_state.release_upload_hash = digest
        st.session_state.release_upload_summary = result
        if old is not None:
            old.cleanup()
    dataset = Path(st.session_state.release_workspace.name)/'dataset'
    with st.expander('Validated upload'):
        st.dataframe(st.session_state.release_upload_summary)
elif source == 'Configured local data':
    dataset = DATA_ROOT
    st.sidebar.caption(f'Configured directory: {dataset}')
else:
    st.sidebar.caption('Sawbone phantom: 36 frames from three scans. This small subset demonstrates the workflow, not reconstruction accuracy.')
    st.sidebar.download_button('Download sample dataset ZIP', (ROOT/'sample_data'/'sawbone_sample.zip').read_bytes(), 'sawbone_sample.zip')

identity = (VERSIONS[selected], str(dataset))
if st.session_state.get('release_active') != identity:
    # Clear variant-specific widgets and reconstruction caches; preserve upload ownership.
    for key in list(st.session_state):
        if not key.startswith('release_'):
            del st.session_state[key]
    st.session_state.release_active = identity
    old_derived = st.session_state.get('release_derived_workspace')
    if old_derived is not None:
        old_derived.cleanup()
    st.session_state.release_derived_workspace = tempfile.TemporaryDirectory(prefix='bone-derived-')
st.session_state.dataset_root = str(dataset)
st.session_state.derived_root = st.session_state.release_derived_workspace.name
with st.sidebar.expander('Baseline image orientation'):
    st.caption('Euler degrees: Rz @ Ry @ Rx. Use acquisition-specific calibration; defaults are provisional.')
    st.session_state.baseline_angles = tuple(st.number_input(f'Baseline {axis} (degrees)', value=value, key=f'baseline_{axis}')
                                            for axis, value in zip('XYZ', (45.0, -90.0, 0.0)))
runpy.run_path(str(ROOT/'variants'/VERSIONS[selected]/'app.py'), run_name='__main__')

