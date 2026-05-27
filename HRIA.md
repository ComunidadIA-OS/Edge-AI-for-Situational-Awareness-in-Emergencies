# Heimdall — Human Rights Impact Assessment (HRIA)

> **Resumen (ES).** Este documento es la **evaluación de impacto en derechos humanos** de Heimdall,
> el sistema de detección de incendios en el borde (drone + NVIDIA Jetson) con predicción física de
> propagación y dashboard de mando. Se realiza en cumplimiento del entregable obligatorio §9.2(4) y
> del §12 de los Términos y Condiciones del *Reto IA Responsable y Abierta en Industria*, usando como
> guía la herramienta del **Programa de las Naciones Unidas para el Desarrollo (PNUD)** disponible en
> [hria.eu](https://hria.eu/#use-cases). El análisis identifica los derechos potencialmente afectados
> (vida y seguridad, privacidad, protección de datos, no discriminación, tutela efectiva, medio ambiente
> sano), valora su probabilidad y severidad, y documenta las medidas de mitigación y el riesgo residual.
> Principio rector: **Heimdall es siempre asesor, nunca autónomo** — toda salida exige validación humana.

---

## 1. About this assessment

| | |
|---|---|
| **System assessed** | Heimdall — Edge AI for Situational Awareness in Emergencies (v0.1, TRL 3–4) |
| **Assessment type** | Human Rights Impact Assessment (HRIA) / human-rights self-assessment |
| **Methodology** | UN Guiding Principles on Business and Human Rights (UNGP); UNDP HRIA tool ([hria.eu](https://hria.eu/#use-cases)); alignment with the EU AI Act risk approach |
| **Regulatory framing** | Universal Declaration of Human Rights (UDHR), EU Charter of Fundamental Rights, GDPR (Reg. (EU) 2016/679), EU AI Act (Reg. (EU) 2024/1689) |
| **Scope** | The released software and model (`Heimdall-Vision-TensorRT-F16`), as published. Operational deployment by third parties is out of direct control and is addressed via downstream obligations. |
| **Status** | Living document — to be reviewed at each release and before any operational deployment |
| **Contact / grievances** | sbriceno@paintec.es (same channel as [SECURITY.md](SECURITY.md)) |

This assessment documents the analysis required by the hackathon Terms & Conditions. Teams are also
expected to run their use case through the UNDP tool at [hria.eu](https://hria.eu/#use-cases); the
content below is structured to map directly onto that tool's questionnaire.

## 2. System description

Heimdall provides real-time wildfire situational awareness, from the edge to the command post:

- **Perception (edge).** A drone carrying an NVIDIA Jetson runs a single-class (`fire`) thermal
  detector — an Ultralytics YOLO26 model fine-tuned on 1,500+ **thermal** images and exported to
  TensorRT FP16. It detects fire in the thermal feed and posts detections to the convergence service.
- **Forecast (edge/local).** The convergence service enriches each detection with weather (Open-Meteo)
  and computes fire spread using an **explainable physical model** (Balbi 2015 rate-of-spread + standard
  fuel models), not an opaque end-to-end network. It exposes a typed `MeteoReport v1` REST contract.
- **Decision support (command post).** A Ground Control dashboard (Next.js, MapLibre GL, Deck.gl)
  renders detections and the forecast for human responders.

**Key design properties relevant to human rights:**

- **Advisory, never autonomous.** The system informs human decision-makers; it never actuates and never
  dispatches resources. Every output requires human-in-the-loop validation.
- **Thermal, single-class perception.** The model detects only `fire`. It is not a person detector, does
  not classify people, and uses thermal (not RGB) imagery, which carries far lower biometric
  identifiability than visible-spectrum video.
- **Explainable safety-critical path.** The forecast is a citable physical model that can be audited,
  cited, and contested — not a black box.
- **Data minimisation by design.** The convergence service keeps an **in-memory, per-process** cache and
  ring buffer; it persists no personal data by design. Training data is not redistributed.
- **Open by construction.** Code is Apache-2.0; the YOLO-derived vision path and weights are AGPL-3.0.

## 3. Rights-holders and stakeholders

- **Members of the public** in or near the monitored area, including people who may be incidentally
  captured in thermal imagery (e.g. residents, hikers, displaced persons during an evacuation).
- **Emergency responders and operators** who rely on Heimdall's advisory outputs.
- **Vulnerable groups** who may be disproportionately affected by wildfire or by an evacuation decision
  (people with reduced mobility, elderly people, children, isolated rural communities).
- **Deploying organisations** (civil-protection agencies, operators) and **society/the environment** at
  large, which benefit from faster, better-informed wildfire response.

## 4. Human rights impact analysis

Severity and likelihood are rated **Low / Medium / High**. Severity considers scale, scope and
remediability per UNGP.

| # | Right (instrument) | Nature of impact | Likelihood | Severity | Residual risk |
|---|--------------------|------------------|:---------:|:--------:|:-------------:|
| 1 | **Life & physical security** (UDHR 3) | **Positive** — faster, better-informed wildfire response. Risk if an advisory error misdirects resources. | Medium | High | Low |
| 2 | **Privacy** (UDHR 12; Charter 7) | Thermal imagery may incidentally capture people; aerial monitoring. | Medium | Medium | Low |
| 3 | **Personal data protection** (Charter 8; GDPR) | Geolocation/telemetry; potential to process personal data if misdeployed. | Low | Medium | Low |
| 4 | **Equality & non-discrimination** (UDHR 7) | Uneven detection performance across terrains/climates/cameras could yield unequal protection. | Medium | Medium | Medium |
| 5 | **Effective remedy & accountability** (UDHR 8) | Diffuse responsibility for an advisory error. | Low | Medium | Low |
| 6 | **Healthy environment** (UNGA 2022 A/RES/76/300) | **Positive** — protects ecosystems and property from wildfire. | High | — | Positive |
| 7 | **Freedom of movement / expression** (UDHR 13, 19) | Possible chilling effect from aerial monitoring. | Low | Low | Low |
| 8 | **Good administration / transparency** | **Positive** — explainable physics forecast supports informed, contestable decisions. | High | — | Positive |

### 4.1 Right to life and physical security — *primary positive impact*
Heimdall's purpose is to shorten the time between "a drone sees fire" and "the command post sees where
it will be," which directly supports the protection of life and property. The corresponding risk is
**over-reliance**: a false negative (missed fire) or an inaccurate forecast could misdirect responders.
This is mitigated by the advisory-only design, the human-in-the-loop requirement, the explainable
forecast (operators can sanity-check it against doctrine), and an explicit **no-certification** statement.

### 4.2 Right to privacy
Aerial thermal monitoring may incidentally capture people. Identifiability is structurally limited
because (a) imagery is **thermal, not RGB**, (b) the model detects **only fire** and performs no person
detection or identification, and (c) the pipeline **persists no imagery of people** by design. Residual
privacy risk is low and is further reduced by the privacy-by-design roadmap item (on-device handling of
incidental persons) and by downstream-consumer obligations (§6).

### 4.3 Personal data protection (GDPR)
By design Heimdall does not collect or persist personal data: detection state lives in an in-memory,
per-process cache. The main exposure is operational misconfiguration — e.g. the sprint default
`CORS_ORIGINS=*` and the absence of API authentication. These are documented limitations and are
explicit roadmap items (authenticated API, TLS, audit logging). Deployers acting as data controllers
must run a GDPR DPIA for their specific context.

### 4.4 Equality and non-discrimination
Heimdall does not classify people, so direct discrimination risk is low. The substantive concern is
**representational/performance bias**: a model trained on 1,500+ thermal images may detect less reliably
in under-represented terrains, climates, vegetation or camera types, which could translate into unequal
protection across communities. This is the **highest residual risk** and is addressed by the roadmap
(dataset expansion, robustness and equity testing across conditions) and by transparent disclosure of
limitations in the [model card](../../tree/v0.1-EdgeDevice/models/MODEL_CARD.md).

### 4.5 Effective remedy and accountability
Because the system is advisory and a human always decides, legal and operational responsibility remains
with the human decision-maker and the deploying organisation. Accountability is supported by the
explainable forecast and by the planned audit-logging roadmap item. A grievance/contact channel is
provided (§7).

### 4.6 Healthy environment & 4.7 freedom of movement/expression
The environmental impact is positive (wildfire mitigation). Any chilling effect from aerial monitoring is
low and bounded by **purpose limitation** (fire only), thermal-only sensing, and the emergency context;
deployers should be transparent about where and when drones operate.

### 4.8 Transparency and explainability
Confining machine learning to **perception** and computing the safety-critical **forecast** with a
citable physical model is a deliberate human-rights-protective choice: decisions can be explained,
audited and contested, supporting informed administration and effective remedy.

## 5. EU AI Act positioning

Heimdall supports emergency response, an area the EU AI Act treats with care. The Annex III high-risk
category for emergency services targets AI used **to evaluate/classify emergency calls or to dispatch,
or to set priority in dispatching, first-response services**. Heimdall does **not** dispatch, prioritise
dispatching, or classify calls — it provides situational-awareness information to humans who decide.
Its design (advisory-only, human oversight, transparency, technical documentation via the model card)
is aligned with the Act's expectations for trustworthy AI. **Any deployer who wires Heimdall into an
automated dispatch or prioritisation pipeline would change its risk classification and must re-assess
under the AI Act before doing so.**

## 6. Mitigation measures (summary)

- **Human-in-the-loop, advisory-only** at every milestone; no automated actuation or dispatch.
- **Explainable forecast** (Balbi 2015 + fuel models) instead of a black box.
- **Thermal, single-class perception**; no person detection or identification.
- **Data minimisation**: in-memory state, no personal-data persistence, training data not redistributed.
- **Transparency**: model card with intended use and limitations; open licensing; this HRIA.
- **No-certification statement**: prototype, re-validate before operational use.
- **Downstream obligations**: consumers of `/latest` must comply with applicable privacy and safety law.
- **Roadmap commitments** (see [README → Roadmap](README.md#roadmap)): dataset expansion + equity/robustness
  testing; authenticated API + TLS + audit logging; privacy-by-design handling of incidental persons;
  durable, auditable history; field validation with human-factors evaluation.

## 7. Governance, monitoring and grievance mechanism

- **Ownership.** The maintainers are responsible for this assessment and its review.
- **Review cadence.** Reviewed at each release and **before any operational deployment**; updated when
  the model, data, or deployment context changes materially.
- **Monitoring.** Performance and limitations are tracked via the model card and the roadmap items above.
- **Grievance / reporting.** Concerns about rights impacts, privacy, or safety can be reported to
  **sbriceno@paintec.es** (the channel defined in [SECURITY.md](SECURITY.md) and
  [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)). Reports are acknowledged and triaged.

## 8. Conclusion

Heimdall's primary human-rights impact is **positive**: it strengthens the right to life, physical
security and a healthy environment by accelerating informed wildfire response. Its main residual risks —
incidental privacy capture and representational performance bias — are **low-to-medium** and are
structurally constrained by design (thermal-only, single-class, advisory-only, explainable, data-minimal)
and actively managed through the roadmap. The deliberate decision to keep humans in the loop and to use
an explainable physical model for the safety-critical forecast is the central safeguard of this design.

---

<sub>Conducted for the SEDIA · *Reto IA Responsable y Abierta en Industria* · Aragón 2026, using the UNDP
HRIA tool ([hria.eu](https://hria.eu/#use-cases)). Living document — last reviewed 2026-05-27.</sub>
