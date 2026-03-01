# Rastion Hub

Rastion Hub is an Astro + FastAPI app for publishing and browsing community decision plugins.

## Stack

- Astro static site generator
- Fontshare fonts: Clash Display + Satoshi
- GitHub Pages deployment via GitHub Actions

## Local development

```bash
npm install
npm run dev
```

The app is served with a repository base path (default: `/rastion-hub`).

## API runtime config

`api/` supports environment-driven configuration for production:

- `DATABASE_URL` (default: local SQLite file)
- `ARCHIVE_BACKEND` (`filesystem` or `db`, default: `filesystem`)
- `RASTION_HUB_STORAGE_DIR` (default: `api/storage`, used with `ARCHIVE_BACKEND=filesystem`)
- `MAX_UPLOAD_BYTES` (default: `26214400`)
- `MAX_ZIP_ENTRIES` (default: `2000`)
- `MAX_ZIP_UNCOMPRESSED_BYTES` (default: `262144000`)
- `CORS_ALLOW_ORIGINS` (comma-separated)

## Render Setup (API)

Use these settings for the FastAPI service in Render:

- Runtime: `Python`
- Root Directory: `api`
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

Required env vars:

- `JWT_SECRET`
- `GITHUB_CLIENT_ID`
- `GITHUB_CLIENT_SECRET`
- `CORS_ALLOW_ORIGINS`

### Free plan (recommended config)

Free web services do not provide persistent disks. Use database-backed archive storage:

- `DATABASE_URL=<your postgres connection string>`
- `ARCHIVE_BACKEND=db`

Notes:

- This stores uploaded ZIP payloads inside the database (`archive_blobs` table).
- Do not use SQLite on free instances if you need data persistence across deploys/restarts.

### Paid plan (filesystem config)

If you have a persistent disk attached:

- `ARCHIVE_BACKEND=filesystem`
- `RASTION_HUB_STORAGE_DIR=/var/data/storage` (or your mount path)
- `DATABASE_URL=<postgres connection string>`

## Build

```bash
npm run build
npm run preview
```

## Deploy to GitHub Pages

1. Push to the `main` branch.
2. In GitHub repo settings, set **Pages** source to **GitHub Actions**.
3. Workflow `.github/workflows/deploy.yml` builds and publishes automatically.
4. Your site will be available at `https://<username>.github.io/rastion-hub/`.

## Project structure

```text
rastion-hub/
├── src/
│   ├── layouts/
│   │   └── Layout.astro
│   ├── pages/
│   │   ├── index.astro
│   │   ├── decision-plugins.astro
│   │   └── ...legacy redirect routes
│   └── components/
│       ├── Header.astro
│       ├── Footer.astro
│       ├── ThemeToggle.astro
│       ├── DecisionPluginCard.astro
│       ├── SolverCard.astro
│       └── Card.astro
├── public/
│   └── favicon.svg
├── astro.config.mjs
├── package.json
└── README.md
```
