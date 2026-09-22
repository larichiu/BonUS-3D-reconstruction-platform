# Release preparation — 2026-09-20

## Update — 2026-09-21

- Main platform page now includes a drag-and-drop ZIP box and Browse files; choosing a file automatically selects uploaded data.
- LCedit v2 navigation adds Focus bone, explicit zoom-in/out, 15-degree rotation/tilt/roll buttons, and Fit all / reset. Focus bone excludes distant tracker decorations from the viewing bounds. Display changes do not alter reconstruction coordinates or exports.
- 2D views now explicitly direct users to Reconstruction for 3D rotation.

- Included the original application and three discovered LCedit variants (v1, v1.1, v2).
- Kept independent geometry implementations and existing variant regression suites.
- Added one deployable entry point with a version selector and session-state reset on version/data changes.
- Replaced workstation-specific source paths with environment configuration and bundled sample defaults.
- Added a portable local-mask route, including multi-sequence loading without the annotation database.
- Added baseline Euler controls while retaining each variant's development defaults.
- Added session-isolated ZIP upload with path, size, naming, mask and tracking validation.
- Added a 36-frame sawbone subset and downloadable template ZIP.
- Added About, development brief, source/data guide, calibration equations, contribution wording and deployment instructions.
- Added Git ignore rules, Docker setup, GitHub Actions and release integration tests.

## Preserved source branches

- Original: tracked boundary reconstruction and visualization.
- LCedit v1: u/v rotation exploration, paired coordinate and matrix exports.
- LCedit v1.1: v1 plus image/mask mirroring, provenance and source-pixel correspondence.
- LCedit v2: baseline geometry plus full boundary-pixel inspection and exports.

These entries summarize source behavior; they do not assign invented historical release dates. Expired remote tunnel addresses, credentials, private run inventories, caches, virtual environments and generated full-data mirrors are not part of this release.
