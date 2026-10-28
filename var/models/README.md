# ローカルモデル成果物

このディレクトリには、検証済みの推論専用成果物を配置します。モデルの重みと
deploymentファイルはGit管理しません。

Asuka 1.1は`make import-asuka1`でBuilding-SLMのv2 SFTチェックポイントから取り込み、
対象artifactに固定したworkerのready確認後に`make deploy-asuka11`で公開対象へ昇格します。
公開deploymentは`asuka-1.1`、artifact directoryは`asuka-1/<artifact-id>/`です。
