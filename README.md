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

## Model: Heimdall TensorRT FP16

YOLOv26m fine-tuned on AWS SageMaker (`xheimdall-yolo26m-20260525-101951`) for single-class
thermal fire detection, exported to TensorRT FP16 for NVIDIA Jetson.

| Metric (200 epochs, val split) | Value |
|---|---|
| mAP@0.5 | 0.463 |
| mAP@0.5:0.95 | 0.246 |
| Precision | 0.493 |
| Recall | 0.456 |

Training: `ml.g5.xlarge` (A10G 24 GB) · 200 epochs · 2 h 45 min · **3 064 thermal frames**.  
See [models/MODEL_CARD.md](models/MODEL_CARD.md) for full details, data sources, limitations and
our recommendation regarding broader-dataset re-training before operational deployment.

Download weights: `python scripts/fetch_model.py` (~44 MB).

---

## Quick Start

> Hardware: NVIDIA Jetson AGX Orin (JetPack 6.x).  
> Software prerequisites: `docker` + `nvidia-container-toolkit` (already
> installed on stock JetPack images).  
> Optional: thermal camera at `/dev/video0` and active buzzer wired to GPIO pin 7.

```bash
# 1. Clone and configure
git clone https://github.com/ComunidadIA-OS/Edge-AI-for-Situational-Awareness-in-Emergencies
cd Edge-AI-for-Situational-Awareness-in-Emergencies
cp docker/.env.example docker/.env   # adjust DRONE_LAT/LON, CAMERA_DEVICE if needed

# 2. Launch the full stack
docker compose -f docker/docker-compose.yml --env-file docker/.env up --build
```

That's everything. On first launch, `vision-inference` will:

1. Download `best.pt` (~44 MB) from the GitHub release (or use any `models/best.pt` you've pre-placed).
2. Export it to `models/best.engine` (TensorRT FP16) — a one-time step that takes 1–3 min on AGX Orin.
3. Run pre-flight checks (camera + engine + audio backend) — beeps on failure.
4. Start the supervisor → live YOLO inference → POST detections to `convergence-api` → expose `MeteoReport` on `GET /latest`.

Ground control points to `http://<jetson-ip>:8000/latest`.

Verify the stack:

```bash
bash scripts/verify_stack.sh
```

Full environment variables and deployment notes: **[howRun.md](./howRun.md)**.

### Audible alert codes

The vision-inference container emits buzzer beeps when a critical error is detected.
The operator does **not** need a screen to diagnose the issue.

| Beeps | Meaning | Action |
|---|---|---|
| 1 | No camera connected at `/dev/video*` | Connect thermal camera, restart |
| 2 | Convergence API not responding | Check `convergence-api` container, network |
| 3 | TensorRT engine file missing | Run `fetch_model.py` + `export_tensorrt.py` |
| 4 | Unclassified fatal error | Connect a screen, check container logs |

---

## Model Weights

Weights are distributed as a GitHub Release asset (not committed to git).

```bash
# Download best.pt (~44 MB)
python scripts/fetch_model.py

# Export to TensorRT FP16 on Jetson (requires CUDA + TensorRT)
python -m vision.inference.export_tensorrt --model models/best.pt --fp16 --output models/best.engine

# Or run directly with PyTorch weights (slower, no TensorRT)
python -m vision.inference.infer_jetson \
  --engine models/best.pt \
  --source /dev/video0 \
  --api-url http://localhost:8000 \
  --drone-lat 41.6837 --drone-lon -0.8881 \
  --drone-alt 120 --drone-heading 250
```

---

## Demo Replay (Plan B)

If the camera or TensorRT is unavailable at demo time, replay pre-recorded detections against the live API:

```bash
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
