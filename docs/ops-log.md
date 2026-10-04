# 運用記録

| 週 | 期間 | 稼働日数 | Billing 実額 | 障害・対処 | メモ |
|---|---|---|---|---|---|
| 1 | 2026-09-26〜09-29 | 3 | 0円（トライアル中、クレジット使用 0） | 障害なし | GCP・GCS 準備、ADR 0001 承認。自動取得は未稼働 |
| 2 | 2026-09-30〜10-04 | 5 | 未確認（Console の請求で確認する） | Cloud Run から OpenSky に接続できない（GCP の IP が遮断）→ 取得を GitHub Actions に移行（ADR 0003）。WIF 設定時に API 有効化直後の PERMISSION_DENIED（再実行で解消） | 10-04 09:25 UTC の枠から Cloud Scheduler → GitHub Actions で5分ごとに自動取得（ADR 0004）。GitHub の schedule は一度も動かず。リポジトリを Public に作り直し |

## 期限のあるもの

| もの | 期限 | 更新の手順 |
|---|---|---|
| GitHub fine-grained token `opensky-ingest-dispatch`（Cloud Scheduler が workflow_dispatch を呼ぶ） | 2027-10-04 ごろ（作成時に1年を選択） | GitHub で Regenerate → `bash scripts/gcp/setup-ingest-scheduler.sh` を再実行（docs/runbook/ingest-scheduler.md） |
| GCP 無料トライアル | 2026-12-29 | アップグレードしない。終了後の扱いを確認する |
