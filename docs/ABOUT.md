# About this platform

## What it does

The platform connects annotated ultrasound to tracked 3D reconstruction. For each image, it finds the superficial mask boundary, converts its pixel coordinates to millimetres, applies image-to-probe geometry and the tracked probe pose, and optionally compensates for the tracked reference marker. It lets the user compare the resulting bone points, original image planes, and calibrated probe-tip path.

It supports inspection of segmentation results rather than segmentation generation: the annotations are supplied as saved masks from another tool or the companion annotation platform.

## Development brief and delivered behavior

This is a reconstructed requirements summary based on the preserved implementation and version documentation, plus the release request. It is not a verbatim transcript or a claim that every historical request was recovered.

| Requested capability represented in the sources | Delivered behavior |
|---|---|
| Build a web interface from ultrasound images, saved masks and NDI tracking | Dataset/side/sequence selection, image-mask review, synchronized reconstruction |
| Understand how calibration affects the reconstructed bone | Probe-marker/tip display, axis conventions, spacing and offset controls, image planes |
| Keep bone and probe movement in a consistent frame | Reference-compensated points and the calibrated probe-tip pathway |
| Compare multiple scans | Combined sequence selection with explicit shared-reference confirmation |
| Explore image-plane rotations without changing tracking | LCedit v1 rotates u/v basis directions about the fixed calibrated tip |
| Keep baseline and changed coordinates inspectable | V1 CSVs contain baseline/new XYZ and per-frame homogeneous transforms |
| Mirror ultrasound and masks together | V1.1 derives lossless mirrored copies, provenance and original-pixel mappings |
| Understand individual segmented pixels in 3D | V2 pixel inspection, distance to tip, full upper-boundary CSVs and a ZIP manifest |
| Share the code, explain the work and let others supply data | This release adds a single version selector, About page, sawbone sample, validated ZIP upload, portable configuration, tests and publishing instructions |

## Version relationships

Original → LCedit v1 → LCedit v1.1 forms the rotation/mirroring branch.
Original → LCedit v2 forms the boundary-pixel-analysis branch.
LC names are retained from the source folders; the expansion of “LC” is not established in the source documentation.

## What the output means

CSV and PLY coordinates are derived from the supplied tracking and calibration. They are not independent measurements of bone geometry. Manual rotation controls permit exploration, not an automatic calibration estimate. Camera rotation changes the viewpoint only. Combined scans do not receive automatic registration, and a moved reference marker invalidates the shared-frame assumption.

## Example and new datasets

The bundled sawbone phantom subset has 36 cropped images, 36 saved masks and 36 corresponding tracking rows across three sequences. Users can download its ZIP structure, replace it with their own synchronized images/masks/poses, upload the result and inspect it using any version. The Upload guide explains required names, columns, units and mask encoding.

## Contribution framing

A defensible present-tense description is: **“An integrated, traceable web workflow for inspecting calibration-dependent reconstruction of segmented, tracked ultrasound bone boundaries.”** This describes the implemented system. Establishing research novelty or improved accuracy requires comparison and evaluation; the software tests alone do not establish either.
