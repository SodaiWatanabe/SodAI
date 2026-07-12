# 会話・リアルタイム基盤

## 境界

会話の永続的な変更と復元はHTTP、生成中の変化はWebSocketで扱います。PostgreSQLが
正本であり、WebSocketの切断やページ再読込によって会話が失われないことを契約とします。

```text
Next.js
  ├─ HTTP /api/v1/conversations ── FastAPI ── PostgreSQL app schema
  └─ WS   /api/v1/realtime      ── RealtimeHub
                                         │
                                  PseudoSodAI stream
```

現在の`RealtimeHub`と疑似推論taskはFastAPIプロセス内で動作します。これはUIから永続化、
再接続、streaming providerまでの縦切りを検証する初期実装です。複数APIプロセスまたはGPU
workerへ展開する際は、同じイベントenvelopeを保ったままRedis Streamsと独立workerへ交換します。
単一プロセスの再起動時には、前プロセスが残した`queued/running` runを`failed`へ収束させ、
会話が永久に送信不能にならないようにします。

## 話者

SodAI内部では`assistant`と`user`を中核概念にしません。

| API / DB | 意味 | モデル入力時の対応 |
| --- | --- | --- |
| `sodai` | SodAI自身 | `<|self|>` |
| `partner` | 対話相手 | `<|partner|>` |

tokenizer固有表現への変換は将来のモデルadapterに閉じ込めます。

## 匿名主体

非ログイン利用者には90日有効のランダムなHttpOnly Cookieを発行し、PostgreSQLにはSHA-256
hashだけを保存します。会話は必ず内部ユーザーまたは匿名セッションの一方だけに所有され、
所有者のない会話は作成しません。本番では`GUEST_COOKIE_SECURE=true`を必須とします。

## API

| Method | Path | 用途 |
| --- | --- | --- |
| `POST` | `/api/v1/conversations` | 初回のpartner発言と推論runを作成 |
| `GET` | `/api/v1/conversations` | 所有する会話一覧 |
| `GET` | `/api/v1/conversations/{id}` | 発言と生成中runを含む会話復元 |
| `POST` | `/api/v1/conversations/{id}/turns` | 次のpartner発言と推論runを作成 |
| `GET` | `/api/v1/models` | 主体が利用できるモデルカタログ |
| `POST` | `/api/v1/realtime/tickets` | 一度限り、30秒有効の接続ticket |
| `WS` | `/api/v1/realtime` | 会話・生成イベント |

モデルIDは公開APIとDBで共通の、不変かつ小文字の識別子です。クライアントはIDを解析せず、
`GET /api/v1/models`が返す`name`、`description`、`is_default`を表示と初期選択に使います。
現在の契約は次のとおりです。

| ID | 表示名 | 利用主体 | runtime ID |
| --- | --- | --- | --- |
| `hina` | Hina | 全主体 | `pseudo-sodai-hina-v1` |
| `asuka-1` | Asuka 1 | ログインユーザー | `pseudo-sodai-asuka-1-v1` |

ゲストのデフォルトは`hina`、ログインユーザーのデフォルトは`asuka-1`です。リクエストで
`model`を省略した場合も、認証主体から同じ規則で選択します。APIが受け取る`model`には公開ID、
`inference_runs.requested_model`にも実際に選択した公開IDを保存します。`resolved_model`には
providerとrevisionを含むruntime IDを保存し、再現性と監査可能性を保ちます。モデル追加時は
`app.domain.model_catalog`の定義を起点として、API enum、対象主体、主体別デフォルト、表示情報、
runtime解決を一貫させます。

## イベント

イベントは`id`、`sequence`、`type`、`conversation_id`、`run_id`、`occurred_at`、`data`を
共通項目とします。現在のイベントは次のとおりです。

- `conversation.created`
- `message.created`
- `response.started`
- `response.delta`
- `response.completed`
- `response.failed`

`response.delta.data.content`はその時点の累積本文です。再送やsnapshotとの競合があっても、
クライアントは文字列を追加するのではなく累積本文で置換できるため重複しません。

## 次の本番化境界

1. 推論run作成とRedis enqueueをtransactional outboxで接続する
2. `PseudoSodAI`を独立GPU workerのproviderへ交換する
3. Realtime履歴をRedis Streamsへ移し、複数FastAPI instance間で共有する
4. API key、project、quota、usage ledgerを開発者APIの認証境界として追加する
5. 匿名会話をログインユーザーへ明示的に引き継ぐ処理を追加する
6. `Idempotency-Key`をprincipal単位で保存し、公開APIの安全な再送を保証する
