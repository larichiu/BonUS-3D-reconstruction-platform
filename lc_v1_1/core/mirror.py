"""Lossless horizontal image AND mask copies for 3D reconstruction."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile

import pandas as pd
from PIL import Image


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def anatomy_label(side, sequence):
    if side.lower() != 'right':
        return 'Unspecified'
    return {'sequence_000':'Medial · left', 'sequence_001':'Apex · middle',
            'sequence_002':'Lateral · right'}.get(sequence, 'Unspecified')


def mirror(data, output_root, progress=None, force=False):
    """Mirror each original image and mask exactly once; leave tracking unchanged.

    Repeated calls read original inputs and reuse verified derived files. Passing
    already mirrored PatientData is rejected to prevent accidentally undoing it.
    """
    if 'mirror_operation' in data.matches and data.matches['mirror_operation'].eq('mirror').any():
        raise ValueError('mirror expects original input files, not an already mirrored series.')
    output_root = Path(output_root).resolve()
    destination = output_root / data.root.parent.parent.name / data.root.parent.name / (data.root.name+'_for3Drecon')
    destination.mkdir(parents=True, exist_ok=True)
    provenance_path = destination / 'mirror_provenance.json'
    previous = json.loads(provenance_path.read_text()) if provenance_path.exists() else {}
    entries = {}
    used = {}
    table = data.matches.copy()
    table['source_frame_path'] = table['frame_path']
    table['source_mask_path'] = table['mask_path']
    table['mirror_operation'] = 'mirror'
    table['mirror_axis'] = 'horizontal'
    table['image_width_px'] = data.frame_size[0]
    table['anatomical_region'] = anatomy_label(data.root.parent.name, data.root.name)

    def save_copy(source, folder):
        source = Path(source).resolve()
        if source.stem.endswith('_for3Drecon') or output_root in source.parents:
            raise ValueError('Refusing to mirror an existing _for3Drecon file. Select the original sequence.')
        relative = Path(folder) / (source.stem+'_for3Drecon.png')
        # Different source folders may contain duplicate basenames. Keep both.
        if str(relative) in used and used[str(relative)] != str(source):
            suffix = hashlib.sha256(str(source).encode()).hexdigest()[:10]
            relative = Path(folder)/(source.stem+'_'+suffix+'_for3Drecon.png')
        used[str(relative)] = str(source)
        target = destination/relative
        digest = sha256(source)
        old = previous.get(str(relative), {})
        if not force and old.get('source_sha256') == digest and old.get('source') == str(source) and target.exists() and old.get('output_sha256') == sha256(target):
            entries[str(relative)] = old
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as image:
            if image.size != data.frame_size:
                raise ValueError(f'Image/mask dimensions do not match the sequence: {source.name}')
            mirrored = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            with tempfile.NamedTemporaryFile(dir=target.parent, suffix='.png', delete=False) as stream:
                temp = Path(stream.name)
            try:
                mirrored.save(temp, format='PNG')
                temp.replace(target)
            finally:
                temp.unlink(missing_ok=True)
        entries[str(relative)] = {'source':str(source),'source_sha256':digest,
            'output':str(target),'output_sha256':sha256(target),'operation':'mirror',
            'axis':'horizontal','pixel_mapping':'u_new = width - 1 - u_original; v_new = v_original'}
        return target

    for count, (index,row) in enumerate(table.iterrows(), start=1):
        if bool(row['has_frame']):
            table.at[index,'frame_path'] = save_copy(row['source_frame_path'],'images')
        if bool(row['has_mask']):
            if not bool(row['has_frame']):
                raise ValueError(f"Mask has no corresponding ultrasound frame: {row['FrameIndex']}")
            table.at[index,'mask_path'] = save_copy(row['source_mask_path'],'masks')
        if progress:
            progress(count,len(table))
    manifest_columns = ['FrameIndex','source_frame_path','frame_path','source_mask_path','mask_path',
                        'has_frame','has_mask','has_pose','mirror_operation','mirror_axis','image_width_px','anatomical_region']
    manifest_columns += [c for c in ('SourceIndex','SourceFrameFile','AnnotationFrameIndex','mask_status') if c in table]
    manifest = table[manifest_columns].copy()
    manifest['tracking_workbook'] = str(data.pose_file)
    for key,value in {'M_00':-1,'M_01':0,'M_02':data.frame_size[0]-1,
                      'M_10':0,'M_11':1,'M_12':0,'M_20':0,'M_21':0,'M_22':1}.items():
        manifest[key] = value
    manifest.to_csv(destination/'mirror_manifest.csv',index=False)
    temporary = provenance_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(entries,indent=2),encoding='utf-8')
    temporary.replace(provenance_path)
    return replace(data, matches=table, frames_dir=destination/'images', masks_dir=destination/'masks',
                   label_source=data.label_source+' · mirror: image and mask copies in '+str(destination))
