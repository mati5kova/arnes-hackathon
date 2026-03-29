# Arnes Hackathon

This repository contains a FastAPI backend for Slovenian cultural heritage data and a React/Vite frontend for the map UI.

## Repository Structure

- `arnes-hackathon-backend/` FastAPI API, dataset loading, backend tests
- `arnes-hackathon-frontend/` React application, frontend tests

## Prerequisites

- Python 3.11+
- Node.js 18+
- npm

## Backend Setup

From the repository root:

```bash
cd arnes-hackathon-backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Run the backend:

```bash
uvicorn main:app --host 0.0.0.0 --port 8787 --reload
```

Available locally at:

- API: `http://127.0.0.1:8787`
- Swagger UI: `http://127.0.0.1:8787/docs`
- ReDoc: `http://127.0.0.1:8787/redoc`

## Frontend Setup

Open a second terminal, then:

```bash
cd arnes-hackathon-frontend
npm install
npm run dev
```

The frontend runs locally at:

- `http://localhost:8080`

By default, frontend development expects the backend at `http://localhost:8787`.

If needed, you can point the frontend to a different backend:

```bash
API_PROXY_TARGET=http://127.0.0.1:8787 npm run dev
```

Or create `arnes-hackathon-frontend/.env.local` with:

```bash
VITE_API_BASE_URL=http://localhost:8787
```

## Running Tests

Backend:

```bash
cd arnes-hackathon-backend
source .venv/bin/activate
pytest -q
```

Frontend:

```bash
cd arnes-hackathon-frontend
npm test
```

## Production Build

Frontend production build:

```bash
cd arnes-hackathon-frontend
npm run build
npm run preview
```

Do not open `dist/index.html` directly with `file://`; serve it through an HTTP server.

## Notes

- Backend data is local-first and uses `arnes-hackathon-backend/rnpd.json` by default.
- Overlay data is exposed through `GET /api/overlays` and `GET /api/overlays/{kind}` (`fire`, `flood`, `air`, `landslide`), with viewport/zoom aggregation for map performance.
- Backend dev dependencies are listed in `arnes-hackathon-backend/requirements-dev.txt`.
- More detailed run notes are in `arnes-hackathon-frontend/RUN.md` and `arnes-hackathon-backend/backedn.md`.

DEV PRIMOŽ
