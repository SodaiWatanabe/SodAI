# SodAI authentication service

Better AuthをHono上で実行する、SodAIの独立認証サービスです。認証ユーザー、外部アカウント、セッション、検証情報、JWT署名鍵と認証メールだけを所有します。会話、プロフィール、クレジットなどのアプリケーションデータは扱いません。

## ローカル起動

```bash
cp .env.example .env
npm install
npm run migrate
npm run dev
```

既定では`127.0.0.1:13201`で待ち受けます。ブラウザはこの内部ポートへ直接アクセスせず、Next.jsの`/api/auth/*` Route Handlerを通して公開originへアクセスします。`BETTER_AUTH_URL`はJWTのissuerとaudienceでもあるため、内部の待受URLではなく公開originを設定します。

## 所有境界

- `AUTH_DATABASE_URL`は`sodai_auth`ロールだけを使用する
- PostgreSQLの`search_path`は常に`auth,public`へ固定する
- 外部へ直接公開せず、信頼できる同一origin gatewayからだけ接続する
- OAuth secret、SMTP secret、`BETTER_AUTH_SECRET`をWebへ渡さない
- FastAPIは認証DBを読まず、JWTとJWKSだけを検証する
- Webへ公開する設定情報は`GET /api/auth/capabilities`の非機密情報だけに限定する

### クライアントIPの信頼境界

既定では、Honoが取得した直接接続元だけをレート制限に使います。AuthサービスをNext.js経由で利用する本番環境では、信頼済みgatewayが受信値を必ず削除してから生成するヘッダーを`AUTH_TRUSTED_CLIENT_IP_HEADER`へ指定します。

```dotenv
# Cloudflareだけが公開originへ到達できる構成
AUTH_TRUSTED_CLIENT_IP_HEADER=cf-connecting-ip

# 自前reverse proxyが受信値を上書きする構成
AUTH_TRUSTED_CLIENT_IP_HEADER=x-forwarded-for
```

公開originへの迂回経路を残したまま設定すると、送信元IPを偽装できます。Authサービス自体を外部公開せず、gateway側で同名の受信ヘッダーを破棄・再生成することを設定条件とします。

## データベース

接続Poolは常にPostgreSQLの`search_path=auth,public`を強制します。マイグレーションも`current_schema()`が`auth`でなければ停止します。

```bash
npm run migrate
npm run migrate:check
```

Better Auth 1.6.23ではPostgreSQLの`rateLimit.lastRequest`を検査すると、実体が正しい`int8`でも期待型との差を示す警告が出ます。`Better Auth schema is up to date.`と表示され、終了コードが0であれば未適用migrationはありません。

## Google OAuth

Google Cloud ConsoleでWeb applicationのOAuth clientを作成し、公開originのcallback URIを登録します。Authサービスの内部ポートは登録しません。

```text
http://localhost:13200/api/auth/callback/google
https://app.sodai.me/api/auth/callback/google
```

`GOOGLE_CLIENT_ID`と`GOOGLE_CLIENT_SECRET`は必ず両方設定します。未設定時はメール認証だけを提供し、`GET /api/auth/capabilities`もその状態を返します。

## FastAPIとの認証契約

ブラウザのBetter AuthセッションCookieはAuthサービスだけが検証します。FastAPIには10分有効のJWTをBearer tokenとして渡します。

- issuer / audience: `BETTER_AUTH_URL`
- subject: Better Authの`user.id`
- algorithm: EdDSA / Ed25519
- JWKS: `/api/auth/jwks`
- claims: `sub`、`email`、`emailVerified`、`name`、`iat`、`exp`、`iss`、`aud`

Authサービスの待受URLを変更しても`BETTER_AUTH_URL`は変更しません。FastAPIの`AUTH_JWKS_URL`だけを内部URLへ向けることで、既存のidentity対応と公開issuerを保ったままサービス間通信を分離できます。

## メールOTP

メールアドレスへ6桁のコードを送り、検証に成功すると既存ユーザーはログインし、未登録ユーザーはBetter Auth上に作成されます。

- 有効期限: 5分
- 入力上限: 3回
- 発行・検証のレート制限: 1分あたり3回
- DB保存: ハッシュ化
- 再送信: 以前のコードを失効させてローテーション

`AUTH_EMAIL_DELIVERY=console`は開発時だけ利用できます。本番では`AUTH_EMAIL_DELIVERY=smtp`を指定し、標準SMTPの設定をAuthサービスへ渡します。

## 確認

```bash
npm test
npm run lint
npm run typecheck
npm run build
npm run migrate:check
```

`GET /healthz`はプロセスのliveness、`GET /readyz`は認証DB接続を含むreadinessを返します。トラフィックの切り替えには`/readyz`を使用します。
