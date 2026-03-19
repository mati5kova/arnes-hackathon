# React Query Cache Policy

This document defines the cache policy for map-related API queries.

## Endpoints and Policies

| Query key | Endpoint | staleTime | gcTime | refetchOnWindowFocus | refetchOnMount | refetchOnReconnect | Reasoning |
| --- | --- | ---: | ---: | --- | --- | --- | --- |
| `["heritage-sites", "markers", bbox, zoom]` | `GET /api/heritage-sites?bbox=...&zoom=...` | `Infinity` | `10m` | `false` | `false` | `false` | Source data is static enough to avoid automatic network refreshes for revisits. |
| `["heritage-sites", "search", search]` | `GET /api/heritage-sites?search=...&limit=20` | `Infinity` | `5m` | `false` | `false` | `false` | Search responses are deterministic for the current dataset snapshot. |
| `["heritage-site", siteId]` | `GET /api/heritage-sites/{siteId}` | `Infinity` | `30m` | `false` | `false` | `false` | Detail metadata is static and benefits from aggressive client reuse. |
| `["api-health"]` | `GET /api/health` | `0` | `1m` | n/a (interval-driven) | n/a (interval-driven) | n/a (interval-driven) | Startup/readiness probe. Polled every `2s` while dataset is loading/not-ready, or while marker query is still fetching/error. Stops once backend is ready and markers are healthy. |

## Cold-Start Retry Policy

To prevent false errors during backend startup, map queries also use retry with exponential backoff:

- Max retries: `120`
- Delay: `500ms` doubling up to `5s`
- Retries on:
  - HTTP `5xx` (`ApiError`)
  - network startup failures (`TypeError`, "Failed to fetch")
- Does not retry on request aborts
- Markers query additionally keeps recovery polling every `3s` while in error state.
- Health query runs without retries (`retry: false`) and relies on interval polling conditions.

## Source of Truth

The executable policy lives in:

- `src/components/heritage-map/use-heritage-map-data.ts`

The `QUERY_CACHE_POLICY` object in that file should be updated together with this document whenever cache behavior changes.
