# 本番環境契約

## Canonical origin

SodAIアプリのcanonical originは`https://app.sodai.me`です。次の値を同じoriginへ
固定します。

- Better Authのbase URL、trusted origin
- JWTのissuer、audience
- Frontend originとSecure Cookie
- ブラウザから利用するFastAPIのbase URL
- Google OAuth callback

`https://sodai.me`は将来のapexサイト用に予約します。現時点ではアプリへのredirect、
Better Authのtrusted origin、Cookie domainへ追加しません。Cookieは`app.sodai.me`の
host-only Cookieとして扱います。

## 公開経路

ブラウザに見えるoriginは1つだけです。

```text
Browser
  │ https://app.sodai.me
  ▼
Cloudflare Tunnel
  ├─ /api/v1/* ───────────────► FastAPI :13202
  └─ /* ──────────────────────► Next.js :13200
                                  └─ /api/auth/* ─► Auth :13201
```

Cloudflareのremotely-managed Tunnelへ、次の順序でpublished application routeを
設定します。

| 優先 | Public hostname | Path | Service |
| --- | --- | --- | --- |
| 1 | `app.sodai.me` | `^/api/v1(/.*)?$` | `http://backend:13202` |
| 2 | `app.sodai.me` | なし | `http://frontend:13200` |

Cloudflare TunnelのpathはGo互換の正規表現です。`^/api/v1(/.*)?$`は`/api/v1`自身と
その配下だけに一致します。Dashboardでrouteを作るとTunnel向けDNS recordも作成されます。
設定時点の公式手順は
[Cloudflare Tunnel: Create a tunnel](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/get-started/create-remote-tunnel/)
と[Configuration file](https://developers.cloudflare.com/tunnel/advanced/local-management/configuration-file/)
を確認します。

WebSocketの`wss://app.sodai.me/api/v1/realtime`も1番目のFastAPI経路を通します。
Authは公開routeを持たず、Next.js proxyだけを経由します。origin hostへ外部から到達できる
別経路は作りません。

## 環境ファイル

開発用`.env`を上書きせず、次の本番専用ファイルを作成します。

```bash
cp .env.production.example .env.production
cp auth/.env.production.example auth/.env.production
cp backend/.env.production.example backend/.env.production
cp frontend/.env.production.example frontend/.env.production
chmod 600 \
  .env.production \
  auth/.env.production \
  backend/.env.production \
  frontend/.env.production
```

`.env.production`の`AUTH_DATABASE_PASSWORD`と`APP_DATABASE_PASSWORD`は、各サービスの
接続URLにも同じ値を設定します。値には`openssl rand -hex 32`のようなURL encode不要の
ランダム文字列を使用します。`BETTER_AUTH_SECRET`、SMTP password、Tunnel tokenは
DBやRedisのpasswordと使い回しません。

本番設定は次で検査します。

```bash
make production-config
```

この検査は、少なくとも次の誤設定を拒否します。

- canonical originが`https://app.sodai.me`ではない
- apexや別API originを認証・ブラウザAPIへ使用している
- issuerとaudienceが一致しない
- guest CookieがSecureではない
- Cloudflare以外のクライアントIPヘッダーを信頼している
- consoleメール、SMTP平文接続、仮の秘密値を使用している
- DB接続URLのpasswordがCompose側と一致しない
- Auth、Backendの内部接続に公開hostnameを使用している

`NEXT_PUBLIC_API_BASE_URL`はブラウザbundleへ入るため、Docker build時に
`.env.production`の`SODAI_PUBLIC_ORIGIN`から渡します。`SODAI_API_BASE_URL`と
`AUTH_SERVICE_URL`は実行時の内部service discoveryだけに使用します。

## コンテナ構成

本番は開発用`compose.dev.yaml`と分離した`compose.production.yaml`を重ねて起動します。
ホストへlisten portを公開するサービスはありません。

| Service | 公開経路 | 実行権限 | Readiness |
| --- | --- | --- | --- |
| Frontend | Tunnelからのみ | non-root、read-only | `/healthz` |
| Backend | TunnelとFrontendからのみ | non-root、read-only | PostgreSQLとRedisを検査 |
| Auth | Frontendからのみ | non-root、read-only | PostgreSQLを検査 |
| Inference × 2 | Redisからのみ | non-root、read-only | model artifactとworker leaseを検査 |
| PostgreSQL / Redis | internal networkのみ | capability追加なし | native ping |

全アプリコンテナはLinux capabilityをdropし、`no-new-privileges`を有効にします。
書き込みが必要な一時領域だけをtmpfsにし、ログはサイズと世代数を制限したDockerの
`local` driverへ送ります。AuthとBackendのmigrationは常駐サービスから分離した
one-shot containerでのみ実行します。

Inference imageへmodel weightは含めません。`.env.production`の
`SODAI_MODEL_HOST_PATH`を`/models`へ読み取り専用mountします。HinaとAsuka 1は独立した
workerで動き、既定では同じresource poolを共有してGPU生成を直列化します。標準構成の
workerはhost側のUID/GID 1000で読み取れるmodel fileを前提とします。

## 初回デプロイ

Cloudflare Dashboardで前述の2 routeを作成し、4つの本番環境ファイルを設定してから、
repository rootで次を順番に実行します。

```bash
# 例: rollback可能なimmutable tagを使う
git rev-parse --short=12 HEAD
# 出力値を .env.production の SODAI_IMAGE_TAG に設定する

make production-config
make production-build
make db-backup ENV_FILE=.env.production
make production-migrate
make production-up-gpu
```

GPU workerをまだ公開に含めない場合だけ、最後を`make production-up`にします。どちらの
targetもAuth、Backend、Frontendがhealthyになった後でCloudflare Tunnelを起動します。
`production-up-gpu`はさらにHinaとAsuka 1をloadし、両方のworker leaseを取得するまで
待ちます。

稼働状態とログは次で確認します。

```bash
make production-ps
make production-logs
```

コンテナ内部のprobeは次の責務に分けています。

- liveness: Auth `/healthz`、Frontend `/healthz`、Backend `/api/v1/health`
- readiness: Auth `/readyz`、Backend `/api/v1/health/ready`
- model readiness: `sodai-inference-healthcheck`

公開後は`https://app.sodai.me/healthz`と
`https://app.sodai.me/api/v1/health/ready`を外側から確認します。Backend readinessの
失敗応答は依存先の詳細を返さず、HTTP 503と`unavailable`だけを返します。

## 更新とrollback

更新ごとにGit commit由来の新しい`SODAI_IMAGE_TAG`でbuildします。Frontendでは同じ値を
Next.js deployment IDにも使うため、deploy前後のasset取り違えを検出できます。

通常の更新手順は`production-config`、`production-build`、backup、
`production-migrate`、`production-up-gpu`です。rollback時は`.env.production`を直前の
image tagへ戻して`production-up-gpu`を再実行します。DB migrationは自動downgradeしません。
schema変更を伴うreleaseは、1つ前のアプリと互換なexpand/contract方式で作成します。

停止が必要な場合は次を使用します。PostgreSQLとRedisのnamed volumeは削除しません。

```bash
make production-down
```

## OAuthとメール

Googleログインを有効にする場合のWeb application callbackは次です。

```text
https://app.sodai.me/api/auth/callback/google
```

認証メールはResendで検証した`auth.sodai.me`から
`SodAI <no-reply@auth.sodai.me>`として送信します。SMTPは`smtp.resend.com:465`の
implicit TLSを使用し、ユーザー名は`resend`、passwordには`auth.sodai.me`だけへ制限した
Sending access API keyを設定します。SPF、DKIMに加え、`_dmarc.auth.sodai.me`へDMARC
policyを設定してから実配送を有効にします。
