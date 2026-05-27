# Contributing to Heimdall

Thank you for your interest in contributing.

Heimdall is a wildfire situational-awareness system that spans three surfaces: edge AI on NVIDIA Jetson, a physics-based convergence engine, and a 3D operations dashboard. This repository is organized across branches — one per deployable surface.

## Project structure

| Branch | What it is | Tech stack |
|--------|-----------|------------|
| `v0.1-Heimdall` | Project hub (you are here) | — |
| `v0.1-EdgeDevice` | Jetson edge stack | Python, FastAPI, TensorRT |
| `v0.1-GroundControl` | Operations dashboard | Next.js, TypeScript, MapLibre GL |

Each branch is self-contained: its README explains how to set up, run, and contribute to that surface.

## Getting started

1. Fork the repository
2. Decide which surface you want to contribute to
3. Check out the corresponding branch:
   ```bash
   git checkout v0.1-EdgeDevice     # for edge AI work
   git checkout v0.1-GroundControl  # for dashboard work
   ```
4. Follow the branch-specific README for setup instructions

## Workflow

- Keep commits small and atomic with descriptive messages in English
- Open a PR against the branch you are contributing to
- All PRs require at least one review before merging
- CI must pass (where configured)

## Code conventions

- **TypeScript (GroundControl)**: strict mode, no `any`, no unjustified `@ts-ignore`, absolute imports with `@/src/...`, Tailwind-first styling
- **Python (EdgeDevice)**: type hints on public APIs, `ruff` for linting, `pytest` for tests
- **Docs**: keep READMEs and runbooks up to date with any behavioral change

## Reporting bugs

Open an issue describing:

1. Which branch/surface the bug affects
2. Expected vs. actual behavior
3. Steps to reproduce
4. Environment details (OS, browser, Jetson model if applicable, demo/real mode)

## Security

For security vulnerabilities, please do **not** open a public issue. See [SECURITY.md](SECURITY.md) for the reporting process.

## License

By contributing, you agree that your code will be published under the terms described in [LICENSE](LICENSE) and [NOTICE](NOTICE) (Apache 2.0 for original code; AGPL-3.0 for YOLO-derived vision components).
