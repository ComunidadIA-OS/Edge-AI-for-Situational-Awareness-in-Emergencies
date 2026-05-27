# 🛰️ Heimdall — Edge AI for Emergency Situational Awareness

> **Edge stack** (Jetson: vision + convergence). For the project hub and the dashboard branch, start at [`v0.1-Heimdall`](../../tree/v0.1-Heimdall).

[![Code License: Apache 2.0](https://img.shields.io/badge/Code%20License-Apache%202.0-blue.svg)](LICENSE)
[![Vision/Model License: AGPL-3.0](https://img.shields.io/badge/Vision%2FModel%20License-AGPL--3.0-orange.svg)](LICENSE-AGPL-3.0.txt)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform: Jetson AGX Orin](https://img.shields.io/badge/platform-Jetson%20AGX%20Orin-76B900.svg)](https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/)
[![Responsible AI](https://img.shields.io/badge/AI-human--in--the--loop-success.svg)](#responsible-ai)

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
.
├── vision/                 # Thermal perception layer  (AGPL-3.0 — derives from YOLO26)
│   ├── inference/          # TensorRT inference loop, geo-projection, API poster, FP16 export
│   ├── io/                 # Thermal TIFF decoding + RGB cross-check
│   └── utils/              # Config loading, debug visualisation
│
├── convergence/            # Propagation & weather layer  (Apache-2.0, FastAPI microservice)
│   ├── api.py              # FastAPI app: /detect, /latest, /history, /health
│   ├── orchestrator.py     # Coordination: weather fetch → Balbi → risk buffers
│   ├── forecast.py         # Balbi 2015 fire-spread physical model
│   ├── client.py           # Open-Meteo async client
│   ├── fuels.py            # Scott/Burgan fuel models 1–13
│   ├── buffers.py          # GeoJSON risk buffer geometry (1/3/5 km rings)
│   ├── history.py          # ReportHistory ring-buffer (dA/dt, d²A/dt²)
│   └── models.py           # Pydantic schemas: FireDetectionPayload → MeteoReport
│
├── edge/                   # Edge orchestration  (Apache-2.0)
│   ├── supervisor.py       # Process supervision (vision ↔ API ↔ alerts)
│   ├── preflight.py        # Camera + engine + audio preflight checks
│   └── alerts.py           # Audible buzzer alert codes
│
├── configs/                # Training and auto-label thresholds
├── docker/                 # Dockerfile.jetson + Dockerfile.vision + docker-compose.yml
├── scripts/                # Model fetch, TensorRT export, demo replay, stack verify
└── tests/                  # edge + convergence + vision test suites
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
| Detection model | `Heimdall-Vision-TensorRT-F16` — [Ultralytics YOLO26](https://docs.ultralytics.com/models/yolo26) fine-tuned for a single `fire` class on thermal imagery (AGPL-3.0) |
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

## Model: `Heimdall-Vision-TensorRT-F16`

[Ultralytics YOLO26](https://docs.ultralytics.com/models/yolo26) fine-tuned for single-class
thermal fire detection, exported to TensorRT FP16 for NVIDIA Jetson.

> **License note.** Because it derives from Ultralytics YOLO26, the weights **and** the
> vision-inference code path (`vision/`) are **AGPL-3.0**, not Apache-2.0. The rest of this
> branch (`convergence/`, `edge/`) is Apache-2.0. See [LICENSE](LICENSE),
> [LICENSE-AGPL-3.0.txt](LICENSE-AGPL-3.0.txt), [NOTICE](NOTICE), and the
> [model card](models/MODEL_CARD.md).

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

## Troubleshooting

Common issues when deploying or developing the edge stack. Full details in [howRun.md](./howRun.md).

| Symptom | Likely cause | Fix |
|---|---|---|
| `convergence-api` exits immediately | Port 8000 already in use | `sudo lsof -i :8000` → kill the process, or change `HOST_PORT` in `.env` |
| `ModuleNotFoundError: No module named 'convergence'` | Not installed in editable mode | `pip install -e ".[dev]"` from the project root |
| `curl http://localhost:8000/health` → connection refused | Container not running or wrong port | `docker compose ps` → check status; verify `HOST_PORT` in `.env` |
| TensorRT export fails with `Could not find any implementation` | ONNX ops not supported by TensorRT version on Jetson | Re-export with `--onnx-opset 17`; verify JetPack ≥ 6.0 |
| `best.pt` not found, `fetch_model.py` fails | Model not in local cache or GitHub release | Download manually from [GitHub Releases](https://github.com/ComunidadIA-OS/Edge-AI-for-Situational-Awareness-in-Emergencies/releases) → place in project root |
| CI fails on push (`tests/edge` or `tests/convergence`) | Dependency mismatch or Python version | Run `pip install -e ".[dev]"` locally; check `python --version` matches CI matrix (3.10–3.12) |
| `docker compose up` → `no configuration file provided` | Not in the project root directory | `cd` to the repo root where `docker-compose.yml` lives |
| Vision container beeps on startup | See [audible alert codes](#audible-alert-codes) above | 1 beep = no camera, 2 = API down, 3 = missing engine, 4 = fatal |

If you hit something not listed here, open an issue using the [bug report template](.github/ISSUE_TEMPLATE/bug_report.yml).

---

## Development

```powershell
pip install -e ".[dev]"
pytest tests/edge tests/convergence   # 50 tests — pure-Python physics + edge, run in CI
pytest -x -q                          # fail-fast (full suite; vision tests need CUDA hardware)
```

The `tests/edge` and `tests/convergence` suites (50 tests) import only pure Python and run on
every push via [GitHub Actions](.github/workflows/ci.yml). The `tests/vision` suite exercises
TensorRT/torch and requires a CUDA-capable machine. Test fixtures with real TIFF data and
convergence payloads live in `tests/data/`.

---

## Responsible AI

Heimdall is designed for **human-in-the-loop** operations:

- All outputs carry a `confidence` score derived from the detector.
- The propagation model is physics-based (Balbi 2015) — no black-box ML in the forecast path.
- `ReportHistory` provides a traceable time series of area evolution so analysts can audit growth trends.
- Risk levels (`low / moderate / high / extreme`) are deterministic functions of FWI + spread rate, not learned classifiers.
- The system never issues evacuation orders; it surfaces structured intelligence for qualified personnel.

---

## Responsible AI

This edge stack is built for a *Responsible and Open AI* challenge, and the constraints are first-class:

- **Advisory only, never autonomous.** Outputs are decision support for trained operators; the system never actuates.
- **Explainable where it counts.** The fire-spread forecast is a citable physical model (Balbi 2015 + standard fuel models), not a black box. Machine learning is confined to perception.
- **Honest about limits.** Model metrics, the narrow training distribution, and false-positive/negative expectations are documented in the [model card](models/MODEL_CARD.md).
- **Privacy.** Thermal imagery may incidentally capture people; downstream consumers must comply with applicable privacy law. Training data is not redistributed.

See [SECURITY.md](../../SECURITY.md) for the full AI-safety scope.

## License

Heimdall's edge stack uses **hybrid licensing** (see [LICENSE](LICENSE), [LICENSE-AGPL-3.0.txt](LICENSE-AGPL-3.0.txt), and [NOTICE](NOTICE)):

- **Apache-2.0** — original Heimdall code: the convergence engine (`convergence/`) and edge orchestration (`edge/`).
- **AGPL-3.0** — the vision-inference code path (`vision/`) and the `Heimdall-Vision-TensorRT-F16` model weights, as derivatives of [Ultralytics YOLO26](https://www.ultralytics.com/license).

The two halves communicate only over a network REST boundary (the `MeteoReport` contract).
