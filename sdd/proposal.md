# RFC-001: YOLO26m Thermal Fire Detection for XHeimdall

**Status**: PROPOSED | **Author**: SDD Propose Subagent | **Date**: 2026-05-22
**Phase**: `sdd-propose` | **Target**: `sdd-spec` upon approval

---

## 1. Título y Resumen Ejecutivo

Entrenar **YOLO26m** (NMS-free, Ultralytics) sobre imágenes térmicas con un **pipeline de auto-etiquetado basado en umbrales de temperatura real (°C)** para detección de incendios forestales/quemas prescritas.
El modelo se entrena en **AWS SageMaker (g5.12xlarge)** con ~1,500 imágenes auto-etiquetadas de FLAME 3 y Hanna Hammock, se exporta a **TensorRT FP16** y se despliega en **NVIDIA Jetson AGX** a 25–35 FPS.

**Problema**: Hay 428 GB de datos térmicos sin una sola etiqueta ni línea de código operativa. Se necesita un pipeline completo desde cero — auto-label, training, export, deploy — en 4 semanas.

**Para quién**: Operadores de drones/UAV con cámaras térmicas (FLIR Boson, Workswell WIRIS) que necesitan detección de fuego en tiempo real onboard.

**Propuesta**: Auto-label pipeline con 4 filtros en cascada (temperatura absoluta → gradiente térmico → área/forma → DBSCAN clustering) sobre TIFFs Celsius → SageMaker training job → TensorRT FP16 → Jetson AGX.

---

## 2. Contexto y Motivación

### 2.1 ¿Por qué ahora?

- **Los datos existen y son accionables**. FLAME 3 (622 fire + 116 no-fire) tiene TIFFs con temperatura real en °C, no imágenes 8-bit normalizadas. El umbral de 150°C captura el 98.2% de incendios con **cero falsos positivos** — esto es un hecho medido, no una hipótesis.
- **Hanna Hammock** (794 frames durante quema prescrita, 0–197°C) complementa con incendios más fríos, necesarios para que el modelo no tenga sesgo hacia fuegos intensos.
- **El hardware objetivo está definido**: Jetson AGX (32 GB unified memory, 512 Tensor Cores). No hay ambigüedad sobre constraints de deployment.
- **YOLO26 es NMS-free**. Esto elimina el post-procesamiento de Non-Maximum Suppression, simplificando el deployment en Jetson y reduciendo latencia.

### 2.2 ¿Qué respalda esta decisión?

| Evidencia | Fuente | Confianza |
|-----------|--------|-----------|
| Auto-label con 150°C: 98.2% catch rate, 0% FP | Análisis de 738 TIFFs FLAME | **Alta** — medido |
| No-fire FLAME: máx 47.2°C | 116 TIFFs analizados | **Alta** — medido |
| Hanna Hammock: 0–197°C, quemas más frías | Muestra de TIFFs LZW | **Media** — requiere batch completo |
| Jetson AGX soporta TensorRT FP16 a 25–35 FPS | Benchmarks YOLO26m en Jetson Orin | **Media** — estimado, no medido en este hardware |
| 1,500 imágenes auto-etiquetables totales | Conteo de datasets | **Alta** |

### 2.3 ¿Qué pasa si no lo hacemos?

- **428 GB de datos sin usar**. Sin pipeline de auto-label, se necesitarían semanas de anotación manual para obtener ~1,500 bounding boxes. Costo: ~$3,000–5,000 USD en anotadores o tiempo de voluntarios.
- **Sin modelo onboard**, los drones térmicos operan a ciegas — el operador humano debe identificar fuego visualmente en tiempo real, con fatiga y error humano.
- **Oportunidad perdida**: XHeimdall tiene una ventaja única (datos radiométricos en °C) que la mayoría de datasets públicos no ofrecen. No aprovecharla ahora implica que otro equipo o proyecto lo hará después con los mismos datos.

### 2.4 Posición única de XHeimdall

A diferencia de datasets públicos (FLIR ADAS, KAIST Multispectral) que entregan imágenes térmicas 8-bit sin metadatos de temperatura, XHeimdall tiene:

- **FLAME Celsius TIFFs**: arrays float32 con valores reales en °C (-22.8°C a 573°C)
- **Hanna Hammock geo_thermal_tiff_celsius**: TIFFs georreferenciados con °C
- **FLIR IRG**: JPEG radiométrico con temperatura embebida (extraíble vía exiftool/pyflir)

Esto significa que **el auto-label no requiere adivinar umbrales** — usa física: `pixel > 150°C → fuego`.

---

## 3. Enfoques Evaluados

### 3A. Infraestructura de Training

#### A) SageMaker Training Job + Custom Docker (← RECOMENDADO)

| Dimensión | Evaluación |
|-----------|------------|
| **Descripción** | Docker container con Ultralytics + CUDA sobre `ultralytics/ultralytics:latest`. Training job efímero en `ml.g5.12xlarge` (4× A10G). Datos desde S3 vía `TrainingInput`. Output a `s3://xheimdall-models/`. Spot instances para reducir costo. |
| **Pros** | (1) Multi-GPU nativo (4× A10G, batch=128 efectivo). (2) Jobs efímeros — solo pagas durante training (~10h = ~$57). (3) Reproducible: Dockerfile versionado, mismo container en cualquier región. |
| **Contras** | (1) Cold start: 5–10 min para levantar instancia + cargar Docker + descargar datos de S3. (2) Sin acceso interactivo durante training — debugging requiere re-lanzar job. (3) Curva de aprendizaje SageMaker SDK + IAM roles. |
| **Esfuerzo** | **M** — Dockerfile (~20 líneas) + script de entrypoint + configuración SageMaker SDK |
| **Impacto** | **Alto** — training multi-GPU profesional, reproducible, costo controlado |

#### B) SageMaker Notebook Instance

| Dimensión | Evaluación |
|-----------|------------|
| **Descripción** | Notebook Jupyter persistente en `ml.g5.4xlarge` (1× A10G). Desarrollo interactivo, training desde el notebook con `model.train()`. |
| **Pros** | (1) Iteración rápida: modificas hiperparámetros y re-entrenas sin re-lanzar jobs. (2) Visualización inmediata de curvas de loss, muestras de validación. (3) Útil para fase de experimentación/desarrollo. |
| **Contras** | (1) Solo 1 GPU (A10G 24 GB) — batch limitado, training más lento. (2) La notebook sigue facturando aunque no esté entrenando (se paga por hora de instancia activa). (3) No escala a multi-GPU sin migrar a Training Job. |
| **Esfuerzo** | **S** — crear notebook, clonar repo, ejecutar |
| **Impacto** | **Medio** — bueno para dev, limitado para training final |

#### C) Google Colab / Kaggle Notebooks (RECHAZADO)

| Dimensión | Evaluación |
|-----------|------------|
| **Descripción** | Notebook gratuito con GPU T4 (16 GB). Subir dataset parcial, entrenar YOLO26s. |
| **Pros** | (1) Costo $0. (2) Sin configuración de infraestructura. |
| **Contras** | (1) **No cabe el dataset**: 428 GB vs ~70 GB disponibles en Colab Pro+. (2) GPU T4 es 3–4× más lenta que A10G. (3) Desconexiones aleatorias en tier gratuito. (4) No escala a TensorRT export para Jetson. |
| **Esfuerzo** | **S** (intentarlo) / **XL** (hacerlo funcionar) |
| **Impacto** | **Bajo** — inviable para dataset completo |

#### D) Local GPU Workstation

| Dimensión | Evaluación |
|-----------|------------|
| **Descripción** | Si el usuario tiene GPU local (RTX 3090/4090 o similar), entrenar directamente en Windows/Linux con datos locales. |
| **Pros** | (1) Sin costos de cloud. (2) Sin latencia S3 — datos en disco local. (3) Control total del entorno. |
| **Contras** | (1) **No confirmado** — no sabemos si existe GPU local. (2) Una GPU = training más lento que 4× A10G. (3) Sin separación de environments — riesgo de contaminación con otros proyectos. |
| **Esfuerzo** | **M** (si GPU existe) / **XL** (si hay que comprar hardware) |
| **Impacto** | **Alto** (si existe) / **Nulo** (si no) |

---

### 3E. Modelo: YOLO26m vs YOLO26s vs YOLO26n

| Dimensión | YOLO26n | YOLO26s | YOLO26m ← REC | YOLO26l |
|-----------|---------|---------|---------|---------|
| **Parámetros** | 3.2M | 9.4M | 25.3M | 46.5M |
| **mAP@50 (COCO, referencia)** | ~38% | ~45% | ~50% | ~53% |
| **Jetson AGX FPS (FP16 est.)** | 60+ | 40–50 | **25–35** | 15–20 |
| **VRAM training (batch=32)** | ~4 GB | ~8 GB | **~16 GB** | ~28 GB |
| **¿Apto para 1-clase térmico?** | Baja capacidad — puede fallar con fuegos pequeños | Balanceado, pero accuracy marginal | **Recomendado** — mejor accuracy sin sacrificar FPS | Overkill — 1 clase no necesita 46M params |
| **Veredicto** | ❌ Sub-entrenado | ⚠️ Opción B | ✅ **Primary** | ❌ Exceso |

**Decisión**: YOLO26m. Con 1 sola clase (`fire`) y ~1,500 imágenes de training, YOLO26n/s tienen riesgo de underfitting en bordes de fuego pequeños y fuegos prescritos fríos. YOLO26m ofrece margen de capacidad sin comprometer el target de 25–35 FPS en Jetson AGX.

---

### 3F. Precisión de Export: FP16 vs INT8 vs FP32

| Dimensión | FP32 | FP16 ← REC | INT8 |
|-----------|------|-----------|------|
| **Jetson FPS (est.)** | 12–18 | **25–35** | 50–70 |
| **Precisión relativa** | Baseline | ~0.3% mAP loss | ~1–2% mAP loss |
| **Tamaño engine** | ~100 MB | ~50 MB | ~25 MB |
| **Complejidad** | Trivial | Trivial (`half=True`) | Requiere dataset de calibración (~100 imágenes) |
| **Memoria Jetson** | 2× FP16 | **1×** | 0.5× FP16 |
| **Veredicto** | ❌ Muy lento | ✅ **Primary** | ⚠️ Fase 2 |

**Decisión**: FP16 para v1. La pérdida de accuracy es negligible (~0.3% mAP) y el speedup es 2× sobre FP32. INT8 se reserva para optimización post-deployment si el modelo no alcanza 25 FPS sostenidos.

---

### 3G. Estrategia de Datos: Thermal-Only vs RGB+Thermal Fusion

| Dimensión | Thermal-Only ← REC | RGB+Thermal Fusion |
|-----------|---------------------|---------------------|
| **Descripción** | Entrenar solo con JPGs térmicos false-color (3-canales, 8-bit). El modelo aprende a mapear color → temperatura → fuego. | Modelo bimodal: una rama para thermal, otra para RGB. Late fusion o early fusion. |
| **Pros** | (1) Pipeline simple — un solo tipo de input. (2) Las cámaras objetivo (FLIR Boson) ya entregan false-color. (3) Auto-label solo necesita TIFF + JPG correspondiente. | (1) RGB puede confirmar fuego en casos ambiguos (humo visible, contexto visual). (2) Potencialmente más robusto. |
| **Contras** | (1) Diferentes cámaras térmicas usan diferentes paletas de color → riesgo de domain gap. (2) Sin contexto visual — puede confundir superficies calientes no-fuego (tubos de escape, rocas al sol). | (1) Requiere datos pareados RGB+Thermal alineados (homografía). (2) 2× más datos, 2× más VRAM. (3) Más complejo de exportar a TensorRT. (4) El dron del usuario puede no tener cámara RGB. |
| **Esfuerzo** | **M** | **XL** |
| **Impacto** | **Alto** | **Medio** (future phase) |
| **Veredicto** | ✅ **v1** | ⚠️ **v2** (si hay datos pareados) |

---

## 4. Recomendación

### 4.1 Enfoque Elegido

| Componente | Elección | Justificación |
|------------|----------|---------------|
| **Training infra** | SageMaker Training Job + Custom Docker (A) | Multi-GPU, efímero, reproducible, costo controlado |
| **Dev infra** | SageMaker Notebook (B) para experimentación | Iteración rápida antes del job final |
| **Modelo** | YOLO26m (E) | Mejor balance accuracy/FPS para 1-clase térmico en Jetson AGX |
| **Precisión** | FP16 (F) | 2× speedup con pérdida negligible |
| **Input** | Thermal-only false-color JPGs (G) | Pipeline más simple, cubre el caso de uso principal |
| **Auto-label** | 4-filtro cascade: temp > threshold → ∇T > 40°C/px → área ≥ 50px + aspecto < 8:1 → DBSCAN + K-Means subdivision | Validado en dataset FLAME, físicamente fundamentado, sin falsos positivos |

### 4.2 Criterios de Éxito (KPIs)

#### Modelo

| Métrica | Target | Medición |
|---------|--------|----------|
| **mAP@0.5** (fire) | ≥ 0.85 | Sobre test set (temporal-aware split, ~360 imágenes) |
| **mAP@0.5:0.95** (fire) | ≥ 0.55 | COCO-style, promediado sobre IoU 0.5–0.95 |
| **Recall** (fire) | ≥ 0.90 | ¿De todos los fuegos reales, cuántos detecta? |
| **Precision** (fire) | ≥ 0.85 | De todas las detecciones, ¿cuántas son fuego real? |
| **False Positive Rate** (no-fire) | ≤ 0.05 | Sobre 116 imágenes no-fire de FLAME + pre/post-burn de Hanna Hammock |
| **FPS en Jetson AGX** (TensorRT FP16) | ≥ 25 FPS | Medido con `model.predict()` en loop, excluyendo I/O de cámara |

#### Auto-Label Pipeline

| Métrica | Target | Medición |
|---------|--------|----------|
| **Precision** (bboxes generados vs ground truth) | ≥ 0.95 | Sobre 10% HITL review de FLAME (muestra de 60 imágenes) |
| **Recall** (bboxes generados vs todos los fuegos reales) | ≥ 0.90 | Misma muestra |
| **Mean IoU** (bbox generado vs bbox anotado manualmente) | ≥ 0.75 | Misma muestra |
| **Tiempo de procesamiento** por TIFF | ≤ 2 segundos | En CPU local (Ryzen/i7), 640×512 TIFF |

### 4.3 Timeline (4 semanas)

```
SEMANA 1 (M1): Auto-Label Pipeline
├── Día 1-2: Instalar dependencias (imagecodecs, opencv-python, tifffile, scikit-learn)
├── Día 2-4: Implementar pipeline completo:
│   ├── thermal_io.py: lectores de TIFF Celsius + TIFF LZW + IRG
│   ├── auto_label.py: cascade de 4 filtros + DBSCAN + K-Means
│   └── prepare_data.py: orquestador → YOLO labels + split temporal-aware
├── Día 4-5: Ejecutar pipeline sobre 738 FLAME TIFFs
├── Día 5-6: Ejecutar pipeline sobre 794 Hanna Hammock TIFFs
├── Día 6-7: HITL review 10% de etiquetas generadas (60 FLAME + 80 Hanna)
└── Día 7:     Ajustar thresholds si es necesario, re-ejecutar pipeline
    ENTREGABLE: ~1,500 imágenes etiquetadas en formato YOLO + split train/val/test

SEMANA 2 (M2): SageMaker Training
├── Día 1-2: Configurar S3 buckets (xheimdall-datasets, xheimdall-models)
├── Día 2-3: Rotar credenciales AWS expuestas, configurar IAM roles mínimos
├── Día 3-4: Subir dataset a S3 (aws s3 sync, ~2-4 horas)
├── Día 4-5: Escribir Dockerfile + train_sagemaker.py entrypoint
├── Día 5-6: Training run #1 en SageMaker Notebook (g5.4xlarge, interactivo):
│   ├── epochs=100, batch=32, imgsz=640
│   └── Validar que pipeline funciona end-to-end
├── Día 6-7: Training run #2 en SageMaker Training Job (g5.12xlarge):
│   ├── epochs=200-300, batch=128 (4× A10G × 32), patience=30
│   └── Monitorear curvas de loss, early stopping si es necesario
└── Día 7:     Descargar best.pt a local
    ENTREGABLE: best.pt con mAP@0.5 ≥ 0.85 en test set

SEMANA 3 (M3): Evaluación + TensorRT Export
├── Día 1-2: Evaluación completa sobre test set:
│   ├── mAP, precision, recall, confusion matrix
│   ├── Análisis de falsos positivos (¿qué confunde al modelo?)
│   └── Análisis de falsos negativos (¿qué fuegos no detecta?)
├── Día 2-3: Si mAP < 0.85 → hyperparameter tuning run
├── Día 3-4: TensorRT FP16 export (en SageMaker GPU o GPU local)
│   ├── yolo export model=best.pt format=engine half=True imgsz=640 workspace=4
│   └── Validar que engine carga y predice correctamente
├── Día 4-5: Benchmark de velocidad en GPU de training (FPS reference)
├── Día 5-7: Documentación de métricas finales + preparación para Jetson
└── Día 7:     Script infer_jetson.py listo
    ENTREGABLE: best.engine (FP16) + reporte de evaluación + script de inferencia

SEMANA 4 (M4): Jetson AGX Deployment + Live Test
├── Día 1-2: Configurar Jetson AGX (JetPack, ultralytics ARM64, TensorRT)
├── Día 2-3: Copiar best.engine a Jetson, validar carga
├── Día 3-4: Prueba con video pregrabado (FLAME o Hanna Hammock JPGs)
├── Día 4-5: Prueba con cámara térmica real (FLIR Boson vía GStreamer)
├── Día 5-6: Medir FPS reales en Jetson, ajustar confianza/IoU thresholds
├── Día 6-7: Documentación de deployment + buffer para imprevistos
└── Día 7:     Demo final: cámara térmica → detección en tiempo real
    ENTREGABLE: Sistema funcionando en Jetson AGX a ≥ 25 FPS con live thermal feed
```

---

## 5. Riesgos y Mitigaciones

### 5.1 Matriz de Riesgos

| # | Riesgo | Probabilidad | Impacto | Mitigación |
|---|--------|-------------|---------|------------|
| **R1** | **Credenciales AWS expuestas en `secrets/heimdall_accessKeys.csv`** | **Alta** (ya ocurrió) | **Crítico** — compromiso de cuenta | **Rotar inmediatamente** en IAM console. Migrar a variables de entorno. Verificar `.gitignore` incluye `secrets/`. Usar IAM roles (no access keys) para SageMaker. |
| **R2** | **Temporal leakage en split** | **Alta** (si se hace random split) | **Alto** — métricas de validación infladas artificialmente | Split por grupo (video/plot), no por frame. FLAME: primeros 70% frames → train, siguientes 15% → val, últimos 15% → test. Hanna Hammock: plot 1 → train, plot 2 pt1 → val, plot 2 pt2 → test. |
| **R3** | **False-color JPG variability entre cámaras** | **Media** | **Alto** — modelo no generaliza entre FLIR Boson, Workswell WIRIS, DJI thermal | (1) Standardizar paleta de color en preprocesamiento (aplicar misma LUT a todos los JPGs). (2) Data augmentation: simular diferentes paletas (shuffle de canales, inversión). (3) Si es crítico, migrar a raw TIFF → custom dataloader en v2. |
| **R4** | **Class imbalance 12:1 (fire:no-fire)** | **Alta** (1,400 fire vs 116 no-fire) | **Medio** — falsos positivos altos en producción | (1) Weighted sampling: oversample no-fire 3× por epoch. (2) Agregar 418 frames pre/post-burn de Hanna Hammock como negativos adicionales. (3) Generar negativos sintéticos: invertir threshold (mantener solo regiones < 50°C de imágenes fire). (4) Class weights en loss function. |
| **R5** | **LZW-compressed TIFFs (Hanna Hammock) no legibles** | **Media** | **Medio** — pérdida de 794 imágenes de training | (1) `imagecodecs` ya está instalado y verificado. (2) Fallback: GDAL para descompresión. (3) Fallback: extraer temperatura de FLIR IRG en vez de TIFF. |
| **R6** | **SageMaker cold start** (5–10 min para levantar job) | **Media** | **Bajo** — solo afecta tiempo de espera, no resultado | Usar spot instances con persistencia de checkpoint en S3. Si el job se interrumpe, resume desde último checkpoint. |
| **R7** | **Domain gap: dataset ≠ drone del usuario** | **Media** | **Alto** — modelo entrenado en FLIR/Workswell falla con cámara del usuario | (1) Incluir data augmentation agresivo (brightness ±30%, contrast ±20%, ruido gaussiano). (2) Si es posible, obtener 10–20 imágenes de la cámara objetivo para fine-tuning rápido (5–10 epochs). (3) Standardizar paleta de color. |
| **R8** | **Fuegos pequeños (< 50 px²) no detectados** | **Media** | **Medio** — incendios incipientes pasan desapercibidos | El filtro de área mínima (50 px) es configurable. Reducir a 20 px con cleanup morfológico. Alternativa: YOLO26m puede aprender a detectar regiones < 50 px si las ve en training (el umbral de 50 px es del auto-label, no del modelo). |
| **R9** | **mAP no alcanza 0.85 en test set** | **Baja** | **Alto** — modelo no cumple criterios de éxito | (1) Si mAP < 0.80: considerar más datos (frame pairs #8 con anotación manual parcial). (2) Si 0.80–0.85: hyperparameter tuning (learning rate, weight decay, augmentation). (3) Si > 0.85: criterio cumplido. |
| **R10** | **Jetson FPS < 25 con FP16** | **Baja** | **Medio** — no cumple target de tiempo real | (1) Reducir imgsz a 512 o 416. (2) Migrar a INT8 (fase 2). (3) Considerar YOLO26s como fallback (40–50 FPS). |

### 5.2 Estrategia de Mitigación para R3 (False-Color Variability)

Este es el riesgo técnico más sutil. Diferentes fabricantes de cámaras térmicas usan diferentes paletas de false-color:

| Cámara | Paleta típica |
|--------|---------------|
| FLIR Boson | White-hot: frío=negro, caliente=blanco |
| Workswell WIRIS | Ironbow: frío=negro→púrpura→rojo→amarillo→blanco |
| DJI Zenmuse H20T | White-hot o Ironbow (configurable) |
| FLAME dataset (Teledyne FLIR) | Rainbow/ironbow |
| Hanna Hammock | Similar a FLAME |

**Mitigación propuesta**:
1. **Preprocesamiento**: Convertir todos los JPGs a escala de grises y luego re-aplicar una paleta estándar (ironbow o white-hot). Esto normaliza el input.
2. **Augmentation**: Durante training, aplicar ChannelShuffle (permutar canales RGB del false-color) y RandomSolarize para simular diferentes paletas.
3. **Validación**: Test set debe incluir al menos 2 fuentes de cámara diferentes (FLAME vs Hanna Hammock).

---

## 6. Siguientes Pasos

### 6.1 Próxima Fase: `sdd-spec`

Una vez aprobada esta propuesta, la fase `sdd-spec` producirá:
- **API de auto-label pipeline**: contrato de entrada/salida de cada módulo (`thermal_io.py`, `auto_label.py`, `prepare_data.py`)
- **Esquema de datos**: formato exacto de labels YOLO, estructura de directorios S3, `data.yaml`
- **Contrato de SageMaker Training Job**: Dockerfile, variables de entorno, canales de entrada/salida
- **Interfaz de inferencia Jetson**: API de `infer_jetson.py`, formato de entrada (GStreamer / numpy array), formato de salida (bboxes + confidence)
- **Criterios de aceptación por módulo**: tests unitarios para cada filtro del pipeline, tests de integración end-to-end

### 6.2 Dependencias a Resolver Antes de Empezar

| Dependencia | Estado | Acción requerida |
|-------------|--------|------------------|
| ⚠️ **Credenciales AWS** | **EXPUESTAS** | **Rotar inmediatamente** — paso bloqueante |
| S3 buckets | No creados | Crear `xheimdall-datasets` y `xheimdall-models` en us-east-1 |
| IAM roles | No configurados | Crear rol SageMaker con permisos S3 (lectura datasets, escritura models) |
| Jetson AGX disponible | No confirmado | Verificar versión de JetPack, TensorRT, CUDA instalados |
| Modelo de cámara térmica | No confirmado | ¿FLIR Boson? ¿Resolución? ¿Formato de salida? |
| NADIRPlots duplicado | 34.92 GB | ¿Borrar para ahorrar espacio o mantener como backup? |
| YOLO26m.pt weights | Descargable | `from ultralytics import YOLO; YOLO("yolo26m.pt")` |

### 6.3 Decisiones Pendientes del Usuario

1. **¿Procedemos con SageMaker?** ¿Hay presupuesto aprobado para ~$120–150 el primer mes?
2. **¿Qué cámara térmica se usará en el Jetson?** FLIR Boson (640×512), modelo específico, formato de salida.
3. **¿Borrar NADIRPlots?** Son 34.92 GB duplicados de Hanna Hammock.
4. **¿Single class `fire` o agregar `smoke` / `hotspot`?** La recomendación es single class para v1.
5. **¿Target de FPS exacto?** ¿25 FPS mínimo o 30+ FPS requerido? Esto determina si necesitamos INT8.
6. **¿Frame Pairs #8 como datos de entrenamiento?** No son auto-etiquetables — requerirían anotación manual parcial.
7. **¿Fine-tuning con datos de la cámara del usuario?** Si podemos obtener 10–20 imágenes de la cámara objetivo, un fine-tuning rápido mejoraría significativamente la generalización.

---

## 7. Budget Breakdown

### 7.1 AWS Costos Estimados (Primer Mes)

| Recurso | Configuración | Horas estimadas | Costo/hora | Subtotal |
|---------|---------------|-----------------|------------|----------|
| **S3 Standard Storage** | 500 GB × 30 días | 720 h/mes | $0.023/GB-mes | **$11.50** |
| **SageMaker Training Job** (spot) | `ml.g5.12xlarge` | 10 h | ~$5.67 (on-demand) / ~$2.27 (spot) | **$22.70–$56.70** |
| **SageMaker Notebook** (dev) | `ml.g5.4xlarge` | 20 h | $1.89 | **$37.80** |
| **S3 Data Transfer** (upload) | 5 GB (labels + data.yaml) | — | $0.00 (upload es gratis) | **$0.00** |
| **S3 Data Transfer** (download best.pt) | ~50 MB | — | $0.00 (mínimo) | **$0.00** |
| **EC2 para TensorRT export** | `g5.4xlarge` (si no se hace en SageMaker) | 2 h | $1.89 | **$3.78** |
| **TOTAL primer mes** | | | | **$75.78–$109.78** |

### 7.2 Comparativa Spot vs On-Demand

| Modo | Costo training (10h) | Riesgo de interrupción | Recomendación |
|------|---------------------|------------------------|---------------|
| **Spot** | ~$22.70 | Moderado (se recupera con checkpointing) | ✅ **Recomendado** para training runs largos |
| **On-demand** | ~$56.70 | Ninguno | Usar para la primera run de validación (corta, 2–3h) |

### 7.3 Costos Recurrentes (Mensuales Post-Desarrollo)

| Recurso | Costo mensual |
|---------|---------------|
| S3 Storage (modelos + datasets) | ~$12 |
| S3 Data Transfer (si se re-entrena) | < $1 |
| **Total recurrente** | **~$12–15/mes** |

### 7.4 Costos No-AWS

| Concepto | Costo |
|----------|-------|
| Jetson AGX (si no se tiene) | $1,500–2,000 (hardware) |
| Cámara térmica FLIR Boson | $2,000–4,000 |
| Mano de obra (anotación manual si pipeline falla) | $0 (auto-label) / $3,000–5,000 (manual fallback, no esperado) |

---

## 8. Go / No-Go Checklist

Antes de avanzar a `sdd-spec`, el usuario debe confirmar:

- [ ] **Presupuesto aprobado**: ~$110 primer mes en AWS
- [ ] **Credenciales AWS rotadas**: `secrets/heimdall_accessKeys.csv` invalidado
- [ ] **Single class `fire`**: Aceptado para v1
- [ ] **YOLO26m + FP16**: Aceptado como configuración base
- [ ] **SageMaker Training Job + Custom Docker**: Arquitectura de training aceptada
- [ ] **Timeline 4 semanas**: Factible con los recursos actuales
- [ ] **Hardware Jetson**: Disponible para semana 4, con JetPack instalado
- [ ] **Cámara térmica**: Modelo y formato de salida conocidos para semana 4

---

## Appendix A: Alternativas Consideradas y Rechazadas

| Alternativa | Razón de rechazo |
|-------------|------------------|
| YOLOv8n/v11n | Demasiado pequeño para precisión aceptable en fuegos pequeños; Jetson AGX tiene capacidad para modelo más grande |
| Google Colab | Dataset de 428 GB no cabe en 70 GB de almacenamiento; GPU T4 insuficiente |
| Temporal flicker filter | Inválido para drone — cámara en movimiento invalida diff entre frames |
| Percentile-based threshold | Innecesario con datos reales en °C; umbral físico es más limpio y explicable |
| Homography alignment (para RGB+Thermal) | No necesario para v1; reservado para future dual-camera setup |
| Multi-class (flame, smoke, hotspot) | Smoke invisible en LWIR térmico; añade complejidad sin beneficio en v1 |

---

*Documento generado por SDD Propose subagent | Modelo: deepseek-v4-pro | RFC basado en skill `product-pitch-strategist-rfc-writer`*

*Próxima fase: `sdd-spec` (requiere aprobación de esta propuesta)*
