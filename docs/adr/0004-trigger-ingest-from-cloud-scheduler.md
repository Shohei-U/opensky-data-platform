# 0004. 取得ワークフローは Cloud Scheduler から起動する

- 日付: 2026-10-04
- ステータス: 承認

## 要約

GitHub の schedule が動かなかったため、Cloud Scheduler が5分ごとに GitHub Actions を起動する。

## 背景

ADR 0003 で取得を GitHub Actions に移し、`schedule`（cron）で5分ごとに動かす予定だった。しかし、このリポジトリでは schedule の実行が1回も作られなかった。

| 時刻（UTC） | 出来事 | schedule の実行 |
|---|---|---|
| 07:16 | `ingest.yml` を main に追加（cron `*/5`） | — |
| 07:16〜08:31 | 待つ | 0回 |
| 08:31 | 登録をやり直す（ワークフローを変更して main に入れる、cron を `2-59/5` に） | — |
| 08:31〜09:03 | 待つ | 0回 |

手動実行（workflow_dispatch）は2回とも成功した。GitHub のコミュニティでも、2026年に同じ症状（新しいリポジトリや一部の Public リポジトリで schedule が動かない）が報告されている。原因は GitHub 側で、こちらからは確かめられない。

## 選択肢

| 選択肢 | 費用 | 良い点 | 気になる点 |
|---|---|---|---|
| GitHub の schedule が動き出すのを待つ | 0円 | 何もしなくてよい | 動く保証がない。待つ間データが欠ける |
| **Cloud Scheduler から workflow_dispatch を呼ぶ** | 0円（無料枠 3 ジョブ） | 時刻が正確。ADP の Cloud Scheduler を実物で使える | GitHub のトークンを GCP に置く。期限が来たら更新が必要 |
| 外部の無料 cron サービスから呼ぶ | 0円 | 設定が簡単 | 第三者にトークンを預ける |
| 手元の Mac（launchd）から呼ぶ | 0円 | すぐできる | スリープ中は止まる |

## 決定

- Cloud Scheduler のジョブ `opensky-ingest-dispatch`（us-central1、`*/5 * * * *`、UTC）が、GitHub API の `POST /repos/Shohei-U/opensky-data-platform/actions/workflows/ingest.yml/dispatches`（`{"ref":"main"}`）を呼ぶ
- トークンは fine-grained personal access token。対象はこのリポジトリだけ、権限は Actions の Read and write だけ
- ワークフローから `schedule:` を外す。GitHub の schedule が後から動き出すと、二重に起動して OpenSky のクレジット（1日 4,000）を超えるため（5分ごと×10回×2 = 1日 5,760）

## 理由

- 0円で、GitHub の schedule の不具合に左右されない
- GCP から GitHub への接続は遮断されていない（遮断されているのは GCP → OpenSky）
- ADR 0003 で取得から外れた Cloud Scheduler を、ここで使える

## 影響・見直し条件

- トークンには期限がある。期限の前に作り直し、`scripts/gcp/setup-ingest-scheduler.sh` を再実行する。期限は `docs/ops-log.md` に書いておく
- トークンは Cloud Scheduler のジョブの設定（ヘッダー）に入る。ジョブの設定を読めるのはプロジェクトのオーナーだけ
- Cloud Scheduler が呼べても、GitHub Actions 側が混んでいると開始が遅れることがある。遅れと欠けは meta の `run_started_at` で測る
- 第8週の Terraform 化で、このジョブも管理対象にする（トークンは Terraform の state に入れない方法を考える）
