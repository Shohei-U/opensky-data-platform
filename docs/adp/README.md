# ADP 試験対策: この基盤で触ったものから学ぶ

Google Cloud Associate Data Practitioner（ADP）の試験範囲と、この基盤で実際に作ったものを対応させたページ。「触った → 読む → 問題で確かめる」の順で使う。

- 試験ガイド（v1.0）: https://services.google.com/fh/files/misc/v1.0_associate_data_practitioner_exam_guide_english.pdf
- 試験のページ: https://cloud.google.com/learn/certification/data-practitioner （近く製品名の変更に合わせて改訂予定と書かれている）

## 使い方（1日10〜20分）

1. 下の対応表から、今週 ✅ になった行を1つ選ぶ
2. 「この基盤のどこ」を開いて、何をしているかを見る（説明は `docs/learning/week-NN.md`）
3. 「試験で問われる観点」を読み、末尾の確認問題を解く

記号: ✅ 触った ／ 🔜 この先の週で触る ／ 📖 読むだけ（費用0円で触れない、または試験で操作まで問われにくい）

## 1. データの準備と取り込み（約30%）

| 試験の項目 | 状態 | この基盤のどこ | 試験で問われる観点 |
|---|---|---|---|
| データの形式（CSV・JSON・Parquet・Avro） | ✅ | `ingestion/src/opensky_ingest/cli.py`（JSON Lines を gzip で保存） | JSON は半構造化。BigQuery へのロードは Avro・Parquet が速くスキーマも持てる。CSV・JSON はスキーマを別に指定する |
| 保存先の選択（GCS・BigQuery・Cloud SQL・Bigtable・Spanner） | ✅ | ADR 0003・0005（生データは GCS、分析は BigQuery） | 生ファイルは GCS、分析は BigQuery、トランザクションは Cloud SQL・Spanner、低遅延の大量キー検索は Bigtable |
| 保存場所の種類（リージョン・デュアルリージョン・マルチリージョン） | ✅ | GCS バケットと BigQuery は `us-central1`（リージョン） | リージョンは安く、近くで処理できる。デュアル・マルチは可用性が高いが高い。無料枠は一部の US リージョンだけ |
| 取り込みツールの選択（DTS・Storage Transfer Service・Dataflow・Data Fusion） | ✅ | ADR 0005（BigQuery Data Transfer Service を選んだ） | GCS・SaaS から BigQuery への定期ロードは DTS。バケット間・他クラウドからのファイル移動は Storage Transfer Service。変換しながらのストリームは Dataflow |
| ロードの道具（gcloud・bq コマンド・クライアントライブラリ） | ✅ / 🔜 | `sink.py`（Python のクライアントライブラリで GCS に書く）。第3週に bq コマンドでテーブルを作る | バッチロードは無料、ストリーミング挿入は有料 |
| ETL と ELT、データ品質、クレンジング | 🔜 第4週 | dbt の staging（重複の除去・型付け・テスト） | ELT は「先に入れて BigQuery の SQL で変換」。今の主流 |
| Transfer Appliance | 📖 | — | ネットワークで送れないほど大量のデータを、物理的な機器で運ぶ |

## 2. データの分析と提示（約27%）

| 試験の項目 | 状態 | この基盤のどこ | 試験で問われる観点 |
|---|---|---|---|
| BigQuery の SQL で集計する | 🔜 第3〜6週 | raw の確認、dbt のマート | パーティションで絞るとスキャン量（＝費用）が減る |
| Looker Studio でダッシュボード | 🔜 第6週 | 日ごとの便数のダッシュボード | Looker Studio は無料で手軽。Looker は LookML でモデルを一元管理する有料製品 |
| BigQuery ML（モデルの作成・評価・予測） | 🔜 第6週（#44、無料と確認できた場合だけ） | 日ごとの便数の時系列予測 | `CREATE MODEL` → `ML.EVALUATE` → `ML.PREDICT` / `ML.FORECAST` の流れ |
| Jupyter・Colab Enterprise、Looker・LookML | 📖 | — | 実行環境や製品が有料のため触らない |

## 3. パイプラインのオーケストレーション（約18%）

| 試験の項目 | 状態 | この基盤のどこ | 試験で問われる観点 |
|---|---|---|---|
| 定期実行（Cloud Scheduler） | ✅ | ADR 0004（5分ごとに取得を起動） | 単純な時刻起動は Cloud Scheduler。依存関係のある複数ステップは Composer や Workflows |
| リトライ・失敗の扱い | ✅ | `retry.py`、`collect.py`（指数バックオフ、429 で中止） | 一時的な失敗は待って再試行、恒久的な失敗はすぐ諦める |
| ログの確認（Cloud Logging） | ✅ / 🔜 第7週 | `cli.py`（1回の実行を JSON 1行で出す）。DTS のログは Cloud Logging に出る | 構造化ログ（JSON）にすると絞り込みや集計ができる |
| スケジュールされたクエリ | 🔜 第4週（#43） | 日次の件数チェック | SQL だけの定期処理ならこれで足りる。複雑になったら dbt や Dataform |
| 監視とアラート（Cloud Monitoring） | 🔜 第7週（#45） | DTS の失敗を通知 | — |
| 変換ツールの選択（Dataform・Dataflow・Dataproc・Data Fusion・Composer） | 📖 | dbt で代わりに体験（Dataform は Google 版の dbt） | SQL の変換は Dataform、ストリームや大規模処理は Dataflow、既存の Spark・Hadoop は Dataproc、ノーコードは Data Fusion |
| イベント駆動（Pub/Sub・Eventarc） | 📖 | — | 「ファイルが置かれたら処理する」は Eventarc や GCS の通知 → Pub/Sub |

## 4. データの管理（約25%）

| 試験の項目 | 状態 | この基盤のどこ | 試験で問われる観点 |
|---|---|---|---|
| IAM の最小権限（基本ロール・事前定義ロール・権限） | ✅ | ADR 0002（バケット単位の objectUser） | 基本ロール（オーナー・編集者・閲覧者）は広すぎる。事前定義ロールをリソース単位で付ける |
| 鍵を作らない認証 | ✅ | Workload Identity Federation（`docs/runbook/github-actions-wif.md`） | サービスアカウントの鍵ファイルは漏えいの危険がある。外部の実行環境からは WIF を使う |
| 期限が来たら自動で消す | 🔜 第3週・第10週 | BigQuery のパーティションの有効期限30日（ADR 0005）、GCS のライフサイクル | BigQuery はテーブルやパーティションの有効期限、GCS はライフサイクルのルール |
| GCS のストレージクラス | 🔜 第10週 | — | 読む頻度で選ぶ: Standard（よく読む）・Nearline（月1回）・Coldline（四半期に1回）・Archive（年1回） |
| GCS のアクセス制御（公開・非公開・均一なアクセス） | 📖 | — | 均一なバケットレベルのアクセスにすると、IAM だけで管理できる |
| 暗号化（CMEK・CSEK・Google 管理の鍵）、Cloud KMS | 📖 | — | 既定は Google 管理の鍵。鍵を自分で管理する必要があれば CMEK（Cloud KMS） |
| 可用性・災害対策、Analytics Hub | 📖 | — | — |

## 確認問題（触ったものから）

答えは各問の下の「答え」を開く。

**問1.** GCS に毎時置かれる JSON ファイルを、コードを書かずに BigQuery へ定期的に入れたい。最も適切なのは？
A. Storage Transfer Service　B. BigQuery Data Transfer Service　C. Dataflow　D. Transfer Appliance

<details><summary>答え</summary>

B。GCS → BigQuery の定期ロードは DTS。A はストレージ間のファイル移動、C はコードを書くパイプライン、D は物理的な機器での移行（ADR 0005）。
</details>

**問2.** GCS のファイルを BigQuery に入れる。追加の費用がかからない（共有スロットで動く）のは？
A. ストリーミング挿入（`tabledata.insertAll`）　B. GCS からのバッチロード　C. Dataflow のストリーミングジョブ　D. Cloud Data Fusion のパイプライン

<details><summary>答え</summary>

B。バッチロードは共有スロットで動くので無料。A は行数・容量で課金、C・D は処理のための計算資源に課金される。なお Storage Write API は毎月 2 TiB まで無料枠がある（ADR 0005 の背景、BigQuery の料金ページ）。
</details>

**問3.** GitHub Actions から GCS に書き込みたい。最も安全な認証方法は？
A. サービスアカウントの鍵を GitHub Secrets に置く　B. 個人アカウントのパスワードを使う　C. Workload Identity Federation　D. バケットを公開する

<details><summary>答え</summary>

C。鍵ファイルを作らずに、GitHub の OIDC トークンを GCP の短期の認証情報に交換する（`docs/runbook/github-actions-wif.md`）。
</details>

**問4.** 取得ジョブに、1つのバケットへの書き込みだけを許したい。最小権限に沿うのは？
A. プロジェクトの編集者　B. プロジェクトの Storage 管理者　C. 対象バケットの Storage オブジェクトユーザー　D. オーナー

<details><summary>答え</summary>

C。範囲（バケット単位）と権限（オブジェクトの読み書きだけ）の両方を絞る（ADR 0002）。
</details>

**問5.** BigQuery の生データを30日で自動的に消したい。最も手間が少ないのは？
A. 毎日 DELETE を流す　B. パーティションの有効期限を設定する　C. 毎月テーブルを作り直す　D. GCS のライフサイクルを設定する

<details><summary>答え</summary>

B。日付でパーティション分けしたテーブルに有効期限を付けると、古いパーティションが自動で消える。D は GCS のオブジェクト向け（ADR 0005）。
</details>
