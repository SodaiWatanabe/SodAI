# 回答評価

## 目的

回答評価はAIとHumanを区別せず、実際に完了してEntryになった回答への依頼者自身の反応を保存する。
初期実装は`positive`と`negative`の二値だけを扱い、集計、コメント、星評価は持たない。

```text
ResponseRequest
  └─ Execution ── result_entry_id ──> ThreadEntry
       └─ ResponseEvaluation
            └─ positive | negative
```

評価をResponseRequestではなくExecutionへ紐づけることで、失敗後に再試行した場合も、どの実行結果を
評価したかを一意に保つ。AI回答とHuman回答は同じテーブル、Service、API、画面投影を通る。

## 保存と認可

`response_evaluations`は`execution_id`を主キーかつ外部キーとして持つ。したがって1つのExecutionに
存在できる現在評価は最大1件で、Execution削除時は一緒に削除される。

- 評価できるのは、そのResponseRequestを作成したPrincipalだけ
- UserとGuestのどちらも同じ所有権判定を使う
- `completed`かつ`result_entry_id`を持つExecutionだけを評価できる
- 所有していないExecutionは存在を漏らさず404として扱う
- 未完了Executionは409として扱う
- `PUT`は新規作成と評価変更を同じ操作で扱う
- `DELETE`は未評価でも成功する冪等な解除操作とする

書き込み時はExecution行をロックし、並行する更新を直列化する。変更履歴は初期実装では保持せず、
現在評価と`created_at`、`updated_at`だけを保存する。

## APIと画面投影

| Method | Path | 用途 |
| --- | --- | --- |
| `PUT` | `/api/v1/executions/{id}/evaluation` | `positive`または`negative`を保存 |
| `DELETE` | `/api/v1/executions/{id}/evaluation` | 評価を解除 |

Thread取得時は、結果Entryへ`execution_id`と`evaluation`を返す。最新ResponseRequestのExecutionにも
同じ`evaluation`を返すため、永続Entryと生成直後の表示のどちらからでも同じ状態を復元できる。

Chatは完了回答にのみ高評価・低評価ボタンを表示し、同じボタンの再選択を解除として扱う。操作時は
先に画面へ反映し、API失敗時だけ直前の状態へ戻す。評価変更はThread本文やrevisionを変更せず、
初期実装ではRealtimeイベントも配信しない。ページ再読込や別タブはThreadのHTTP再取得で収束する。

## クレジットと将来拡張

評価Serviceはクレジット台帳、Human profile、rankを呼ばない。現在のクレジット消費とHuman回答報酬は
モデルと思考の深さだけで確定し、評価後も変更しない。

将来ボーナスを導入する場合は、回答完了時の確定取引を変更せず、評価集計を入力とする独立した追加取引
として設計する。rank反映や品質集計も現在評価の保存境界とは分離する。
