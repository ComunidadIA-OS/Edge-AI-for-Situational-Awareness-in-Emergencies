#!/usr/bin/env bash
# Entrypoint for the vision-inference container.
#
# Idempotent: on first launch it (a) fetches best.pt from the GitHub release,
# (b) exports it to a TensorRT FP16 engine, then hands off to the supervisor.
# On subsequent launches it skips both steps and starts immediately.
#
# Designed so that a fresh-clone user on a stock Jetson AGX Orin only needs:
#   docker compose -f docker/docker-compose.yml --env-file docker/.env up --build
#
set -e

ENGINE_PATH="${MODEL_ENGINE_PATH:-/models/best.engine}"
WEIGHTS_PATH="${MODEL_WEIGHTS_PATH:-/models/best.pt}"

log() { printf "[entrypoint] %s\n" "$*"; }

if [ -f "$ENGINE_PATH" ]; then
    log "TensorRT engine present: $ENGINE_PATH"
else
    log "TensorRT engine not found at $ENGINE_PATH"

    if [ ! -f "$WEIGHTS_PATH" ]; then
        log "Weights not found at $WEIGHTS_PATH — fetching from GitHub release..."
        if ! python3 /app/scripts/fetch_model.py --output "$WEIGHTS_PATH"; then
            log "FATAL: could not download best.pt."
            log "  Workaround: place best.pt at $WEIGHTS_PATH on the host"
            log "  (the host directory is bind-mounted to /models in the container)"
            log "  and restart with: docker compose restart vision-inference"
            exit 1
        fi
    else
        log "Weights present: $WEIGHTS_PATH"
    fi

    log "Exporting $WEIGHTS_PATH -> $ENGINE_PATH (TensorRT FP16) ..."
    log "  This is a one-time step and may take 1-3 minutes on Jetson AGX Orin."
    # Note: export_tensorrt.py defaults to FP16; --fp32 would opt out.
    if ! python3 -m vision.inference.export_tensorrt \
        --model "$WEIGHTS_PATH" \
        --output "$ENGINE_PATH"; then
        log "FATAL: TensorRT export failed."
        log "  Likely causes:"
        log "    1. nvidia-container-toolkit not installed on the host"
        log "    2. docker-compose service is missing 'runtime: nvidia'"
        log "    3. base image does not match this Jetson's JetPack version"
        exit 1
    fi
    log "Engine exported successfully."
fi

log "Starting supervisor..."
exec python3 -m edge.supervisor
