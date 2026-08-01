# セルフホスト運用

## 構成ファイル

- `compose.yaml`: 本番の基準。PostgreSQLとRedisは`internal` networkだけに所属し、ホストポートを公開しない
- `compose.dev.yaml`: 開発用。データポートとMailpitを`127.0.0.1`だけへ公開する
- `.env`: Compose用の秘密値。Git管理しない
- `auth/.env`: Better Auth、認証DB、OAuth、SMTP用の秘密値。Git管理しない
- `frontend/.env.local`: Auth/FastAPIの内部到達URL。認証秘密値は置かない
- `infra/postgres/init/`: 新規volumeを初期化するときだけ実行されるDB境界設定

## 初回起動

```bash
cp .env.example .env
cp auth/.env.example auth/.env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
openssl rand -hex 32
```

生成を4回行い、`.env`の次の値へ別々に設定します。

- `POSTGRES_ADMIN_PASSWORD`
- `AUTH_DATABASE_PASSWORD`
- `APP_DATABASE_PASSWORD`
- `REDIS_PASSWORD`

```bash
chmod 600 .env auth/.env backend/.env frontend/.env.local
```

起動前検査はサンプル値、短すぎる値、4項目間の使い回しを拒否します。

アプリケーション用の`auth/.env`、`frontend/.env.local`、`backend/.env`もGit管理外です。`BETTER_AUTH_SECRET`、Google OAuth secret、SMTP password、DB接続URLはpassword managerなどへ別途保管し、ファイルを`chmod 600`にします。これらの秘密値は`auth/.env`だけに置き、Next.jsへ渡しません。特に`BETTER_AUTH_SECRET`はDB内のJWT署名鍵を復号するため、PostgreSQL dumpとは別の安全な場所にも保持します。

本番の認証レート制限へ利用者IPを渡す場合は、公開originへの直接アクセスを閉じ、信頼済みgatewayが上書きするヘッダー名だけを`auth/.env`の`AUTH_TRUSTED_CLIENT_IP_HEADER`へ設定します。Cloudflare専用originなら`cf-connecting-ip`、自前proxyなら受信値を破棄して再生成する`x-forwarded-for`などを使用します。

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

このコマンドはAuthサービスからBetter Authの定義を`auth`schemaへ、Alembicの定義を`app`schemaへ適用します。

## アプリケーションの更新

認証を含む更新は、Auth、FastAPI、Frontendの順に起動します。Authは`/healthz`ではなく、DB接続も確認する`/readyz`が200になってから後続へ進みます。Frontendの`AUTH_SERVICE_URL`は実行時に評価されるため、ビルド時と起動時で同じ値を焼き込む必要はありません。

Next.js内蔵のBetter Authから初めて分離するときは、既存の`AUTH_DATABASE_URL`、`BETTER_AUTH_SECRET`、`BETTER_AUTH_URL`を値を変えずに`frontend/.env.local`から`auth/.env`へ移します。特に`BETTER_AUTH_SECRET`を再生成すると、既存session Cookieが無効になり、DB内のJWT署名鍵も従来の秘密値で復号できなくなります。Google OAuthとSMTPの設定もAuthへ移し、移行完了後はNext.js側から認証秘密値を削除します。

切り替え前に、Honoの`/readyz`、既存Cookieを付けた`/api/auth/get-session`と`/api/auth/token`、Next.js経由の同じ2 endpointを順に確認します。Googleを利用する環境ではcallback、メール認証ではOTP送信・検証・sign-outも確認してからトラフィックを切り替えます。応答ヘッダーに既存の`sodai` Cookieが保たれることも確認します。

rollback時は、DB migrationに後方互換性がある範囲でFrontend、FastAPI、Authの順に旧版へ戻します。認証schemaを戻す必要がある変更では、先に書き込みを止め、取得済みのPostgreSQL backupから復元します。`BETTER_AUTH_URL`はJWT issuer / audienceであり、内部配置の変更では書き換えません。

### app schemaを再初期化するとき

Platform core baselineは後方互換migrationを持ちません。開発中の旧Conversation schemaから
Space・Thread基盤へ切り替える場合は、必要なデータを先にバックアップし、FastAPIと推論workerを
停止してから`app`schemaだけを明示的に再初期化します。`auth`schemaは保持されますが、SodAI内部の
ユーザー対応、Space、Thread、Entry、実行履歴はすべて削除されます。

```bash
make db-backup
CONFIRM_REINITIALIZE_APP_SCHEMA=1 make reinitialize-app-schema
```

通常の起動や更新でこのtargetを使ってはいけません。確認変数がない実行は拒否されます。

開発用の確認メールはSMTP `127.0.0.1:13205`へ送信し、<http://127.0.0.1:13206>で確認できます。Authサービスをホストで動かす場合の設定は次の通りです。

```dotenv
AUTH_EMAIL_DELIVERY=smtp
AUTH_SMTP_HOST=127.0.0.1
AUTH_SMTP_PORT=13205
AUTH_SMTP_SECURE=false
AUTH_EMAIL_FROM="SodAI <no-reply@sodai.local>"
```

MailpitではSMTPユーザー名とパスワードを設定しません。Authサービスをコンテナ化する場合は`AUTH_SMTP_HOST=mailpit`へ変更します。Mailpitは開発overrideにだけ存在し、メールはコンテナの一時領域へ保持されます。本番のメール配送には使用しません。

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

復元は現在のデータベース内容を置き換えます。書き込みを行うAuthサービス、FastAPI、workerを停止し、対象ファイルを確認してから実行します。

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

SodAIの本番canonical originは`https://app.sodai.me`です。`sodai.me`は将来の
apexサイト用に予約し、アプリへのredirectや認証のtrusted originにはまだ追加しません。

```dotenv
CLOUDFLARE_TUNNEL_TOKEN=<secret tunnel token>
```

```bash
make tunnel-up
```

公開hostnameのoriginはCloudflare側で設定します。コンテナ本番構成では、Next.jsとFastAPIを
`sodai-edge` networkへ接続し、`app.sodai.me`のpath正規表現`^/api/v1(/.*)?$`をFastAPIへ、それ以外を
Next.jsへ送ります。Cloudflareのpublished application routeはhostnameにpath情報を指定できます。
より限定的なpath ruleをcatch-allより先に設定します。

`/api/auth/*`は常にNext.jsの実行時proxyを通します。Authは`AUTH_HOST=0.0.0.0`で
コンテナ内を待ち受けますが、host portや公開hostnameを持たず、内部networkからだけ到達可能にします。
FastAPIにも別の`api.sodai.me`を作らず、PostgreSQLやRedisを公開hostnameへ登録してはいけません。
詳細なroute値と環境変数は[本番環境契約](production-environment.md)に固定します。

現在のようにアプリをホストプロセスとして起動する開発時は、ホストへインストールした`cloudflared`から`127.0.0.1`へ接続する方が安全です。Compose内のTunnelからホストへ接続するためにアプリを`0.0.0.0`へ無制限公開する運用は避けます。

Tunnel tokenが漏えいした場合はCloudflare側で直ちにrotate/revokeし、`.env`を更新します。tokenをログ、issue、バックアップdumpへ混入させないでください。

## PostgreSQL volumeを削除するとき

通常の`make infra-down`はvolumeを保持します。volume削除はすべてのDBデータを失う破壊的操作です。削除が必要な場合は、暗号化済みバックアップと復元試験を確認した上で、対象volume名`sodai-postgres-data`を明示して別途実行してください。
