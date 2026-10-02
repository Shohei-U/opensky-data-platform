# 0003. 取得は GitHub Actions で動かし、リポジトリを Public にする

- 日付: 2026-10-02
- ステータス: 承認
- 置き換え: ADR 0002 のうち「取得を Cloud Run Jobs で動かす」前提（権限の考え方は引き続き有効）

## 背景

#10 で取得を Cloud Run Jobs にデプロイしたところ、OpenSky に接続できず失敗した。

| 実行した場所 | `auth.opensky-network.org` | `opensky-network.org/api` | 結果 |
|---|---|---|---|
| 手元の Mac（自宅の回線） | 接続できる | 200 | 取得できる |
| Cloud Run Jobs（us-central1） | `ConnectTimeout`（2回とも） | — | 失敗 |
| Cloud Shell（GCP） | `000`（10秒で時間切れ） | `000` | 接続できない |
| GitHub Actions のランナー（ubuntu-latest、1回） | `404`（接続できる） | `200` | 接続できる |

OpenSky の README には "We may block AWS and other hyperscalers due to generalized abuse from these IPs." とある（https://github.com/openskynetwork/opensky-api）。GCP からの接続は遮断されていると判断した。

## 選択肢

| 選択肢 | 費用 | 24時間の取得 | 備考 |
|---|---|---|---|
| 手元の Mac（launchd） | 0円 | ✕ スリープ・持ち出し中は欠ける | |
| GitHub Actions（Private のまま） | 無料枠 2,000分/月に対し、必要な時間は約 43,000分/月 | — | 無料では足りない |
| **GitHub Actions（Public にする）** | 0円（標準ランナーは無制限） | ○ ただし schedule は遅れ・抜けがある | |
| VPS | 月500〜1,000円 | ○ | 接続できるかは未確認。月0円の方針から外れる |
| OpenSky に問い合わせ | 0円 | — | 返事の有無・時期が不明 |

## 決定

- 取得は GitHub Actions の `schedule`（5分ごと）で動かす
- そのためリポジトリを Public にする。会社のアカウント名や個人のメールアドレスを履歴に残さないため、整理した状態で新しいリポジトリに作り直し、旧リポジトリは Private で残す（Issue は移動する）
- GitHub Actions から GCS へは Workload Identity Federation で認証する（鍵ファイルを作らない）
- BigQuery へのロードと dbt の実行場所（GitHub Actions か Cloud Run Jobs か）は第3週で決める

## 理由

- 0円で24時間動く選択肢はこれだけ。Mac は欠けが大きく、VPS は費用がかかる
- Workload Identity Federation は鍵の漏えいリスクがなく、ADP の「データの管理」（IAM）の学習にもなる

## 影響・見直し条件

- #10 で作った Artifact Registry のイメージ、Cloud Run Job、Secret Manager のシークレット、サービスアカウントは残す（実行しなければ費用はほぼ0）。第3週以降のロードや dbt に使い回すか決める
- GitHub Actions のランナーも Azure 上で動くため、今後遮断される可能性がある。取得の失敗率をメタで監視し、増えたら選択肢を見直す
- schedule の遅れ・抜けで5分枠に欠けが出る。欠けの割合を第4週の freshness テストで測る
- Public のリポジトリでは、60日間動きがないと schedule が自動で止まる
