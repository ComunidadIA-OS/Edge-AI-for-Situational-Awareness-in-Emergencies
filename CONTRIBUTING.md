# Contributing to Heimdall (edge stack)

Thanks for your interest in Heimdall! This branch (`v0.1-EdgeDevice`) is the Jetson edge
stack: the thermal **vision** service and the physics-based **convergence** forecaster.
Heimdall is a research/competition prototype for the SEDIA *Reto IA Responsable y Abierta* —
contributions are welcome, with a few project-specific ground rules below.

## Ground rules: this is an advisory system

Heimdall is **advisory, never autonomous**. Please keep contributions consistent with that:

- The forecast path stays **explainable** — the propagation model is physics (Balbi 2015 + fuel
  models), not a black box. Don't replace it with an opaque end-to-end network.
- Machine learning is confined to **perception** (fire detection in thermal imagery).
- Every output is decision support for a human operator; the system must never actuate.

## Licensing of contributions — read before you PR

This branch is **dual-licensed**, and which license applies depends on *where* you contribute:

| Path | License | Notes |
|------|---------|-------|
| `convergence/`, `edge/`, configs, their tests | **Apache-2.0** | Original Heimdall code |
| `vision/` and anything touching the model weights | **AGPL-3.0** | Derivative of [Ultralytics YOLO26](https://www.ultralytics.com/license) |

By submitting a contribution you agree to license it under the license that governs the files
you touch. See [LICENSE](LICENSE), [LICENSE-AGPL-3.0.txt](LICENSE-AGPL-3.0.txt), and [NOTICE](NOTICE).

## Development setup

```bash
git clone https://github.com/ComunidadIA-OS/Edge-AI-for-Situational-Awareness-in-Emergencies
cd Edge-AI-for-Situational-Awareness-in-Emergencies
git checkout v0.1-EdgeDevice

# Slim install — pure-Python physics + edge, no torch/CUDA needed
pip install -e ".[dev]"
pytest tests/edge tests/convergence      # 50 tests, runs anywhere
```

- The `tests/edge` and `tests/convergence` suites import only pure Python and run in
  [CI](.github/workflows/ci.yml) on every push.
- The `tests/vision` suite exercises TensorRT/torch and needs a CUDA-capable machine
  (`pip install -e ".[jetson,thermal]"`).
- To run the full stack locally, see **[howRun.md](howRun.md)** (`docker compose` two-service stack).

## Pull requests

1. Branch from `v0.1-EdgeDevice`.
2. Keep changes focused; one logical change per PR.
3. Add or update tests for behaviour changes (physics changes especially).
4. Run `pytest tests/edge tests/convergence` locally — keep it green.
5. Use [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, …).
6. Never commit secrets. `.env`, `.env.*`, and `*.local` are git-ignored — commit only `docker/.env.example`.

## Reporting issues

- **Bugs / false positives:** use the [issue templates](.github/ISSUE_TEMPLATE).
- **Security vulnerabilities:** do **not** open a public issue — see [SECURITY.md](SECURITY.md).

By participating you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).
