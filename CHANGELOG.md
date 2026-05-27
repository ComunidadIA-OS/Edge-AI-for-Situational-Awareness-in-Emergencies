# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-05-27

First public release, built for the SEDIA *Reto IA Responsable y Abierta* (Aragón, 2026).

### Added

- **Vision** — `Heimdall-Vision-TensorRT-F16`: an Ultralytics YOLO26 detector fine-tuned for a single `fire` class on 1,500+ thermal images, exported to TensorRT FP16 for the Jetson AGX Orin. Published as a GitHub release with a model card.
- **Convergence** — explainable fire-spread forecasting (Balbi 2015 rate-of-spread + standard fuel models), risk buffers, and report history, served over a FastAPI REST API.
- **Edge** — one-command Jetson deployment, audible alert codes, and a preflight check.
- **Ground Control** — 3D situational-awareness dashboard (Next.js, MapLibre GL, Deck.gl).
- **Contracts** — typed `MeteoReport` REST contract shared between edge and dashboard.
- **Docs & OSS hygiene** — README, model card, deployment guide, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, CITATION, issue/PR templates.

### Fixed

- `MeteoReport` GeoJSON `type` discriminator was missing, breaking schema validation on the dashboard.

### Security

- Removed a hardcoded third-party API credential from the vision-model loader. The credential has since been **revoked and rotated**.

[0.1.0]: https://github.com/ComunidadIA-OS/Edge-AI-for-Situational-Awareness-in-Emergencies/releases/tag/v0.1.0
