# Antigravity 実装指示: ロール・リソース管理の是正

本書は `doc/role_resource_management_spec.md`（仕様整理書）に基づく実装指示である。
スタック: FastAPI(async SQLAlchemy 2.0 / asyncpg) + Vue3/Vuetify + Pinia + Postgres。DBスキーマは起動時 `app/main.py` の lifespan 内 `Base.metadata.create_all` で生成（alembic 不使用）。

## 前提・厳守事項
- 既存の動作中機能（ガント、プランB、ヒアリング、RAGクロール、成果物レビュー）を壊さないこと。
- 各フェーズ完了ごとに該当エンドポイント/画面の動作を実際に確認し、結果を報告すること。
- 既定値（初期パスワード・トークン有効期限）は本書の指定に従う。変更が必要なら理由を添えて確認すること。

---

## フェーズ0: 依存・設定の追加

1. `backend/requirements.txt` に追記:
   - `passlib[bcrypt]`
   - `pyjwt`
2. `backend/app/config.py` の `Settings` に追加（環境変数化）:
   - `SECRET_KEY: str = os.getenv("SECRET_KEY", "<dev用ランダム文字列>")`
   - `ACCESS_TOKEN_EXPIRE_HOURS: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "12"))`
   - `ALGORITHM: str = "HS256"`
3. `pip install -r requirements.txt` が通ることを確認。

---

## フェーズ1: データモデル/スキーマ変更（resources）

対象: `backend/app/models/resource.py`, `backend/app/schemas/resource.py`

1. `Resource` モデルに追加・変更:
   - 追加 `password_hash: Mapped[str] = mapped_column(String(255), nullable=False, default="")`
   - 変更 `email` を `unique=True, index=True, nullable=False` に
   - 追加（任意）`last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)`
2. スキーマ:
   - `ResourceResponse` には **`password_hash` を絶対に含めない**（現状のまま `password_hash` フィールドを持たないこと）。
   - `ResourceCreate` / `ResourceUpdate` に `password: Optional[str] = None`（平文・任意）を追加。サーバ側でハッシュ化して `password_hash` に保存し、`password` は永続化しない。
3. **DBマイグレーション**（既存 `resources` テーブルがある前提。`create_all` では列追加されない）:
   - 非破壊で以下を Postgres(`ai_pmo_postgres`) に適用する手順を実装/手順書化:
     ```sql
     ALTER TABLE resources ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255) NOT NULL DEFAULT '';
     ALTER TABLE resources ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ NULL;
     CREATE UNIQUE INDEX IF NOT EXISTS ix_resources_email ON resources (email);
     ```
   - 既存行の `password_hash` を初期パスワードのハッシュで backfill（下記フェーズ5のシード値と一致させる）。
   - 開発環境で作り直しが許容される場合は「`resources` テーブル drop → 再起動で再シード」でも可。どちらを採ったか報告すること。

---

## フェーズ2: 認証コア（JWT + パスワード）

新規: `backend/app/core/security.py`

1. パスワード:
   - `pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")`
   - `hash_password(plain) -> str`, `verify_password(plain, hashed) -> bool`
2. JWT:
   - `create_access_token(subject: str, system_role: str) -> str`（`sub`, `system_role`, `exp` を含む。`settings.SECRET_KEY` / `ALGORITHM` / `ACCESS_TOKEN_EXPIRE_HOURS` 使用）
   - `decode_access_token(token) -> dict`（失敗時は例外）
3. 認証依存（`backend/app/core/deps.py` か `security.py`）:
   - `get_current_user(authorization: str = Header(None), db = Depends(get_db)) -> Resource`
     - `Authorization: Bearer <token>` を解析→`sub` から `Resource` を取得。
     - トークン不正/期限切れ/ユーザー不在/`is_active=False` は `401`。
   - `require_roles(*roles)` のような依存ファクトリ（権限不足は `403`）。

---

## フェーズ3: 認証エンドポイント

新規: `backend/app/api/v1/endpoints/auth.py`、`backend/app/api/router.py` に登録（prefix `/auth`, tags `["auth"]`）。

1. `POST /api/v1/auth/login`
   - body: `{ "email": str, "password": str }`
   - 処理: email で `Resource` 検索 → `verify_password` → `is_active` 確認 → `create_access_token`。
   - 成功: `{ "access_token": <jwt>, "token_type": "bearer", "user": { id, name, email, system_role, role } }`、`last_login_at` 更新。
   - 失敗（不一致 / 無効アカウント）: `401`、メッセージ「メールアドレスまたはパスワードが正しくありません。」（無効アカウントは「このアカウントは無効化されています。」）。
2. `GET /api/v1/auth/me`（認証必須）: 現在ユーザーの `{ id, name, email, system_role, role }` を返す。
3. `/auth/login` は未認証許可。それ以外の保護対象APIは `get_current_user` を要求。

---

## フェーズ4: 既存APIの権限判定をトークン由来へ置換

対象: `backend/app/api/v1/endpoints/resources.py`、`backend/app/api/v1/endpoints/pmo.py` 他、`x_user_role` を使う箇所すべて。

1. `resources.py`:
   - すべての `x_user_role: str = Header(None)` を廃止し、`current: Resource = Depends(get_current_user)` に置換。権限判定は `current.system_role`。
   - `clean_role_header` のヘッダ→日本語ロール変換ロジックは不要化（トークンの `system_role` は最初から日本語値）。`mask_resource_cost` は `current.system_role` を引数に取る形へ修正（マスク仕様は維持: メンバーは `hourly_cost_jpy=0`）。
   - 権限（仕様書の権限マトリクス）:
     - 作成/削除/`system_role`・`is_active` 変更/パスワード設定(他者): `管理者` のみ
     - 一般項目編集: `管理者` or `マネージャ`
     - 本人のパスワード変更: 本人可
2. `pmo.py` のアロケーション操作・その他ヘッダ参照箇所も同様に `get_current_user` ベースへ統一。
3. 認証必須化: 既存の保護すべきエンドポイントに `get_current_user` 依存を付与（ガント等の参照系も認証必須でよい。`/auth/login` のみ除外）。

---

## フェーズ5: 管理者のアサイン禁止（UI候補除外 + バックエンド拒否）

共通ヘルパ（例 `resources.py` または `core`）:
```python
def is_assignable(resource: Resource) -> bool:
    return resource.system_role != "管理者" and resource.is_active
```

1. **候補返却系で管理者除外**:
   - `GET /api/v1/resources/search`（NLP推薦）: LLM へ渡す候補リスト生成前に `is_assignable` で絞り込む（管理者を入力からも結果からも除外）。フォールバックのキーワード一致でも同様。
2. **アサイン確定系で拒否（400）**:
   - `ResourceAllocation` の作成/更新（`pmo.py` の `apply_allocation_shift` 等、`resource_id` を扱う箇所）で、対象 `Resource.system_role == "管理者"` の場合 `400`、メッセージ「システム管理者はリソースとしてアサインできません。」。
   - 将来タスク担当をリソース参照化する場合も同ヘルパで拒否（本対応では `assignee_name` 自由入力は現状維持）。
3. AIワーカー（`system_role=メンバー`）は除外対象外＝従来どおりアサイン可。

---

## フェーズ6: シード更新

対象: `backend/app/main.py`（lifespan 内シード）。

1. シードする各 `Resource` に `password_hash` を設定（`hash_password` 使用）。初期パスワード（開発用・既定）:
   - 全シードユーザー共通で `password`（※本番不可。デモ用。変更要望あれば差し替え）。
2. シードユーザーの email がすべて一意であることを確認。
3. シード対象: `nhigashira`(管理者) / Manager(マネージャ) / Frontend Engineer(メンバー) / AI Worker(メンバー)。

---

## フェーズ7: フロントエンド — 認証導入と切替廃止

1. **store**（`frontend/src/store/project.js`）:
   - axios interceptor: `X-User-Id` / `X-User-Role` の付与を**廃止**し、`token` があれば `Authorization: Bearer <token>` を付与。
   - state: `token`（localStorage 連携）, `currentUser`, `currentRole`（**読み取り専用**。直接 set するUIは作らない）。
   - 既存 `setCurrentUser`（切替用）アクションを**削除**。
   - 追加アクション: `login(email, password)`（成功でtoken/ユーザー保存）、`logout()`（token破棄・state クリア）、`fetchMe()`（再読込時の復元）。
   - 401 をハンドルする response interceptor を追加し、`logout()` → `/login` 遷移。
2. **ログイン画面**（新規 `frontend/src/views/Login.vue`、ルート `/login` を `router/index.js` に追加）:
   - メール/パスワード入力、ログインボタン、エラー表示。既存のグラスモーフィズム調デザインに合わせる。
   - ログイン済みで `/login` アクセス時はダッシュボードへ。
3. **ルーターガード**（`router/index.js`）:
   - `beforeEach`: token 無しなら `/login` へリダイレクト（`/login` 自身は除外）。リロード時は `fetchMe()` で復元。
4. **サイドバー**（`frontend/src/App.vue`）:
   - 「操作ユーザー切替」セレクト・`selectedUser`・`userOptions`・`setCurrentUser` 連動を**完全削除**。
   - 代わりに**ログイン中ユーザー表示**（氏名 + システム権限バッジ、読み取り専用）+ **ログアウトボタン**を配置。
   - 「システム管理」ナビ項目は `currentRole` に応じ表示制御（メンバーには非表示）。

---

## フェーズ8: フロントエンド — 管理者アサイン除外 & UI整理

対象: `frontend/src/views/AdminView.vue`, `frontend/src/views/GanttView.vue`

1. **NLP推薦結果・アサイン候補UI**: `system_role=管理者` を表示しない（バックエンドが除外済みでも、二重防御でフロントもフィルタ）。
2. **リソース一覧（AdminView）**: 管理者も表示しつつ「アサイン対象外」を視覚化（バッジ/淡色/注記）。
3. **用語整理**: 「役割（職種）」=`role`、「システム権限」=`system_role` とラベルを明確化。
4. **パスワード設定欄**をリソース編集ダイアログに追加（管理者は任意ユーザー、本人は自分のみ）。空欄なら変更しない。
5. 権限制御（`canCreateResource` 等）の判定元を、ログイン由来の `store.currentRole` に統一（既存 computed のままで可、値の出所が切替UIでなくログインになる）。
6. `GanttView.vue` のタスク担当はスコープ外（`assignee_name` 自由入力維持）。ただしリソース選択UI化する場合は管理者除外を適用する旨をコメントで明記。

---

## 受け入れ条件（実装後に実機確認し報告）

1. 「操作ユーザー切替」UIが存在しない。サイドバーはログイン中ユーザー表示 + ログアウトのみ。
2. 未認証で各画面にアクセスすると `/login` にリダイレクトされる。
3. 正しい email+password でログインでき、`system_role` がセッション中固定（変更手段が無い）。
4. 誤パスワード / `is_active=false` はログイン不可（401）。
5. クライアントが `X-User-Role` を送っても権限は変わらない（トークン由来判定／詐称不可）。
6. `GET /resources/search` の結果に `system_role=管理者` が出ない。
7. `ResourceAllocation` 等で管理者 `resource_id` を指定すると 400。
8. リソース一覧では管理者も表示され「アサイン対象外」が判別できる。
9. メンバーは `hourly_cost_jpy` が 0 マスク表示（既存挙動維持）。
10. AIワーカー（メンバー）は従来どおりアサイン候補に出る。

### 確認コマンド例
```bash
# ログイン → トークン取得
curl -s -X POST http://localhost:8008/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"nhigashira@example.com","password":"password"}'
# 取得トークンで /me
curl -s http://localhost:8008/api/v1/auth/me -H 'Authorization: Bearer <TOKEN>'
# 管理者がNLP候補に出ないこと
curl -s "http://localhost:8008/api/v1/resources/search?query=設計できる人" -H 'Authorization: Bearer <TOKEN>'
```

---

## スコープ外（実装しない）
- タスク `assignee_name` のリソースFK化、`resource_name`/`resource_id` の名称二重管理解消。
- 招待メール/パスワードリセットメール、リフレッシュトークン、監査ログ。
