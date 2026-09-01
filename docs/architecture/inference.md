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
  └─ Asuka 1.1 worker ── var/models/asuka-1/<artifact-id>
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
6. 料金表snapshotと、必要な場合はクレジットの最大額予約

生成中の回答本文は`Execution.partial_output`です。Asuka 1.1の内部思考は
`Execution.thinking_output`へ別チャネルとして保存し、Entry、検索、次のprompt、公開HTTP API、
公開WebSocketへは投影しません。`generation_phase`だけを公開し、本文を明かさずクライアントへ
`thinking`／`answering`を伝えます。空のモデルEntryを先に作らず、completed eventのprojector
transactionだけが回答を結果Entryとして作り、ExecutionとResponseRequestをcompletedへ移します。
failed eventはエラー状態だけを確定し、会話履歴へ疑似メッセージを混ぜません。

新しいモデルExecutionでは`thinking_tokens`と`answer_tokens`を0から計測します。既存履歴は
計測不能なためNULLのままとし、0と区別します。`output_tokens`は停止・制御tokenを含む従来の
課金用生成token総数であり、チャネル別token数の和はこれを超えません。

terminal eventを投影するtransactionでは、使用量記録とクレジット予約の確定も同時に行います。
completedは計測済みtokenから実額を確定し、failedとtimeoutは予約を全額解放します。イベント再配送で
二重請求せず、価格改定も開始済みExecutionへ遡及しません。有料推論でtoken計測が欠落した場合は、
料金表に明記したfallback額へ収束し、暗黙に無料化しません。詳細は[クレジット基盤](credits.md)を
参照してください。

## 共通配送路

Outbox dispatcherはcommit済みjobをmodelとartifact別のRedis Streamへ発行します。内部jobは
`execution_id`、`response_request_id`、`attempt_id`、`thread_id`、`answerer_actor_id`、model、
artifact、context、生成条件、deadlineを含みます。内部eventは`execution_id + attempt_id`と
単調増加する`sequence`を持ちます。

Projectorはeventを適用、重複、gap保留、破棄へ分類します。gapはACKせず先行eventを待ち、DBに
適用されなかったeventを公開WebSocketへ流しません。完了済みExecutionへの同一event再送も
結果Entryを増やしません。

内部stream名、consumer group、worker readiness keyはcontract v3で分離しています。旧payloadを
誤って処理せず、後方互換層を持ちません。v2から切り替えるdeploymentでは、v2の実行中job、event、
未publish outboxを先にdrainしてからAPIとworkerをv3へ同時に切り替えます。

jobは直近32 Entry、本文合計64KiBまでです。guest・modelごとのactive Executionを1件、
modelごとの合計を既定32件までに制限します。同じGPUを共有するworkerはresource pool名を
共通化し、Redis leaseで生成を1件ずつ直列化します。Cookie再作成を含むIP単位の濫用対策は
公開edgeのrate limit、DBのadvisory lockをGPU queueの最終防衛線とします。

## 障害復旧

Workerはterminal eventをRedisへ書いた後にだけjobをacknowledgeします。未acknowledge jobは
consumer groupから同じExecutionとしてreclaimします。明示的な再試行だけが新しいattemptを
作ります。

再試行は元Executionのartifactをpinしたまま、同じResponseRequestへ新Executionを追加します。
deployment切替後も旧artifactのactive Executionが存在する間は、運用診断がそのartifact専用streamと
worker readinessを個別に列挙します。旧workerはactive件数がゼロになるまで停止しません。

eventとattemptの配送位置はRedis scriptで原子的に記録します。sampling seedとchunk境界はjobに
対して決定的であり、同じartifact、runtime、device classでの再実行時に異なる文章を途中へ
継ぎ足しません。現在のworker poolへ異種GPUを混在させることはサポートしません。

明示的なcancelは現在APIで即時にExecutionをterminalへ移します。Workerはcancel検知時に手元の
thinking／answer bufferをflushしますが、検知前にAPIがterminal化した未投影bufferまでの完全保存は
保証しません。これは回答本文にも共通する制約です。cancel時も生成済みtokenを完全保存するには、
将来`cancelling`状態とWorkerの終端snapshotを待つhandshakeを導入します。

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

## Asuka 1.1

Asuka 1.1はBuilding-SLM v2のstep 200 SFT成果物を出自とするRoPEモデルです。公開IDは
`asuka-1.1`です。推論互換性を表すruntime modelは`asuka-1`のまま保ち、公開deployment slot
`asuka-1.1`がimmutable artifactを選びます。旧Asuka 1は選択肢と本番workerから外しますが、
過去のResponseRequest、Actor、resolved modelは履歴として変更しません。

```text
公開answerer ID  asuka-1.1
deployment slot   asuka-1.1
runtime model     asuka-1
学習上の出自      Building-SLM v2 / gpt_sft_asuka1_v0.2.1_train_only.pt / step 200
architecture      rope_gpt
context length    512
runtime dtype     float16
prompt template   asuka1-dialogue-v1
resolved model    asuka-1@<artifact-id>
```

入力はSFTと同じく改行を挿入せず、現在ターンを
`<|bos|><|partner|>...<|end_turn|><|self|><|bot|>`として構築します。過去のself発話は
`<|self|><|bot|><|eot|>...<|end_turn|>`として再構築し、過去thinkingは入力しません。
512 tokenのうち標準で256 tokenを出力へ予約し、古いpartner/selfペアから除外します。

生成中は`<|eot|>`までをthinking decoder、以降をanswer decoderで独立に復号します。Workerは
thinking deltaを内部eventとして送り、projectorがPostgreSQLの非公開チャネルへ保存します。
`<|eot|>`を一方向のphase境界として、回答deltaだけを`partial_output`と公開WebSocketへ投影します。
`<|end_turn|>`またはEOSで停止します。terminal eventはthinking／answer両方の最終snapshotと
チャネル別token数を持ち、再配送やbuffer境界によらずDBを同じ値へ収束させます。KV cache、FP16、
temperature 0.85、top-p 0.9、top-kなし、repetition penalty 1.10を使用します。

## 運用状態と検証

`GET /api/v1/health/inference`は`healthy`、`degraded`、`unavailable`だけを公開し、schema revision、
artifact、queue件数は返しません。ホスト上では`make inference-status`がDB revision、Outbox、
Execution、Redis consumer group、current／pinned-active artifact、worker leaseを詳細表示します。
正常な1件の配送ではdegradedへ揺らさず、Outbox、event、jobが一定時間進まない場合だけdegraded、
DB revision不一致、consumer group欠落、worker lease消失はunavailableと判定します。

`make test-inference-e2e`はlocal PostgreSQL／Redisだけを許可し、runごとの専用DBとRedis namespaceを
作ります。CUDA deviceを事前検証して実モデルworkerを一時起動し、HTTP作成、Outbox dispatch、GPU生成、
stream投影、WebSocketイベント、再読込復元、terminal event冪等性を検証後に全資源を削除します。
