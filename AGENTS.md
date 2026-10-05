# AGENTS.md

OpenSky Network の ADS-B データを沖縄周辺で取得し、GCS → BigQuery → dbt でフライト単位に集計する個人のデータ基盤。GCP 無料枠内で運用する。

## 計画とローカル環境

- 12週間の計画（ロードマップ・コスト設計・資格との並走）は本人の手元にあり、リポジトリには置かない
- この Mac の環境・アカウントの分け方は `AGENTS.local.md`（git の管理外）にある。gh・gcloud・git の操作前に読む
- 設計の経緯は `docs/adr/`、週ごとの学びは `docs/learning/`

## 作業ルール

- 設計判断は本人が決める。決め方は「図1枚＋問い1つ＋案2〜3個」を会話で出し、本人が選ぶ。ADR は後から戻しにくい判断（データの置き場所・動かす場所・スキーマ）だけ、決めた後にエージェントが1ページで清書する（本人は読まなくてよい）。形と読み方は `docs/adr/README.md`（初心者向けの説明つき）。小さな調整は PR の本文に理由を書くだけにする
- コードと定型の git / GitHub 操作（Issue・ブランチ・commit・push・PR 作成）はエージェントが行う。アカウント作成・課金設定・クラウドへの変更は本人が実行する（コマンドの意味を説明してから）
- GCP 無料枠を守る: リージョンは `us-central1` 固定、Cloud Logging にデバッグログを垂れ流さない、BigQuery に生データを長期保持しない、`SELECT *` をマートに向けない、Cloud Run は Jobs のみ（Service を常時起動しない）、Composer / Data Fusion は起動しない
- 費用は0円が絶対条件（基盤もハンズオンも）。無料枠を少しでも超える設計は選ばない。資格（ADP）のために足すハンズオンも同じ。着手前に公式の料金ページで無料枠に収まることを確かめ、出典を Issue に残す。有料・不明・期限つきの無料（期限までに削除できないもの）なら、作らずに座学にする
- GCP を有料アカウントへアップグレードしない、$300 クレジットは使わない（トライアル終了時の扱いは要確認: https://cloud.google.com/free）
- 認証情報はリポジトリに置かない（`.gitignore` 済み）。OpenSky は `~/.config/opensky/credentials.json` または環境変数 `OPENSKY_CLIENT_ID` / `OPENSKY_CLIENT_SECRET`
- 顧客・社内データ・社内コードは持ち込まない
- commit / push 前にセキュリティスキャン（credentials 混入チェック）を行う
- 危険な操作（gcloud・merge・terraform・bq・認証情報の読み取り）の ask / deny は `.claude/settings.json` に定義している。ルールを緩める変更は本人が判断する
- 1タスク = 1PR（詳細は「開発フロー」）。日次メモは `notes/YYYY-MM-DD.md` に1行

## 現在の状態（2026-10-04 時点・第2週完了）

```
① 取り込み  ✅ #7 繰り返し取得 ✅ #8 リトライ ✅ #9 GCS へ書く ✅ #10 コンテナ化・Cloud Run（遮断が判明）
            ✅ Public に作り直し（#31） ✅ Workload Identity Federation（#29） ✅ #28 失敗ログ ✅ #30 定期実行（Cloud Scheduler → GitHub Actions、ADR 0004）
② 蓄積 BigQuery（第3週）✅ ADR 0005 → ③ 変換 dbt（第4〜5週） → ④ 提供 Looker Studio（第6週） → ⑤ 運用（第7〜12週）
```

- ADR 0001: 沖縄周辺（24–28N, 123–129E）、1クレジット/回（間隔は ADR 0006 で変更）
- ADR 0002: Cloud Run Job 用サービスアカウント `opensky-ingest` にバケット単位の objectUser、認証情報は Secret Manager の `opensky-credentials`（JSON 1つ）
- ADR 0003: GCP の IP は OpenSky に遮断される（Cloud Run・Cloud Shell とも接続不可、GitHub Actions は接続可）。取得は GitHub Actions の schedule で動かし、リポジトリを Public にする。GCS へは Workload Identity Federation で認証する
- GCP: プロジェクト `opensky-data-platform`（無料トライアル中、期限 2026-12-29、アップグレードしない）、予算アラート 月500円（20/60/100%、クレジットを差し引かない）
- GCS: `gs://opensky-data-platform-raw`（us-central1）。`raw/` と `meta/` は `dt=YYYY-MM-DD/hh=HH/<5分枠>.jsonl(.gz)`。試しの書き込みは `dev/` の下
- #10 で作ったもの（残してある。実行しなければ費用はほぼ0）: Artifact Registry `opensky`（イメージ `ingest`、最新2つだけ残す）、Cloud Run Job `opensky-ingest`、Secret `opensky-credentials`、サービスアカウント `opensky-ingest`。手順は `docs/runbook/cloud-run-job.md`
- ADR 0004: GitHub の schedule は動かなかったため、Cloud Scheduler `opensky-ingest-dispatch`（us-central1、毎時0分）が workflow_dispatch を呼ぶ。トークン（fine-grained、Actions: Read and write のみ）の期限は 2027-10-04 ごろ。手順は `docs/runbook/ingest-scheduler.md`
- ADR 0005: GCS → BigQuery は Data Transfer Service の Cloud Storage 転送（1時間ごと、raw と meta の2設定）。raw テーブルは日付パーティション、有効期限30日（正本は GCS）
- ADR 0006: GCS の Class A を無料枠内にするため、取得は毎時起動して30秒×108回（約54分）を1回で書く。トークンは25分で取り直す。DTS は毎時30分、転送元 `raw/dt={run_time-1h|"%Y-%m-%d"}/*`、MIRROR でその日のパーティションを入れ直す（Class A 約3,000回/月）
- 取得: `.github/workflows/ingest.yml`（workflow_dispatch のみ。1回約55分、timeout 65分）。OpenSky の認証情報は GitHub Secrets（`OPENSKY_CLIENT_ID` / `OPENSKY_CLIENT_SECRET`）
- CI: `.github/workflows/ci.yml`（PR と main への push で ruff・pytest）。main はブランチ保護（PR 必須・CI 必須・管理者にも適用）
- Workload Identity Federation: プール `github`、プロバイダ `opensky-repo`（このリポジトリの ID と main だけ）、なりすまし先は `opensky-ingest`。手順は `docs/runbook/github-actions-wif.md`
- `gh` は接続先が2つ（`origin` と旧リポジトリの `archive`）あるため、`-R Shohei-U/opensky-data-platform` を付けて実行する
- 権限ルール: `.claude/settings.json`（gcloud・terraform apply・bq は ask、削除・課金系は deny）

次にやること:

- 第3週: `bash scripts/gcp/setup-bigquery.sh`（データセット `opensky_raw`、テーブル `states`・`fetch_meta`）→ Console で DTS を2つ作る → SQL で確認。手順は `docs/runbook/bigquery-dts.md`

未解決:

- クレジットが戻るタイミング（UTC 0時では戻らなかった。直近24時間の積算か未確認）
- トライアル終了後（2026-12-29 以降）にアップグレードなしで無料枠を使い続けられるか
- GCS の操作回数: 無料枠は Class A 月 5,000 回・Class B 月 5万回（us-central1、2026-10-04 に確認）。ADR 0006 で Class A は月約3,000回、Class B は約1.8万回の見込み。切り替え後に実際の回数を Console の請求で確かめる
- Secret Manager の無料枠の数値（ADR 0002 の前提、未確認）
- 地上機（`on_ground=true`）が見えていない。離着陸は高度の変化で判定する方針（第6週）

## 開発フロー（個人開発の GitHub Flow）

手順は `gh-flow` スキルに従う。以下はこのリポジトリの規約で、スキルの既定値より優先する。

- 管理: GitHub Projects https://github.com/users/Shohei-U/projects/1 、マイルストーン `Week N`。ボードのステータスは `scripts/board.sh <Issue番号> "In Progress"`
- main には PR 経由でしか入れない（main へ直接 push しない）。ブランチは短命（1〜2日で merge）、関係のない変更は別ブランチに分ける
- Issue は週のゴールと作業の単位だけ作る。調べもの・小さな調整・ルールの変更は Issue にせず、次の PR にまとめる
- ブランチ名 `<Issue番号>-<kebab要約>`（Issue なしは `chore-<要約>` など）。PR 本文は「何を・なぜ・どう確認したか」と `Closes #番号`。squash merge、merge 後はブランチを削除
- commit: Conventional Commits `<type>(<scope>): <要約> (#番号)`
- Issue タイトルは内容をそのまま書く（`[対象]` は付けない）。ラベルは `human`（本人作業）/ `agent`（エージェント実装）/ `adr`（設計判断）
- リポジトリを変えない Issue（アカウント作成・クラウド設定など）はブランチを切らず、結果を Issue にコメントして閉じる
- 役割: git / GitHub の手続き（Issue・ボード・ブランチ・commit・push・PR・merge・ブランチ削除）はすべてエージェントが行い、報告では省く。merge は `gh pr checks` が全て成功してから。本人は技術の理解と実装、設計判断、クラウド操作の確認に集中する
- 実装はエージェントが書き、何をしているかを随時説明する（本人はコードを書かない）: ① 今回の技術テーマを短く説明（なぜ必要か・仕組み・ADP との対応）→ ② 実装しながら、判断が入る箇所は理由を説明 → ③ 実際に動かして挙動を見せる → ④ 報告は「何を学べるか」を中心にする。本人への確認は設計判断とクラウド操作だけ
- ADP の試験対策は `docs/adp/README.md` に集める。作業が終わるたびに、対応する行の状態（✅ / 🔜 / 📖）と「この基盤のどこ」を更新し、触ったものから確認問題を1〜2問足す
- gcloud・bq は意味を説明してから本人が実行する。実装した週に ADP 試験ガイドの該当範囲を読む
- Public にしたら main のブランチ保護（PR 必須・CI 必須）を設定する

## よく使うコマンド

```bash
uv run --project ingestion pytest ingestion              # テスト
uv run --project ingestion ruff check ingestion           # lint
uv run --project ingestion python -m opensky_ingest.cli   # 30秒間隔×10回取得 → data/raw/, data/meta/（--dest gs://opensky-data-platform-raw で GCS）
```

`data/` は `.gitignore` 済み（生データは GCS に置く）。
