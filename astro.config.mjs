import { defineConfig } from 'astro/config';

const repository = process.env.GITHUB_REPOSITORY?.split('/')[1] ?? 'rastion-hub';
const base = `/${repository}`;

export default defineConfig({
  site: process.env.SITE_URL ?? 'https://username.github.io',
  base,
  trailingSlash: 'always'
});
