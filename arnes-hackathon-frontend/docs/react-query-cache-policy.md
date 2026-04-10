# React query cache policy

V tem dokumentu so prisotne vse definicije za obnašanje React query predpomnilnika navezujoče na API poizvedbe.

## Endpoints

| Query key                                   | Endpoint                                      |  staleTime | gcTime | refetchOnWindowFocus | refetchOnMount | refetchOnReconnect | Reasoning                                                                                                     |
| ------------------------------------------- | --------------------------------------------- | ---------: | -----: | -------------------- | -------------- | ------------------ | ------------------------------------------------------------------------------------------------------------- |
| `["heritage-sites", "markers", bbox, zoom]` | `GET /api/heritage-sites?bbox=...&zoom=...`   | `Infinity` |  `10m` | `false`              | `false`        | `false`            | Izvorno podatki so dovolj statični da se lahko izognemo avtomatskemu "network refreshu" pri ponovnih obiskih. |
| `["overlay-grid", kind, bbox, zoom]`        | `GET /api/overlays/{kind}?bbox=...&zoom=...`  |      `45s` |  `10m` | `false`              | `false`        | `false`            | "Overlay" celice so lahko shranjene da se izgonemo ponovnem nalaganjo ob hitrih premikih znotraj zemljevida.  |
| `["heritage-sites", "search", search]`      | `GET /api/heritage-sites?search=...&limit=20` | `Infinity` |   `5m` | `false`              | `false`        | `false`            | Odgovori na iskanja so deterministični.                                                                       |
| `["heritage-site", siteId]`                 | `GET /api/heritage-sites/{siteId}`            | `Infinity` |  `30m` | `false`              | `false`        | `false`            | Podrobni meta podatki so statični in je priročno da so v predpomnilniku.                                      |

## Politika ponovnega poizkusa za hladen zagon

Da se izognemo krivim napakam med zagonom zalednega dela "queriji" ki se nanašajo na zemljevid tudi uporabljajo ponovni poizkus z eksponentno "backoff" strategijo:

- Maksimalno število poizkusov: `120`
- Zakasnitev: `500ms` s podvajanjem do `5s`
- Ponovni poizkus ob:
    - HTTP `5xx` (`ApiError`)
    - network startup failures (`TypeError`, "Failed to fetch")
- Ni ponovnih poizkusov ob prekinitvah requestov

Beri `src/components/heritage-map/use-heritage-map-data.ts`
