# 取得ワークフローを Cloud Scheduler から起動する（ADR 0004・0006）

```
Cloud Scheduler: opensky-ingest-dispatch（us-central1、毎時0分、UTC）
  │ POST https://api.github.com/repos/Shohei-U/opensky-data-platform/actions/workflows/ingest.yml/dispatches
  │ body {"ref":"main"}、ヘッダー Authorization: Bearer <fine-grained token>
  ▼
GitHub Actions: ingest（workflow_dispatch）── 30秒×108回（約54分）──▶ OpenSky ──▶ GCS（1時間に2ファイル）
```

## 1. GitHub のトークンを作る（本人、ブラウザ）

GitHub → 右上のアイコン → **Settings** → 左の一番下 **Developer settings** → **Personal access tokens** → **Fine-grained tokens** → **Generate new token**

| 項目 | 値 |
|---|---|
| Token name | `opensky-ingest-dispatch` |
| Expiration | 期限を選ぶ（例: 1年）。期限は ops-log に書く |
| Resource owner | `Shohei-U` |
| Repository access | **Only select repositories** → `Shohei-U/opensky-data-platform` |
| Permissions → Repository permissions | **Actions: Read and write**（Metadata: Read-only は自動で付く）。ほかは No access のまま |

**Generate token** を押し、表示された `github_pat_...` をコピーする（この画面を閉じると二度と表示されない）。チャットやファイルには貼らない。

## 2. Cloud Scheduler のジョブを作る（本人、ターミナル）

トークンをコピーした直後に、リポジトリのルートで実行する。

```bash
bash scripts/gcp/setup-ingest-scheduler.sh
```

| 手順 | やること |
|---|---|
| クリップボードを読む | `pbpaste` でトークンを読む。`github_pat_` で始まらなければ止まる。画面にも履歴にも出ない |
| 1/2 | Cloud Scheduler の API を有効にする |
| 2/2 | ジョブがなければ作る、あれば更新する（トークンの更新もこれで行う） |

終わったら、クリップボードを別の内容で上書きしておく。

## 3. 確かめる

```bash
gcloud scheduler jobs run opensky-ingest-dispatch --location=us-central1   # 今すぐ1回呼ぶ
gh run list -R Shohei-U/opensky-data-platform --workflow ingest.yml --limit 3
gcloud scheduler jobs describe opensky-ingest-dispatch --location=us-central1 \
  --format='value(state,schedule,lastAttemptTime,status)'
```

`gh run list` に `workflow_dispatch` の実行が増えていれば成功。Cloud Scheduler の呼び出しが失敗すると、ジョブの `status` にエラーのコード（401 ならトークンの誤りか期限切れ）が出る。

## 間隔だけ変える（トークンはそのまま）

```bash
gcloud scheduler jobs update http opensky-ingest-dispatch --location=us-central1 \
  --schedule="0 * * * *"
```

`update` は指定した項目だけを変える。ヘッダー（トークン）は残る。2026-10-05 に5分ごとから毎時に変えた（ADR 0006）。

## 止める・再開する

```bash
gcloud scheduler jobs pause opensky-ingest-dispatch --location=us-central1
gcloud scheduler jobs resume opensky-ingest-dispatch --location=us-central1
```
