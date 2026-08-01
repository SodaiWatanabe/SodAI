# ローカルモデル成果物

このディレクトリには、検証済みの推論専用成果物を配置します。モデルの重みと
deploymentファイルはGit管理しません。

Hinaは`make import-hina`でBuilding-SLMのv1 SFTチェックポイントから取り込み、対象artifactへ
固定したworkerのready確認後に`make deploy-hina`で公開対象へ昇格します。
Asuka 1は`make import-asuka1`でBuilding-SLMのv2 SFTチェックポイントから取り込み、
`make deploy-asuka1`で公開対象へ昇格します。両モデルは独立したartifact directoryとworkerを持ちます。
SodAIの実行時プロセスがBuilding-SLMを直接参照することはありません。
