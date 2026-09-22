"""Filesystem configuration; defaults to the bundled sawbone example."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_ROOT = Path(os.environ.get('BONE_DATA_ROOT', ROOT / 'sample_data')).expanduser().resolve()
ANNOTATION_DB = Path(os.environ.get('BONE_ANNOTATION_DB', ROOT / 'data' / 'annotations.db')).expanduser().resolve()
ANNOTATION_ROOT = Path(os.environ.get('BONE_ANNOTATION_ROOT', ROOT / 'data' / 'annotations')).expanduser().resolve()
DERIVED_ROOT = Path(os.environ.get('BONE_DERIVED_ROOT', ROOT / 'data' / 'derived_series')).expanduser().resolve()

