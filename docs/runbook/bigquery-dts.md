# BigQuery のテーブルと DTS の転送を作る（ADR 0005・0006）

```
GCS  raw/dt=<日付>/*   ──DTS「opensky-states」 毎時30分・MIRROR──▶  opensky_raw.states$<日付>
GCS  meta/dt=<日付>/*  ──DTS「opensky-fetch-meta」毎時30分・MIRROR──▶ opensky_raw.fetch_meta$<日付>
```

- データセット `opensky_raw`（us-central1）、テーブル `states` と `fetch_meta`
- テーブルは日付でパーティション分け（取り込み時刻のパーティション）。パーティションは30日で自動的に消える
- クエリには日付の絞り込み（`WHERE _PARTITIONDATE = ...`）が必須。付け忘れて全期間を読むことを防ぐ
- スキーマは `bigquery/schema/*.json`。取得のコード（`ingestion/src/opensky_ingest/fetch.py` の `STATE_FIELDS`）と同じ順

## 1. データセットとテーブルを作る（本人、ターミナル）

```bash
bash scripts/gcp/setup-bigquery.sh
```

| 手順 | やること |
|---|---|
| 1/3 | BigQuery と Data Transfer Service の API を有効にする |
| 2/3 | データセット `opensky_raw` を us-central1 に作る（あれば飛ばす） |
| 3/3 | テーブル `states`・`fetch_meta` を作る。日ごとのパーティション、有効期限30日、日付の絞り込み必須 |

最後にテーブルの一覧が出れば成功。

## 2. DTS の転送を2つ作る（本人、Cloud Console）

`bq` コマンドでは Cloud Storage の転送の実行スケジュールを設定できないため、画面で作る。

**BigQuery** → 左のメニュー **データ転送** → **転送を作成**

| 項目 | states 用 | fetch_meta 用 |
|---|---|---|
| ソース | Google Cloud Storage | 同じ |
| 転送構成名 | `opensky-states` | `opensky-fetch-meta` |
| スケジュール オプション | 繰り返しの頻度「時間」、1時間ごと。開始時刻は次の「毎時30分」（例: 日本時間 13:30 ＝ UTC 04:30） | 同じ |
| データセット | `opensky_raw` | 同じ |
| 宛先テーブル | `states${run_time-1h\|"%Y%m%d"}` | `fetch_meta${run_time-1h\|"%Y%m%d"}` |
| Cloud Storage の URI | `opensky-data-platform-raw/raw/dt={run_time-1h\|"%Y-%m-%d"}/*` | `opensky-data-platform-raw/meta/dt={run_time-1h\|"%Y-%m-%d"}/*` |
| 書き込み設定 | **MIRROR** | 同じ |
| ファイル形式 | JSON | 同じ |
| 許可されている不良レコード数 | 0 | 同じ |
| サービス アカウント | 空欄（自分のアカウントで実行する） | 同じ |
| 通知オプション | **メール通知**を ON（失敗したらメールが来る。無料） | 同じ |

※ 表の `\|` は `|`（縦棒）。画面には `states${run_time-1h|"%Y%m%d"}` のように入れる。

**保存**を押すと、権限の確認画面が出たら個人アカウントで許可する。

### 値の意味

- `{run_time-1h|"%Y-%m-%d"}`: 実行予定時刻の1時間前の日付。0時30分の実行は前日のフォルダを見るので、23時台のファイル（23時56分ごろに書かれる）を取りこぼさない
- `$` の後ろの日付: その日のパーティションだけを入れ直す（パーティション デコレータ）
- MIRROR: 指定したパーティションを、フォルダの全ファイルで丸ごと置き換える。同じ枠を上書きしても重複しない

## 3. 確かめる

転送の詳細画面で **今すぐ転送を実行** → **1回限りの転送** を押す。数分後に実行履歴が「成功」になったら、BigQuery の **クエリ** で次を実行する。

```sql
-- 今日入った行数と時刻の範囲（日付の絞り込みが必須）
SELECT COUNT(*) AS rows, MIN(fetched_at) AS first, MAX(fetched_at) AS last
FROM `opensky-data-platform.opensky_raw.states`
WHERE _PARTITIONDATE = CURRENT_DATE();

-- 取得の失敗の数（meta）
SELECT COUNT(*) AS fetches, COUNTIF(error IS NOT NULL) AS failed
FROM `opensky-data-platform.opensky_raw.fetch_meta`
WHERE _PARTITIONDATE = CURRENT_DATE();
```

クエリを流す前に、エディタの右上に出る「このクエリを実行すると ○ MB が処理されます」を見る。1日分なら数十 MB で、月 1 TiB の無料枠に対して十分小さい。

## 費用（ADR 0006）

| もの | 量 | 無料枠 |
|---|---|---|
| DTS の転送・ロード | 1日48回 | 無料 |
| BigQuery の保存 | 30日分で約0.4GB | 10GiB |
| GCS の一覧（Class A） | 月約1,500回 | 書き込みと合わせて 5,000回 |
| GCS の読み取り（Class B） | 月約1.8万回 | 5万回 |

## 止める・直す

- 止める: 転送の詳細画面 → **転送を無効にする**
- 前日分の入れ直し（23時台が遅れて入らなかったとき）: 転送の詳細画面 → **今すぐ転送を実行** → **期間を指定した転送（バックフィル）** で前日の日付を選ぶ
