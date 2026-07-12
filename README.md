# SodAI

SodAI は FastAPI バックエンドと Next.js フロントエンドを分離して開発する AI アプリケーションの土台です。

## 構成

```text
SodAI/
├── backend/
│   ├── app/
│   │   ├── core/       # 設定・共通基盤
│   │   ├── routers/    # HTTP エンドポイント
│   │   ├── schemas/    # API 入出力モデル
│   │   ├── services/   # ユースケース・ビジネスロジック
│   │   └── main.py     # FastAPI エントリーポイント
│   └── tests/
└── frontend/
    └── src/
        ├── app/        # Next.js App Router
        ├── components/ # UI コンポーネント
        └── lib/        # API クライアントなど
```

## セットアップ

Python 3.10 以上と Node.js 20.9 以上を使用します。

```bash
make install
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

## 開発サーバー

2つのターミナルでそれぞれ起動します。

```bash
make dev-backend
```

```bash
make dev-frontend
```

- Frontend: <http://localhost:3000>
- API: <http://localhost:8000>
- OpenAPI UI: <http://localhost:8000/api/v1/docs>

## 検証

```bash
make check
```
