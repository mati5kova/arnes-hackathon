# RUN

Operational runbook for local development, preview, and production build checks.

## Prerequisites

- Node.js 18+ (recommended: current LTS)
- npm
- Backend running at `http://localhost:8787` (or set `VITE_API_BASE_URL`)

## Install

```bash
npm install
```

## Development

1. Start backend (from `../arnes-hackathon-backend`):

```bash
python3 main.py
```

2. Start frontend (from this folder):

```bash
npm run dev
```

3. Open:

```text
http://localhost:8080
```

If your backend runs on a different port during frontend development, set `API_PROXY_TARGET`:

```bash
API_PROXY_TARGET=http://127.0.0.1:8787 npm run dev
```

If backend is not on the default URL, create `.env.local`:

```bash
VITE_API_BASE_URL=http://localhost:8787
```

`VITE_API_BASE_URL` is optional for local development; when omitted, Vite proxies `/api` to `API_PROXY_TARGET`.

## Preview Built App

Build and run the production bundle locally:

```bash
npm run build
npm run preview
```

Open the URL printed by Vite Preview (usually `http://localhost:4173`).

## Production Build

Create deployable assets:

```bash
npm run build
```

Output directory:

```text
dist/
```

Serve `dist/` with an HTTP server (Nginx, Caddy, Netlify, Vercel static output, etc.).

## Asset Notes

- Leaflet styles are bundled from `leaflet/dist/leaflet.css` at build time (no runtime CDN dependency).
- Routes are code-split in production (`/capabilities` and `*` are lazy-loaded).

## Important: Do Not Open `dist/index.html` via `file://`

Do **not** double-click `dist/index.html` and open it directly in the browser using `file://...`.
Modern browsers block module/CSS loading in that mode and you will see CORS/`ERR_FAILED` errors.

Always use an HTTP server (`npm run preview` or your deployment server).
