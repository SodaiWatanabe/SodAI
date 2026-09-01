# SodAI

SodAI は、独自LLMをチャット・評価・クレジット・将来のモデル公開へつなぐ、データ主権を重視したAIプラットフォームです。Next.js、Hono上のBetter Auth、FastAPI、PostgreSQL、Redis、独立GPU推論ワーカーを用いてセルフホストできます。

## アーキテクチャ

```text
Browser
  ├─ Next.js ── /api/auth/* ── Hono / Better Auth ── PostgreSQL auth schema
  └─ FastAPI ─────────────────────────────────────── PostgreSQL app schema / inference outbox
                                                             │
                                                             └─ Redis Streams ── Hina / Asuka 1.1 GPU workers

Internet ── Cloudflare Tunnel ── 自宅環境
                                      └─ SodAI GPU worker
```

本番アプリのcanonical originは`https://app.sodai.me`です。`sodai.me`は将来の
apexサイト用に予約し、認証のissuer、audience、Cookie、ブラウザAPIは
`app.sodai.me`へ統一します。

認証プロバイダーのユーザーIDをサービス全体の主キーにせず、SodAI内部の不変UUIDと`(issuer, subject)`の対応として扱います。これによりBetter Authを自前運用しながら、将来Cognitoなどへ段階移行できます。詳細は[認証・アカウント境界](docs/architecture/authentication.md)を参照してください。

作業文脈はSpaceとThreadとしてHTTPで永続化し、Hina／Asukaの生成差分をWebSocketで配信します。匿名利用、再読込後の復元、イベント再同期、応答主体の権限境界は[Space・Thread・リアルタイム基盤](docs/architecture/spaces-threads-realtime.md)、モデル成果物とGPU実行の境界は[推論基盤](docs/architecture/inference.md)にまとめています。複式簿記、期限付きLot、推論予約、将来の購入・報酬との接続は[クレジット基盤](docs/architecture/credits.md)を参照してください。

## ディレクトリ

```text
SodAI/
├── backend/                 # FastAPI、app schema、認証トークン検証
├── auth/                    # Hono、Better Auth、auth schema、認証メール
├── frontend/                # Next.js、UI、Auth/APIクライアント
├── inference/               # Hina／Asuka 1.1のモデル別GPU推論worker
├── packages/contracts/      # APIとworkerのversioned内部契約
├── var/models/              # Git管理外のimmutableモデル成果物
├── infra/
│   └── postgres/            # 初期権限、バックアップ、復元
├── docs/
│   ├── architecture/        # 境界と移行方針
│   └── operations/          # セルフホスト運用手順
├── compose.yaml             # 非公開データネットワーク（本番の基準）
└── compose.dev.yaml         # localhost限定の開発用ポート公開
```

## 必要環境

- Docker Engine + Docker Compose
- Python 3.10以上
- Node.js 20.9以上

## 開発セットアップ

```bash
cp .env.example .env
```

`.env`内の`change-me-*`を、それぞれ異なる十分に長いランダム値へ変更します。例えば、値は次のコマンドで生成できます。

```bash
openssl rand -hex 32
```

設定後、秘密ファイルを所有者だけが読めるようにします。`make infra-config`はサンプル値、24文字未満の値、秘密値の使い回しを拒否します。

```bash
chmod 600 .env
```

続いてインフラとアプリ依存関係を準備します。

```bash
make infra-config
make infra-up
make install
cp backend/.env.example backend/.env
cp auth/.env.example auth/.env
cp frontend/.env.example frontend/.env.local
```

`auth/.env`の`AUTH_DATABASE_URL`には`.env`の`AUTH_DATABASE_PASSWORD`と同じ値を、`backend/.env`の`DATABASE_URL`には`APP_DATABASE_PASSWORD`と同じ値を設定します。`BETTER_AUTH_SECRET`はこれらと別のランダム値にします。最後に両schemaのmigrationを適用します。

```bash
make migrate
```

HinaをBuilding-SLMのv1 SFT成果物から取り込みます。

```bash
make import-hina \
  CHECKPOINT=../Building-SLM/checkpoints/v1/gpt_sft.pt \
  TOKENIZER=../Building-SLM/tokenizer \
  SOURCE_REPOSITORY=../Building-SLM
# 別ターミナルで、importが表示したartifactを固定してworkerを先に起動
make dev-inference HINA_ARTIFACT_ID=<artifact-id>
# worker ready後に、新規runの向き先を原子的に切り替える
make deploy-hina ARTIFACT_ID=<importで表示されたartifact-id>
```

初回導入でも更新時でも、`deploy-hina`より先に対象artifactのworkerを起動します。promotion後は
そのpinned workerを動かし続けて構いません。次回起動からは`HINA_ARTIFACT_ID`を省略できます。

Asuka 1.1はBuilding-SLM v2のSFT成果物からAsuka runtime artifactとして取り込み、
Hinaとは別workerで起動します。

```bash
make import-asuka1 \
  CHECKPOINT=../Building-SLM/checkpoints/v2/gpt_sft.pt \
  TOKENIZER=../Building-SLM/tokenizer \
  SOURCE_REPOSITORY=../Building-SLM
make dev-inference MODEL=asuka-1 DEPLOYMENT=asuka-1.1 ARTIFACT_ID=<artifact-id> DEVICE=cuda:0
make deploy-asuka11 ARTIFACT_ID=<artifact-id>
```

開発用overrideはPostgreSQLとRedisを`127.0.0.1`だけへ公開します。`compose.yaml`単体では両者をホストへ一切公開しません。

## 開発サーバー

別々のターミナルで起動します。

```bash
make dev-auth
make dev-backend
make dev-frontend
make dev-inference
```

上のimport手順でpinned workerをすでに起動している場合、同じartifactのworkerを重ねて起動する
必要はありません。

- Frontend: <http://localhost:13200>
- Auth liveness（内部待受）: <http://127.0.0.1:13201/healthz>
- Auth readiness（内部待受）: <http://127.0.0.1:13201/readyz>
- API: <http://localhost:13202>
- OpenAPI UI: <http://localhost:13202/api/v1/docs>
- PostgreSQL（localhost限定）: `127.0.0.1:13203`
- Redis（localhost限定）: `127.0.0.1:13204`
- Mailpit SMTP: `127.0.0.1:13205`
- Mailpit UI: <http://localhost:13206>

ローカル開発では`13200`から`13209`までをSodAI専用として扱います。Compose project、
volume、networkも`sodai-*`で固定されており、同じホスト上の別プラットフォームとは共有しません。

## インフラ運用

```bash
make infra-ps
make infra-logs
make db-backup
make infra-down
```

`infra-down`はコンテナとネットワークだけを停止し、永続volumeを削除しません。バックアップ・復元、Cloudflare Tunnel、秘密情報のローテーションは[セルフホスト運用](docs/operations/self-hosting.md)にまとめています。`app.sodai.me`向けのURL、環境変数、Tunnel経路は[本番環境契約](docs/operations/production-environment.md)を参照してください。

## 検証

```bash
make check
make infra-config
# 実PostgreSQLで台帳不変条件とmigration往復を検証
make test-integration
# local CUDA上で実Hinaを含む隔離E2E
make test-inference-e2e
# 公開しない詳細な推論運用状態
make inference-status
```

## 設計上の原則

- 認証情報、会話、クレジット、推論ログは自前PostgreSQLへ保存する
- Google、メール配送、Cloudflareは交換可能な外部接続先として扱う
- `auth`と`app`は別ロール・別schemaにし、所有権を分離する
- アプリデータをBetter Auth固有IDへ直接結合しない
- PostgreSQLとRedisを公開ホスト名やインターネットへ露出させない
- バックアップは暗号化して別ホストにも保持し、定期的に復元確認する
