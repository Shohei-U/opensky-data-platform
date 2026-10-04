#!/usr/bin/env bash
# Let GitHub Actions in this repository write to GCS without a key file
# (Workload Identity Federation). Run once, by a person, with the project's gcloud config.
# Explained step by step in docs/runbook/github-actions-wif.md.
# Safe to re-run: steps whose resource already exists are skipped.
set -euo pipefail

PROJECT=opensky-data-platform
PROJECT_NUMBER=111971818872
REPO_ID=1401906814   # Shohei-U/opensky-data-platform (the ID never changes, unlike the name)
POOL=github
PROVIDER=opensky-repo
SA=opensky-ingest@${PROJECT}.iam.gserviceaccount.com

echo "== 1/4 enable the APIs that exchange GitHub tokens for GCP credentials"
gcloud services enable iam.googleapis.com iamcredentials.googleapis.com sts.googleapis.com \
  --project="$PROJECT"

echo "== 2/4 create the workload identity pool"
if gcloud iam workload-identity-pools describe "$POOL" --project="$PROJECT" --location=global \
  --format=none 2>/dev/null; then
  echo "   already exists, skipped"
else
  gcloud iam workload-identity-pools create "$POOL" --project="$PROJECT" --location=global \
    --display-name="GitHub Actions"
fi

echo "== 3/4 create the OIDC provider (only this repository's main branch is accepted)"
if gcloud iam workload-identity-pools providers describe "$PROVIDER" --project="$PROJECT" \
  --location=global --workload-identity-pool="$POOL" --format=none 2>/dev/null; then
  echo "   already exists, skipped"
else
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER" --project="$PROJECT" \
    --location=global --workload-identity-pool="$POOL" \
    --display-name="opensky-data-platform main" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository_id=assertion.repository_id,attribute.ref=assertion.ref" \
    --attribute-condition="assertion.repository_id=='${REPO_ID}' && assertion.ref=='refs/heads/main'"
fi

echo "== 4/4 let workflows from this repository act as the ingest service account"
gcloud iam service-accounts add-iam-policy-binding "$SA" --project="$PROJECT" \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/attribute.repository_id/${REPO_ID}" \
  --format=none

echo
echo "provider: projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/providers/${PROVIDER}"
echo "service account: ${SA}"
