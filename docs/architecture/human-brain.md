# Human Brain MVP

SodAI ChatとSodAI Brainは、同じResponse/Execution/Thread基盤を別の入口から使う。
ChatではHuman Lite、Human Standard、Human ProへPromptを送り、BrainではHumanとして割り当てを受ける。

## 不変条件

- `human-lite`、`human-standard`、`human-pro`は変更しない公開IDで、表示名はcatalogから変更できる。
- Humanモデルの差は`required_human_rank`だけで表す。matcherはモデルIDで分岐しない。
- Prompt作成者と実回答者は別のUserでなければならない。
- 実回答者はThread memberにせず、active Claimを持つ間だけ割り当て文脈を読める。回答後は
  answered Claimを根拠に、回答時のsnapshotと自分の回答だけを履歴として読める。
- Thread上の回答者はHuman Lite/Standard/ProのModel Actorとする。実回答者UserはClaimだけに記録する。
- 回答本文は`thread_entries`、完了状態はResponseRequest/Executionを正本とし、Human用に複製しない。

## 最小データ

- `human_profiles`: Userの現在rankとrank変更時刻。
- `human_rank_events`: 昇降格時のpolicy revisionと判定根拠を保存する監査履歴。
- `human_tasks`: Human Executionの必要rankとFIFO時刻。
- `human_wait_entries`: 準備OKになったHumanのFIFO待機とreadiness lease。
- `human_claims`: Taskと実回答者の一時割当、skip/answer/expire履歴。

rankはLiteを1、Standardを2、Proを3とする。`make human-rank`は運営による
明示的な上書きとして残すが、通常のrankは回答実績から自動判定する。

Response作成時にHuman TaskはThreadの全Entryを既存`response_context_items`へsnapshotする。
AI生成用のturn/byte上限は適用しない。Human回答はAI回答と同じ完了関数でThreadEntryへ確定する。

## Human rank policy

昇降格条件はDBではなく`domain/human_ranks.py`のapplication policyに定義する。
DBは判定材料と現在rankだけを保持し、統計値の複製tableや条件設定tableは作らない。
判定は現在rankと同じrequested answererのClaimだけを対象にする。ProがLite価格で
回答した実績は、Pro価格の品質証明に使わない。

| 遷移 | 条件 |
| --- | --- |
| Lite → Standard | Lite回答20件、評価10件以上、高評価率80%以上、完了率90%以上 |
| Standard → Lite | 評価10件以上で高評価率65%未満、または15試行以上で完了率75%未満 |
| Standard → Pro | Standard回答50件、評価20件以上、高評価率90%以上、完了率95%以上 |
| Pro → Standard | 評価10件以上で高評価率75%未満、または15試行以上で完了率80%未満 |

完了率の分母は`answered + expired`とし、正当なskip、decline、依頼者cancelは除外する。
完了率は直近最大30試行、高評価率は直近最大20評価から計算し、評価のない回答は
高評価率の分母に入れない。昇格基準と降格基準の間はrankを維持し、
一回の判定で動くのは一段階だけとする。rank変更後は新しい価格帯の実績を改めて蓄積する。

回答完了、回答期限切れ、評価の設定・変更・解除時に、matcherと同じadvisory lock内で
profileを再判定する。待機中であればwait entryのrankも同じtransactionで更新する。
既に開始済みのClaimは開始時のモデル、料金、報酬を維持し、新しいrankは次のマッチから適用する。
評価はrankにのみ影響し、確定済み・将来の回答報酬額には影響しない。

## 思考の深さと実行期限

思考の深さはHuman固有の属性ではなく、AIとHumanが共有するResponseRequestの
`reasoning_effort`として保存する。公開値は`none`、`low`、`medium`、`high`、`xhigh`で、
同じResponseRequestを再試行するExecutionにも同じ値を引き継ぐ。各Answererが対応値と既定値を
catalogで宣言し、未対応値はリクエスト境界で拒否する。現在のAI Answererは`none`だけに対応する。
Human Answererは`none`を選択できず、モデルのrankに応じて思考の深さが累積で開放される。
Human Liteの既定値は`low`、Human StandardとHuman Proの既定値は`medium`とする。

Humanの回答可能時間は専用列へ保存せず、マッチ成立時に共通reasoning policyから導出して、
既存の`executions.deadline_at`へ絶対時刻を保存する。マッチング待機中は回答時間を消費しない。

| reasoning_effort | 表示名 | Human回答時間 | 利用可能モデル |
| --- | --- | --- | --- |
| `low` | 軽い | 2分 | Human Lite以上 |
| `medium` | 中程度 | 5分 | Human Standard以上 |
| `high` | 深い | 20分 | Human Standard以上 |
| `xhigh` | 非常に深い | 1時間 | Human Pro |

`human_claims.lease_expires_at`は接続生存確認、`executions.deadline_at`は回答期限であり、相互に
代用しない。どちらかが切れたClaimは`expired`へ閉じ、Executionをqueuedへ戻して別の適格Humanへ
再割当する。期限後の回答確定は拒否する。

Humanは割り当て時にClaimへ保存した`skip_allowed_until`までTaskをskipできる。Brainはこの境界に
達した時点で操作を辞退へ切り替え、APIも境界前の辞退と境界以降のskipを拒否する。skipと辞退は
それぞれ`skipped`、`declined`として区別して保存するが、どちらも下書きを破棄し、Executionを
queuedへ戻してHumanを待機列へ戻す。画面の再読み込みやreadiness更新では猶予を延長しない。

## Realtime matching

Task作成、readiness更新、skip、answerの後に同じmatcherを起動する。matcherはPostgreSQLの
transaction advisory lock内で、次の順に一組ずつ割り当てる。

1. 現在マッチ可能なTaskを`queued_at, execution_id`順に選ぶ。
2. そのTaskに適格なHumanを`ready_at, wait_entry_id`順に選ぶ。
3. 自分のPrompt、rank不足、同じTaskを過去にskip/expireしたHumanを除外する。

古いTaskが現在のHumanと非互換でも、新しい互換Taskを妨げない。DB commit後、Prompt側へ
`response.started/completed/queued/cancelled`、Brain側へ`human.assigned`または
`human.assignment.cancelled`を既存WebSocketで通知する。
Brainは10秒ごとの冪等な`PUT /human/readiness`と再接続時の`GET /human/state`で状態を復元する。

## 回答履歴

回答履歴はThreadへの事後的な閲覧権限ではない。`answered`状態の`human_claims`を回答者本人の
所有証明として、`response_context_items`の凍結文脈とExecutionの確定回答だけを返す。
元Thread ID、依頼者User ID、Claim ID、回答後に追加されたEntryは公開しない。別の回答者による
取得と、skipped/declined/expired/cancelled Claimからの取得は、存在しない回答と同じ404にする。

`GET /human/answers`は回答完了日時とExecution IDによるkeyset paginationで概要を返し、
`GET /human/answers/{execution_id}`は読み取り専用の詳細を返す。回答概要の表示文はThread titleを
参照せず、snapshot済みのinput Entryから生成する。履歴のための複製テーブルは作らない。

BrainのreadinessとClaim leaseはページではなく共通providerが管理する。回答待ちの間は履歴を
閲覧してもheartbeatを継続し、割り当てを受けたら回答画面へ戻る。active Claim中は下書きと
回答期限を守るため履歴への移動を許可しない。

Prompt作成者が停止した場合、同じadvisory lock内でactive Claimを`cancelled`へ閉じ、
実回答者を待機列へ戻す。Brainは一致するClaimの取消eventを受けた時点で、入力中の回答と
表示中の文脈を即座に破棄してから`GET /human/state`で再同期する。取消eventにはClaim IDと
理由だけを含め、回答本文や実回答者のUser IDはPrompt側へ公開しない。一度表示済みの文脈を
技術的に回収することはできないため、停止は以後の回答操作を無効化する境界として扱う。

現在のRealtimeHubはprocess-localなので、MVPのAPIは単一workerを前提とする。複数worker化では
event fan-outとticket storeを共有brokerへ移すが、DB matcherとClaimの一意制約はそのまま保つ。

## 拡張点

将来のSodAIモデルも同じ`reasoning_effort`からcompute budget、生成上限、Tool利用枠、料金を
application policyとして導出する。画像生成などのToolもTask requirementとAssignment payloadを
追加し、matcherへ能力条件を一つ足す。テキスト回答の正本やThread参加モデルは変えない。
評価ボーナスと需要表示は現在の範囲の外に置く。
