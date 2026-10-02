# Cloud Run Job のデプロイ手順（#10）

> 2026-10-02: Cloud Run からは OpenSky に接続できない（GCP の IP が遮断される）ため、取得は GitHub Actions に移した（ADR 0003）。この手順で作った部品は残してあり、第3週以降のロードや dbt に使い回す可能性がある。

第8週に Terraform へ置き換えるまで、クラウドの設定はこの手順で行う。決定の理由は [ADR 0002](../adr/0002-cloud-run-job-permissions-and-secrets.md)。

gcloud の個人用の構成で実行する。各コマンドの前に、変数を設定しておく。

```bash
PROJECT=opensky-data-platform
REGION=us-central1
BUCKET=opensky-data-platform-raw
SA=opensky-ingest@${PROJECT}.iam.gserviceaccount.com
IMAGE=${REGION}-docker.pkg.dev/${PROJECT}/opensky/ingest
```

## 1. 使う API を有効にする（初回のみ）

```bash
gcloud services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com
```

Cloud Run・Artifact Registry・Secret Manager をこのプロジェクトで使えるようにする。有効にするだけでは課金されない。

## 2. イメージ置き場を作る（初回のみ）

```bash
gcloud artifacts repositories create opensky --repository-format=docker --location=$REGION
gcloud artifacts repositories set-cleanup-policies opensky --location=$REGION \
  --policy=docs/runbook/artifact-cleanup-policy.json --no-dry-run
```

Artifact Registry に Docker 用のリポジトリ `opensky` を作り、最新の2つ以外のイメージを自動で消すルールを付ける（無料枠 0.5GB を超えないため）。

## 3. サービスアカウントと権限（初回のみ）

```bash
gcloud iam service-accounts create opensky-ingest --display-name="OpenSky ingest job"
gcloud storage buckets add-iam-policy-binding gs://$BUCKET \
  --member=serviceAccount:$SA --role=roles/storage.objectUser
```

ジョブ専用のアカウントを作り、このバケットだけに読み書き（上書き含む）の権限を付ける。プロジェクト全体には権限を付けない。

## 4. OpenSky の認証情報を Secret Manager に置く（初回のみ）

```bash
gcloud secrets create opensky-credentials --replication-policy=user-managed --locations=$REGION \
  --data-file=$HOME/.config/opensky/credentials.json
gcloud secrets add-iam-policy-binding opensky-credentials \
  --member=serviceAccount:$SA --role=roles/secretmanager.secretAccessor
```

手元の `credentials.json` を丸ごと1つのシークレットにし、ジョブのアカウントだけが読めるようにする。値はターミナルに表示されない。

## 5. イメージをビルドして送る（コードを変えるたび）

```bash
gcloud auth configure-docker ${REGION}-docker.pkg.dev   # 初回のみ
docker build --platform linux/amd64 -t $IMAGE:latest ingestion
docker push $IMAGE:latest
```

- `configure-docker`: `docker push` のときに gcloud の認証を使うよう、`~/.docker/config.json` に `us-central1-docker.pkg.dev` 用の設定を1行足す
- `--platform linux/amd64`: Cloud Run は x86 で動くため、Apple Silicon の Mac でも x86 用にビルドする

## 6. ジョブを作る（初回のみ。2回目以降は `create` を `update` に）

```bash
gcloud run jobs create opensky-ingest --region=$REGION --image=$IMAGE:latest \
  --service-account=$SA \
  --set-secrets=/secrets/opensky/credentials.json=opensky-credentials:latest \
  --set-env-vars=OPENSKY_DEST=gs://$BUCKET,OPENSKY_CREDENTIALS_PATH=/secrets/opensky/credentials.json \
  --cpu=1 --memory=512Mi --task-timeout=10m --max-retries=1
```

- `--set-secrets`: シークレットをファイルとして `/secrets/opensky/credentials.json` に置く
- `--task-timeout=10m`: 1回の実行は約5分なので、10分で打ち切る
- `--max-retries=1`: プロセスごと落ちたときに1回だけやり直す。API の一時的な失敗はアプリの中でリトライ済み（#8）

## 7. 手動で1回実行して確かめる

```bash
gcloud run jobs execute opensky-ingest --region=$REGION --wait
gcloud storage ls -l "gs://$BUCKET/raw/dt=$(date -u +%F)/**" | tail -3
gcloud logging read 'resource.type="cloud_run_job" AND resource.labels.job_name="opensky-ingest"' \
  --limit=5 --freshness=15m --format='value(severity,jsonPayload.message)'
```

`--wait` で終わるまで待つ。GCS にその5分枠のファイルができ、ログに1行（`fetched N rows in 10 fetches`）が出ていれば完了。
