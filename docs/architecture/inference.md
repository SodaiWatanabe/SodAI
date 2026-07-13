# 推論基盤

## 所有境界

SodAIは推論を含めて単一repository内で実行できますが、APIとGPU runtimeは別プロセス・別依存
として分離します。

```text
Browser
  ├─ HTTP / WebSocket
  ▼
FastAPI ── PostgreSQL
  │           ├─ conversations / messages / inference_runs
  │           └─ inference_outbox
  ▼
Redis Streams
  ▼
Inference worker ── var/models/hina/<artifact-id>
```

- FastAPIは会話、所有権、run状態、公開イベントを確定します。
- Workerはversioned jobを受信して内部生成イベントを返すだけです。
- WorkerはPostgreSQL、認証token、WebSocket接続を知りません。
- PyTorch、Transformers、CUDA依存は`inference/`だけに閉じ込めます。

## Hina

`Hina`は製品モデル名です。`hina-1`というモデルは作りません。Building-SLMの`v1`は学習上の
出自であり、SodAIの公開APIには現れません。

```text
公開モデルID      hina
学習上の出自      Building-SLM v1 / gpt_sft.pt
architecture      absolute_position_gpt
context length    512
prompt template   partner-self-v1
resolved model    hina@<artifact-id>
```

`artifact-id`はcheckpoint、tokenizer bundle全体、manifest schema、runtime ABIから導出した
内容hashです。manifestはdtype、prompt template、語彙内にある必須special token集合も固定します。
ジョブには投入時のartifact IDを固定し、deployment変更後も途中のrunが別の重みへ切り替わらない
ようにします。

importとdeployment promotionは別操作です。新artifact用workerを`HINA_ARTIFACT_ID`で先に起動し、
readinessを確認してからdeploymentを切り替えます。promotionコマンドも対象workerのreadinessを
Redisで検証します。job streamはmodelとartifactごとに分離されるため、
旧workerと新workerを同時に動かしても重みの異なるjobが交差しません。

## 永続ジョブ

会話、partner発言、空のself発言、inference run、outboxを同一PostgreSQL transactionで作ります。
ブラウザはrunを開始しません。outbox dispatcherがcommit済みjobをRedis Streamへ発行します。

内部jobは`attempt_id`、`artifact_id`、会話turn、生成条件、deadlineを含みます。内部eventは
`attempt_id`とrun内の単調増加`sequence`を含みます。Backend projectorはeventを適用、直前eventの
再配信、破棄、gap保留に分類します。gapはACKせず先行eventを待ち、DBへ適用しなかったeventを
新しい状態としてWebSocketへ流しません。

job payloadは直近32 turnかつ本文合計64KiBまでに制限し、workerも新しいturnからcontextへ収めます。
guestは同時Hina runを1件、全体queueは既定32件までに制限します。Cookieの作り直しを含むIP単位の
濫用対策はCloudflare側のrate limitを公開時の必須境界とし、DBのglobal admissionがGPU queueの
最終防衛線になります。

Workerはterminal eventをRedisへ書いた後にだけjobをacknowledgeします。未acknowledge jobは
Redis consumer groupからreclaimできます。attempt lockはevent配信ごとに所有者確認付きで更新し、
lock失効後かつrunning lease失効前に別workerがjobを回収します。eventとattempt配信位置は単一の
Redis scriptで原子的に記録し、再取得時は記録済みsequenceの次から配送を再開します。sampling seedとchunk境界はjobに対して決定的な
ため、同一artifact・同一pinned runtime・同一device classでの再実行では異なる文章が継ぎ足されません。
現在のworker poolへ異種GPUを混在させることはサポートしません。PostgreSQLが正本であり、Redisは
配送路です。

Backendとworkerはlock 60秒、claim idle 90秒、job timeout下限120秒という時間的不変条件を共有
contractから参照します。`XAUTOCLAIM`は返却cursorを保持してPEL全体を巡回し、先頭付近のpending
entryだけに回収が偏らないようにします。

Redisは配送路であって会話archiveではありません。project済みeventと完了jobは`XACK`と`XDEL`を
同じRedis scriptで処理し、公開済みoutboxからもpayloadを消去します。応答と会話履歴の正本は
PostgreSQLだけに残します。

queued runにはjob deadline、running runには更新式leaseがあります。API側reconcilerが期限切れrunを
failedへ収束させるため、Redis停止やworker消失で会話が永久に送信不能になることはありません。
起動時とDB/Redis障害からの復旧時だけ、reconcilerは未検査eventがなくなるまでprojectorを先行させます。
定常時はglobal trafficから独立して動き、row lockと追加graceで正常eventとの競合を避けます。既知の
DEFERは復旧完了を妨げないため、解消不能なgapもlease timeout後にfailedへ収束し、共有stream全体を
止めません。公開eventの再配信も最後にcommitしたevent IDとtypeの完全一致を必要とします。

## ストリーミング

HinaのByteLevel tokenizerは、単独tokenをdecodeすると日本語の途中byteが置換文字になることが
あります。Workerは生成済みtoken ID列全体を毎回decodeし、安定した接頭辞の差分だけを配信します。
短い差分は4文字まで束ね、Redis AOFとDB更新を過剰に増やさず視覚的なstreamingを
維持します。

モデル内部の話者は`<|partner|>`と`<|self|>`です。512 tokenのうち標準で128 tokenを出力用に
予約し、履歴は古いturnからturn境界単位で除外します。最新partner発言が長い場合だけ本文を左から
token単位で切り詰め、prompt envelopeは必ず残します。

## Asuka 1

Building-SLMの`v2`はAsukaの基盤モデルとして学習中です。可変な学習checkpointをSodAIが直接参照
することはありません。SFTと評価を終えた成果物を同じimport、hash、deployment工程へ通した後に、
`rope_gpt` architectureと`asuka_1` adapterを追加します。
