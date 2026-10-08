# Arian NDS AI — GitHub Pages Dashboard

This is the static/mobile dashboard shell for the Arian NDS AI project.

## Publish on GitHub Pages
1. Create a **public** GitHub repository, e.g. `arian-nds-ai-dashboard`.
2. Upload `index.html` and `.github/workflows/pages.yml`.
3. In GitHub: Settings → Pages → Source: GitHub Actions.
4. Wait for the workflow to finish. The site will be available at:
   `https://YOUR_USERNAME.github.io/arian-nds-ai-dashboard/`

## Important
GitHub Pages hosts the frontend only. It cannot run the Python/FastAPI trading agent. The dashboard therefore expects an API endpoint configured in `index.html` when the backend is deployed.

Real trading is disabled in the project.
