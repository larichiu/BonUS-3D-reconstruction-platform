# 3D Bone Reconstruction Platform

A Streamlit research application for inspecting how segmented ultrasound bone boundaries become tracked 3D points. It brings together ultrasound images, saved masks, synchronized probe/reference poses, calibration controls, and traceable exports.

**Included:** the original platform and LCedit v1, v1.1 and v2; a 36-frame sawbone phantom example; ZIP upload; calibration and pixel-analysis tools; an in-app About page; automated checks and deployment files.

This platform consumes existing segmentation masks. It does not train a segmentation model or provide the separate annotation editor. It extracts the uppermost foreground pixel in each populated mask column and maps those boundary pixels into 3D. A displayed surface is a visualization of reconstructed points, not a validated anatomical model.

## Quick start

Use Python **3.12**. From this repository:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe launch.py
```

macOS / Linux:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python launch.py
```

Open **http://127.0.0.1:8501**. The bundled sawbone sample is selected by default. If another app already uses that port, run `python launch.py --port 8510` with your environment's Python. Keep the server process running while using the platform.

## Choose a version

All versions are accessible from the sidebar of the same app and deployed URL. Changing versions clears the current reconstruction and geometry widgets; downloaded exports remain yours to keep.

| Version | Purpose | Distinguishing behavior |
|---|---|---|
| Original | Baseline reconstruction | Boundary points, probe trajectory, image planes, combined scans, CSV/PLY |
| [LCedit v1](variants/lc_v1/README.md) | Explore image-plane calibration | Independent u/v rotations about the calibrated tip; baseline/new XYZ and per-frame transformation matrices |
| [LCedit v1.1](variants/lc_v1_1/README.md) | Explore mirrored inputs | Mirrors images and masks together, retains source-pixel correspondence, and adds anatomical camera conventions; inherits v1 rotations |
| [LCedit v2](variants/lc_v2/README.md) | Inspect boundary pixels | Per-pixel XYZ, distance from probe tip, full boundary exports and frame manifests; retains baseline geometry rather than v1 rotation controls |

V2 is a separate analysis branch, not a superset of v1.1. The repository preserves their separate geometry implementations.

## First walkthrough

1. Keep **Bundled sawbone sample** selected. Choose a sequence and review the ultrasound image and mask.
2. In **Geometry**, inspect spacing, probe-tip offset, axis flips and image orientation. Defaults reproduce the development setup; they are not universal calibration values.
3. Open **Reconstruction** and create or inspect the point cloud and calibrated probe path.
4. Choose **LCedit v1** to compare u/v rotations and download calibrated CSVs and matrices.
5. Choose **LCedit v1.1** to reconstruct mirrored image/mask copies. These are generated separately in a temporary session directory.
6. Choose **LCedit v2** and **Pixel analysis** to inspect a boundary pixel or export all available boundary pixels.
7. To combine scans, select the sequences and confirm a common, fixed reference marker and calibration. This does not register scans automatically.

The small example is intentionally sparse. It demonstrates correspondence and the workflow; it is not a complete scan or an accuracy benchmark.

## Use your own data

Use the **Upload your ultrasound dataset** box at the top of the platform: drag a ZIP onto it or click **Browse files**. Choosing a file automatically switches to that dataset. Follow [the data guide](docs/DATA_GUIDE.md) and download [the sawbone sample ZIP](sample_data/sawbone_sample.zip) as a concrete template. Uploaded data are validated before use and stored in a temporary directory for that server session.

For close inspection in LCedit v2, open **Reconstruction → Focus bone**. Use **Zoom + / −**, **Move**, **Rotate**, or the 15-degree rotation buttons. **Fit all / reset** restores the complete scene. The Data review panel is a 2D image and has no 3D rotation.

For larger local datasets, set `BONE_DATA_ROOT` to a folder containing `DATASET/SIDE/sequence_*` and choose **Configured local data**. The legacy annotation database adapter is also available; see [data sources and integration](docs/DATA_SOURCES.md).

## Publish and access online

Uploading this repository to GitHub shares the source code. A running Streamlit server supplies the interactive website. Use the repository-root entry point **`streamlit_app.py`** when deploying. See [GitHub and hosting instructions](docs/PUBLISHING.md) for Streamlit Community Cloud and Docker options. No remote URL has been created by this release package.

## Documentation

- [About, original development brief and implemented features](docs/ABOUT.md)
- [Input data, source locations and annotation integration](docs/DATA_SOURCES.md)
- [Upload format and analysis workflow](docs/DATA_GUIDE.md)
- [Calibration equations and assumptions](docs/CALIBRATION.md)
- [Possible contribution / novelty statements](docs/CONTRIBUTIONS.md)
- [Version history and release changes](CHANGELOG.md)
- [Validation results and limits](docs/VALIDATION.md)
- [Sawbone sample description](sample_data/README.md)

## Tests

```bash
python -m pip install -r requirements-dev.txt
python scripts/run_tests.py
```

Run with the environment where requirements are installed. Existing tests run separately per variant to isolate their `core` imports. Release tests validate the example archive, upload rejection rules, all four application views, reconstruction, version switching, and calibration exports. See the validation report for actual results.

## Scope and rights

Research calibration and reconstruction exploration only; clinical performance has not been established. Geometry tests establish implementation consistency, not physical calibration accuracy. The original authors retain their rights; this preparation does not assign a new open-source license. See [rights and redistribution](RIGHTS.md) before selecting a repository license. Dependency licenses remain with their respective projects.
