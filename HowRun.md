# How to run Heimdall — Ground Control

A step-by-step setup guide. **You do not need to know React, Next.js, pnpm, or anything about Node.** Follow the steps in order.

> If you are looking for **what this project is** and **why it exists**, read [`README.md`](./README.md) first.

There are **two ways** to run the dashboard:

| Path | Who it's for | What you need installed |
|---|---|---|
| **A. Docker (recommended)** | Anyone who just wants to use it | Docker Desktop only |
| **B. Local dev (Node + pnpm)** | Contributors who want to edit the code | Node.js, pnpm, Git |

The Docker path leaves **zero** trace on your machine outside of Docker itself — no Node, no pnpm, no `node_modules/` polluting your global environment. Pick path A unless you intend to modify the source.

---

## Table of contents

- [Path A — Docker (recommended)](#path-a--docker-recommended)
- [Path B — Local dev (contributors)](#path-b--local-dev-contributors)
- [Running against a real Jetson AGX](#running-against-a-real-jetson-agx)
- [Troubleshooting](#troubleshooting)
- [Project structure cheat-sheet](#project-structure-cheat-sheet)

---

## Path A — Docker (recommended)

### 1. Install Docker Desktop

Download from <https://www.docker.com/products/docker-desktop/> and install. It bundles Docker Engine and `docker compose`.

Verify both work:

```bash
docker --version          # Docker version 27.x or newer
docker compose version    # Docker Compose version v2.x or newer
```

You do **not** need: Node.js, pnpm, Python, an NVIDIA GPU, CUDA, an API key, or a paid map account.

### 2. Get the code

```bash
git clone https://github.com/ComunidadIA-OS/Edge-AI-for-Situational-Awareness-in-Emergencies.git
cd Edge-AI-for-Situational-Awareness-in-Emergencies
git checkout v0.1-GroundControl
cd ground-control
```

### 3. Build and run

From inside the `ground-control/` folder:

```bash
docker compose up --build
```

First build takes **2–4 min** (downloads the Node and Nginx base images, installs ~700 packages inside the builder, produces the static export, copies it into a minimal Nginx image). Subsequent runs reuse the cache and start in seconds.

When you see:

```
heimdall-ground-control  | start worker processes
```

open <http://localhost:3000>.

1. The **Connect screen** appears.
2. Type the URL of any service that emits a valid `MeteoReport v1` on `GET /latest` (e.g. `http://192.168.1.100:8000` for a Jetson on your LAN, or any local mock you're running).
3. Click **Connect**. The dashboard opens with a 3D map, fire perimeter, risk buffers, drone trail, and the right-hand sidebar.

> The dashboard does **not** care whether the JSON it receives comes from a real Jetson AGX, a Python simulator, a static fixture, or your own test harness. It validates the schema and renders. That's the whole contract.

To stop: press `Ctrl + C`, then optionally `docker compose down` to remove the container.

### 4. Update later

```bash
git pull
docker compose up --build
```

That is the entire lifecycle. The container exposes port 80 internally and is mapped to your host's port 3000, runs as Nginx (~10 MB image overhead), and has no writable state — restarts are cheap.

---

## Path B — Local dev (contributors)

Use this path only if you intend to modify the source. It installs Node + pnpm globally on your machine.

### 1. Prerequisites

| Tool | Version | Check it works | Get it |
|---|---|---|---|
| **Node.js** | `>= 20.0` (LTS) | `node --version` | <https://nodejs.org/> |
| **pnpm** | `>= 11.0` | `pnpm --version` | `npm install -g pnpm` |
| **Git** | any recent | `git --version` | <https://git-scm.com/> |

**Operating system:** Windows 10/11, macOS 12+, or any modern Linux. All commands below work the same on all three.

### 2. Get the code and install

```bash
git clone https://github.com/ComunidadIA-OS/Edge-AI-for-Situational-Awareness-in-Emergencies.git
cd Edge-AI-for-Situational-Awareness-in-Emergencies
git checkout v0.1-GroundControl
cd ground-control
pnpm install
```

The install downloads ~700 packages into a local `node_modules/`. **30 s – 2 min** depending on connection.

### 3. Run the dev server

```bash
pnpm dev
```

You should see:

```
   ▲ Next.js 16.2.6 (Turbopack)
   - Local:        http://localhost:3000
   ✓ Ready in 766ms
```

Open <http://localhost:3000>. In dev mode the bundled **MSW** service worker automatically intercepts `GET /latest` and replies with a realistic synthetic `MeteoReport` — so whatever URL you type on the Connect screen, the dashboard renders. Hot-reload is on: saving any `.tsx` file refreshes the browser instantly.

To stop, press `Ctrl + C`.

### 4. Build / test / typecheck

```bash
pnpm exec tsc --noEmit   # type-check (no output files)
pnpm test                # Vitest one-shot
pnpm test:watch          # Vitest re-run on file change
pnpm build               # produce static export in out/
```

The Docker image is built from the same `pnpm build` output, so if `pnpm build` passes locally the container will build too.

---

## Running against a real Jetson AGX

This works the same in both Path A and Path B. You need the **edge device** half of the project (the Jetson with the FastAPI + YOLOv9 + meteorological stack) running on the same network.

That codebase lives at branch [`v0.1-EdgeDevice`](https://github.com/ComunidadIA-OS/Edge-AI-for-Situational-Awareness-in-Emergencies/tree/v0.1-EdgeDevice). Follow its own setup guide.

Once the Jetson is up and serving `GET /latest`:

1. Note its IP address on the LAN, e.g. `192.168.1.100`, and the port it exposes (default `8000`).
2. From a browser on the same network, verify the endpoint works:
   ```
   curl http://192.168.1.100:8000/latest
   ```
   You should get a big JSON object back.
3. Open the dashboard at <http://localhost:3000>.
4. On the Connect screen, paste the Jetson URL: `http://192.168.1.100:8000`.
5. Click **Connect**.

The dashboard polls the Jetson every 2 seconds. Top-bar shows **green = online**, **amber = stale**, **red = offline**.

> If the connection state goes amber/red, the Jetson is reachable but no fresh MeteoReport has been received in the last 10 seconds. Check the Jetson logs.

---

## Troubleshooting

### Docker — "port is already allocated"

Something else on your machine is using port 3000. Edit `docker-compose.yml` and change the left side of `"3000:80"` to a free port, e.g. `"3001:80"`.

### Docker — slow first build

Most of the time is downloading the Node base image and installing the 700 deps. The pnpm store is cached across builds, so the second `docker compose up --build` is much faster.

### Local — `pnpm install` fails with `[ERR_PNPM_IGNORED_BUILDS]`

pnpm v11 blocks postinstall scripts by default. This repo ships a `pnpm-workspace.yaml` with `strictDepBuilds: false` that fixes this. If you see the error anyway:

1. Make sure you ran `pnpm install` **inside `ground-control/`**, not at the parent repo root.
2. Make sure pnpm is `>= 11.0`: `pnpm --version`.
3. As a last resort: `pnpm install --config.strict-dep-builds=false`.

### Local — port 3000 is already in use

```bash
pnpm dev -- --port 3001
```

### The map is blank / grey

- Make sure your machine has internet (the basemap tiles come from public OSM-style tile servers).
- Open the browser DevTools console — any red error gives the cause.

### Dev mode shows no data after connecting

MSW registers a service worker on first load and only activates on the **second** load. Hard-reload the page (`Ctrl + Shift + R`) once after clicking Connect. After that, the synthetic `MeteoReport` polls every 2 s.

### Stale or empty data with a real Jetson

1. `curl http://<jetson-ip>:8000/latest` from your laptop — does it return JSON?
2. Are you on the same LAN / subnet as the Jetson?
3. Is the Jetson behind a firewall? Open port 8000 (or whatever it exposes).
4. CORS error in DevTools? The Jetson's FastAPI service must allow your origin.

### TypeScript or ESLint errors after pulling new commits

```bash
pnpm install
```

Lockfile drifted; reinstalling fixes the local `node_modules`.

---

## Project structure cheat-sheet

```
ground-control/
├── README.md           ← what & why
├── HowRun.md           ← this file (how to run)
├── Dockerfile          ← multi-stage: node:20-alpine → nginx:1.27-alpine
├── docker-compose.yml  ← one-command run on port 3000
├── .dockerignore       ← keeps node_modules / .next / .env out of the build context
├── package.json        ← scripts and dependencies
├── pnpm-workspace.yaml ← pnpm install config (strictDepBuilds: false)
├── next.config.ts      ← Next.js config (output: "export")
├── tsconfig.json       ← TypeScript config (strict mode)
├── vitest.config.ts    ← test runner config
├── app/                ← Next.js App Router (layout, page, globals.css)
├── public/             ← static assets + MSW service worker
└── src/
    ├── api/            ← HTTP client + TanStack Query hooks
    ├── schemas/        ← Zod validation
    ├── types/          ← TypeScript types
    ├── stores/         ← Zustand state
    ├── hooks/          ← reusable React hooks
    ├── lib/            ← Providers, small utils
    ├── mocks/          ← MSW handlers + synthetic data generator
    └── components/
        ├── app/        ← ConnectScreen, TopBar, root composition
        ├── map/        ← MapLibreMap + Deck.gl layers + legend
        ├── sidebar/    ← Status / Situation / Layers panels
        └── ui/         ← ErrorBoundary, primitives
```

That is the whole codebase. Every file is small, single-purpose, and TypeScript-strict.

---

**You are good to go.** If anything in this guide is unclear, open an issue on GitHub — the README/HowRun is part of the project, not an afterthought, and we treat doc bugs as code bugs.
