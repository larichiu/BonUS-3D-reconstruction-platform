# Publish the source and run the website

## GitHub repository

Create an empty repository in your own account, then run these commands from the extracted release folder (replace OWNER/REPOSITORY):

```bash
git init
git branch -M main
git add .
git commit -m "Add bone reconstruction platform and LC variants"
git remote add origin https://github.com/OWNER/REPOSITORY.git
git push -u origin main
```

Suggested repository name: `bone-reconstruction-platform`.

Suggested GitHub About text:

> Web platform for calibration exploration and segmentation-based 3D ultrasound bone reconstruction, with LC variants, sawbone sample, ZIP upload and traceable coordinate exports.

Suggested topics: `ultrasound`, `bone-reconstruction`, `calibration`, `segmentation`, `streamlit`, `3d-reconstruction`.

Before a public release, the owner must choose appropriate code and sample-data licensing. No license grant was inferred in preparing this package. The included sawbone subset is deliberate; private annotation databases, credentials, logs and derived full scans are excluded.

## Streamlit Community Cloud

1. Push the repository to GitHub.
2. Create an app in Streamlit Community Cloud and select your repository and branch.
3. Set the entry point to **`streamlit_app.py`**, at the repository root.
4. Select Python **3.12** in advanced settings.
5. Deploy. The root `requirements.txt` installs the tested direct dependency versions.
6. Open the assigned app URL. Test the sample, each version, the About page, and a sample ZIP upload.
7. Add the deployed URL to GitHub's Website field and to this README after verifying it.

All four versions share this one URL and the sidebar selector. Cloud hosting cannot access the original workstation's D: drive. The bundled sample and uploaded ZIPs are the portable inputs. Treat uploads as temporary and download results promptly. Hosting and access controls must match the data being used.

Official references: [deployment steps](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy), [repository file organization](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization).

## Docker

```bash
docker build -t bone-reconstruction .
docker run --rm -p 127.0.0.1:8501:8501 bone-reconstruction
```

Then open http://127.0.0.1:8501. A remote host needs its own network route, TLS and access control. No authentication gateway or temporary tunnel credentials are included. See [Streamlit's Docker guide](https://docs.streamlit.io/deploy/tutorials/docker).

## What is and is not published

The repository is source plus an example, not a hosted application by itself. GitHub Pages does not run this Python server. The original localhost links work only when a server runs on that computer. This prepared package has not been pushed to GitHub or deployed to a hosting account.
