# Arnes Hackathon: Kulturko - UI za klasifikacijo ogroženosti kulturne dediščine

Ta repozitorij vsebuje vse podatke, cevovode za obdelavo podatkov in kodo potrebno za lokalni zagon aplikacije.

## Struktura repozitorija

- `arnes-hackathon-backend/` FastAPI API, obdelava podatkov, chat_service.py, vektorska baza Chroma, ...
- `arnes-hackathon-frontend/` React uporabniški vmesnik, sloji ogroženosti, klepetalnik, ...

## Pomembnejše datoteke
- `arnes-hackathon-backend/rnpd`
- ``
- ``

## Potrebna orodja in okolja

- Python 3.11+
- Node.js 18+
- npm

## Zagon zalednega dela

Iz korena `arnes-hackathon/` izvedemo:

```bash
cd arnes-hackathon-backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
```

Poženemo FastAPI strežnik:

```bash
uvicorn main:app --host 0.0.0.0 --port 8787 --reload
```

Za klepetalnik je potrebna dodatna konfiguracija za Azure OpenAI znotraj `arnes-hackathon-backend/.env`.

- Nastavi `AZURE_OPENAI_BASE_URL` na tvoj Azure oddaljen vir (URL) ki se konča z `/openai/v1/`
- Nastavi `AZURE_OPENAI_API_KEY` na tvoj deljen ali pa 'per model' ključ `CHAT_MODEL_*_API_KEY`
- Nastavi ali ohrani privzete `CHAT_MODEL_*_DEPLOYMENT` vrednosti da ustrezajo tvojim

Lokalno dostopno na:

- API: `http://127.0.0.1:8787`
- Swagger UI: `http://127.0.0.1:8787/docs`
- ReDoc: `http://127.0.0.1:8787/redoc`

## Vzpostavitev uporabniškega vmesnika

V drugem terminalu:

```bash
cd arnes-hackathon-frontend
cp .env.example .env.local
npm install
npm run dev
```

Lokalno dostopno na:

- `http://localhost:8080`

Privzeto aplikacija zaledni del pričakuje na naslovu `http://localhost:8787`.
Po potrebi lahko to obnašanje tudi spremenimo z:

```bash
API_PROXY_TARGET=http://127.0.0.1:8787 npm run dev
```

Ali ustvarimo `arnes-hackathon-frontend/.env.local` z:

```bash
VITE_API_BASE_URL=http://localhost:8787
```

## Poganjanje testov

Zaledni del:

```bash
cd arnes-hackathon-backend
source .venv/bin/activate
pytest
```

Čelni del:

```bash
cd arnes-hackathon-frontend
npm test
```

## "Production build"

```bash
cd arnes-hackathon-frontend
npm run build
npm run preview
```

Do not open `dist/index.html` directly with `file://`; serve it through an HTTP server.

## Notes

- Backend data is local-first and uses `arnes-hackathon-backend/rnpd.json` by default.
- The chat assistant also uses `arnes-hackathon-backend/AI/Data/kd_z_nevarnost.geojson` for local heritage-risk lookups.
- Overlay data is exposed through `GET /api/overlays` and `GET /api/overlays/{kind}` (`fire`, `flood`, `air`, `landslide`), with viewport/zoom aggregation for map performance. Heavy area overlays (`flood`, `landslide`) use low-zoom grid rendering for faster responses and keep polygon detail at higher zoom.
- Chat endpoints are available at `GET /api/chat/models`, `GET /api/chat/usage`, and `POST /api/chat`.
- Backend dev dependencies are listed in `arnes-hackathon-backend/requirements-dev.txt`.
- More detailed run notes are in `arnes-hackathon-frontend/RUN.md` and `arnes-hackathon-backend/backend.md`.
