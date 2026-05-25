# Heimdall — Edge AI for Situational Awareness in Emergencies

> **Hackathon SEDIA · Reto IA Responsable y Abierta en Industria · Mayo 2026**

Sistema de conciencia situacional en tiempo real para emergencias de incendios forestales. Detecta fuego desde el borde (NVIDIA Jetson + YOLOv9 + TensorRT) y despliega resultados en un dashboard 3D interactivo para los equipos de respuesta.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Next.js](https://img.shields.io/badge/Next.js-16-black)](https://nextjs.org)
[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-teal)](https://fastapi.tiangolo.com)

---

## Arquitectura

```
Dron con Jetson AGX              Ground Control                 Servicios externos
┌─────────────────────┐         ┌──────────────────┐          ┌──────────────────┐
│ YOLOv9 + TensorRT   │──REST──▶│ Dashboard (Next)  │◀────────│ NASA FIRMS       │
│ GPS + Telemetría    │  API    │ MapLibre + Deck   │         │ Open-Meteo       │
│ Starlink / 4G / 5G  │         │ Zustand + React   │         │ MapTiler tiles    │
└─────────────────────┘         └──────────────────┘          └──────────────────┘
```

---

## Estructura del monorepo

```
heimdall/
├── .github/            # CI/CD workflows, issue/PR templates
├── .opencode/          # Agentes y skills de IA
├── packages/
│   ├── edge/           # Jetson (Python 3.11, FastAPI, YOLOv9 + TensorRT)
│   ├── dashboard/      # Ground Control (Next.js 16, MapLibre GL, Deck.gl)
│   └── simulator/      # Simulador de telemetría para desarrollo local
├── pnpm-workspace.yaml
├── package.json        # Scripts y dependencias globales
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
└── LICENSE
```

| Paquete | Stack | Descripción |
|---------|-------|-------------|
| `packages/edge` | Python 3.11, FastAPI, YOLOv9, TensorRT | API REST de detección en el Jetson a bordo del dron |
| `packages/dashboard` | Next.js 16, TypeScript, MapLibre GL, Deck.gl | Dashboard de conciencia situacional para el equipo en tierra |
| `packages/simulator` | TypeScript / Python | Generador de telemetría sintética para desarrollo sin hardware |

---

## Inicio rápido

### Requisitos

- Node.js ≥ 18 + pnpm ≥ 9
- Python ≥ 3.11 (para `packages/edge` y `packages/simulator`)

```bash
git clone https://github.com/ComunidadIA-OS/Edge-AI-for-Situational-Awareness-in-Emergencies.git
cd Edge-AI-for-Situational-Awareness-in-Emergencies
pnpm install
```

### Dashboard (Ground Control)

```bash
pnpm dev:dashboard        # Modo desarrollo con datos simulados (MSW)
pnpm build:dashboard      # Build estático → packages/dashboard/out/
```

### Edge (Jetson)

```bash
cd packages/edge
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Simulador

```bash
pnpm dev:simulator        # Arranca el generador de telemetría sintética
```

---

## API del Jetson

El dashboard espera los siguientes endpoints REST en el Jetson:

| Endpoint | Intervalo | Descripción |
|----------|-----------|-------------|
| `GET /api/status` | 5s | Estado del sistema, modelo IA, conectividad |
| `GET /api/telemetry` | 2s | Posición GPS, actitud, batería, modo de vuelo |
| `GET /api/detections` | 2s | Detecciones GeoJSON de fuego/humo con confianza |
| `GET /api/mission` | mount | Información de misión, waypoints, área de interés |

---

## Contribuir

Lee [CONTRIBUTING.md](CONTRIBUTING.md) antes de abrir un PR.

## Licencia

[MIT](LICENSE) © 2026 Heimdall Team
