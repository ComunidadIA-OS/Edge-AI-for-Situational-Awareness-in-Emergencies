# XHeimdall — Docker Build & ECR Push (PowerShell)
# Usage: .\docker\build_and_push.ps1 -Account 123456789012 -Region us-east-1
param(
    [Parameter(Mandatory=$true)]
    [string]$Account,
    [string]$Region = "us-east-1"
)

$ErrorActionPreference = "Stop"
$IMAGE_NAME = "xheimdall-training"
$IMAGE_TAG = "latest"
$ECR_URI = "${Account}.dkr.ecr.${Region}.amazonaws.com/${IMAGE_NAME}:${IMAGE_TAG}"

Write-Host "=== Step 1: Create ECR repository (if not exists) ==="
$exists = aws ecr describe-repositories --repository-names $IMAGE_NAME --region $Region 2>&1
if ($LASTEXITCODE -ne 0) {
    aws ecr create-repository --repository-name $IMAGE_NAME --region $Region
}

Write-Host "=== Step 2: Login to ECR ==="
aws ecr get-login-password --region $Region | `
    docker login --username AWS --password-stdin "${Account}.dkr.ecr.${Region}.amazonaws.com"

Write-Host "=== Step 3: Build Docker image (linux/amd64) ==="
docker build --platform linux/amd64 `
    -t "${IMAGE_NAME}:${IMAGE_TAG}" `
    -f docker/Dockerfile `
    .

Write-Host "=== Step 4: Tag image ==="
docker tag "${IMAGE_NAME}:${IMAGE_TAG}" $ECR_URI

Write-Host "=== Step 5: Push to ECR ==="
docker push $ECR_URI

Write-Host ""
Write-Host "=== DONE ==="
Write-Host "Image URI: $ECR_URI"
Write-Host ""
Write-Host "Smoke test: docker run --rm $ECR_URI"
