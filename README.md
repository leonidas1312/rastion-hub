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
