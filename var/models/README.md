# ローカルモデル成果物

このディレクトリには、検証済みの推論専用成果物を配置します。モデルの重みと
deploymentファイルはGit管理しません。

Hinaは`make import-hina`でBuilding-SLMのv1 SFTチェックポイントから取り込み、対象artifactへ
固定したworkerのready確認後に`make deploy-hina`で公開対象へ昇格します。
SodAIの実行時プロセスがBuilding-SLMを直接参照することはありません。
