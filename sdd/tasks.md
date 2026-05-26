# XHeimdall — Task Backlog

**Phase**: `sdd-tasks` | **Date**: 2026-05-22 | **RFC**: RFC-001 YOLO26m Thermal Fire Detection
**Status**: READY FOR EXECUTION | **Subagent**: `sdd-tasks`
**Input**: `sdd/design.md` (21 technical decisions, 11-step build order), `sdd/spec.md` (13 modules, 11 ACs)

---

## Summary Table

| Ticket | Title | Priority | Estimate | Dependencies | Milestone |
|--------|-------|----------|----------|-------------|-----------|
| TICKET-001 | Project Scaffolding | P0 | M | ninguna | M1 |
| TICKET-002 | Configuration Layer | P0 | M | TICKET-001 | M1 |
| TICKET-003 | Thermal I/O Module | P0 | L | TICKET-001 | M1 |
| TICKET-004 | Auto-Label Core Filters | P1 | L | TICKET-001 | M1 |
| TICKET-005 | Auto-Label Orchestrator | P1 | M | TICKET-003, TICKET-004 | M1 |
| TICKET-006 | Dataset Processor + Split | P1 | L | TICKET-002, TICKET-003, TICKET-005 | M1 |
| TICKET-007 | Debug Visualization | P2 | S | TICKET-001 | M1 |
| TICKET-008 | Docker Container + ECR Push | P1 | M | TICKET-001 | M2 |
| TICKET-009 | SageMaker Training Scripts | P1 | M | TICKET-002, TICKET-008 | M2 |
| TICKET-010 | Test Training Run (5-epoch smoke test) | P1 | M | TICKET-006, TICKET-009 | M2 |
| TICKET-011 | Full Training Run (Operational) | P1 | L | TICKET-010 | M2 |
| TICKET-012 | TensorRT Export | P1 | M | TICKET-011 | M3 |
| TICKET-013 | Jetson Inference | P1 | L | TICKET-012 | M4 |
| TICKET-014 | Integration Smoke Test | P1 | M | TICKET-013 | M4 |
| TICKET-015 | Auto-Label Calibration + HITL Review | P2 | L | TICKET-006 | M3 |

---

## Critical Path

```
TICKET-001 (scaffold, 3h)
  → TICKET-003 (thermal_io, 6h)
    → TICKET-004 (auto-label core, 7h)         ← parallel with TICKET-003
      → TICKET-005 (auto-label orch., 4h)
        → TICKET-006 (dataset prep+split, 8h)
          → TICKET-010 (test training run, 5h)
            → TICKET-011 (full training, 4h dev + 8h compute)
              → TICKET-012 (TensorRT export, 3h)
                → TICKET-013 (Jetson inference, 5h)
                  → TICKET-014 (smoke test, 3h)
```

**Total dev time excl. training compute**: ~48 hours
**Total elapsed (4 milestones)**: ~4 weeks

---

## Milestone 1: Auto-Label Pipeline + Dataset Ready (Week 1)

**Goal**: Read thermal TIFFs, run auto-label cascade, produce a split YOLO dataset ready for S3 upload.

---

### TICKET-001: Project Scaffolding

**Prioridad**: P0
**Estimación**: M (3h)
**Dependencias**: ninguna
**Archivos**:
- `src/__init__.py` [new]
- `src/utils/__init__.py` [new]
- `tests/__init__.py` [new]
- `tests/conftest.py` [new]
- `configs/auto_label_fire.yaml` [new]
- `configs/auto_label_prescribed.yaml` [new]
- `configs/training.yaml` [new]
- `docker/Dockerfile` [new]
- `requirements.txt` [new]
- `.gitignore` [existing — verify completeness]

**Milestone**: M1

**Descripcion**: Crear la estructura de directorios del proyecto, todos los archivos `__init__.py`, `requirements.txt` con dependencias pineadas, archivos de configuracion YAML iniciales (contenido real de los configs), y `tests/conftest.py` con fixtures compartidos (synthetic numpy arrays). Verificar que `pytest` puede descubrir el directorio `tests/`.

**Criterios de Aceptacion**:
- [ ] `src/`, `src/utils/`, `tests/`, `configs/`, `docker/` existen con `__init__.py`
- [ ] `requirements.txt` contiene todas las dependencias del spec §17.1 con versiones pineadas
- [ ] `configs/auto_label_fire.yaml` contiene los 9 parametros con valores wildfire (threshold=150.0)
- [ ] `configs/auto_label_prescribed.yaml` contiene los 9 parametros con valores prescribed (threshold=100.0)
- [ ] `configs/training.yaml` contiene hiperparametros de entrenamiento + seccion `sagemaker:`
- [ ] `docker/Dockerfile` tiene estructura base `FROM ultralytics/ultralytics:latest` (se completa en TICKET-008)
- [ ] `tests/conftest.py` contiene fixtures: `celsius_fire_array`, `celsius_nofire_array`, `celsius_with_nan`, `sample_bboxes`
- [ ] `pytest tests/` se ejecuta sin error (0 tests collected es valido — confirma que pytest funciona)
- [ ] `.gitignore` cubre: `datasets/`, `secrets/`, `__pycache__/`, `*.pt`, `*.engine`, `runs/`, `data/`

**Definition of Done**:
- [ ] Directorios y archivos creados
- [ ] `pytest tests/` corre exitosamente
- [ ] No lint errors

---

### TICKET-002: Configuration Layer

**Prioridad**: P0
**Estimación**: M (3h)
**Dependencias**: TICKET-001
**Archivos**:
- `src/utils/config.py` [new]

**Milestone**: M1

**Descripcion**: Implementar el modulo de configuracion con tres funciones: `load_yaml_config()` para cargar y validar archivos YAML contra un schema, `validate_schema()` para chequeo de keys requeridas y tipos, y `get_aws_credentials()` que lee exclusivamente de variables de entorno (nunca del CSV expuesto en `secrets/`). Usa `pyyaml` (ya en requirements.txt).

**Criterios de Aceptacion**:
- [ ] `load_yaml_config("configs/auto_label_fire.yaml", schema)` retorna dict con las 9 keys del schema
- [ ] `load_yaml_config("nonexistent.yaml")` levanta `FileNotFoundError`
- [ ] `load_yaml_config` con archivo YAML con key faltante requerida retorna dict con errores (no levanta excepcion)
- [ ] `validate_schema(config, schema)` retorna lista de errores; lista vacia = valido
- [ ] `get_aws_credentials()` con `AWS_ACCESS_KEY_ID` y `AWS_SECRET_ACCESS_KEY` seteadas retorna `(key, secret, None)`
- [ ] `get_aws_credentials()` sin variables de entorno levanta `RuntimeError` con mensaje claro
- [ ] NO importa ni referencia `secrets/heimdall_accessKeys.csv` (anti-patron prohibido por spec §18.1)
- [ ] Funciones usan type hints completos (`-> dict`, `-> tuple[str, str, str | None]`, `-> list[str]`)

**Definition of Done**:
- [ ] Codigo implementado en `src/utils/config.py`
- [ ] Tests pasan: se prueban en `tests/test_prepare_data.py` (TICKET-006) con configs reales
- [ ] Typecheck pasa
- [ ] No lint errors

---

### TICKET-003: Thermal I/O Module

**Prioridad**: P0
**Estimación**: L (6h)
**Dependencias**: TICKET-001
**Archivos**:
- `src/thermal_io.py` [new]
- `tests/test_thermal_io.py` [new]

**Milestone**: M1

**Descripcion**: Implementar el lector de TIFF termicos: `read_celsius_tiff()` soporta float32 sin compresion y LZW comprimido via `tifffile` + `imagecodecs`, `read_irg_temperature()` extrae temperatura de FLIR IRG via `pyflir` con fallback a `exiftool`, y `find_paired_rgb()` localiza la imagen RGB pareada usando heuristicas de path por dataset (FLAME, Hanna Hammock, Frame Pairs). Incluir tests unitarios con TIFF sinteticos y un subset real de 5-9 imagenes en `tests/data/`.

**Criterios de Aceptacion**:
- [ ] `read_celsius_tiff(path)` con TIFF float32 valido retorna `np.ndarray (H,W) float32`
- [ ] `read_celsius_tiff(path)` con TIFF LZW comprimido (Hanna Hammock) retorna array correcto
- [ ] `read_celsius_tiff(path)` con archivo inexistente retorna `None` y loggea WARNING
- [ ] `read_celsius_tiff(path)` con TIFF corrupto (`TiffFileError`) retorna `None` y loggea WARNING
- [ ] `read_celsius_tiff(path)` con TIFF uint16 no calibrado retorna `None` y loggea WARNING
- [ ] `read_celsius_tiff(path)` con TIFF uint8 (probable false-color) retorna `None` y loggea WARNING
- [ ] `read_irg_temperature(path)` con IRG valido retorna `np.ndarray (H,W) float32`
- [ ] `read_irg_temperature(path)` sin `pyflir` ni `exiftool` disponibles retorna `None` y loggea WARNING
- [ ] `find_paired_rgb(thermal_path)` encuentra RGB en patron FLAME (`Thermal/Celsius TIFF/fire_001.TIFF` → `RGB/Corrected FOV/fire_001.jpg`)
- [ ] `find_paired_rgb(thermal_path)` encuentra RGB en patron Hanna Hammock (match por basename)
- [ ] `find_paired_rgb(thermal_path)` sin par RGB retorna `None`
- [ ] `tests/test_thermal_io.py` cubre ≥ 90% de lineas (spec §5.5)
- [ ] Test fixtures en `tests/conftest.py` incluyen `sample_celsius_tiff` (tmp file float32), `missing_path`, `uint16_tiff`

**Definition of Done**:
- [ ] Codigo implementado en `src/thermal_io.py`
- [ ] Tests pasan (`pytest tests/test_thermal_io.py -v`)
- [ ] Typecheck pasa
- [ ] No lint errors

---

### TICKET-004: Auto-Label Core Filters

**Prioridad**: P1
**Estimación**: L (7h)
**Dependencias**: TICKET-001
**Archivos**:
- `src/auto_label.py` [new] — funciones 1-5 del cascade
- `tests/test_auto_label.py` [new]

**Milestone**: M1

**Descripcion**: Implementar las 5 funciones puras del cascade de auto-label: `apply_absolute_threshold` (mascara binaria por temperatura > threshold con manejo de NaN), `apply_gradient_filter` (Sobel gradient magnitude + binary_closing 3x3 para refinar mascara), `apply_area_shape_filter` (connected components: filtrar por area minima y aspect ratio maximo), `cluster_fire_regions` (DBSCAN para agrupar pixeles de fuego + K-Means para subdividir clusters grandes), y `bboxes_to_yolo` (convertir bboxes de pixeles a formato YOLO normalizado con 6 decimales, clamp a [0,1], filtro min_fill_ratio). Todas las funciones trabajan sobre numpy arrays sinteticos — no dependen de `thermal_io.py`.

**Criterios de Aceptacion**:
- [ ] `apply_absolute_threshold(celsius, 150.0)` con array que tiene pixeles > 150°C retorna mascara con True en esos pixeles
- [ ] `apply_absolute_threshold(celsius, 150.0)` con array todo < 50°C retorna mascara toda False
- [ ] `apply_absolute_threshold(celsius, 150.0)` con NaN en celsius: NaN pixels son False (no fire)
- [ ] `apply_absolute_threshold(None, 150.0)` levanta `ValueError`
- [ ] `apply_gradient_filter(thermal, mask, 40.0)`: region uniforme (gradiente bajo) → excluida; borde sharp (gradiente alto) → incluida
- [ ] `apply_gradient_filter` aplica `binary_closing` 3x3 despues de filtrar por gradiente
- [ ] `apply_gradient_filter` con shapes que no coinciden levanta `ValueError`
- [ ] `apply_area_shape_filter(mask, min_area=50, max_aspect=8.0)`: componentes < 50px eliminados, lineas finas con aspect > 8:1 eliminadas
- [ ] `cluster_fire_regions(mask, eps=30, min_samples=5)`: 2 clusters desconectados → 2 bounding boxes
- [ ] `cluster_fire_regions(mask, max_bbox_ratio=0.4)`: cluster grande (> 40% del ancho) → subdividido con K-Means
- [ ] `cluster_fire_regions(mask)` con mascara vacia retorna `[]`
- [ ] `bboxes_to_yolo(bboxes, 640, 512)` convierte pixeles a coordenadas normalizadas [0,1] con 6 decimales
- [ ] `bboxes_to_yolo` con bbox que no cumple `min_fill_ratio` → omitido del output
- [ ] `bboxes_to_yolo` con lista vacia retorna `""` (string vacio, no None)
- [ ] `tests/test_auto_label.py` cubre ≥ 85% de lineas (spec §5.5)

**Definition of Done**:
- [ ] Codigo implementado: 5 funciones en `src/auto_label.py` (process_single_tiff va en TICKET-005)
- [ ] Tests pasan (`pytest tests/test_auto_label.py -v`)
- [ ] Typecheck pasa
- [ ] No lint errors

---

### TICKET-005: Auto-Label Orchestrator

**Prioridad**: P1
**Estimación**: M (4h)
**Dependencias**: TICKET-003, TICKET-004
**Archivos**:
- `src/auto_label.py` [modify] — agregar `process_single_tiff`

**Milestone**: M1

**Descripcion**: Implementar `process_single_tiff()` — el orquestador que ejecuta el cascade completo sobre un TIFF: leer con `read_celsius_tiff`, pasar por los 5 filtros, y generar string YOLO + debug overlay. Incluir tests de integracion con TIFFs reales del subset en `tests/data/`. Agregar `conftest.py` fixtures para el subset de test data (5 fire + 2 no-fire FLAME, 2 Hanna Hammock).

**Criterios de Aceptacion**:
- [ ] `process_single_tiff(tiff_path, config, jpg_path)` ejecuta el cascade 1→5 en orden
- [ ] Con TIFF de fuego FLAME (real, > 150°C): retorna `(yolo_string, debug_image)` con al menos 1 bbox
- [ ] Con TIFF no-fire FLAME (real, < 50°C): `yolo_string` es `""` (string vacio, no None), debug_image no es None si jpg_path provisto
- [ ] Con `tiff_path` inexistente: retorna `None` y loggea WARNING
- [ ] Con `config` sin key requerida: levanta `ValueError` con nombre de la key faltante
- [ ] Debug overlay image tiene dimensiones correctas, incluye bboxes dibujados e info footer
- [ ] Test de integracion en `test_auto_label.py`: `process_single_tiff` sobre 5 TIFFs reales de FLAME fire — todos generan al menos 1 bbox
- [ ] Test de integracion: `process_single_tiff` sobre 2 TIFFs reales de FLAME no-fire — ambos generan string vacio
- [ ] `conftest.py` fixture `test_data_dir` apunta a `tests/data/` con subset de 9 imagenes

**Definition of Done**:
- [ ] Codigo implementado en `src/auto_label.py`
- [ ] Tests de integracion pasan con datos reales de `tests/data/`
- [ ] Typecheck pasa
- [ ] No lint errors

---

### TICKET-006: Dataset Processor + Split

**Prioridad**: P1
**Estimación**: L (8h)
**Dependencias**: TICKET-002, TICKET-003, TICKET-005
**Archivos**:
- `src/prepare_data.py` [new]
- `src/split_dataset.py` [new]
- `tests/test_prepare_data.py` [new]
- `tests/test_split_dataset.py` [new]

**Milestone**: M1

**Descripcion**: Construir el pipeline de preparacion de datos completo. `prepare_data.py` con `process_dataset()`: lee fuentes del config (FLAME fire/no-fire, Hanna Hammock plots), ejecuta auto-label sobre cada TIFF, copia JPGs, genera labels YOLO, escribe `data.yaml`, y produce `processing_report.json`. `split_dataset.py` con `split_temporal_aware()`: agrupa por prefijo de filename, ordena alfanumericamente, split secuencial 70/15/15 SIN shuffle, crea symlinks (con fallback a `copy2` en Windows). `validate_split()`: verifica que no hay leakage temporal, orphans, o distribucion vacia.

**Criterios de Aceptacion**:
- [ ] `process_dataset(dataset_config)` crea estructura `data/images/all/`, `data/labels/all/`, `data/debug/`
- [ ] Procesa fuente FLAME fire (622 TIFFs) con config wildfire → genera labels YOLO, copia JPGs
- [ ] Procesa fuente FLAME no-fire (116 TIFFs) → escribe archivos de label vacios (0 bytes)
- [ ] Procesa fuente Hanna Hammock (794 TIFFs) con config prescribed → genera labels
- [ ] Excluye directorio NADIRPlots (duplicado de 34.92 GB — spec §18.1)
- [ ] `generate_data_yaml(data_path, nc=1, names=["fire"])` produce `data.yaml` valido con `path: .`
- [ ] `processing_report.json` contiene: `total_images`, `fire_images`, `nofire_images`, `total_bboxes`, `errors[]`, `skipped[]`
- [ ] `split_temporal_aware(data_dir, output_dir, (0.7, 0.15, 0.15))`:
  - Agrupa por prefijo (`flame_fire_`, `flame_nofire_`, `hanna_plot1_`, etc.)
  - Dentro de cada grupo: primeras 70% → train, siguientes 15% → val, ultimas 15% → test
  - NO random shuffle — split secuencial basado en orden alfanumerico
- [ ] Crea symlinks con fallback a `shutil.copy2` en `OSError` (Windows sin Developer Mode)
- [ ] `validate_split(output_dir)` retorna `{"valid": True, "leakage_detected": False}`
- [ ] `validate_split` detecta leakage si un grupo aparece en > 1 split
- [ ] `validate_split` detecta orphans (.jpg sin .txt o viceversa)
- [ ] Suma de ratios distinta de 1.0 → `ValueError`
- [ ] Menos de 3 imagenes total → `ValueError`
- [ ] `tests/test_split_dataset.py` cubre ≥ 85% de lineas (spec §5.5)

**Definition of Done**:
- [ ] Codigo implementado en `src/prepare_data.py` y `src/split_dataset.py`
- [ ] Tests pasan (`pytest tests/test_prepare_data.py tests/test_split_dataset.py -v`)
- [ ] Mini-run de integracion: procesar subset de 10 imagenes, verificar estructura de output
- [ ] Typecheck pasa
- [ ] No lint errors

---

### TICKET-007: Debug Visualization

**Prioridad**: P2
**Estimación**: S (2h)
**Dependencias**: TICKET-001
**Archivos**:
- `src/utils/debug_viz.py` [new]
- `tests/test_debug_viz.py` [new]

**Milestone**: M1

**Descripcion**: Implementar `create_debug_overlay()` para generar imagenes de debug para revision HITL. Superpone JPG false-color con mascara termica semi-transparente (COLORMAP_INFERNO), bounding boxes en verde con label de fill ratio, barra de leyenda de temperatura, y footer informativo (filename, threshold, count de bboxes, pixeles de fuego). Esta funcion es independiente — puede construirse en paralelo con TICKET-002 al -006.

**Criterios de Aceptacion**:
- [ ] `create_debug_overlay(jpg_path, celsius, mask, bboxes, output_path)` retorna `np.ndarray (H,W,3) uint8 BGR`
- [ ] Si `output_path` no es None, guarda la imagen en disco y retorna el array
- [ ] La imagen de output contiene: JPG de fondo, overlay de mascara roja semi-transparente, bboxes verdes, footer con metadata
- [ ] Los bboxes dibujados corresponden a las coordenadas provistas (verificar posicion visualmente o con asserts de color)
- [ ] Si no hay bboxes (lista vacia), la imagen se genera igual pero sin rectangulos — solo mascara + footer
- [ ] La barra de leyenda muestra gradiente de temperatura: Cold (0°C) a Hot (200°C)
- [ ] `tests/test_debug_viz.py` cubre ≥ 70% de lineas: verificar dimensiones de output, presencia de canales BGR, no excepciones

**Definition of Done**:
- [ ] Codigo implementado en `src/utils/debug_viz.py`
- [ ] Tests pasan (`pytest tests/test_debug_viz.py -v`)
- [ ] Typecheck pasa
- [ ] No lint errors

---

## Milestone 2: Docker + SageMaker Training (Week 2)

**Goal**: Dockerizar el pipeline, lanzar training en SageMaker, ejecutar el entrenamiento completo de 200 epochs.

---

### TICKET-008: Docker Container + ECR Push

**Prioridad**: P1
**Estimación**: M (3h)
**Dependencias**: TICKET-001
**Archivos**:
- `docker/Dockerfile` [modify] — completar con todas las dependencias

**Milestone**: M2

**Descripcion**: Completar el Dockerfile para el contenedor de SageMaker Training. Basado en `ultralytics/ultralytics:latest`, instalar `sagemaker-training`, `boto3`, `imagecodecs`, `scikit-learn`, `opencv-python-headless`, `pyflir`, `pyyaml`. Copiar `src/train_sagemaker.py` como entrypoint. Configurar `SAGEMAKER_PROGRAM=train.py`. Build multi-plataforma (`--platform linux/amd64`), taggear y pushear a ECR. Verificar que el contenedor arranca localmente (si hay GPU disponible).

**Criterios de Aceptacion**:
- [ ] `docker/Dockerfile` usa `FROM ultralytics/ultralytics:latest` (version pineada: `8.2.0-cuda12.1` recomendada)
- [ ] Instala: `sagemaker-training`, `boto3`, `imagecodecs`, `scikit-learn`, `opencv-python-headless`, `pyflir`, `pyyaml`
- [ ] Copia `src/train_sagemaker.py` → `/opt/ml/code/train.py`
- [ ] `ENV SAGEMAKER_PROGRAM=train.py`
- [ ] `WORKDIR /opt/ml/code`
- [ ] `ENTRYPOINT` configurado correctamente
- [ ] `docker build --platform linux/amd64 -t xheimdall-training:latest -f docker/Dockerfile .` completa sin errores
- [ ] ECR repository `xheimdall-training` existe o se crea
- [ ] `docker push` a ECR exitoso
- [ ] Verificacion: `docker run --gpus all xheimdall-training:latest nvidia-smi` muestra GPUs (si GPU disponible)

**Definition of Done**:
- [ ] Dockerfile completo y funcional
- [ ] Build + push a ECR documentado
- [ ] Contenedor validado (nvidia-smi o smoke test local)
- [ ] No hardcoded credentials en Dockerfile

---

### TICKET-009: SageMaker Training Scripts

**Prioridad**: P1
**Estimación**: M (4h)
**Dependencias**: TICKET-002, TICKET-008
**Archivos**:
- `src/train_sagemaker.py` [new]
- `src/launch_training.py` [new]

**Milestone**: M2

**Descripcion**: Implementar el entrypoint de entrenamiento (`train_sagemaker.py`): script que lee 18 variables de entorno (`SM_MODEL_DIR`, `SM_CHANNEL_TRAINING`, `YOLO_EPOCHS`, etc.), carga `yolo26m.pt`, entrena con augmentations especificas para termal (`hsv_h=0, hsv_s=0, flipud=0`), guarda `best.pt` + `metrics.json` en `SM_MODEL_DIR`, y sincroniza checkpoints a S3. Implementar `launch_training.py` con `launch_training_job()`: crea SageMaker Estimator con spot instances, checkpoint S3 URI, y `TrainingInput` desde S3.

**Criterios de Aceptacion**:
- [ ] `train_sagemaker.py` lee 18 env vars con defaults correctos (spec §7.2)
- [ ] Usa `YOLO("yolo26m.pt")` con `model.train(data=data_yaml_path, epochs=200, ...)`
- [ ] Augmentations termal-especificas: `hsv_h=0.0, hsv_s=0.0, hsv_v=0.3, flipud=0.0`
- [ ] `fliplr=0.5, mosaic=1.0, mixup=0.1, scale=0.5, erasing=0.4`
- [ ] Copia `best.pt` a `SM_MODEL_DIR/best.pt`
- [ ] Escribe `metrics.json` con `mAP50`, `mAP50_95`, `precision`, `recall`, `epochs_completed`
- [ ] Si `OUTPUT_CHECKPOINT_S3` esta definido, ejecuta `aws s3 sync` de checkpoints
- [ ] Maneja signal `SIGTERM` para spot interruption: sync final a S3 antes de salir
- [ ] `launch_training.py`: `launch_training_job()` lee `configs/training.yaml`, crea `Estimator` con `use_spot_instances=True`
- [ ] `TrainingInput` configurado con `input_mode="File"` desde `s3://xheimdall-datasets/yolo_dataset/`
- [ ] `checkpoint_s3_uri` configurado para spot recovery
- [ ] Hiperparametros de `training.yaml` pasados como `environment` dict al Estimator

**Definition of Done**:
- [ ] Codigo implementado en `src/train_sagemaker.py` y `src/launch_training.py`
- [ ] Ambos scripts son importables sin errores (no requieren SageMaker runtime para import)
- [ ] Typecheck pasa
- [ ] No lint errors
- [ ] Validacion con `SM_CHANNEL_TRAINING` y `SM_MODEL_DIR` seteados como vars locales de prueba

---

### TICKET-010: Test Training Run (5-Epoch Smoke Test)

**Prioridad**: P1
**Estimación**: M (5h — incluye tiempo de espera SageMaker)
**Dependencias**: TICKET-006, TICKET-009
**Archivos**:
- `configs/training.yaml` [modify] — agregar config 5-epoch test

**Milestone**: M2

**Descripcion**: Preparar un subset del dataset (50-100 imagenes representativas) en S3, lanzar un training job de 5 epochs en `ml.g5.xlarge` (1 GPU) para validar el pipeline end-to-end: S3 data → Docker container → YOLO train → best.pt en S3. Este paso detecta problemas de configuracion (IAM, ECR, S3 paths, CUDA) ANTES del costoso entrenamiento de 200 epochs en g5.12xlarge.

**Criterios de Aceptacion**:
- [ ] Subset de 50-100 imagenes con labels YOLO subido a `s3://xheimdall-datasets/test_subset/`
- [ ] `data.yaml` para el subset en S3 apunta correctamente a `train/` y `val/`
- [ ] Training job lanzado via `launch_training.py` con `instance_type="ml.g5.xlarge"`, `epochs=5`
- [ ] Training job completa con estado `Completed` (no `Failed`)
- [ ] `best.pt` aparece en `s3://xheimdall-models/weights/best.pt`
- [ ] `metrics.json` contiene campos poblados (aunque metricas seran bajas con solo 5 epochs)
- [ ] CloudWatch logs muestran que YOLO26m se cargo, entreno 5 epochs, y guardo el modelo
- [ ] Sin errores CUDA OOM (batch size adecuado para 1 GPU: batch=16)
- [ ] Sin errores de IAM/S3/ECR permissions

**Definition of Done**:
- [ ] SageMaker training job `Completed`
- [ ] `best.pt` y `metrics.json` en S3
- [ ] Logs de CloudWatch verificados sin errores fatales
- [ ] Costo total del test job < $5

---

### TICKET-011: Full Training Run (Operational)

**Prioridad**: P1
**Estimación**: L (4h dev + 8h compute SageMaker)
**Dependencias**: TICKET-010
**Archivos**:
- ningun archivo nuevo — es ejecucion operacional

**Milestone**: M2

**Descripcion**: Subir el dataset completo (~1,500 imagenes) a S3 via `aws s3 sync`, lanzar el entrenamiento completo de 200 epochs en `ml.g5.12xlarge` spot (4x A10G), monitorear via CloudWatch, verificar que el checkpointing funciona para spot interruptions. Al finalizar, `best.pt` debe estar en S3 con mAP50 ≥ 0.85.

**Criterios de Aceptacion**:
- [ ] Dataset completo sincronizado a `s3://xheimdall-datasets/yolo_dataset/` (estructura correcta: `images/train/`, `labels/train/`, `data.yaml`)
- [ ] Training job lanzado en `ml.g5.12xlarge` spot con `epochs=200, batch=32, device=0,1,2,3`
- [ ] Training job completa (Completed o spot-interrupted + resumed exitosamente)
- [ ] `best.pt` logra **mAP50 ≥ 0.85** en validation set (spec AC-07)
- [ ] `mAP50_95 ≥ 0.55` en validation set
- [ ] `best.pt` file size es aproximadamente 50-60 MB (YOLO26m FP32)
- [ ] Checkpoints existen en `s3://xheimdall-models/checkpoints/{job_name}/`
- [ ] `metrics.json` incluye todas las metricas: `mAP50`, `mAP50_95`, `precision`, `recall`, `epochs_completed`, `best_epoch`
- [ ] Curva de entrenamiento (via TensorBoard o plots de Ultralytics en `runs/`) no muestra overfitting severo
- [ ] Sin errores CUDA OOM en ninguna etapa

**Definition of Done**:
- [ ] `best.pt` con mAP50 ≥ 0.85 en `s3://xheimdall-models/weights/`
- [ ] `metrics.json` validado
- [ ] CloudWatch logs guardados para referencia
- [ ] Costo total del job dentro del presupuesto (~$100 spot)

---

## Milestone 3: TensorRT Export + Calibration (Week 3)

**Goal**: Exportar modelo a TensorRT FP16, calibrar parametros de auto-label con HITL.

---

### TICKET-012: TensorRT Export

**Prioridad**: P1
**Estimación**: M (3h)
**Dependencias**: TICKET-011
**Archivos**:
- `src/export_tensorrt.py` [new]

**Milestone**: M3

**Descripcion**: Implementar `export_to_tensorrt()`: descarga `best.pt` de S3 (o lee de path local), exporta a TensorRT FP16 via `model.export(format="engine", half=True, imgsz=640, workspace=4, dynamic=False, simplify=True, opset=17, batch=1)`, valida que el engine carga y predice correctamente, y sube `best.engine` a S3. Incluir verificacion de versiones (loggear `tensorrt.__version__` en export y carga) para mitigar el riesgo R13 de version mismatch.

**Criterios de Aceptacion**:
- [ ] `export_to_tensorrt(model_path, output_path)` produce archivo `best.engine` (o `best_fp16.engine`)
- [ ] Engine file size ~25-50 MB (FP16, single batch, fixed 640x640)
- [ ] `YOLO("best.engine")` carga sin errores
- [ ] `model.predict(dummy_frame)` sobre frame sintetico (640x640 BGR) retorna resultados validos
- [ ] Inferencia sobre frame sintetico < 5ms (GPU, excluyendo I/O)
- [ ] Log incluye: `tensorrt.__version__`, `torch.__version__`, tiempo de export, tamaño de engine
- [ ] Si export falla (sin GPU, sin TensorRT), error es claro: "TensorRT export requires CUDA-capable GPU"
- [ ] Subida a `s3://xheimdall-models/engines/best_fp16.engine` exitosa

**Definition of Done**:
- [ ] Codigo implementado en `src/export_tensorrt.py`
- [ ] Engine validado: carga + predict sobre frame sintetico
- [ ] Engine en S3 (`s3://xheimdall-models/engines/best_fp16.engine`)
- [ ] Typecheck pasa
- [ ] No lint errors

---

### TICKET-015: Auto-Label Calibration + HITL Review

**Prioridad**: P2
**Estimación**: L (5h)
**Dependencias**: TICKET-006
**Archivos**:
- `configs/auto_label_fire.yaml` [modify] — ajustar thresholds basado en HITL
- `configs/auto_label_prescribed.yaml` [modify] — ajustar thresholds

**Milestone**: M3

**Descripcion**: Cross-cutting: ejecutar el pipeline de auto-label sobre el subset completo, generar debug images para HITL review, evaluar calidad via metricas (precision ≥ 0.95, recall ≥ 0.90, mean IoU ≥ 0.75 segun spec AC-10), recalibrar thresholds si es necesario. Este proceso itera: ejecutar pipeline → revisar debug images → ajustar thresholds en YAML → re-ejecutar hasta calidad satisfactoria.

**Criterios de Aceptacion**:
- [ ] Debug images generadas para ≥ 10% de FLAME fire images (~62 imagenes)
- [ ] Debug images generadas para ≥ 10% de Hanna Hammock images (~80 imagenes)
- [ ] HITL review identifica: bounding boxes que no cubren completamente el fuego, falsos positivos (warm ground etiquetado como fire), clusters que deberian ser subdivididos
- [ ] Ajustes de thresholds documentados en los archivos YAML con comentarios explicando la razon del cambio
- [ ] **Precision** de auto-label: ≥ 95% de bboxes generadas son correctas (menos de 5% falsos positivos)
- [ ] **Recall** de auto-label: ≥ 90% de regiones de fuego visibles tienen al menos 1 bbox
- [ ] **Mean IoU** entre bbox auto-label y referencia manual ≥ 0.75
- [ ] Imagenes que no pasan los thresholds de calidad son flaggeadas para correccion manual (lista en `processing_report.json`)
- [ ] No se introducen falsos positivos en imagenes no-fire (0% FPR mantenido)

**Definition of Done**:
- [ ] HITL review completada
- [ ] Thresholds calibrados y documentados en YAML
- [ ] Metricas de calidad cumplen spec AC-10
- [ ] Imagenes problematicas identificadas en reporte

---

## Milestone 4: Jetson Deploy + Validation (Week 4)

**Goal**: Desplegar modelo en Jetson AGX, verificar FPS ≥ 25, smoke test end-to-end.

---

### TICKET-013: Jetson Inference

**Prioridad**: P1
**Estimación**: L (5h)
**Dependencias**: TICKET-012
**Archivos**:
- `src/infer_jetson.py` [new]

**Milestone**: M4

**Descripcion**: Implementar el modulo de inferencia para Jetson AGX: `load_model()` carga el TensorRT engine y ejecuta warm-up inference, `predict_frame()` ejecuta deteccion en un solo frame retornando bboxes con confianza, y `run_camera_loop()` mantiene el loop principal de captura de camara (GStreamer pipeline para FLIR Boson, con fallback a video file para testing). Incluye calculo de FPS, overlay de detecciones, y opcion de grabacion. Soporta 3 templates de pipeline: FLIR Boson USB, v4l2 generico, RTSP IP camera.

**Criterios de Aceptacion**:
- [ ] `load_model("best.engine")` carga el engine y ejecuta warm-up sin errores
- [ ] `load_model` loggea `tensorrt.__version__` y `torch.__version__` para debugging de compatibilidad
- [ ] `predict_frame(model, frame, conf=0.25)` retorna `list[dict]` con `x_min, y_min, x_max, y_max, confidence`
- [ ] Frame sin detecciones retorna `[]` (lista vacia, no None)
- [ ] `run_camera_loop(source, model, config)` con `source="test_video.mp4"` procesa frames y muestra ventana con detecciones
- [ ] `run_camera_loop` con GStreamer pipeline abre la camara FLIR Boson correctamente
- [ ] Pipeline GStreamer default: `v4l2src device=/dev/video0 ! video/x-raw,format=UYVY,width=640,height=512,framerate=30/1 ! videoconvert ! video/x-raw,format=BGR ! appsink drop=1 max-buffers=2`
- [ ] El loop muestra FPS promedio movil (ultimos 100 frames)
- [ ] Overlay de detecciones: bboxes verdes con `FIRE {conf:.2f}`, contador FPS en esquina
- [ ] Presionar 'q' cierra el loop limpiamente (`cap.release()`, `cv2.destroyAllWindows()`)
- [ ] Si `source` no puede abrirse (camara desconectada, path incorrecto), levanta `RuntimeError` con mensaje descriptivo
- [ ] Soporta `--list-cameras` para enumerar dispositivos `/dev/video*` (helper function)

**Definition of Done**:
- [ ] Codigo implementado en `src/infer_jetson.py`
- [ ] Testeado con video file (cualquier .mp4) — detecciones se muestran, FPS reportado, sin crashes
- [ ] Testeado con camara FLIR Boson en Jetson (si hardware disponible) — FPS ≥ 25
- [ ] Typecheck pasa
- [ ] No lint errors

---

### TICKET-014: Integration Smoke Test

**Prioridad**: P1
**Estimación**: M (3h)
**Dependencias**: TICKET-013
**Archivos**:
- `tests/smoke_test.py` [new]
- `tests/data/` [new] — tiny pre-labeled dataset (10 images)

**Milestone**: M4

**Descripcion**: Implementar `tests/smoke_test.py` que valida el pipeline end-to-end: carga un dataset pre-etiquetado de 10 imagenes (5 fire + 5 no-fire), entrena YOLO26n por 1 epoch (smoke test — verifica que el pipeline no crashea), exporta a TensorRT, ejecuta inferencia en 2 frames. Este test se corre rapidamente (< 2 min con GPU) para detectar problemas de configuracion y dependencias. Requiere un subset de test data en `tests/data/` con imagenes JPG y labels YOLO pre-verificados.

**Criterios de Aceptacion**:
- [ ] `tests/data/` contiene 10 imagenes JPG + 10 labels YOLO (5 fire con al menos 1 bbox cada uno, 5 no-fire con archivos vacios)
- [ ] `tests/data/data.yaml` configurado con `nc: 1, names: {0: fire}`
- [ ] `smoke_test.py` ejecuta:
  1. `YOLO("yolo26n.pt").train(data="tests/data/data.yaml", epochs=1, imgsz=320, batch=4, device="cpu")` — verifica que no crashea
  2. Carga `best.pt` y ejecuta `model.predict(test_frame)` en 2 frames — verifica que retorna predicciones
  3. Exporta a TensorRT (`model.export(format="engine", ...)`) si GPU disponible — skippea si no hay GPU
  4. Carga engine y ejecuta predict — verifica que no crashea
- [ ] Test pasa en < 2 minutos con GPU, < 5 minutos en CPU
- [ ] Assertions: sin excepciones, `best.pt` existe, predicciones tienen el formato correcto, engine carga
- [ ] Skipea pasos de GPU si `torch.cuda.is_available()` es False (no falla en CI sin GPU)

**Definition of Done**:
- [ ] `tests/smoke_test.py` implementado
- [ ] `tests/data/` poblado con 10 imagenes pre-etiquetadas
- [ ] `pytest tests/smoke_test.py -v` pasa (localmente, con o sin GPU)
- [ ] Test usa modelo nano (`yolo26n.pt`) para minimizar tiempo
- [ ] Todos los pasos del pipeline son ejercitados

---

## Risk Mitigation Tracking

| Risk ID | Risk | Mitigated By | Status |
|---------|------|-------------|--------|
| R11 | Symlink fails on Windows | TICKET-006: `copy2` fallback | ✅ Handled |
| R12 | DBSCAN O(N²) memory | TICKET-004: pixel count check + downsampling | ✅ Handled |
| R13 | TensorRT version mismatch | TICKET-012: version logging + opset=17 pin; TICKET-013: version check en load | ✅ Handled |
| R14 | yolo26m.pt download fails in SageMaker | TICKET-009: pre-download to S3 or bake into Docker image | ⚠️ Monitored |
| R15 | GStreamer pipeline wrong | TICKET-013: 3 template pipelines + `--list-cameras` helper | ✅ Handled |
| R16 | prepare_data.py appears hung | TICKET-006: progress logging every 50 images + tqdm opcional | ✅ Handled |

---

## Environment Variables Quick Reference

Verificar que estas variables esten seteadas ANTES de ejecutar cualquier ticket que toque AWS:

| Variable | Ticket que la usa |
|----------|------------------|
| `AWS_ACCESS_KEY_ID` | TICKET-002, TICKET-008, TICKET-009, TICKET-010, TICKET-011, TICKET-012 |
| `AWS_SECRET_ACCESS_KEY` | TICKET-002, TICKET-008, TICKET-009, TICKET-010, TICKET-011, TICKET-012 |
| `AWS_DEFAULT_REGION` | TICKET-009, TICKET-010, TICKET-011 |

---

*Task backlog generated by SDD Tasks subagent | `tpm-agile-backlog-generator-notion-integration` | deepseek-v4-pro | 2026-05-22*

*Ready for: `sdd-apply` phase — Code implementation ticket by ticket.*
