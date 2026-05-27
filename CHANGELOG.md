# Changelog

All notable changes to the Heimdall **edge stack** are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-05-27

First public release, built for the SEDIA *Reto IA Responsable y Abierta* (Aragón, 2026).

### Added

- **Vision** — `Heimdall-Vision-TensorRT-F16`: an Ultralytics YOLO26 detector fine-tuned for a single `fire` class on 3,000+ thermal images, exported to TensorRT FP16 for the Jetson AGX Orin. Published as a GitHub release with a [model card](models/MODEL_CARD.md).
- **Convergence** — explainable fire-spread forecasting (Balbi 2015 rate-of-spread + Scott/Burgan fuel models), risk buffers, and report history, served over a FastAPI REST API (`/detect`, `/latest`, `/history`, `/health`).
- **Edge** — process supervisor, audible buzzer alert codes, and a preflight check (camera + engine + audio).
- **Contracts** — typed `MeteoReport` REST contract shared between the vision and convergence services.
- **Tooling** — `docker compose` two-service stack (`vision-inference` + `convergence-api`), demo replay (`scripts/replay_detections.py`), and a stack verifier.
- **CI** — GitHub Actions runs the 50 pure-Python edge + convergence tests on every push.
- **Docs & OSS hygiene** — README, model card, deployment guide (`howRun.md`), CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, CITATION, NOTICE.

### Fixed

- `MeteoReport` GeoJSON `type` discriminator was missing, breaking schema validation downstream.

### Security

- Removed a hardcoded third-party API credential from the vision-model loader and stopped tracking `.env.local`. The credential has since been **revoked and rotated**.

### Licensing

- Clarified **hybrid licensing**: the `vision/` inference path and model weights are **AGPL-3.0** (derived from Ultralytics YOLO26); the `convergence/` and `edge/` code is **Apache-2.0**. Corrected an earlier model-card claim that the weights were Apache-2.0.

[0.1.0]: https://github.com/ComunidadIA-OS/Edge-AI-for-Situational-Awareness-in-Emergencies/releases/tag/v0.1.0
