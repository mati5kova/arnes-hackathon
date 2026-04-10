# Zaledni del

Zaledni del je implementiran na ogrodju FastAPI in "proxija" in normalizira podatke iz RNPD (register nepremične kulturne dediščine - OPSI)

Privzeto se vse poganja lokalno brez odvisnosti na OPSI in omrežje.

## Endpoint-i

- `GET /api/health`
- `GET /api/metrics`
- `GET /api/heritage-sites`
- `GET /api/heritage-sites?bbox=minLng,minLat,maxLng,maxLat`
- `GET /api/heritage-sites?search=ljubljana&limit=20`
- `GET /api/heritage-sites?bbox=minLng,minLat,maxLng,maxLat&zoom=8` (clustered map points)
- `GET /api/heritage-sites/{site_id}`
- `GET /api/overlays` (katalog vseh dostopnih slojev)
- `GET /api/overlays/{kind}?bbox=...&zoom=...` (`kind` = `fire|flood|air|landslide|river`

### FastAPI dokumentacija

Ko je strežnik zagnan je dokumentacija vseh endpointov, pričakovanih vhodov in izhodov dostopna na:

- Swagger UI: `http://127.0.0.1:8787/docs`
- ReDoc: `http://127.0.0.1:8787/redoc`
- OpenAPI JSON: `http://127.0.0.1:8787/openapi.json`

## Lokalno razvoj

```bash
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
```

Run the backend:

```bash
uvicorn main:app --host 0.0.0.0 --port 8787 --reload
```

## Nujno potrebni lokalni o rekah

Sloj rek in cevovod za obogatitev podatkov potrebujeta uradnje DRSV podatke o rekah na lokaciji:

```bash
arnes-hackathon-backend/AI/Data_Processing/DRSV_HIDRO5_LIN_PV/
```

Ti podatki so namenomo vključeni v `.gitignore` datoteki saj so preveliki za hrambo na Github-u

Nalozi podatke iz enega od teh virov:

- [DRSV_HIDRO5_LIN_PV.zip](https://www.statika.evode.gov.si/fileadmin/vodkat/DRSV_HIDRO5_LIN_PV.zip)
- [podatki.gov.si resource page](https://podatki.gov.si/dataset/obmocne-enote-direkcije-rs-za-vode/resource/108f0bdc-19a4-4e78-bf4b-45880fabdebb)

Po prenosu, "extractaj" podatke tako da so datoteke kot so `HIDRO5_LIN_PV_TIPTV1_2.shp`, `.dbf`, `.shx` dostopne direktno znotraj tega imenika
