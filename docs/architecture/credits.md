# クレジット基盤

## 目的

クレジットは画面上の残高カウンターではなく、SodAI内の価値移転を記録する会計境界です。推論、
貢献報酬、購入、サブスクリプション、キャンペーンを同じ台帳へ載せ、後から由来と消費先を説明
できることを優先します。

```text
付与元 ── CreditTransaction ── CreditPosting ── CreditAccount
              │                         │
              └─ CreditLot              ├─ 利用可能残高
                    │                    └─ 予約勘定
                    ├─ 由来
                    └─ 任意の有効期限

AI Execution ── BillingIntent ── CreditReservation ── UsageRecord
                         │                 │
                         └─ 料金表snapshot └─ LotへのFEFO配賦

Human Execution ───────────────── CreditReservation
                                          │
                                          └─ 回答者90% + 運営10%
```

Hinaはゲストを含む全ユーザーが無料で利用できます。Asuka 1は認証済みユーザー向けの有料モデルで、
成功した応答1回につき0.1 creditを消費します。どちらも同じExecution、料金表snapshot、使用量記録を
通るため、無料・有料で会話や推論の基盤を分岐させません。

HumanもAIと同じExecution、ResponseRequest、`reasoning_effort`を使います。料金はAnswerer catalogの
モデルと思考の深さから決まり、既存の予約・Posting・Lotで精算します。Human専用の料金テーブル、
予約テーブル、報酬残高は作りません。

## 金額表現

資産コードは`sodai-credit`、scaleは`1,000,000`です。APIとDBは浮動小数点を使わず、常に
最小単位の整数で金額を表します。

```text
1 credit = 1,000,000 subunits
```

この方式なら将来の細かな従量課金でも丸め誤差が生じず、価格表示だけをクライアント側でscaleに
従って整形できます。クレジットと日本円などの法定通貨は別資産です。購入時の決済記録を台帳へ
直接混ぜず、決済adapterが確定した結果だけをクレジット付与として記録します。

## 台帳の不変条件

残高を保存して更新する列はありません。残高は複式簿記のPosting合計から導出します。

- 1つのTransactionには2件以上のPostingがあり、合計は必ず0
- 発行元以外のユーザー・system勘定は負残高にならない
- Transaction、Posting、Lot、配賦、Lot消費は作成後に更新・削除しない
- 同じ冪等キーは同じ操作だけを再生し、条件が異なる再利用は拒否する
- Transactionの記録作成時刻と会計上の`effective_at`を分け、期限判定は後者を正本にする
- クレジット付与は必ず1つのLotを作り、由来と任意の有効期限を保持する
- 推論予約はユーザー勘定から予約勘定へ移し、確定時に収益・返却・失効へ一度だけ振り分ける
- Human回答の確定は予約額を回答者90%と運営10%へ同じTransactionで分割する
- Human回答者へのPostingは、同じTransactionを発行元とする90日間有効な`earned` Lotと一致する
- Grant仕訳とLot、予約仕訳と配賦元Lot、確定仕訳とLot消費は勘定・金額・参照先まで一致する
- 料金表snapshotと使用量記録はExecution削除後も残り、ユーザー帰属の匿名化以外は変更しない

これらはPythonだけでなく、遅延制約triggerと保護triggerによりPostgreSQLでも検証します。管理者の
手作業や将来の別サービスからの誤更新でも、不均衡や過剰消費をcommitできません。訂正は既存行の
編集ではなく、元取引を参照する新しい反対仕訳として追加します。

## アカウントとLot

`credit_accounts`にはユーザー勘定と、次のsystem勘定があります。

| system勘定 | 用途 |
| --- | --- |
| `issuance` | 新規クレジットの発行元 |
| `reserve` | 実行中推論の一時確保 |
| `revenue` | 完了した推論の消費先 |
| `expired` | 有効期限切れの消費先 |

Lotの`source_kind`は`admin`、`purchased`、`subscription`、`earned`、`promotional`を区別します。
`expires_at`はnullableなので、無期限クレジットと期限付きクレジットを同じ構造で扱えます。ただし
`earned`は例外なく`issued_at`から2160時間（90日）後を`expires_at`に設定します。期間は
アプリケーションポリシーを正本とし、Lotへ確定済みの期限を保存するため、期限テーブルは作りません。
ポリシー導入前の既存`earned`もmigrationで同じ期限へ揃えます。予約時は
期限が近いLotからFEFOで配賦し、予約時の配賦と確定時の消費順をDB制約でも同じ順序に固定します。
期限切れLotは新規予約へ使いません。APIの利用可能残高も期限内・未消費・未予約のLotから導出する
ため、期限切れ処理jobの実行前でも、表示額と実際に予約できる額がずれません。

期限切れ処理は台帳の`expire`取引として記録されます。予約中に期限を迎えた分は予約を維持し、
Execution終了時に利用分を確定した後、未使用分をユーザーへ戻さず`expired`へ移します。これにより
実行途中で予約原資が消えることも、有効期限を越えたクレジットが復活することもありません。

現段階では期限切れの自動スケジュールを有効化していません。運用コマンドを冪等にしてあり、将来は
同じServiceを定期jobから呼び出せます。

## オンデマンド無料枠

認証済みユーザーには20 creditsの無料枠があります。ただし登録日やカレンダー週を起点にはしません。
activeな無料枠がない状態で、クレジットを使うモデルへ有効なリクエストを発行した瞬間から168時間を
そのユーザーの1周期とします。残高を20へ上書きせず、開始時刻を`issued_at`、終了時刻を
`expires_at`に持つ`promotional` Lotを1つ発行します。通常のキャンペーン付与とは、発行Transactionの
`reference_type = free_credit_allowance`で区別します。

```text
activeな無料枠なし + 有料推論
  └─ リクエスト時刻から168時間の20-credit Lotを発行
       ├─ Asuka 1・Humanの予約と確定へFEFO配賦
       ├─ 期限後は次の有料推論まで休止
       └─ earned / adminなど他のLotには影響しない
```

`GET /credits`、Hina、guestのリクエストはLotを発行せず、時計も開始しません。有料リクエストではユーザーの
wallet行をロックし、DB時刻を取得してからactive Lotの確認、必要な発行、最大料金予約を行います。
Execution、Outboxを含む同じDB transactionでcommitするため、予約できずrollbackしたリクエストは
周期を開始しません。別Executionの並行リクエストもwallet lockで直列化され、二重発行しません。

周期は`[issued_at, expires_at)`の半開区間です。残量を使い切っても期限までは新しいLotを発行しません。
期限後は自動更新も未利用週の遡及発行もせず、次の有料推論時刻から新しい168時間を開始します。開始後に
推論が失敗した場合は予約だけを解放し、開始済み周期は維持します。無料枠の金額変更はactive Lotへ
遡及せず、次に開始するLotから適用します。

無料枠の未使用分は持ち越しません。一方、Human回答報酬で得る`earned` Lotや管理付与は別Lot
なので、それぞれの有効期限どおり保持されます。`earned`の90日は無料枠の周期から独立しています。
期限を跨いだ実行中予約は維持し、完了時に利用分を
確定して、期限を越えた未使用予約分を`expired`へ移します。

## 推論の予約と確定

Answerer catalogが各モデルの料金表を一意に所有します。Threadへの入力と同じDB transactionで、
Execution、料金表snapshot、最大額の予約、Outboxを作ります。残高不足なら全体をrollbackし、推論jobを
配送しません。

```text
queued
  └─ 最大料金を予約
       ├─ completed + token数あり ── 実料金を収益へ、差額を返却
       ├─ completed + token数なし ── 明示したfallback額を確定
       ├─ cancelled + input計測済み ─ 計測済み実料金を確定、差額を返却
       ├─ cancelled + input未計測 ─── 全額返却
       ├─ failed / timeout ────────── 全額返却
       └─ free ───────────────────── 使用量だけを記録
```

料金表は`revision`、固定額、入力token単価、出力token単価、最大額、計測不能時のfallback額を
Executionごとにsnapshotします。有料料金表ではfallback額を必須とし、workerの計測不具合が無料化へ
直結するfail-openを許しません。
後でcatalogの価格を変えても、開始済みの推論価格は変わりません。terminal eventの投影、予約確定、
使用量記録は同じtransactionでcommitされ、イベントの再配送でも二重請求しません。再試行は新しい
Executionなので、前の失敗予約を解放してから独立した料金snapshotと予約を持ちます。
停止時は、workerが入力token数を報告済みなら固定額と計測済みtoken分だけを確定し、まだ入力を
計測していなければ全額を返却します。部分回答の長さそのものを独立した料金指標にはしません。

現在のAI料金表は次のとおりです。Answerer APIは機械可読な料金表を返します。

| Answerer | 対象 | 料金 |
| --- | --- | --- |
| Hina | ゲスト・認証済み | 無料、回数制限なし |
| Asuka 1 | 認証済み | 成功1応答につき0.1 credit、失敗時は全額返却 |

Asuka 1の現在の疑似workerはtoken数を報告しないため、料金表`asuka-1-flat-v2`は固定額、最大予約額、
計測不能時fallback額をすべて0.1 creditとし、入力・出力token単価を0にしています。実モデルが計測値を
返すようになるまでは、見せかけのtoken従量課金を行いません。

## Humanの消費と報酬

Humanの料金表はDBではなくAnswerer catalogがモデルと思考の深さごとに所有します。待機中の価格変更を
扱うsnapshotは作らず、リクエスト時と回答時に同じアプリケーション設定を参照します。予約額そのものは
価値移転の事実として既存の`inference_credit_reservations`へ記録します。

| Humanモデル | 思考の深さ | 依頼者の消費 | 回答者報酬 | 運営取り分 |
| --- | --- | ---: | ---: | ---: |
| Human Lite | 軽い | 0.5 | 0.45 | 0.05 |
| Human Standard | 軽い | 0.75 | 0.675 | 0.075 |
| Human Standard | 中程度 | 1.5 | 1.35 | 0.15 |
| Human Standard | 深い | 3 | 2.7 | 0.3 |
| Human Pro | 軽い | 1 | 0.9 | 0.1 |
| Human Pro | 中程度 | 2 | 1.8 | 0.2 |
| Human Pro | 深い | 4 | 3.6 | 0.4 |
| Human Pro | 非常に深い | 12 | 10.8 | 1.2 |

金額はすべてsubunit整数で定義し、全組み合わせで10%を端数なく分割できることをアプリ起動時に検証
します。評価は基礎報酬へ影響しません。将来評価ボーナスを加える場合も、この確定取引を書き換えず、
独立した追加取引にします。

```text
Humanリクエスト作成
  requester -料金 ──> reserve

回答完了（回答保存と同じDB transaction）
  reserve -料金 ─────┬─> performer +90% ──> 90日間有効なearned Lot
                     └─> revenue   +10%

依頼者取消
  reserve -料金 ───────> requester +料金
```

スキップ、接続lease切れ、回答制限時間切れでは同じExecutionを再キューし、予約は保持します。依頼者が
取り消した場合は全額を返却します。回答本文の保存、Execution完了、回答者報酬、運営収益、
予約確定は1つのtransactionでcommitするため、回答だけ存在して報酬がない状態や二重報酬を作りません。
デプロイ前から待機中で予約を持たないHuman依頼だけは、遡及請求せず従来どおり無料で完了します。

## APIと運用

認証済みユーザーには次の読み取りAPIを提供します。

| Method | Path | 用途 |
| --- | --- | --- |
| `GET` | `/api/v1/credits` | 利用可能額、予約中額、activeな無料枠 |
| `GET` | `/api/v1/credits/transactions` | 不透明cursorによる取引履歴 |

Answerer APIの`pricing`は`kind`、`asset_code`、`scale`に加え、料金表revision、固定額、token単価、
最大額、計測不能時のfallback額を返します。Frontendと外部API clientはモデル名と同様に、価格情報も
APIを唯一の正本として扱います。各`reasoning_efforts`はHuman向けに`customer_charge`と
`performer_reward`も返します。表示の有無にかかわらず、価格と報酬の機械可読な契約として扱います。

`GET /credits`は読み取り専用で、無料枠を開始しません。応答は`private, no-store`です。取引履歴の
期限付きLotには`expires_at`を返し、Frontendは報酬獲得を含む履歴に有効期限の日時を表示します。
active時は総残高
とは別に`free_allowance`として`limit`、`used`、`reserved`、`remaining`、`starts_at`、`expires_at`を
返し、休止中は`free_allowance: null`を返します。Frontendのアカウントメニューは無料枠だけを表示し、
休止中は100%のバーと表示時点から168時間後のリセット期日、active時は残量に応じて減るバーと
サーバーが返した実際のリセット期日を「M月D日にリセットされます」の形式で表示します。creditの
絶対値や総残高は表示しないため、将来`earned`残高が
加わっても無料枠の表示へ混ざりません。

開発・初期運用ではホスト上の管理コマンドから付与します。`AMOUNT`は最小単位です。

```bash
make credits-grant \
  USER_ID=<SodAI user UUID> \
  AMOUNT=1000000 \
  IDEMPOTENCY_KEY=admin-20260713-<unique>

make credits-grant \
  USER_ID=<SodAI user UUID> \
  AMOUNT=1000000 \
  IDEMPOTENCY_KEY=campaign-20260713-<unique> \
  SOURCE_KIND=promotional \
  EXPIRES_AT=2026-08-01T00:00:00+09:00

make credits-expire

make credits-audit
```

付与コマンドの再実行は同じ結果を返します。同じキーを別ユーザー、別金額、別期限へ使い回すと
拒否します。`credits-expire`は1回につき最大100 Lotを処理するため、`expired_lots=0`になるまで安全に
繰り返せます。

`credits-audit`は台帳を書き込まず、全`earned` Lotの期限を90日ポリシーと突合します。また、現在も
Executionが存在するHuman予約について、依頼者、モデル、思考の深さ、回答者Claim、`earned` Lot、
10%の運営Postingをアプリケーション設定と突合します。
複式の釣り合い、Lot保存則、予約の一度きりの状態遷移はDB制約が中核として常時保証し、会話ドメインとの
意味的な整合性はこの読み取り専用監査へ分離します。不一致があれば`ERROR`を出力して終了コード1を
返します。

## データ寿命と将来拡張

認証主体や会話を削除しても金融監査記録は消しません。有料Executionは先に失敗または取消へ収束させ、
予約を確定しなければDBが削除を拒否します。
その後、ユーザー勘定からSodAIユーザーIDを外して匿名化し、
不変な勘定ID、仕訳、Lot、推論参照を保持します。推論参照は金融記録がThreadやExecutionの保存期間に
引きずられないよう、意図的に運用テーブルへの外部キーを持ちません。

今後の機能は台帳を書き換えず、入口と出口を追加します。

- クレジット購入: 決済providerの確定eventを冪等な`purchased` Lotへ変換する
- サブスクリプション: entitlement期間ごとに`subscription` Lotを発行する
- 評価ボーナス: 確定済みの基礎報酬とは別の追加取引として90日間有効な`earned` Lotを付与する
- Human Answerer: 現在の`Human Lite`、`Human Standard`、`Human Pro`に加え、将来のtierも独立した安定IDで追加する
- Asuka Thinking: Lite／Highなどを独立したAnswerer IDと料金表revisionで追加し、Asukaの主体IDは共有する
- 返金・取消: 元取引を参照する`reversal`取引を追加する
- 自動期限切れ: schedulerが既存の期限切れServiceを繰り返し実行する
- ブロックチェーン連携: 内部台帳を正本のままproof/exportを作り、必要ならdeposit/withdrawal adapterを追加する

ブロックチェーンを将来使う場合も、Threadや個人情報をchainへ載せません。まずPostgreSQLの取引IDと
整合する外部決済・settlement境界として導入し、chain停止、reorg、鍵紛失を会話や推論の可用性から
分離します。

## 検証

```bash
make test-integration
make test-inference-e2e
```

`test-integration`は実PostgreSQLの隔離DBで、複式不変条件、無料枠の休止・並行発行、正確な168時間、
長期未利用、rollback、報酬の90日期限、並行予約、FEFO、期限切れ、
失敗・timeout解放、匿名化、履歴paginationに加え、孤立仕訳や誤ったLot由来を直接書き込む破壊系も
検証します。さらにmigrationを`head -> 0002 -> head`と往復し、Alembicのschema差分がないことを
確認します。`test-inference-e2e`は実HinaのGPU生成後に使用量記録と無料確定まで検証します。
