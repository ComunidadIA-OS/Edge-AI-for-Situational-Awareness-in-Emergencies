# Model Card: Heimdall TensorRT FP16

Single-class thermal fire detection model, exported to TensorRT FP16 for NVIDIA Jetson deployment.
Fine-tuned from YOLOv26m on AWS SageMaker using nadir thermal imagery.

---

## Model details

| Field | Value |
|---|---|
| **Name** | Heimdall TensorRT FP16 |
| **Base architecture** | YOLOv26m (Ultralytics YOLO v8 family) |
| **Task** | Object detection — single class (`fire`) |
| **Input modality** | Thermal / infrared images (FLIR, nadir-pointing) |
| **Input size** | 1280 × 1280 px |
| **Export precision** | **TensorRT FP16** (half precision) |
| **Target hardware** | NVIDIA Jetson AGX Orin (JetPack 5.x) |
| **Training job** | `xheimdall-yolo26m-20260525-101951` |
| **Training date** | 2026-05-25 |

---

## Performance metrics

Metrics from the final completed epoch (200/200), evaluated on the held-out validation split.

| Metric | Value |
|---|---|
| **mAP@0.5** | 0.463 |
| **mAP@0.5:0.95** | 0.246 |
| **Precision** | 0.493 |
| **Recall** | 0.456 |

---

## Training details

| Parameter | Value |
|---|---|
| **Epochs** | 200 (all completed) |
| **Batch size** | 8 |
| **Optimizer** | SGD (lr=0.01, momentum=0.937) |
| **Training instance** | AWS SageMaker `ml.g5.xlarge` (NVIDIA A10G, 24 GB VRAM) |
| **Training duration** | ~2 h 45 min (9 916 billable seconds) |
| **Job status** | Completed |
| **Model S3 path** | `s3://xheimdall-models/training/xheimdall-yolo26m-20260525-101951/output/model.tar.gz` |

---

## Training data

| Field | Value |
|---|---|
| **Total images** | **3 064** thermal frames |
| **Total dataset size** | 410 MB (images + labels) |
| **Train / val / test split** | 70 % / 15 % / 15 % |
| **Class labels** | 1 class: `fire` |
| **S3 source** | `s3://xheimdall-datasets/yolo_dataset/` |

### Data sources

- **FLAME 3 CV Dataset** (Sycan Marsh, Oregon) — airborne thermal video of prescribed burns; frames extracted and annotated for fire bounding boxes.
- **NADIR Plots — Hanna Hammock Plot 1 & 2** — nadir thermal TIFF/JPG captures from controlled burns in Florida scrub-shrub habitat.

Imagery was acquired with nadir-facing FLIR cameras at altitudes ranging from 30 m to 200 m AGL.
All annotations are axis-aligned bounding boxes around active flame regions.

---

## Intended use

Heimdall TensorRT FP16 is designed for **early fire detection** on drone platforms equipped with
thermal cameras. It is intended as one component of a broader situational awareness pipeline
(fire perimeter estimation, spread rate prediction, weather integration) — not as a standalone
autonomous decision-making system.

**This model requires human-in-the-loop oversight.** Detections should be reviewed by a trained
operator before triggering any emergency response action.

---

## Limitations and recommendations

The current dataset (~3 000 images) covers specific North American chaparral and scrub habitats
under controlled-burn conditions. Performance may degrade in:

- Mediterranean vegetation (maquis, garrigue, pine forests typical of Spain / southern Europe)
- Night-time or high-humidity conditions that alter apparent thermal signatures
- Very small fires or smouldering smoke at the detection threshold
- Altitude ranges significantly outside the training distribution (< 30 m or > 300 m AGL)

**We recommend re-training with a larger and more diverse thermal dataset** before operational
deployment in environments not represented in the current training data. Specifically:
- Expand to ≥ 10 000 annotated thermal frames
- Include Mediterranean vegetation and European wildfire scenarios
- Add night/dawn/dusk captures and varying humidity conditions
- Incorporate data augmentation specific to thermal sensor noise models

---

## Download

Weights are distributed as a GitHub Release asset (not tracked in git due to file size).

```bash
# Download best.pt (~44 MB) from GitHub Releases
python scripts/fetch_model.py

# Export to TensorRT FP16 on Jetson (requires CUDA + TensorRT)
python -m vision.inference.export_tensorrt --model models/best.pt --fp16 --output models/best.engine
```

---

## Citation

If you use this model in your work, please cite:

```bibtex
@misc{heimdall2026,
  title  = {Heimdall: Edge AI for Situational Awareness in Emergencies},
  author = {XHeimdall contributors},
  year   = {2026},
  url    = {https://github.com/ComunidadIA-OS/Edge-AI-for-Situational-Awareness-in-Emergencies},
  note   = {Model: Heimdall TensorRT FP16, training job xheimdall-yolo26m-20260525-101951}
}
```

---

## License

**Apache License 2.0** — see [LICENSE](../LICENSE) for the full text.

The same license applies to the model weights (`best.pt`) distributed via
GitHub Releases and to the inference code in this repository. Apache 2.0 is
the de-facto standard for open ML models (PyTorch, TensorFlow, HuggingFace
Transformers, Ultralytics YOLO all use it) and includes an explicit patent
grant that protects downstream users from future patent claims.

### Training data licenses (separate from this model's license)

The training datasets are owned and licensed by their original authors:

- **FLAME 3 CV Dataset** (Sycan Marsh) — check upstream license terms before
  redistributing the raw frames; the trained weights derived from them
  are released here under Apache 2.0.
- **NADIR Plots — Hanna Hammock 1 & 2** — same caveat.

If you intend to redistribute the *raw training data*, contact the dataset
authors. If you only redistribute the *trained model* (this release), the
Apache 2.0 license applies.
