# lc_v1_1

Launch from the repository root: `python launch.py --variant lc_v1_1`. See [root README](../../README.md).

## mirror

The command is named **mirror**. It horizontally flips BOTH the ultrasound image
and its matching annotated mask before reconstruction, saving separate lossless PNGs.
The original image, mask, annotation database, tracking poses, and calibrated tip
are unchanged. Pixel mapping: `u_new = width - 1 - u_original; v_new = v_original`.

In the platform, click **mirror** in the sidebar to create or refresh the derived
series for the current selection. V1.1 also prepares these copies automatically
when loading a sequence. It always starts from original files: repeated calls reuse
verified copies or refresh changed inputs, and never mirror an already mirrored series.

From this folder, the command-line equivalent is:

```bash
python -m variants.lc_v1_1.mirror path/to/dataset/right/sequence_000
```

Pass multiple original sequence folders to process several sequences.

## Saved series

Mirrored outputs are generated locally and excluded from Git. Each series contains images, masks, mirror_manifest.csv and mirror_provenance.json.

## Preview and geometry

**Data review** shows the mirrored image with the mirrored mask, with an expandable
original comparison. **Geometry** retains V1's u/v rotation controls and per-sequence
sample frames, now using the mirrored file copies. Reconstruction, boundary extraction,
3D image textures, CSVs, and PLYs all consume those same derived files.

The existing image-axis direction settings are preserved. Reversing an axis about
the calibrated origin and reflecting pixel columns about the image center are
separate operations; the new file mirror is applied exactly once.

For a right tibia, using the user's scan-start convention:

- sequence_000: medial / left.
- sequence_001: apex / middle.
- sequence_002: lateral / right.

The optional scan-start camera looks along sequence_000 probe travel and uses the
medial-to-lateral start positions to define screen-right. This changes the camera,
not the reconstructed coordinates. If the apex start is not between the medial and
lateral starts, the platform reports the calibration/alignment mismatch rather than
inventing a translation, rotation, registration, or anatomical shape. Both medial
and lateral sequences are needed to establish this camera convention.

## Export conventions

`u,v` now identify the mirrored pixels; `source_u,source_v` identify their original
pixels. `unmirrored_x_mm,y_mm,z_mm` (axis-named columns) show corresponding unmirrored
positions under the same current calibration. `original_x_mm`, etc. retain V1's
meaning of baseline u/v angles set to zero, now applied to mirrored pixels.
`new_x_mm`, etc. equal the exported reconstruction XYZ.

`T_00` ... `T_33` still maps mirrored image millimetres to output XYZ:

```
[x,y,z,1]^T = T @ [u*spacing_u_mm, v*spacing_v_mm, 0, 1]^T
```

`SourcePixel_T_00` ... `SourcePixel_T_33` additionally includes pixel spacing and
reflection, and maps ORIGINAL pixel coordinates directly to the mirrored result:

```
[x,y,z,1]^T = SourcePixel_T @ [source_u, source_v, 0, 1]^T
```

