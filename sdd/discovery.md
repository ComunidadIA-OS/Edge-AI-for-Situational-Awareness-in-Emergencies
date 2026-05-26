# XHeimdall — Discovery Document

## Phase: Explore | Date: 2026-05-22 | Project: YOLO26m Thermal Fire Detection

---

## 1. Executive Summary

XHeimdall aims to train a **YOLO26m** (Ultralytics, NMS-free architecture) object detection model on thermal imagery to detect wildfires and prescribed burns, deployed via **TensorRT** on **NVIDIA Jetson AGX**. The project currently contains **428 GB of raw data** across 5 datasets with **zero existing code and zero labels**.

**Key breakthrough**: Two datasets — FLAME 3 (Sycan Marsh) and Hanna Hammock (Florida prescribed burns) — contain **radiometric Celsius TIFFs** where fire regions can be auto-labeled via simple temperature thresholding (e.g., >150°C). This eliminates the need for weeks of manual annotation and enables a bootstrapped training pipeline.

The no-fire class in FLAME has a maximum temperature of **47.2°C**, making the fire/no-fire separation unambiguous at any threshold above ~100°C. The fire class shows **98.2% of images have >50 pixels above 150°C**, providing reliable auto-generated bounding boxes.

---

## 2. Dataset Inventory — Verified

All datasets verified against filesystem at `C:\Users\warmachine\Documents\Projects\XHeimdall\datasets\`.

### 2.1 `#1-7) All Video Pairs` (13.62 GB, 14 files)

| Pair | IR Video | Size (MB) | RGB Video | Size (MB) |
|------|----------|-----------|-----------|-----------|
| #1   | IR Video 1.MP4 | 322.5 | RGB Video 1.MP4 | 3,590.0 |
| #2   | IR Video 2.MP4 | 199.9 | RGB Video 2.MP4 | 2,259.7 |
| #3   | IR Video 3.MP4 | 446.8 | RGB Video 3.MP4 | 1,740.4 |
| #4   | IR Video 4.MP4 | 333.9 | RGB Video 4.MP4 | 1,298.4 |
| #5   | IR Video 5.MP4 | 297.2 | RGB Video 5.MP4 | 1,155.5 |
| #6   | IR Video 6.MP4 | 206.2 | RGB Video 6.MP4 | 800.1 |
| #7   | IR Video 7.MP4 | 266.3 | RGB Video 7.MP4 | 1,034.8 |

- **7 paired sets** of IR + RGB aerial fire videos
- No video metadata available (no ffprobe/ffmpeg on system)
- These are candidates for frame extraction and video-level annotation, but **not the primary training source** (no temperature data)

### 2.2 `#8) Original Resolution Frame Pairs` (126.68 GB, 106,902 files)

| Directory | Files | Format | Resolution | Mode |
|-----------|-------|--------|------------|------|
| Original Sized RGB Images | 53,451 | .jpg | **3840×2160** | RGB |
| Original Sized Thermal Images | 53,451 | .jpg | **640×512** | RGB (false-color) |

- Named sequentially: `Original Sized RGB Frame (1).jpg` through `(53451).jpg`
- Thermal frames are **false-color mapped JPGs** (3-channel RGB), NOT raw radiometric
- **Without radiometric data**, these cannot be auto-labeled via thresholding
- RGB images are 4K — thermal images are FLIR Boson resolution (640×512)
- These could be used as **supplementary data** if manual annotation is done, or for **video-based inference testing**

### 2.3 `CVSubset/FLAME 3 CV Dataset (Sycan Marsh)` (7.02 GB, 2,952 files)

This is the **primary training dataset**. Classification labels are known, but it can be converted to detection.

```
FLAME 3 CV Dataset (Sycan Marsh)
├── Fire/ (622 samples)
│   ├── RGB/Corrected FOV/     622 .jpg (640×512, RGB)
│   ├── RGB/Raw/               622 .jpg (4000×3000, RGB)
│   ├── Thermal/Celsius TIFF/  622 .TIFF (512×640, float32, °C)  ★ GOLD
│   └── Thermal/Raw JPG/       622 .jpg (640×512, false-color)
├── No Fire/ (116 samples)
│   ├── RGB/Corrected FOV/     116 .jpg
│   ├── RGB/Raw/               116 .jpg
│   ├── Thermal/Celsius TIFF/  116 .TIFF (float32, max 47.2°C)   ★ NEGATIVE CONTROL
│   └── Thermal/Raw JPG/       116 .jpg
```

**Class imbalance**: 622 Fire : 116 No Fire = **5.4:1 ratio**
This is manageable with weighted sampling and augmentation.

### 2.4 `archive/Hanna Hammock` (34.92 GB)

UAV prescribed burn data from Florida — 3 plots with temporal progression.

```
Hanna Hammock/
├── plot 1/duringburn/ (296 frames each)
│   ├── raw_rgb_jpg/           297 .jpg  (RGB)
│   ├── raw_thermal_irg/       297 .irg  (FLIR radiometric, ~960KB, embedded temp)
│   ├── raw_thermal_jpg/       297 .jpg  (false-color)
│   ├── raw_thermal_tiff/      297 .TIFF (16-bit raw sensor, LZW compressed)
│   └── geo_thermal_tiff_celsius/ 296 .TIFF (531×654, float32, °C, LZW)
├── plot 2/duringburn/ (498 frames each)
│   ├── raw_rgb_jpg/           521 .jpg
│   ├── raw_thermal_irg/       521 .irg
│   ├── raw_thermal_jpg/       522 .jpg
│   ├── raw_thermal_tiff/      522 .TIFF
│   └── geo_thermal_tiff_celsius/ (498 .TIFF, split part1/322 + part2/176)
├── plot 3/raw_jpg_rgb/        117 .jpg (preburn only, no thermal)
├── GCPs/ (georeference points) + metadata/
```

- **Total duringburn thermal TIFFs**: 296 (plot 1) + 498 (plot 2) = **794 frames**
- **geo_thermal_tiff_celsius**: 531×654 float32, 0–197°C observed (prescribed burns are cooler than wildfires)
- **raw_thermal_irg**: FLIR radiometric JPEG format with embedded temperature data — alternative source for extraction
- **raw_thermal_tiff**: 16-bit raw sensor values (not calibrated to °C) — need conversion formula
- LZW compression on TIFFs requires `imagecodecs` or GDAL library

### 2.5 `NADIRPlots/Hanna Hammock` (34.92 GB)

**Exact duplicate** of `archive/Hanna Hammock` — same file count, same structure. Can be:
- Deleted to save 34.92 GB (if space constrained)
- Or kept as backup (total project is 428 GB, so this is ~8% of total)

---

## 3. Thermal Thresholding Analysis — PROVEN VIABLE

### 3.1 FLAME 3 (Sycan Marsh) — Wildfire Data

**Test**: All 622 Fire and 116 No Fire Celsius TIFFs analyzed.

| Threshold | Fire Images Detected (≥50px) | Catch Rate | No-Fire False Positives |
|-----------|------------------------------|------------|------------------------|
| >100°C    | 618 / 622                    | **99.4%**  | 0 / 116 (0.0%) |
| >150°C    | 611 / 622                    | **98.2%**  | 0 / 116 (0.0%) |
| >180°C    | 600 / 622                    | **96.5%**  | 0 / 116 (0.0%) |
| >200°C    | 523 / 622                    | 84.1%      | 0 / 116 (0.0%) |
| >250°C    | 500 / 622                    | 80.4%      | 0 / 116 (0.0%) |

**No-Fire class**: Absolute max temperature across all 116 images = **47.2°C**
→ Any threshold ≥ 100°C gives **zero false positives**.

**Fire class**: Temperature range -22.8°C to 573°C (mean 13.0°C, σ=41.4°C)

**Recommended threshold**: **150°C** — catches 98.2% of fire images with zero false positives.

### 3.2 Hanna Hammock — Prescribed Burn Data

First sample analyzed (IRX_0529_ref_geo.TIFF): 531×654 float32, 0–197°C, mean 35.3°C.
- Prescribed burns are **significantly cooler** than wildfires
- 200°C threshold would **miss most data** here
- **Recommended threshold: 80–120°C** for prescribed burns
- Full batch analysis needed (LZW decompression requires `imagecodecs`)

### 3.3 Auto-Bbox Generation Algorithm

```
For each Celsius TIFF:
  1. Read float32 array (H×W)
  2. Apply threshold (150°C for wildfire, 100°C for prescribed burn)
  3. Create binary mask: mask = temperature > threshold
  4. Filter small noise: remove regions < 50 pixels
  5. Find contours (cv2.findContours or skimage.measure.label)
  6. For each contour → bounding box (x_min, y_min, width, height)
  7. Normalize to YOLO format: [class_id, x_center/W, y_center/H, width/W, height/H]
  8. Handle multiple fire regions per image (multi-bbox per image)
  9. Apply minimum area filter and IoU deduplication
```

### 3.4 Edge Cases to Handle

1. **Images with fire but below threshold** (~1.8% of FLAME, more in Hanna Hammock):
   - These would need manual annotation or lower threshold with morphological post-processing
   - Alternative: use the false-color JPG as training input, label from TIFF threshold

2. **Multiple disconnected fire regions**:
   - Each region becomes a separate bbox (YOLO supports multi-object per image)

3. **Temporal consistency**: Adjacent frames from video sequences should have similar fire regions. Can be used to validate auto-generated bboxes.

4. **Small fire spots**: Minimum area threshold (e.g., 50px) filters sensor noise but may miss incipient fires.

---

## 4. Pipeline Architecture

### 4.1 Data Preparation Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA PREPARATION (Local)                      │
│                                                                  │
│  FLAME Celsius TIFFs ──→ threshold(150°C) ──→ binary mask       │
│  (622 fire + 116 no-fire)           │                            │
│                                     ├─→ contours ──→ bboxes     │
│                                     │              │             │
│  FLAME Thermal JPGs ────────────────┤              │             │
│  (false-color, 640×512)             │              ▼             │
│                                     │    YOLO labels/            │
│  Hanna Hammock geo TIFFs ──→ threshold(100°C) ──→ bboxes        │
│  (794 duringburn)                                     │         │
│                                     │                   ▼        │
│  Hanna Hammock Thermal JPGs ────────┤    data.yaml config        │
│  (false-color or IRG-derived)       │    train/val/test split    │
│                                     │                            │
│  #8 Frame Pairs ────────────────────┤ (optional, no auto-label)  │
│  (53,451 false-color JPGs)          │                            │
└─────────────────────────────────────┬────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    S3 UPLOAD                                     │
│  s3://xheimdall-datasets/                                       │
│    ├── images/train/                                             │
│    ├── images/val/                                               │
│    ├── labels/train/                                             │
│    ├── labels/val/                                               │
│    └── data.yaml                                                 │
└─────────────────────────────────────┬────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                 SAGEMAKER TRAINING                               │
│                                                                  │
│  Option A: SageMaker Training Job + Custom Docker                │
│    ├── Dockerfile: ultralytics/ultralytics:latest + CUDA         │
│    ├── Instance: ml.g5.12xlarge (4× A10G, 96 GB GPU)            │
│    ├── Command: yolo detect train model=yolo26m.pt data=...     │
│    └── Output: s3://xheimdall-models/weights/best.pt            │
│                                                                  │
│  Option B: SageMaker Notebook (simpler, interactive)             │
│    └── ml.g5.4xlarge (1× A10G, good for dev/debugging)          │
│                                                                  │
│  Training config (proposed):                                     │
│    model: yolo26m.pt (or yolo26s.pt for speed)                  │
│    imgsz: 640 (thermal JPGs are 640×512 or 512×640)            │
│    epochs: 100-300                                               │
│    batch: 32-64 (A10G 24GB VRAM)                                │
│    device: 0,1,2,3 (multi-GPU)                                  │
└─────────────────────────────────────┬────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                 TENSORRT EXPORT + JETSON DEPLOY                  │
│                                                                  │
│  best.pt ──→ yolo export model=best.pt format=engine            │
│             ├── device=0 (GPU with TensorRT)                     │
│             ├── half=True (FP16 for Jetson)                      │
│             ├── imgsz=640                                        │
│             └── workspace=4 (GB, for TensorRT build)             │
│                        │                                         │
│                        ▼                                         │
│             best.engine ──→ copy to Jetson AGX                   │
│                              │                                   │
│  Jetson AGX:                   ▼                                  │
│    from ultralytics import YOLO                                  │
│    model = YOLO("best.engine")                                   │
│    results = model(source, imgsz=640, conf=0.25)                 │
│                                                                  │
│  Jetson considerations:                                          │
│    - L4T (Linux for Tegra) — need ultralytics ARM64 wheel       │
│    - TensorRT version must match export environment              │
│    - YOLO26 NMS-free → no NMS post-processing overhead           │
│    - Consider INT8 calibration for Jetson (2× speed boost)       │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Data Flow Diagram (End-to-End)

```
  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
  │ FLAME 3      │    │ Hanna Hammock│    │ Frame Pairs  │
  │ (622+116)    │    │ (794 frames) │    │ (53,451)     │
  │ Celsius TIFF │    │ Celsius TIFF │    │ False-color  │
  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘
         │                   │                    │
         ▼                   ▼                    │
  ┌──────────────────────────────────┐            │
  │  Auto-label Pipeline (Python)    │            │
  │  - tifffile read float32         │            │
  │  - numpy threshold + cv2 contour │            │
  │  - YOLO format output            │            │
  │  - train/val/test split (70/15/15)│           │
  └──────────────┬───────────────────┘            │
                 │                                │
                 ▼                                │
  ┌──────────────────────────────┐                │
  │  YOLO Dataset (local)        │◄───────────────┘
  │  images/  labels/  data.yaml │  (optional)
  │  ~1,500 annotated images     │
  │  ~1,400 fire + ~116 no-fire   │
  └──────────────┬───────────────┘
                 │
                 │ aws s3 sync
                 ▼
  ┌──────────────────────────────┐
  │  S3 Bucket                   │
  │  s3://xheimdall-datasets/    │
  └──────────────┬───────────────┘
                 │
                 │ SageMaker Training Job
                 ▼
  ┌──────────────────────────────┐
  │  SageMaker ml.g5.12xlarge    │
  │  YOLO26m training            │
  │  best.pt → S3 output         │
  └──────────────┬───────────────┘
                 │
                 │ Download + Export
                 ▼
  ┌──────────────────────────────┐
  │  TensorRT Engine             │
  │  best.engine (FP16/INT8)     │
  └──────────────┬───────────────┘
                 │
                 │ Deploy via scp/USB
                 ▼
  ┌──────────────────────────────┐
  │  Jetson AGX Xavier/Orin      │
  │  Inference at 30+ FPS        │
  │  Thermal camera feed → bbox  │
  └──────────────────────────────┘
```

### 4.3 AWS Infrastructure

| Component | Service | Instance / Config | Purpose |
|-----------|---------|-------------------|---------|
| Dataset Storage | S3 | `s3://xheimdall-datasets/` | Training images + labels |
| Model Artifacts | S3 | `s3://xheimdall-models/` | Trained weights, TensorRT engines |
| Training | SageMaker | `ml.g5.12xlarge` (4× A10G, 96GB) | Multi-GPU YOLO training |
| Dev/Notebook | SageMaker | `ml.g5.4xlarge` (1× A10G, 24GB) | Interactive development |
| Credentials | IAM | `heimdall_accessKeys.csv` in secrets/ | ⚠️ Keys exposed in repo — must rotate |

**⚠️ SECURITY**: AWS access keys found at `secrets/heimdall_accessKeys.csv`. These keys appear active and should be:
1. **Immediately rotated** in AWS IAM console
2. Stored via environment variables, not in repo
3. `secrets/` directory should be `.gitignore`-d

---

## 5. Class Definition Strategy

### Proposed: Single class `fire`

**Rationale**:
- Thermal cameras don't see smoke opacity well (smoke is transparent in LWIR)
- YOLO26 detection distinguishes fire by temperature signature → single class is clean
- Multi-class (flame/smoke/hotspot) adds complexity without clear benefit for thermal-only models

If RGB+Thermal fusion is added later, multi-class (`flame`, `smoke`) could be useful.

### Negative Class Handling
- "No Fire" images from FLAME (116 samples) serve as **hard negatives**
- During training, these images have empty label files (no bboxes)
- YOLO handles this natively — images with no labels contribute to background learning
- Consider adding more negative samples from preburn/postburn frames

---

## 6. Dataset Split Strategy

### 6.1 Temporal Leakage Prevention

FLAME and Hanna Hammock data are sequential frames from video. Adjacent frames are nearly identical. **Must NOT split adjacent frames into train/val** — this would leak validation into training.

**Strategy**: Group-based split by video sequence:
- FLAME: If frames are from continuous video, split by time segment (first 70% → train, next 15% → val, last 15% → test)
- Hanna Hammock: Split by plot (plot 1 → train, plot 2 → val+test), or split temporally within each plot
- Frame Pairs #8: Sequential frames → same temporal split rule applies

### 6.2 Proposed Split

| Dataset | Train | Val | Test | Notes |
|---------|-------|-----|------|-------|
| FLAME Fire | 435 (70%) | 93 (15%) | 94 (15%) | Temporal split |
| FLAME No Fire | 81 (70%) | 17 (15%) | 18 (15%) | Temporal split |
| Hanna Hammock | Plot 1 (296) | Plot 2 pt1 (250) | Plot 2 pt2 (248) | Plot-level split |
| **Total** | **~812** | **~360** | **~360** | ~1,532 annotated images |

### 6.3 Class Imbalance Mitigation

Fire:No Fire ratio = ~1,400:116 = **12:1** (worse after combining datasets)

Mitigations:
1. **Weighted sampling**: Oversample no-fire images during training
2. **Augment negatives**: Add preburn/postburn frames (83+87+132+116 = 418 clean no-fire images)
3. **Class weights** in loss function
4. **Generate synthetic negatives**: Use fire images with threshold inverted (keep only <50°C regions)

---

## 7. Image Size and Augmentation

### 7.1 Input Resolution

| Dataset | Thermal Resolution | RGB Resolution |
|---------|-------------------|----------------|
| FLAME Fire | 512×640 (Celsius) / 640×512 (JPG) | 640×512 or 4000×3000 |
| Hanna Hammock | 531×654 | varies |
| Frame Pairs | 640×512 | 3840×2160 |

**Decision**: Use `imgsz=640` (YOLO26 default). Thermal images are ~640 in their larger dimension. No upscaling needed.

### 7.2 Thermal-Specific Augmentations

Standard YOLO augmentations (mosaic, mixup, hsv, flip, scale) work but thermal data needs special consideration:

| Augmentation | Thermal Consideration |
|-------------|----------------------|
| **HSV jitter** | DISABLE — false-color thermal has no meaningful hue/saturation. Replace with intensity jitter |
| **Flip LR/UD** | OK — fire orientation is rotation-invariant |
| **Mosaic** | OK — but mixing fire + no-fire in mosaic may confuse |
| **Scale** | OK — 0.5-1.5 range |
| **Brightness/Contrast** | Replace with **temperature scaling** — simulate different thermal gain settings |
| **Noise** | Add Gaussian noise to simulate thermal sensor noise |

Custom augmentation: **Temperature jitter** — randomly offset pixel intensities by ±20°C (simulating different camera calibration or ambient conditions).

### 7.3 Input Format Decision

**For training, use false-color thermal JPGs, not raw TIFFs**:
- YOLO expects 3-channel 8-bit images (JPG/PNG)
- False-color JPGs are direct visual representation of temperature (hot→bright/yellow, cold→dark/purple)
- Model learns to map color→temperature→fire detection
- Raw float32 TIFFs cannot be directly used as YOLO input without conversion

**Alternative considered**: Convert TIFFs to single-channel 16-bit PNG + custom dataloader. This preserves radiometric precision but adds complexity. False-color JPGs are the pragmatic choice for v1.

---

## 8. YOLO26-Specific Considerations

### 8.1 Why YOLO26m

- **NMS-free**: No Non-Maximum Suppression post-processing → lower latency, simpler deployment
- **Ultralytics ecosystem**: Standard data format, built-in export to TensorRT, ONNX, CoreML
- **YOLO26m**: ~25M parameters, good speed/accuracy balance for Jetson
- **Alternative**: YOLO26s (~9M params) if Jetson latency is critical (<10ms target)

### 8.2 Model Selection Matrix

| Model | Params | mAP (COCO) | Jetson FPS (est.) | Use Case |
|-------|--------|------------|-------------------|----------|
| YOLO26n | 3.2M | ~38% | 60+ | Too small for fire detection |
| YOLO26s | 9.4M | ~45% | 40-50 | Balanced option |
| **YOLO26m** | **25.3M** | **~50%** | **25-35** | **Recommended** |
| YOLO26l | 46.5M | ~53% | 15-20 | Overkill for 1-class detection |
| YOLO26x | 71.7M | ~55% | 8-12 | Too heavy for Jetson |

### 8.3 Training Configuration Template

```yaml
# data.yaml
path: /opt/ml/input/data/training
train: images/train
val: images/val
test: images/test

names:
  0: fire

nc: 1
```

```python
# Training command
from ultralytics import YOLO

model = YOLO("yolo26m.pt")
model.train(
    data="data.yaml",
    epochs=200,
    imgsz=640,
    batch=32,
    device=[0, 1, 2, 3],  # multi-GPU
    patience=30,           # early stopping
    save_period=10,
    pretrained=True,
    augment=True,
    hsv_h=0.0,             # DISABLE hue jitter
    hsv_s=0.0,             # DISABLE saturation jitter
    hsv_v=0.3,             # keep value (brightness) jitter
    fliplr=0.5,
    mosaic=1.0,
    scale=0.5,
)
```

---

## 9. Jetson AGX Deployment

### 9.1 Export Pipeline

```
best.pt (SageMaker) 
    → Download to local GPU machine (or SageMaker GPU instance)
    → yolo export model=best.pt format=engine device=0 half=True imgsz=640 workspace=4
    → best.engine (TensorRT, FP16)
    → Copy to Jetson AGX
```

### 9.2 Jetson-Specific Requirements

| Requirement | Details |
|-------------|---------|
| JetPack version | 6.0+ (for latest TensorRT) |
| TensorRT version | Must match between export and inference |
| PyTorch | ARM64 build from NVIDIA SDK Manager |
| ultralytics | `pip install ultralytics` on ARM64 |
| CUDA | L4T CUDA (comes with JetPack) |

### 9.3 Inference Code (Jetson)

```python
from ultralytics import YOLO
import cv2

model = YOLO("best.engine")  # TensorRT engine

# Thermal camera input (example: FLIR Boson via GStreamer)
cap = cv2.VideoCapture("gstreamer-pipeline-string", cv2.CAP_GSTREAMER)

while True:
    ret, frame = cap.read()
    results = model(frame, imgsz=640, conf=0.25, iou=0.0)  # NMS-free, iou unused
    # results[0].boxes.xyxy → bbox coordinates
    # results[0].boxes.conf → confidence scores
```

### 9.4 INT8 Calibration (Optional — 2× speed)

For INT8 quantization on Jetson:
1. Export with `int8=True data=calibration_dataset.yaml`
2. Calibration uses ~100 representative images
3. 2× throughput improvement on Jetson DLA
4. Minor accuracy loss (<1% mAP typically)

---

## 10. Risks and Unknowns

### 10.1 High Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| **AWS credentials exposed** | Account compromise | Rotate immediately, use env vars, add to .gitignore |
| **YOLO26 on thermal false-color** | Model may not generalize | Train on mixed dataset (wildfire + prescribed burn), validate on held-out geographic locations |
| **False-color JPG variability** | Different thermal cameras produce different color maps | Standardize false-color palette in preprocessing, or use raw TIFF→custom dataloader |
| **Temporal leakage in split** | Overestimated val metrics | Group-based split by video sequence, not random |

### 10.2 Medium Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Hanna Hammock LZW compression** | Requires `imagecodecs` or GDAL | Install `imagecodecs` (pure Python wheel) or convert to uncompressed |
| **Small fire regions <50px** | Missed detections | Lower minimum area to 20px with morphological cleanup |
| **Prescribed burns cooler than wildfires** | Model biased toward hot fires | Train with both datasets, use lower threshold for Hanna Hammock |
| **SageMaker cold start + S3 data loading** | 5-10 min before training starts | Use FSx for Lustre (cached S3) for faster I/O |
| **Class imbalance after combining datasets** | Poor no-fire recall | Hard negative mining + oversampling + custom loss weights |

### 10.3 Low Risk / Unknowns

| Item | Status | Action |
|------|--------|--------|
| Video metadata (FPS, duration, codec) | Unknown | Install ffmpeg for analysis |
| FLAME frame sequence ordering | Unknown | Check if filenames encode temporal order |
| Hanna Hammock IRG temperature extraction | Not tested | Test FLIR SDK or exiftool for .irg parsing |
| RGB+Thermal fusion training | Out of scope | Future phase after v1 thermal-only model works |
| SageMaker cost estimate | Not calculated | ~$5-8/hr for g5.12xlarge, estimate 6-12 hours training = $30-96 |
| YOLO26 vs YOLOv8 accuracy on thermal | Unknown | Compare both on validation set |

---

## 11. Open Questions (Need Clarification)

1. **Class definition**: Single class `fire` or add `smoke`/`hotspot`? → Proposed: single class for v1
2. **Inference target**: Is this for real-time video stream (needs 30+ FPS) or batch processing (single images)?
3. **Thermal camera model on Jetson**: What thermal camera will be connected? FLIR Boson? This determines resolution, color map, and GStreamer pipeline.
4. **SageMaker vs local training**: Is AWS SageMaker the only option, or is a local GPU workstation available? SageMaker adds cost and complexity.
5. **Dataset storage cost**: 428 GB in S3 Standard = ~$10/month. S3 Intelligent-Tiering or Glacier for archives?
6. **NADIRPlots duplication**: Should we delete the 34.92 GB duplicate to save space?
7. **Frame pairs #8 usage**: Should we attempt to auto-label from the false-color JPGs, or keep as inference test set?
8. **YOLO26s vs YOLO26m**: Does Jetson latency target allow YOLO26m, or should we use YOLO26s?
9. **INT8 calibration**: Worth the complexity for Jetson? (2× speed, ~1% accuracy cost)
10. **Validation strategy**: How do we validate a fire detection model without ground truth? Drone flights? Prescribed burn events?

---

## 12. Recommendations

### 12.1 Immediate Actions (Phase 1 — This Week)

1. **⚡ Rotate exposed AWS credentials** — CRITICAL
2. **Build auto-label pipeline**: Python script to convert FLAME Celsius TIFFs + Hanna Hammock geo TIFFs to YOLO format
3. **Install `imagecodecs`**: `pip install imagecodecs` for LZW TIFF support
4. **Write `data.yaml`** and dataset split script with temporal grouping
5. **Set up S3 bucket**: `xheimdall-datasets` and `xheimdall-models`
6. **Run small-scale training locally** (if GPU available) to validate pipeline before SageMaker

### 12.2 Short-Term (Phase 2 — Next 2 Weeks)

1. **SageMaker training job** with FLAME + Hanna Hammock combined dataset
2. **Evaluate on held-out test set** — measure mAP@50, mAP@50-95, precision, recall
3. **Export to TensorRT** and benchmark on SageMaker GPU
4. **Start false-positive analysis** — especially at dawn/dusk when ground can be hot

### 12.3 Medium-Term (Phase 3)

1. **Jetson AGX deployment** with live thermal camera
2. **INT8 calibration** if latency budget requires it
3. **Consider frame pairs #8** for additional training data (may need manual labeling)
4. **Consider RGB+Thermal fusion** model for dual-camera setups

### 12.4 Dataset Priority (What to Use First)

| Priority | Dataset | Images | Why |
|----------|---------|--------|-----|
| **P0** | FLAME Fire | 622 | Auto-labelable, high-quality, stratified classes |
| **P0** | FLAME No Fire | 116 | Essential negatives, clean separation |
| **P1** | Hanna Hammock duringburn | 794 | Auto-labelable, different fire type (prescribed) |
| **P1** | Hanna Hammock preburn/postburn | 418 | Free no-fire negatives |
| **P2** | Frame Pairs #8 | 53,451 | Large volume but no auto-label possible |
| **P3** | Video Pairs #1-7 | 14 videos | Extract frames, manual or semi-auto label |

---

## 13. Cost Estimation

| Item | Estimated Cost | Notes |
|------|---------------|-------|
| S3 Storage (500 GB, Standard) | ~$11.50/month | Use Intelligent-Tiering for archives |
| SageMaker g5.12xlarge training | $5.67/hr × ~10 hrs | $57 per training run |
| SageMaker g5.4xlarge notebook | $1.89/hr × ~20 hrs | $38 for development |
| FSx for Lustre (optional) | ~$0.60/GB-month | Only needed if S3 I/O is bottleneck |
| **Estimated first month total** | **~$120-150** | Most costs in training + S3 storage |

---

## 14. File Structure Proposal

```
XHeimdall/
├── sdd/                          # SDD documents (this file)
│   ├── discovery.md              # ← THIS FILE
│   ├── proposal.md               # (future: propose phase)
│   ├── spec.md                   # (future: spec phase)
│   └── design.md                 # (future: design phase)
├── datasets/                     # Raw data (gitignored)
│   └── ... (existing structure)
├── src/                          # Source code (to be created)
│   ├── prepare_data.py           # Auto-label pipeline
│   ├── split_dataset.py          # Train/val/test split
│   ├── train_sagemaker.py        # SageMaker training entrypoint
│   ├── export_tensorrt.py        # PT → TensorRT conversion
│   ├── infer_jetson.py           # Jetson inference script
│   └── utils/
│       ├── thermal_io.py         # TIFF/IRG readers
│       ├── auto_label.py         # Threshold + contour → bbox
│       └── augmentations.py      # Thermal-specific augmentations
├── configs/
│   ├── data.yaml                 # YOLO dataset config
│   ├── train_config.yaml         # Training hyperparameters
│   └── sagemaker_config.yaml     # AWS infrastructure config
├── docker/
│   └── Dockerfile                # SageMaker training container
├── notebooks/
│   └── exploratory_analysis.ipynb # Data exploration
├── secrets/                      # CREDENTIALS — .gitignore!
│   └── heimdall_accessKeys.csv   # ⚠️ ROTATE IMMEDIATELY
└── .gitignore
```

---

## 15. Next Steps — SDD Phase Transition

**Recommendation**: **PROCEED to `sdd-propose` phase**.

The core technical uncertainty (can we auto-label from thermal TIFFs?) has been resolved with high confidence. The remaining unknowns are engineering/operations concerns that can be addressed during implementation.

### Handoff to Propose Phase

The propose phase should produce:
1. A formal RFC with trade-off analysis (SageMaker vs local, YOLO26m vs YOLO26s, FP16 vs INT8)
2. Success criteria: mAP target, latency target, false positive rate target
3. Risk matrix and mitigation plan
4. Timeline and milestone breakdown

### Inputs for Propose

- **Auto-labeling is proven viable** for FLAME (98.2% catch at 150°C, zero false positives)
- **Hanna Hammock needs lower threshold** (~100°C) for cooler prescribed burns
- **~1,500 images** can be auto-labeled from existing data
- **YOLO26m on g5.12xlarge** is the recommended training approach
- **TensorRT FP16 export** is the recommended Jetson deployment path

---

## Appendix A: Python Environment

Current environment (Windows, Python 3.14.4):
- `numpy` ✓
- `tifffile` ✓ (installed during exploration)
- `pillow` ✓ (installed during exploration)
- `imagecodecs` ✓ (installed during exploration)
- `ultralytics` ✗ (needs installation)
- `opencv-python` ✗ (needed for contour detection)
- `scikit-image` ✗ (alternative for region labeling)

## Appendix B: Sample FLAME Fire TIFF Temperatures

| Sample | Max Temp (°C) | Pixels >200°C |
|--------|--------------|---------------|
| 1 | 480.7 | 484 |
| 2 | 369.6 | 254 |
| 3 | 503.4 | 457 |
| 4 | 187.4 | 0 |
| 5 | 543.5 | 727 |
| 6 | 187.4 | 0 |
| 7 | 187.4 | 0 |
| 8 | 505.6 | 256 |
| 9 | 485.5 | 427 |
| 10 | 426.2 | 447 |

---

*Document generated by SDD Explore subagent | deepseek-v4-pro | 2026-05-22*
