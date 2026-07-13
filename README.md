# SodAI

SodAI は、独自LLMをチャット・評価・クレジット・将来のモデル公開へつなぐ、データ主権を重視したAIプラットフォームです。Next.js、Better Auth、FastAPI、PostgreSQL、Redis、独立GPU推論ワーカーを用いてセルフホストできます。

## アーキテクチャ

```text
Browser
  ├─ Next.js / Better Auth  ── PostgreSQL auth schema
  └─ FastAPI                ── PostgreSQL app schema / inference outbox
                                  │
                                  └─ Redis Streams ── Hina GPU worker

Internet ── Cloudflare Tunnel ── 自宅環境
                                      └─ SodAI GPU worker
```

認証プロバイダーのユーザーIDをサービス全体の主キーにせず、SodAI内部の不変UUIDと`(issuer, subject)`の対応として扱います。これによりBetter Authを自前運用しながら、将来Cognitoなどへ段階移行できます。詳細は[認証・アカウント境界](docs/architecture/authentication.md)を参照してください。

会話はHTTPで永続化し、Hina workerからの生成差分をWebSocketで配信します。匿名会話、再読込後の復元、イベント再送、モデル権限の境界は[会話・リアルタイム基盤](docs/architecture/conversations-realtime.md)、モデル成果物とGPU実行の境界は[推論基盤](docs/architecture/inference.md)にまとめています。

## ディレクトリ

```text
SodAI/
├── backend/                 # FastAPI、app schema、認証トークン検証
├── frontend/                # Next.js、Better Auth、auth schema
├── inference/               # HinaのGPU推論worker
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
cp frontend/.env.example frontend/.env.local
```

`frontend/.env.local`の`AUTH_DATABASE_URL`には`.env`の`AUTH_DATABASE_PASSWORD`と同じ値を、`backend/.env`の`DATABASE_URL`には`APP_DATABASE_PASSWORD`と同じ値を設定します。`BETTER_AUTH_SECRET`はこれらと別のランダム値にします。最後に両schemaのmigrationを適用します。

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

開発用overrideはPostgreSQLとRedisを`127.0.0.1`だけへ公開します。`compose.yaml`単体では両者をホストへ一切公開しません。

## 開発サーバー

別々のターミナルで起動します。

```bash
make dev-backend
make dev-frontend
make dev-inference
```

上のimport手順でpinned workerをすでに起動している場合、同じartifactのworkerを重ねて起動する
必要はありません。

- Frontend: <http://localhost:3000>
- API: <http://localhost:8000>
- OpenAPI UI: <http://localhost:8000/api/v1/docs>
- Mailpit（開発メール）: <http://localhost:8025>

## インフラ運用

```bash
make infra-ps
make infra-logs
make db-backup
make infra-down
```

`infra-down`はコンテナとネットワークだけを停止し、永続volumeを削除しません。バックアップ・復元、Cloudflare Tunnel、秘密情報のローテーションは[セルフホスト運用](docs/operations/self-hosting.md)にまとめています。

## 検証

```bash
make check
make infra-config
```

## 設計上の原則

- 認証情報、会話、クレジット、推論ログは自前PostgreSQLへ保存する
- Google、メール配送、Cloudflareは交換可能な外部接続先として扱う
- `auth`と`app`は別ロール・別schemaにし、所有権を分離する
- アプリデータをBetter Auth固有IDへ直接結合しない
- PostgreSQLとRedisを公開ホスト名やインターネットへ露出させない
- バックアップは暗号化して別ホストにも保持し、定期的に復元確認する
