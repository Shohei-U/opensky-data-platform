# GitHub Actions から GCS に書く設定（Workload Identity Federation, #29）

ADR 0003 で、取得を GitHub Actions で動かすことにした。鍵ファイル（サービスアカウントの JSON キー）は作らず、GitHub が発行する ID トークンを GCP の一時的な認証情報に交換する。

```
GitHub Actions のジョブ
  │ ① GitHub が署名した ID トークン（repository_id・ref などが入っている）
  ▼
STS（Security Token Service）── プール github / プロバイダ opensky-repo
  │ ② 条件を確かめる: repository_id == 1401906814 かつ ref == refs/heads/main
  │ ③ 合えば、短命の連携トークンを返す
  ▼
IAM Credentials ── サービスアカウント opensky-ingest になりすます（workloadIdentityUser）
  │ ④ 1時間ほどで失効するアクセストークン
  ▼
GCS（バケット opensky-data-platform-raw に objectUser）
```

## 実行

本人が、リポジトリのルートで1回だけ実行する（gcloud は個人用の構成）。

```bash
bash scripts/gcp/setup-github-wif.sh
```

| 手順 | やること | なぜ |
|---|---|---|
| 1 | IAM・IAM Credentials・STS の API を有効にする | トークンの交換とサービスアカウントのなりすましに使う。有効にするだけでは課金されない |
| 2 | プール `github` を作る | 外部の ID（GitHub）をまとめて受け入れる入れ物 |
| 3 | プロバイダ `opensky-repo` を作る | GitHub のトークンを信用する設定。**このリポジトリの main からだけ**受け入れる条件を付ける |
| 4 | サービスアカウント `opensky-ingest` に `workloadIdentityUser` を付ける | このリポジトリのワークフローだけが、このアカウントとして動ける |

## 判断のメモ

- 条件は名前（`Shohei-U/opensky-data-platform`）ではなく **repository_id** で書く。名前は変えられる（実際に旧リポジトリの名前を変えた）ので、同じ名前のリポジトリを別に作られても通らないようにする
- `ref == refs/heads/main` で、PR やほかのブランチからは GCS に書けないようにする（Public リポジトリなので、他人の PR から書かれるのを防ぐ）
- サービスアカウントは Cloud Run Job 用に作った `opensky-ingest` を使い回す。権限はバケット単位の objectUser だけ（ADR 0002）
- プール・プロバイダ・IAM の利用は無料

## 確認

```bash
gcloud iam workload-identity-pools providers describe opensky-repo \
  --location=global --workload-identity-pool=github --format='value(state,attributeCondition)'
gcloud iam service-accounts get-iam-policy opensky-ingest@opensky-data-platform.iam.gserviceaccount.com
```

実際に書けるかは、#30 のワークフローを main で手動実行して確かめる。
