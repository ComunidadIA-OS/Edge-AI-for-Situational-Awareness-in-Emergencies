# XHeimdall ECR Push — Overnight background job
# Logs to $env:TEMP\ecr-push-overnight.log
#
# PREREQUISITES:
#   $env:AWS_ACCOUNT_ID    — your AWS account ID (e.g., 123456789012)
#   $env:AWS_DEFAULT_REGION — AWS region (default: us-east-1)
#   AWS credentials must be configured via aws configure or env vars.
#
# Usage: .\scripts\ecr_push_overnight.ps1

$logFile = "$env:TEMP\ecr-push-overnight.log"
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

$ACCOUNT_ID = $env:AWS_ACCOUNT_ID
$REGION = if ($env:AWS_DEFAULT_REGION) { $env:AWS_DEFAULT_REGION } else { "us-east-1" }

if (-not $ACCOUNT_ID) {
    Add-Content -LiteralPath $logFile -Value "[$timestamp] ERROR: AWS_ACCOUNT_ID env var not set"
    Write-Host "ERROR: Set AWS_ACCOUNT_ID environment variable"
    exit 1
}

$ECR_URI = "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

Add-Content -LiteralPath $logFile -Value "[$timestamp] Starting ECR push..."

# ECR login
Add-Content -LiteralPath $logFile -Value "[$timestamp] Authenticating to ECR..."
aws ecr get-login-password --region $REGION | podman login --username AWS --password-stdin $ECR_URI *>> $logFile

if ($LASTEXITCODE -ne 0) {
    Add-Content -LiteralPath $logFile -Value "[$timestamp] ECR AUTH FAILED"
    exit 1
}

# Push
$pushStart = Get-Date
Add-Content -LiteralPath $logFile -Value "[$timestamp] Starting podman push (9GB)..."
podman push ${ECR_URI}/xheimdall-training:latest *>> $logFile
$pushEnd = Get-Date
$elapsed = ($pushEnd - $pushStart).TotalMinutes

if ($LASTEXITCODE -eq 0) {
    Add-Content -LiteralPath $logFile -Value "[$($pushEnd.ToString('yyyy-MM-dd HH:mm:ss'))] PUSH COMPLETE in $($elapsed.ToString('0.0')) min"
} else {
    Add-Content -LiteralPath $logFile -Value "[$($pushEnd.ToString('yyyy-MM-dd HH:mm:ss'))] PUSH FAILED after $($elapsed.ToString('0.0')) min"
}
