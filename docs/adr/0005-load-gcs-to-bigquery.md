# 0005. GCS から BigQuery へのロード方法と実行場所

- 日付: 2026-10-04
- ステータス: 承認（書き込みの設定 APPEND と転送元のパスは ADR 0006 で置き換え）

## 要約

GCS のデータは Data Transfer Service が1時間ごとに BigQuery へ入れる。BigQuery の raw は30日で消し、元のデータは GCS に残す。

## 背景

第2週で `gs://opensky-data-platform-raw` に5分ごとに2つのファイルが貯まるようになった（ADR 0003・0004）。

- `raw/dt=YYYY-MM-DD/hh=HH/<YYYYMMDDTHHMMZ>.jsonl.gz`: state vector（1行 = 1機の1時点）
- `meta/dt=YYYY-MM-DD/hh=HH/<YYYYMMDDTHHMMZ>.jsonl`: 取得1回ごとの記録（状態コード・行数・残りクレジット）

第3週はこれを BigQuery で見えるようにする。ADR 0003 で「BigQuery へのロードと dbt の実行場所は第3週で決める」としていた。

### データ量（2026-10-04 に GCS を読んで実測）

| 項目 | 実測 | 1日（288回）に換算 | 1か月に換算 |
|---|---|---|---|
| raw のファイル | 40個で 130 KB（gzip） | 約 0.9 MB | 約 28 MB |
| raw の行数・元の大きさ | 直近5回で 481行・221 KB（1回あたり約96行・44 KB） | 約 2.8万行・約 13 MB | 約 83万行・約 380 MB |
| meta のファイル | 40個で 174 KB | 約 1.3 MB | 約 38 MB |

直近5回は UTC 12時台（日本時間の夜）で、便が多い時間帯。1日の平均はこれより少ない見込み。BigQuery の無料ストレージ 10 GiB に対して、1年分を残しても 5 GB 未満。

### 料金・仕様（公式ドキュメント、2026-10-04 に確認）

- バッチロード（ロードジョブ）は無料。共有スロット `default-pipeline` を使う
- ストレージは毎月 10 GiB まで無料、クエリは毎月 1 TiB まで無料
- ストリーミング挿入（Storage Write API の REST）は $0.01 / 200 MiB で有料 → 今回の選択肢から外す
- Data Transfer Service（DTS）の Cloud Storage 転送は無料。実行の最短間隔は15分（既定は24時間）
- DTS の APPEND は「前回の成功以降に更新された（`updated` が新しい）ファイル」だけを読む。MIRROR は毎回すべてのファイルで上書きする
- DTS では、ワイルドカードに当たるすべてのファイルが転送先テーブルと同じスキーマでなければ失敗する

出典:
- https://cloud.google.com/bigquery/pricing
- https://cloud.google.com/bigquery/docs/cloud-storage-transfer-overview
- https://cloud.google.com/bigquery/docs/cloud-storage-transfer

### 前提になる作り

- 同じ5分枠をやり直すと、同じオブジェクトを上書きする（`cli.py` の `object_path`）。上書きで `updated` が変わるため、どの方法でも「同じ枠が2回入る」可能性がある → dbt の staging で `(icao24, time_position または api_time)` などで重複を取り除く前提にする
- BigQuery は OpenSky に接続しないため、GCP の IP が遮断されていても GCP の中で動かせる（ADR 0003 の制約は取得だけにかかる）

## 選択肢

| 選択肢 | 動く場所 | 費用 | BigQuery に入るまで | 良い点 | 気になる点 |
|---|---|---|---|---|---|
| **A. DTS の Cloud Storage 転送（APPEND）** | GCP（マネージド） | 0円 | 間隔による（最短15分） | コードを書かない。取得（GitHub Actions）と切り離せる。ADP の DTS を実物で使える | 実行のたびにバケットを一覧する（GCS の操作回数）。raw と meta で転送設定が2つ |
| B. 取得の直後に GitHub Actions からロードジョブ | GitHub Actions | 0円（1日288ジョブ。上限はテーブルごとに1日1,500） | 約5分 | ほぼリアルタイム。今書いたファイルだけを読むので一覧が不要 | 5分間隔に対する余裕（約20秒）がさらに減る。`opensky-ingest` に BigQuery の権限が要る。Actions が止まるとロードも止まる |
| C. 外部テーブル（hive パーティション）を dbt が直接読む | なし（クエリのときに読む） | 0円 | すぐ | BigQuery に生データを置かない（「生データを長期保持しない」の方針に最も合う） | クエリのたびに GCS のファイルを読む。`dt` で絞り忘れると全ファイルを読み、GCS の読み取り回数を使う |
| D. Cloud Run Job（#10 で作ったもの）を Cloud Scheduler から起動してロード | GCP | 0円（無料枠内） | 間隔による | 第2週の資産を使い回せる | ロード用のコードとイメージを保守する。Cloud Scheduler の無料枠（3ジョブ）を1つ使う |

## 決定

- BigQuery Data Transfer Service の Cloud Storage 転送で入れる。書き込みは APPEND（前回以降に更新されたファイルだけ）
- 転送設定は2つ: `raw/` → raw の state vector のテーブル、`meta/` → 取得記録のテーブル。どちらも us-central1
- 間隔は1時間ごと
- raw のテーブルは日付でパーティション分けし、パーティションの有効期限を30日にする。正本は GCS に残す
- データセット名・テーブル名・スキーマ（state vector 17項目＋`api_time`・`fetched_at`）は実装の Issue で決める

## 理由

- 見せる先は Looker Studio のダッシュボード（第6週）で、数分の鮮度は要らない。1時間で足りる
- コードも新しいイメージも増えない。取得の場所（GitHub Actions）が規約や遮断で変わっても、ロードは影響を受けない
- 生データの正本は GCS にあるので、BigQuery 側は30日で消してよい（AGENTS の「BigQuery に生データを長期保持しない」）。消した後でも GCS から入れ直せる
- 外部テーブル（C）は BigQuery にデータを置かない点で魅力があるが、クエリのたびに GCS を読む。dbt の実行や試しのクエリが増えると GCS の読み取り回数が読みにくくなるため外した

## 影響・見直し条件

- 同じ5分枠をやり直すとファイルが上書きされ、APPEND でもう一度入る。重複は dbt の staging で取り除く（第4週）
- DTS は実行のたびにバケットを一覧する（1時間ごとに2設定で月約1,440回）。GCS の操作回数の無料枠（Class A・Class B の月の回数）は未確認。取得の書き込み（月約1.7万回）と合わせて確かめる
- 転送先のスキーマとファイルのスキーマがずれると、転送が失敗する。取得側で項目を変えるときは、先に BigQuery のテーブルのスキーマを変える
- 鮮度が足りなくなったら間隔を短くする（最短15分）。それでも足りなければ B（取得の直後にロード）を見直す
- DTS の転送を動かすサービスアカウントと権限（バケットの読み取り・BigQuery への書き込み）は実装の Issue で決め、手順を `docs/runbook/` に書く
