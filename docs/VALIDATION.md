# Validation — updated 2026-09-21

## Environment

A fresh Python 3.12 virtual environment was created on Windows. The pinned requirements installed successfully, and `pip check` reported no broken requirements. pytest 9.1.1 was used for the full suite. These results concern the packaged source, not merely the original running app.

## Automated results

| Suite | Passed | Skipped |
|---|---:|---:|
| Original | 8 | 0 |
| LCedit v1 | 18 | 0 |
| LCedit v1.1 | 23 | 0 |
| LCedit v2 | 13 | 3 |
| Release integration and navigation | 10 | 0 |
| Total | **72** | **3** |

Four variant subtests also passed within the release reconstruction test. The three v2 skips concern v1-only rotation behavior. pytest collects both the inherited unittest classes and standalone geometry test functions.

Coverage includes analytical transforms, reference compensation, boundary extraction, u/v rotation order, mirroring and source preservation, export-matrix equivalence, per-frame boundary ZIP manifests, uploading the sample archive, rejecting traversal and mismatched masks, standalone reconstruction in every variant, single/combined scans, version switching, About rendering and the uploaded-data app path. Streamlit AppTest exercises Python UI execution; the file-uploader return value is supplied in the upload integration test, not automated through an operating-system file picker.

Browser inspection confirmed the deployed local interface loads the sample with matching frame/mask/pose counts and displays its navigation and data review. The application was started at localhost port 8510 for this review. That address is a local preview, not a permanent remote service.

## Known limits

- Streamlit emits a deprecation warning for the inherited `components.v1.html` renderer; the pinned version still renders it. A future dependency upgrade should migrate and retest custom camera controls.
- Linux CI configuration and Docker files are included but were not executed on a Linux runner or Docker engine in this preparation.
- No GitHub push or hosted deployment was performed. Hosted access, browser gestures across devices, concurrent large uploads and resource limits need deployment-specific checks.
- The sawbone subset is sparse and the calibration defaults remain provisional. Software tests do not establish reconstruction accuracy, anatomical validity or research novelty.

Run `python -m pip install -r requirements-dev.txt` and `python scripts/run_tests.py` to reproduce the suite. A failed test makes the test runner return a nonzero exit status.

## 2026-09-21 browser checks

Selected the sample ZIP through the actual browser file chooser and verified automatic source switching, validation and reconstruction. Visually checked Focus bone, Zoom + and a 15-degree rotation on the uploaded sample. The main-page upload box is available without selecting the upload source first.
