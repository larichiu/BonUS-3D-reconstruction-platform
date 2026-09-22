# Upload this package to GitHub

## With GitHub Desktop (no terminal required)

1. Extract `bone-reconstruction-platform-github.zip`.
2. Install/open GitHub Desktop and sign in to your GitHub account.
3. Choose **File → New repository**. Name it `bone-reconstruction-platform` and choose a local folder. Create the repository.
4. Open that new repository folder. Copy **everything inside** the extracted `bone-reconstruction-platform` folder into it. Include `.github`, `.streamlit` and `.gitignore`. `README.md`, `requirements.txt` and `streamlit_app.py` must be directly at the repository root, not inside an extra nested folder. Do not upload only the ZIP.
5. In GitHub Desktop, review the changes. Enter `Initial platform release` as the summary and click **Commit to main** (or the default branch shown).
6. Click **Publish repository**, choose public/private visibility, then publish.
7. Open the GitHub repository and confirm README.md, streamlit_app.py, variants/, docs/ and sample_data/ appear at the top level. The Actions tab will show the automated tests once they run.

Official guide: https://docs.github.com/en/desktop/overview/creating-your-first-repository-using-github-desktop

## Make the interactive platform accessible online

GitHub stores the source. A Streamlit deployment runs the web application.

1. Open https://share.streamlit.io/ and connect your GitHub account.
2. Create an app and select this repository and its published branch.
3. Set **Main file path** to `streamlit_app.py`.
4. In advanced settings, select Python **3.12**.
5. Click **Deploy** and wait for installation/startup.
6. Open the assigned app URL. Verify the sawbone example and upload workflow, then share that URL with users and add it to the GitHub Website field.

All four versions are available from one app through the sidebar. The repository includes a sawbone example so the hosted app does not require access to the original workstation. No hosted URL is created merely by downloading this archive.

Official guide: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy

See docs/PUBLISHING.md for command-line and Docker alternatives; README.md for local startup; docs/DATA_GUIDE.md for preparing users' own data; RIGHTS.md for the unassigned code and example-data licensing status.
