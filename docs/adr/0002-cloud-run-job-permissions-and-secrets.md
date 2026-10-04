# 0002. Cloud Run Job の GCS 権限と OpenSky 認証情報の渡し方

- 日付: 2026-10-02
- ステータス: 承認

## 要約

Cloud Run Job は専用のサービスアカウントで動かし、権限はバケット単位の objectUser だけ。OpenSky の認証情報は Secret Manager に置く。

## 背景

取得スクリプトを Cloud Run Jobs で5分ごとに動かす（#10・#11）。ジョブは専用のサービスアカウントで動き、次の2つが必要になる。

- GCS（`gs://opensky-data-platform-raw`）に raw / meta を書く。同じ5分枠をやり直したときは同じオブジェクトを上書きする設計（#9）
- OpenSky の OAuth2 クライアント（`clientId` / `clientSecret`）を受け取る

## 選択肢

### GCS の権限

| 選択肢 | できること | 上書き |
|---|---|---|
| バケット単位で `roles/storage.objectUser` | 作成・上書き・読み取り・一覧・削除（このバケットだけ） | できる |
| バケット単位で `roles/storage.objectCreator` | 作成のみ | できない（やり直しは失敗する） |
| プロジェクト単位のロール | 全バケットに及ぶ | できる |

### 認証情報

| 選択肢 | Secret Manager へのアクセス（月 8,640 回実行） | 無料枠（月 1 万アクセス） |
|---|---|---|
| JSON 1つのシークレットをファイルとしてマウント | 約 8,640 回 | 収まる |
| ID と Secret を別々のシークレットにして環境変数で渡す | 約 17,280 回 | 超える |
| 環境変数に平文で設定 | 0 回 | — （Console やジョブ定義に値が見える） |

無料枠の数値（月 1 万アクセス、有効なバージョン 6 個）はエージェントの知識による値で、未確認。https://cloud.google.com/free の Secret Manager の欄で確かめる。

## 決定

- サービスアカウント `opensky-ingest@opensky-data-platform.iam.gserviceaccount.com` に、`opensky-data-platform-raw` バケット単位で `roles/storage.objectUser` を付ける。プロジェクト単位のロールは付けない
- 認証情報は `credentials.json` を丸ごと1つのシークレット `opensky-credentials` に入れ、ジョブには `/secrets/opensky/credentials.json` としてマウントする。サービスアカウントにはこのシークレットだけに `roles/secretmanager.secretAccessor` を付ける

## 理由

- 上書きによる冪等性（#9）を保つには、作成に加えて削除の権限が要る。範囲をバケット1つに絞れば、漏れたときの影響もこのバケットに限られる
- 1つのシークレットにすると無料枠に収まり、既存の `load_credentials()` が JSON をそのまま読める

## 影響・見直し条件

- 第8週の Terraform 化で、同じ権限をコードに置き換える
- 取得間隔を短くしてアクセス数が月 1 万回を超えそうなら、シークレットの読み方を見直す
- Secret Manager の無料枠（有効なシークレットのバージョン 6 個まで）を超えないよう、古いバージョンは無効化する
