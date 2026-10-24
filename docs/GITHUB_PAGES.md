# Publish the browser dashboard with GitHub Pages

GitHub Pages serves the browser-only dashboard in `web/`. It displays a validated snapshot of the same saved experiment results as Streamlit. Model/horizon/split selection, historical replay, comparisons, equal-margin allocation and CSV downloads run in JavaScript. It does not train neural models, measure live traffic or generate new forecasts. The Python training and Streamlit implementation remain available locally.

## Publish

1. Commit and push `.github/workflows/pages.yml`, `web/`, the two Pages Python scripts, `DATA_ATTRIBUTION.md`, and this documentation. The `results/` and raw-data directories stay ignored.
2. Open the repository on GitHub. Go to **Settings → Pages**.
3. Under **Build and deployment**, set **Source** to **GitHub Actions**.
4. Open **Actions → Deploy traffic dashboard to GitHub Pages**. Run the workflow on `main` if it has not started from your push.
5. When the deployment succeeds, open the URL reported by the deployment. The expected project URL is:

   `https://w-s-m-007.github.io/Internet-Traffic-Forecasting-for-Intelligent-Bandwidth-Prediction/`

The workflow builds `_site/` from the tracked snapshot and deploys only that directory. It needs no Python package installation, training job, external chart CDN or secret token. GitHub supplies the workflow deployment credentials. Keep the site's asset links relative so the repository path works.

The site offers result CSVs and dataset attribution. The research report, presentation and viva guide are excluded from the published site. Rebuilding an existing `_site/` also removes the four document downloads produced by older builds; the original project documents remain in their project folders.

GitHub instructions: https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site and https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages.

## Local preview

From the project root in Git Bash:

```bash
python -m scripts.build_pages
python -m http.server 8000 --directory _site --bind 127.0.0.1
```

Open http://127.0.0.1:8000/. Use an HTTP server rather than double-clicking `index.html`, because browsers restrict local-file JSON fetches. The existing virtual environment works; building needs only the Python standard library.

## Update the published results

After intentionally regenerating and verifying the experiment:

```bash
source VirtEnv/Scripts/activate
python -m scripts.export_pages
python -m scripts.build_pages
node scripts/check_pages.mjs
```

The exporter requires the existing dashboard dependencies because it uses the same artifact validation as Streamlit. It reads saved results, checks all predictors and allocation provenance, then exports a compact public snapshot into `web/data/`. Commit that snapshot to publish updates. Publishing never tries to retrieve ignored result files from GitHub.

`web/data/manifest.json` binds the exported files by SHA256 and records forecast-source hashes. Public JSON uses UTF-8 with LF endings; validation normalizes CRLF to LF so Git line-ending conversion does not cause Windows/Linux checksum mismatches. Building still fails if the data changes without regenerating the manifest. The published snapshot contains recorded rates, forecasts, UTC timestamps and aggregate scores, with dataset attribution. No checkpoints, raw archives, local environments or credentials are deployed.

## If deployment fails

- **Pages not enabled / Get Pages site failed:** set Settings → Pages → Source to GitHub Actions, then rerun the workflow.
- **Permission or environment error:** check that GitHub Actions is enabled and that the `github-pages` environment permits the `main` branch. The deploy job already requests `pages: write` and `id-token: write`.
- **Missing dataset attribution:** commit `DATA_ATTRIBUTION.md`; the builder includes it for the published data's source and license. Report, slide and viva files are not required for a Pages build.
- **Changed static export:** rerun the validated exporter locally, then commit its JSON files together.
- **404 immediately after deployment:** use the exact deployment URL including the repository name and wait for the successful Pages deployment, rather than opening the account root.
