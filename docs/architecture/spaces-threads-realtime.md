# Space・Thread・リアルタイム基盤

## 中核モデル

SodAIは「1対1の会話」を永続化の最上位概念にしません。現在のチャットUIも、将来の共同作業や
エージェント実行も、次の同じ構造で表現します。

```text
Principal ── 認証・認可を受ける接続主体
    │
    ▼
Actor ────── Entryを残す作中主体
    │
    ▼
Space ────── 所有権・参加権限・データ寿命の境界
    │
    └─ Thread ── 順序を持つ一つの作業文脈
         ├─ Entry ─────────── 確定済みで不変の記録
         └─ ResponseRequest ─ 誰が誰へ応答を求めたか
              └─ Execution ── 実行試行と生成中の状態
```

`Principal`と`Actor`は別のID空間です。Principalはリクエスト時の本人確認に使い、Actorは
人、モデル、将来のagent、tool、systemを同じ著者モデルへ載せます。認証主体が削除されても、
共有Spaceの履歴上必要なActorは匿名化された主体として残せます。
公開APIはActorのUUID、kind、表示名だけを返し、内部registry keyやPrincipal IDを露出しません。
human Actorの内部keyもActor自身のUUIDから生成し、認証主体のIDを埋め込みません。

現在はユーザーまたはゲストごとにpersonal Spaceを遅延作成し、UIにSpace選択を露出しません。
Threadは現在の「会話」に相当しますが、複数参加者やエージェント作業へ拡張しても構造を
変更する必要がありません。

## 書き込み契約

PostgreSQLの`app` schemaが唯一の正本です。Entryは確定した内容だけを持ち、UPDATEをDB triggerで
拒否します。ストリーミング中の本文は`executions.partial_output`へ投影し、完了イベントを適用する
同じtransactionで結果Entryを一度だけ作成します。失敗時に空のEntryやエラー文を履歴へ混ぜません。

入力Entry、ResponseRequest、初回Execution、context snapshot、outboxは一つのtransactionで
確定します。部分unique indexにより、同じThreadにactiveなResponseRequestは1件、同じRequestに
activeなExecutionも1件だけです。入力Entryと結果Entryが別Threadを指すことは複合外部キーで
禁止します。

## API

| Method | Path | 用途 |
| --- | --- | --- |
| `GET` | `/api/v1/spaces` | Principalが利用できるSpace |
| `POST` | `/api/v1/threads` | Thread、入力Entry、ResponseRequestを作成 |
| `GET` | `/api/v1/threads` | activeなThread一覧 |
| `GET` | `/api/v1/threads/{id}` | Entryと最新ResponseRequestを含む復元 |
| `PATCH` | `/api/v1/threads/{id}` | Thread名を更新 |
| `POST` | `/api/v1/threads/{id}/archive` | Threadをアーカイブ |
| `POST` | `/api/v1/response-requests` | 既存Threadへ入力と応答要求を追加 |
| `GET` | `/api/v1/answerers` | Principalが選択できる応答主体 |
| `POST` | `/api/v1/realtime/tickets` | 一度限り、短寿命の接続ticket |
| `WS` | `/api/v1/realtime` | Thread・Entry・Responseの変更通知 |

応答主体の公開ID、表示名、説明、利用権限、主体別デフォルトはBackendのanswerer catalogだけが
正本です。現在はゲストの既定値が`hina`、ログインユーザーの既定値が`asuka-1`です。

アーカイブは削除ではありません。`status=archived`として通常一覧と追記対象から外し、将来の
復元と完全削除を別操作として追加できる境界を残します。

## リアルタイム契約

永続的な変更と復元はHTTP、生成途中の変化はWebSocketで扱います。公開イベントは共通して
`id`、`sequence`、`type`、`space_id`、`thread_id`、`thread_revision`、
`response_request_id`、`execution_id`、`occurred_at`、`data`を持ちます。

- `thread.created`
- `thread.updated`
- `thread.archived`
- `entry.created`
- `response.started`
- `response.delta`
- `response.completed`
- `response.failed`
- `sync.required`

`response.delta.data.content`はその時点の累積本文です。クライアントはdeltaの単純追加ではなく
累積本文で置換するため、再送でも重複しません。購読queueが溢れた場合は古い構造イベントを
黙って落とさず`sync.required`へ置き換え、Thread一覧と表示中ThreadをHTTPで再取得して
PostgreSQLのrevisionへ収束します。ページ再読込も同じ復元経路を使います。

Realtime hubと一度限りticketは現在process-localです。FastAPIを水平分割する前に、ticket storeと
commit後イベントのfan-outを共有基盤へ移す必要があります。

## 匿名主体

非ログイン利用者には90日有効のランダムなHttpOnly Cookieを発行し、DBにはSHA-256 hashだけを
保存します。guest sessionはpersonal Spaceを所有します。本番では`GUEST_COOKIE_SECURE=true`を
必須とします。
