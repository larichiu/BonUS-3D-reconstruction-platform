# Input data and where they come from

## Development installation

The original application used these local sources:

| Input | Original source | Purpose |
|---|---|---|
| Reduced/cropped ultrasound frames | `D:\McGill\Ultrasound\Bonus_Dataset\reduced_recordings` | Image pixels and frame identity |
| Annotation records | `D:\McGill\Ultrasound\app_annotation_051.db` | Match sequences, images, annotators and saved mask status |
| Saved mask files | `D:\McGill\Ultrasound\annotations` | Foreground bone/shadow segmentation from the annotation workflow |
| Tracking workbooks | Sequence folders under the reduced-recordings root | `Frame_NDI_Sync` rows with probe and reference poses |

The application does not retrieve these from GitHub or the internet. It reads local files. The prepared-platform adapter reads the database in read-only mode. The prepared tracking route accepts saved `accepted` and `propagated` masks, including a saved mask on a skipped frame; older fallback adapters select accepted masks. Multiple annotators for the same prepared frame cause an error rather than a silent choice.

In a prepared sequence, `sequence_tracking` points to the reduced workbook, and `full.xlsx` supplies the full probe trajectory. Matching checks use annotation frame IDs, source indices and frame paths; another adapter can match image contents. These checks matter because reduced frame numbering need not equal original acquisition numbering.

## Portable release

The default source is `sample_data/sawbone/right/sequence_*` inside the repository. It needs no database. Each sequence has `frames/`, `masks/` and a matching XLSX. The release uses local masks in preference to database lookup when `masks/` exists. Local uploaded masks are user-supplied, not automatically certified as accepted annotations.

The sample is derived only from the explicitly requested sawbone folders, not from numbered patient folders. Images are re-encoded without source file metadata; masks are converted to binary grayscale using the original reader's alpha/threshold interpretation. Tracking retains only the required columns. The manifest records sequence, frame ID, saved status and pixel hashes without source-machine absolute paths. Acquisition provenance is supported by the selected sawbone directory; no independent acquisition-record audit is claimed.

## Configure an existing annotation installation

Set these before starting the server, then select **Configured local data**:

```powershell
$env:BONE_DATA_ROOT = 'D:\McGill\Ultrasound\Bonus_Dataset\reduced_recordings'
$env:BONE_ANNOTATION_DB = 'D:\McGill\Ultrasound\app_annotation_051.db'
$env:BONE_ANNOTATION_ROOT = 'D:\McGill\Ultrasound\annotations'
python launch.py
```

The adapter retains the original `reduced_recordings` directory convention and expects the companion database schema. It is not a generic SQLite annotation importer. Copying only the database is insufficient: its referenced masks, frames, reduced workbooks and `full.xlsx` must remain accessible. For unrelated segmentation tools, export the portable ZIP format instead.

The separate annotation web application, trained weights and full data collections are not included. The reconstruction package includes the code needed to consume masks and tracking, not to reproduce the original mask-generation model.

## Data flow

`ultrasound image + corresponding saved mask → upper boundary pixels → pixel spacing and image basis → probe-marker-to-tip offset → tracked probe transform → optional inverse reference transform → 3D cloud and exports`

The probe path comes from tracking independently of masks. An uploaded sequence supplies only the tracking rows in its own workbook; the small sample therefore has a sparse path. V1.1 additionally creates derived mirrored images/masks and records their correspondence to original pixels.
