# XHeimdall — Architecture Design

**Phase**: `sdd-design` | **Date**: 2026-05-22 | **RFC**: RFC-001 YOLO26m Thermal Fire Detection
**Status**: DESIGNED | **Subagent**: `analista-de-ux-ui-y-arquitectura-cloud-multimodal`
**Input**: `sdd/spec.md` (2026 lines, 13 modules specified)

---

## Table of Contents

1. [Refined Architecture Diagram](#1-refined-architecture-diagram)
2. [File Structure](#2-file-structure)
3. [Technical Decisions per Module](#3-technical-decisions-per-module)
4. [Design Patterns](#4-design-patterns)
5. [Testing Strategy](#5-testing-strategy)
6. [Implementation Plan (Build Order)](#6-implementation-plan-build-order)
7. [Error Handling Strategy](#7-error-handling-strategy)
8. [Configuration Management](#8-configuration-management)
9. [Risks and Mitigations](#9-risks-and-mitigations)

---

## 1. Refined Architecture Diagram

This diagram shows the complete system with data flow direction (`──→`), protocol/format at each boundary, and each component's responsibility. This is the canonical map for all implementation work.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         PHASE 1: DATA INGEST                                  │
│                                                                              │
│  datasets/                         ┌──────────────────┐                     │
│  ├── FLAME 3/                      │                  │                     │
│  │   └── Thermal/Celsius TIFF/     │  thermal_io.py   │                     │
│  │       *.TIFF (float32, LZW) ───→│                  │                     │
│  │                                 │ read_celsius_tiff│                     │
│  ├── Hanna Hammock/                │ read_irg_temp    │                     │
│  │   └── geo_thermal_tiff_celsius/ │ find_paired_rgb  │                     │
│  │       *.TIFF (float32, LZW) ───→│                  │                     │
│  │                                 └────────┬─────────┘                     │
│  └── Frame Pairs #8/                        │                                │
│      └── *.jpg (false-color) ───→ skip TIFF │ (no temp data)                 │
│                                     │                                       │
│            OUTPUT: np.ndarray       │                                       │
│            (H, W) float32 °C        │                                       │
│                                     ▼                                       │
├──────────────────────────────────────────────────────────────────────────────┤
│                         PHASE 2: AUTO-LABEL                                   │
│                                                                              │
│                              ┌──────────────────────────────────┐           │
│                              │     auto_label.py                │           │
│                              │                                  │           │
│  np.ndarray (H,W) float32 ──→│ 1. apply_absolute_threshold      │           │
│                              │    mask = celsius > 150°C        │           │
│                              │                     │            │           │
│                              │ 2. apply_gradient_filter         │           │
│                              │    sobel(celsius) > 40°C/px      │           │
│                              │    + binary_closing(3×3)         │           │
│                              │                     │            │           │
│                              │ 3. apply_area_shape_filter       │           │
│                              │    area ≥ 50px, aspect < 8:1     │           │
│                              │                     │            │           │
│                              │ 4. cluster_fire_regions          │           │
│                              │    DBSCAN(eps=30,min=5)          │           │
│                              │    + KMeans subdivision          │           │
│                              │                     │            │           │
│  img_w, img_h ──────────────→│ 5. bboxes_to_yolo               │           │
│                              │    normalize → clamp → 6dp       │           │
│                              │                                                                     │           │
│                              │ 6. process_single_tiff (orch.)            │           │
│                              │    pipeline 1→5 + debug overlay           │           │
│                              └────────────┬─────────────────────┘           │
│                                           │                                  │
│                    OUTPUT: str (YOLO)       OUTPUT: np.ndarray (debug)       │
│                    "0 0.45 0.56 0.23 0.31"  (H,W,3) uint8 BGR               │
│                                           │                                  │
│                                           ▼                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│                         PHASE 3: DATA PREPARATION                             │
│                                                                              │
│  ┌─────────────────────────┐    ┌──────────────────────────┐                │
│  │   prepare_data.py        │    │   split_dataset.py       │                │
│  │                          │    │                          │                │
│  │ process_dataset()        │    │ split_temporal_aware()   │                │
│  │  • reads sources config  │    │  • group by filename     │                │
│  │  • for each TIFF:        │    │    prefix (flame_,       │                │
│  │    → read_celsius_tiff   │    │    hanna_plot1_, etc.)   │                │
│  │    → process_single_tiff │    │  • sort alphanumerically │                │
│  │    → write label to      │    │  • sequential split      │                │
│  │      labels/all/*.txt    │    │    70/15/15 by group     │                │
│  │    → copy JPG to         │    │  • create symlinks       │                │
│  │      images/all/*.jpg    │    │    (fallback: copy2)     │                │
│  │  • write debug images    │    │                          │                │
│  │  • generate data.yaml    │    │ validate_split()         │                │
│  │  • write metadata.json   │    │  • check leakage         │                │
│  └──────────┬───────────────┘    │  • class distribution     │                │
│             │                    │  • orphan files           │                │
│             │                    └──────────┬───────────────┘                │
│             │                               │                                │
│             ▼                               ▼                                │
│  ┌────────────────────────────────────────────────────────────┐             │
│  │                    data/ (output directory)                 │             │
│  │  ├── images/                                               │             │
│  │  │   ├── all/       (temp staging, ~1,500 JPGs)            │             │
│  │  │   ├── train/     (symlinks → all/, ~812 files)          │             │
│  │  │   ├── val/       (symlinks → all/, ~360 files)          │             │
│  │  │   └── test/      (symlinks → all/, ~360 files)          │             │
│  │  ├── labels/                                               │             │
│  │  │   ├── all/       (temp staging)                         │             │
│  │  │   ├── train/     (symlinks → all/)                      │             │
│  │  │   ├── val/                                              │             │
│  │  │   └── test/                                             │             │
│  │  ├── debug/          (optional, 10% sample)                 │             │
│  │  ├── data.yaml                                             │             │
│  │  └── metadata.json   (processing report)                   │             │
│  └──────────────────────────┬─────────────────────────────────┘             │
│                             │                                                │
│                             │ aws s3 sync (manual)                           │
│                             ▼                                                │
├──────────────────────────────────────────────────────────────────────────────┤
│                         PHASE 4: S3 STORAGE                                  │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  s3://xheimdall-datasets/yolo_dataset/                               │   │
│  │    ├── images/train/    ├── labels/train/    └── data.yaml            │   │
│  │    ├── images/val/      ├── labels/val/                               │   │
│  │    └── images/test/     └── labels/test/                              │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                         PHASE 5: SAGEMAKER TRAINING                          │
│                                                                              │
│  ┌────────────────────────┐                                                 │
│  │  launch_training.py     │   (runs LOCALLY on dev machine)                 │
│  │                         │                                                 │
│  │  launch_training_job()  │                                                 │
│  │   • reads training.yaml │                                                 │
│  │   • creates Estimator   │                                                 │
│  │   • spot=True           │                                                 │
│  │   • checkpoint_s3_uri   │                                                 │
│  │   • hyperparameters     │                                                 │
│  │     passed as env vars  │                                                 │
│  └───────────┬─────────────┘                                                 │
│              │                                                                │
│              │ SageMaker SDK API call                                        │
│              ▼                                                                │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │            SageMaker Training Job (ml.g5.12xlarge spot)               │   │
│  │                                                                       │   │
│  │  ┌────────────────────────────────────────────┐                       │   │
│  │  │  docker/Dockerfile                         │                       │   │
│  │  │  FROM ultralytics/ultralytics:latest       │                       │   │
│  │  │  + sagemaker-training + imagecodecs + ...  │                       │   │
│  │  │  → ECR: xheimdall-training:latest          │                       │   │
│  │  └────────────────────────────────────────────┘                       │   │
│  │                         │                                              │   │
│  │                         ▼                                              │   │
│  │  ┌────────────────────────────────────────────┐                       │   │
│  │  │  train_sagemaker.py  (ENTRYPOINT)           │                       │   │
│  │  │                                            │                       │   │
│  │  │  1. Read 18 env vars (SM_MODEL_DIR,        │                       │   │
│  │  │     SM_CHANNEL_TRAINING, YOLO_EPOCHS...)   │                       │   │
│  │  │  2. Load YOLO("yolo26m.pt")               │                       │   │
│  │  │  3. model.train(                           │                       │   │
│  │  │       data=data.yaml,                      │                       │   │
│  │  │       epochs=200, batch=32/GPU,            │                       │   │
│  │  │       device=0,1,2,3,                     │                       │   │
│  │  │       hsv_h=0, hsv_s=0,                   │                       │   │
│  │  │       patience=30, save_period=10)         │                       │   │
│  │  │  4. Copy best.pt → SM_MODEL_DIR/           │                       │   │
│  │  │  5. Write metrics.json                    │                       │   │
│  │  │  6. aws s3 sync checkpoint (if spot)       │                       │   │
│  │  └────────────────────┬───────────────────────┘                       │   │
│  │                       │                                                │   │
│  │                       ▼                                                │   │
│  │  ┌────────────────────────────────────────────┐                       │   │
│  │  │  SM_MODEL_DIR (/opt/ml/model/)              │                       │   │
│  │  │    ├── best.pt                             │                       │   │
│  │  │    ├── metrics.json                        │                       │   │
│  │  │    └── train/weights/last.pt               │                       │   │
│  │  └────────────────────┬───────────────────────┘                       │   │
│  │                       │                                                │   │
│  └───────────────────────┼────────────────────────────────────────────────┘   │
│                          │                                                    │
│                          │ SageMaker auto-upload                               │
│                          ▼                                                    │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  s3://xheimdall-models/                                              │   │
│  │    ├── weights/best.pt          (output from training)                │   │
│  │    ├── weights/metrics.json                                          │   │
│  │    └── checkpoints/{job_name}/  (spot recovery)                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                         PHASE 6: TENSORRT EXPORT                             │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────┐          │
│  │  export_tensorrt.py    (runs on SageMaker GPU or local GPU)    │          │
│  │                                                                │          │
│  │  export_to_tensorrt()                                          │          │
│  │   1. Download best.pt from S3 (/ or read from local path)      │          │
│  │   2. model = YOLO("best.pt")                                   │          │
│  │   3. model.export(                                             │          │
│  │        format="engine",                                        │          │
│  │        half=True,        # FP16                                │          │
│  │        imgsz=640,                                              │          │
│  │        workspace=4,      # GB                                  │          │
│  │        dynamic=False,    # fixed size for Jetson               │          │
│  │        simplify=True,    # ONNX graph optimization             │          │
│  │        opset=17,                                               │          │
│  │        batch=1)                                                │          │
│  │   4. Validate: YOLO("best.engine") loads + predicts            │          │
│  │   5. Upload best.engine → s3://xheimdall-models/engines/      │          │
│  └──────────────────────────────┬────────────────────────────────┘          │
│                                 │                                             │
│                                 │ scp / USB drive / S3 download              │
│                                 ▼                                             │
├──────────────────────────────────────────────────────────────────────────────┤
│                         PHASE 7: JETSON DEPLOYMENT                           │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                        JETSON AGX Xavier/Orin                        │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────────────────────────────┐                 │   │
│  │  │  infer_jetson.py                                 │                 │   │
│  │  │                                                  │                 │   │
│  │  │  load_model("best.engine")                       │                 │   │
│  │  │    → YOLO engine object, warm-up inference       │                 │   │
│  │  │                                                  │                 │   │
│  │  │  run_camera_loop(source, model, config)          │                 │   │
│  │  │    source = GStreamer pipeline (FLIR Boson)      │                 │   │
│  │  │    loop:                                         │                 │   │
│  │  │      frame = cap.read()     ← v4l2src /dev/video0│                 │   │
│  │  │      dets = model.predict(frame, conf=0.25)      │                 │   │
│  │  │      draw bboxes + FPS overlay                   │                 │   │
│  │  │      cv2.imshow() + cv2.waitKey(1)               │                 │   │
│  │  │                                                  │                 │   │
│  │  │  predict_frame(model, frame, conf)               │                 │   │
│  │  │    → list[dict] with xyxy + confidence           │                 │   │
│  │  └─────────────────────────────────────────────────┘                 │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────────────────────────────┐                 │   │
│  │  │  Hardware I/O                                    │                 │   │
│  │  │                                                  │                 │   │
│  │  │  FLIR Boson 640×512 @ 30Hz                       │                 │   │
│  │  │    → USB/GMSL → v4l2 /dev/video0                 │                 │   │
│  │  │    → GStreamer: videoconvert → BGR → appsink     │                 │   │
│  │  └─────────────────────────────────────────────────┘                 │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                       SHARED UTILITIES (all phases)                           │
│                                                                              │
│  ┌───────────────────────┐  ┌──────────────────────────┐                    │
│  │  utils/config.py      │  │  utils/debug_viz.py       │                    │
│  │                       │  │                           │                    │
│  │  load_yaml_config()   │  │  create_debug_overlay()   │                    │
│  │  validate_schema()    │  │   • JPG + mask + bboxes   │                    │
│  │  get_aws_credentials()│  │   • temp legend bar       │                    │
│  │    (env vars only!)   │  │   • info footer            │                    │
│  └───────────────────────┘  └──────────────────────────┘                    │
└──────────────────────────────────────────────────────────────────────────────┘

LEGEND:
  ──→  Data flow (arrays, strings, files)
  ═══→ Network transfer (S3 upload/download, ECR push/pull)
  ─ ─→ Control flow (function calls, SageMaker SDK)

PROTOCOLS AT BOUNDARIES:
  TIFF → numpy float32  :  tifffile.imread() with imagecodecs for LZW
  IRG  → numpy float32  :  pyflir.FLIRImage.get_temperature() or exiftool fallback
  numpy → YOLO string   :  custom format, 6 decimal places, single space delimiter
  numpy → debug PNG     :  cv2.imwrite(), optional output
  files → S3            :  aws s3 sync (or boto3 upload)
  S3 → SageMaker        :  SageMaker TrainingInput (File mode, S3 → EBS copy)
  .pt → .engine         :  ultralytics YOLO.export() → ONNX → TensorRT
  .engine → Jetson      :  scp or USB drive copy
  camera → Jetson       :  GStreamer pipeline (v4l2src → videoconvert → appsink)
```

---

## 2. File Structure

All files are `[new]` — this is a greenfield project with zero existing code. The spec defines 11 modules; this section assigns exact file paths and adds supplementary files needed for development.

```
XHeimdall/                                    # Project root
│
├── sdd/                                      # [existing] SDD documents
│   ├── discovery.md                          # [existing]
│   ├── proposal.md                           # [existing]
│   ├── spec.md                               # [existing]
│   └── design.md                             # [new] ← THIS FILE
│
├── src/                                      # [new] Source code
│   ├── __init__.py                           # [new] Package marker
│   │
│   ├── thermal_io.py                         # [new] TIFF/IRG readers
│   │   # Functions: read_celsius_tiff, read_irg_temperature, find_paired_rgb
│   │   # Dependencies: numpy, tifffile, imagecodecs, pyflir
│   │   # Zero internal deps → built first
│   │
│   ├── auto_label.py                         # [new] 4-filter cascade auto-labeler
│   │   # Functions: apply_absolute_threshold, apply_gradient_filter,
│   │   #   apply_area_shape_filter, cluster_fire_regions,
│   │   #   bboxes_to_yolo, process_single_tiff
│   │   # Dependencies: numpy, scipy, scikit-learn (DBSCAN/KMeans)
│   │   # Internal dep: thermal_io (for process_single_tiff only)
│   │   # Core filters work on raw arrays → testable independently
│   │
│   ├── prepare_data.py                       # [new] Dataset processor orchestrator
│   │   # Functions: process_dataset, generate_data_yaml
│   │   # Dependencies: thermal_io, auto_label, utils/config, utils/debug_viz
│   │   # Internal deps: thermal_io + auto_label + utils
│   │
│   ├── split_dataset.py                      # [new] Temporal-aware split
│   │   # Functions: split_temporal_aware, validate_split
│   │   # Dependencies: os, shutil, pathlib (stdlib only)
│   │   # Zero internal deps → independent module
│   │
│   ├── train_sagemaker.py                    # [new] SageMaker training entrypoint
│   │   # Script (no functions): entrypoint of Docker container
│   │   # Dependencies: ultralytics, pyyaml, boto3, os
│   │   # Zero internal deps → independent (runs in container)
│   │
│   ├── launch_training.py                    # [new] SageMaker job launcher
│   │   # Functions: launch_training_job
│   │   # Dependencies: sagemaker, boto3
│   │   # Internal dep: utils/config (for reading training.yaml + AWS creds)
│   │
│   ├── export_tensorrt.py                    # [new] PT → TensorRT export
│   │   # Functions: export_to_tensorrt
│   │   # Dependencies: ultralytics, onnx, tensorrt
│   │   # Zero internal deps → independent
│   │
│   ├── infer_jetson.py                       # [new] Jetson inference
│   │   # Functions: load_model, predict_frame, run_camera_loop
│   │   # Dependencies: ultralytics, cv2, numpy
│   │   # Zero internal deps → independent
│   │
│   └── utils/                                # [new] Shared utilities
│       ├── __init__.py                       # [new]
│       ├── config.py                         # [new] Config loader + AWS creds
│       │   # Functions: load_yaml_config, validate_schema, get_aws_credentials
│       │   # Dependencies: pyyaml, os (stdlib)
│       │   # Zero internal deps → independent
│       │
│       └── debug_viz.py                      # [new] Debug overlay visualizer
│           # Functions: create_debug_overlay
│           # Dependencies: cv2, numpy
│           # Zero internal deps → independent
│
├── configs/                                  # [new] Configuration files
│   ├── auto_label_fire.yaml                  # [new] Wildfire threshold config (150°C)
│   ├── auto_label_prescribed.yaml            # [new] Prescribed burn config (100°C)
│   └── training.yaml                         # [new] Training hyperparameters + SageMaker config
│
├── docker/                                   # [new] SageMaker container
│   └── Dockerfile                            # [new] FROM ultralytics/ultralytics:latest
│
├── tests/                                    # [new] Test suite
│   ├── __init__.py                           # [new]
│   ├── conftest.py                           # [new] Shared fixtures (sample TIFF data, mock configs)
│   ├── test_thermal_io.py                    # [new] Unit tests for TIFF/IRG readers
│   ├── test_auto_label.py                    # [new] Unit tests for each filter + integration
│   ├── test_prepare_data.py                  # [new] Integration tests for orchestrator
│   ├── test_split_dataset.py                 # [new] Unit tests for split logic
│   └── test_debug_viz.py                     # [new] Unit tests for overlay generation
│
├── notebooks/                                # [new] Exploration & development
│   └── exploratory_analysis.ipynb            # [new] Optional: dataset exploration (phase 1)
│
├── requirements.txt                          # [new] Python dependencies
├── .gitignore                                # [existing] Already configured
└── datasets/                                 # [existing] Git-ignored, 428 GB raw data
```

**File count**: 28 new files, 0 modified, 0 deleted.

---

## 3. Technical Decisions per Module

Each decision documents: **Problem → Alternatives → Decision → Justification → Consequences**.

### 3.1 `src/thermal_io.py`

#### D1: TIFF reading library — `tifffile` vs `rasterio`

| Aspect | Detail |
|--------|--------|
| **Problem** | LZW-compressed geo TIFFs from Hanna Hammock require a reader that supports LZW decompression. FLAME TIFFs are uncompressed float32. Both formats must be handled transparently. |
| **Alternatives** | **(A) `tifffile` + `imagecodecs`**: Pure Python, handles LZW/Deflate/PackBits, already validated during discovery. **(B) `rasterio`**: GDAL-based, heavier install (requires GDAL system lib), supports georeferencing but we don't need it. **(C) `cv2.imread`**: Cannot read float32 TIFFs — only 8-bit. |
| **Decision** | **`tifffile.imread()` + `imagecodecs`** |
| **Justification** | Already installed and verified during discovery phase. Successfully read 622 FLAME TIFFs and a sample Hanna Hammock LZW TIFF. Pure Python wheel — no system-level GDAL dependency. `rasterio` adds ~200 MB of C library dependencies for functionality we don't need (georeferenced transforms, CRS handling). |
| **Consequences** | `imagecodecs` must be in `requirements.txt` and the Dockerfile. If `imagecodecs` is missing, LZW TIFFs fail with `TiffFileError` — this is logged and returns `None` (not fatal). Uncompressed TIFFs still work without `imagecodecs`. |

#### D2: IRG extraction — `pyflir` primary vs `exiftool` fallback

| Aspect | Detail |
|--------|--------|
| **Problem** | Hanna Hammock has 818 `.irg` files (FLIR radiometric JPEGs with embedded temperature). These are an alternative data source if TIFFs fail. Need a reliable extraction path. |
| **Alternatives** | **(A) `pyflir` only**: `pyflir.FLIRImage(path).get_temperature()`. Pure Python, simple API. **(B) `exiftool` subprocess**: Extract `RawThermalImage` binary + Planck calibration constants, reconstruct Celsius via Planck's law. **(C) Both as fallback chain**: `pyflir` first, `exiftool` second. |
| **Decision** | **Two-tier fallback: `pyflir` primary, `exiftool` secondary** |
| **Justification** | `pyflir` is simpler and faster (no subprocess). But it may not support all FLIR camera models or firmware versions. `exiftool` is a mature, widely-compatible fallback. The spec already defines this two-tier approach — we formalize it here as a design decision with explicit error boundaries. |
| **Consequences** | `pyflir` goes in `requirements.txt`. `exiftool` must be on system PATH (documented as optional dependency). If neither is available, `read_irg_temperature` returns `None` with a clear log message. The `exiftool` path creates temp files — cleanup in `finally` block is critical. |

### 3.2 `src/auto_label.py`

#### D3: Clustering algorithm — DBSCAN vs HDBSCAN vs OPTICS

| Aspect | Detail |
|--------|--------|
| **Problem** | After threshold + gradient + area/shape filters, fire pixels form irregular clusters. Need spatial clustering to produce bounding boxes. Adjacent clusters should be separated; large clusters should be subdivided. |
| **Alternatives** | **(A) DBSCAN**: `eps=30` (pixel distance), `min_samples=5`. Simple, well-understood, eps has physical meaning. **(B) HDBSCAN**: Adaptive epsilon, better for variable-density clusters. But harder to tune, requires `hdbscan` package. **(C) OPTICS**: Similar to DBSCAN but hierarchical. Slower, more memory. **(D) Connected components (`scipy.ndimage.label`)**: Fastest, but generates one bbox per connected component — can't handle nearby-but-disconnected fire regions that should be grouped. |
| **Decision** | **DBSCAN with K-Means subdivision for large clusters** |
| **Justification** | DBSCAN's `eps` parameter (30px) has direct physical meaning: fire pixels within 30 pixels of each other belong to the same fire region. This is tunable via config. The K-Means subdivision handles the case where DBSCAN groups a huge fire into one cluster — it subdivides based on the `max_bbox_ratio` threshold. HDBSCAN adds a dependency for marginal benefit; our fire clusters are not highly variable in density. Connected components (`label`) was prototyped in discovery but rejected because it fails when flame regions are pixel-disconnected but semantically the same fire — DBSCAN bridges small gaps. |
| **Consequences** | `scikit-learn` added to `requirements.txt` (~5 MB). DBSCAN has O(N²) memory for N fire pixels — for images with >10,000 fire pixels, we should downsample first (documented in spec). The `max_bbox_ratio` parameter in config controls K-Means subdivision aggressiveness. |

#### D4: Gradient computation — `scipy.ndimage.sobel` vs `cv2.Sobel` vs `skimage.filters.sobel`

| Aspect | Detail |
|--------|--------|
| **Problem** | Need Sobel gradient magnitude to filter uniform warm regions. Must work on float32 arrays with NaN handling. |
| **Alternatives** | **(A) `scipy.ndimage.sobel`**: Returns float64 gradient, NaN-safe (NaN regions → 0.0). Already a dependency (`binary_closing`, `label`). **(B) `cv2.Sobel`**: Requires uint8 input, would need to normalize/scale float32 array first — loses precision. **(C) `skimage.filters.sobel`**: Same output as scipy, but adds another dependency. |
| **Decision** | **`scipy.ndimage.sobel`** |
| **Justification** | Works natively on float32 arrays — no precision loss from uint8 conversion. NaN handling is automatic (NaN * kernel = NaN, but `np.sqrt(gx²+gy²)` with NaN → we set to 0.0). `scipy` is already required for `binary_closing` and `label` in `apply_area_shape_filter`. Using `cv2.Sobel` would require: (1) normalize 0–200°C → 0–255, (2) lose float precision, (3) compute gradient on 8-bit which has banding artifacts. |
| **Consequences** | `scipy.ndimage` is in `requirements.txt` (already there for `label`). Gradient computation is ~5ms on 640×512 array — negligible in the overall pipeline. |

#### D5: Morphological closing kernel size

| Aspect | Detail |
|--------|--------|
| **Problem** | The gradient filter removes pixels at the edges of fire regions where temperature transition is gradual (<40°C/px). This can fragment bboxes. Morphological closing reconnects these fragments. |
| **Alternatives** | **(A) 3×3 kernel, 1 iteration**: Tiny fill, minimal shape distortion. **(B) 5×5 kernel, 1 iteration**: More aggressive fill, risks merging separate fires. **(C) No closing**: Accept fragmented bboxes from gradient filter. |
| **Decision** | **3×3 kernel, 1 iteration of `binary_closing`** |
| **Justification** | A 3×3 kernel with 1 iteration fills single-pixel gaps introduced by gradient filtering without merging truly separate fire regions. 5×5 risks merging fires that are 4–5 pixels apart. No closing would produce lower-quality bboxes (lots of small disconnected regions that DBSCAN then has to recluster). The spec already defines this — we confirm it as the right choice with explicit rationale. |
| **Consequences** | Uses `scipy.ndimage.binary_closing(structure=np.ones((3,3)), iterations=1)`. This is ~2ms on typical masks. |

### 3.3 `src/prepare_data.py`

#### D6: Processing strategy — Sequential with in-memory arrays

| Aspect | Detail |
|--------|--------|
| **Problem** | ~1,500 TIFFs to process. Each TIFF is ~340KB (640×512 float32). Read TIFF → run cascade → write label → copy JPG. What's the optimal processing strategy? |
| **Alternatives** | **(A) Sequential, in-memory**: Process one TIFF at a time. Load array into memory, run cascade, write output, release memory. **(B) Batch to disk**: Pre-convert all TIFFs to numpy memmap arrays, process in batch. **(C) ThreadpoolExecutor**: 4 workers processing in parallel. |
| **Decision** | **Sequential, in-memory, with progress logging every 50 images** |
| **Justification** | Each 640×512 float32 array is ~1.3 MB — trivial. The I/O (reading TIFF + writing JPG) dominates over CPU time. Threading would add complexity (shared filesystem contention on output directories, GIL limits numpy parallelism anyway) without meaningful speedup. Batch-to-disk adds intermediate storage overhead. Sequential with `tqdm`-style progress logs is the simplest debuggable approach. |
| **Consequences** | Total processing time estimate: 1,500 images × ~1 second = ~25 minutes. Acceptable for a pipeline that runs once per dataset configuration. If this becomes a bottleneck, ThreadPoolExecutor is the upgrade path (I/O-bound, GIL released during file ops). |

#### D7: data.yaml generation — Single vs dual config for SageMaker

| Aspect | Detail |
|--------|--------|
| **Problem** | `data.yaml` must have `path` set correctly. On local dev, `path` is the absolute path to `data/`. On SageMaker, `path` is `/opt/ml/input/data/training`. How to handle this? |
| **Alternatives** | **(A) Generate with placeholder, override in SageMaker**: Write `data.yaml` with `path: null` (YOLO treats null as relative to data.yaml location). This works both locally and on SageMaker. **(B) Write SageMaker path to data.yaml**: Hardcodes `/opt/ml/input/data/training` — fails locally. **(C) Generate two copies**: `data.yaml` (local) and `data_sagemaker.yaml` (cloud). |
| **Decision** | **Use `path: .` (relative) in generated data.yaml. Override via env var in SageMaker if needed.** |
| **Justification** | Ultralytics YOLO resolves `path: .` relative to the `data.yaml` file location. If `images/train/` is a sibling directory, it works. On SageMaker, `train_sagemaker.py` reads the env var `SM_CHANNEL_TRAINING` and constructs the absolute path if needed. Actually, looking at Ultralytics behavior: if `path` is set to the dataset root, YOLO prepends it to `train`/`val` paths. The simplest approach is to set `path` to the directory containing `images/` — which is `data/` locally and `/opt/ml/input/data/training/` on SageMaker. **Final decision**: generate `data.yaml` with `path: .` locally. The `prepare_data.py` script writes it to the output directory. Before uploading to S3 and running on SageMaker, `train_sagemaker.py` patches the path if needed. |
| **Consequences** | Add a line in `train_sagemaker.py` that checks if the data.yaml path needs adjusting for SageMaker's channel mount. This is a one-line fix: `data_config["path"] = os.environ["SM_CHANNEL_TRAINING"]`. |

### 3.4 `src/split_dataset.py`

#### D8: Temporal sequence detection — Filename pattern vs explicit manifest

| Aspect | Detail |
|--------|--------|
| **Problem** | Adjacent video frames must stay in the same split to prevent temporal leakage. We need to detect which frames belong to the same video sequence. |
| **Alternatives** | **(A) Filename prefix heuristic**: Parse source dataset from standardized filenames (`flame_fire_`, `hanna_plot1_`, etc.). Sort alphanumerically within group → sequential split. **(B) Explicit manifest file**: User writes a `split_manifest.yaml` listing every image and its group. **(C) EXIF timestamp extraction**: Read JPEG creation time, group by temporal proximity. |
| **Decision** | **Filename prefix heuristic with alphanumeric sort** |
| **Justification** | The `prepare_data.py` module already produces standardized filenames (`{source}_{class_or_plot}_{index}.jpg`). The source prefix (flame_, hanna_, framepairs_) cleanly separates groups. Alphanumeric sort preserves temporal order because indices are zero-padded sequential numbers. A manifest file adds maintenance burden and is error-prone (forgetting to add new files). EXIF timestamps are unreliable — some thermal cameras don't set them, and the discovery phase confirmed no EXIF metadata was checked. |
| **Consequences** | **This decision is correct IF `prepare_data.py` produces correctly standardized filenames**. If filenames deviate from the convention, grouping fails silently — `validate_split` catches this by checking leakage. This coupling is documented: `split_dataset.py` depends on `prepare_data.py`'s naming convention. |

#### D9: Symlink vs hard copy for splits

| Aspect | Detail |
|--------|--------|
| **Problem** | After splitting, do we create symlinks from `all/` to `train/val/test/` or hard-copy the files? |
| **Alternatives** | **(A) `os.symlink`**: Disk-efficient (no duplication), but Windows requires admin privileges or Developer Mode. SageMaker runs Linux (symlinks work natively). **(B) `shutil.copy2`**: Always works, duplicates 1,500 JPGs (~500 MB extra). **(C) Try symlink, fall back to copy2.** |
| **Decision** | **`os.symlink` with `shutil.copy2` fallback on `OSError`** |
| **Justification** | Symlinks save ~500 MB of duplicated JPG storage and avoid I/O overhead. On Linux (SageMaker, most dev environments) symlinks work natively. Windows 10+ with Developer Mode enabled also supports symlinks without admin. The `OSError` fallback to `copy2` ensures the pipeline never fails due to filesystem limitations. |
| **Consequences** | Adds a try/except block around symlink creation. The spec already specifies this fallback behavior — we confirm it as the design pattern. Cross-platform robustness without sacrificing Linux efficiency. |

### 3.5 `src/train_sagemaker.py`

#### D10: Multi-GPU strategy — DataParallel vs DistributedDataParallel

| Aspect | Detail |
|--------|--------|
| **Problem** | `ml.g5.12xlarge` has 4× NVIDIA A10G (24 GB each). Ultralytics supports multi-GPU training. Which strategy to use? |
| **Alternatives** | **(A) `device=[0,1,2,3]`**: Ultralytics uses PyTorch `DataParallel` internally. Single process, model replicated across GPUs, batches split automatically. **(B) `device=0` with DDP**: Launch 4 processes with `torchrun`, each process owns one GPU. Requires process management, shared filesystem for checkpoint coordination. |
| **Decision** | **`device=[0,1,2,3]` (DataParallel)** |
| **Justification** | Ultralytics' internal `device` parameter triggers `torch.nn.DataParallel` which handles 4 GPUs transparently. For single-machine training with 4 GPUs, DataParallel provides 95%+ of DDP's throughput with zero additional complexity. DDP requires: (1) launching via `torchrun --nproc_per_node=4`, (2) coordinating checkpoint saves to avoid corruption, (3) ensuring `local_rank` is read correctly. These are error-prone in a SageMaker container where the entrypoint script is simple. The 5% throughput difference is negligible for a 200-epoch training run that already takes ~6–8 hours. |
| **Consequences** | Batch size per GPU = 32. Effective batch = 128 (4 GPUs). VRAM usage per GPU ~16 GB — well within A10G's 24 GB. `device="0,1,2,3"` is set via env var `YOLO_DEVICE` with default `0,1,2,3`. |

#### D11: Checkpoint strategy for spot interruption

| Aspect | Detail |
|--------|--------|
| **Problem** | Spot instances can be interrupted with 2-minute notice. Training must resume from checkpoint, not restart. |
| **Alternatives** | **(A) SageMaker managed spot + `checkpoint_s3_uri`**: SageMaker handles the 2-minute warning signal, trainees should save state to the checkpoint path. **(B) Manual `aws s3 sync` every N epochs**: Active polling, uploads weights periodically. **(C) No checkpointing**: Accept restart on interruption (costs money). |
| **Decision** | **SageMaker managed spot checkpoints + manual `aws s3 sync` after each `save_period` (10 epochs)** |
| **Justification** | Ultralytics already saves checkpoints every `save_period` epochs to the local `runs/` directory. We add a post-save hook: after each `save_period`, run `aws s3 sync runs/weights/ s3://xheimdall-models/checkpoints/{job_name}/`. On resume, SageMaker copies the checkpoint S3 prefix back to the local directory, and Ultralytics' `resume=True` picks up from the last epoch. |
| **Consequences** | The `aws s3 sync` call adds ~5 seconds every 10 epochs (negligible). The IAM role must have `s3:PutObject` on the checkpoint path. If sync fails (e.g., network blip), training continues — worst case, we lose 10 epochs of progress on the next interruption. |

### 3.6 `docker/Dockerfile`

#### D12: Base image — `ultralytics/ultralytics:latest` vs `nvidia/cuda:12.x-runtime`

| Aspect | Detail |
|--------|--------|
| **Problem** | Need a Docker image with CUDA, cuDNN, PyTorch, and Ultralytics for SageMaker Training. Must be reproducible and versioned. |
| **Alternatives** | **(A) `ultralytics/ultralytics:latest`**: Official Ultralytics image. Pre-built with CUDA, PyTorch, Ultralytics. Just add SageMaker toolkit + extra packages. ~4 GB. **(B) `nvidia/cuda:12.1-runtime-ubuntu22.04`**: Clean CUDA base. Must manually install PyTorch, Ultralytics, all Python deps. ~2 GB base + ~3 GB deps = ~5 GB total. **(C) `pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime`**: PyTorch pre-installed. Must add Ultralytics + SageMaker deps. |
| **Decision** | **`ultralytics/ultralytics:latest`** |
| **Justification** | The Ultralytics image is maintained by the Ultralytics team and tested with their releases. It guarantees CUDA/cuDNN/PyTorch/Ultralytics version compatibility. Building from `nvidia/cuda` means we take responsibility for PyTorch-CUDA compatibility and risk version mismatches. The base image size (4 GB vs 5 GB) difference is negligible for SageMaker. The spec already specifies this — we confirm with rationale. |
| **Consequences** | Must pin to a specific tag (e.g., `ultralytics/ultralytics:8.2.0-cuda12.1`) in production — `:latest` is non-deterministic. The `Dockerfile` `FROM` line should use a pinned version. In development, `:latest` is fine. |

### 3.7 `src/export_tensorrt.py`

#### D13: Export environment — SageMaker GPU vs local workstation

| Aspect | Detail |
|--------|--------|
| **Problem** | TensorRT export requires a CUDA-capable GPU and matching TensorRT version. Where should we export? |
| **Alternatives** | **(A) On the SageMaker training instance** (as post-processing step): Export immediately after training, while GPU is still allocated. **(B) On a separate SageMaker Processing job** (`ml.g5.xlarge`): Dedicated export job, downloads best.pt from S3. **(C) On local GPU workstation**: Download best.pt, export locally, upload .engine to S3. |
| **Decision** | **Export on a separate SageMaker GPU instance (`ml.g5.xlarge`) or local GPU, NOT on the training instance** |
| **Justification** | Exporting on the training instance after training sounds efficient but has a subtle problem: the training container image (ultralytics/ultralytics) may not have TensorRT installed. Adding TensorRT to the training image bloats it and couples training + export. A separate export step is cleaner — it can use a different image (`nvidia/tensorrt:24.06-py3`) or run locally if the dev machine has a CUDA GPU. The spec's `export_tensorrt.py` is designed to run standalone with just `best.pt` as input. |
| **Consequences** | Export adds a small cost (~$2–4 for `g5.xlarge`, 1 hour). If no CUDA GPU is available locally, we must use a SageMaker Processing job or EC2 GPU instance. |

#### D14: ONNX opset version — 17+

| Aspect | Detail |
|--------|--------|
| **Problem** | TensorRT 10.0+ requires ONNX opset 17 or higher. Using an older opset causes silent failures or suboptimal graph compilation. |
| **Alternatives** | **(A) `opset=17`**: Minimum required for TensorRT 10. **(B) `opset=20`**: Latest opset, best optimization. May not be supported by older TensorRT versions on Jetson. |
| **Decision** | **`opset=17`** |
| **Justification** | opset 17 is the minimum that TensorRT 10 supports well. Jetson AGX ships with TensorRT 8.6 in JetPack 6.0, which supports opset 17. Using opset 20 risks forward-compatibility issues if Jetson TensorRT is older than the export environment's TensorRT. The spec already specifies `opset=17` — we confirm this and add that it's specifically for Jetson compatibility. |
| **Consequences** | We must log TensorRT versions on both export and Jetson sides for debugging. The `export_to_tensorrt` function should print `tensorrt.__version__` at INFO level. |

### 3.8 `src/infer_jetson.py`

#### D15: Camera input — GStreamer vs OpenCV vs Jetson Argus

| Aspect | Detail |
|--------|--------|
| **Problem** | FLIR Boson camera connects via USB/GMSL to Jetson. Need a reliable, low-latency video capture pipeline. |
| **Alternatives** | **(A) GStreamer pipeline via `cv2.VideoCapture(source, cv2.CAP_GSTREAMER)`**: Flexible pipeline, supports any v4l2 device, hardware-accelerated color conversion on Jetson. **(B) OpenCV `cv2.VideoCapture(0)` for webcam-style access**: Simple API, but no control over pixel format or buffer count. May not work with FLIR Boson's UYVY format. **(C) Jetson Argus (`nvarguscamerasrc`)**: NVIDIA's proprietary camera API. Lowest latency for CSI cameras, but FLIR Boson uses USB/UVC, not CSI. |
| **Decision** | **GStreamer via OpenCV (`cv2.CAP_GSTREAMER`)** |
| **Justification** | FLIR Boson appears as a standard UVC device (`/dev/video0`) with UYVY pixel format. GStreamer's `v4l2src` element captures this directly; `videoconvert` element does hardware-accelerated UYVY→BGR conversion on Jetson's NVENC block. The pipeline string is configurable (`source` parameter), so it works with USB webcams, IP cameras (RTSP), and video files for testing. Jetson Argus only works with CSI-connected cameras (Raspberry Pi Cam, Jetson Camera Module) — not applicable for USB FLIR Boson. |
| **Consequences** | The GStreamer pipeline string is complex but well-documented. A template pipeline is provided in the spec (DEFAULT_PIPELINE). Users must customize `device=/dev/video0` for their exact setup. Video file testing (`source="test_video.mp4"`) uses `cv2.VideoCapture` without GStreamer, which is simpler for development. |

### 3.9 `src/utils/config.py`

#### D16: Config format — YAML vs JSON vs TOML

| Aspect | Detail |
|--------|--------|
| **Problem** | Configuration files need to be human-readable, support comments, and be loadable from both local Windows and SageMaker Linux. |
| **Alternatives** | **(A) YAML**: `pyyaml`, supports comments, hierarchical, used by Ultralytics for `data.yaml`. **(B) JSON**: `json` stdlib, no comments, verbose syntax. **(C) TOML**: `tomli`/`tomllib`, supports comments, simpler than YAML, but not used anywhere else in the pipeline. |
| **Decision** | **YAML via `pyyaml`** |
| **Justification** | YAML is the native config format of Ultralytics (`data.yaml`). Having all configs in one format reduces cognitive overhead. Comments are essential for documenting thresholds and why values were chosen (e.g., `absolute_threshold: 150.0  # °C — catches 98.2% of FLAME fires`). `pyyaml` is already in `requirements.txt` for other modules. TOML is cleaner but would introduce a second config format for no benefit. |
| **Consequences** | YAML's type coercion quirks (`yes`/`no` → bool, `1.0` → float) are a known footgun. Config values should always be quoted strings or explicit types. Use `yaml.safe_load` (not `yaml.load`) to avoid arbitrary code execution. Schema validation in `validate_schema()` catches type mismatches early. |

#### D17: AWS credential loading — Environment variables only

| Aspect | Detail |
|--------|--------|
| **Problem** | AWS credentials were found exposed in `secrets/heimdall_accessKeys.csv`. Need a secure, non-exposable credential loading strategy. |
| **Alternatives** | **(A) Environment variables**: `os.environ.get("AWS_ACCESS_KEY_ID")`. Standard AWS SDK pattern. **(B) AWS credentials file**: `~/.aws/credentials`. Also standard, but not portable to SageMaker container. **(C) IAM roles (SageMaker)**: No credentials needed — SageMaker assumes the execution role. **(D) SSM Parameter Store / Secrets Manager**: Overkill for this project. |
| **Decision** | **Environment variables on local dev; IAM roles on SageMaker. Never from files in repo.** |
| **Justification** | This is non-negotiable — the spec explicitly forbids reading from the CSV file. `get_aws_credentials()` reads `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` from `os.environ`. On SageMaker, IAM roles provide credentials transparently via the metadata service — no env vars needed. On local, the user sets these in their shell profile (Windows env vars). This follows AWS SDK best practices and is already verified as working by `boto3`. |
| **Consequences** | The `secrets/` directory must remain in `.gitignore` (already there). The exposed keys have been flagged for rotation (R1 in proposal risk matrix). `get_aws_credentials()` raises `RuntimeError` if env vars are missing — this is a hard stop, not a silent fallback. |

### 3.10 Testing Framework

#### D18: Test framework — pytest vs unittest

| Aspect | Detail |
|--------|--------|
| **Problem** | Need a testing framework for unit tests and integration tests. Must support fixtures, parameterized tests, and coverage reporting. |
| **Alternatives** | **(A) `pytest`**: Third-party, fixture-based, parameterized tests via `@pytest.mark.parametrize`, `pytest-cov` for coverage. **(B) `unittest`**: stdlib, class-based, `setUp`/`tearDown`, `unittest.mock`. |
| **Decision** | **`pytest` with `pytest-cov`** |
| **Justification** | pytest's fixture system is superior for our use case: we need to share sample TIFF data (or synthetic numpy arrays) across multiple test files. `conftest.py` fixtures make this clean. Parameterized tests are essential for testing the auto-label cascade with different thresholds. pytest is the de facto Python testing standard. Both are in `requirements.txt`. |
| **Consequences** | Tests are in `tests/` directory, run with `pytest tests/ -v --cov=src`. Coverage target: ≥80% line coverage. |

---

## 4. Design Patterns

### 4.1 Pipeline Pattern (Chain of Responsibility variant)

**Where**: `auto_label.py` — the 4-filter cascade

```
apply_absolute_threshold ──→ apply_gradient_filter ──→ apply_area_shape_filter ──→ cluster_fire_regions ──→ bboxes_to_yolo
```

Each filter:
1. Receives a mask (or creates one)
2. Applies one transformation
3. Returns a refined mask (or bbox list)
4. Is a **pure function** — no side effects, no state mutation

**Why this pattern**: The filters are independently testable. Order matters (gradient must come after threshold, area/shape after gradient), and the pipeline can be extended (add a 5th filter for temporal consistency in v2) without modifying existing filters. Each filter has a clear single responsibility.

### 4.2 Strategy Pattern (config-driven thresholds)

**Where**: `auto_label.py` + `configs/auto_label_fire.yaml` + `configs/auto_label_prescribed.yaml`

Two strategies for auto-labeling:
- **Wildfire strategy** (`auto_label_fire.yaml`): threshold=150°C, gradient=40°C/px, min_area=50px
- **Prescribed burn strategy** (`auto_label_prescribed.yaml`): threshold=100°C, gradient=30°C/px, min_area=30px

The `process_single_tiff` function receives a `config: dict` that selects the strategy. No if/else branches — the behavior is entirely data-driven.

**Why this pattern**: New fire types (e.g., coal seam fires, peat fires) can be added with a new YAML config file — zero code changes. The strategy is validated against a schema (`validate_schema`) before use.

### 4.3 Factory Pattern (implicit in `read_celsius_tiff`)

**Where**: `thermal_io.py`

```python
def read_celsius_tiff(path: str) -> np.ndarray | None:
    arr = tifffile.imread(path)
    if arr.dtype == np.float32:
        return arr  # Celsius TIFF (FLAME, Hanna geo)
    elif arr.dtype == np.uint16:
        log_warning("uint16 — cannot auto-calibrate")
        return None
    elif arr.dtype == np.uint8:
        log_warning("uint8 — likely false-color, not radiometric")
        return None
    return arr  # unknown type, pass through
```

**Why this pattern**: The function inspects the dtype and decides the processing path. This is implicit factory behavior — the caller doesn't need to know what kind of TIFF they have. New TIFF types (e.g., 32-bit integer) can be added with a new elif branch.

### 4.4 Observer Pattern (progress logging)

**Where**: `prepare_data.py`

Every 50 images processed, log progress:
```python
if i % 50 == 0:
    logging.info(f"Processed {i}/{total} images. "
                 f"Fire: {fire_count}, No-fire: {nofire_count}")
```

**Why this pattern**: Long-running batch processing (~25 minutes) needs visibility. The observer (logging handler) receives periodic status updates. This is lightweight — no callback registration, just inline logging.

### 4.5 Null Object Pattern (empty label files)

**Where**: `auto_label.py` → `bboxes_to_yolo`

No-fire images produce **empty label files** (0 bytes), not absent label files. YOLO treats empty label files as negative examples. This is a Null Object pattern — an empty file is a valid "no detections" response, avoiding the need for `None` checks in the training data loader.

### 4.6 Anti-Patterns Explicitly Avoided

| Anti-Pattern | Why Avoided | Design Decision |
|-------------|-------------|-----------------|
| **God Object** (single orchestrator doing everything) | `process_single_tiff` delegates to 5 focused functions, `process_dataset` delegates to `process_single_tiff` | Pipeline + delegation |
| **Global mutable state** | All filter functions are pure; config is passed explicitly | Pure functions with explicit config |
| **Hardcoded paths** | All paths come from config files or env vars | `pathlib.Path` with relative base |
| **Swallowed exceptions** | `try/catch` only on recoverable I/O errors; config errors raise immediately | Explicit error boundaries |
| **Premature optimization** | Sequential processing with in-memory arrays is sufficient for 1,500 images | YAGNI: no threading until bottleneck proven |

---

## 5. Testing Strategy

### 5.1 Unit Tests

| Module | Test File | What's Tested | Mock/Real | Key Fixtures |
|--------|-----------|---------------|-----------|--------------|
| `thermal_io.py` | `test_thermal_io.py` | `read_celsius_tiff` with valid TIFF, corrupt TIFF, missing file, uint16 TIFF, uint8 TIFF | **Real TIFFs** from a small test subset (5 FLAME + 2 Hanna) + **synthetic numpy** for edge cases | `sample_celsius_tiff` (tmp file with float32), `missing_path`, `uint16_tiff` |
| `thermal_io.py` | `test_thermal_io.py` | `read_irg_temperature` with valid IRG, missing pyflir, corrupt IRG | **Mock pyflir** if not installed, **real IRG** if available | `mock_pyflir_image`, `sample_irg_path` |
| `thermal_io.py` | `test_thermal_io.py` | `find_paired_rgb` for FLAME pattern, Hanna pattern, unmatched | **Real directory structure** (tmpdir with known layout) | `tmp_flame_dir`, `tmp_hanna_dir` |
| `auto_label.py` | `test_auto_label.py` | `apply_absolute_threshold`: normal, all-below, NaN handling, None input | **Synthetic numpy arrays** (deterministic) | `celsius_fire_array` (200°C peak), `celsius_nofire_array` (all <50°C), `celsius_with_nan` |
| `auto_label.py` | `test_auto_label.py` | `apply_gradient_filter`: uniform region (excluded), sharp edge (included), NaN region | **Synthetic numpy arrays** with known gradients | `uniform_array`, `sharp_edge_array` |
| `auto_label.py` | `test_auto_label.py` | `apply_area_shape_filter`: small component (<min_area), large component, thin line (high aspect) | **Synthetic binary masks** | `mask_small_speck`, `mask_large_region`, `mask_thin_line` |
| `auto_label.py` | `test_auto_label.py` | `cluster_fire_regions`: two clusters, one huge cluster (K-Means trigger), empty mask | **Synthetic binary masks** | `mask_two_clusters`, `mask_huge_cluster` |
| `auto_label.py` | `test_auto_label.py` | `bboxes_to_yolo`: normal bboxes, empty list, zero-size bbox, NaN fill, min_fill_ratio filter | **Synthetic bbox dicts** | `sample_bboxes`, `bbox_zero_area` |
| `utils/config.py` | (test in `test_prepare_data.py`) | `load_yaml_config`: valid YAML, missing file, schema validation failure | **Real YAML files** (configs/*.yaml) + **temp YAML** for invalid cases | `tmp_yaml_file`, `sample_schema` |
| `utils/debug_viz.py` | `test_debug_viz.py` | `create_debug_overlay`: outputs correct shape, bboxes drawn, mask overlay applied | **Synthetic arrays** + **real JPG** | `sample_jpg_path`, `celsius_array`, `mask_array`, `bbox_list` |

### 5.2 Integration Tests

| Test | What's Tested | Implementation |
|------|---------------|----------------|
| **Auto-label end-to-end** | `process_single_tiff` on 5 real FLAME fire TIFFs + 2 no-fire TIFFs → validate YOLO string format, debug image shape | In `test_auto_label.py`, use real TIFF paths from a test data directory |
| **Dataset processing mini-run** | `process_dataset` on a small subset (3 sources → 10 images each) → validate output directory structure, data.yaml, metadata.json | In `test_prepare_data.py`, use a temporary dataset config pointing to test subset |
| **Split validation** | `split_temporal_aware` + `validate_split` on a synthetic 30-file dataset → verify no leakage, correct ratios, symlinks created | In `test_split_dataset.py`, create temp directory with standardized filenames |
| **TensorRT round-trip** | `export_to_tensorrt` → `load_model` → `predict_frame` on a **tiny YOLO model** (YOLO26n, 5 epochs for speed) → verify engine loads and outputs valid format | Separate `tests/test_export_integration.py` — requires CUDA GPU |

### 5.3 E2E Tests (Smoke Test)

A single script `tests/smoke_test.py` that:
1. Loads a small pre-prepared dataset (10 images, 5 fire + 5 no-fire, with pre-computed labels)
2. Trains YOLO26n for 1 epoch (smoke test — just verify pipeline works)
3. Exports to TensorRT
4. Runs inference on 2 frames
5. Asserts no crashes

This is run **before** the full pipeline to catch configuration and dependency issues early.

### 5.4 Test Data Strategy

| Data Type | Source | Size | Purpose |
|-----------|--------|------|---------|
| **Synthetic numpy arrays** | Generated in `conftest.py` fixtures | 0 bytes on disk | Deterministic unit tests for filter logic |
| **Real TIFF subset** | 5 FLAME fire + 2 FLAME no-fire + 2 Hanna Hammock TIFFs | ~3 MB | Validates TIFF reading pipeline with real data |
| **Real JPG subset** | Paired false-color JPGs from the same 9 images | ~1 MB | Validates debug overlay generation |
| **Tiny pre-labeled dataset** | 10 images with hand-verified YOLO labels | ~5 MB | Integration and smoke tests |

**The test data subset** is stored in `tests/data/` (committed to git). The full 428 GB dataset remains in `datasets/` (git-ignored).

### 5.5 Coverage Targets

| Module | Line Coverage Target | Notes |
|--------|---------------------|-------|
| `thermal_io.py` | ≥90% | Simple functions, well-defined error paths |
| `auto_label.py` | ≥85% | Complex functions; some edge cases hard to trigger with synthetic data |
| `prepare_data.py` | ≥75% | Heavy I/O — integration tests cover the real paths |
| `split_dataset.py` | ≥85% | Logic-heavy, I/O-light |
| `utils/config.py` | ≥90% | Simple validation logic |
| `utils/debug_viz.py` | ≥70% | Visual output — manual inspection is the real test |
| **Overall** | **≥80%** | |

### 5.6 CI/CD Testing (Future)

Not part of v1 initial implementation. When CI is added:
- Run unit tests on every push (CPU-only, using synthetic data)
- Skip integration tests that require CUDA GPU
- SageMaker training job tests run manually (costs money)

---

## 6. Implementation Plan (Build Order)

Dependencies drive the order. A module can only be built after its dependencies exist.

```
DEPENDENCY GRAPH:

  utils/config.py        ← ZERO deps (stdlib + pyyaml)
  utils/debug_viz.py     ← ZERO deps (cv2 + numpy, but doesn't depend on our code)
  thermal_io.py          ← ZERO internal deps (only numpy + tifffile)
  split_dataset.py       ← ZERO internal deps (stdlib only)
  auto_label.py          ← DEPENDS ON: thermal_io (for process_single_tiff only;
                           core filters are independent on raw arrays)
  prepare_data.py        ← DEPENDS ON: thermal_io, auto_label, utils/config, utils/debug_viz
  launch_training.py     ← DEPENDS ON: utils/config (for reading training.yaml + AWS creds)
  train_sagemaker.py     ← ZERO internal deps (runs in isolated container)
  docker/Dockerfile      ← DEPENDS ON: train_sagemaker.py (copied into container)
  export_tensorrt.py     ← ZERO internal deps (needs best.pt from training output)
  infer_jetson.py        ← ZERO internal deps (needs best.engine from export)
```

### Build Sequence

```
STEP 0: PROJECT SCAFFOLDING                        [~1 hour]
  ├── Create directory structure (src/, src/utils/, tests/, configs/, docker/)
  ├── Create all __init__.py files
  ├── Create requirements.txt
  └── Verify: pytest can discover tests/

STEP 1: CONFIGURATION LAYER                        [~2 hours]
  ├── utils/config.py          ← BUILDS FIRST
  │   ├── load_yaml_config()   — YAML loading + validation
  │   ├── validate_schema()    — schema checking
  │   └── get_aws_credentials() — env var reading
  ├── configs/auto_label_fire.yaml
  ├── configs/auto_label_prescribed.yaml
  └── configs/training.yaml
  ✓ UNBLOCKS: prepare_data.py, launch_training.py

STEP 2: THERMAL I/O                                 [~3 hours]
  ├── thermal_io.py            ← BUILDS SECOND
  │   ├── read_celsius_tiff()  — tifffile + imagecodecs
  │   ├── read_irg_temperature() — pyflir + exiftool fallback
  │   └── find_paired_rgb()    — heuristic matching
  └── tests/test_thermal_io.py
  ✓ UNBLOCKS: auto_label.py, prepare_data.py

STEP 3: AUTO-LABEL PIPELINE                          [~6 hours]
  ├── auto_label.py             ← BUILDS THIRD
  │   ├── apply_absolute_threshold()   ← testable with synthetic arrays NOW
  │   ├── apply_gradient_filter()      ← testable with synthetic arrays NOW
  │   ├── apply_area_shape_filter()    ← testable with synthetic arrays NOW
  │   ├── cluster_fire_regions()       ← testable with synthetic arrays NOW
  │   ├── bboxes_to_yolo()             ← testable with synthetic bboxes NOW
  │   └── process_single_tiff()        ← needs thermal_io + above 5 functions
  └── tests/test_auto_label.py
  ✓ UNBLOCKS: prepare_data.py
  ✓ NOTE: Core filters (1-5) can be developed and tested in parallel with STEP 2

STEP 4: DATA PREPARATION                           [~5 hours]
  ├── prepare_data.py          ← BUILDS FOURTH
  │   ├── process_dataset()    — main orchestrator
  │   └── generate_data_yaml() — YOLO config writer
  ├── split_dataset.py         ← independent, can build in parallel
  │   ├── split_temporal_aware()
  │   └── validate_split()
  └── tests/test_prepare_data.py, test_split_dataset.py
  ✓ UNBLOCKS: dataset ready for S3 upload → training

STEP 5: DEBUG VISUALIZATION                         [~2 hours]
  ├── utils/debug_viz.py       ← can build anytime, parallel to STEP 2-4
  │   └── create_debug_overlay()
  └── tests/test_debug_viz.py

STEP 6: DOCKER CONTAINER                            [~2 hours]
  ├── docker/Dockerfile         ← BUILDS FIFTH
  │   └── FROM ultralytics/ultralytics:latest + sagemaker-training
  ├── Build + push to ECR
  └── Verify: docker run --gpus all test locally (if GPU available)

STEP 7: SAGEMAKER TRAINING                           [~3 hours]
  ├── train_sagemaker.py        ← BUILDS SIXTH
  │   └── Entrypoint script with env var reading + YOLO train
  ├── launch_training.py        ← BUILDS SIXTH (parallel)
  │   └── launch_training_job() — SageMaker SDK
  └── Manual validation: launch a 5-epoch test job on ml.g5.xlarge

STEP 8: TRAINING RUN (OPERATIONAL, NOT CODE)        [~8 hours compute]
  ├── Upload dataset to S3 (aws s3 sync, ~1 hour)
  ├── Launch full training job on ml.g5.12xlarge spot
  └── Monitor: CloudWatch logs, checkpoints to S3

STEP 9: TENSORRT EXPORT                             [~2 hours]
  ├── export_tensorrt.py       ← BUILDS SEVENTH
  │   └── export_to_tensorrt() — PT → ONNX → TensorRT
  └── Verify: best.engine loads and infers on test frame

STEP 10: JETSON INFERENCE                            [~3 hours]
  ├── infer_jetson.py           ← BUILDS EIGHTH
  │   ├── load_model()
  │   ├── predict_frame()
  │   └── run_camera_loop()
  └── Deploy to Jetson AGX + test with video file + live camera

STEP 11: FINAL INTEGRATION SMOKE TEST               [~2 hours]
  └── tests/smoke_test.py — end-to-end pipeline validation
```

### Parallelization Opportunities

| Group | Modules | Can Run Concurrently |
|-------|---------|---------------------|
| **Group A** | `utils/config.py`, `thermal_io.py`, `split_dataset.py`, `utils/debug_viz.py` | Yes — zero inter-dependencies |
| **Group B** | `auto_label.py` core filters (functions 1-5) | Yes — work on synthetic arrays |
| **Group C** | `docker/Dockerfile`, `train_sagemaker.py`, `launch_training.py` | Yes — after Group A configs are done |
| **Group D** | `export_tensorrt.py`, `infer_jetson.py` | After training produces best.pt |

### Critical Path

```
config.py (2h) → thermal_io.py (3h) → auto_label.py (6h) → prepare_data.py (5h)
    → dataset processed → S3 upload → training (8h) → best.pt
    → export_tensorrt.py (2h) → infer_jetson.py (3h)
```

Total path excluding training compute: **~23 hours of dev time**.

---

## 7. Error Handling Strategy

### 7.1 Error Classification

| Category | Examples | Handling | Recovery |
|----------|----------|----------|----------|
| **FATAL_CONFIG** | Missing required config key, `nc != len(names)`, invalid paths | Raise `ValueError` or `RuntimeError` immediately | Fix config, re-run |
| **FATAL_ENV** | Missing AWS credentials, no CUDA GPU for training | Raise `RuntimeError` with clear message | Set env vars, provision GPU |
| **RECOVERABLE_IO** | Corrupt TIFF, missing file, network timeout | Log `WARNING`, return `None` or empty result, continue with next item | Pipeline continues; failed items in error report |
| **RECOVERABLE_DATA** | uint16 TIFF (non-calibrated), empty fire mask, DBSCAN all-noise | Log `WARNING` or `INFO`, return `None` or empty list | Pipeline continues; counted in `skipped` stats |
| **SPOT_INTERRUPTION** | SageMaker spot instance reclaimed | Save checkpoint to S3, exit with code 0 | SageMaker resumes job from checkpoint |

### 7.2 Logging Levels

| Level | When | Example |
|-------|------|---------|
| `CRITICAL` | Temporal leakage detected in split validation | `"LEAKAGE: flame_fire appears in train AND val!"` |
| `ERROR` | Source directory not found, disk full, config missing required key | `"Source directory not found: datasets/FLAME/"` |
| `WARNING` | Corrupt TIFF skipped, uint16 TIFF skipped, no-fire missing from train split | `"Corrupt TIFF skipped: flame_fire_042.TIFF"` |
| `INFO` | Processing progress (every 50 images), training metrics, export completed | `"Processed 50/1500 images. Fire: 48, No-fire: 2"` |
| `DEBUG` | Detailed per-image filter results (for HITL debugging) | `"fire_001: 3 bboxes, 1247 fire pixels, fill=0.34"` |

### 7.3 Module-Specific Error Handling

#### `thermal_io.py`
```python
# Pattern: Return None on recoverable errors, log and continue
def read_celsius_tiff(path: str) -> np.ndarray | None:
    try:
        arr = tifffile.imread(path)
    except FileNotFoundError:
        logging.warning(f"TIFF not found: {path}")
        return None
    except tifffile.TiffFileError as e:
        logging.warning(f"Corrupt TIFF: {path} — {e}")
        return None
    except ImportError:
        logging.error("imagecodecs not installed — LZW TIFFs will fail")
        raise  # Fatal — dependency missing
    # dtype and shape validation...
    return arr
```

#### `auto_label.py`
```python
# Pattern: Validate inputs early, raise on invalid params
def apply_absolute_threshold(celsius: np.ndarray, threshold: float) -> np.ndarray:
    if celsius is None:
        raise ValueError("celsius array is None")
    if celsius.ndim != 2:
        raise ValueError(f"Expected 2D array, got {celsius.ndim}D")
    # Proceed with computation...
```

#### `prepare_data.py`
```python
# Pattern: Collect errors, report at end
def process_dataset(dataset_config: dict) -> dict:
    errors = []
    skipped = []
    for source in dataset_config["sources"]:
        try:
            process_source(source)
        except FileNotFoundError as e:
            errors.append(f"Source not found: {e}")
            continue  # Try next source
        except Exception as e:
            skipped.append(f"Skipped {source['name']}: {e}")
            continue
    return {"errors": errors, "skipped": skipped, ...}
```

#### `train_sagemaker.py`
```python
# Pattern: Let SageMaker handle failures. Write status files.
try:
    results = model.train(...)
    # Write success marker
    with open(os.path.join(os.environ["SM_MODEL_DIR"], "SUCCESS"), "w") as f:
        f.write("Training completed successfully")
except Exception as e:
    logging.exception("Training failed")
    # Write failure marker for SageMaker
    with open(os.path.join(os.environ["SM_OUTPUT_DATA_DIR"], "FAILURE"), "w") as f:
        f.write(str(e))
    raise  # SageMaker marks job as failed
```

### 7.4 SageMaker Spot Interruption Handling

```python
# In train_sagemaker.py — periodic checkpoint with S3 sync
# Ultralytics saves checkpoints every `save_period` epochs to SM_MODEL_DIR/runs/
# After each save, we sync to S3

import signal
import subprocess

def handle_spot_interruption(signum, frame):
    """SageMaker sends SIGTERM 2 minutes before spot termination."""
    logging.warning("Spot interruption signal received — syncing checkpoints to S3")
    checkpoint_s3 = os.getenv("OUTPUT_CHECKPOINT_S3")
    if checkpoint_s3:
        # Sync last checkpoint
        subprocess.run([
            "aws", "s3", "cp",
            os.path.join(os.environ["SM_MODEL_DIR"], "train", "weights", "last.pt"),
            checkpoint_s3,
        ], check=False)
    # SageMaker will resume from checkpoint_s3_uri on next attempt

signal.signal(signal.SIGTERM, handle_spot_interruption)
```

---

## 8. Configuration Management

### 8.1 Config File Flow

```
LOCAL DEV                                     SAGEMAKER CLOUD
──────────                                    ────────────────

configs/
├── auto_label_fire.yaml ──→ prepare_data.py
├── auto_label_prescribed.yaml ──→ prepare_data.py
└── training.yaml ──→ launch_training.py ──→ env vars ──→ train_sagemaker.py
                           │                                   │
                           │  Reads sagemaker: section         │  Reads env vars:
                           │  to configure Estimator           │  YOLO_EPOCHS, YOLO_BATCH,
                           │                                   │  YOLO_DEVICE, etc.
                           ▼                                   ▼
                    SageMaker Estimator              YOLO model.train()
                    (instance_type, spot,            (data, epochs, batch,
                     checkpoint_s3_uri)                hsv_h=0, hsv_s=0, ...)
```

### 8.2 Two Auto-Label Config Profiles

| Parameter | Wildfire (`auto_label_fire.yaml`) | Prescribed (`auto_label_prescribed.yaml`) |
|-----------|-----------------------------------|-------------------------------------------|
| `absolute_threshold` | 150.0°C | 100.0°C |
| `gradient_threshold` | 40.0°C/px | 30.0°C/px |
| `min_area` | 50 px | 30 px |
| `dbscan_eps` | 30 px | 25 px |
| `dbscan_min_samples` | 5 | 3 |
| **Rationale** | Hot, intense wildfires with sharp thermal edges | Cooler prescribed burns with gentler gradients |

The `process_dataset` function selects the config based on the source definition:
```python
# In prepare_dataset.yaml (config for process_dataset)
sources:
  - name: "flame"
    config: "configs/auto_label_fire.yaml"  # ← Selects wildfire strategy
  - name: "hanna_plot1"
    config: "configs/auto_label_prescribed.yaml"  # ← Selects prescribed strategy
```

### 8.3 Training Hyperparameters — Where Defined, How Versioned

| Layer | What's Defined | File |
|-------|---------------|------|
| **Source of truth** | All hyperparameters with defaults | `configs/training.yaml` |
| **SageMaker launch** | Reads `training.yaml`, passes as env vars | `launch_training.py` |
| **SageMaker runtime** | Reads env vars with fallback defaults | `train_sagemaker.py` |
| **Versioning** | Git commits track hyperparameter changes | `git log configs/training.yaml` |

Every training run's hyperparameters are also captured in the SageMaker training job metadata (visible in AWS Console) and in `metrics.json` written to S3. This creates an audit trail: given a `best.pt`, you can trace back to the exact hyperparameters used.

### 8.4 Environment Variables Contract

| Variable | Required | Default | Set By | Consumed By |
|----------|----------|---------|--------|-------------|
| `AWS_ACCESS_KEY_ID` | Yes (local) | — | User shell profile | `utils/config.py`, `boto3` |
| `AWS_SECRET_ACCESS_KEY` | Yes (local) | — | User shell profile | `utils/config.py`, `boto3` |
| `AWS_DEFAULT_REGION` | No | `us-east-1` | User shell profile | `boto3` |
| `SM_MODEL_DIR` | Yes (SageMaker) | — | SageMaker platform | `train_sagemaker.py` |
| `SM_CHANNEL_TRAINING` | Yes (SageMaker) | — | SageMaker platform | `train_sagemaker.py` |
| `YOLO_EPOCHS` | No | `200` | `launch_training.py` | `train_sagemaker.py` |
| `YOLO_BATCH` | No | `32` | `launch_training.py` | `train_sagemaker.py` |
| `YOLO_IMGSZ` | No | `640` | `launch_training.py` | `train_sagemaker.py` |
| `YOLO_PATIENCE` | No | `30` | `launch_training.py` | `train_sagemaker.py` |
| `YOLO_LR0` | No | `0.01` | `launch_training.py` | `train_sagemaker.py` |
| `YOLO_DEVICE` | No | `0,1,2,3` | `launch_training.py` | `train_sagemaker.py` |
| `YOLO_NUM_WORKERS` | No | `8` | `launch_training.py` | `train_sagemaker.py` |
| `YOLO_PRETRAINED` | No | `true` | `launch_training.py` | `train_sagemaker.py` |
| `YOLO_SAVE_PERIOD` | No | `10` | `launch_training.py` | `train_sagemaker.py` |
| `OUTPUT_CHECKPOINT_S3` | No | — | `launch_training.py` | `train_sagemaker.py` |

---

## 9. Risks and Mitigations

This section augments the proposal's risk matrix (§5) with **implementation-specific risks** discovered during design.

### 9.1 New Risks from Design Phase

| # | Risk | Probability | Impact | Mitigation |
|---|------|-------------|--------|------------|
| **R11** | **Symlink creation fails on Windows Dev** | **Medium** | Low — stops local `split_dataset.py` testing | Implement `shutil.copy2` fallback (already in design §3.4 D9). Windows users must enable Developer Mode. |
| **R12** | **DBSCAN O(N²) memory on huge fire images** | **Low** | Medium — OOM crash on images with >10,000 fire pixels | Add pixel count check before DBSCAN: if N > 10,000, downsample mask by 2× with `scipy.ndimage.zoom` before clustering. Document in code comments. |
| **R13** | **TensorRT version mismatch export → Jetson** | **Medium** | High — engine fails to load silently (cryptic CUDA error) | Log `tensorrt.__version__` on both export and Jetson load. Document required TensorRT version in deployment README. Implement `torch.cuda.is_available()` check with helpful error message. |
| **R14** | **yolo26m.pt download fails in SageMaker container** | **Medium** | High — training job fails before starting | Pre-download yolo26m.pt to S3, mount as separate SageMaker channel. Fallback: bake the base weights into the Docker image (adds ~50 MB). |
| **R15** | **GStreamer pipeline wrong for user's camera** | **High** | Medium — `run_camera_loop` fails to open camera | Provide 3 template pipelines (FLIR Boson USB, generic v4l2, IP camera RTSP). User selects via config. Add `--list-cameras` mode that enumerates `/dev/video*` devices. |
| **R16** | **prepare_data.py runs for 25 min without progress** | **Low** | Low — user thinks it hung | Log progress every 50 images (already in design). Add `tqdm` progress bar as optional dependency. |

### 9.2 Risk R13 Deep Dive — TensorRT Version Compatibility

This is the highest-impact design risk. The path: `best.pt → ONNX → TensorRT engine` involves three version-sensitive steps:

```
PyTorch version → ONNX opset compatibility
ONNX opset → TensorRT builder compatibility
TensorRT builder version → TensorRT runtime version (Jetson)
```

**Mitigation Strategy**:
1. **Pin TensorRT versions**: Export on the same JetPack version that runs on the Jetson. JetPack 6.0 ships TensorRT 8.6. Export using `nvidia/tensorrt:24.06-py3` Docker image (which includes TensorRT 10.x — cross-compilation for Jetson's 8.6 is supported via compatibility mode).
2. **Build on Jetson directly** (Plan B): If cross-compilation fails, install `ultralytics` on Jetson and export the engine there. This guarantees version match but is slower (Jetson CPU/GPU is less powerful than A10G).
3. **Version check at load time**: `infer_jetson.py` logs `torch.__version__`, `tensorrt.__version__`, and CUDA version. If engine load fails, the error message includes version troubleshooting instructions.
4. **Fallback to ONNX**: If TensorRT engine fails, Jetson can run ONNX via `onnxruntime-gpu`. Lower FPS but guaranteed to work.

### 9.3 Risk R15 Deep Dive — GStreamer Pipeline

The FLIR Boson outputs UYVY format at 640×512 @ 30Hz. The GStreamer pipeline in the spec is:
```
v4l2src device=/dev/video0 ! video/x-raw,format=UYVY,width=640,height=512,framerate=30/1 ! videoconvert ! video/x-raw,format=BGR ! appsink drop=1 max-buffers=2
```

**What can go wrong**:
- Device node is `/dev/video1` instead of `/dev/video0`
- Camera outputs YUYV instead of UYVY
- Resolution is different (e.g., 320×256 in low-power mode)
- Camera requires specific v4l2 controls (gain, exposure)

**Mitigation**:
1. `run_camera_loop` accepts `source` as a string — the user can pass any GStreamer pipeline.
2. A helper function `detect_thermal_camera()` probes `/dev/video*` devices with `v4l2-ctl --list-formats` and suggests a pipeline.
3. Video file fallback: `source="test_video.mp4"` works with `cv2.VideoCapture` without GStreamer for development.
4. Config-driven: the pipeline string lives in a config file or env var, not hardcoded.

---

## Appendix A: Dependency Graph (Module-Level)

```
                    ┌──────────────────┐
                    │  utils/config.py │  (stdlib + pyyaml)
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
    ┌─────────────┐  ┌───────────┐  ┌────────────────┐
    │prepare_data │  │launch_    │  │ (used by config │
    │    .py      │  │training.py│  │  validation)    │
    └──────┬──────┘  └───────────┘  └────────────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
┌────────┐  ┌──────────────┐
│thermal │  │ auto_label   │
│_io.py  │  │    .py       │
└────────┘  └──────┬───────┘
                   │
         ┌─────────┴─────────┐
         │                   │
         ▼                   ▼
┌──────────────┐   ┌─────────────────┐
│prepare_data  │   │ utils/debug_viz │
│   .py        │   │     .py         │
└──────┬───────┘   └─────────────────┘
       │
       ▼
┌──────────────┐
│split_dataset │
│    .py       │
└──────────────┘

--- S3 BOUNDARY ---

┌────────────────┐     ┌──────────────────┐
│launch_training │────▶│train_sagemaker   │
│    .py         │     │    .py           │
└────────────────┘     └────────┬─────────┘
                                │ best.pt
                                ▼
                       ┌────────────────┐
                       │export_tensorrt │
                       │    .py         │
                       └────────┬───────┘
                                │ best.engine
                                ▼
                       ┌────────────────┐
                       │ infer_jetson   │
                       │    .py         │
                       └────────────────┘

LEGEND:
  ──→  Import dependency
  ═══→ Data artifact dependency (file produced by one module, consumed by another)
```

---

## Appendix B: Key Design Trade-offs Accepted

| Trade-off | Accepted Because |
|-----------|-----------------|
| **DataParallel over DDP** | Simpler container, 95%+ throughput on 4 GPUs, no multi-process coordination |
| **Symlinks + copy2 fallback** | Disk-efficient on Linux, graceful degradation on Windows |
| **Sequential over threaded processing** | 25-minute pipeline is acceptable; threading adds complexity without I/O benefit |
| **DBSCAN over HDBSCAN** | Simpler parameter tuning (eps=30px has physical meaning), no extra dependency |
| **Export on separate GPU** | Cleaner separation of concerns; training container stays focused on training |
| **False-color JPGs over raw TIFFs for training** | YOLO expects 8-bit 3-channel input; false-color preserves temperature information visually |
| **Single class `fire` over multi-class** | User confirmed; smoke is invisible in LWIR thermal; simplifies labeling and training |

---

*Design document generated by SDD Design subagent | `analista-de-ux-ui-y-arquitectura-cloud-multimodal` | deepseek-v4-pro | 2026-05-22*

*Ready for: `sdd-tasks` phase — Task breakdown, estimation, and assignment.*
