# opensky-data-platform

OpenSky Network の航空機位置データ（ADS-B）を沖縄周辺で継続取得し、GCS → BigQuery → dbt でフライト単位に集計するデータ基盤。GCP の無料枠内で運用する個人プロジェクト。

## 現状（2026-09-29 / 第1週完了）

- [x] 沖縄 bbox を取得し、JSONL.gz で保存（18機・1クレジット/回）
- [x] GCS（us-central1）に配置: `gs://opensky-data-platform-raw/raw/dt=/hh=/`
- [x] [ADR 0001](docs/adr/0001-bbox-selection.md)（取得範囲: 沖縄周辺、5分ごとに10回取得）
- [ ] 第2週: Cloud Run Jobs + Scheduler で5分ごとに自動取得

## 構成（予定）

```
Cloud Scheduler → Cloud Run Jobs (Python) → GCS raw/dt=/hh=/ → BigQuery raw.states → dbt → Looker Studio
```

## 使い方

```bash
# 認証情報: 環境変数 OPENSKY_CLIENT_ID / OPENSKY_CLIENT_SECRET
# または ~/.config/opensky/credentials.json
uv run --project ingestion pytest ingestion
uv run --project ingestion python -m opensky_ingest.cli   # → data/raw/dt=YYYY-MM-DD/hh=HH/*.jsonl.gz
```

## ドキュメント

- [ADR](docs/adr/)
- [運用記録](docs/ops-log.md)

## データ出典

Data provided by [The OpenSky Network](https://opensky-network.org/). 非商用・研究目的で利用。

> Matthias Schäfer, Martin Strohmeier, Vincent Lenders, Ivan Martinovic and Matthias Wilhelm.
> "Bringing Up OpenSky: A Large-scale ADS-B Sensor Network for Research."
> In Proceedings of the 13th IEEE/ACM International Symposium on Information Processing in Sensor Networks (IPSN), pages 83-94, April 2014.
