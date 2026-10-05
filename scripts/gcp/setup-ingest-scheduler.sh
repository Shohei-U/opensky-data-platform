#!/usr/bin/env bash
# Start the ingest workflow every hour from Cloud Scheduler (ADR 0004, ADR 0006).
# Run by a person, once (re-run to rotate the token). Explained in docs/runbook/ingest-scheduler.md.
#
# The GitHub token is read from the clipboard (copy it right before running) so it never
# appears on screen, in shell history, or in this repository.
set -euo pipefail

PROJECT=opensky-data-platform
REGION=us-central1
JOB=opensky-ingest-dispatch
URL=https://api.github.com/repos/Shohei-U/opensky-data-platform/actions/workflows/ingest.yml/dispatches

TOKEN="$(pbpaste | tr -d '[:space:]')"
if [[ "$TOKEN" != github_pat_* ]]; then
  echo "The clipboard does not hold a fine-grained GitHub token (github_pat_...). Copy it and re-run." >&2
  exit 1
fi

echo "== 1/2 enable the Cloud Scheduler API"
gcloud services enable cloudscheduler.googleapis.com --project="$PROJECT"

if gcloud scheduler jobs describe "$JOB" --project="$PROJECT" --location="$REGION" \
  --format=none 2>/dev/null; then
  action=update
  header_flag=--update-headers
else
  action=create
  header_flag=--headers
fi

echo "== 2/2 ${action} the job ${JOB} (every hour on the hour, UTC)"
gcloud scheduler jobs "$action" http "$JOB" --project="$PROJECT" --location="$REGION" \
  --schedule="0 * * * *" --time-zone="Etc/UTC" \
  --uri="$URL" --http-method=POST \
  --message-body='{"ref":"main"}' \
  "$header_flag"="Authorization=Bearer ${TOKEN},Accept=application/vnd.github+json,X-GitHub-Api-Version=2022-11-28,User-Agent=opensky-ingest-scheduler,Content-Type=application/json" \
  --attempt-deadline=30s --format=none

echo
echo "job: ${JOB} (${REGION}) -> ${URL}"
echo "you can clear the clipboard now (e.g. copy something else)."
