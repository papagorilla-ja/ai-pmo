# ③ Gitea連携 仕様書

最終更新: 2026-06-24  
対象: AI-PMO（FastAPI バックエンド + Vue3/Vuetify フロントエンド）  
前提: ② 階層モデル・① AIプランニング は実装済み。

---

## 0. 目的とスコープ

Gitea（ローカル自己ホスト Git サービス）と AI-PMO を連携させ、以下の 3 つを実現する。

| # | 機能 | 一言 |
|---|------|------|
| A | **進捗自動更新** | コミット/PR から WBS タスクの `status` / `actual_hours` を自動反映 |
| B | **教訓自己生成** | PR マージ時に LLM が lessons-learned を抽出し `Knowledge` へ自動登録 |
| C | **成果物 RAG 索引化** | リポジトリ内の Markdown 等を Qdrant へ定期クロールし、① AI プランニングの RAG に活用 |

---

## 1. 全体フロー

```
[Gitea] コミット push / PR merge
    │
    │ Webhook  POST /api/v1/webhooks/gitea
    ▼
[FastAPI: gitea_service]
    ├─ A) コミットメッセージ解析 → Task.status / actual_hours 更新（DB書き込み）
    ├─ B) PR説明 → LLM 教訓抽出 → Knowledge 登録 → Qdrant ベクトル化
    └─ C) (定期) Gitea API → リポジトリ .md クロール → Qdrant 索引更新

[フロントエンド]
    ├─ タスク詳細: Gitea リポジトリ紐付け設定UI
    └─ 進捗更新は自動反映（既存の tasks リスト / Gantt が再取得で反映）
```

---

## 2. 環境構築（Docker）

### 2.1 docker-compose.yml への追加

既存の `docker-compose.yml` に以下のサービスとボリュームを追記する。

```yaml
  gitea:
    image: gitea/gitea:latest
    container_name: ai_pmo_gitea
    restart: always
    environment:
      USER_UID: 1000
      USER_GID: 1000
      GITEA__database__DB_TYPE: sqlite3
      GITEA__server__ROOT_URL: http://localhost:3000/
      GITEA__server__HTTP_PORT: 3000
    ports:
      - "3000:3000"
      - "222:22"
    volumes:
      - giteadata:/data

volumes:
  giteadata:   # 既存の pgdata/qdrantdata に追記
```

### 2.2 設定値（config.py）

```python
# Gitea Settings
GITEA_BASE_URL: str = os.getenv("GITEA_BASE_URL", "http://localhost:3000")
GITEA_ADMIN_TOKEN: str = os.getenv("GITEA_ADMIN_TOKEN", "")      # Gitea管理者アクセストークン
GITEA_WEBHOOK_SECRET: str = os.getenv("GITEA_WEBHOOK_SECRET", "ai_pmo_webhook_secret")
```

### 2.3 初期セットアップ手順（実装外・運用手順）

1. `docker compose up gitea -d` で起動
2. ブラウザで `http://localhost:3000` → 管理者アカウント作成
3. 管理者設定 → アプリケーション → アクセストークン生成 → `.env` の `GITEA_ADMIN_TOKEN` に設定
4. 各リポジトリの設定 → Webhook → 追加:
   - URL: `http://host.docker.internal:8008/api/v1/webhooks/gitea`
   - シークレット: `GITEA_WEBHOOK_SECRET` の値
   - トリガー: **プッシュ** ＋ **プルリクエスト**

---

## 3. データモデル変更

### 3.1 Task モデルへの追加フィールド（Alembic マイグレーション）

```python
# backend/app/models/task.py に追加
gitea_repo: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
# "{owner}/{repo}" 形式。例: "tanaka/payment-service"
gitea_issue_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
# 紐付く Gitea Issue 番号（任意）
```

### 3.2 既存モデルへの影響

- `Knowledge.source` の取りうる値に `"gitea_pr"` / `"gitea_doc"` を追加（スキーマ変更なし、値の追加のみ）。
- `planning_service.py` の RAG フィルタ（source != "message" 判定）は `"gitea_pr"` / `"gitea_doc"` を **教訓として使用** するため除外しない。

---

## 4. API

### 4.1 `POST /api/v1/webhooks/gitea`（**認証なし・Webhook シークレット検証**）

Gitea から受信するイベントを処理する。JWT 認証ではなく HMAC-SHA256 署名検証を行う。

- ヘッダ: `X-Gitea-Event`（push / pull_request）、`X-Gitea-Signature`（HMAC-SHA256）
- シークレット検証失敗時: 403 を返してスキップ。
- 処理は `BackgroundTasks` で非同期実行（Webhook へのレスポンスは即座に 200）。
- レスポンス: `{ "received": true }`

### 4.2 `GET /api/v1/gitea/repos`（認証必須）

Gitea 管理者トークンを使い、利用可能なリポジトリ一覧を返す。タスク紐付けUI のセレクトボックス用。

- レスポンス: `[{ "full_name": "tanaka/payment-service", "description": "…", "html_url": "…" }]`
- Gitea 未設定（GITEA_ADMIN_TOKEN 未設定）の場合は `{ "repos": [], "configured": false }` を返す。

### 4.3 `PATCH /api/v1/tasks/{task_id}/gitea-link`（認証必須）

タスクに Gitea リポジトリ / Issue を紐付ける。

```json
{ "gitea_repo": "tanaka/payment-service", "gitea_issue_number": 42 }
```

- レスポンス: 更新後の Task オブジェクト。

### 4.4 `POST /api/v1/gitea/crawl`（認証必須・管理者のみ）

指定リポジトリの Markdown ファイルを即時クロールして Qdrant に索引化する（定期クロールの手動実行）。

```json
{ "repo": "tanaka/payment-service" }
```

---

## 5. バックエンドサービス（`services/gitea_service.py`）

### 5.1 Webhook 受信・振り分け（`handle_webhook`）

```
receive(event_type, payload)
├─ "push"          → handle_push(payload)
└─ "pull_request" + action=="closed" + merged==true → handle_pr_merged(payload)
```

### 5.2 push イベント処理（`handle_push`）

コミットメッセージを解析してタスクの進捗を更新する。

**タスク参照の記法（コミットメッセージ）:**

```
[PMO:{task_id_prefix8}] 決済画面の実装 #完了 [3h]
例: [PMO:a1b2c3d4] Stripe SDK 統合完了 #完了 [8h]
```

| 記法 | 説明 |
|------|------|
| `[PMO:{8文字以上のtask_id prefix}]` | 更新対象タスクの特定（必須） |
| `#完了` / `#done` / `#fix` / `#close` | status → `DONE` |
| `#進行中` / `#wip` / `#start` | status → `IN_PROGRESS` |
| `#レビュー` / `#review` | status → `REVIEW` |
| `[Nh]` / `[Nm]` | actual_hours に N時間/N分 を**加算** |

- task_id の前方一致で DB 検索（`LIKE '{prefix}%'`）。複数マッチは最初の 1 件。
- actual_hours は上書きではなく**加算**。
- `DONE` へ更新時、当該タスクの `actual_end` を更新日時で設定（フィールドがあれば）。
- ステータスキーワードなしコミットは actual_hours のみ加算（status 変更なし）。

### 5.3 PR マージ処理（`handle_pr_merged`）

**5.3.1 教訓自己生成（B）**

PR のタイトル＋本文が一定の長さ（> 100 文字）の場合、LLM に送信して教訓を抽出する。

プロンプト（system）:
```
あなたはプロジェクト管理の教訓(Lessons-Learned)抽出AIです。
GitのPRの内容から、今後のプロジェクトで活かせる教訓・注意点・ベストプラクティスを抽出してください。
出力は JSON 配列: [{"title": "…(30字以内)", "content": "…(200字以内)"}]
該当なければ空配列 []。解説不要、JSONのみ出力。
```

- LLM 出力を `_clean_json_string` でパースし、各エントリを `Knowledge` として保存。
  - `source = "gitea_pr"`
  - `confidence_score = 0.8`（固定）
  - `status = "ACTIVE"`
- 保存後、既存の `rag_service.add_knowledge(知識内容)` でベクトル化して Qdrant に追加。
- LLM 失敗・空配列はスキップ（ログ出力のみ）。フォールバック登録は行わない。

**5.3.2 リンクタスクの自動完了（A との連携）**

PR 本文に `[PMO:{task_id_prefix}]` の記載があれば、該当タスクを `DONE` に更新。

### 5.4 Markdown クロール（C）

`crawl_repository(repo: str)` として実装。

1. `GET {GITEA_BASE_URL}/api/v1/repos/{repo}/git/trees/HEAD?recursive=true` でファイル一覧取得。
2. 拡張子 `.md` / `.txt` / `.rst` のファイルを対象にフィルタ（最大 50 ファイル/リポジトリ）。
3. 各ファイルを `GET {GITEA_BASE_URL}/api/v1/repos/{repo}/raw/{path}?ref=HEAD` で取得。
4. 既存 `rag_service.search` で重複確認 → 未登録なら Knowledge 保存 ＋ Qdrant 追加。
   - `source = "gitea_doc"`
   - `content` は `{ファイルパス}\n{本文の先頭2000文字}`
5. nightly crawl の既存スケジューラ（あれば）に追加、なければ `crawl_repository` を手動 API（4.4）で呼び出す。

---

## 6. フロントエンド

### 6.1 タスク詳細ダイアログへの Gitea 連携セクション

既存のタスク詳細（編集）ダイアログに「Gitea 連携」セクションを追加する。

```
[ Gitea 連携 ]
リポジトリ: [▼ セレクトボックス (GET /gitea/repos 取得)] 
Issue番号:  [数値入力 任意]
[保存]
```

- Gitea 未設定（`configured: false`）の場合はセクション全体を非表示。
- 保存時: `PATCH /tasks/{id}/gitea-link`。

### 6.2 タスク一覧 / Gantt での Gitea 表示

- `gitea_repo` が設定されているタスクに Gitea アイコン（mdi-git）バッジを表示。
- クリックで `{GITEA_BASE_URL}/{gitea_repo}` を別タブで開く。

### 6.3 進捗更新の反映

Webhook による自動更新は DB への書き込みのみ。フロントは以下の既存ポーリング/再取得で反映：
- タスク一覧: 既存の `fetchTasks()` を手動リフレッシュ or 30秒自動リフレッシュ（任意）。
- Gantt: 既存の `fetchProjectWbsTree()` 再取得。

---

## 7. HMAC-SHA256 検証

Webhook の改ざん防止のため、受信時に署名を検証する。

```python
import hmac, hashlib

def verify_gitea_signature(body: bytes, signature: str, secret: str) -> bool:
    expected = "sha256=" + hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

---

## 8. 非機能要件

| 項目 | 方針 |
|------|------|
| Gitea 未設定時 | `GITEA_ADMIN_TOKEN` 未設定の場合、Webhook 受信以外の Gitea 機能は gracefully skip（エラーにしない）。フロントの Gitea セクションは非表示。 |
| LLM 呼び出し失敗 | 教訓抽出は失敗してもスキップ（Webhook レスポンスには影響させない）。`LLM_TIMEOUT_SECONDS`(300s) を使用。 |
| Gitea API 失敗 | クロール失敗はログ出力のみ、タスク進捗 Webhook のレスポンスはすでに 200 返済のためユーザー影響なし。 |
| セキュリティ | Webhook エンドポイントは JWT 不要だが HMAC 検証必須。署名なし/不一致は 403。 |
| トランザクション | タスク更新は既存の async SQLAlchemy セッションで 1 トランザクション。LLM 呼び出しは DB コミット後に非同期で実施。 |

---

## 9. 既存資産の流用

- `llm_service.get_response()` — 教訓抽出 LLM 呼び出し。
- `rag_service` の Knowledge 登録・Qdrant ベクトル化パターン。
- `_clean_json_string` — LLM JSON パース。
- `planning_service` の RAG フィルタ（`source != "message"`）— `"gitea_pr"` / `"gitea_doc"` は通過済み。
- Alembic マイグレーション（Task フィールド追加）。

---

## 10. MVPスコープ / 後続

**MVP（本フェーズ）:**
- Docker Gitea 環境構築
- Webhook 受信（push / PR マージ）→ タスク進捗自動更新（A）
- PR マージ → 教訓自己生成（B）
- リポジトリ Markdown クロール（C）
- タスク詳細での Gitea リポジトリ紐付け UI

**後続（スコープ外）:**
- Gitea Issue の自動作成（WBS → Issue 同期の逆方向）
- リアルタイム WebSocket 通知（進捗更新をフロントにプッシュ）
- 複数リポジトリの自動クロールスケジューラ

---

## 11. 受け入れ条件

1. `docker compose up` で Gitea が `http://localhost:3000` で起動する。
2. コミットメッセージに `[PMO:{id}] #完了 [2h]` を含めると、対象タスクの `status=DONE` / `actual_hours+=2` が反映される。
3. ステータスキーワードなしコミット（`[PMO:{id}] [1h]`）は actual_hours のみ加算、status 変更なし。
4. PR マージ時、本文 100 文字超の場合は Knowledge に教訓が登録され、analyze の RAG で参照される。
5. `POST /api/v1/gitea/crawl` でリポジトリの .md ファイルが Qdrant に索引化される。
6. HMAC 署名不正の Webhook リクエストは 403 で拒否される。
7. Gitea 未設定（GITEA_ADMIN_TOKEN 未設定）でも既存機能が壊れない。
