# セルフホスト運用

## 構成ファイル

- `compose.yaml`: 本番の基準。PostgreSQLとRedisは`internal` networkだけに所属し、ホストポートを公開しない
- `compose.dev.yaml`: 開発用。データポートとMailpitを`127.0.0.1`だけへ公開する
- `.env`: Compose用の秘密値。Git管理しない
- `infra/postgres/init/`: 新規volumeを初期化するときだけ実行されるDB境界設定

## 初回起動

```bash
cp .env.example .env
openssl rand -hex 32
```

生成を4回行い、`.env`の次の値へ別々に設定します。

- `POSTGRES_ADMIN_PASSWORD`
- `AUTH_DATABASE_PASSWORD`
- `APP_DATABASE_PASSWORD`
- `REDIS_PASSWORD`

```bash
chmod 600 .env
```

起動前検査はサンプル値、短すぎる値、4項目間の使い回しを拒否します。

アプリケーション用の`frontend/.env.local`と`backend/.env`もGit管理外です。`BETTER_AUTH_SECRET`、Google OAuth secret、SMTP password、DB接続URLはpassword managerなどへ別途保管し、ファイルを`chmod 600`にします。特に`BETTER_AUTH_SECRET`はDB内のJWT署名鍵を復号するため、PostgreSQL dumpとは別の安全な場所にも保持します。

設定を検査して、開発構成を起動します。

```bash
make infra-config
make infra-up
make infra-ps
```

アプリ側の接続URLへ同じロール別パスワードを設定した後、DB定義を適用します。

```bash
make migrate
```

このコマンドはBetter Authの定義を`auth`schemaへ、Alembicの定義を`app`schemaへ適用します。

開発用の確認メールはSMTP `127.0.0.1:1025`へ送信し、<http://127.0.0.1:8025>で確認できます。Next.jsをホストで動かす場合の設定は次の通りです。

```dotenv
AUTH_EMAIL_DELIVERY=smtp
AUTH_SMTP_HOST=127.0.0.1
AUTH_SMTP_PORT=1025
AUTH_SMTP_SECURE=false
AUTH_EMAIL_FROM="SodAI <no-reply@sodai.local>"
```

MailpitではSMTPユーザー名とパスワードを設定しません。Next.jsもコンテナ化する場合は`AUTH_SMTP_HOST=mailpit`へ変更します。Mailpitは開発overrideにだけ存在し、メールはコンテナの一時領域へ保持されます。本番のメール配送には使用しません。

開発構成でも公開先は`127.0.0.1`です。LANへ公開する目的で`POSTGRES_BIND_ADDRESS`や`REDIS_BIND_ADDRESS`を変更しないでください。本番でアプリケーションもコンテナ化した場合は、データポートを公開しない次の構成を使います。

```bash
make infra-up-internal
```

## 初期化と秘密情報の変更

`docker-entrypoint-initdb.d`は空のPostgreSQL volumeに対して一度だけ動作します。そのため、既存volumeがある状態で`.env`のDBパスワードだけを書き換えても、DBロールのパスワードは変わりません。

パスワードをローテーションするときは、管理者接続で`ALTER ROLE`を実行し、アプリケーションの秘密値を更新してから接続を再起動します。管理者パスワードもDB内と`.env`の双方を揃えます。実施前に必ずバックアップを作成してください。

## バックアップ

```bash
make db-backup
```

`backups/postgres/sodai-<UTC timestamp>.dump`とSHA-256ファイルを作成します。出力はGit管理外で、ディレクトリは所有者だけが読める権限になります。dumpには認証情報、メールアドレス、会話などの機密データが含まれるため、次を守ります。

- raw dumpをクラウドストレージへ直接アップロードしない
- `age`、`restic`などで暗号化してから別ホストへ複製する
- 暗号鍵をdumpと同じ機器だけに置かない
- 世代保持と削除期限を決める
- 定期的に隔離環境へ復元して、取得だけでなく復旧可能性を確認する

Docker volume自体はアプリケーションレベルでは暗号化されません。自宅ホストではLUKSなどのディスク暗号化、適切なファイル権限、OS更新、物理アクセス制御を別途適用します。

RedisはAOFで再起動時の状態を保持しますが、アカウント、クレジット、会話の正本にはしません。Redis喪失時に未完了ジョブを失敗・再試行として扱えるようにし、主権データの復旧はPostgreSQLを基準にします。

このdumpはデータベース内容と所有者名を保持しますが、ロール自体は含みません。復旧先では先に通常の初期化を行い、`sodai_auth`と`sodai_app`を作成してから復元します。

## 復元

復元は現在のデータベース内容を置き換えます。書き込みを行うNext.js、FastAPI、workerを停止し、対象ファイルを確認してから実行します。

```bash
make db-restore BACKUP=/absolute/path/to/sodai-20260101T000000Z.dump
```

確認文字列`restore sodai`の入力が必要です。同じ場所に`.sha256`があれば復元前に整合性を検査します。復元後は次を確認します。

1. Better Authで既存ユーザーがログインできる
2. FastAPIが同じ内部ユーザーUUIDを解決できる
3. `sodai_auth`から`app`schema、`sodai_app`から`auth`schemaへアクセスできない
4. セッション失効方針とメール認証フローが期待通りである

## Cloudflare Tunnel

Cloudflare Tunnelは任意profileとして分離されています。Cloudflareでremotely-managed tunnelを作成し、tokenだけを`.env`へ設定します。

```dotenv
CLOUDFLARE_TUNNEL_TOKEN=<secret tunnel token>
```

```bash
make tunnel-up
```

公開hostnameのoriginはCloudflare側で設定します。コンテナ本番構成では、Next.jsとFastAPIを`sodai-edge` networkへ接続し、それぞれサービス名（例: `http://frontend:3000`、`http://backend:8000`）をoriginにします。PostgreSQLやRedisを公開hostnameへ登録してはいけません。

現在のようにアプリをホストプロセスとして起動する開発時は、ホストへインストールした`cloudflared`から`127.0.0.1`へ接続する方が安全です。Compose内のTunnelからホストへ接続するためにアプリを`0.0.0.0`へ無制限公開する運用は避けます。

Tunnel tokenが漏えいした場合はCloudflare側で直ちにrotate/revokeし、`.env`を更新します。tokenをログ、issue、バックアップdumpへ混入させないでください。

## PostgreSQL volumeを削除するとき

通常の`make infra-down`はvolumeを保持します。volume削除はすべてのDBデータを失う破壊的操作です。削除が必要な場合は、暗号化済みバックアップと復元試験を確認した上で、対象volume名`sodai-postgres-data`を明示して別途実行してください。
