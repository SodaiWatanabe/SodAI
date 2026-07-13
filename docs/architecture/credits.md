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

Execution ── BillingIntent ── CreditReservation ── UsageRecord
                    │                 │
                    └─ 料金表snapshot └─ LotへのFEFO配賦
```

現在のHinaとAsuka 1は無料です。ただし、すべてのExecutionが料金表のsnapshotと使用量記録を
通るため、モデルを有料化しても会話・推論基盤を分岐させません。

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
`expires_at`はnullableなので、無期限クレジットと期限付きクレジットを同じ構造で扱えます。予約時は
期限が近いLotからFEFOで配賦し、予約時の配賦と確定時の消費順をDB制約でも同じ順序に固定します。
期限切れLotは新規予約へ使いません。APIの利用可能残高も期限内・未消費・未予約のLotから導出する
ため、期限切れ処理jobの実行前でも、表示額と実際に予約できる額がずれません。

期限切れ処理は台帳の`expire`取引として記録されます。予約中に期限を迎えた分は予約を維持し、
Execution終了時に利用分を確定した後、未使用分をユーザーへ戻さず`expired`へ移します。これにより
実行途中で予約原資が消えることも、有効期限を越えたクレジットが復活することもありません。

現段階では期限切れの自動スケジュールを有効化していません。運用コマンドを冪等にしてあり、将来は
同じServiceを定期jobから呼び出せます。

## 推論の予約と確定

Answerer catalogが各モデルの料金表を一意に所有します。Threadへの入力と同じDB transactionで、
Execution、料金表snapshot、最大額の予約、Outboxを作ります。残高不足なら全体をrollbackし、推論jobを
配送しません。

```text
queued
  └─ 最大料金を予約
       ├─ completed + token数あり ── 実料金を収益へ、差額を返却
       ├─ completed + token数なし ── 明示したfallback額を確定
       ├─ failed / timeout ────────── 全額返却
       └─ free ───────────────────── 使用量だけを記録
```

料金表は`revision`、固定額、入力token単価、出力token単価、最大額、計測不能時のfallback額を
Executionごとにsnapshotします。有料料金表ではfallback額を必須とし、workerの計測不具合が無料化へ
直結するfail-openを許しません。
後でcatalogの価格を変えても、開始済みの推論価格は変わりません。terminal eventの投影、予約確定、
使用量記録は同じtransactionでcommitされ、イベントの再配送でも二重請求しません。再試行は新しい
Executionなので、前の失敗予約を解放してから独立した料金snapshotと予約を持ちます。

## APIと運用

認証済みユーザーには次の読み取りAPIを提供します。

| Method | Path | 用途 |
| --- | --- | --- |
| `GET` | `/api/v1/credits` | 利用可能額と予約中額 |
| `GET` | `/api/v1/credits/transactions` | 不透明cursorによる取引履歴 |

Answerer APIの`pricing`は`kind`、`asset_code`、`scale`に加え、料金表revision、固定額、token単価、
最大額、計測不能時のfallback額を返します。Frontendと外部API clientはモデル名と同様に、価格情報も
APIを唯一の正本として扱います。

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
```

付与コマンドの再実行は同じ結果を返します。同じキーを別ユーザー、別金額、別期限へ使い回すと
拒否します。`credits-expire`は1回につき最大100 Lotを処理するため、`expired_lots=0`になるまで安全に
繰り返せます。

## データ寿命と将来拡張

認証主体や会話を削除しても金融監査記録は消しません。有料Executionは先に失敗または取消へ収束させ、
予約を確定しなければDBが削除を拒否します。
その後、ユーザー勘定からSodAIユーザーIDを外して匿名化し、
不変な勘定ID、仕訳、Lot、推論参照を保持します。推論参照は金融記録がThreadやExecutionの保存期間に
引きずられないよう、意図的に運用テーブルへの外部キーを持ちません。

今後の機能は台帳を書き換えず、入口と出口を追加します。

- クレジット購入: 決済providerの確定eventを冪等な`purchased` Lotへ変換する
- サブスクリプション: entitlement期間ごとに`subscription` Lotを発行する
- 貢献報酬・Human推論: 成果確定を`earned` Lotとして付与する
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

`test-integration`は実PostgreSQLの隔離DBで、複式不変条件、並行予約、冪等性、FEFO、期限切れ、
失敗・timeout解放、匿名化、履歴paginationに加え、孤立仕訳や誤ったLot由来を直接書き込む破壊系も
検証します。さらにmigrationを`0003 -> 0002 -> 0003`と往復し、Alembicのschema差分がないことを
確認します。`test-inference-e2e`は実HinaのGPU生成後に使用量記録と無料確定まで検証します。
