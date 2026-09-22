# Upload and analyze your own segmented ultrasound

## Required inputs

1. Cropped ultrasound images as PNGs, all at the same size within a sequence.
2. Corresponding **binary grayscale PNG masks**, 0 for background and 255 for foreground, aligned pixel-for-pixel with each image. Export a single target label from multi-class masks. Some images may have no mask; they contribute tracking but no bone points.
3. One synchronized tracking row per image, with probe and reference translations in millimetres and quaternions in `w,x,y,z` order.
4. Your acquisition-specific pixel spacing, probe-marker-to-image-origin offset and image-axis calibration. Enter these in Geometry; see the calibration guide for the fixed baseline orientation in each version.

Images and masks alone cannot produce this tracked reconstruction. If reference compensation is intentionally disabled, identity reference poses can be supplied (`0,0,0,1,0,0,0`) and the checkbox must be disabled in Geometry. This changes output to tracker coordinates; it does not recover missing physical reference measurements.

## ZIP layout

Put the dataset folder at the ZIP root, with no extra enclosing directory:

```text
MY_DATASET/
  right/
    sequence_000/
      frames/
        frame_000000.png
        frame_000004.png
      masks/
        frame_000000.png
        frame_000004.png
      sequence_000.xlsx
```

More `sequence_*`, side and dataset folders may be included. Use letters, digits, underscores, hyphens and spaces in folder names. Filenames must follow `frame_<integer>.png` exactly and mask basenames must equal the corresponding image basenames. Nonconsecutive frame IDs are allowed.

Download the bundled sample ZIP to see a working example. Compress the dataset folder itself, not a folder containing it. Only PNG and XLSX files in this structure are accepted. Limits: 100 MB compressed, 300 MB uncompressed, 5,000 archive entries. Use configured local data for larger datasets.

## Tracking workbook

Create the worksheet **`Frame_NDI_Sync`** with these columns:

| Columns | Meaning |
|---|---|
| `FrameIndex` | Unique nonnegative integer equal to the image filename's numeric suffix |
| `FrameFile` | Relative path, e.g. `frames/frame_000004.png` |
| `Prob_1, Prob_2, Prob_3` | Probe-marker X, Y, Z translation in mm |
| `Prob_4, Prob_5, Prob_6, Prob_7` | Probe quaternion w, x, y, z |
| `Ref_1, Ref_2, Ref_3` | Reference-marker X, Y, Z translation in mm |
| `Ref_4, Ref_5, Ref_6, Ref_7` | Reference quaternion w, x, y, z |

Both poses must describe marker-to-tracker transforms at the image acquisition time. Perform synchronization before upload; this interface does not synchronize raw tracker logs or estimate missing poses. Do not rename acquisition indices without updating both image filenames and workbook rows. Do not infer image-to-probe calibration from the reference quaternion.

## Workflow

1. Drag the archive into **Upload your ultrasound dataset**, or click **Upload / Browse files** and select it. The uploaded-data source is selected automatically. Validation checks paths, format, IDs, finite poses, nonzero quaternions, image/mask sizes and binary mask encoding.
2. Review the validated sequence counts and select a dataset, side and sequence.
3. Check the image-mask overlay in **Data review**.
4. Set spacing and tip offsets in **Geometry**. Verify origin, image axes, handedness and quaternion convention with your acquisition setup.
5. Inspect the calibrated path and image planes before interpreting the reconstructed cloud.
6. Use Original for baseline reconstruction, v1 for u/v comparison, v1.1 for deliberate image+mask mirroring, or v2 for pixel-level analysis.
7. Export points, matrices or pixel CSVs using the controls available in that version. Download before closing the session.

The method uses the **uppermost foreground pixel per populated image column**. It does not reconstruct every foreground voxel or an entire filled mask volume. Confirm this boundary definition represents the bone surface you intend to study.

Combining sequences requires a common fixed reference and consistent calibration. The right-side sequence_000/001/002 anatomical labels in v1.1 reflect the original scan-start convention (medial/apex/lateral); they are not inferred anatomical labels for arbitrary uploads.

## Upload lifecycle

Uploads are stored in a separate temporary directory per session on the server. A successfully replaced upload removes the previous upload directory. Cleanup on session/process termination follows Python temporary-directory lifecycle and is not a guaranteed immediate-retention policy. The application does not write uploads into Git or the original annotation database. A host administrator can access server files; use an appropriately controlled deployment for private data.

## Common problems

- **Frame mismatch:** align filenames, FrameIndex and FrameFile exactly.
- **Empty reconstruction:** inspect foreground masks, selected frame range and pose validity.
- **Mirrored or rotated anatomy:** check calibration and pixel-origin conventions, not just the viewer camera.
- **Separated combined scans:** check whether the reference marker moved between scans.
- **Cannot reach localhost:** start the server and use its displayed port. Localhost addresses point to the computer running your browser.
