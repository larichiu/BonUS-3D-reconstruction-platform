"""Combine saved scans in a shared reference-marker coordinate system."""
from pathlib import Path
import pandas as pd
from .io import DEFAULT_ANNOTATION_DB, _connect_read_only, load_patient
from .models import PatientData


def annotated_sequences(patient_folder: Path) -> list[dict]:
    local = sorted(p for p in patient_folder.glob('*/sequence_*') if (p/'masks').is_dir())
    if local:
        return [dict(side=p.parent.name, name=p.name, accepted=int(load_patient(p).matches.has_mask.sum()),
                     propagated=0, folder=p, label=f"{p.parent.name} / {p.name}") for p in local]
    with _connect_read_only(DEFAULT_ANNOTATION_DB) as con:
        rows=con.execute('''SELECT s.side,s.name,
            SUM(fs.status='accepted') AS accepted,SUM(fs.status='propagated') AS propagated
            FROM sequences s JOIN patients p ON p.id=s.patient_id
            JOIN masks m ON m.sequence_id=s.id
            JOIN frame_status fs ON fs.sequence_id=m.sequence_id AND fs.frame_idx=m.frame_idx AND fs.annotator_id=m.annotator_id
            WHERE p.code=? AND fs.status IN ('accepted','propagated')
            GROUP BY s.id ORDER BY s.side,s.name''',(patient_folder.name,)).fetchall()
    return [dict(r,folder=patient_folder/r['side']/r['name'],label=f"{r['side']} / {r['name']}") for r in rows]


def combine_data(scans: list[PatientData], patient_folder: Path) -> PatientData:
    if not scans:
        raise ValueError('Select at least one sequence with saved masks.')
    if len({s.frame_size for s in scans})!=1:
        raise ValueError('Selected sequences have different image sizes. Verify their crop and pixel spacing before combining.')
    tables=[];poses=[];offset=0
    for scan in scans:
        if not scan.matches.has_mask.any():
            raise ValueError(f'{scan.root.name} has no eligible saved masks.')
        name=f'{scan.root.parent.name}/{scan.root.name}'
        ids=sorted(set(scan.poses.FrameIndex.astype(int)) | set(scan.matches.FrameIndex.astype(int)))
        mapping={old:offset+i+1 for i,old in enumerate(ids)}
        for original,target in ((scan.matches,tables),(scan.poses,poses)):
            table=original.copy()
            table['sequence']=name
            table['source_frame_index']=table.FrameIndex.astype(int)
            table['frame_label']=[f'{name} · frame {i}' for i in table.source_frame_index]
            table['FrameIndex']=table.FrameIndex.map(mapping)
            target.append(table)
        offset+=len(ids)
    first=scans[0]
    return PatientData(patient_folder,patient_folder,first.masks_dir,first.pose_file,
        pd.concat(poses,ignore_index=True),pd.concat(tables,ignore_index=True),first.frame_size,
        f'{len(scans)} sequences combined: ' + '; '.join(sorted({s.label_source for s in scans})),None)


def load_collection(folders: list[Path], patient_folder: Path) -> PatientData:
    return combine_data([load_patient(folder) for folder in folders],patient_folder)
