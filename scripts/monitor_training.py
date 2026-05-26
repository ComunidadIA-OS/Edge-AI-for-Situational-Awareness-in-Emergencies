"""Monitor SageMaker training job — polls every 30 min, shows status + metrics.

Usage:
    python scripts/monitor_training.py [JOB_NAME]
    python scripts/monitor_training.py [JOB_NAME] --once
    python scripts/monitor_training.py [JOB_NAME] --interval 60

Env vars:
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION=us-east-1
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any

import boto3

# Force UTF-8 on Windows to avoid emoji encoding crashes
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_JOB = "xheimdall-yolo26m-20260525-094252"
REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
INTERVAL = 1800  # 30 minutes


def describe_job(sm: Any, job_name: str) -> dict:
    """Fetch full training job description with detailed status."""
    resp = sm.describe_training_job(TrainingJobName=job_name)
    return resp


def print_status(resp: dict) -> None:
    """Pretty-print training job status."""
    status = resp["TrainingJobStatus"]
    secondary = resp.get("SecondaryStatus", "N/A")
    detail = resp.get("FailureReason", "")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    print(f"\n{'='*60}")
    print(f"[{ts}] Training Job: {resp['TrainingJobName']}")
    print(f"{'='*60}")

    # Status emoji + detail
    emoji = {"InProgress": "⏳", "Completed": "✅", "Failed": "❌",
             "Stopped": "⏹️", "Stopping": "🛑"}.get(status, "❓")
    print(f"  Status:        {emoji} {status}")
    print(f"  Secondary:     {secondary}")

    # Timing
    creation = resp.get("CreationTime")
    start = resp.get("TrainingStartTime")
    end = resp.get("TrainingEndTime")
    if creation:
        print(f"  Created:       {creation.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    if start:
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        hours = int(elapsed // 3600)
        mins = int((elapsed % 3600) // 60)
        print(f"  Started:       {start.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print(f"  Elapsed:       {hours}h {mins}m")
    if end:
        print(f"  Ended:         {end.strftime('%Y-%m-%d %H:%M:%S')} UTC")

    # Resource
    rc = resp.get("ResourceConfig", {})
    print(f"  Instance:      {rc.get('InstanceType', 'N/A')} x {rc.get('InstanceCount', 0)}")
    print(f"  Volume:        {rc.get('VolumeSizeInGB', 'N/A')} GB")
    print(f"  Spot:          {resp.get('EnableManagedSpotTraining', False)}")

    # Billing
    billable = resp.get("BillableTimeInSeconds", 0)
    if billable:
        hours_billable = billable / 3600.0
        print(f"  Billable:      {hours_billable:.1f}h")

    # Metrics (if available from CloudWatch — check final metrics)
    metric_defs = resp.get("FinalMetricDataList", [])
    if metric_defs:
        print(f"  --- Final Metrics ---")
        for m in metric_defs:
            print(f"  {m['MetricName']}: {m['Value']:.4f}")

    # Debug info
    debug = resp.get("DebugHookConfig")
    if debug:
        print(f"  DebugHook:     {debug.get('S3OutputPath', 'N/A')}")

    # Output
    output = resp.get("OutputDataConfig", {})
    print(f"  Output S3:     {output.get('S3OutputPath', 'N/A')}")

    # CloudWatch logs
    print(f"  Console:       https://{REGION}.console.aws.amazon.com/sagemaker/home?region={REGION}#/jobs/{resp['TrainingJobName']}")

    if detail:
        print(f"\n  ⚠️  Failure reason: {detail}")

    print()


def is_finished(status: str) -> bool:
    """Terminal states: Completed, Failed, Stopped."""
    return status in ("Completed", "Failed", "Stopped")


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor SageMaker training job")
    parser.add_argument("job_name", nargs="?", default=DEFAULT_JOB, help="SageMaker training job name")
    parser.add_argument("--once", action="store_true", help="Single check, then exit")
    parser.add_argument("--interval", type=int, default=INTERVAL, help="Polling interval in seconds (default: 1800)")
    args = parser.parse_args()

    job_name = args.job_name
    interval = args.interval
    session = boto3.Session(region_name=REGION)
    sm = session.client("sagemaker")

    try:
        resp = describe_job(sm, job_name)
    except Exception as e:
        print(f"ERROR Cannot connect to SageMaker: {e}")
        print("   Check: AWS credentials, region, VPN, and job name.")
        return 1

    print_status(resp)

    if is_finished(resp["TrainingJobStatus"]):
        print("Job already finished.")
        return 0

    if args.once:
        return 0

    print(f"Monitoring every {interval // 60} minutes. Press Ctrl+C to stop.")
    print(f"   Job: {job_name}")
    print(f"   Region: {REGION}")

    try:
        while True:
            time.sleep(interval)
            resp = describe_job(sm, job_name)
            print_status(resp)
            if is_finished(resp["TrainingJobStatus"]):
                total = (datetime.now(timezone.utc) - resp.get("TrainingStartTime", datetime.now(timezone.utc))).total_seconds()
                hours = int(total // 3600)
                mins = int((total % 3600) // 60)
                print(f"Training finished after {hours}h {mins}m.")
                break
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
