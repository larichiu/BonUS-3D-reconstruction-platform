# Calibration and coordinate conventions

The preserved variants start with pixel spacing `0.05392 mm/pixel` on both axes, probe-marker-to-tip offset `[-163.326, -19.6482, -206.473] mm`, horizontal and depth flips enabled, and provisional baseline Euler angles `(45°, -90°, 0°)`. These values reproduce the development setup; they are not measured calibration for another scanner or dataset.

The release sidebar exposes baseline Euler angles for other calibrated setups, retaining the original defaults. Geometry contains spacing, tip offsets and axis flips. Changing any of these changes exported coordinates. The image origin remains cropped pixel `(0,0)`; if your calibrated origin is elsewhere, convert your image-origin offset into the equivalent marker-to-cropped-top-left offset first.

## Transform

For a cropped-image pixel `(u,v)`, spacing `(s_u,s_v)`, image basis `(b_u,b_v)` and marker-to-origin offset `t`:

```text
p_probe = t + (u*s_u)*b_u + (v*s_v)*b_v
p_tracker = R_probe @ p_probe + t_probe
p_reference = R_reference.T @ (p_tracker - t_reference)
```

Translations and outputs use millimetres. NDI quaternion fields are `w,x,y,z`; the quaternion defines the marker-to-tracker rotation. Baseline rotation is `Rz @ Ry @ Rx`, applied to the original local X and Z image directions; the configured flips change their signs.

With reference compensation disabled, output is `p_tracker`. With it enabled, output is relative to the reference marker at that frame. The viewer camera does not change either coordinate system.

## LCedit variants

V1 applies `R_v(v_angle) @ R_u(u_angle)` about the fixed baseline image basis, pivoting around the calibrated tip. The tip offset and tracker poses remain unchanged. Zero u/v angles mean the selected baseline, not necessarily the development baseline if the release controls were changed.

V1 exports a rigid homogeneous matrix:

```text
[x,y,z,1]^T = T @ [u*s_u, v*s_v, 0, 1]^T
```

V1.1 first mirrors image and mask columns using `u_mirror = width-1-u_source`. This pixel reflection differs from reversing a local image axis. It exports both the mirrored-pixel transform and `SourcePixel_T`, which includes reflection and spacing and operates directly on original pixel coordinates.

V2 retains the selected baseline without v1's additional u/v rotations. It exports all upper-boundary pixels, regardless of reconstruction subsampling, range or outlier-filter controls. Each pixel's distance to the synchronized tip is `norm(pixel_xyz-tip_xyz)`. Rotation about the tip preserves this distance, so these distances alone cannot establish the correct image orientation.

## Verification with your acquisition

Check pixel scale and crop origin, pose timestamps, quaternion order, units, marker-to-image transform and signs against known physical motion or landmarks. Confirm reference attachment did not change when combining scans. A plausible-looking point cloud is insufficient evidence of correct calibration. The software does not solve a calibration optimization problem, estimate synchronization, or register independently moving scans.
