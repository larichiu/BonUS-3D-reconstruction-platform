# lc_v1

Launch from the repository root: `python launch.py --variant lc_v1`. See [root README](../../README.md).

## Image rotation

In **Geometry → Image-plane rotation**, adjust u and v in degrees:

- **u**: rotation about the baseline lateral/image-right direction.
- **v**: rotation about the baseline longitudinal/image-depth direction.
- Both pivot about the calibrated probe tip, currently the cropped top-left image origin.
- Positive angles use the right-hand rule. First rotate about u, then about v.
  Both rotation axes are fixed in the baseline image basis (extrinsic rotations).
- Zero/zero preserves the original provisional X=45°, Y=−90°, Z=0° mapping,
  including the current horizontal/depth flips.

The adjustment is `R_v(v_angle) @ R_u(u_angle)` in probe-marker coordinates.
The same adjusted image basis is used by bone points, original image planes,
the calibration visualization, and exports. Probe tracking and tip offset are not
rotated by these controls. This allows manual exploration; it does not estimate
calibration from independent measurements.

## CSV exports

In **Reconstruction**, select **Build calibrated CSV exports**. Two downloads appear:

1. Coordinate CSV: existing `x,y,z`, `original_x_mm,original_y_mm,original_z_mm`,
   `new_x_mm,new_y_mm,new_z_mm`, pixel `u,v`, frame identifiers, rotations,
   spacing, coordinate frame, and `T_00` through `T_33`.
2. Matrix CSV: one transformation record per exported frame.

`x,y,z` equal the new coordinates. Original coordinates use the same pixels,
tracking, spacing, tip offset, flips, and baseline orientation with only the added
u/v adjustments set to zero. Comparison rows use the rotated reconstruction's
selected/sampled/filtered point set; they are not an independently filtered original cloud.

T is a rigid 4×4 homogeneous transform, with row-major column names and column-vector use:

```
[x_mm, y_mm, z_mm, 1]^T = T @ [u * spacing_u_mm, v * spacing_v_mm, 0, 1]^T
```

Its first two rotation columns are the adjusted lateral and depth unit vectors
in output coordinates; its third is their cross product. Its translation is the
calibrated tip in output coordinates. Scaling is applied to pixel coordinates
before T. All XYZ values use the exported `coordinate_frame` (`leg_reference`
or `NDI_tracker`), independent of the viewer's display-camera orientation.

With reference compensation enabled:

```
T.rotation = R_reference.T @ R_probe @ [u_basis, v_basis, cross(u_basis,v_basis)]
T.translation = R_reference.T @ (p_probe + R_probe @ tip_offset - p_reference)
```

