# opensky-data-platform

[![ingest](https://github.com/Shohei-U/opensky-data-platform/actions/workflows/ingest.yml/badge.svg)](https://github.com/Shohei-U/opensky-data-platform/actions/workflows/ingest.yml)
[![CI](https://github.com/Shohei-U/opensky-data-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/Shohei-U/opensky-data-platform/actions/workflows/ci.yml)

OpenSky Network の航空機位置データ（ADS-B）を沖縄周辺で継続取得し、GCS → BigQuery → dbt でフライト単位に集計するデータ基盤。GCP の無料枠内で運用する個人プロジェクト（12週間）。

## 構成

```
Cloud Scheduler（5分ごと）── workflow_dispatch ──▶ GitHub Actions ── 30秒×10回取得 ──▶ OpenSky REST API（沖縄周辺 24–28N, 123–129E）
   │ Workload Identity Federation（鍵ファイルなし）
   ▼
GCS  gs://opensky-data-platform-raw
   ├ raw/dt=YYYY-MM-DD/hh=HH/<5分枠>.jsonl.gz   state vector（1回の起動 = 1ファイル）
   └ meta/dt=YYYY-MM-DD/hh=HH/<5分枠>.jsonl     取得ごとのステータス・件数・残りクレジット・試行回数
   ▼
BigQuery（第3週）→ dbt（第4〜5週）→ Looker Studio（第6週）
```

取得を GCP ではなく GitHub Actions で動かしているのは、**OpenSky が GCP の IP からの接続を遮断している**ため（Cloud Run・Cloud Shell から接続できないことを確かめた）。経緯は [ADR 0003](docs/adr/0003-ingestion-runs-on-github-actions.md)。GitHub Actions の schedule はこのリポジトリでは動かなかったため、起動は Cloud Scheduler から行う（[ADR 0004](docs/adr/0004-trigger-ingest-from-cloud-scheduler.md)）。

## 現状（2026-10-04 / 第2週）

- [x] 第1週: 沖縄 bbox を1回取得して GCS に配置、取得範囲を決定（[ADR 0001](docs/adr/0001-bbox-selection.md)）
- [x] 第2週: 5分ごとに自動で取得して GCS に貯める（2026-10-04 09:25 UTC の枠から稼働）
  - 30秒×10回を1ファイルに、指数バックオフと 429 対応、5分枠のファイル名で冪等に上書き
  - Cloud Run Jobs にデプロイ → OpenSky に接続できないと判明 → GitHub Actions に移行（[ADR 0002](docs/adr/0002-cloud-run-job-permissions-and-secrets.md)・[ADR 0003](docs/adr/0003-ingestion-runs-on-github-actions.md)）
  - 失敗も1行の構造化ログ（`severity` 付き JSON）
- [ ] 第3週: BigQuery で生データが見える

## 設計判断（ADR）

| # | 決定 |
|---|---|
| [0001](docs/adr/0001-bbox-selection.md) | 取得範囲は沖縄周辺（1クレジット/回）、5分ごとに起動して30秒間隔×10回 |
| [0002](docs/adr/0002-cloud-run-job-permissions-and-secrets.md) | サービスアカウントはバケット単位の objectUser、認証情報は Secret Manager に JSON 1つ |
| [0003](docs/adr/0003-ingestion-runs-on-github-actions.md) | GCP の IP は遮断されるため、取得は GitHub Actions（Public リポジトリ）で動かす |
| [0004](docs/adr/0004-trigger-ingest-from-cloud-scheduler.md) | GitHub の schedule が動かないため、Cloud Scheduler から workflow_dispatch で起動する |

## 使い方

```bash
# 認証情報: 環境変数 OPENSKY_CLIENT_ID / OPENSKY_CLIENT_SECRET
# または ~/.config/opensky/credentials.json（OPENSKY_CREDENTIALS_PATH で場所を変えられる）
uv run --project ingestion pytest ingestion                          # テスト
uv run --project ingestion ruff check ingestion                      # lint
uv run --project ingestion python -m opensky_ingest.cli              # 30秒×10回 → data/raw/, data/meta/
uv run --project ingestion python -m opensky_ingest.cli --dest gs://<bucket> --count 2 --interval 5
```

| ディレクトリ | 中身 |
|---|---|
| `ingestion/` | 取得（`fetch`）、リトライ（`retry`）、繰り返し取得（`collect`）、出力先（`sink`: ローカル / GCS）、CLI、Dockerfile |
| `.github/workflows/` | `ingest.yml`（取得。Cloud Scheduler から起動）、`ci.yml`（ruff・pytest） |
| `scripts/gcp/` | GCP の設定スクリプト（Workload Identity Federation、Cloud Scheduler） |
| `docs/adr/` | 設計判断 |
| `docs/runbook/` | クラウドの設定手順（Cloud Run Job、Workload Identity Federation、Cloud Scheduler） |
| `docs/learning/` | 週ごとに学んだこと |

## ドキュメント

- [ADR](docs/adr/)
- [手順書](docs/runbook/)
- [週ごとの学び](docs/learning/)
- [運用記録](docs/ops-log.md)

## データ出典

Data provided by [The OpenSky Network](https://opensky-network.org/). 非商用・研究目的で利用。

> Matthias Schäfer, Martin Strohmeier, Vincent Lenders, Ivan Martinovic and Matthias Wilhelm.
> "Bringing Up OpenSky: A Large-scale ADS-B Sensor Network for Research."
> In Proceedings of the 13th IEEE/ACM International Symposium on Information Processing in Sensor Networks (IPSN), pages 83-94, April 2014.
