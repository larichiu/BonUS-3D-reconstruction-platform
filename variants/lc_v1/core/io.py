from __future__ import annotations

import re
import hashlib
import sqlite3
from pathlib import Path

import pandas as pd
from PIL import Image

from .models import PatientData


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
from bone_config import ANNOTATION_DB as DEFAULT_ANNOTATION_DB, ANNOTATION_ROOT as DEFAULT_ANNOTATION_ROOT, DATA_ROOT as DEFAULT_REDUCED_ROOT


def _image_files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)


def _find_frames_dir(root: Path) -> Path:
    if _image_files(root):
        return root
    candidates = [
        p for p in root.iterdir()
        if p.is_dir() and "cropped_frames" in p.name.lower()
    ]
    if not candidates:
        candidates = [p for p in root.iterdir() if p.is_dir() and p.name.lower().endswith("frames")]
    if not candidates:
        descendant_folders = sorted({p.parent for p in root.rglob("frame_*.png")})
        if len(descendant_folders) == 1:
            return descendant_folders[0]
        if len(descendant_folders) > 1:
            raise ValueError(
                "More than one frame sequence was found. Select a specific side or sequence folder."
            )
        raise FileNotFoundError(f"No frame folder was found inside: {root}")
    return sorted(candidates)[0]


def _find_pose_file(root: Path, frames_dir: Path | None = None) -> Path:
    files = sorted(p for p in root.glob("*.xlsx") if not p.name.startswith("~$"))
    if not files and frames_dir is not None:
        files = sorted(p for p in frames_dir.glob("*.xlsx") if not p.name.startswith("~$"))
    if not files:
        files = sorted(p for p in root.rglob("*.xlsx") if not p.name.startswith("~$"))
    if not files:
        raise FileNotFoundError(f"No Excel pose file was found inside: {root}")
    if len(files) > 1:
        expected_name = f"{frames_dir.name if frames_dir is not None else root.name}.xlsx"
        preferred = [p for p in files if p.name.lower() == expected_name.lower()]
        if len(preferred) == 1:
            return preferred[0]
        sequence_matches = [p for p in files if frames_dir is not None and p.parent == frames_dir]
        if len(sequence_matches) == 1:
            return sequence_matches[0]
        raise ValueError("More than one Excel pose file was found. Select a specific sequence folder.")
    return files[0]


def _frame_index(name: str) -> int | None:
    values = re.findall(r"\d+", Path(name).stem)
    return int(values[-1]) if values else None


def _mask_map(mask_dir: Path) -> dict[int, Path]:
    result: dict[int, Path] = {}
    for path in _image_files(mask_dir):
        idx = _frame_index(path.name)
        if idx is not None:
            result[idx] = path
    return result


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _original_index_from_reduced_path(rel_path: str) -> int:
    """Reduced filenames are one-based original positions (1, 5, 9, ...)."""
    idx = _frame_index(Path(rel_path).name)
    if idx is None or idx < 1:
        raise ValueError(f"Cannot recover original frame index from {rel_path!r}")
    return idx - 1


def _connect_read_only(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _matching_annotation_sequence(
    frames: dict[int, Path], sequence_name: str, db_path: Path, reduced_root: Path
) -> tuple[int, str]:
    """Identify the annotation sequence by image content, not patient aliases."""
    with _connect_read_only(db_path) as connection:
        candidates = connection.execute(
            "SELECT s.id, p.code, s.side, s.name FROM sequences s "
            "JOIN patients p ON p.id=s.patient_id WHERE s.name=?",
            (sequence_name,),
        ).fetchall()
        matches: list[tuple[int, str]] = []
        for candidate in candidates:
            rows = connection.execute(
                "SELECT idx, rel_path FROM frames WHERE sequence_id=? ORDER BY idx",
                (candidate["id"],),
            ).fetchall()
            if not rows:
                continue
            probes = [rows[0], rows[len(rows) // 2], rows[-1]]
            compared = 0
            valid = True
            for row in probes:
                try:
                    original_idx = _original_index_from_reduced_path(row["rel_path"])
                except ValueError:
                    valid = False
                    break
                original = frames.get(original_idx)
                reduced = reduced_root / Path(row["rel_path"])
                if original is None or not reduced.is_file():
                    valid = False
                    break
                compared += 1
                if original.stat().st_size != reduced.stat().st_size or _digest(original) != _digest(reduced):
                    valid = False
                    break
            if valid and compared:
                matches.append((int(candidate["id"]), f"patient {candidate['code']} / {candidate['side']} / {candidate['name']}"))
    if not matches:
        raise FileNotFoundError(
            "No annotation sequence matches these cropped frames. The patient may not have been indexed or labelled yet."
        )
    if len(matches) > 1:
        raise ValueError("More than one annotation sequence has the same image fingerprint; automatic selection is ambiguous.")
    return matches[0]


def annotation_mask_map(
    frame_paths: list[Path], sequence_name: str,
    db_path: Path = DEFAULT_ANNOTATION_DB,
    annotation_root: Path = DEFAULT_ANNOTATION_ROOT,
    reduced_root: Path = DEFAULT_REDUCED_ROOT,
) -> tuple[dict[int, Path], dict[int, Path], Path, int, str]:
    if not db_path.is_file():
        raise FileNotFoundError(f"Annotation database was not found: {db_path}")
    frames = {_frame_index(path.name): path for path in frame_paths}
    sequence_id, description = _matching_annotation_sequence(frames, sequence_name, db_path, reduced_root)
    result: dict[int, Path] = {}
    reduced_frames: dict[int, Path] = {}
    with _connect_read_only(db_path) as connection:
        frame_rows = connection.execute(
            "SELECT idx, rel_path FROM frames WHERE sequence_id=? ORDER BY idx",
            (sequence_id,),
        ).fetchall()
        for row in frame_rows:
            original_idx = _original_index_from_reduced_path(row["rel_path"])
            reduced_path = reduced_root / Path(row["rel_path"])
            if reduced_path.is_file():
                reduced_frames[original_idx] = reduced_path
        rows = connection.execute(
            "SELECT m.frame_idx, m.rel_path, f.rel_path AS frame_rel_path "
            "FROM masks m "
            "JOIN frame_status fs ON fs.annotator_id=m.annotator_id "
            " AND fs.sequence_id=m.sequence_id AND fs.frame_idx=m.frame_idx "
            "JOIN frames f ON f.sequence_id=m.sequence_id AND f.idx=m.frame_idx "
            "WHERE m.sequence_id=? AND fs.status='accepted' ORDER BY m.frame_idx",
            (sequence_id,),
        ).fetchall()
        for row in rows:
            original_idx = _original_index_from_reduced_path(row["frame_rel_path"])
            mask = annotation_root / Path(row["rel_path"])
            if mask.is_file():
                if original_idx in result:
                    raise ValueError(f"Multiple accepted masks map to original frame {original_idx}.")
                result[original_idx] = mask
    if not result:
        raise FileNotFoundError(f"The matched annotation sequence ({description}) has no accepted mask files.")
    if not reduced_frames:
        raise FileNotFoundError(f"No reduced images were found for the matched annotation sequence ({description}).")
    return result, reduced_frames, annotation_root, sequence_id, description


def _direct_reduced_annotation(
    root: Path,
    reduced_file_to_original: dict[str, int],
    db_path: Path = DEFAULT_ANNOTATION_DB,
    annotation_root: Path = DEFAULT_ANNOTATION_ROOT,
) -> tuple[dict[int, Path], int, str]:
    patient_code = root.parent.parent.name
    side = root.parent.name
    sequence_name = root.name
    with _connect_read_only(db_path) as connection:
        sequence = connection.execute(
            "SELECT s.id FROM sequences s JOIN patients p ON p.id=s.patient_id "
            "WHERE p.code=? AND s.side=? AND s.name=?",
            (patient_code, side, sequence_name),
        ).fetchone()
        if sequence is None:
            raise FileNotFoundError(
                f"The annotation database has no sequence for {patient_code}/{side}/{sequence_name}."
            )
        sequence_id = int(sequence["id"])
        rows = connection.execute(
            "SELECT m.frame_idx, m.rel_path, f.rel_path AS frame_rel_path "
            "FROM masks m "
            "JOIN frame_status fs ON fs.annotator_id=m.annotator_id "
            " AND fs.sequence_id=m.sequence_id AND fs.frame_idx=m.frame_idx "
            "JOIN frames f ON f.sequence_id=m.sequence_id AND f.idx=m.frame_idx "
            "WHERE m.sequence_id=? AND fs.status='accepted' ORDER BY m.frame_idx",
            (sequence_id,),
        ).fetchall()
    masks: dict[int, Path] = {}
    for row in rows:
        reduced_name = Path(row["frame_rel_path"]).name.lower()
        original_idx = reduced_file_to_original.get(reduced_name)
        if original_idx is None:
            continue
        mask = annotation_root / Path(row["rel_path"])
        if mask.is_file():
            masks[original_idx] = mask
    return masks, sequence_id, f"patient {patient_code} / {side} / {sequence_name}"


def read_poses(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="Frame_NDI_Sync")
    required = [
        "FrameIndex", "FrameFile",
        "Prob_1", "Prob_2", "Prob_3", "Prob_4", "Prob_5", "Prob_6", "Prob_7",
        "Ref_1", "Ref_2", "Ref_3", "Ref_4", "Ref_5", "Ref_6", "Ref_7",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Pose workbook is missing columns: {', '.join(missing)}")
    for col in required[2:]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["FrameIndex"] = pd.to_numeric(df["FrameIndex"], errors="coerce").astype("Int64")
    return df


def platform_revision() -> tuple:
    """Invalidate displayed data after committed platform edits, including WAL."""
    result = []
    for path in (DEFAULT_ANNOTATION_DB, Path(str(DEFAULT_ANNOTATION_DB)+'-wal')):
        try:
            stat = path.stat()
            result.append((stat.st_mtime_ns, stat.st_size))
        except FileNotFoundError:
            result.append(None)
    return tuple(result)


def _load_platform_prepared(root: Path) -> PatientData | None:
    """Read one consistent platform snapshot; never prepare or modify its data."""
    with _connect_read_only(DEFAULT_ANNOTATION_DB) as con:
        con.execute('BEGIN')
        if not con.execute("SELECT 1 FROM sqlite_master WHERE name='sequence_tracking'").fetchone():
            return None
        seq = con.execute('''SELECT s.id,s.rel_root,t.workbook_rel_path,t.frame_count
            FROM sequences s JOIN patients p ON p.id=s.patient_id
            JOIN sequence_tracking t ON t.sequence_id=s.id
            WHERE p.code=? AND s.side=? AND s.name=?''',
            (root.parent.parent.name, root.parent.name, root.name)).fetchone()
        if seq is None:
            return None
        pose_file = DEFAULT_REDUCED_ROOT / seq['workbook_rel_path']
        poses = read_poses(pose_file)
        rows = con.execute('SELECT idx,rel_path,source_idx FROM frames WHERE sequence_id=? ORDER BY idx', (seq['id'],)).fetchall()
        masks = con.execute('''SELECT m.frame_idx,m.rel_path,m.annotator_id,fs.status FROM masks m
            JOIN frame_status fs ON fs.annotator_id=m.annotator_id AND fs.sequence_id=m.sequence_id AND fs.frame_idx=m.frame_idx
            WHERE m.sequence_id=? AND fs.status IN ('accepted','propagated') ''', (seq['id'],)).fetchall()
    needed = {'AnnotationFrameIndex','SourceIndex','SourceFrameFile'}
    if not needed.issubset(poses.columns) or len(poses) != len(rows) or len(rows) != seq['frame_count']:
        raise ValueError('Platform tracking export is stale or incomplete. Republish tracking from the annotation platform.')
    if poses['AnnotationFrameIndex'].duplicated().any() or poses['FrameIndex'].duplicated().any():
        raise ValueError('Platform tracking has duplicate frame IDs')
    by_idx = poses.set_index('AnnotationFrameIndex')
    mask_map = {}
    status_map = {}
    for mask in masks:
        if mask['frame_idx'] in mask_map:
            raise ValueError('Multiple annotators have masks for the same frame. Select an annotation set before reconstruction.')
        mask_path = DEFAULT_ANNOTATION_ROOT / mask['rel_path']
        if not mask_path.is_file():
            raise ValueError(f"Accepted mask file is missing for frame {mask['frame_idx']}")
        mask_map[mask['frame_idx']] = mask_path
        status_map[mask['frame_idx']] = mask['status']
    records = []
    for frame in rows:
        if frame['idx'] not in by_idx.index:
            raise ValueError('Platform tracking is missing an annotation frame ID')
        pose = by_idx.loc[frame['idx']]
        rel = Path(frame['rel_path']).relative_to(Path(seq['rel_root'])).as_posix()
        if int(pose['SourceIndex']) != frame['source_idx'] or str(pose['FrameFile']).replace('\\','/') != rel:
            raise ValueError('Platform frame-to-tracking identity mismatch; reconstruction stopped')
        path = DEFAULT_REDUCED_ROOT / frame['rel_path']
        if not path.is_file():
            raise ValueError(f"Platform frame is missing: {frame['idx']}")
        records.append({'FrameIndex':int(pose['FrameIndex']), 'frame_path':path, 'mask_path':mask_map.get(frame['idx']), 'mask_status':status_map.get(frame['idx'],'none')})
    if not records:
        raise ValueError('Platform sequence has no frames')
    matches = pd.DataFrame(records).merge(poses, on='FrameIndex', validate='one_to_one')
    matches['has_frame'] = True
    matches['has_mask'] = matches['mask_path'].notna()
    matches['has_pose'] = matches['Prob_1'].notna()
    with Image.open(records[0]['frame_path']) as im:
        size = im.size
    full_poses = read_poses(pose_file.with_name('full.xlsx'))
    return PatientData(root, root, DEFAULT_ANNOTATION_ROOT, pose_file, full_poses, matches, size,
                       'Annotation platform: saved accepted + propagated masks, including skipped frames', int(seq['id']))


def load_patient(root: str | Path, masks_dir: str | Path | None = None) -> PatientData:
    root = Path(root).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Patient folder does not exist: {root}")
    if masks_dir is None and (root / 'masks').is_dir():
        masks_dir = root / 'masks'
    if masks_dir is None and 'reduced_recordings' in {p.lower() for p in root.parts}:
        prepared = _load_platform_prepared(root)
        if prepared is not None:
            return prepared
    frames_dir = _find_frames_dir(root)
    pose_file = _find_pose_file(root, frames_dir)
    direct_reduced = masks_dir is None and "reduced_recordings" in {part.lower() for part in frames_dir.parts}
    if direct_reduced:
        root = frames_dir
        reduced_paths = _image_files(frames_dir)
        poses = read_poses(pose_file)
        reduced_file_to_original = {
            Path(str(row["FrameFile"])).name.lower(): int(row["FrameIndex"])
            for _, row in poses.dropna(subset=["FrameIndex", "FrameFile"]).iterrows()
        }
        reconstruction_frames = {}
        for path in reduced_paths:
            original_idx = reduced_file_to_original.get(path.name.lower())
            if original_idx is not None:
                reconstruction_frames[original_idx] = path
        if not reconstruction_frames:
            raise ValueError("The tracking workbook's FrameFile values do not match the reduced images.")
        masks, annotation_sequence_id, description = _direct_reduced_annotation(
            root, reduced_file_to_original
        )
        mask_path = DEFAULT_ANNOTATION_ROOT
        label_source = f"Annotation platform reduced images: {description} (accepted masks only)"
        frames = pd.DataFrame(
            [{"FrameIndex": idx, "frame_path": path} for idx, path in sorted(reconstruction_frames.items())]
        )
        frames["FrameIndex"] = frames["FrameIndex"].astype("Int64")
        frames["mask_path"] = frames["FrameIndex"].map(masks)
        matches = frames.merge(poses, how="left", on="FrameIndex", suffixes=("", "_pose"))
        matches["has_frame"] = True
        matches["has_mask"] = matches["mask_path"].notna()
        matches["has_pose"] = matches["Prob_1"].notna()
        with Image.open(frames.iloc[0]["frame_path"]) as image:
            frame_size = image.size
        return PatientData(
            root, frames_dir, mask_path, pose_file, poses, matches, frame_size,
            label_source, annotation_sequence_id,
        )

    original_frame_paths = _image_files(frames_dir)
    sequence_name = frames_dir.name.replace("__cropped_frames", "").replace("_cropped_frames", "")
    label_source = "Local mask folder"
    annotation_sequence_id = None
    if masks_dir:
        mask_path = Path(masks_dir).expanduser().resolve()
        if not mask_path.is_dir():
            raise FileNotFoundError(f"Mask folder does not exist: {mask_path}")
        masks = _mask_map(mask_path)
        reconstruction_frames = {
            _frame_index(path.name): path for path in original_frame_paths
            if _frame_index(path.name) is not None
        }
    else:
        local_candidates = [p for p in root.iterdir() if p.is_dir() and "mask" in p.name.lower()]
        if local_candidates:
            mask_path = sorted(local_candidates)[0]
            masks = _mask_map(mask_path)
            reconstruction_frames = {
                _frame_index(path.name): path for path in original_frame_paths
                if _frame_index(path.name) is not None
            }
        else:
            masks, reconstruction_frames, mask_path, annotation_sequence_id, description = annotation_mask_map(
                original_frame_paths, sequence_name
            )
            frames_dir = next(iter(reconstruction_frames.values())).parent
            label_source = f"Annotation platform reduced images: {description} (accepted masks only)"

    poses = read_poses(pose_file)
    frames = pd.DataFrame(
        [{"FrameIndex": idx, "frame_path": path} for idx, path in sorted(reconstruction_frames.items())]
    )
    frames["FrameIndex"] = frames["FrameIndex"].astype("Int64")
    frames["mask_path"] = frames["FrameIndex"].map(masks)
    matches = frames.merge(poses, how="left", on="FrameIndex", suffixes=("", "_pose"))
    matches["has_frame"] = True
    matches["has_mask"] = matches["mask_path"].notna()
    matches["has_pose"] = matches["Prob_1"].notna()
    with Image.open(frames.iloc[0]["frame_path"]) as image:
        frame_size = image.size
    return PatientData(
        root, frames_dir, mask_path, pose_file, poses, matches, frame_size,
        label_source, annotation_sequence_id,
    )


def write_ply(points, path: str | Path) -> None:
    path = Path(path)
    with path.open("w", encoding="ascii", newline="\n") as stream:
        stream.write("ply\nformat ascii 1.0\n")
        stream.write(f"element vertex {len(points)}\n")
        stream.write("property float x\nproperty float y\nproperty float z\n")
        stream.write("property int frame_index\nend_header\n")
        for x, y, z, frame_index in points[["x", "y", "z", "frame_index"]].itertuples(index=False, name=None):
            stream.write(f"{x:.6f} {y:.6f} {z:.6f} {int(frame_index)}\n")
