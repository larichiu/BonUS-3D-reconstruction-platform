# lc_v2

Launch from the repository root: `python launch.py --variant lc_v2`. See [root README](../../README.md).

## Pixel analysis

Select a patient/sequence or a combined selection, then open **Pixel analysis**.
Choose an original frame and a boundary image column. The image overlay marks
the inspected pixel, and the platform shows XYZ and distance from the calibrated
probe tip. Coordinates are derived from synchronized tracking and the original
calibration; they are not independent measurements of pixel locations.

Per the requested export scope, each row is the uppermost foreground mask pixel
in one populated image column. Interior mask pixels are not included. All boundary
columns and all saved masked frames are eligible, irrespective of reconstruction
sample step, frame step, frame range, or outlier filter.

- **Download this frame · boundary pixels CSV** exports one selected frame.
- **Build all-frame boundary CSVs (ZIP)** creates one CSV per masked frame in the
  selected sequences, plus `frame_manifest.csv` and explanatory notes.
- Invalid/missing tracking is reported explicitly in the manifest. Frames with
  invalid poses are skipped; empty masks are distinguished from skipped frames.

Columns include zero-based `pixel_u,pixel_v`, pixel `x_mm,y_mm,z_mm`, calibrated
probe-tip XYZ, tip-to-pixel ΔXYZ, Euclidean `distance_from_probe_tip_mm`, patient,
sequence, frame identifiers, mask status, spacing and coordinate frame. Source
acquisition identifiers are retained when provided by the workbook. Pixel indices
refer to saved cropped images; they are not uncropped acquisition-image indices.

Distances compare each pixel with the tip at that frame's synchronized tracking
pose, in the same coordinate system and in millimetres:

```
distance = sqrt((x - tip_x)^2 + (y - tip_y)^2 + (z - tip_z)^2)
```

A rigid rotation around the calibrated tip changes XYZ but preserves the distance
to that tip. These distances therefore cannot independently diagnose the orientation
error. The baseline cropped top-left origin and X=45°, Y=−90° provisional orientation
remain unchanged from the original platform.

The manifest also records T_00 through T_33, the row-major matrix used with column
vectors to map `[pixel_u*spacing_u_mm, pixel_v*spacing_v_mm, 0, 1]` to output XYZ.
The viewer's display-camera orientation does not alter exports.

