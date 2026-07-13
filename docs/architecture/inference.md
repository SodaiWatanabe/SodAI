# 推論基盤

## プロセス境界

SodAIは単一repositoryで配布しますが、APIとGPU runtimeを別プロセス・別依存として保ちます。

```text
Browser
  ├─ HTTP / WebSocket
  ▼
FastAPI ── PostgreSQL
  │           ├─ threads / entries
  │           ├─ response_requests / executions
  │           └─ response_context_items / outbox_events
  ▼
Redis Streams
  ├─ Hina worker ── var/models/hina/<artifact-id>
  └─ Asuka pseudo worker
```

- FastAPIは所有権、応答要求、実行状態、確定Entry、公開イベントを管理します。
- Workerはversioned jobを受信し、内部生成イベントを返すだけです。
- WorkerはPostgreSQL、認証token、WebSocketを知りません。
- PyTorch、tokenizer、CUDA依存は`inference/`だけに閉じ込めます。
- HinaとAsukaはruntimeが違っても、同じjob、event、projectorを通ります。

## ResponseRequestとExecution

ResponseRequestは「どのActorが、どの入力Entryを根拠に、どのActorへ応答を求めたか」という
利用者の意図です。Executionはその要求を処理する個々の試行です。再試行を追加しても要求を
複製せず、`attempt_no`を増やした新Executionとして記録できます。

Threadへの入力時は、次を同じPostgreSQL transactionで確定します。

1. 対話相手による不変の入力Entry
2. queued状態のResponseRequest
3. attempt 1のExecution
4. その時点のEntryから切り出したcontext snapshot
5. `model.generation.requested` outbox event

生成中の本文は`Execution.partial_output`です。空のモデルEntryを先に作りません。completed eventの
projector transactionだけが結果Entryを作り、ExecutionとResponseRequestをcompletedへ移します。
failed eventはエラー状態だけを確定し、会話履歴へ疑似メッセージを混ぜません。

## 共通配送路

Outbox dispatcherはcommit済みjobをmodelとartifact別のRedis Streamへ発行します。内部jobは
`execution_id`、`response_request_id`、`attempt_id`、`thread_id`、`answerer_actor_id`、model、
artifact、context、生成条件、deadlineを含みます。内部eventは`execution_id + attempt_id`と
単調増加する`sequence`を持ちます。

Projectorはeventを適用、重複、gap保留、破棄へ分類します。gapはACKせず先行eventを待ち、DBに
適用されなかったeventを公開WebSocketへ流しません。完了済みExecutionへの同一event再送も
結果Entryを増やしません。

内部stream名とconsumer groupはcontract v2で分離しています。旧payloadを誤って処理せず、
後方互換層を持ちません。

jobは直近32 Entry、本文合計64KiBまでです。Hinaではguestのactive Executionを1件、全体を
既定32件までに制限します。Cookie再作成を含むIP単位の濫用対策は公開edgeのrate limit、DBの
advisory lockをGPU queueの最終防衛線とします。

## 障害復旧

Workerはterminal eventをRedisへ書いた後にだけjobをacknowledgeします。未acknowledge jobは
consumer groupから同じExecutionとしてreclaimします。明示的な再試行だけが新しいattemptを
作ります。

eventとattemptの配送位置はRedis scriptで原子的に記録します。sampling seedとchunk境界はjobに
対して決定的であり、同じartifact、runtime、device classでの再実行時に異なる文章を途中へ
継ぎ足しません。現在のworker poolへ異種GPUを混在させることはサポートしません。

queued Executionにはjob deadline、running Executionには更新式leaseがあります。APIの
reconcilerが期限切れをfailedへ収束させるため、Redis停止やworker消失でThreadが永久に送信不能に
なりません。復旧直後は未検査eventをprojectorが先に処理し、正常なterminal eventとの競合を
避けます。

Redisは配送路です。project済みeventと完了jobは`XACK + XDEL`し、公開済みoutboxからもpayloadを
除去します。Redisへ未配信のままExecutionが期限切れになったoutboxは`discarded_at`を記録して
payloadを除去し、機密な入力本文を未処理queueへ残しません。Entryと実行監査の正本は
PostgreSQLだけです。

## Hina

`Hina`が製品モデル名です。`hina-1`という公開モデルは作りません。Building-SLMの`v1`は学習上の
出自であり、SodAIの公開APIには現れません。

```text
公開answerer ID  hina
runtime model     hina
学習上の出自      Building-SLM v1 / gpt_sft.pt
architecture      absolute_position_gpt
context length    512
prompt template   partner-self-v1
resolved model    hina@<artifact-id>
```

`artifact-id`はcheckpoint、tokenizer bundle、manifest schema、runtime ABIから導出した内容hashです。
manifestはdtype、prompt template、必須special tokenも固定します。job作成時にartifactをpinし、
deployment変更後も実行途中で別の重みへ切り替えません。

importとdeployment promotionは別操作です。新artifact専用workerを先に起動し、readinessをRedisで
確認してからdeploymentを切り替えます。旧workerと新workerはartifact別streamを読むため共存できます。

HinaのByteLevel tokenizerは単独tokenのdecodeで日本語の途中byteが置換文字になることがあります。
Workerは生成済みtoken ID列全体をdecodeし、安定した接頭辞の差分だけを配信します。短い差分は
4文字まで束ね、Redis AOFとDB更新を増やしすぎず視覚的なstreamingを維持します。

モデル入力の役割は`<|partner|>`と`<|self|>`です。これは公開APIのActor表現をtokenizerへ落とす
adapter境界であり、APIの`assistant/user`関係ではありません。512 tokenのうち標準で128 tokenを
出力へ予約し、古いEntryから境界単位で除外します。

## Asuka 1

現在のAsuka 1は、製品のストリーミング経路を検証する決定的な疑似runtimeです。immutableな
runtime revisionは`pseudo-v1`、resolved modelは`asuka-1@pseudo-v1`です。FastAPI内で直接本文を
DBへ書かず、専用workerとしてHinaと同じGenerationJobを消費し、同じGenerationEventを返します。
eventとattempt progressも同じく一つのRedis scriptで保存するため、再claim時は記録済みsequenceの
次から再開します。このためUI、再読込、失敗収束、Entry確定の挙動がruntimeごとに分岐しません。

Building-SLMの`v2`はAsukaの基盤モデルとして学習中です。SFTと評価を終えた成果物をHinaと同じ
import、hash、deployment工程へ通した後、疑似runtimeを実モデルadapterへ交換します。公開ID、
Actor、ResponseRequest、Execution、Frontend契約はその交換で変わりません。
