# XHeimdall — Technical Specification

**Phase**: `sdd-spec` | **Date**: 2026-05-22 | **RFC**: RFC-001 YOLO26m Thermal Fire Detection
**Status**: SPECIFIED | **Subagent**: `especificador-tecnico-senior`

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Data Schemas & Formats](#2-data-schemas--formats)
3. [Module: `src/thermal_io.py` — TIFF/IRG Readers](#3-module-srcthermal_iopy--tiffirg-readers)
4. [Module: `src/auto_label.py` — 4-Filter Cascade Auto-Labeler](#4-module-srcauto_labelpy--4-filter-cascade-auto-labeler)
5. [Module: `src/prepare_data.py` — Dataset Processor](#5-module-srcprepare_datapy--dataset-processor)
6. [Module: `src/split_dataset.py` — Temporal-Aware Split](#6-module-srcsplit_datasetpy--temporal-aware-split)
7. [Module: `src/train_sagemaker.py` — SageMaker Training Entrypoint](#7-module-srctrain_sagemakerpy--sagemaker-training-entrypoint)
8. [Module: `docker/Dockerfile` — SageMaker Container](#8-module-dockerdockerfile--sagemaker-container)
9. [Module: `src/launch_training.py` — SageMaker Job Launcher](#9-module-srclaunch_trainingpy--sagemaker-job-launcher)
10. [Module: `src/export_tensorrt.py` — PT → TensorRT Engine](#10-module-srcexport_tensorrtpy--pt--tensorrt-engine)
11. [Module: `src/infer_jetson.py` — Jetson Inference](#11-module-srcinfer_jetsonpy--jetson-inference)
12. [Module: `src/utils/config.py` — Configuration Loader](#12-module-srcutilsconfigpy--configuration-loader)
13. [Module: `src/utils/debug_viz.py` — Debug Visualizer](#13-module-srcutilsdebug_vizpy--debug-visualizer)
14. [Config File Schemas](#14-config-file-schemas)
15. [AWS Infrastructure Contract](#15-aws-infrastructure-contract)
16. [Acceptance Criteria](#16-acceptance-criteria)
17. [Dependencies & Prerequisites](#17-dependencies--prerequisites)
18. [Anti-Patterns & Forbidden Operations](#18-anti-patterns--forbidden-operations)

---

## 1. System Overview

### 1.1 Architecture

```
┌─ DATA INGEST ─────────────────────────────────────────────────────────┐
│  thermal_io.py    │  Reads Celsius TIFFs (float32, LZW), IRG radiometry │
│                    │  Locates paired RGB images                         │
├─ AUTO-LABEL ───────────────────────────────────────────────────────────┤
│  auto_label.py    │  4-filter cascade: temp → gradient → area/shape     │
│                    │  → DBSCAN+KMeans → YOLO labels                     │
├─ DATA PREP ────────────────────────────────────────────────────────────┤
│  prepare_data.py  │  Orchestrator: reads TIFFs, auto-labels,             │
│                    │  copies JPGs, generates debug images                │
│  split_dataset.py │  Temporal-aware train/val/test split (no leakage)   │
├─ TRAINING ─────────────────────────────────────────────────────────────┤
│  launch_training.py│ SageMaker Estimator + TrainingInput                │
│  train_sagemaker.py│ Training entrypoint (env vars, YOLO config)        │
│  docker/Dockerfile │ SageMaker custom container                         │
├─ EXPORT ───────────────────────────────────────────────────────────────┤
│  export_tensorrt.py│ best.pt → best.engine (FP16 TensorRT)              │
├─ DEPLOY ───────────────────────────────────────────────────────────────┤
│  infer_jetson.py  │ TensorRT inference, GStreamer camera loop           │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Key Constraints

| Constraint | Value | Rationale |
|------------|-------|-----------|
| HSV jitter | **DISABLED** (`hsv_h=0`, `hsv_s=0`) | Thermal false-color has no meaningful hue/saturation |
| Split strategy | **Temporal-aware ONLY** | Random split causes data leakage from adjacent frames |
| LZW TIFF support | `tifffile` + `imagecodecs` | Hanna Hammock geo TIFFs are LZW-compressed |
| Min fill ratio | **0.15** | Bbox must contain ≥ 15% fire pixels |
| Bbox coordinates | Clamped to `[0.0, 1.0]` | YOLO normalized format compliance |
| Model input | 3-channel 8-bit false-color JPGs | Not raw float32 TIFFs |
| Single class | `fire` (class_id=0) | Confirmed by user; smoke invisible in LWIR thermal |

---

## 2. Data Schemas & Formats

### 2.1 YOLO Label Format

```
<class_id> <x_center> <y_center> <width> <height>
```

| Field | Type | Range | Decimals | Description |
|-------|------|-------|----------|-------------|
| `class_id` | `int` | `0` | — | Always `0` for `fire` |
| `x_center` | `float` | `[0.0, 1.0]` | 6 | Bbox center X, normalized by image width |
| `y_center` | `float` | `[0.0, 1.0]` | 6 | Bbox center Y, normalized by image height |
| `width` | `float` | `[0.0, 1.0]` | 6 | Bbox width, normalized by image width |
| `height` | `float` | `[0.0, 1.0]` | 6 | Bbox height, normalized by image height |

**Constraints**:
- Six decimal places fixed (e.g., `0.451234`)
- Values must be clamped: `max(0.0, min(1.0, value))`
- `width` and `height` must be strictly > 0.0
- `x_center - width/2 ≥ 0.0` and `x_center + width/2 ≤ 1.0` (enforced via clamp)
- No trailing spaces, single space delimiter

**Example** (`fire_001.txt`):
```
0 0.451234 0.562109 0.234500 0.312000
0 0.123000 0.890100 0.067800 0.098700
```

**No-fire images**: Empty label file (zero bytes) — YOLO handles these as negative samples.

### 2.2 Dataset Directory Structure

```
data/
├── data.yaml                          # YOLO dataset config
├── images/
│   ├── train/
│   │   ├── flame_fire_001.jpg         # False-color JPG (640×512 or similar)
│   │   ├── flame_nofire_081.jpg
│   │   └── hanna_plot1_001.jpg
│   ├── val/
│   │   └── ...
│   └── test/
│       └── ...
├── labels/
│   ├── train/
│   │   ├── flame_fire_001.txt         # YOLO format, one line per bbox
│   │   ├── flame_nofire_081.txt       # Empty file (no-fire negative)
│   │   └── hanna_plot1_001.txt
│   ├── val/
│   │   └── ...
│   └── test/
│       └── ...
└── debug/
    ├── train/
    │   ├── flame_fire_001_debug.jpg   # TIFF + mask overlay for HITL review
    │   └── ...
    └── ...
```

**Naming convention**: `{source_dataset}_{class_or_plot}_{index}.{ext}`
- `source_dataset`: `flame`, `hanna`, `framepairs`
- `class_or_plot`: `fire`, `nofire`, `plot1`, `plot2`, `plot3`
- `index`: zero-padded 4-digit sequential number

### 2.3 S3 Bucket Structure

```
s3://xheimdall-datasets/
├── yolo_dataset/
│   ├── data.yaml
│   ├── images/
│   │   ├── train/          # ~812 training images
│   │   ├── val/            # ~360 validation images
│   │   └── test/           # ~360 test images
│   └── labels/
│       ├── train/
│       ├── val/
│       └── test/

s3://xheimdall-models/
├── weights/
│   ├── best.pt             # Best YOLO26m checkpoint
│   ├── last.pt             # Last epoch checkpoint
│   └── metrics.json        # Training metrics (mAP, loss curves)
├── engines/
│   ├── best_fp16.engine    # TensorRT FP16 engine
│   └── best_int8.engine    # TensorRT INT8 engine (future)
└── checkpoints/
    └── {job_name}/         # Per-job checkpoints for spot interruption recovery
```

### 2.4 data.yaml Schema

```yaml
# Required fields
path: /opt/ml/input/data/training    # Root dataset path (SageMaker Training channel)
train: images/train                   # Relative path from `path`
val: images/val                       # Relative path from `path`
test: images/test                     # Relative path from `path` (optional for YOLO)

# Class definition
nc: 1                                 # Number of classes
names:
  0: fire                             # Single class

# Download (not used — local/S3 datasets)
download: null
```

**Validation**:
- `nc` must match `len(names)` exactly
- `names` keys must be contiguous integers starting at 0
- `train` and `val` paths must exist relative to `path`
- `path` must be an absolute path or `null` (YOLO treats `null` as relative to `data.yaml` location)

### 2.5 Auto-Label Config Schema

```python
# TypeScript-style definition for auto_label config dict
AutoLabelConfig = {
    # Temperature thresholds
    "absolute_threshold": float,         # °C (150.0 for wildfire, 100.0 for prescribed)
    "gradient_threshold": float,         # °C/px (default 40.0)
    
    # Area & shape filters
    "min_area": int,                     # Minimum pixel area (default 50)
    "max_aspect_ratio": float,           # Max width/height or height/width (default 8.0)
    
    # Clustering
    "dbscan_eps": int,                   # DBSCAN epsilon in pixels (default 30)
    "dbscan_min_samples": int,           # DBSCAN min samples per cluster (default 5)
    "max_bbox_ratio": float,             # Max single bbox as fraction of image (default 0.4)
    "kmeans_subdivide_threshold": int,   # Pixels above which to subdivide with K-Means (default 500)
    
    # Bbox quality
    "min_fill_ratio": float,             # Min fire-pixel fill ratio within bbox (default 0.15)
    
    # Output
    "class_id": int,                     # YOLO class ID (default 0)
}
```

---

## 3. Module: `src/thermal_io.py` — TIFF/IRG Readers

### 3.1 Contract: `read_celsius_tiff`

```python
def read_celsius_tiff(path: str) -> np.ndarray | None
```

| Aspect | Detail |
|--------|--------|
| **Summary** | Read a radiometric Celsius TIFF (float32) from FLAME or Hanna Hammock. Supports uncompressed and LZW-compressed TIFFs. |
| **Parameter** | `path: str` — absolute path to `.TIFF` or `.tiff` file |
| **Returns** | `np.ndarray` of shape `(H, W)` with dtype `np.float32` containing temperature values in °C, or `None` if the file cannot be read |
| **Exceptions** | Never raises — returns `None` on all failure paths and logs a warning |

#### Behavior

**Preconditions**:
- File exists at `path`
- File is a TIFF with embedded temperature data (float32 or 16-bit raw sensor values)
- `tifffile` and `imagecodecs` are installed

**Normal Flow**:
1. Open file with `tifffile.imread(path)` — automatically handles LZW, Deflate, and uncompressed TIFFs
2. Inspect dtype:
   - **float32**: Return array as-is (already in °C for FLAME Celsius TIFFs and Hanna Hammock geo TIFFs)
   - **uint16** (raw sensor): Log warning — cannot be auto-calibrated to °C without camera-specific formula. Return `None`.
   - **uint8**: Log error — likely a false-color image, not radiometric. Return `None`.
3. Validate shape: must be 2D `(H, W)`. If 3D (multi-channel TIFF), take first channel and log warning.
4. Check for degenerate data:
   - All-NaN array → log warning, return `None`
   - All-identical values (e.g., all 0.0) → log warning, return `None`
5. Return the `(H, W)` float32 ndarray.

**Error Cases**:

| Error | Handling |
|-------|----------|
| `FileNotFoundError` | Log `f"TIFF not found: {path}"`, return `None` |
| `tifffile.TiffFileError` (corrupt TIFF) | Log `f"Corrupt TIFF: {path} — {error}"`, return `None` |
| `ImportError` (missing imagecodecs) | Log `"imagecodecs not installed — LZW TIFFs will fail"`, raise — this is a hard dependency |
| Non-2D array (e.g., RGB TIFF) | Take first channel if 3D, else log error and return `None` |
| Out-of-range values (< -50°C or > 2000°C) | Log warning but do not filter — auto-label thresholds handle this downstream |

**Side Effects**:
- Logs at `WARNING` level for all failures
- No filesystem writes
- No state mutation

#### Acceptance Criteria

```
AC-IO-001: Read uncompressed float32 Celsius TIFF
  Given a valid FLAME Celsius TIFF at "data/FLAME/Fire/Thermal/Celsius TIFF/fire_001.TIFF"
  When  read_celsius_tiff(path) is called
  Then  returns ndarray of shape (H, W), dtype float32
   And  all values are ≥ -50.0 °C (sanity check)
   And  at least one pixel > 150°C (fire present)

AC-IO-002: Read LZW-compressed Hanna Hammock geo TIFF
  Given a valid Hanna Hammock geo_thermal_tiff_celsius at "data/Hanna/plot1/geo_thermal_tiff_celsius/IRX_0529_ref_geo.TIFF"
  When  read_celsius_tiff(path) is called
  Then  returns ndarray of shape (531, 654), dtype float32
   And  values range 0–200°C approximately
   And  no decompression errors

AC-IO-003: Handle missing file
  Given a path that does not exist "data/nonexistent.TIFF"
  When  read_celsius_tiff(path) is called
  Then  returns None
   And  a WARNING-level log message is emitted with the file path
   And  no exception is raised

AC-IO-004: Handle 16-bit raw sensor TIFF (non-calibrated)
  Given a Hanna Hammock raw_thermal_tiff with dtype uint16
  When  read_celsius_tiff(path) is called
  Then  returns None
   And  a WARNING log indicates "cannot auto-calibrate uint16 to Celsius"
```

### 3.2 Contract: `read_irg_temperature`

```python
def read_irg_temperature(path: str) -> np.ndarray | None
```

| Aspect | Detail |
|--------|--------|
| **Summary** | Extract radiometric temperature data from FLIR IRG (JPEG with embedded radiometric metadata). Uses `pyflir` or `exiftool` to extract the raw sensor + calibration parameters and reconstruct a Celsius float32 array. |
| **Parameter** | `path: str` — absolute path to `.irg` file |
| **Returns** | `np.ndarray` of shape `(H, W)` with dtype `np.float32` containing temperature values in °C, or `None` if extraction fails |

#### Behavior

**Preconditions**:
- File exists and has `.irg` extension
- File is a valid FLIR radiometric JPEG with embedded `RawThermalImage` and calibration metadata
- `pyflir` package is installed, or `exiftool` is on system PATH

**Normal Flow**:
1. Attempt extraction via `pyflir` (preferred — pure Python):
   ```python
   import pyflir
   img = pyflir.FLIRImage(path)
   celsius = img.get_temperature()  # Returns float32 ndarray in °C
   ```
2. If `pyflir` fails or is not installed, fall back to `exiftool` subprocess:
   ```bash
   exiftool -b -RawThermalImage path > raw.bin
   exiftool -PlanckR1 -PlanckB -PlanckF -PlanckO -PlanckR2 path
   ```
   Parse calibration constants and reconstruct temperature via Planck's law.
3. Validate output: at least 50% of values must be in range `[-50, 500]` °C. If not, log warning.
4. Return `(H, W)` float32 ndarray.

**Error Cases**:

| Error | Handling |
|-------|----------|
| `pyflir` not installed AND `exiftool` not on PATH | Log `"Neither pyflir nor exiftool available for IRG extraction"`, return `None` |
| Corrupt IRG (missing `RawThermalImage`) | Log warning, return `None` |
| Calibration constants parse failure | Log warning with raw values, return `None` |

**Side Effects**:
- If using `exiftool` path: creates temporary binary files — clean up in `finally` block
- Logs at `WARNING` for failures, `INFO` for successful extraction

### 3.3 Contract: `find_paired_rgb`

```python
def find_paired_rgb(thermal_path: str) -> str | None
```

| Aspect | Detail |
|--------|--------|
| **Summary** | Given a thermal image path, locate the corresponding RGB image from the paired directory structure. Used for debug visualization and optional RGB+Thermal fusion (future v2). |
| **Parameter** | `thermal_path: str` — absolute path to a thermal image (TIFF, JPG, or IRG) |
| **Returns** | `str` — absolute path to the paired RGB image, or `None` if no pair found |

#### Behavior

**Preconditions**:
- `thermal_path` points to a valid file
- The directory structure follows known patterns (FLAME, Hanna Hammock, Frame Pairs)

**Normal Flow**:
1. Determine source dataset from path:
   - **FLAME**: `Thermal/Celsius TIFF/fire_001.TIFF` → `RGB/Corrected FOV/fire_001.jpg`
   - **Hanna Hammock**: `plot1/geo_thermal_tiff_celsius/IRX_0529_ref_geo.TIFF` → `plot1/raw_rgb_jpg/IRX_0529_ref_geo.jpg` (match by basename)
   - **Frame Pairs #8**: `Original Sized Thermal Images/Thermal Frame (1).jpg` → `Original Sized RGB Images/RGB Frame (1).jpg` (match by number)
2. Extract identifier from thermal filename:
   - FLAME: numeric index in filename
   - Hanna Hammock: full stem (before extension)
   - Frame Pairs: number in parentheses
3. Glob for matching RGB file in expected paired directory.
4. Return the first match if exactly one match; if multiple, log warning and return first; if zero, return `None`.

**Error Cases**:
- Source dataset not recognized → log warning, return `None`
- Expected RGB directory does not exist → log warning, return `None`
- Multiple matching RGB files → log warning with paths, return first match

**Side Effects**: None.

---

## 4. Module: `src/auto_label.py` — 4-Filter Cascade Auto-Labeler

### 4.1 Contract: `apply_absolute_threshold`

```python
def apply_absolute_threshold(celsius: np.ndarray, threshold: float) -> np.ndarray
```

| Aspect | Detail |
|--------|--------|
| **Summary** | Create a binary mask where temperature exceeds the given threshold. This is the first and most critical filter in the cascade. |
| **Parameters** | `celsius: np.ndarray` — `(H, W)` float32 array of temperature values in °C. `threshold: float` — cutoff temperature (150.0 for wildfire, 100.0 for prescribed). |
| **Returns** | `np.ndarray` — `(H, W)` binary mask, dtype `np.uint8` (or `bool`) where `True`/`1` = fire candidate pixel |

#### Behavior

**Preconditions**:
- `celsius` is a valid 2D float32 ndarray (from `read_celsius_tiff`)
- `threshold` is a positive float
- NaN values in `celsius` are handled: `np.isnan(celsius)` → treated as `False` (below threshold)

**Normal Flow**:
```python
mask = (celsius > threshold) & (~np.isnan(celsius))
return mask.astype(np.uint8)
```

**Error Cases**:
- `celsius` is `None` → raise `ValueError("celsius array is None")`
- `celsius` is not 2D → raise `ValueError(f"Expected 2D array, got {celsius.ndim}D")`
- `threshold` is negative → log warning (temperatures cannot be negative in fire context), but proceed

**Side Effects**: None. Pure function.

### 4.2 Contract: `apply_gradient_filter`

```python
def apply_gradient_filter(
    thermal_img: np.ndarray,
    mask: np.ndarray,
    gradient_threshold: float = 40.0
) -> np.ndarray
```

| Aspect | Detail |
|--------|--------|
| **Summary** | Refine the binary mask by computing the Sobel gradient magnitude on the thermal image. Pixels must have both: temperature > threshold AND gradient > gradient_threshold. This eliminates large warm-but-uniform regions (e.g., heated ground, asphalt) that pass the absolute threshold but lack the sharp thermal edges characteristic of fire. |
| **Parameters** | `thermal_img: np.ndarray` — `(H, W)` float32 Celsius array. `mask: np.ndarray` — binary mask from `apply_absolute_threshold`. `gradient_threshold: float` — minimum Sobel gradient magnitude in °C/px (default 40.0). |
| **Returns** | `np.ndarray` — `(H, W)` refined binary mask, dtype `np.uint8` |

#### Behavior

**Preconditions**:
- `thermal_img` and `mask` have identical `(H, W)` shapes
- `gradient_threshold > 0`

**Normal Flow**:
1. Compute gradient magnitude:
   ```python
   from scipy.ndimage import sobel
   gx = sobel(thermal_img, axis=0)  # Vertical gradient
   gy = sobel(thermal_img, axis=1)  # Horizontal gradient
   gradient_mag = np.sqrt(gx**2 + gy**2)
   ```
2. Combine with existing mask:
   ```python
   gradient_mask = gradient_mag > gradient_threshold
   combined_mask = mask & gradient_mask
   ```
3. Apply morphological closing (3×3 kernel, 1 iteration) to fill small gaps introduced by gradient filter:
   ```python
   from scipy.ndimage import binary_closing
   combined_mask = binary_closing(combined_mask, structure=np.ones((3,3)), iterations=1)
   ```
4. Return refined mask.

**Error Cases**:
- Shape mismatch → raise `ValueError(f"Shape mismatch: thermal {thermal_img.shape} vs mask {mask.shape}")`
- `gradient_threshold ≤ 0` → raise `ValueError("gradient_threshold must be positive")`
- NaN handling: gradient of NaN regions → 0.0, so they are excluded from mask

**Side Effects**: None. Pure function.

### 4.3 Contract: `apply_area_shape_filter`

```python
def apply_area_shape_filter(
    mask: np.ndarray,
    min_area: int = 50,
    max_aspect_ratio: float = 8.0
) -> np.ndarray
```

| Aspect | Detail |
|--------|--------|
| **Summary** | Filter connected components by area (≥ min_area pixels) and aspect ratio (< max_aspect_ratio). Eliminates sensor noise (small specks) and thin linear artifacts (e.g., scan lines, edges of heated structures). |
| **Parameters** | `mask: np.ndarray` — binary mask. `min_area: int` — minimum connected component area in pixels. `max_aspect_ratio: float` — maximum width/height ratio (aspect ratio defined as `max(w,h) / min(w,h)`, clamped at minimum 1.0). |
| **Returns** | `np.ndarray` — `(H, W)` filtered binary mask, dtype `np.uint8` |

#### Behavior

**Preconditions**:
- `mask` is a binary (0/1 or bool) 2D array
- `min_area ≥ 1`
- `max_aspect_ratio ≥ 1.0`

**Normal Flow**:
1. Find connected components via `scipy.ndimage.label`:
   ```python
   labeled, num_features = label(mask)
   ```
2. For each component:
   ```python
   # Find bounding box from pixel coordinates
   ys, xs = np.where(labeled == i)
   h = ys.max() - ys.min() + 1
   w = xs.max() - xs.min() + 1
   area = len(ys)
   aspect = max(w, h) / max(min(w, h), 1)  # avoid div by zero
   ```
3. Keep component if `area >= min_area AND aspect < max_aspect_ratio`.
4. Return new mask with only kept components.

**Error Cases**:
- Zero components found → return empty mask (all zeros) with log at INFO level
- `min_area < 1` → raise `ValueError("min_area must be ≥ 1")`
- `max_aspect_ratio < 1.0` → raise `ValueError("max_aspect_ratio must be ≥ 1.0")`

**Side Effects**: None. Pure function.

### 4.4 Contract: `cluster_fire_regions`

```python
def cluster_fire_regions(
    mask: np.ndarray,
    eps: int = 30,
    min_samples: int = 5,
    max_bbox_ratio: float = 0.4
) -> list[dict]
```

| Aspect | Detail |
|--------|--------|
| **Summary** | Apply DBSCAN clustering to group nearby fire pixels. Subdivide large clusters using K-Means to produce tighter bounding boxes. This directly affects the quality of YOLO training labels. |
| **Parameters** | `mask: np.ndarray` — binary mask after area/shape filtering. `eps: int` — DBSCAN epsilon (pixels). `min_samples: int` — DBSCAN min samples per cluster. `max_bbox_ratio: float` — if any bbox dimension exceeds `max_bbox_ratio * image_dimension`, trigger K-Means subdivision. |
| **Returns** | `list[dict]` — each dict: `{"x_min": int, "y_min": int, "width": int, "height": int, "area": int, "centroid": (float, float), "cluster_size": int}` |

#### Behavior

**Preconditions**:
- `mask` contains at least one `True` pixel
- `eps > 0`, `min_samples ≥ 1`
- `0 < max_bbox_ratio ≤ 1.0`

**Normal Flow**:
1. Get pixel coordinates of all fire pixels:
   ```python
   points = np.column_stack(np.where(mask > 0))  # (N, 2) array of (y, x)
   ```
2. If `len(points) < min_samples` → return empty list.
3. Run DBSCAN:
   ```python
   from sklearn.cluster import DBSCAN
   clustering = DBSCAN(eps=eps, min_samples=min_samples, metric='euclidean').fit(points)
   ```
4. Group points by cluster label (ignore noise: label = -1).
5. For each cluster, compute bounding box in pixel coordinates:
   ```python
   cluster_points = points[labels == cluster_id]
   y_min, x_min = cluster_points.min(axis=0)
   y_max, x_max = cluster_points.max(axis=0)
   w = x_max - x_min + 1
   h = y_max - y_min + 1
   ```
6. **K-Means subdivision**: If `w > max_bbox_ratio * img_w OR h > max_bbox_ratio * img_h`:
   - Determine `k = max(2, ceil(max(w, h) / (max_bbox_ratio * max(img_w, img_h))))`
   - Run K-Means with `k` clusters on the cluster points
   - Generate separate bounding boxes for each K-Means sub-cluster
7. Return list of bounding box dicts (pixel coordinates).

**Error Cases**:
- DBSCAN returns all noise (all labels = -1) → log INFO, return empty list
- K-Means convergence failure → log warning, fall back to single bbox for the cluster
- Empty mask → return `[]`

**Side Effects**:
- `sklearn.cluster.DBSCAN` allocates `O(N²)` distance matrix memory for `N` fire pixels. For images with very large fire regions (>10,000 px), consider downsampling first.

### 4.5 Contract: `bboxes_to_yolo`

```python
def bboxes_to_yolo(
    bboxes: list[dict],
    img_w: int,
    img_h: int,
    class_id: int = 0,
    min_fill_ratio: float = 0.15
) -> str
```

| Aspect | Detail |
|--------|--------|
| **Summary** | Convert pixel-coordinate bounding boxes to YOLO normalized format string. Apply min_fill_ratio quality filter. |
| **Parameters** | `bboxes: list[dict]` — bbox dicts from `cluster_fire_regions`. `img_w: int`, `img_h: int` — image dimensions. `class_id: int` — class ID (always 0). `min_fill_ratio: float` — minimum ratio of fire pixels to bbox area for a valid bbox. |
| **Returns** | `str` — multi-line YOLO format string, one bbox per line. Empty string if no valid bboxes. |

#### Behavior

**Preconditions**:
- `bboxes` is a list (may be empty)
- `img_w > 0`, `img_h > 0`
- `0.0 ≤ min_fill_ratio ≤ 1.0`

**Normal Flow**:
1. For each bbox dict:
   ```python
   # Calculate fill ratio: fire_pixels / bbox_area
   fill = bbox["cluster_size"] / max(bbox["width"] * bbox["height"], 1)
   ```
2. Skip if `fill < min_fill_ratio`.
3. Convert to YOLO normalized:
   ```python
   x_center = (bbox["x_min"] + bbox["width"] / 2) / img_w
   y_center = (bbox["y_min"] + bbox["height"] / 2) / img_h
   norm_w = bbox["width"] / img_w
   norm_h = bbox["height"] / img_h
   ```
4. **Clamp** all values to `[0.0, 1.0]`:
   ```python
   x_center = max(0.0, min(1.0, x_center))
   y_center = max(0.0, min(1.0, y_center))
   norm_w = max(0.0, min(1.0, norm_w))
   norm_h = max(0.0, min(1.0, norm_h))
   ```
5. Format with 6 decimal places:
   ```python
   line = f"{class_id} {x_center:.6f} {y_center:.6f} {norm_w:.6f} {norm_h:.6f}"
   ```
6. Join lines with `\n`. Return joined string (or empty string).

**Error Cases**:
- `bboxes` is `None` → return `""`
- All bboxes fail `min_fill_ratio` → return `""` (valid no-fire image)
- `bbox` has zero width or height → skip, log warning
- NaN values after normalization → skip, log warning (indicates upstream calculation error)

**Side Effects**: None. Pure function.

### 4.6 Contract: `process_single_tiff`

```python
def process_single_tiff(
    tiff_path: str,
    config: dict,
    jpg_path: str | None = None,
    rgb_path: str | None = None
) -> tuple[str, np.ndarray] | None
```

| Aspect | Detail |
|--------|--------|
| **Summary** | Full pipeline orchestrator for a single TIFF: read → threshold → gradient → area/shape → cluster → YOLO format. Optionally pairs with corresponding false-color JPG and/or RGB path for debug visualization. |
| **Parameters** | `tiff_path: str` — path to Celsius TIFF. `config: dict` — auto-label config (see schema in §2.5). `jpg_path: str | None` — paired false-color JPG (for debug overlay). `rgb_path: str | None` — paired RGB image. |
| **Returns** | `tuple[str, np.ndarray]` — `(yolo_label_string, debug_overlay_rgb_image)` or `None` if processing fails |

#### Behavior

**Preconditions**:
- `tiff_path` file exists and is readable
- `config` dict contains all required keys (see §2.5)

**Normal Flow**:
1. `celsius = read_celsius_tiff(tiff_path)`. If `None`, return `None`.
2. `mask = apply_absolute_threshold(celsius, config["absolute_threshold"])`
3. `mask = apply_gradient_filter(celsius, mask, config["gradient_threshold"])`
4. `mask = apply_area_shape_filter(mask, config["min_area"], config["max_aspect_ratio"])`
5. `bboxes = cluster_fire_regions(mask, config["dbscan_eps"], config["dbscan_min_samples"], config["max_bbox_ratio"])`
6. `img_h, img_w = celsius.shape`
7. `yolo_str = bboxes_to_yolo(bboxes, img_w, img_h, config["class_id"], config["min_fill_ratio"])`
8. Generate debug overlay (if `jpg_path` provided):
   - Load false-color JPG
   - Draw bounding boxes in green (fire) with confidence-like score (fill ratio)
   - Overlay thermal mask as semi-transparent red
   - Draw temperature legend bar
   - Resize to `img_w × img_h` if needed
9. Return `(yolo_str, debug_img)` where `debug_img` is `None` if no `jpg_path`.

**Error Cases**:
- Any pipeline step returns invalid data → log error with step name, return `None`
- Config missing required keys → raise `ValueError` with missing key names
- `tiff_path` is not a valid Celsius TIFF → return `None` (logged by `read_celsius_tiff`)

**Side Effects**:
- Logs at `INFO` for each successful processing: `f"Processed {tiff_path}: {len(bboxes)} bboxes, {fire_pixel_count} fire pixels"`
- No filesystem writes (caller is responsible for writing YOLO labels and debug images)

---

## 5. Module: `src/prepare_data.py` — Dataset Processor

### 5.1 Contract: `process_dataset`

```python
def process_dataset(dataset_config: dict) -> dict
```

| Aspect | Detail |
|--------|--------|
| **Summary** | Master orchestrator: reads all Celsius TIFFs from configured source directories, runs the 4-filter auto-label pipeline on each, copies false-color JPGs to the standardized dataset directory, generates debug overlay images, and writes all YOLO label files. Returns processing statistics. |
| **Parameter** | `dataset_config: dict` — see schema in §14.1. Contains source paths, thresholds, output dir, and debug flags. |
| **Returns** | `dict` — `{"total_images": int, "fire_images": int, "nofire_images": int, "total_bboxes": int, "avg_bboxes_per_image": float, "errors": list[str], "skipped": list[str]}` |

#### Behavior

**Preconditions**:
- All source directories in `dataset_config["sources"]` exist
- Output directory (`dataset_config["output_dir"]`) is writable
- `tifffile`, `imagecodecs`, `opencv-python`, `scipy`, `scikit-learn` installed

**Normal Flow**:
1. Validate `dataset_config` against schema (use `utils/config.py`).
2. Create output directory structure:
   ```
   {output_dir}/
   ├── images/
   │   ├── train/    (empty — split happens later)
   │   ├── val/
   │   └── test/
   ├── labels/
   │   ├── train/
   │   ├── val/
   │   └── test/
   └── debug/        (if debug enabled)
   ```
3. For each source in `dataset_config["sources"]`:
   a. **FLAME source**: Process 622 fire TIFFs + 116 no-fire TIFFs
      - Threshold: `dataset_config["absolute_threshold"]` (150°C for wildfire)
      - For each fire TIFF: find paired false-color JPG → process → write label
      - For each no-fire TIFF: write empty label file (class is known: no fire)
      - Copy JPGs to `{output_dir}/images/all/` with standardized names
   b. **Hanna Hammock source**: Process 794 duringburn TIFFs
      - Threshold: `dataset_config["hanna_threshold"]` (100°C for prescribed)
      - Auto-label each and write labels
      - Include preburn/postburn frames as no-fire negatives (empty labels)
   c. **Frame Pairs #8 (optional)**: Copy false-color JPGs only (no auto-label possible)
      - Write empty labels (serve as supplementary negatives or inference test set)
4. Generate `data.yaml` via `generate_data_yaml`.
5. Generate processing report JSON at `{output_dir}/processing_report.json`.
6. Return statistics dict.

**Error Cases**:
- Source directory not found → log error, add to `errors` list, continue with next source
- Single TIFF processing fails → log error, add to `skipped` list, continue
- Disk full during copy → raise `OSError` (fatal — partial dataset is invalid)
- Zero images processed from a source → log WARNING, add to `errors`

**Side Effects**:
- Writes labels to `{output_dir}/labels/all/`
- Copies JPGs to `{output_dir}/images/all/`
- Writes debug images (if enabled) to `{output_dir}/debug/all/`
- Writes `processing_report.json` to output directory
- Logs progress every 50 images

### 5.2 Contract: `generate_data_yaml`

```python
def generate_data_yaml(
    dataset_path: str,
    nc: int,
    names: list[str],
    output_path: str
) -> None
```

| Aspect | Detail |
|--------|--------|
| **Summary** | Generate the YOLO `data.yaml` configuration file. |
| **Parameters** | `dataset_path: str` — root path for the dataset (where `images/` and `labels/` live). `nc: int` — number of classes (always 1). `names: list[str]` — class name(s) (always `["fire"]`). `output_path: str` — path to write `data.yaml`. |
| **Returns** | `None` — writes file |

#### Behavior

**Preconditions**:
- `nc == len(names)`
- `output_path` parent directory exists
- `dataset_path` is valid

**Normal Flow**:
1. Build YAML dict with `yaml.dump`:
   ```python
   data = {
       "path": dataset_path,
       "train": "images/train",
       "val": "images/val",
       "test": "images/test",
       "nc": nc,
       "names": {i: name for i, name in enumerate(names)},
       "download": None,
   }
   ```
2. Write to `output_path` with `yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)`.

**Error Cases**:
- `nc != len(names)` → raise `ValueError`
- `output_path` can't be written → raise `IOError`

---

## 6. Module: `src/split_dataset.py` — Temporal-Aware Split

### 6.1 Contract: `split_temporal_aware`

```python
def split_temporal_aware(
    data_dir: str,
    output_dir: str,
    ratios: tuple[float, float, float] = (0.7, 0.15, 0.15)
) -> dict
```

| Aspect | Detail |
|--------|--------|
| **Summary** | **CRITICAL**: Split images into train/val/test sets using temporal grouping. Adjacent frames from the same video sequence MUST stay in the same split to prevent data leakage. Uses file ordering (by name or creation time) within each group. |
| **Parameters** | `data_dir: str` — path to directory with `images/all/` and `labels/all/`. `output_dir: str` — path where `images/{train,val,test}/` and `labels/{train,val,test}/` will be created via symlinks or copies. `ratios: tuple[float,float,float]` — train/val/test proportions, must sum to 1.0. |
| **Returns** | `dict` — `{"train": int, "val": int, "test": int, "train_fire": int, "val_fire": int, "test_fire": int, "train_nofire": int, ...}` |

#### Behavior

**Preconditions**:
- `sum(ratios) == 1.0`
- `data_dir/labels/all/` contains YOLO label files (one per image)
- Files can be grouped by source dataset prefix (embedded in filename: `flame_`, `hanna_`, `framepairs_`)

**Normal Flow**:
1. Inventory all images: scan `data_dir/images/all/` for `.jpg` files.
2. For each `.jpg`, verify matching `.txt` exists in `data_dir/labels/all/`. Skip if missing.
3. **Group by video/plot** (temporal grouping):
   ```python
   # Grouping logic by filename prefix
   groups = {}
   for img in images:
       if img.startswith("flame_fire_"):
           groups.setdefault("flame_fire", []).append(img)
       elif img.startswith("flame_nofire_"):
           groups.setdefault("flame_nofire", []).append(img)
       elif img.startswith("hanna_plot1_"):
           groups.setdefault("hanna_plot1", []).append(img)
       elif img.startswith("hanna_plot2_"):
           groups.setdefault("hanna_plot2", []).append(img)
       # etc.
   ```
4. **Sort within each group** by filename (alphanumeric assumes sequential order).
5. **Sequential split within each group** — NEVER shuffle:
   ```python
   for group_name, files in groups.items():
       sorted_files = sorted(files)  # preserve temporal order
       n = len(sorted_files)
       n_train = int(n * ratios[0])
       n_val = int(n * ratios[1])
       train_files = sorted_files[:n_train]
       val_files = sorted_files[n_train:n_train + n_val]
       test_files = sorted_files[n_train + n_val:]
   ```
6. **Stratified constraint**: Each split must contain both fire and no-fire images. If a group is fire-only, distribute across splits ensuring each split has fire samples.
7. Create symlinks (preferred) or hard copies from `all/` to `{train,val,test}/`:
   ```python
   for split_name, files in [("train", train_files), ("val", val_files), ("test", test_files)]:
       for f in files:
           os.symlink(
               os.path.join(data_dir, "images", "all", f),
               os.path.join(output_dir, "images", split_name, f)
           )
           os.symlink(
               os.path.join(data_dir, "labels", "all", f.replace(".jpg", ".txt")),
               os.path.join(output_dir, "labels", split_name, f.replace(".jpg", ".txt"))
           )
   ```
8. Return split statistics dict.

**Error Cases**:
- `sum(ratios) != 1.0` → raise `ValueError`
- Less than 3 images total → raise `ValueError("Cannot split fewer than 3 images")`
- No-fire images absent from a split → log WARNING (train needs negatives), but proceed
- Symlink creation fails (Windows without admin) → fallback to `shutil.copy2`

**Side Effects**:
- Creates symlinks or copies in output directory
- Logs split distribution per group at INFO level

### 6.2 Contract: `validate_split`

```python
def validate_split(output_dir: str) -> dict
```

| Aspect | Detail |
|--------|--------|
| **Summary** | Post-split validation: check for temporal leakage, class distribution, and file integrity. |
| **Parameter** | `output_dir: str` — directory with `images/{train,val,test}/` and `labels/{train,val,test}/` |
| **Returns** | `dict` — `{"valid": bool, "leakage_detected": bool, "class_distribution": dict, "issues": list[str]}` |

#### Behavior

**Preconditions**: Split has been executed by `split_temporal_aware`.

**Normal Flow**:
1. **Leakage check**: For each group (flame_fire, hanna_plot1, etc.), verify ALL files from that group are in exactly ONE split.
   ```python
   for group in groups:
       splits_present = {s for s in ["train","val","test"] if any(f.startswith(group) for f in split_files[s])}
       if len(splits_present) > 1:
           issues.append(f"LEAKAGE: {group} appears in {splits_present}")
   ```
2. **Class distribution check**: Count fire vs no-fire per split.
3. **Empty split check**: Each split must have ≥ 1 image.
4. **Orphan check**: Every `.jpg` must have matching `.txt`. Every `.txt` must have matching `.jpg`.
5. Return validation dict.

**Error Cases**:
- Leakage detected → `valid = False`, log CRITICAL error
- No-fire missing from train → `valid = True` but log WARNING
- Orphans found → `valid = False`

---

## 7. Module: `src/train_sagemaker.py` — SageMaker Training Entrypoint

### 7.1 Contract

```python
# This file is the ENTRYPOINT of the SageMaker Docker container.
# It is invoked as: python train_sagemaker.py
# No function signature — it's a script.
```

### 7.2 Environment Variables Contract

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SM_MODEL_DIR` | Yes | — | SageMaker output path for model artifacts (`/opt/ml/model/`) |
| `SM_CHANNEL_TRAINING` | Yes | — | SageMaker input data path (`/opt/ml/input/data/training/`) |
| `SM_CHANNEL_VALIDATION` | No | — | Optional separate validation channel |
| `YOLO_MODEL` | No | `yolo26m.pt` | Base model to fine-tune |
| `YOLO_EPOCHS` | No | `200` | Number of training epochs |
| `YOLO_BATCH` | No | `32` | Batch size per GPU |
| `YOLO_IMGSZ` | No | `640` | Input image size |
| `YOLO_PATIENCE` | No | `30` | Early stopping patience |
| `YOLO_LR0` | No | `0.01` | Initial learning rate |
| `YOLO_DEVICE` | No | `0,1,2,3` | CUDA device IDs |
| `YOLO_NUM_WORKERS` | No | `8` | DataLoader workers |
| `YOLO_PRETRAINED` | No | `true` | Use pretrained weights |
| `YOLO_SAVE_PERIOD` | No | `10` | Checkpoint every N epochs |
| `OUTPUT_CHECKPOINT_S3` | No | — | If set, checkpoint to S3 after each `save_period` (spot recovery) |

### 7.3 Behavior

**Preconditions**:
- SageMaker Training Job has started with `SM_MODEL_DIR` and `SM_CHANNEL_TRAINING` set
- `data.yaml` exists at `{SM_CHANNEL_TRAINING}/data.yaml`
- YOLO26m base weights are downloadable
- GPU(s) are detected by PyTorch

**Normal Flow**:
```python
import os
import json
import yaml
from ultralytics import YOLO

# 1. Read config from environment
epochs = int(os.getenv("YOLO_EPOCHS", "200"))
batch = int(os.getenv("YOLO_BATCH", "32"))
imgsz = int(os.getenv("YOLO_IMGSZ", "640"))
patience = int(os.getenv("YOLO_PATIENCE", "30"))
lr0 = float(os.getenv("YOLO_LR0", "0.01"))
device = os.getenv("YOLO_DEVICE", "0,1,2,3")
pretrained = os.getenv("YOLO_PRETRAINED", "true").lower() == "true"
model_name = os.getenv("YOLO_MODEL", "yolo26m.pt")
save_period = int(os.getenv("YOLO_SAVE_PERIOD", "10"))

# 2. Validate data.yaml
data_yaml_path = os.path.join(os.environ["SM_CHANNEL_TRAINING"], "data.yaml")
with open(data_yaml_path) as f:
    data_config = yaml.safe_load(f)
assert data_config["nc"] == 1, "Single class only"

# 3. Load model
model = YOLO(model_name)

# 4. Train with thermal-specific config
results = model.train(
    data=data_yaml_path,
    epochs=epochs,
    imgsz=imgsz,
    batch=batch,
    device=device,
    patience=patience,
    lr0=lr0,
    save_period=save_period,
    pretrained=pretrained,

    # === CRITICAL: Thermal-specific augmentations ===
    hsv_h=0.0,           # DISABLE hue jitter — false-color has no meaningful hue
    hsv_s=0.0,           # DISABLE saturation jitter
    hsv_v=0.3,           # Keep brightness jitter (thermal intensity variation)

    # Standard augmentations
    mosaic=1.0,
    mixup=0.1,           # Reduced — mixing fire+no-fire confuses
    fliplr=0.5,
    flipud=0.0,          # Disable — upside-down fire is unrealistic
    scale=0.5,
    translate=0.1,
    erasing=0.4,

    # Output
    project=os.environ["SM_MODEL_DIR"],
    name="train",
    exist_ok=True,
)

# 5. Copy best model to SM_MODEL_DIR
import shutil
best_pt = os.path.join(os.environ["SM_MODEL_DIR"], "train", "weights", "best.pt")
shutil.copy2(best_pt, os.path.join(os.environ["SM_MODEL_DIR"], "best.pt"))

# 6. Save metrics
metrics = {
    "mAP50": float(results.results_dict.get("metrics/mAP50(B)", 0.0)),
    "mAP50_95": float(results.results_dict.get("metrics/mAP50-95(B)", 0.0)),
    "precision": float(results.results_dict.get("metrics/precision(B)", 0.0)),
    "recall": float(results.results_dict.get("metrics/recall(B)", 0.0)),
    "epochs_completed": epochs - patience if results.epoch > patience else epochs,
    "best_epoch": int(results.best_epoch) if results.best_epoch else epochs,
}
with open(os.path.join(os.environ["SM_MODEL_DIR"], "metrics.json"), "w") as f:
    json.dump(metrics, f, indent=2)

# 7. Checkpoint to S3 (if configured, for spot recovery)
checkpoint_s3 = os.getenv("OUTPUT_CHECKPOINT_S3")
if checkpoint_s3:
    import subprocess
    subprocess.run([
        "aws", "s3", "sync",
        os.path.join(os.environ["SM_MODEL_DIR"], "train", "weights"),
        checkpoint_s3,
    ])
```

**Error Cases**:
- `data.yaml` not found → raise `FileNotFoundError`, SageMaker marks job as failed
- GPU not detected → fall back to CPU (log WARNING), but training will be extremely slow
- CUDA OOM → log batch size, let SageMaker capture exception → job fails
- `yolo26m.pt` download fails → `ultralytics` raises, job fails (no network → check VPC/subnet)

**Side Effects**:
- Writes `best.pt` and `metrics.json` to `SM_MODEL_DIR` (SageMaker uploads to S3 automatically)
- Creates `runs/` directory with logs, loss curves, validation predictions
- Checkpoints to S3 if configured

---

## 8. Module: `docker/Dockerfile` — SageMaker Container

### 8.1 Contract

```dockerfile
# Dockerfile — no function signature (it's a Dockerfile)
```

### 8.2 Behavior

**Base Image**: `ultralytics/ultralytics:latest`

**Build Steps**:
```dockerfile
FROM ultralytics/ultralytics:latest

# SageMaker Training Toolkit
RUN pip install --no-cache-dir \
    sagemaker-training \
    boto3 \
    imagecodecs \
    scikit-learn \
    opencv-python-headless \
    pyflir \
    pyyaml

# Copy training entrypoint
COPY src/train_sagemaker.py /opt/ml/code/train.py

# SageMaker expects this
ENV SAGEMAKER_PROGRAM=train.py

# Set working directory
WORKDIR /opt/ml/code

# SageMaker Training Toolkit entrypoint
ENTRYPOINT ["python", "/opt/ml/code/train.py"]
```

**Constraints**:
- Must be built with `--platform linux/amd64` (SageMaker runs x86_64, not ARM)
- Docker image pushed to Amazon ECR: `{account}.dkr.ecr.{region}.amazonaws.com/xheimdall-training:latest`
- No hardcoded credentials in Dockerfile
- `ultralytics/ultralytics:latest` already includes CUDA, cuDNN, PyTorch

**Build & Push Commands**:
```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin {account}.dkr.ecr.us-east-1.amazonaws.com
docker build --platform linux/amd64 -t xheimdall-training:latest -f docker/Dockerfile .
docker tag xheimdall-training:latest {account}.dkr.ecr.us-east-1.amazonaws.com/xheimdall-training:latest
docker push {account}.dkr.ecr.us-east-1.amazonaws.com/xheimdall-training:latest
```

---

## 9. Module: `src/launch_training.py` — SageMaker Job Launcher

### 9.1 Contract

```python
# Script to be run locally (or from SageMaker Notebook) to launch training jobs.

def launch_training_job(
    image_uri: str,
    role_arn: str,
    s3_data_path: str,
    s3_output_path: str,
    instance_type: str = "ml.g5.12xlarge",
    instance_count: int = 1,
    use_spot: bool = True,
    hyperparameters: dict[str, str] | None = None,
    max_wait_seconds: int = 43200  # 12 hours
) -> str
```

| Aspect | Detail |
|--------|--------|
| **Summary** | Creates and launches a SageMaker Estimator training job. Returns the training job name for monitoring. |
| **Parameters** | `image_uri: str` — ECR image URI for training container. `role_arn: str` — IAM role ARN with SageMaker and S3 permissions. `s3_data_path: str` — S3 URI for dataset (e.g., `s3://xheimdall-datasets/yolo_dataset/`). `s3_output_path: str` — S3 URI for model output. `instance_type: str` — SageMaker instance type. `use_spot: bool` — whether to use spot instances. `hyperparameters: dict[str,str]` — environment variables for training script. `max_wait_seconds: int` — timeout for spot instance fulfillment. |
| **Returns** | `str` — SageMaker training job name |

#### Behavior

**Preconditions**:
- AWS credentials configured (env vars or IAM role if running on SageMaker Notebook)
- ECR image exists and is accessible
- S3 data path and output path exist
- IAM role has `AmazonSageMakerFullAccess` + custom S3 policy

**Normal Flow**:
```python
import sagemaker
from sagemaker.estimator import Estimator
from sagemaker.inputs import TrainingInput

session = sagemaker.Session()

# Checkpoint for spot recovery
checkpoint_s3_uri = f"s3://xheimdall-models/checkpoints/{job_name}/"

estimator = Estimator(
    image_uri=image_uri,
    role=role_arn,
    instance_count=instance_count,
    instance_type=instance_type,
    output_path=s3_output_path,
    sagemaker_session=session,
    use_spot_instances=use_spot,
    max_wait=max_wait_seconds if use_spot else None,
    max_run=max_wait_seconds,
    checkpoint_s3_uri=checkpoint_s3_uri if use_spot else None,
    environment=hyperparameters or {},
)

# TrainingInput with Pipe mode for faster data loading (optional, falls back to File)
train_input = TrainingInput(
    s3_data=s3_data_path,
    content_type="application/x-recordio",
    input_mode="File",  # File mode: S3 → EBS copy; Pipe: streaming
)

estimator.fit({"training": train_input})

return estimator.latest_training_job.name
```

**Error Cases**:
- `role_arn` invalid → `sagemaker.exceptions.UnexpectedStatusException`
- ECR image not accessible → training job stays in `Pending` → timeout
- Spot capacity unavailable → SageMaker retries; if `max_wait` exceeded, throws exception
- S3 path incorrect → training job fails in `Downloading` phase

**Side Effects**:
- Creates SageMaker Training Job (visible in AWS Console)
- Incurs cost as soon as job starts
- Output artifacts written to S3

---

## 10. Module: `src/export_tensorrt.py` — PT → TensorRT Engine

### 10.1 Contract: `export_to_tensorrt`

```python
def export_to_tensorrt(
    model_path: str,
    output_path: str,
    config: dict | None = None
) -> str
```

| Aspect | Detail |
|--------|--------|
| **Summary** | Convert a YOLO26 PyTorch checkpoint (`best.pt`) to a TensorRT engine optimized for NVIDIA Jetson AGX. Defaults to FP16 precision. |
| **Parameters** | `model_path: str` — path to `.pt` file. `output_path: str` — directory for output `.engine` file. `config: dict | None` — export configuration overrides. |
| **Returns** | `str` — path to the exported `.engine` file |

#### Behavior

**Preconditions**:
- `model_path` file exists and is a valid YOLO26 `.pt` checkpoint
- NVIDIA GPU is present (TensorRT requires CUDA-capable GPU for build)
- Output directory is writable
- `ultralytics` is installed with TensorRT support (`pip install ultralytics onnx onnxruntime-gpu tensorrt`)

**Normal Flow**:
```python
import os
from ultralytics import YOLO

defaults = {
    "format": "engine",
    "half": True,         # FP16
    "int8": False,         # Set True for INT8 (requires calibration data)
    "imgsz": 640,
    "workspace": 4.0,      # GB — TensorRT build workspace
    "device": 0,           # GPU device
    "dynamic": False,      # Fixed input size for Jetson optimal
    "simplify": True,      # ONNX graph simplification
    "opset": 17,           # ONNX opset (17+ required for TensorRT 10+)
    "batch": 1,            # Single-batch inference (real-time)
}

if config:
    defaults.update(config)

model = YOLO(model_path)
export_path = model.export(**defaults)

# Verify engine loads
engine_model = YOLO(export_path)
assert engine_model is not None, "Engine failed to load"

return export_path  # String path to .engine file
```

**Error Cases**:
- TensorRT not installed → `ultralytics` raises `ImportError`
- GPU memory insufficient for `workspace` → TensorRT build fails with OOM
- ONNX export fails → check opset compatibility, log error
- INT8 requested but no calibration data → raise `ValueError("INT8 calibration data required")`

**Side Effects**:
- Writes `.engine` file to `output_path`
- Logs export time and engine file size at INFO level

---

## 11. Module: `src/infer_jetson.py` — Jetson Inference

### 11.1 Contract: `load_model`

```python
def load_model(engine_path: str) -> "ultralytics.YOLO"
```

| Aspect | Detail |
|--------|--------|
| **Summary** | Load a TensorRT engine for inference. Returns a YOLO model object ready for `.predict()`. |
| **Parameter** | `engine_path: str` — path to `.engine` file |
| **Returns** | `ultralytics.YOLO` — loaded model object |

#### Behavior

**Preconditions**:
- `engine_path` file exists and is a valid TensorRT engine
- Engine was exported with same TensorRT version as installed on Jetson
- `ultralytics` is installed on Jetson (ARM64 wheel)

**Normal Flow**:
```python
from ultralytics import YOLO

model = YOLO(engine_path)
# Warm-up inference
import numpy as np
dummy = np.zeros((1, 640, 640, 3), dtype=np.uint8)
_ = model.predict(dummy, imgsz=640, verbose=False)
return model
```

**Error Cases**:
- Engine file not found → `FileNotFoundError`
- TensorRT version mismatch → cryptic CUDA error at load time. Mitigation: log TensorRT versions on export and import.
- Engine compiled for different GPU architecture → fails to load

### 11.2 Contract: `predict_frame`

```python
def predict_frame(
    model: "ultralytics.YOLO",
    frame: np.ndarray,
    conf: float = 0.25
) -> list[dict]
```

| Aspect | Detail |
|--------|--------|
| **Summary** | Run inference on a single frame. Returns detected fire regions. |
| **Parameters** | `model: YOLO` — loaded model. `frame: np.ndarray` — `(H, W, 3)` uint8 BGR or RGB image. `conf: float` — confidence threshold (0.0–1.0). |
| **Returns** | `list[dict]` — `[{"x_min": int, "y_min": int, "x_max": int, "y_max": int, "confidence": float}, ...]` |

#### Behavior

**Preconditions**:
- `frame` is a valid 3-channel image
- `conf` in range `[0.0, 1.0]`
- Model is loaded

**Normal Flow**:
```python
results = model.predict(
    frame,
    imgsz=640,
    conf=conf,
    iou=0.0,          # NMS-free — iou is unused for YOLO26
    verbose=False,
    stream=False,
    device=0,
)

detections = []
if results and len(results) > 0 and results[0].boxes is not None:
    boxes = results[0].boxes
    for i in range(len(boxes)):
        x1, y1, x2, y2 = boxes.xyxy[i].tolist()
        conf_val = float(boxes.conf[i])
        detections.append({
            "x_min": int(x1),
            "y_min": int(y1),
            "x_max": int(x2),
            "y_max": int(y2),
            "confidence": conf_val,
        })
return detections
```

**Error Cases**:
- `frame` is `None` → return `[]`
- `frame.shape` has wrong dimensions → log warning, attempt resize to 640, or return `[]`

### 11.3 Contract: `run_camera_loop`

```python
def run_camera_loop(
    source: str,
    model: "ultralytics.YOLO",
    config: dict | None = None
) -> None
```

| Aspect | Detail |
|--------|--------|
| **Summary** | Main inference loop: capture frames from thermal camera (GStreamer pipeline or video file), run detection, display/stream results. |
| **Parameters** | `source: str` — GStreamer pipeline string, video file path, or camera index. `model: YOLO` — loaded engine. `config: dict` — `{"conf": float, "display": bool, "record": str|None, "crop_detections": bool}` |

#### Behavior

**Preconditions**:
- `source` is a valid GStreamer pipeline or accessible video file
- Camera is connected and streaming thermal false-color
- Model is loaded and valid

**GStreamer Pipeline for FLIR Boson**:
```python
DEFAULT_PIPELINE = (
    "v4l2src device=/dev/video0 ! "
    "video/x-raw,format=UYVY,width=640,height=512,framerate=30/1 ! "
    "videoconvert ! "
    "video/x-raw,format=BGR ! "
    "appsink drop=1 max-buffers=2"
)
```

**Normal Flow**:
```python
import cv2
import time

defaults = {"conf": 0.25, "display": True, "record": None, "crop_detections": False}
if config:
    defaults.update(config)

# Open source
if source.startswith("v4l2") or source.startswith("nvargus"):
    cap = cv2.VideoCapture(source, cv2.CAP_GSTREAMER)
else:
    cap = cv2.VideoCapture(source)

if not cap.isOpened():
    raise RuntimeError(f"Cannot open source: {source}")

fps_counter = []
try:
    while True:
        t0 = time.perf_counter()
        ret, frame = cap.read()
        if not ret:
            break

        detections = predict_frame(model, frame, conf=defaults["conf"])

        # Compute FPS
        elapsed = time.perf_counter() - t0
        fps_counter.append(1.0 / max(elapsed, 0.001))
        if len(fps_counter) > 100:
            fps_counter.pop(0)
        current_fps = sum(fps_counter) / len(fps_counter)

        # Display (optional)
        if defaults["display"]:
            vis_frame = frame.copy()
            for d in detections:
                color = (0, 255, 0)  # Green for fire
                cv2.rectangle(vis_frame, (d["x_min"], d["y_min"]),
                              (d["x_max"], d["y_max"]), color, 2)
                cv2.putText(vis_frame, f'FIRE {d["confidence"]:.2f}',
                            (d["x_min"], d["y_min"] - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            cv2.putText(vis_frame, f"FPS: {current_fps:.1f}",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.imshow("XHeimdall Thermal Fire Detection", vis_frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        # Record (optional)
        if defaults["record"]:
            # Write frame with detections to video file
            pass

finally:
    cap.release()
    if defaults["display"]:
        cv2.destroyAllWindows()
```

**Error Cases**:
- Camera disconnect during loop → `cap.read()` returns `False`, loop exits gracefully
- GPU memory leak → monitor VRAM usage, force periodic `torch.cuda.empty_cache()`
- FPS drops below target → log WARNING with current FPS

**Side Effects**:
- Displays GUI window (if `display=True`)
- Writes video file (if `record` is set)
- Prints FPS stats every 30 seconds to stdout

---

## 12. Module: `src/utils/config.py` — Configuration Loader

### 12.1 Contract

```python
def load_yaml_config(path: str, schema: dict | None = None) -> dict
```

| Aspect | Detail |
|--------|--------|
| **Summary** | Load and validate a YAML configuration file against an optional schema. |
| **Parameters** | `path: str` — path to `.yaml` file. `schema: dict | None` — if provided, validate against this schema (keys, types, required fields). |
| **Returns** | `dict` — validated configuration |
| **Raises** | `FileNotFoundError`, `yaml.YAMLError`, `ValueError` (schema validation failure) |

#### Validation Logic
```python
def validate_schema(config: dict, schema: dict) -> list[str]:
    """Check required keys and types. Returns list of errors (empty = valid)."""
    errors = []
    for key, spec in schema.items():
        if spec.get("required", False) and key not in config:
            errors.append(f"Missing required key: {key}")
        if key in config and "type" in spec:
            expected_type = spec["type"]
            actual = config[key]
            if expected_type == "int" and not isinstance(actual, int):
                errors.append(f"Key '{key}': expected int, got {type(actual).__name__}")
            elif expected_type == "float" and not isinstance(actual, (int, float)):
                errors.append(f"Key '{key}': expected float, got {type(actual).__name__}")
            # etc.
    return errors
```

### 12.2 Contract: `get_aws_credentials`

```python
def get_aws_credentials() -> tuple[str, str, str | None]
```

| Aspect | Detail |
|--------|--------|
| **Summary** | Read AWS credentials from environment variables only. Never from files in the repo. |
| **Returns** | `(access_key, secret_key, session_token)` — session token may be `None` |
| **Raises** | `RuntimeError` if credentials not found |

**Behavior**:
```python
import os

access_key = os.environ.get("AWS_ACCESS_KEY_ID")
secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
session_token = os.environ.get("AWS_SESSION_TOKEN")

if not access_key or not secret_key:
    raise RuntimeError(
        "AWS credentials not found in environment. "
        "Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY."
    )

return access_key, secret_key, session_token
```

**Anti-pattern**: DO NOT read from `secrets/heimdall_accessKeys.csv`. Those keys are exposed and must be rotated. The spec explicitly forbids importing or referencing the CSV path.

---

## 13. Module: `src/utils/debug_viz.py` — Debug Visualizer

### 13.1 Contract: `create_debug_overlay`

```python
def create_debug_overlay(
    jpg_path: str,
    celsius: np.ndarray,
    mask: np.ndarray,
    bboxes: list[dict],
    output_path: str | None = None
) -> np.ndarray
```

| Aspect | Detail |
|--------|--------|
| **Summary** | Generate a debug visualization image for HITL review: false-color JPG overlaid with thermal mask, bounding boxes, and temperature legend. |
| **Parameters** | `jpg_path: str` — false-color thermal JPG. `celsius: np.ndarray` — `(H,W)` float32 temperature array. `mask: np.ndarray` — final binary fire mask. `bboxes: list[dict]` — detected fire bboxes. `output_path: str | None` — if provided, save to this path. |
| **Returns** | `np.ndarray` — `(H, W, 3)` uint8 BGR debug image |

#### Visualization Layout
```
┌──────────────────────────────────────────┐
│  False-color JPG (background)            │
│  ┌────────────────────┐                  │
│  │ Green bbox + conf  │  ← fire bboxes   │
│  └────────────────────┘                  │
│  Red semi-transparent overlay ← mask     │
│                                          │
│  Temp Legend:  Cold ────────────────── Hot│
│               (0°C)                 (200°C)│
│  Image: flame_fire_001.jpg               │
│  Threshold: 150°C | Bboxes: 3 | Px: 1,234│
└──────────────────────────────────────────┘
```

**Behavior**:
1. Load JPG with `cv2.imread`.
2. Resize to match `celsius.shape` if needed.
3. Normalize `celsius` to 0-255 for display: `celsius_viz = ((celsius - 0) / (200 - 0) * 255).clip(0, 255).astype(np.uint8)`.
4. Apply `cv2.applyColorMap(celsius_viz, cv2.COLORMAP_INFERNO)` as semi-transparent overlay.
5. Draw mask outline in cyan (`cv2.findContours` + `cv2.drawContours`).
6. Draw bboxes in green with fill ratio label.
7. Draw information bar at bottom.
8. Save if `output_path` provided. Return ndarray.

---

## 14. Config File Schemas

### 14.1 `configs/auto_label_fire.yaml`

```yaml
# Wildfire detection (FLAME 3 Sycan Marsh)
absolute_threshold: 150.0   # °C
gradient_threshold: 40.0    # °C/px (Sobel)
min_area: 50                # pixels
max_aspect_ratio: 8.0
dbscan_eps: 30              # pixels
dbscan_min_samples: 5
max_bbox_ratio: 0.4         # max bbox dim as fraction of image dim
kmeans_subdivide_threshold: 500
min_fill_ratio: 0.15
class_id: 0
```

### 14.2 `configs/auto_label_prescribed.yaml`

```yaml
# Prescribed burn detection (Hanna Hammock)
absolute_threshold: 100.0   # °C — prescribed burns are cooler
gradient_threshold: 30.0    # °C/px — lower gradient for cooler fires
min_area: 30                # pixels — smaller fires acceptable in prescribed burns
max_aspect_ratio: 8.0
dbscan_eps: 25              # tighter clustering for cooler fires
dbscan_min_samples: 3
max_bbox_ratio: 0.4
kmeans_subdivide_threshold: 500
min_fill_ratio: 0.15
class_id: 0
```

### 14.3 `configs/training.yaml`

```yaml
model: yolo26m.pt
epochs: 200
batch: 32                  # per GPU
imgsz: 640
patience: 30
lr0: 0.01
device: "0,1,2,3"
workers: 8
pretrained: true
save_period: 10

# Augmentations (thermal-specific)
hsv_h: 0.0                # DISABLED
hsv_s: 0.0                # DISABLED
hsv_v: 0.3                # brightness jitter only
mosaic: 1.0
mixup: 0.1
fliplr: 0.5
flipud: 0.0               # DISABLED
scale: 0.5
translate: 0.1
erasing: 0.4

# SageMaker
sagemaker:
  instance_type: "ml.g5.12xlarge"
  instance_count: 1
  use_spot: true
  max_wait_seconds: 43200
  image_name: "xheimdall-training"
  region: "us-east-1"
  s3_data: "s3://xheimdall-datasets/yolo_dataset/"
  s3_output: "s3://xheimdall-models/"
  checkpoint_s3: "s3://xheimdall-models/checkpoints/"
```

### 14.4 Prepare Dataset Config Schema

```yaml
# Schema for process_dataset input
sources:
  - name: "flame"
    type: "celsius_tiff"
    celsius_dir: "datasets/CVSubset/FLAME 3 CV Dataset (Sycan Marsh)/Fire/Thermal/Celsius TIFF"
    jpg_dir: "datasets/CVSubset/FLAME 3 CV Dataset (Sycan Marsh)/Fire/Thermal/Raw JPG"
    rgb_dir: "datasets/CVSubset/FLAME 3 CV Dataset (Sycan Marsh)/Fire/RGB/Corrected FOV"
    config: "configs/auto_label_fire.yaml"
    class: "fire"

  - name: "flame_nofire"
    type: "negative"
    celsius_dir: "datasets/CVSubset/FLAME 3 CV Dataset (Sycan Marsh)/No Fire/Thermal/Celsius TIFF"
    jpg_dir: "datasets/CVSubset/FLAME 3 CV Dataset (Sycan Marsh)/No Fire/Thermal/Raw JPG"
    class: "nofire"

  - name: "hanna_plot1"
    type: "celsius_tiff"
    celsius_dir: "datasets/archive/Hanna Hammock/plot 1/duringburn/geo_thermal_tiff_celsius"
    jpg_dir: "datasets/archive/Hanna Hammock/plot 1/duringburn/raw_thermal_jpg"
    config: "configs/auto_label_prescribed.yaml"
    class: "fire"

  - name: "hanna_plot2"
    type: "celsius_tiff"
    celsius_dir: "datasets/archive/Hanna Hammock/plot 2/duringburn/geo_thermal_tiff_celsius/part1"
    celsius_dir_2: "datasets/archive/Hanna Hammock/plot 2/duringburn/geo_thermal_tiff_celsius/part2"
    jpg_dir: "datasets/archive/Hanna Hammock/plot 2/duringburn/raw_thermal_jpg"
    config: "configs/auto_label_prescribed.yaml"
    class: "fire"

output_dir: "data/"
debug: true
debug_sample_rate: 0.1    # Generate debug images for 10% of images
```

---

## 15. AWS Infrastructure Contract

### 15.1 IAM Role Minimum Permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket",
        "s3:PutObject"
      ],
      "Resource": [
        "arn:aws:s3:::xheimdall-datasets/*",
        "arn:aws:s3:::xheimdall-datasets",
        "arn:aws:s3:::xheimdall-models/*",
        "arn:aws:s3:::xheimdall-models"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

### 15.2 Environment Variables (Required)

| Variable | Purpose | Set By |
|----------|---------|--------|
| `AWS_ACCESS_KEY_ID` | AWS access key | User (env) |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key | User (env) |
| `AWS_DEFAULT_REGION` | AWS region (default: `us-east-1`) | User (env) |
| `HEIMDALL_S3_DATASETS` | S3 dataset bucket | User (env, default: `xheimdall-datasets`) |
| `HEIMDALL_S3_MODELS` | S3 models bucket | User (env, default: `xheimdall-models`) |

---

## 16. Acceptance Criteria

### AC-01: TIFF Reading — FLAME Celsius
```
Given  a valid FLAME 3 Celsius TIFF at 512×640 float32 with fire temperatures up to 573°C
When   read_celsius_tiff(path) is called
Then   returns a (H, W) float32 ndarray
 And   at least one value > 150.0°C (fire detected in raw data)
 And   the array contains no NaN outside masked regions
 And   processing time per file < 100ms
 And   no exception is raised
```

### AC-02: TIFF Reading — Hanna Hammock LZW
```
Given  a valid Hanna Hammock geo_thermal_tiff_celsius with LZW compression at path ".../IRX_0529_ref_geo.TIFF"
When   read_celsius_tiff(path) is called
Then   returns a (531, 654) float32 ndarray
 And   all values are in range [0.0, 200.0]°C (reasonable prescribed burn range)
 And   imagecodecs handles LZW decompression transparently
 And   returns None if tifffile raises TiffFileError (corrupt file)
```

### AC-03: Auto-Label Pipeline — 4 Filters Applied Sequentially
```
Given  a FLAME fire TIFF with known fire region (temperature range -22°C to 573°C)
 And   config with threshold=150°C, gradient=40°C/px, min_area=50px, max_aspect=8.0
When   process_single_tiff(path, config) runs the full cascade
Then   absolute_threshold mask contains > 0 fire pixels for 98% of fire images
 And   gradient_filter removes uniform warm regions (e.g., heated ground edges)
 And   area_shape_filter removes components < 50px and aspect ratio > 8:1
 And   at least one valid YOLO bbox is generated per fire image
 And   all bbox coordinates are within [0.0, 1.0] after normalization
 And   no exception is raised for any valid FLAME fire TIFF
```

### AC-04: Auto-Label — No-Fire Images Generate Empty Labels
```
Given  a FLAME no-fire TIFF (max temperature 47.2°C)
 And   config with threshold=150°C
When   process_single_tiff(path, config) runs the cascade
Then   absolute_threshold mask contains zero fire pixels (all pixels ≤ 47.2°C < 150°C)
 And   bboxes_to_yolo returns empty string
 And   no false positive bboxes are generated
```

### AC-05: DBSCAN + K-Means Subdivision
```
Given  a binary mask with two disconnected fire clusters (cluster A: 1000px, cluster B: 300px)
 And   cluster A is 200px wide (60% of image width, exceeds max_bbox_ratio=0.4)
 And   cluster B is 40px compact
When   cluster_fire_regions(mask) runs DBSCAN + K-Means
Then   DBSCAN separates into at least 2 clusters (cluster A, cluster B, + noise)
 And   cluster A triggers K-Means subdivision because width > 0.4 * image_width
 And   cluster A produces at least 2 sub-bboxes after K-Means (k determined by size ratio)
 And   cluster B produces exactly 1 bbox (no subdivision needed)
 And   all returned bboxes have valid pixel coordinates (non-negative, within image bounds)
```

### AC-06: Temporal-Aware Split — No Leakage
```
Given  a dataset with 622 FLAME fire images named flame_fire_0000.jpg through flame_fire_0621.jpg
 And   split ratios (0.7, 0.15, 0.15)
When   split_temporal_aware(data_dir, output_dir, ratios) is called
Then   train receives flame_fire_0000.jpg through flame_fire_0435.jpg (first 70%)
 And   val receives flame_fire_0436.jpg through flame_fire_0528.jpg (next 15%)
 And   test receives flame_fire_0529.jpg through flame_fire_0621.jpg (last 15%)
 And   validate_split returns valid=True with leakage_detected=False
 And   no image from the flame_fire group appears in more than one split
```

### AC-07: SageMaker Training Job Completes
```
Given  a SageMaker Training Job launched on ml.g5.12xlarge with spot instances
 And   dataset at s3://xheimdall-datasets/yolo_dataset/
 And   training config: epochs=200, batch=32/GPU, imgsz=640, patience=30
 And   thermal-specific augmentations: hsv_h=0, hsv_s=0, fliplr=0.5, erasing=0.4
When   the training job runs to completion (200 epochs or early stopping)
Then   best.pt is saved to SM_MODEL_DIR and uploaded to s3://xheimdall-models/weights/best.pt
 And   metrics.json is saved with mAP50, mAP50_95, precision, recall fields
 And   metrics.json mAP50 ≥ 0.85 on validation set
 And   metrics.json mAP50_95 ≥ 0.55 on validation set
 And   training log contains no CUDA OOM errors
 And   if spot interrupted, job resumes from latest S3 checkpoint
```

### AC-08: TensorRT FP16 Export Validates
```
Given  a trained best.pt file with mAP50 ≥ 0.85
 And   a CUDA-capable GPU (for TensorRT build)
When   export_to_tensorrt(model_path, output_path, {"half": True, "imgsz": 640}) is called
Then   best.engine file is created at output_path
 And   engine file size is approximately 25-50 MB (FP16)
 And   engine loads successfully: model = YOLO("best.engine") does not raise
 And   engine.predict(dummy_frame) returns valid detections on a test frame
 And   inference latency on dummy frame is < 5ms (GPU, excluding I/O)
```

### AC-09: Jetson Deployment End-to-End
```
Given  best.engine copied to Jetson AGX at /opt/xheimdall/best.engine
 And   a FLIR Boson connected via USB/GMSL outputting 640×512 false-color thermal
 And   GStreamer pipeline configured for the camera
 And   config with conf=0.25, display=True
When   run_camera_loop(gstreamer_pipeline, model, config) is started
Then   camera feed is displayed with fire detections overlaid as green bboxes
 And   sustained FPS ≥ 25 over a 60-second test window
 And   no false detections on a room-temperature scene (≤ 0.05 FPR on 116 known no-fire images)
 And   detections are stable (no flickering bboxes on consecutive frames)
 And   pressing 'q' exits the loop cleanly
 And   camera disconnect during operation logs error and exits without crash
```

### AC-10: HITL Review — Auto-Label Quality
```
Given  10% of auto-labeled FLAME images (60 images) with generated YOLO labels
 And   a human annotator reviews debug overlay images
When   HITL validation compares auto-labels against manual annotation
Then   precision of auto-generated bboxes ≥ 0.95 (less than 5% false bboxes)
 And   recall ≥ 0.90 (more than 90% of fire regions have a bbox)
 And   mean IoU between auto-bbox and manual-bbox ≥ 0.75
 And   any images failing quality thresholds are flagged for manual correction
```

### AC-11: End-to-End Pipeline Integration
```
Given  all source datasets present in datasets/ directory
 And   all dependencies installed per requirements.txt
 And   AWS credentials configured in environment
 And   config YAML files present in configs/
When   the full pipeline is executed:
       1. process_dataset(dataset_config) — produces ~1,500 labeled images
       2. split_temporal_aware(data_dir, output_dir) — creates train/val/test splits
       3. generate_data_yaml(...) — writes data.yaml
       4. launch_training_job(...) — SageMaker Training Job completes
       5. export_to_tensorrt(best.pt, ...) — produces best.engine
Then   all steps complete without unhandled exceptions
 And   data.yaml is valid YOLO format
 And   best.pt achieves mAP50 ≥ 0.85 on held-out test set
 And   best.engine loads and infers correctly
 And   total end-to-end time (excluding training) is < 4 hours on local CPU
```

---

## 17. Dependencies & Prerequisites

### 17.1 Python Dependencies (`requirements.txt`)

```
# Core
numpy>=1.24.0,<2.0
tifffile>=2024.1.0
imagecodecs>=2024.1.0
pillow>=10.0.0
pyyaml>=6.0

# Computer Vision & ML
opencv-python>=4.8.0
scipy>=1.10.0
scikit-image>=0.21.0
scikit-learn>=1.3.0

# Thermal Image Processing
pyflir>=0.3.0

# YOLO & Export
ultralytics>=8.2.0
onnx>=1.15.0
onnxruntime-gpu>=1.16.0

# AWS
boto3>=1.28.0
sagemaker>=2.190.0

# Development
pytest>=7.4.0
pytest-cov>=4.1.0
```

### 17.2 System Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| Python | 3.10+ | Runtime |
| CUDA | 12.1+ (training) / L4T CUDA (Jetson) | GPU compute |
| NVIDIA GPU Driver | 535+ | CUDA support |
| TensorRT | 8.6+ (Jetson) / 10.0+ (export) | Inference engine |
| exiftool | 12.0+ (optional) | IRG radiometric extraction fallback |
| Docker | 24+ | SageMaker container build |
| AWS CLI | 2.0+ | S3 sync, ECR auth |

### 17.3 AWS Resources (to be Created)

| Resource | Name/ARN | Purpose |
|----------|----------|---------|
| S3 Bucket | `xheimdall-datasets` | Training dataset storage |
| S3 Bucket | `xheimdall-models` | Model artifacts + checkpoints |
| ECR Repository | `xheimdall-training` | SageMaker training container |
| IAM Role | `SageMakerHeimdallRole` | SageMaker + S3 permissions |
| SageMaker Domain | (existing or new) | Notebook + Training Job management |

### 17.4 Migrations

None — this is a greenfield project with no existing database or deployment.

### 17.5 Variables de Entorno (Runtime)

All credentials via environment only. See §15.2 for required variables.

---

## 18. Anti-Patterns & Forbidden Operations

### 18.1 DO NOT

| Anti-Pattern | Why | Correct Approach |
|-------------|-----|-----------------|
| ❌ Read creds from `secrets/heimdall_accessKeys.csv` | Keys are exposed in repo history | ✅ `os.environ.get("AWS_ACCESS_KEY_ID")` only |
| ❌ Random split (`sklearn.train_test_split`) | Temporal leakage from adjacent frames | ✅ `split_temporal_aware` with sequential grouping |
| ❌ HSV jitter enabled (`hsv_h > 0` or `hsv_s > 0`) | False-color has no meaningful hue/saturation | ✅ `hsv_h=0, hsv_s=0` in training config |
| ❌ `yolo26n.pt` base model | 3.2M params insufficient for 1-class thermal detection | ✅ `yolo26m.pt` (25.3M params) |
| ❌ FP32/INT8 export default | FP32 too slow; INT8 needs calibration | ✅ FP16 via `half=True` |
| ❌ Hardcoded paths (Linux `/home/...` or Windows `C:\...`) | Not portable between Windows dev and Linux SageMaker | ✅ `pathlib.Path` with relative paths or env-variable-injected paths |
| ❌ `try/catch` without specific exception types | Swallows real errors silently | ✅ Specific `except (FileNotFoundError, ValueError)` etc. |
| ❌ `any` type hints | Loses static analysis benefits | ✅ Explicit types: `np.ndarray`, `list[dict]`, `tuple[str, np.ndarray]` |
| ❌ NADIRPlots directory in data processing | Exact 34.92 GB duplicate of Hanna Hammock | ✅ Exclude from `process_dataset` sources; user confirmed deletion |
| ❌ Multi-class labels (`flame`, `smoke`, `hotspot`) | User confirmed single class `fire` | ✅ `nc: 1` and `class_id: 0` only |

### 18.2 MUST DO

| Best Practice | Rationale |
|---------------|-----------|
| ✅ Validate all config files against schemas before processing | Catch misconfiguration early |
| ✅ Log all warnings and errors with file paths and timestamps | Debuggability without re-running |
| ✅ Write empty label files for no-fire images (not skip/omit) | YOLO requires label files for all images |
| ✅ Clamp bbox coordinates to [0.0, 1.0] | YOLO format compliance |
| ✅ Resume from S3 checkpoints on spot interruption | Cost efficiency for long training jobs |
| ✅ Verify TensorRT version compatibility between export and Jetson | Avoid cryptic CUDA errors on deployment |
| ✅ Include processing_report.json in dataset output | Reproducibility and audit trail |
| ✅ Sort files alphanumerically before temporal split | Deterministic splits |
| ✅ Test with subset (10 images) before full pipeline | Quick failure detection |

---

## File Structure (Final)

```
XHeimdall/
├── sdd/
│   ├── discovery.md
│   ├── proposal.md
│   └── spec.md                    # ← THIS FILE
├── src/
│   ├── __init__.py
│   ├── thermal_io.py              # TIFF/IRG readers
│   ├── auto_label.py              # 4-filter cascade auto-labeler
│   ├── prepare_data.py            # Dataset processor orchestrator
│   ├── split_dataset.py           # Temporal-aware split
│   ├── train_sagemaker.py         # SageMaker training entrypoint
│   ├── launch_training.py         # SageMaker job launcher
│   ├── export_tensorrt.py         # PT → TensorRT export
│   ├── infer_jetson.py            # Jetson inference script
│   └── utils/
│       ├── __init__.py
│       ├── config.py              # YAML config loader + AWS creds
│       └── debug_viz.py           # Debug overlay visualization
├── configs/
│   ├── auto_label_fire.yaml
│   ├── auto_label_prescribed.yaml
│   └── training.yaml
├── docker/
│   └── Dockerfile                 # SageMaker custom container
├── tests/
│   ├── __init__.py
│   ├── test_thermal_io.py
│   ├── test_auto_label.py
│   └── test_prepare_data.py
├── requirements.txt
├── .gitignore
└── datasets/                      # Git-ignored (428 GB)
```

---

*Specification generated by SDD Spec subagent | `especificador-tecnico-senior` | deepseek-v4-pro | 2026-05-22*

*Ready for: `sdd-design` phase — Component architecture, data flows, and file-level design.*
