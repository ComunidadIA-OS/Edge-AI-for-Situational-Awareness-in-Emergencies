# XHeimdall — Warm-Restart Image Build & ECR Push (Podman)
#
# Builds the patched training image (with SM_CHANNEL_PRETRAINED + augmentation
# env vars) and pushes to ECR under a SEPARATE tag (:warm-restart-v1) so the
# existing :latest tag used by Job 1 is untouched.
#
# RUN THIS ONLY AFTER JOB 1 HAS FINISHED (Completed/Stopped/Failed).
#
# Usage:
#   .\docker\build_and_push_warm_restart.ps1 -Account 810299942818 -Region us-east-1
#
# Optional: -Tag warm-restart-v1   (override tag)
#           -SkipBuild             (only login + push; assumes image already built)

param(
    [Parameter(Mandatory=$true)]
    [string]$Account,
    [string]$Region = "us-east-1",
    [string]$Tag = "warm-restart-v1",
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$IMAGE_NAME = "xheimdall-training"
$ECR_URI = "${Account}.dkr.ecr.${Region}.amazonaws.com/${IMAGE_NAME}:${Tag}"

# Run from packages/edge/ (one level up from this script)
$EDGE_ROOT = Split-Path -Parent $PSScriptRoot
Set-Location $EDGE_ROOT
Write-Host "CWD: $EDGE_ROOT"

if (-not $SkipBuild) {
    Write-Host "=== Step 1: Build image with Podman (linux/amd64) ==="
    podman build --platform linux/amd64 `
        -t "${IMAGE_NAME}:${Tag}" `
        -f docker/Dockerfile `
        .
    if ($LASTEXITCODE -ne 0) { throw "podman build failed" }
}

Write-Host "=== Step 2: Login to ECR ==="
$ecrPassword = aws ecr get-login-password --region $Region
if ($LASTEXITCODE -ne 0) { throw "aws ecr get-login-password failed" }
$ecrPassword | podman login --username AWS --password-stdin "${Account}.dkr.ecr.${Region}.amazonaws.com"
if ($LASTEXITCODE -ne 0) { throw "podman login failed" }

Write-Host "=== Step 3: Tag for ECR ==="
podman tag "${IMAGE_NAME}:${Tag}" $ECR_URI
if ($LASTEXITCODE -ne 0) { throw "podman tag failed" }

Write-Host "=== Step 4: Push to ECR ==="
podman push $ECR_URI
if ($LASTEXITCODE -ne 0) { throw "podman push failed" }

Write-Host ""
Write-Host "=== DONE ==="
Write-Host "Image URI: $ECR_URI"
Write-Host ""
Write-Host "Next step: set SAGEMAKER_IMAGE_URI to this URI and run launch_warm_restart.py"
Write-Host "  `$env:SAGEMAKER_IMAGE_URI = '$ECR_URI'"
Write-Host "  python scripts/launch_warm_restart.py --base-job xheimdall-yolo26m-20260525-101951"
