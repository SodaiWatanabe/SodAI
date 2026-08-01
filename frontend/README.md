# SodAI Web

Next.js App Router、TypeScript、Tailwind CSSで構成したSodAIのWebアプリケーションです。UI、ルーティング、Server Component、ブラウザ向けAuth/APIクライアントだけを所有します。認証DB、OAuth secret、SMTP、Better Authサーバーは`auth/`サービスが所有します。

## ローカル起動

```bash
cp .env.example .env.local
npm install
npm run dev -- --hostname 127.0.0.1 --port 13200
```

先にリポジトリルートから`make dev-auth`と`make dev-backend`を起動してください。Webは <http://localhost:13200> で起動します。リポジトリルートの`make dev-frontend`はSodAI専用ポートを明示して起動します。

## Authサービスとの境界

ブラウザには従来どおり同一originの`/api/auth/*`を公開します。薄いRoute Handlerがリクエスト時の`AUTH_SERVICE_URL`へ透過転送するため、Cookie名、複数の`Set-Cookie`、Google OAuth callback、JWT issuerは変わりません。転送先はビルド成果物へ固定されず、起動環境ごとに設定できます。

Server Componentは受信CookieをAuthサービスへ転送し、セッションまたは10分有効のJWTを読み取ります。セッション期限の更新は同一originのブラウザ経路だけが担い、サーバー描画中に再発行Cookieを失いません。ブラウザ側のJWTは有効期限直前までメモリ上だけで共有し、FastAPIへBearer tokenとして送信します。

Next.jsへ次の秘密値や依存を追加しないでください。

- `AUTH_DATABASE_URL`
- `BETTER_AUTH_SECRET`
- Google Client Secret
- SMTP password
- `pg`、`nodemailer`

Googleログインの有効状態はAuthサービスの`GET /api/auth/capabilities`から取得し、Web側でsecretの有無を判定しません。

## FastAPIとの接続

- `NEXT_PUBLIC_API_BASE_URL`: ブラウザからFastAPIへ到達する公開URL
- `SODAI_API_BASE_URL`: Server ComponentからFastAPIへ到達する内部URL
- `AUTH_SERVICE_URL`: Next.jsからHonoへ到達する内部URL

本番のcanonical originは`https://app.sodai.me`です。ブラウザ向けAPIも
`NEXT_PUBLIC_API_BASE_URL=https://app.sodai.me`として同一originを維持し、Cloudflare
Tunnelが`/api/v1/*`だけをFastAPIへ振り分けます。`SODAI_API_BASE_URL`と
`AUTH_SERVICE_URL`には、公開hostnameではなく内部サービス名を設定します。

## 確認

```bash
npm test
npm run lint
npm run build
```
