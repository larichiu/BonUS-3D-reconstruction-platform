"""Explicit image-plane transforms and full-resolution upper-boundary exports."""
from dataclasses import replace
import io
import json
from pathlib import Path
import zipfile

import numpy as np
import pandas as pd

from .geometry import rotation_from_wxyz
from .reconstruct import load_binary_mask, upper_boundary


def frame_transform(row, settings):
    """T maps [u_mm, v_mm, normal_mm, 1] to output millimetres."""
    pp = row[[f'Prob_{i}' for i in range(1, 4)]].to_numpy(dtype=float)
    pr = rotation_from_wxyz(row[[f'Prob_{i}' for i in range(4, 8)]].to_numpy(dtype=float))
    rp = row[[f'Ref_{i}' for i in range(1, 4)]].to_numpy(dtype=float) if settings.use_reference else np.zeros(3)
    rr = rotation_from_wxyz(row[[f'Ref_{i}' for i in range(4, 8)]].to_numpy(dtype=float)) if settings.use_reference else np.eye(3)
    if not np.isfinite(np.r_[pp, rp, settings.tip_offset]).all():
        raise ValueError('Non-finite tracking position or tip offset')
    u, v = settings.image_basis
    image_rotation = np.column_stack([u, v, np.cross(u, v)])
    transform = np.eye(4)
    transform[:3, :3] = rr.T @ pr @ image_rotation
    transform[:3, 3] = rr.T @ (pp + pr @ settings.tip_offset - rp)
    marker = rr.T @ (pp - rp)
    return transform, marker


def transform_pixels(pixels, transform, settings):
    image_mm = np.column_stack([pixels[:, 0] * settings.spacing_x_mm,
                                pixels[:, 1] * settings.spacing_y_mm,
                                np.zeros(len(pixels))])
    return image_mm @ transform[:3, :3].T + transform[:3, 3]


def metadata(row, data, settings):
    result = {
        'patient': data.root.name if 'sequence' in row else data.root.parent.parent.name,
        'sequence': row.get('sequence', f'{data.root.parent.name}/{data.root.name}'),
        'frame_index': int(row['FrameIndex']),
        'source_frame_index': row.get('source_frame_index', int(row['FrameIndex'])),
        'frame_file': Path(row['frame_path']).name,
        'mask_status': row.get('mask_status', 'unspecified'),
        'coordinate_frame': 'leg_reference' if settings.use_reference else 'NDI_tracker',
        'spacing_u_mm': settings.spacing_x_mm,
        'spacing_v_mm': settings.spacing_y_mm,
    }
    for field in ['SourceIndex', 'SourceFrameFile', 'AnnotationFrameIndex']:
        if field in row:
            result[field] = row[field]
    return result


def matrix_record(row, data, settings):
    transform, _ = frame_transform(row, settings)
    record = metadata(row, data, settings)
    record.update({f'T_{i}{j}': transform[i, j] for i in range(4) for j in range(4)})
    record['rotation_u_deg'] = getattr(settings, 'rotation_u_deg', 0.0)
    record['rotation_v_deg'] = getattr(settings, 'rotation_v_deg', 0.0)
    record['baseline_orientation_deg'] = json.dumps(settings.orientation_deg)
    record['flip_horizontal'] = settings.flip_horizontal
    record['flip_depth'] = settings.flip_depth
    record['tip_offset_mm'] = json.dumps(settings.tip_offset_mm)
    return record


def v1_coordinate_export(points, data, settings):
    """Preserve plotted XYZ, add baseline/new XYZ and per-frame 4x4 matrix."""
    baseline = replace(settings, rotation_u_deg=0.0, rotation_v_deg=0.0)
    rows = data.matches.set_index('FrameIndex', drop=False)
    chunks, matrices = [], []
    for frame_id, group in points.groupby('frame_index', sort=False):
        row = rows.loc[frame_id]
        old_transform, _ = frame_transform(row, baseline)
        new_transform, _ = frame_transform(row, settings)
        pixels = group[['u', 'v']].to_numpy(dtype=float)
        original = transform_pixels(pixels, old_transform, settings)
        updated = transform_pixels(pixels, new_transform, settings)
        np.testing.assert_allclose(updated, group[['x', 'y', 'z']], atol=1e-8)
        chunk = group.copy()
        for i, axis in enumerate('xyz'):
            chunk[f'original_{axis}_mm'] = original[:, i]
            chunk[f'new_{axis}_mm'] = updated[:, i]
        record = matrix_record(row, data, settings)
        for key, value in record.items():
            chunk[key] = value
        chunks.append(chunk)
        matrices.append(record)
    return pd.concat(chunks, ignore_index=True), pd.DataFrame(matrices)


def boundary_pixel_export(row, data, settings):
    """One row per uppermost foreground pixel in every populated mask column."""
    mask = load_binary_mask(row['mask_path'], settings.mask_threshold)
    if mask.shape != (data.frame_size[1], data.frame_size[0]):
        raise ValueError('Mask dimensions do not match the original image')
    pixels = upper_boundary(mask, sample_step_px=1)
    transform, marker = frame_transform(row, settings)
    xyz = transform_pixels(pixels, transform, settings)
    tip = transform[:3, 3]
    delta = xyz - tip
    frame = pd.DataFrame(xyz, columns=['x_mm', 'y_mm', 'z_mm'])
    frame.insert(0, 'pixel_v', pixels[:, 1].astype(int))
    frame.insert(0, 'pixel_u', pixels[:, 0].astype(int))
    for axis, index in zip('xyz', range(3)):
        frame[f'probe_tip_{axis}_mm'] = tip[index]
        frame[f'tip_to_pixel_d{axis}_mm'] = delta[:, index]
    frame['distance_from_probe_tip_mm'] = np.linalg.norm(delta, axis=1)
    for key, value in metadata(row, data, settings).items():
        frame[key] = value
    return frame


EXPORT_NOTES = '''Bone Reconstruction_LCedit_v2 — upper-boundary pixel export
Each frame CSV contains one row for the uppermost foreground pixel in every
populated mask column. No boundary subsampling, frame stepping, or outlier
filtering is applied. Interior mask pixels are not included.
pixel_u = zero-based column; pixel_v = zero-based row in the saved cropped image.
These are not uncropped acquisition-image coordinates. Source frame identifiers
are retained when supplied by the tracking workbook.
XYZ and calibrated probe-tip XYZ are in the coordinate_frame named in each row,
in millimetres. Distance is Euclidean norm(pixel XYZ - calibrated tip XYZ) using
the synchronized pose for that frame. The tip is not held at one global position.
These are calculated coordinates, not independently measured pixel locations.
Baseline image orientation is retained; V1 rotation controls are not applied.
frame_manifest.csv lists exported, empty, and skipped frames and their reasons.
T_00 through T_33 are the row-major homogeneous 4x4 matrix for column vectors:
[x_mm,y_mm,z_mm,1]^T = T @ [pixel_u*spacing_u_mm,pixel_v*spacing_v_mm,0,1]^T.
The image origin is the cropped top-left, mapped to the calibrated probe tip.
Rigid rotation of the image about this tip changes XYZ but cannot change its
distance from that tip. Tip distances alone cannot identify orientation errors.
'''


def write_boundary_archive(path, rows, data, settings, progress=None):
    manifest = []
    total_pixels = 0
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for count, (_, row) in enumerate(rows.iterrows(), start=1):
            record = metadata(row, data, settings)
            try:
                if not bool(row['has_pose']):
                    raise ValueError('No synchronized probe pose')
                frame = boundary_pixel_export(row, data, settings)
                record.update(matrix_record(row, data, settings))
                filename = f"frames/frame_{int(row['FrameIndex']):08d}.csv"
                with archive.open(filename, 'w') as raw:
                    with io.TextIOWrapper(raw, encoding='utf-8', newline='') as text:
                        frame.to_csv(text, index=False, chunksize=10000)
                total_pixels += len(frame)
                record.update(status='exported' if len(frame) else 'empty_mask', pixel_count=len(frame), csv_file=filename, reason='')
            except (ValueError, OSError, KeyError) as exc:
                record.update(status='skipped', pixel_count=0, csv_file='', reason=str(exc))
            manifest.append(record)
            if progress:
                progress(count, len(rows))
        report = pd.DataFrame(manifest)
        archive.writestr('frame_manifest.csv', report.to_csv(index=False))
        archive.writestr('README.txt', EXPORT_NOTES)
    return report, total_pixels
