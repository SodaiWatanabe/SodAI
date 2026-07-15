# 認証・アカウント境界

## 目的

SodAIはBetter Authをセルフホストします。ただし、Better Authを永続的に交換不能な中心には置きません。認証は「本人が誰であるかを証明する層」、SodAIアカウントは「会話、権限、クレジット、貢献を所有する層」として分離します。

```text
Google / Email OTP
      │
      ▼
Hono / Better Auth ── auth schema
      │ issuer + subject
      ▼
SodAI identity mapping ── app schema
      │ internal user UUID
      ├─ spaces / threads / entries
      ├─ credit accounts
      ├─ feedback
      └─ response requests / executions
```

## PostgreSQLの所有境界

1つのPostgreSQLデータベース`sodai`の中で、schemaとロールを分けます。

| 領域 | DBロール | schema | 所有するデータ |
| --- | --- | --- | --- |
| 認証 | `sodai_auth` | `auth` | Better Authのユーザー、セッション、アカウント、検証情報、鍵 |
| アプリ | `sodai_app` | `app` | SodAI内部ユーザー、identity対応、Space、Thread、クレジット、フィードバック |

各ロールは自分のschemaだけを所有し、他方のschemaへ権限を持ちません。ロールごとの`search_path`もデータベース初期化時に固定します。Better AuthとFastAPIが同じPostgreSQLを利用しても、誤ったmigrationで相手のテーブルを変更しにくい境界です。

アプリケーションの接続契約は次の通りです。

```text
Auth:     AUTH_DATABASE_URL=postgresql://sodai_auth:...@HOST:5432/sodai
FastAPI:  DATABASE_URL=postgresql+asyncpg://sodai_app:...@HOST:5432/sodai
```

Dockerネットワーク内の`HOST`は`postgres`、ホストから開発する場合は`127.0.0.1`です。パスワードを含むURLはコミットしません。

Next.jsは認証DBへ接続しません。ブラウザ向けの`/api/auth/*`は実行時の薄いRoute Handlerで同一originのままHonoへ転送し、Server Componentは受信Cookieを内部Auth URLへ転送してセッションと短命JWTを取得します。セッション更新はブラウザ経路だけが所有し、Server Componentは読み取り時にCookieを更新しません。OAuth secret、SMTP secret、`BETTER_AUTH_SECRET`はAuthサービスだけに配置します。

## アプリ内の不変ID

アプリ内ではSodAIが発行するUUIDをユーザーの主キーとします。認証主体は概念上、次の対応表で関連付けます。

```text
auth_identities
├─ user_id       # SodAI内部UUID
├─ issuer        # トークン発行者
├─ subject       # 発行者内のユーザー識別子
├─ email
└─ email_verified

UNIQUE (issuer, subject)
```

所有権を表すpersonal Spaceやクレジット台帳は内部`user_id`を起点に解決します。Entryの著者は別ID空間のActorで表し、認証Principalと混同しません。メールアドレスは変更可能であり、主キーや無条件のアカウント結合キーにはしません。

## FastAPIの認証境界

FastAPIは「Better Authのテーブル」を読んで認証しません。受け取ったトークンを発行者ごとの検証器で検証し、正規化済みの認証主体へ変換します。

```text
Bearer token
   └─ Token verifier (issuer / JWKS / audience)
          └─ AuthenticatedPrincipal(issuer, subject, email, email_verified)
                 └─ app schemaのidentityからinternal user UUIDを解決
```

署名、`issuer`、`audience`、有効期限を検証し、クレジットやモデル利用権はトークン内の値を信用せず`app`schemaから取得します。WebSocketを追加するときは、同じ検証境界から一度限り・短寿命の接続ticketを発行します。

## Cognitoへの将来移行

AWSへのホスティング移行とCognitoへの認証移行は別々に実施できます。まずRDSやECSへ配置を移し、Better Authを継続しても構いません。

Cognitoへ移る場合は、次の順序で停止時間を小さくします。

1. Cognito User PoolとGoogle IdPを準備する
2. FastAPIへCognitoのissuer/JWKS検証器を追加し、旧新両issuerを許可する
3. Cognitoでの初回ログイン時に、確認済みの手続きで既存の内部UUIDへidentityを追加する
4. 新規ログインをCognitoへ切り替える
5. 旧セッションの期限後にBetter Auth issuerを停止する
6. `auth`schemaを保持したバックアップを取得してから旧認証サービスを撤去する

Google利用者は再ログインで移行できます。メールOTP利用者も、新しい認証基盤でメール所有を再確認したあと、確認済みの手続きで既存の内部UUIDへidentityを追加します。どちらの場合も、Spaceやクレジットは内部UUIDから解決されるため移動しません。

## 外部依存を正確に捉える

データ主権は「外部サービスを一切使わない」という意味ではありません。

- Google OAuthにはログイン時の識別情報が渡る
- メール配送事業者には宛先とメール本文が渡る
- Cloudflare Tunnel利用時は公開経路とTLS終端をCloudflareへ依存する

一方、OTP検証情報、セッションDB、SpaceとThread、クレジット台帳、モデル、学習データはSodAI管理下に残します。各外部依存は固有IDをアプリ全体へ漏らさず、設定とadapter境界で交換できるようにします。
