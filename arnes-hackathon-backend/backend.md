# Backend Setup (FastAPI)

This backend is implemented with FastAPI and proxies/normalizes the Slovenian RNPD dataset.
By default it runs fully from local files (no dependency on OPSI/network).

## Endpoints

- `GET /api/health`
- `GET /api/metrics`
- `GET /api/heritage-sites`
- `GET /api/heritage-sites?bbox=minLng,minLat,maxLng,maxLat`
- `GET /api/heritage-sites?search=ljubljana&limit=20`
- `GET /api/heritage-sites?bbox=minLng,minLat,maxLng,maxLat&zoom=8` (clustered map points)
- `GET /api/heritage-sites/{site_id}`
- `GET /api/overlays` (available overlay catalog)
- `GET /api/overlays/{kind}?bbox=...&zoom=...` (`kind` = `fire|flood|air|landslide|river`, backend-aggregated for rendering performance; heavy area overlays switch to low-zoom grid cells for faster delivery, while `river` returns viewport-clipped linework)

### FastAPI Docs

When the server is running locally on port `8787`, API docs are available at:

- Swagger UI: `http://127.0.0.1:8787/docs`
- ReDoc: `http://127.0.0.1:8787/redoc`
- OpenAPI JSON: `http://127.0.0.1:8787/openapi.json`

## Local Development

Install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
```

Run the backend:

```bash
uvicorn main:app --host 0.0.0.0 --port 8787 --reload
```

## Required Local River Data

The river overlay and the flood-enrichment pipeline expect the official DRSV hydrography dataset to be present locally at:

```bash
arnes-hackathon-backend/AI/Data_Processing/DRSV_HIDRO5_LIN_PV/
```

This folder is intentionally ignored by Git because the extracted shapefile set is too large for the repository.

Download the archive from one of these official links:

- [DRSV_HIDRO5_LIN_PV.zip](https://www.statika.evode.gov.si/fileadmin/vodkat/DRSV_HIDRO5_LIN_PV.zip)
- [podatki.gov.si resource page](https://podatki.gov.si/dataset/obmocne-enote-direkcije-rs-za-vode/resource/108f0bdc-19a4-4e78-bf4b-45880fabdebb)

After downloading, extract the archive so files such as `HIDRO5_LIN_PV_TIPTV1_2.shp`, `.dbf`, `.shx`, and related sidecar files live directly inside that directory.

If this dataset is missing:

- the `river` map overlay will not work
- regenerating `AI/Data/kd_z_nevarnost_enriched_verified.geojson` will fail

## Tests

Install dev dependencies and run backend tests:

```bash
pip3 install -r requirements-dev.txt
pytest
```

## Data Source Mode

- Default (`RNPD_ALLOW_REMOTE=0`): local-only mode.
  The backend reads RNPD data from:
    1. `RNPD_LOCAL_FILE` (if set)
    2. `./rnpd.json`
    3. `../arnes-hackathon-frontend/src/data/rnpd.json` (legacy fallback path; optional)
- Optional remote fallback: set `RNPD_ALLOW_REMOTE=1` to allow fetching from `RNPD_SOURCE_URL` if local files are missing.

## Preprocessed Dataset Cache

To speed up cold starts, normalized sites are persisted to a preprocessed cache file and reused on startup when source metadata matches.

- `RNPD_PREPROCESSED_CACHE_ENABLED` (default: `1`)
- `RNPD_PREPROCESSED_CACHE_FILE` (default: `./rnpd.preprocessed.json`)

## API Guardrails and Caching

- Invalid `bbox` now returns `400` with validation details.
- Unbounded list requests (no `bbox`, no `search`, no `limit`) are capped by `API_UNBOUNDED_LIST_LIMIT` (default: `2500`).
- Response items are hard-capped by `RNPD_MAX_RESPONSE_ITEMS` (default: `5000`).
- `GET /api/heritage-sites` and `GET /api/heritage-sites/{site_id}` support conditional requests via `ETag`/`If-None-Match` and may return `304`.
- Data-loading failures return `503` on data endpoints (`/api/heritage-sites`, `/api/heritage-sites/{site_id}`).
- Cache headers can be configured per endpoint:
    - `API_CACHE_CONTROL_HEALTH`
    - `API_CACHE_CONTROL_METRICS`
    - `API_CACHE_CONTROL_SITES`
    - `API_CACHE_CONTROL_SITE_DETAIL`
    - `API_CACHE_CONTROL_OVERLAYS`
