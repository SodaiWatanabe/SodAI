# 推論worker

Asuka 1.1はBuilding-SLM v2のRoPE SFT成果物をAsuka runtimeのartifactとして取り込みます。
実行時に学習repositoryをimportせず、optimizer stateを除去した検証済みのimmutableな
`model.safetensors`を読み込みます。

```bash
make install-inference
make import-asuka1 \
  CHECKPOINT=../Building-SLM/checkpoints/v2/gpt_sft.pt \
  TOKENIZER=../Building-SLM/tokenizer \
  SOURCE_REPOSITORY=../Building-SLM
make dev-inference ARTIFACT_ID=<artifact-id> DEVICE=cuda:0
# 別ターミナルでworkerのreadinessを確認してから実行
make deploy-asuka11 ARTIFACT_ID=<artifact-id>
```

公開モデルIDと既定deploymentは`asuka-1.1`、runtime modelは`asuka-1`です。
成果物は`var/models/asuka-1/<artifact-id>/`に置かれ、Git管理されません。
`artifact-id`はモデル名や世代番号ではなく、回答再現用の内容hashです。

importとdeployment promotionは別操作です。新artifactに固定したworkerを先に起動し、
`make deploy-asuka11`がRedisのworker readinessを検証してから新規Executionの向き先を
切り替えます。job streamはartifact別なので、旧workerは旧artifactに固定されたExecutionを
最後まで処理できます。次回起動からは`ARTIFACT_ID`を省略できます。

非ログイン時も同じAsuka 1.1 workerを使います。ゲストの無料料金表と認証済みユーザーの
料金表はバックエンドで選択し、配送・復旧・推論経路は共通です。
