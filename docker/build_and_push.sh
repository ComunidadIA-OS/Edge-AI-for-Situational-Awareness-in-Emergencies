#!/usr/bin/env bash
# XHeimdall — Docker Build & ECR Push
# Usage: ACCOUNT=123456789012 REGION=us-east-1 bash docker/build_and_push.sh
set -euo pipefail

ACCOUNT="${ACCOUNT:-}"
REGION="${REGION:-us-east-1}"
IMAGE_NAME="xheimdall-training"
IMAGE_TAG="latest"
ECR_URI="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com/${IMAGE_NAME}:${IMAGE_TAG}"

if [ -z "$ACCOUNT" ]; then
    echo "ERROR: ACCOUNT is required. Usage: ACCOUNT=123456789012 REGION=us-east-1 bash docker/build_and_push.sh"
    exit 1
fi

echo "=== Step 1: Create ECR repository (if not exists) ==="
aws ecr describe-repositories --repository-names "${IMAGE_NAME}" > /dev/null 2>&1 || \
    aws ecr create-repository --repository-name "${IMAGE_NAME}" --region "${REGION}"

echo "=== Step 2: Login to ECR ==="
aws ecr get-login-password --region "${REGION}" | \
    docker login --username AWS --password-stdin "${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"

echo "=== Step 3: Build Docker image (linux/amd64) ==="
docker build --platform linux/amd64 \
    -t "${IMAGE_NAME}:${IMAGE_TAG}" \
    -f docker/Dockerfile \
    .

echo "=== Step 4: Tag image ==="
docker tag "${IMAGE_NAME}:${IMAGE_TAG}" "${ECR_URI}"

echo "=== Step 5: Push to ECR ==="
docker push "${ECR_URI}"

echo ""
echo "=== DONE ==="
echo "Image URI: ${ECR_URI}"
echo ""
echo "Smoke test: docker run --rm ${ECR_URI}"
