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

`NEXT_PUBLIC_API_BASE_URL`はブラウザbundleへ入るため、本番Frontendのbuild時にも
`frontend/.env.production`を適用します。`SODAI_API_BASE_URL`と`AUTH_SERVICE_URL`は
実行時の内部service discoveryだけに使用します。

## OAuthとメール

Googleログインを有効にする場合のWeb application callbackは次です。

```text
https://app.sodai.me/api/auth/callback/google
```

認証メールのFrom domainには`sodai.me`を使用できます。SMTP provider側でSPF、DKIMを
設定し、`sodai.me`にDMARC policyを追加してから実配送を有効にします。
