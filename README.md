# Heimdall — Ground Control

**Real-time wildfire situational-awareness dashboard.**
Pure visualisation client for the **MeteoReport v1** JSON contract emitted by an NVIDIA Jetson AGX edge device.

> Submitted to the **SEDIA Hackathon — "IA Responsable y Abierta en Industria"** (May 2026).
> Built by the [ComunidadIA-OS](https://github.com/ComunidadIA-OS) team.

---

## 1. What this is (in one paragraph)

Ground Control is the **web cockpit** that emergency-response operators look at while a drone flies over an active wildfire.
It connects to a Jetson AGX running computer-vision + meteorological models, polls a single endpoint (`GET /latest`), and renders everything in real time on a 3D map: fire perimeter, hourly forecasts, risk buffers, drone telemetry, satellite hotspots, weather and recommended actions.

It is the *eyes* of the system. The Jetson is the *brain*.

---

## 2. What it does NOT do (very important)

> **Ground Control performs zero calculations, zero AI inference, and zero physics simulations.**

It does not:

- ❌ Run any fire-spread model (Balbi'15, FARSITE, FlamMap…).
- ❌ Run any object-detection model (YOLO, etc.).
- ❌ Pull weather data from Open-Meteo or any other API.
- ❌ Compute Fire Weather Index, fuel moisture, growth rate, or hotspots.
- ❌ Mutate, smooth, or interpolate the data it receives.

Everything that lives on screen is **whatever the Jetson sent in the last MeteoReport** — verbatim, validated, rendered.
This is a deliberate edge-computing decision: heavy compute stays at the edge (Jetson), the dashboard stays a thin, fast, focused visualisation layer.

---

## 3. What it does, in concrete terms

| Responsibility | How |
|---|---|
| **Connect to the Jetson** | User enters the Jetson URL on the *Connect* screen → stored locally (Zustand + `localStorage`). |
| **Poll for fresh data** | TanStack Query refetches `GET {jetsonUrl}/latest` every **2 s** (configurable). |
| **Validate the contract** | Every response is parsed through a **Zod** schema (`MeteoReportSchema`). Malformed payloads are rejected before they reach the UI. |
| **Render the map** | MapLibre GL 5 with AWS Terrarium DEM (3D terrain) + Deck.gl overlay (`MapboxOverlay`, non-interleaved). |
| **Show fire intelligence** | Fire perimeter, 24 h predicted perimeter, risk buffers (5 / 3 / 1 km), drone trail, hotspots, infrastructure at risk. |
| **Show KPIs** | FWI, spread rate, current area, predicted 24 h area, fuel model, trend, confidence, warnings, recommended actions. |
| **Survive a Jetson outage** | Connection state machine: `online` → `stale` (no fresh data in 10 s) → `offline`. UI shows a banner, never crashes. |
| **Stay testable offline** | MSW (Mock Service Worker) intercepts `/latest` in development and replays realistic synthetic data. |

---

## 4. How it is built (architecture)

```
┌──────────────────────────────────────┐
│  Jetson AGX (separate repo)          │
│  FastAPI · YOLOv9 · Balbi'15 · etc.  │
│  GET /latest → MeteoReport v1 JSON   │
└──────────────┬───────────────────────┘
               │  HTTP polling every 2 s
               ▼
┌──────────────────────────────────────────────────────────────┐
│  GROUND CONTROL (this package)                               │
│                                                              │
│  api/meteo-report.ts ──► TanStack Query ──► Zod validate     │
│                                  │                           │
│                                  ▼                           │
│  Zustand stores  (connection · settings · ui · layers · map) │
│                                  │                           │
│                                  ▼                           │
│  React 19 components                                         │
│   ├── MapLibre GL 5  + AWS Terrarium DEM   (3D terrain)      │
│   ├── Deck.gl 9      + MapboxOverlay       (GIS layers)      │
│   ├── Sidebar        (Status · Situation · Layers panels)    │
│   ├── TopBar         (live connection / staleness banners)   │
│   └── ErrorBoundary  (each panel isolated)                   │
└──────────────────────────────────────────────────────────────┘
```

### Folder layout (`src/`)

```
src/
├── api/          HTTP client (ky) + TanStack Query hooks
├── schemas/      Zod schema for MeteoReport (single source of truth at runtime)
├── types/        TypeScript types for MeteoReport, map state, UI
├── stores/       Zustand: connection · settings · ui · layers · map
├── hooks/        Reusable hooks (e.g. useDroneUrl)
├── lib/          Providers (QueryClient), small utils
├── mocks/        MSW handlers + a realistic MeteoReport generator
└── components/
    ├── app/      ConnectScreen · TopBar · root composition
    ├── map/      MapLibreMap + Deck.gl layers + LegendPanel
    ├── sidebar/  Sidebar tabs (Status / Situation / Layers)
    └── ui/       ErrorBoundary, small primitives
```

---

## 5. Why this stack (rationale)

| Choice | Reason |
|---|---|
| **Next.js 16 + Turbopack** | Fast dev refresh, RSC where useful, easy static export if needed. |
| **React 19** | Concurrent rendering keeps the map smooth while polling happens. |
| **TypeScript strict** | The MeteoReport contract has ~50 fields — types catch drift between Jetson and UI. |
| **Zod runtime validation** | Types alone are not enough. The Jetson is a separate codebase; we *prove* every response matches the contract before rendering. |
| **TanStack Query** | Polling + retry + stale logic + cache, with no manual `useEffect` plumbing. |
| **Zustand** | Tiny, no boilerplate, perfect for ephemeral UI state (active tab, layer toggles, droneUrl). |
| **MapLibre GL 5** | Open-source, vector-tiled, supports `terrain` from a DEM source — true 3D without Mapbox tokens. |
| **Deck.gl + MapboxOverlay (non-interleaved)** | GPU rendering for many polygons, lines and icons. Non-interleaved avoids depth conflicts with MapLibre's terrain. |
| **Tailwind 4 + lucide-react** | Fast, consistent dark UI; zero design-system overhead. |
| **MSW** | Run the entire dashboard offline against realistic mocked data — essential for demo and CI. |
| **Vitest + Testing Library** | Schema tests, generator tests, panel tests. Fast, ESM-native. |

---

## 6. The contract (MeteoReport v1)

The only thing this dashboard knows about the world is this JSON shape:

```ts
interface MeteoReport {
  metadata:              { generated_at, model_version, location, forecast_hours, data_sources }
  current_weather:       { temperature_c, humidity, wind, gusts, soil_*, ... }
  fire_perimeter:        { polygon (GeoJSON), area_ha, centroid, hotspots[], ... }
  prediction:            { trend, FWI, fuel_*, spread_rate, hourly[24], ... }
  situational_awareness: { summary, warnings[], recommended_actions[], infrastructure_at_risk[] }
  risk_buffers:          { distance_km, geometry }[]
  drone_telemetry:       { lat, lon, altitude_m, heading_deg, speed_kmh, timestamp } | null
}
```

The authoritative definition lives in:

- **Types:** `src/types/meteo-report.ts`
- **Runtime schema:** `src/schemas/meteo-report.schema.ts`

If the Jetson team changes the contract, those two files are the only places this repo needs to change.

---

## 7. Quick start — one command, zero friction

You only need **Docker Desktop**. No Node, no pnpm, no toolchain on the host.

```bash
docker compose up --build
# open http://localhost:3000 → enter your MeteoReport endpoint URL → Connect
```

First build is ~2–4 min; subsequent runs start in seconds. The dashboard is **agnostic to the data source** — point it at any service that emits a valid `MeteoReport v1` on `GET /latest`.

If you want to hack on the source instead of just running it, see [**HowRun.md**](./HowRun.md) for the local-dev (Node + pnpm) path.

---

## 8. Scripts

| Command | What it does |
|---|---|
| `pnpm dev` | Next.js dev server with Turbopack on `localhost:3000`. |
| `pnpm build` | Production build. |
| `pnpm start` | Run the production build. |
| `pnpm lint` | ESLint. |
| `pnpm test` | Run the Vitest suite once. |
| `pnpm test:watch` | Vitest in watch mode. |

---

## 9. Project status

This package is **`v0.1-GroundControl`**, the dashboard half of a two-repo edge-AI submission.
The Jetson edge device lives at branch [`v0.1-EdgeDevice`](https://github.com/ComunidadIA-OS/Edge-AI-for-Situational-Awareness-in-Emergencies/tree/v0.1-EdgeDevice) of the same repository.

Both halves share a single contract — `MeteoReport v1` — and nothing else.

---

## 10. License

MIT (see repository root).
