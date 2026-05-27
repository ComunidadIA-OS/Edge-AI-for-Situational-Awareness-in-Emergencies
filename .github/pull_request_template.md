---
name: Pull Request
about: Submit a change to the Heimdall edge stack
---

## Description

<!-- Describe the changes you are introducing. Link related issues. -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation
- [ ] Refactor / code quality
- [ ] Model / inference improvement

## Component

- [ ] convergence (weather / Balbi propagation)
- [ ] vision (thermal inference / detection)
- [ ] edge (orchestration / data pipeline)
- [ ] CI / tests
- [ ] documentation / config

## Licensing

<!-- READ BEFORE SUBMITTING — this branch is dual-licensed -->

- [ ] I confirm my contribution to `convergence/`, `edge/`, or configs is under **Apache-2.0**
- [ ] I confirm my contribution to `vision/` or model weights is under **AGPL-3.0** (derivative of Ultralytics YOLO26)
- [ ] N/A — documentation / CI only

## Checklist

- [ ] I have run `pytest tests/edge tests/convergence` and all tests pass
- [ ] I have added or updated tests for any behaviour changes
- [ ] I have not committed any secrets (`.env`, `.env.*`, `*.local` are git-ignored)
- [ ] My code follows the project conventions (no `any`, no `try/catch` abuse, type hints)
- [ ] If changing physics (Balbi constants, fuel models), I have cited the source
