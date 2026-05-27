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

### 1. Install **and start** Docker Desktop

Download from <https://www.docker.com/products/docker-desktop/> and install. It bundles Docker Engine and `docker compose`.

> **Then actually launch the Docker Desktop app and wait until the whale icon stops animating / it says "Engine running".** This is the #1 cause of first-run failures: the `docker` CLI is on your PATH and the commands appear to work, but there is no engine behind them yet. On Windows it must also be in **Linux containers** mode (the default).

Verify the **daemon is reachable** — not just the client:

```bash
docker version    # NOTE: no dashes. Must print BOTH a Client and a Server block.
docker info       # must succeed without "Cannot connect to the Docker daemon"
```

> `docker --version` (with dashes) only prints the client version and succeeds even when the engine is down — it does **not** prove Docker is ready. Always use `docker version` / `docker info` to confirm.

You do **not** need: Node.js, pnpm, Python, an NVIDIA GPU, CUDA, an API key, or a paid map account.

### 2. Get the code

```bash
git clone https://github.com/ComunidadIA-OS/Edge-AI-for-Situational-Awareness-in-Emergencies.git
cd Edge-AI-for-Situational-Awareness-in-Emergencies
git checkout v0.1-GroundControl
```

> On the `v0.1-GroundControl` branch the dashboard **is** the repository root — there is no `ground-control/` subfolder to `cd` into. The `Dockerfile`, `docker-compose.yml` and `package.json` all live at the root. Run every command below from there.

### 3. Build and run

From the repository root (the folder that contains `docker-compose.yml`):

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

> ⚠️ **The Docker image is a production build, so it ships with NO built-in demo data.** The synthetic `MeteoReport` mocks (MSW) only run in local dev mode (`pnpm dev`). If you launch the container, connect, and the dashboard stays empty / shows **offline**, it is *not broken* — it simply has no data source yet. You need either a real endpoint serving `GET /latest`, or, if you just want to **see the dashboard populated with realistic fake data**, use **Path B** (`pnpm dev`) instead, which auto-mocks the endpoint. See ["Container runs but the dashboard shows no data"](#docker--container-runs-but-the-dashboard-shows-no-data) below.

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
pnpm install
```

> Again: no `cd ground-control` — the package is the repo root on this branch.

The install downloads the dependencies into a local `node_modules/`. **30 s – 2 min** depending on connection.

> **pnpm version:** `package.json` pins `"packageManager": "pnpm@11.1.2"`. If you have [corepack](https://nodejs.org/api/corepack.html) enabled (`corepack enable`), the correct pnpm version is selected automatically — you don't have to manage it by hand. If you installed pnpm globally and see a version-mismatch warning, it is safe to ignore as long as you're on `>= 11.0`.

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

Most first-run problems are **environment** problems (Docker not ready, network, disk), not problems with this project. Below, each entry is **symptom → cause → fix**. Find the one whose error text matches yours.

> ### 🔍 First: how to see the *real* error behind a Docker build failure
>
> When a build fails, Docker prints only a generic last line, e.g.:
> ```
> failed to solve: process "/bin/sh -c pnpm install ..." did not complete successfully: exit code: 1
> ```
> **That is not the real error** — the real one (an `ERR_PNPM_…`, `ETIMEDOUT`, `ENOSPC`, etc.) is printed a few lines *above* it and is usually hidden by Docker's compact output. Re-run with plain progress and save the full log:
>
> ```powershell
> # Windows PowerShell
> docker compose build --progress=plain --no-cache 2>&1 | Tee-Object build.log
> ```
> ```bash
> # macOS / Linux / Git-Bash
> docker compose build --progress=plain --no-cache 2>&1 | tee build.log
> ```
> Then read the **bottom** of `build.log`. The matching fix below will be obvious once you see the real message.

---

### Docker — `Cannot connect to the Docker daemon` / `npipe:////./pipe/dockerDesktopLinuxEngine ... El sistema no puede encontrar el archivo especificado`

**Cause:** the Docker **engine is not running** (or, on Windows, Docker is in *Windows containers* mode). The `docker` CLI works but has nothing to talk to.

**Fix:**
1. Launch the **Docker Desktop** app and wait until it says **"Engine running"**.
2. Confirm with `docker info` — it must succeed without the "Cannot connect" message.
3. **Windows only:** right-click the Docker tray icon. If it offers *"Switch to Linux containers…"*, click it (you were in Windows-container mode). The pipe name `…LinuxEngine` means the CLI expects the Linux engine.
4. **Windows only:** ensure the WSL 2 backend is healthy: `wsl --status`, then `wsl --update`. In Docker Desktop → *Settings → General*, *"Use the WSL 2 based engine"* must be ticked.

### Docker — `pnpm install ... did not complete successfully: exit code: 1`

Capture the real error first (see the box above), then match it:

- **`ERR_PNPM_FETCH_*`, `ETIMEDOUT`, `ECONNRESET`, `socket hang up`, `request to https://registry.npmjs.org ... failed`** → **network / proxy / slow connection.** The download was interrupted.
  - Just retry: `docker compose build` again — the pnpm store is cached, so it resumes.
  - Behind a corporate proxy? Set it in **Docker Desktop → Settings → Resources → Proxies**, and make sure the registry is reachable: `docker run --rm node:20-alpine npm ping`.
  - This repo already retries transient failures (`fetch-retries` in `.npmrc`) and no longer pulls the heavy unused `@arcgis/core` package, so the install is smaller and more resilient than before — but a dead connection will still fail.
- **`ENOSPC` / `no space left on device`** → **Docker's disk is full.** Reclaim space with `docker system prune -af` and, if needed, raise the disk limit in **Docker Desktop → Settings → Resources**.
- **`ERR_PNPM_OUTDATED_LOCKFILE` / "Cannot install with frozen-lockfile because … is not up to date"** → `package.json` and `pnpm-lock.yaml` are out of sync. As an end-user, `git pull` to get a matching pair. As a contributor, run `pnpm install` locally and commit the updated `pnpm-lock.yaml`.

### Docker — `no configuration file provided: not found` / `no such file or directory`

**Cause:** you ran `docker compose …` from the wrong folder (e.g. you tried to `cd ground-control`, which does not exist on this branch).

**Fix:** run it from the **repository root** — the folder that contains `docker-compose.yml`.

### Docker — `Bind for 0.0.0.0:3000 failed: port is already allocated`

Something else on your machine is using port 3000. Edit `docker-compose.yml` and change the **left** side of `"3000:80"` to a free port, e.g. `"3001:80"`, then open <http://localhost:3001>.

### Docker — container runs but the dashboard shows no data

**This is expected, not a bug.** The Docker image is a **production build**, and the synthetic-data mocks (MSW) are **disabled in production** — they only run under `pnpm dev`. A freshly launched container has the UI but no data source.

**Fix — pick one:**
- Point the **Connect** screen at a real endpoint that serves a valid `MeteoReport v1` on `GET /latest` (a Jetson on your LAN, or any mock server you run).
- Or, if you only want to *see the dashboard populated*, use **Path B** (`pnpm dev`) — in dev mode any URL you type is auto-answered with realistic fake data.

### Docker — slow first build

Most of the time is downloading the Node/Nginx base images and installing the dependencies. The pnpm store is cached across builds via a BuildKit cache mount, so the **second** `docker compose up --build` is much faster.

---

### The map is blank / grey

- Make sure your machine has internet — the basemap tiles come from public OSM-style tile servers.
- Open the browser DevTools console; any red error gives the cause.

### Dev mode shows no data after connecting (`pnpm dev`)

MSW registers a service worker on first load and only activates on the **second** load. Hard-reload the page (`Ctrl + Shift + R`) once after clicking Connect. After that, the synthetic `MeteoReport` polls every 2 s.

### Stale or empty data with a real Jetson

1. `curl http://<jetson-ip>:8000/latest` from your laptop — does it return JSON?
2. Are you on the same LAN / subnet as the Jetson?
3. Is the Jetson behind a firewall? Open port 8000 (or whatever it exposes).
4. CORS error in DevTools? The Jetson's FastAPI service must allow your origin. (The browser, not the container, makes the request — so the Jetson must permit the dashboard's origin.)

---

### Local — `pnpm install` fails with `[ERR_PNPM_IGNORED_BUILDS]`

pnpm v11 blocks postinstall scripts by default. This repo ships a `pnpm-workspace.yaml` with `strictDepBuilds: false` that fixes this. If you see the error anyway:

1. Make sure you ran `pnpm install` at the **repository root** (there is no `ground-control/` subfolder on this branch).
2. Make sure pnpm is `>= 11.0`: `pnpm --version`. (With `corepack enable`, the pinned `pnpm@11.1.2` is used automatically.)
3. As a last resort: `pnpm install --config.strict-dep-builds=false`.

### Local — port 3000 is already in use

```bash
pnpm dev -- --port 3001
```

### Local — TypeScript or ESLint errors after pulling new commits

```bash
pnpm install
```

Lockfile drifted; reinstalling fixes the local `node_modules`.

---

## Project structure cheat-sheet

```
. (repo root on v0.1-GroundControl — the dashboard IS the root, no subfolder)
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
