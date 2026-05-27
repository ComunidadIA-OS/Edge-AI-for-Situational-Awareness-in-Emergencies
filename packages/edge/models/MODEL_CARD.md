# Model Card: Heimdall-Vision-TensorRT-F16

Single-class thermal fire detection model, exported to TensorRT FP16 for NVIDIA Jetson deployment.
Fine-tuned from **Ultralytics YOLO26** on AWS SageMaker using nadir thermal imagery.

> **License at a glance.** Because this model is fine-tuned from Ultralytics YOLO26, both the
> weights and the vision-inference code path are distributed under **AGPL-3.0**, not Apache-2.0.
> See [License](#license) below and the repository [NOTICE](../NOTICE).

---

## Model details

| Field | Value |
|---|---|
| **Name** | Heimdall-Vision-TensorRT-F16 |
| **Base architecture** | [Ultralytics YOLO26](https://docs.ultralytics.com/models/yolo26) (AGPL-3.0) |
| **Task** | Object detection — single class (`fire`) |
| **Input modality** | Thermal / infrared images (FLIR, nadir-pointing) |
| **Input size** | 1280 × 1280 px |
| **Export precision** | **TensorRT FP16** (half precision) |
| **Target hardware** | NVIDIA Jetson AGX Orin (JetPack 6.x) |
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

These numbers reflect a small, geographically narrow dataset (see
[Limitations](#limitations-and-recommendations)). They are honest baseline figures for a
competition prototype, **not** production accuracy claims.

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

---

## Training data

| Field | Value |
|---|---|
| **Total images** | **3 064** thermal frames |
| **Total dataset size** | 410 MB (images + labels) |
| **Train / val / test split** | 70 % / 15 % / 15 % |
| **Class labels** | 1 class: `fire` |

### Data sources

- **FLAME 3 CV Dataset** (Sycan Marsh, Oregon) — airborne thermal video of prescribed burns; frames extracted and annotated for fire bounding boxes.
- **NADIR Plots — Hanna Hammock Plot 1 & 2** — nadir thermal TIFF/JPG captures from controlled burns in Florida scrub-shrub habitat.

Imagery was acquired with nadir-facing FLIR cameras at altitudes ranging from 30 m to 200 m AGL.
All annotations are axis-aligned bounding boxes around active flame regions.

The trained weights are released as a GitHub Release asset; the **raw training imagery is the
authors' proprietary asset and is not redistributed** with this project.

---

## Intended use

Heimdall-Vision-TensorRT-F16 is designed for **early fire detection** on drone platforms equipped with
thermal cameras. It is intended as one component of a broader situational awareness pipeline
(fire perimeter estimation, spread rate prediction, weather integration) — not as a standalone
autonomous decision-making system.

**This model requires human-in-the-loop oversight.** Detections should be reviewed by a trained
operator before triggering any emergency response action. The system never actuates.

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

False positives (e.g. thermal noise classified as fire) and false negatives are expected and
documented behaviour for an advisory system. Report systematic misclassifications via the issue tracker.

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

## License

**AGPL-3.0.** This model is fine-tuned from [Ultralytics YOLO26](https://www.ultralytics.com/license),
which is licensed under AGPL-3.0. A model fine-tuned from an AGPL-3.0 base is a **derivative work**
and inherits AGPL-3.0 — retraining on new data does *not* relicense it. Accordingly, **both the
`Heimdall-Vision-TensorRT-F16` weights and the vision-inference code that loads them are released
under AGPL-3.0**, regardless of the Apache-2.0 license used by the rest of Heimdall.

- Full AGPL-3.0 text: [LICENSE-AGPL-3.0.txt](../LICENSE-AGPL-3.0.txt) · <https://www.gnu.org/licenses/agpl-3.0.txt>
- The Apache-2.0 components (convergence engine, edge orchestration, dashboard) communicate with
  this AGPL-3.0 vision service only over a network REST boundary (the `MeteoReport` contract).
  See the repository [NOTICE](../NOTICE) for the full split.

> **Commercial / embedded use.** AGPL-3.0 obligations (including network/source-disclosure) apply.
> If those terms do not fit your deployment, Ultralytics offers an
> [Enterprise License](https://www.ultralytics.com/license) for the underlying YOLO architecture.

### Training data licenses (separate from this model's license)

The training datasets are owned and licensed by their original authors:

- **FLAME 3 CV Dataset** (Sycan Marsh) — check upstream license terms before redistributing the raw frames.
- **NADIR Plots — Hanna Hammock 1 & 2** — same caveat.

The trained weights are released under AGPL-3.0; the raw training data is not redistributed.

---

## Citation

If you use this model in your work, please cite:

```bibtex
@software{heimdall_2026,
  author = {Briceño, Saúl and Langa, Carlos and {ComunidadIA-OS contributors}},
  title  = {Heimdall — Edge AI for Situational Awareness in Emergencies},
  year   = {2026},
  url    = {https://github.com/ComunidadIA-OS/Edge-AI-for-Situational-Awareness-in-Emergencies},
  note   = {Vision model: Heimdall-Vision-TensorRT-F16}
}
```
