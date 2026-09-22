# Possible contribution statements

These are candidate descriptions of implemented capabilities. They are not verified priority claims. Avoid “first”, “novel calibration algorithm” or “improves accuracy” without a literature comparison and appropriate experiment.

## A — Traceable reconstruction workflow

**“We present a web-based workflow that links segmented ultrasound bone-boundary pixels to tracked 3D coordinates, with per-frame transformation exports for inspecting the reconstruction chain.”**

Best fit: emphasize reproducibility and inspectability. Evidence: image/mask correspondence, tracking identifiers, XYZ, matrix exports and reference-frame metadata. Evaluate reconstruction against known phantom geometry and audit reproducibility from exported transforms.

## B — Interactive calibration exploration

**“The platform supports interactive exploration of image-plane calibration by applying controlled rotations around the tracked probe tip while preserving the underlying tracking data and reporting baseline and adjusted coordinates.”**

Best fit: emphasize LCedit v1. It is manual exploration, not an automatic calibration solver. Evaluate recovery of known injected orientation offsets and user performance versus a conventional viewer.

## C — Mirror-aware correspondence

**“We provide a mirror-aware reconstruction workflow that transforms ultrasound images and segmentation masks together, preserving the mapping from original pixels to derived 3D points.”**

Best fit: emphasize LCedit v1.1. Evidence: mirrored copies, provenance, source/mirrored pixel coordinates and source-pixel transforms. Evaluate correspondence correctness and whether explicit tracking of mirroring prevents interpretation errors.

## D — Pixel-level geometric inspection

**“The platform exposes the 3D position and probe-tip distance of each segmented upper-boundary pixel, enabling detailed inspection of how image segmentation and tracking contribute to bone reconstruction.”**

Best fit: emphasize LCedit v2. Distances are derived from the supplied calibration; they are not independent measurements. Evaluate known synthetic poses and calibrated phantom landmarks.

## E — Integrated research platform

**“We developed an integrated web platform for calibration exploration and segmentation-based 3D ultrasound bone reconstruction, combining image-mask review, tracked probe visualization, mirror-aware processing and auditable coordinate exports.”**

Best fit: an overall thesis/software contribution. The features exist across selectable variants rather than all in one combined processing mode. A defensible claim is integration of these capabilities; methodological novelty remains to be established.

## Suggested concise description

**“A traceable web platform for calibration exploration and 3D reconstruction of segmented, tracked ultrasound bone boundaries.”**

No literature novelty review or new accuracy study was performed in preparing this software release. Choose the framing that matches the experiments you plan to report.
