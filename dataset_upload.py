"""Validate a portable dataset before allowing reconstruction."""
import re
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath
import numpy as np
import pandas as pd
from PIL import Image

MAX_BYTES = 300 * 1024 * 1024
MAX_FILES = 5000
POSE_COLUMNS = [f'{p}_{i}' for p in ('Prob', 'Ref') for i in range(1, 8)]

def extract_dataset(source, destination):
    """Extract to a new private session directory; reject traversal and oversized archives."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    try:
        with zipfile.ZipFile(source) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_FILES or sum(x.file_size for x in entries) > MAX_BYTES:
                raise ValueError('ZIP exceeds 5,000 entries or 300 MB uncompressed.')
            seen = set()
            for entry in entries:
                path = PurePosixPath(entry.filename)
                if (path.is_absolute() or '..' in path.parts or '\\' in entry.filename
                        or ':' in entry.filename or stat.S_ISLNK(entry.external_attr >> 16)):
                    raise ValueError('ZIP contains an unsafe path or symbolic link.')
                if not path.parts or entry.is_dir():
                    continue
                key = path.as_posix().casefold()
                if key in seen:
                    raise ValueError('ZIP contains duplicate filenames.')
                seen.add(key)
                if path.suffix.lower() not in {'.png', '.xlsx'}:
                    raise ValueError('Only PNG images/masks and XLSX tracking workbooks are accepted.')
                if not all(re.fullmatch(r'[A-Za-z0-9_. -]+', p) for p in path.parts):
                    raise ValueError('Use letters, digits, underscores, hyphens and spaces in names.')
                target = destination.joinpath(*path.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry) as src, target.open('wb') as dst:
                    shutil.copyfileobj(src, dst)
        summary = validate_dataset(destination)
        return summary
    except Exception:
        shutil.rmtree(destination)
        raise

def validate_dataset(root):
    root = Path(root)
    sequences = sorted(p for p in root.glob('*/*/sequence_*') if p.is_dir())
    if not sequences:
        raise ValueError('Expected DATASET/SIDE/sequence_000/{frames,masks,sequence_000.xlsx} at ZIP root.')
    summary = []
    used = set()
    for seq in sequences:
        frames = sorted((seq/'frames').glob('*.png'))
        masks = sorted((seq/'masks').glob('*.png'))
        workbook = seq/(seq.name+'.xlsx')
        if not frames or not masks or not workbook.is_file():
            raise ValueError(f'{seq.name}: frames, masks and matching XLSX workbook are required.')
        # XLSX itself is an archive: reject decompression bombs before parsing.
        with zipfile.ZipFile(workbook) as xlsx:
            if sum(x.file_size for x in xlsx.infolist()) > 50*1024*1024:
                raise ValueError('Tracking workbook expands beyond 50 MB.')
        table = pd.read_excel(workbook, sheet_name='Frame_NDI_Sync')
        required = ['FrameIndex', 'FrameFile'] + POSE_COLUMNS
        if not set(required).issubset(table):
            raise ValueError(f'{seq.name}: missing columns: {sorted(set(required)-set(table))}')
        ids = pd.to_numeric(table.FrameIndex, errors='coerce')
        if ids.isna().any() or ids.duplicated().any() or (ids < 0).any() or (ids % 1 != 0).any():
            raise ValueError('FrameIndex must contain unique nonnegative integers.')
        pose = table[POSE_COLUMNS].apply(pd.to_numeric, errors='coerce').to_numpy(dtype=float)
        if not np.isfinite(pose).all():
            raise ValueError('Tracking contains missing or non-finite values.')
        for prefix in ('Prob', 'Ref'):
            q = table[[f'{prefix}_{i}' for i in range(4,8)]].to_numpy(dtype=float)
            if (np.linalg.norm(q, axis=1) < 1e-8).any():
                raise ValueError('Tracking contains a zero quaternion.')
        by_id = {int(row.FrameIndex): row for _, row in table.iterrows()}
        sizes = set()
        frame_names = {p.name for p in frames}
        if any(p.name not in frame_names for p in masks):
            raise ValueError('Every mask filename must match an image filename.')
        if len(table) != len(frames):
            raise ValueError('Provide exactly one tracking row per uploaded image.')
        for frame in frames:
            match = re.fullmatch(r'frame_(\d+)\.png', frame.name)
            if not match or int(match[1]) not in by_id:
                raise ValueError('Use frame_000000.png names with corresponding FrameIndex values.')
            row = by_id[int(match[1])]
            if str(row.FrameFile).replace('\\','/') != 'frames/'+frame.name:
                raise ValueError('FrameFile must equal frames/<matching filename>.')
            with Image.open(frame) as im:
                im.load()
                size = im.size
                sizes.add(size)
            mask = seq/'masks'/frame.name
            if mask.exists():
                with Image.open(mask) as im:
                    im.load()
                    if im.size != size or im.mode != 'L' or not set(np.unique(im)).issubset({0,255}):
                        raise ValueError('Masks must match image dimensions and be grayscale PNGs with 0/255 pixels.')
        if len(sizes) != 1:
            raise ValueError('All images in one sequence must have identical dimensions.')
        used.update(frames + masks + [workbook])
        summary.append({'dataset': seq.parent.parent.name, 'side': seq.parent.name,
                        'sequence': seq.name, 'frames': len(frames), 'masks': len(masks)})
    files = {p for p in root.rglob('*') if p.is_file()}
    if files != used:
        raise ValueError('Unexpected files or folders: ZIP must contain only the documented dataset structure.')
    return summary

