# Security Policy

## Supported versions

Heimdall is a research and competition prototype. Only the latest release is supported.

| Version | Supported |
|---------|-----------|
| `0.1.x` (latest) | ✅ |
| older / unreleased | ❌ |

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

1. **Preferred:** open a private [GitHub Security Advisory](https://github.com/ComunidadIA-OS/Edge-AI-for-Situational-Awareness-in-Emergencies/security/advisories/new).
2. **Or email:** [sbriceno@paintec.es](mailto:sbriceno@paintec.es) (maintainer: [@AndreSaul16](https://github.com/AndreSaul16)).

We aim to acknowledge reports within a few working days. Please include reproduction steps and the affected component (vision / convergence / edge / dashboard).

## AI-safety scope

Heimdall is an **advisory** system, not an autonomous one. The following are by design, not vulnerabilities:

- **Human-in-the-loop required.** All outputs (detections, spread forecasts, risk buffers) are decision support for trained operators. The system never actuates and must never be treated as authoritative for life-safety decisions.
- **No certification.** Heimdall is not certified for operational emergency use. Re-validate against your own requirements before any field deployment.
- **Model outputs are probabilistic.** False positives (e.g. thermal noise classified as fire) and false negatives are expected. Report systematic misclassifications via the issue tracker.

## Data sensitivity

Thermal and RGB imagery may **incidentally capture people**. Operators and downstream consumers are responsible for complying with applicable privacy and data-protection law (e.g. GDPR). Heimdall does not redistribute training data.

## Out of scope

- **Model weights** (`Heimdall-Vision-TensorRT-F16`) are released **as-is** under AGPL-3.0. Validate accuracy for your conditions before relying on them.
- Third-party services (Open-Meteo, MapTiler) and their availability or terms.
