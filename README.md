# Heimdall — Edge AI for Emergency Situational Awareness

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](../../LICENSE)

Real-time wildfire detection and propagation forecasting on an NVIDIA Jetson AGX, streaming structured intelligence to field commanders.

---

## Vision

Emergencies unfold faster than humans can process raw sensor feeds. Heimdall puts a thermal eye and a physics-based forecast engine at the edge — on the drone itself — so that first responders receive actionable intelligence within seconds of a new detection, with no cloud dependency.

## Mission

Given a nadir-facing FLIR thermal camera aboard a drone, Heimdall:

1. Detects active fire perimeters in real time using a YOLO26m model fine-tuned on thermal imagery.
2. Projects pixel detections into geo-referenced GeoJSON polygons using drone telemetry (GPS + heading + altitude).
3. Feeds those polygons into a physics-based propagation engine (Balbi 2015) coupled with live Open-Meteo weather forecasts.
4. Streams the resulting `MeteoReport` — fire perimeter, spread rate, risk buffers, FWI, hotspots — to any consumer (dashboard, command tablet, GIS) via a lightweight JSON API.

Everything runs on the Jetson. No internet required for inference. Open-Meteo is optional; the system degrades gracefully to last-known weather if the network is unavailable.

---

## Architecture

```
packages/edge/
├── vision/                 # Thermal perception layer
│   ├── training/           # SageMaker fine-tuning, data preparation
│   ├── inference/          # TensorRT inference loop, geo-projection, API poster
│   └── export/             # ONNX → TensorRT FP16 export for Jetson
│
├── convergence/            # Propagation & weather layer (FastAPI microservice)
│   ├── api.py              # FastAPI app: /detect, /latest, /history, /health
│   ├── orchestrator.py     # Coordination: weather fetch → Balbi → risk buffers
│   ├── forecast.py         # Balbi 2015 fire-spread physical model
│   ├── client.py           # Open-Meteo async client
│   ├── fuels.py            # Scott/Burgan fuel models 1–13
│   ├── buffers.py          # GeoJSON risk buffer geometry (1/3/5 km rings)
│   ├── history.py          # ReportHistory ring-buffer (dA/dt, d²A/dt²)
│   └── models.py           # Pydantic schemas: FireDetectionPayload → MeteoReport
│
├── configs/                # Training and auto-label thresholds
├── docker/                 # Dockerfile.jetson, docker-compose.yml, .env.example
├── scripts/                # SageMaker launch, TensorRT export, demo replay
├── tests/                  # Full test suite (54 tests)
└── sdd/                    # System Design Document: discovery → tasks
```

### Data flow

```
FLIR Boson 640 (thermal)
        │  raw frames (30 fps)
        ▼
vision/inference/infer_jetson.py
   YOLO26m → TensorRT FP16
   pixel bboxes → geo-polygon (flat-earth nadir projection)
        │  FireDetectionPayload (JSON)  POST /detect
        ▼
convergence/api.py  (uvicorn, port 8000)
   orchestrator → Open-Meteo → Balbi 2015 → risk buffers
   ReportHistory ring-buffer (dA/dt, d²A/dt²)
        │  MeteoReport (JSON)  GET /latest
        ▼
Dashboard / field tablet (any HTTP client)
```

**One process = one drone.** The convergence API holds all state in memory. For multiple drones, run one container per drone on different ports with distinct `DRONE_ID` values.

---

## Stack

| Layer | Technology |
|-------|-----------|
| Detection model | YOLO26m (21.7 M params, 74.7 GFLOPs) fine-tuned on thermal fire imagery |
| Inference runtime | TensorRT FP16 on Jetson AGX Orin |
| Geo-projection | Flat-earth nadir camera model, GSD via HFOV + altitude, heading rotation matrix |
| Propagation model | Balbi 2015 (physics-based, no ML) |
| Weather source | Open-Meteo free API — no key required |
| Fuel models | Scott/Burgan 1–13 |
| API framework | FastAPI + uvicorn, Pydantic v2 |
| State management | In-process `asyncio` state + `ReportHistory` ring-buffer |
| Container | `python:3.11-slim-bookworm` — no torch, no CUDA, no OpenCV |

---

## JSON Contract

The convergence API emits `MeteoReport` on `GET /latest`. Minimal shape:

```json
{
  "drone_id": "drone-0",
  "generated_at": "2026-05-26T14:32:00Z",
  "fire_perimeter": {
    "type": "Polygon",
    "coordinates": [[[lon, lat], ...]]
  },
  "area_ha": 3.7,
  "centroid": { "lat": 41.6488, "lon": -0.8891 },
  "spread_rate_m_min": 12.4,
  "fwi": 24.1,
  "risk_level": "high",
  "risk_buffers": {
    "type": "FeatureCollection",
    "features": [
      { "properties": { "ring_km": 1, "label": "immediate" }, ... },
      { "properties": { "ring_km": 3, "label": "watch" }, ... },
      { "properties": { "ring_km": 5, "label": "advisory" }, ... }
    ]
  },
  "hotspots": [{ "lat": 41.649, "lon": -0.888, "temp_c": 394, "confidence": 0.87 }],
  "growth_rate_m2_s": 0.42,
  "acceleration_m2_s2": 0.03,
  "weather": {
    "wind_speed_kmh": 28,
    "wind_dir_deg": 245,
    "temperature_c": 34,
    "relative_humidity_pct": 18,
    "forecast_horizon_h": 24
  }
}
```

All coordinates are GeoJSON `[lon, lat]` order.

Interactive schema docs: `http://localhost:8000/docs` (Swagger UI, live on the Jetson).

---

## Quick Start

Full instructions — image contents, env vars, `podman`/`docker` commands, healthcheck — are in **[howRun.md](./howRun.md)**.

```powershell
# 1. Configure environment
copy docker\.env.example docker\.env

# 2. Start the convergence API
podman compose -f docker/docker-compose.yml --env-file docker/.env up --build

# 3. Verify
curl http://localhost:8000/health
```

---

## Model Weights

The trained `best.pt` is stored in S3 — not in this repo (weights are ~85 MB and version-controlled separately):

```powershell
aws s3 cp s3://xheimdall-models/training/xheimdall-yolo26m-20260525-101951/output/model.tar.gz .
tar xzf model.tar.gz
```

Export to TensorRT FP16 for Jetson:

```powershell
python scripts/export_tensorrt.py best.pt --fp16
# produces best.engine
```

Run live inference:

```powershell
python -m vision.inference.infer_jetson \
  --engine best.engine \
  --source /dev/video0 \
  --api-url http://localhost:8000 \
  --drone-lat 41.6488 --drone-lon -0.8891 \
  --drone-alt 120 --drone-heading 250
```

---

## Demo Replay (Plan B)

If the camera or TensorRT is unavailable at demo time, replay pre-recorded detections against the live API:

```powershell
python scripts/replay_detections.py \
  --file tests/data/demo_replay.jsonl \
  --api-url http://localhost:8000 \
  --interval 5 --loop
```

The fixture (`tests/data/demo_replay.jsonl`) simulates a growing wildfire near Zaragoza: 0.5 → 15 ha over 8 steps.

---

## Development

```powershell
pip install -e ".[dev]"
pytest                       # 54 tests
pytest -x -q                 # fail-fast
```

Test fixtures with real TIFF data and convergence payloads live in `tests/data/`.

---

## Responsible AI

Heimdall is designed for **human-in-the-loop** operations:

- All outputs carry a `confidence` score derived from the detector.
- The propagation model is physics-based (Balbi 2015) — no black-box ML in the forecast path.
- `ReportHistory` provides a traceable time series of area evolution so analysts can audit growth trends.
- Risk levels (`low / moderate / high / extreme`) are deterministic functions of FWI + spread rate, not learned classifiers.
- The system never issues evacuation orders; it surfaces structured intelligence for qualified personnel.

---

## License

Apache-2.0 — see [LICENSE](../../LICENSE).
