#!/usr/bin/env bash
# Create the BigQuery dataset and the two raw tables that DTS loads into (ADR 0005, ADR 0006).
# Run by a person, once. Re-running skips what already exists.
# Explained in docs/runbook/bigquery-dts.md. The DTS transfers themselves are made in the
# Console, because `bq mk --transfer_config` cannot set the schedule for Cloud Storage.
set -euo pipefail

PROJECT=opensky-data-platform
LOCATION=us-central1          # same region as the bucket; the free tier is US-region only
DATASET=opensky_raw
EXPIRATION=$((30 * 24 * 60 * 60))  # 30 days: GCS keeps the originals (ADR 0005)

cd "$(dirname "$0")/../.."

echo "== 1/3 enable the BigQuery and Data Transfer APIs"
gcloud services enable bigquery.googleapis.com bigquerydatatransfer.googleapis.com \
  --project="$PROJECT"

echo "== 2/3 dataset ${DATASET} (${LOCATION})"
if bq --project_id="$PROJECT" --format=none show "$DATASET" 2>/dev/null; then
  echo "exists, skipped"
else
  bq --project_id="$PROJECT" --location="$LOCATION" mk --dataset \
    --description="OpenSky raw data loaded from GCS by DTS. Partitions expire after 30 days." \
    "${PROJECT}:${DATASET}"
fi

echo "== 3/3 tables (partitioned by day, partitions expire after 30 days)"
for table in states fetch_meta; do
  if bq --project_id="$PROJECT" --format=none show "${DATASET}.${table}" 2>/dev/null; then
    echo "${table}: exists, skipped"
    continue
  fi
  # Ingestion-time partitioning: DTS writes each day into table$YYYYMMDD (ADR 0006).
  bq --project_id="$PROJECT" mk --table \
    --time_partitioning_type=DAY \
    --time_partitioning_expiration="$EXPIRATION" \
    --require_partition_filter=true \
    "${PROJECT}:${DATASET}.${table}" "bigquery/schema/${table}.json"
done

echo
bq --project_id="$PROJECT" ls "$DATASET"
