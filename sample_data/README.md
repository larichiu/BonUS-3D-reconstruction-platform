# Sawbone example

This is a real subset selected from the existing `sawbone/right` annotation workflow at the user's request, not synthetic ultrasound. It contains **36 cropped images, 36 masks and 36 synchronized pose rows**, with 12 evenly spaced eligible frames from each of `sequence_000`, `sequence_001` and `sequence_002`.

Only rows with saved masks and finite probe/reference pose values were selected. Original frame indices are retained. The subset spans each scan but is sparse; it should not be used to assess surface completeness or reconstruction accuracy.

Images were re-encoded without image-file metadata, with pixel content retained. Masks were normalized to grayscale 0/255 using the existing app's foreground interpretation (alpha for RGBA, threshold >127). No additional segmentation or interpolation was performed. Workbooks retain only FrameIndex, FrameFile and the required Prob/Ref fields; FrameFile values point to the packaged images. The JSON manifest records saved status and pixel hashes.

The directory name identifies this as the user's sawbone phantom example. This packaging operation did not independently verify acquisition provenance. No numbered-patient dataset, annotation database or complete acquisition collection is included.

Download `sawbone_sample.zip` and upload it unchanged to test the portable-data workflow. Its top-level folder is `sawbone/`. `manifest.json` and this README remain outside the upload ZIP.

Suggested first example: select LCedit v2, review sequence_000, inspect Geometry and Pixel analysis, then compare the same dataset in v1 and v1.1. Default calibration reflects the development setup and remains provisional. Redistribution rights are retained by the data owner; no separate data license is assigned by this package.
