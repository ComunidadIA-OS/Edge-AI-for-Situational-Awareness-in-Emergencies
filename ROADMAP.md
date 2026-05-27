# Roadmap

*Hoja de ruta de desarrollo prevista.*

Heimdall is a **v0.1 prototype at TRL 3–4** (experimental proof-of-concept, validated in controlled conditions). The path below is organised by horizon, with each item tied to the current architecture and pointing toward an operationally relevant system (TRL 5–6). Heimdall stays **advisory, never autonomous** at every milestone — more capability never removes the human in the loop.

## Shipped in v0.1 (current state)
- **Thermal fire detection on the edge:** YOLO26 single-class (`fire`) detector, exported to TensorRT FP16 for Jetson AGX Orin, one-command deploy with audible alerts.
- **Physics-based spread forecast:** Balbi 2015 rate-of-spread + standard fuel models over Open-Meteo weather, served on the typed `MeteoReport v1` REST contract.
- **Ground Control dashboard:** Next.js + MapLibre GL + Deck.gl, with live connection banner, JSON inspector, and map/legend.
- **Hybrid open licensing:** (Apache-2.0 + AGPL-3.0), published model card, and full governance.

## Near-term — v0.2 · toward TRL 5 (validation in a relevant environment)
- **Multi-drone fusion.** Today one process serves one drone (`DRONE_ID`); aggregate detections from several drones into a single operational picture.
- **Detection robustness.** Grow the training with thermal images, add a `fire` class, and calibrate confidence with per-detection uncertainty to cut false positives/negatives.
- **Durable history.** Replace the in-memory `ReportHistory` ring buffer with persistent time-series storage so `dA/dt` and `d²A/dt²` survive restarts and feed post-incident analysis.
- **Field validation campaign.** Structured outdoor trials measuring detection and forecast accuracy against ground truth.

## Mid-term — v0.3 · operational features + security by design
- **Richer spread physics.** Add terrain/slope from a DEM, live fuel-moisture inputs, and multiple simultaneous fronts.
- **Authenticated API.** Move from the sprint default `CORS=*` to authn/authz, TLS, and audit logging on the convergence API.
- **Multi-incident dashboard.** Concurrent incidents, event replay/playback, alert routing, and role-based access.
- **Edge resilience.** Store-and-forward operation under degraded or intermittent connectivity.
- **Privacy by design.** On-device handling of incidental persons in thermal frames and documented data minimisation (see [HRIA.md](HRIA.md)).

## Long-term — operational pilot
- **Partner pilot** with a civil-protection / emergency-response organisation, including human-factors evaluation of the advisory UX by real operators.
- **Robustness & equity testing** across terrains, climates, and camera types, documented in the model card.
- **Standards alignment.** A path toward validation against operational and EU AI Act expectations for emergency-support tools — with no certification claim (see [Responsible AI](#-responsible-ai) and [HRIA.md](HRIA.md)).
- **Internationalisation & accessibility** (i18n, WCAG) on the dashboard.
