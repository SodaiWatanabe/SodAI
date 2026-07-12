# SodAI frontend / authentication service

Next.js App Router、TypeScript、Tailwind CSS、Better Authで構成したSodAIのWeb・認証サービスです。
ユーザー、セッション、外部アカウント、検証トークン、JWT署名鍵は、すべてSodAIが所有するPostgreSQLの`auth`スキーマへ保存します。

## ローカル起動

```bash
cp .env.example .env.local
npm install
npm run auth:migrate
npm run dev
```

開発サーバーは <http://localhost:3000> で起動します。`AUTH_EMAIL_DELIVERY=console`の場合、メール確認とパスワード再設定のURLはNext.jsサーバーの標準出力へ表示されます。本番環境ではconsole配送を拒否するため、SMTPを設定してください。

## データベース境界

Better Authは`AUTH_DATABASE_URL`だけを参照します。接続Poolは常にPostgreSQLの`search_path=auth,public`を強制し、マイグレーションコマンドも`current_schema()`が`auth`でなければ停止します。

```bash
npm run auth:migrate        # 不足テーブル・カラムを適用
npm run auth:migrate:check  # 差分があれば非ゼロ終了
```

Better Auth 1.6.23ではPostgreSQLの`rateLimit.lastRequest`を検査すると、実体が正しい
`int8`でも期待型との差を示す警告が出ます。`Better Auth schema is up to date.`と表示され、
終了コードが0であれば未適用migrationはありません。

`auth`スキーマはインフラ初期化時に作成し、認証専用DBロールだけをownerにします。会話、クレジット、モデル権限などのアプリケーションデータをBetter Authのユーザーテーブルへ追加しないでください。それらはFastAPI側の不変なSodAIユーザーIDに紐付け、認証identityは`issuer + subject`として関連付けます。

## Google OAuth

Google Cloud ConsoleでWeb applicationのOAuth clientを作成し、次のredirect URIを登録します。

```text
http://localhost:3000/api/auth/callback/google
https://platform.sodai.me/api/auth/callback/google
```

`GOOGLE_CLIENT_ID`と`GOOGLE_CLIENT_SECRET`は必ず両方設定します。未設定時もメール認証は利用できます。

## FastAPIとの認証契約

ブラウザのBetter AuthセッションはNext.js内でのみ利用します。FastAPIへは`authClient.token()`で取得した10分有効のJWTをBearer tokenとして送信します。

- issuer: `BETTER_AUTH_URL`
- audience: `BETTER_AUTH_URL`
- subject: Better Authの`user.id`
- algorithm: EdDSA / Ed25519
- JWKS: `${BETTER_AUTH_URL}/api/auth/jwks`
- claims: `sub`, `email`, `emailVerified`, `name`, `iat`, `exp`, `iss`, `aud`

JWTはセッションの代替ではなく、FastAPIなど別サービスへ本人性を渡すためだけに発行します。JWT署名秘密鍵も`auth.jwks`へ暗号化して保存されます。

## メール配送

メール配送は`AuthEmailDelivery`インターフェースで分離されています。

- `console`: ローカル開発専用
- `smtp`: 本番またはMailpit用。特定ベンダーに依存しない標準SMTP

SMTPでは`AUTH_EMAIL_FROM`、`AUTH_SMTP_HOST`、`AUTH_SMTP_PORT`、`AUTH_SMTP_SECURE`を指定します。認証が必要な場合だけ`AUTH_SMTP_USER`と`AUTH_SMTP_PASSWORD`を両方設定してください。
