from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd
from PIL import Image

from .geometry import point_in_reference, points_in_reference, rotation_from_wxyz
from .models import PatientData, ReconstructionSettings


def load_binary_mask(path, threshold: int = 127) -> np.ndarray:
    with Image.open(path) as image:
        if image.mode in {"RGBA", "LA"}:
            array = np.asarray(image)
            channel = array[..., 3] if array.shape[-1] >= 4 else array[..., 0]
        else:
            channel = np.asarray(image.convert("L"))
    return channel > threshold


def upper_boundary(mask: np.ndarray, sample_step_px: int = 1) -> np.ndarray:
    """Return [u,v] pixels for the first foreground pixel in each populated column."""
    if mask.ndim != 2:
        raise ValueError("Mask must be a two-dimensional image.")
    populated = mask.any(axis=0)
    columns = np.flatnonzero(populated)
    if not len(columns):
        return np.empty((0, 2), dtype=np.float64)
    columns = columns[::max(1, int(sample_step_px))]
    rows = np.argmax(mask[:, columns], axis=0)
    return np.column_stack([columns, rows]).astype(np.float64)


def reconstruct(
    data: PatientData,
    settings: ReconstructionSettings,
    start_frame: int | None = None,
    end_frame: int | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> pd.DataFrame:
    table = data.matches[data.matches["has_mask"] & data.matches["has_pose"]].copy()
    if start_frame is not None:
        table = table[table["FrameIndex"] >= start_frame]
    if end_frame is not None:
        table = table[table["FrameIndex"] <= end_frame]
    table = table.iloc[::max(1, settings.frame_step)]
    output: list[pd.DataFrame] = []

    for count, (_, row) in enumerate(table.iterrows(), start=1):
        boundary = upper_boundary(load_binary_mask(row["mask_path"], settings.mask_threshold), settings.sample_step_px)
        if len(boundary):
            # Cropped image top-left (0, 0) is the calibrated tip.
            horizontal = boundary[:, 0] * settings.spacing_x_mm
            depth = boundary[:, 1] * settings.spacing_y_mm
            if settings.flip_horizontal:
                horizontal *= -1
            if settings.flip_depth:
                depth *= -1
            local = np.zeros((len(boundary), 3), dtype=np.float64)
            local[:, 0] = horizontal
            local[:, 2] = depth
            local = settings.image_points(boundary[:,0], boundary[:,1])

            probe_pos = row[["Prob_1", "Prob_2", "Prob_3"]].to_numpy(dtype=np.float64)
            probe_rot = rotation_from_wxyz(row[["Prob_4", "Prob_5", "Prob_6", "Prob_7"]].to_numpy(dtype=np.float64))
            if settings.use_reference:
                ref_pos = row[["Ref_1", "Ref_2", "Ref_3"]].to_numpy(dtype=np.float64)
                ref_rot = rotation_from_wxyz(row[["Ref_4", "Ref_5", "Ref_6", "Ref_7"]].to_numpy(dtype=np.float64))
            else:
                ref_pos = np.zeros(3)
                ref_rot = np.eye(3)
            xyz = points_in_reference(local, probe_pos, probe_rot, ref_pos, ref_rot)
            frame = pd.DataFrame(xyz, columns=["x", "y", "z"])
            frame["frame_index"] = int(row["FrameIndex"])
            frame["u"] = boundary[:, 0]
            frame["v"] = boundary[:, 1]
            for column in ('sequence','source_frame_index','frame_label'):
                if column in row:
                    frame[column]=row[column]
            output.append(frame)
        if progress:
            progress(count, len(table))
    if not output:
        return pd.DataFrame(columns=["x", "y", "z", "frame_index", "u", "v"])
    return pd.concat(output, ignore_index=True)


def probe_pathway(data: PatientData, settings: ReconstructionSettings) -> pd.DataFrame:
    """Return the calibrated probe-tip trajectory using every valid pose sample."""
    probe_columns = [
        "Prob_1", "Prob_2", "Prob_3", "Prob_4", "Prob_5", "Prob_6", "Prob_7",
    ]
    reference_columns = [
        "Ref_1", "Ref_2", "Ref_3", "Ref_4", "Ref_5", "Ref_6", "Ref_7",
    ]
    required = probe_columns + (reference_columns if settings.use_reference else [])
    table = data.poses.dropna(subset=required).copy()
    output: list[dict[str, float | int]] = []
    for sample_order, (_, row) in enumerate(table.iterrows()):
        probe_pos = row[["Prob_1", "Prob_2", "Prob_3"]].to_numpy(dtype=np.float64)
        probe_rot = rotation_from_wxyz(
            row[["Prob_4", "Prob_5", "Prob_6", "Prob_7"]].to_numpy(dtype=np.float64)
        )
        if settings.use_reference:
            ref_pos = row[["Ref_1", "Ref_2", "Ref_3"]].to_numpy(dtype=np.float64)
            ref_rot = rotation_from_wxyz(
                row[["Ref_4", "Ref_5", "Ref_6", "Ref_7"]].to_numpy(dtype=np.float64)
            )
        else:
            ref_pos = np.zeros(3, dtype=np.float64)
            ref_rot = np.eye(3, dtype=np.float64)
        xyz = point_in_reference(settings.tip_offset, probe_pos, probe_rot, ref_pos, ref_rot)
        output.append({
            "x": float(xyz[0]), "y": float(xyz[1]), "z": float(xyz[2]),
            "frame_index": int(row["FrameIndex"]), "sample_order": sample_order,
        })
        for column in ('sequence','source_frame_index','frame_label'):
            if column in row:
                output[-1][column]=row[column]
    return pd.DataFrame(output) if output else pd.DataFrame(columns=["x", "y", "z", "frame_index", "sample_order"])


def probe_marker_pose(
    data: PatientData, frame_index: int, use_reference: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """Return probe NDI marker position and orientation at one exact frame."""
    rows = data.poses[data.poses["FrameIndex"] == frame_index]
    if rows.empty:
        raise ValueError(f"No tracking sample exists for frame {frame_index}.")
    row = rows.iloc[0]
    probe_pos = row[["Prob_1", "Prob_2", "Prob_3"]].to_numpy(dtype=np.float64)
    probe_rot = rotation_from_wxyz(
        row[["Prob_4", "Prob_5", "Prob_6", "Prob_7"]].to_numpy(dtype=np.float64)
    )
    if not use_reference:
        return probe_pos, probe_rot
    ref_pos = row[["Ref_1", "Ref_2", "Ref_3"]].to_numpy(dtype=np.float64)
    ref_rot = rotation_from_wxyz(
        row[["Ref_4", "Ref_5", "Ref_6", "Ref_7"]].to_numpy(dtype=np.float64)
    )
    return ref_rot.T @ (probe_pos - ref_pos), ref_rot.T @ probe_rot


def statistical_filter(points: pd.DataFrame, z_limit: float = 4.0) -> pd.DataFrame:
    if points.empty or z_limit <= 0:
        return points.copy()
    xyz = points[["x", "y", "z"]].to_numpy(dtype=np.float64)
    median = np.median(xyz, axis=0)
    mad = np.median(np.abs(xyz - median), axis=0)
    scale = np.where(mad > 1e-9, 1.4826 * mad, np.inf)
    score = np.max(np.abs((xyz - median) / scale), axis=1)
    return points.loc[score <= z_limit].reset_index(drop=True)
