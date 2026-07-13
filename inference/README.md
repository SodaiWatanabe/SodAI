# SodAI Inference

SodAI内部だけに公開するGPU推論ワーカーです。FastAPIとはRedis Streams上のversioned contractで
通信し、PostgreSQL、認証、WebSocketへ直接アクセスしません。

HinaはBuilding-SLM内部のv1 SFT成果物を出自とします。実行時にBuilding-SLMをimportしたり、
学習用checkpointへsymlinkしたりしません。`sodai-import-hina`がoptimizer stateを除去し、
検証済みのimmutableな`model.safetensors`へ変換します。

```bash
make install-inference
make import-hina \
  CHECKPOINT=../Building-SLM/checkpoints/v1/gpt_sft.pt \
  TOKENIZER=../Building-SLM/tokenizer \
  SOURCE_REPOSITORY=../Building-SLM
make dev-inference HINA_ARTIFACT_ID=<importで表示されたartifact-id>
# 別ターミナルで、上のworkerがreadyになってから実行
make deploy-hina ARTIFACT_ID=<importで表示されたartifact-id>
```

成果物は`var/models/hina/<artifact-id>/`に置かれ、Git管理されません。公開モデルIDは常に
`hina`です。`artifact-id`はモデル名や世代番号ではなく、回答再現用の内容hashです。

importとdeployment promotionは意図的に分離しています。更新時は新artifactをimportし、
`make dev-inference HINA_ARTIFACT_ID=<artifact-id>`で専用workerのreadinessを確認してから
`make deploy-hina`で新規runの向き先を切り替えます。job streamもartifact別なので、旧workerは
旧artifactに固定されたrunを最後まで処理できます。promotion時にはコマンド自身が対象artifactの
worker readinessをRedisで検証します。初回導入も同じ順序です。promotion後はpinned workerをそのまま
利用でき、次回起動から`HINA_ARTIFACT_ID`を省略できます。
