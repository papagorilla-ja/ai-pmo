# 【Antigravity作業指示】⑤ ガバナンス監査強化

## 概要

ガバナンス監査の品質を強化する。Qdrant に `governance_rules` 専用コレクションを追加し、
10件の標準セキュリティ/コーディングルールをシーディングする。
`audit-document` API をこのコレクションで検索するよう切り替える。

**変更はバックエンド3ファイルのみ。フロントエンドは変更しない。**

---

## 前提知識（必ず読んでから作業すること）

### 既実装の確認ポイント

**`backend/app/config.py`**
- `QDRANT_COLLECTION_NAME: str = "ai_pmo_knowledge"` — 汎用知識コレクション（既存）
- `QDRANT_LESSONS_COLLECTION_NAME: str = "lessons_learned"` — 教訓コレクション（既存）
- 今回 `QDRANT_GOVERNANCE_COLLECTION_NAME` を追加する

**`backend/app/main.py`**
- `_SEED_LESSONS` + `_seed_lessons_learned()` パターンがすでに実装済み（L12-73）
- `lifespan` 関数内で `await _seed_lessons_learned()` を呼び出している（L393）
- **今回は同じパターンで** `_SEED_GOVERNANCE_RULES` + `_seed_governance_rules()` を追加する

**`backend/app/services/rag.py`**
- `add_documents(documents, metadatas, ids, collection_name=None)` — `collection_name` 引数対応済み
- `search(query, limit, collection_name=None)` — `collection_name` 引数対応済み
- `count_documents(collection_name=None)` — `collection_name` 引数対応済み

**`backend/app/api/v1/endpoints/pmo.py`（L96-180）**
- `POST /governance/audit-document` エンドポイントが実装済み
- 現在 `rag_service.search(payload.content, limit=3)` は **汎用コレクション** を検索している（collection_name 未指定）
- 今回 `collection_name=settings.QDRANT_GOVERNANCE_COLLECTION_NAME` を指定するよう変更する

**フロントエンド（変更不要・参考のみ）**
- `frontend/src/views/ArtifactsView.vue` — 「ガバナンス監査を実行」ボタンとインラインハイライト実装済み
- `store.runGovernanceAudit()` → `POST /pmo/governance/audit-document` を呼ぶ流れも実装済み

---

## 実装 1: config.py にガバナンスコレクション名を追加

### ファイル
`backend/app/config.py`

### 変更内容

現在の `QDRANT_LESSONS_COLLECTION_NAME` の行の直後に1行追加する。

**変更前（L18）：**
```python
QDRANT_LESSONS_COLLECTION_NAME: str = "lessons_learned"
```

**変更後：**
```python
QDRANT_LESSONS_COLLECTION_NAME: str = "lessons_learned"
QDRANT_GOVERNANCE_COLLECTION_NAME: str = "governance_rules"
```

---

## 実装 2: main.py にシードデータと初期化関数を追加

### ファイル
`backend/app/main.py`

### 変更内容

既存の `_SEED_LESSONS` リスト定義（L12）の**直前**に、以下のリストと関数を挿入する。
（`import uuid` は L1 で既にインポート済みのため追加不要）

**挿入するコード（`_SEED_LESSONS = [` の直前）：**

```python
_SEED_GOVERNANCE_RULES = [
    {
        "title": "認証情報の平文記述禁止",
        "content": (
            "社内セキュリティ規約 第3条: APIキー、データベース接続文字列、パスワード、JWTシークレットを"
            "ソースコード内に平文でハードコードしてはならない。"
            "すべての認証情報は環境変数（.env）またはシークレット管理サービスから取得すること。"
            "違反例: SECRET_KEY = 'hardcoded_secret'、DB_URL = 'postgresql://user:pass@localhost'"
        ),
        "category": "security",
        "severity": "CRITICAL"
    },
    {
        "title": "PostgreSQL接続プール必須",
        "content": (
            "コーディング標準 第5条: 本番環境のデータベース接続は必ず asyncpg + SQLAlchemy のコネクションプールを使用すること。"
            "pool_size=5、max_overflow=10 を基準とし、接続数制限（PostgreSQL の max_connections）に配慮すること。"
            "直接 psycopg2 を同期的に使用することを禁止する。"
        ),
        "category": "coding_standard",
        "severity": "HIGH"
    },
    {
        "title": "本番環境ログ記録の義務化",
        "content": (
            "運用規約 第8条: 本番環境では INFO レベル以上のログを必ず出力すること。"
            "例外発生時は logger.error() でスタックトレースを記録すること。"
            "print() によるデバッグ出力を本番コードに残してはならない。"
            "機密情報（パスワード、トークン）をログに出力することを禁止する。"
        ),
        "category": "operational",
        "severity": "HIGH"
    },
    {
        "title": "SQLインジェクション対策：パラメータ化クエリの必須使用",
        "content": (
            "セキュリティ規約 第7条: データベースクエリでは必ず ORM（SQLAlchemy）または"
            "パラメータ化クエリを使用すること。"
            "ユーザー入力を f-string や文字列結合でクエリに組み込むことを禁止する。"
            "違反例: query = f\"SELECT * FROM users WHERE name = '{user_input}'\""
        ),
        "category": "security",
        "severity": "CRITICAL"
    },
    {
        "title": "APIエンドポイントへの認証必須",
        "content": (
            "セキュリティ規約 第4条: すべての APIエンドポイント（GET含む）は"
            "`Depends(get_current_user)` を使用した JWT 認証を付与すること。"
            "認証が不要なエンドポイントは `/api/v1/auth/` 配下のみ許可。"
            "認証なし公開エンドポイントを追加する場合はセキュリティレビューを要する。"
        ),
        "category": "security",
        "severity": "HIGH"
    },
    {
        "title": "CORSの適切な設定（全オリジン許可の禁止）",
        "content": (
            "セキュリティ規約 第6条: CORS の `allow_origins` に `[\"*\"]` を指定することを禁止する。"
            "許可するオリジンは明示的にリストアップし、環境変数で管理すること。"
            "本番環境では `allow_credentials=True` と `allow_origins=[\"*\"]` の組み合わせは"
            "CORS仕様上エラーとなるため特に注意すること。"
        ),
        "category": "security",
        "severity": "HIGH"
    },
    {
        "title": "個人情報・機密データの暗号化義務",
        "content": (
            "情報セキュリティポリシー 第12条: メールアドレス、氏名、電話番号などの個人情報は"
            "保存時にハッシュ化または暗号化すること。"
            "パスワードは bcrypt または argon2 によるハッシュを必須とする。"
            "平文パスワードをデータベースに保存することを厳禁とする。"
        ),
        "category": "security",
        "severity": "CRITICAL"
    },
    {
        "title": "エラーハンドリング必須（詳細エラーの外部露出禁止）",
        "content": (
            "コーディング標準 第9条: 本番環境の API は 500 エラー時にスタックトレースや"
            "内部実装の詳細をレスポンスに含めてはならない。"
            "FastAPI では `HTTPException` を使用し、ユーザー向けメッセージのみを返すこと。"
            "未処理の例外は setup_exception_handlers で一括捕捉し、ログに記録すること。"
        ),
        "category": "coding_standard",
        "severity": "HIGH"
    },
    {
        "title": "DBマイグレーション前バックアップ義務",
        "content": (
            "運用規約 第15条: 本番データベースへの Alembic マイグレーション実行前に"
            "必ずフルバックアップ（pg_dump）を取得すること。"
            "マイグレーションスクリプトはステージング環境で本番相当データ量を使用して"
            "リハーサルを行ってから本番適用すること。"
            "ダウンタイムが発生する ALTER TABLE はメンテナンスウィンドウ内で実施すること。"
        ),
        "category": "operational",
        "severity": "HIGH"
    },
    {
        "title": "本番デプロイ前のコードレビュー必須",
        "content": (
            "開発プロセス規約 第2条: main/master ブランチへのマージには"
            "必ず1名以上のピアレビュー承認を必要とする。"
            "セキュリティに影響するコード変更（認証、暗号化、外部API連携）は"
            "PMO セキュリティチームのレビューを追加で必要とする。"
            "CI/CD パイプラインのテストが全て PASS していることをマージ条件とする。"
        ),
        "category": "process",
        "severity": "MEDIUM"
    },
]

async def _seed_governance_rules():
    from app.services.rag import rag_service
    col = settings.QDRANT_GOVERNANCE_COLLECTION_NAME
    if rag_service.count_documents(col) > 0:
        logger.info(f"Governance Rules collection '{col}' already seeded. Skipping.")
        return
    documents = [f"{r['title']}\n{r['content']}" for r in _SEED_GOVERNANCE_RULES]
    metadatas = [
        {
            "type": "governance_rule",
            "title": r["title"],
            "category": r["category"],
            "severity": r["severity"],
            "source": "seed"
        }
        for r in _SEED_GOVERNANCE_RULES
    ]
    ids = [str(uuid.uuid5(uuid.NAMESPACE_DNS, f"gov_rule_{r['title']}")) for r in _SEED_GOVERNANCE_RULES]
    registered = await rag_service.add_documents(documents, metadatas, ids, col)
    logger.info(f"Seeded {len(registered)} governance rules into '{col}' collection.")

```

### lifespan 関数への追加

`main.py` の `lifespan` 関数内、`await _seed_lessons_learned()` の**直後**に1行追加する。

**変更前（L392-395）：**
```python
    # Seed Lessons Learned Qdrant collection
    await _seed_lessons_learned()

    yield
```

**変更後：**
```python
    # Seed Lessons Learned Qdrant collection
    await _seed_lessons_learned()
    # Seed Governance Rules Qdrant collection
    await _seed_governance_rules()

    yield
```

---

## 実装 3: audit-document エンドポイントを governance_rules で検索

### ファイル
`backend/app/api/v1/endpoints/pmo.py`

### 変更内容

#### ① `from app.config import settings` のインポート確認

現在の pmo.py の冒頭に `from app.config import settings` が存在するか確認すること。
**存在する場合は変更不要。存在しない場合のみ** 以下の位置に追加する（L9 `from app.database import get_db` の下）：

```python
from app.config import settings
```

#### ② `rag_service.search()` 呼び出しを変更

現在の L107-116 を以下のように変更する。

**変更前：**
```python
    # 1. Query Qdrant governance guidelines
    search_hits = await rag_service.search(payload.content, limit=3)
    rules_context = ""
    if search_hits:
        rules_context = "\n---\n".join([hit["content"] for hit in search_hits])
    else:
        # Fallback dummy rules if vector search is empty
        rules_context = (
            "社内セキュリティ規約 第3条: 個人情報および認証情報は暗号化して保管すること。接続文字列をコード内に平文で記載してはならない。\n"
            "コーディング標準 第5条: 本番環境のデータベースは必ず PostgreSQL 16 以上のコネクションプールを使用すること。接続数制限に配慮せよ。"
        )
```

**変更後：**
```python
    # 1. Query governance_rules collection (dedicated security/coding standards)
    search_hits = await rag_service.search(
        payload.content[:500],  # 先頭500文字をクエリに使用（長文対策）
        limit=5,
        collection_name=settings.QDRANT_GOVERNANCE_COLLECTION_NAME
    )
    rules_context = ""
    if search_hits:
        rules_context = "\n---\n".join([
            f"[{hit['metadata'].get('severity','?')}] {hit['content']}"
            for hit in search_hits
        ])
    else:
        # Fallback rules if vector search is empty (Qdrant unavailable)
        rules_context = (
            "社内セキュリティ規約 第3条: 個人情報および認証情報は暗号化して保管すること。接続文字列をコード内に平文で記載してはならない。\n"
            "コーディング標準 第5条: 本番環境のデータベースは必ず PostgreSQL 16 以上のコネクションプールを使用すること。接続数制限に配慮せよ。\n"
            "セキュリティ規約 第7条: ユーザー入力は必ずパラメータ化クエリを使用すること。SQLインジェクション対策を徹底すること。"
        )
```

---

## 実装後の確認手順

### バックエンド確認

```bash
# バックエンド再起動
kill $(ps aux | grep "run.py" | grep -v grep | awk '{print $2}')
cd /Users/nhigashira/Documents/dev/ai-pmo/backend
./venv/bin/python run.py > backend.log 2>&1 &

# 起動ログ確認（governance_rules シーディングのログが出るか確認）
sleep 4 && grep -i "governance\|seeded" backend.log | tail -5

# 期待するログ:
# INFO: Seeded 10 governance rules into 'governance_rules' collection.
```

### API テスト

```bash
# 認証トークン取得
TOKEN=$(curl -s -X POST http://localhost:8008/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"nhigashira@example.com","password":"password"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# タスクID取得（audit用）
TASK_ID=$(curl -s http://localhost:8008/api/v1/tasks \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json; tasks=json.load(sys.stdin); print(tasks[0]['id'])")

# ガバナンス監査テスト（セキュリティ違反を含むコードを送信）
curl -s -X POST http://localhost:8008/api/v1/pmo/governance/audit-document \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"task_id\": \"$TASK_ID\",
    \"content\": \"SECRET_KEY = 'hardcoded_value'\nDB_URL = 'postgresql://user:pass@localhost/db'\nprint('debug log in production')\nquery = f\\\"SELECT * FROM users WHERE name = '{user_input}'\\\"\"
  }" | python3 -m json.tool
```

**期待結果:** `line_number` と警告 `content` を含む JSON 配列が返る。
LLM が `governance_rules` コレクションから取得したルールを参照して具体的な違反指摘が入ること。

```json
[
  {
    "line_number": 1,
    "content": "【セキュリティ警告】APIキーまたはシークレットが平文でハードコードされています。環境変数から読み込むよう変更してください。"
  },
  {
    "line_number": 4,
    "content": "【セキュリティ警告】SQLインジェクションのリスク: f-string でユーザー入力をクエリに埋め込んでいます。パラメータ化クエリを使用してください。"
  }
]
```

---

## 禁止事項

- `frontend/` 配下のファイルは一切変更しない（フロントエンドは実装済み）
- `backend/app/models/` 配下のモデルファイルは変更しない（マイグレーション不要）
- `backend/app/services/rag.py` は変更しない（`collection_name` 引数は既に対応済み）
- `_SEED_LESSONS` リストと `_seed_lessons_learned()` 関数は変更しない
- 新規ファイルは作成しない（既存ファイルの差分修正のみ）
