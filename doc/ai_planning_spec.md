# ① AIプランニング 仕様書（タスク登録の自動化）

最終更新: 2026-06-22
対象: AI-PMO（FastAPI バックエンド + Vue3/Vuetify フロントエンド）
前提: ② 階層モデル（自己参照 Task ツリー / node_type / estimated_hours / template_type / `/projects/{id}/tree`）は実装済み。

---

## 0. 目的とスコープ

打ち合わせの**文字起こし等のテキスト**から、AIが **WBS（フェーズ／機能／タスク・成果物・担当候補・依存・粗見積り）を下案化**し、人が**ステージング画面で整理・承認**してから DB（②の階層）へ登録する機能。

- 入力手段は **テキスト貼り付けのみ**（音声→文字起こしは将来対応）。
- 核は「**AIが下案、人が承認**」。AI精度が完璧でなくても、人が整理する前提で実用に乗せる。
- 該当する担当者がいない／工数不足の場合は **要員提言（増員・採用の提案）** を出す。

---

## 1. 全体フロー

```
[1] テキスト入力        … 議事録/要件メモを貼り付け＋対象プロジェクト選択（既存 or 新規+テンプレ）
        ↓ POST /planning/analyze
[2] AIが下案を生成      … フェーズ/機能/タスクのツリー + 担当候補 + 依存 + 粗見積り
                          + 不足リソース提言 + 確認質問 + 予防タスク（教訓由来）
        ↓
[3] ステージング画面    … 下案をツリー表示。各項目を 採用/編集/却下。担当・工数・親・依存を調整
        ↓ POST /planning/apply
[4] WBSへ登録          … 承認済み下案を②の階層（Task ツリー）へ一括作成 → ガント/一覧へ反映
```

DB への書き込みは **[4] の承認後のみ**。[2][3] の間、下案はフロント状態として保持（MVPはサーバ非永続）。

---

## 2. AIが返す下案の構造（analyze レスポンス）

```jsonc
{
  "summary": "今回の打ち合わせから抽出したWBSの方針サマリー",
  "nodes": [
    {
      "temp_id": "n1",                  // 下案内の一時ID（apply時に実IDへ変換）
      "title": "要件定義",
      "description": "…",
      "node_type": "PHASE",             // PHASE/FEATURE/SPRINT/STORY/TASK
      "parent_temp_id": null,           // 階層（null=プロジェクト直下）
      "deliverable": "要件定義書",       // 成果物（任意）
      "estimated_hours": 0,             // サマリーは0（葉から積み上げ）
      "suggested_assignee": null,
      "dependencies": [],
      "confidence": 0.9
    },
    {
      "temp_id": "n2",
      "title": "ヒアリングと整理",
      "node_type": "TASK",
      "parent_temp_id": "n1",
      "deliverable": "ヒアリング議事録",
      "estimated_hours": 16,
      "suggested_assignee": { "resource_id": "<uuid|null>", "name": "山田", "reason": "要件定義経験+業務知識" },
      "dependencies": ["n_x"],          // temp_id 参照
      "confidence": 0.7
    }
  ],
  "staffing_recommendations": [          // 不足リソース提言
    { "skill": "決済API", "type": "NO_HOLDER", "detail": "該当スキル保持者が0名。要員採用/オンボードを推奨" },
    { "skill": "Vue3", "type": "CAPACITY_SHORTAGE", "detail": "保持者の工数が約40h不足。+1名 または 期間延長を推奨" }
  ],
  "clarifying_questions": [              // 曖昧点の逆質問
    "決済プロバイダーは確定していますか？（Stripe/他）"
  ],
  "preventive_tasks": [                  // 教訓（Lessons-Learned）由来の予防タスク提案
    { "title": "決済サンドボックス申請", "reason": "過去に発行2週間で遅延した教訓" }
  ]
}
```

---

## 3. データモデル

- **MVPは原則ステートレス**: analyze の結果はフロントが保持し、apply で②の `tasks`/`projects` に書き込む。新規テーブルは必須としない。
- （任意・後続）監査/再開用に軽量な `planning_drafts`(id, project_id, source_text, draft_json, status, created_at) を持たせてもよい。MVPでは見送り可。
- 既存モデルを利用: `Project`(template_type) / `Task`(parent_id, node_type, estimated_hours, assignee_name/type, dependencies) / `Resource`(skills_phase/domain/free, daily_working_hours, allocation_limit, working_days, available_from/to, system_role) / `Knowledge`(教訓)。

---

## 4. API

### 4.1 `POST /api/v1/planning/analyze`（認証必須）
- リクエスト:
  ```json
  { "source_text": "<貼り付けテキスト>",
    "project_id": "<uuid|null>",        // 既存プロジェクトに追加する場合
    "new_project": { "name": "…", "template_type": "PHASE_BASED|FEATURE_BASED|FLAT" } // 新規の場合
  }
  ```
- 処理: planning_service が LLM＋RAG＋Resource を使って §2 の下案JSONを生成して返す（**DBは書かない**）。
- レスポンス: §2 の構造。

### 4.2 `POST /api/v1/planning/apply`（認証必須）
- リクエスト: 承認・編集後の下案
  ```json
  { "project_id": "<uuid|null>",
    "new_project": { "name": "…", "template_type": "…" },   // project_id が無ければ新規作成
    "nodes": [ { temp_id, title, description, node_type, parent_temp_id, estimated_hours,
                 assignee_name, assignee_type, dependencies:[temp_id], planned_start?, planned_end? } ] }
  ```
- 処理:
  1. project_id 未指定なら `new_project` でプロジェクト作成（②の POST /projects 相当, テンプレスカフォールドは任意）。
  2. nodes を**親→子の順**で作成し、temp_id→実ID のマップを構築。`parent_id` は親の実IDで設定。
  3. `dependencies`(temp_id) を実IDに変換して task_dependency に登録。
  4. 担当（assignee_name/type）・estimated_hours・node_type を設定。日付未指定は当日基準の仮値。
  5. **管理者(system_role=管理者)を担当に指定された場合は拒否**（②の is_assignable ルール踏襲）。
- レスポンス: `{ success, project_id, created_count }`。

---

## 5. AI抽出サービス（backend `services/planning_service.py`）

既存 `llm_service` / `rag_service` / `orchestrator` の作法を流用。

1. **コンテキスト収集**
   - アサイン候補リソース: `Resource` から `is_assignable`（管理者除外・is_active）のみ抽出し、id/name/role/skills(phase/domain/free)/daily_working_hours/allocation_limit/working_days/available_from-to を LLM に渡す。
   - 既存プロジェクト構造（project_id 指定時）: 既存ツリーを渡し、追記先フェーズを判断させる。
   - 教訓: `rag_service.search(source_text)` で関連 Knowledge を取得 → preventive_tasks の素材に。
2. **プロンプト設計**（system）
   - 「あなたはPMOのプランニングAI。議事録から WBS を JSON ツリーで抽出する。各タスクに title/description/deliverable/node_type/parent/estimated_hours(粗)/dependencies、および候補リストから最適な担当(resource_id+理由)を割り当てる。曖昧点は clarifying_questions に。出力は生JSONのみ。」
   - フェーズ判定: テンプレートに応じて PHASE/FEATURE 配下へ配置するよう指示。
3. **担当 & 要員提言ロジック**（LLM出力後にサーバ側で検証・補強）
   - タスクの必要スキルに対し候補をスキル一致で選定。
   - **NO_HOLDER**: 該当スキル保持者が候補に0名 → staffing_recommendations に「採用/オンボード推奨」。
   - **CAPACITY_SHORTAGE**: 保持者はいるが、割当予定工数の合計 > 保有キャパ（daily_working_hours×稼働日×割当上限%）→「+N時間／増員／期間延長」を提言。
   - 算出は Resource の稼働情報＋②の estimated_hours ロールアップを利用。
4. **フォールバック**: LLM 接続不可時は、最小限の下案（フェーズ雛形＋「初期調査タスク」）＋エラー注記を返す（orchestrator の踏襲）。
5. JSON 抽出は `_clean_json_string` 相当でコードフェンス除去。

---

## 6. フロントエンド

### 6.1 導線・画面
- WBS画面に「**AIで計画を作成**」ボタンを追加（または新規ナビ「AIプランニング」）。クリックで**プランニング・ドロワー/ダイアログ**を開く。
- ステップUI（1画面 or 2ペイン）:
  - **入力ペイン**: テキストエリア（議事録貼り付け）＋ 対象プロジェクト選択（既存 / 新規+テンプレ）＋「解析する」ボタン。
  - **下案ペイン（ステージング）**: 下案ツリーを編集可能表示。

### 6.2 ステージング（差分レビュー）
- 下案ツリー: 各ノードに node_type バッジ、見積工数、担当(セレクト=**管理者除外**の候補)、依存、**確信度バッジ**（低いものは強調）。各行に **採用/編集/却下** トグル。
- 付帯セクション:
  - **不足リソース提言**（増員/採用の警告カード）
  - **確認質問**（チェックして残課題化、またはテキストで回答）
  - **予防タスク**（「WBSへ追加」ボタンで下案ツリーに挿入）
- フッター: 「**WBSへ登録**」→ 承認済みノードのみ `POST /planning/apply` → 成功後ガント/一覧を再取得。

### 6.3 store（`store/project.js`）
- 追加: `analyzePlanning(payload)`（POST /planning/analyze）、`applyPlanning(payload)`（POST /planning/apply → fetchProjectTree/fetchTasks 再実行）。

---

## 7. 既存資産の流用
- `llm_service`（LM Studio/OpenAI）, `orchestrator`（JSON抽出・フォールバックの作法）。
- `rag_service` / `Knowledge`（教訓→予防タスク）。
- `/resources`・`is_assignable`・スキル(phase/domain/free)・稼働情報（担当候補＋要員提言）。
- ②の階層作成（parent_id/node_type/estimated_hours/dependencies）と `/projects`・`/tasks`。
- Plan-First の思想（DRAFT→承認）をプロジェクト計画レベルに拡張。

---

## 8. MVPスコープ / 後続
- **MVP**: テキスト入力 → analyze（タスク/フェーズ配置/担当候補/粗見積り/依存）→ ステージング（採用/編集/却下）→ apply。要員提言・確認質問・教訓予防タスクを含む。
- **後続**: 音声→文字起こし、下案のサーバ永続（保存/再開）、対話的リファイン（追記指示）、見積りRAG（過去実績からの工数提示）。

---

## 9. 受け入れ条件
1. テキストを貼り付け「解析」すると、フェーズ/タスクのツリー下案が返り、画面にツリー表示される（DBは未変更）。
2. 各下案を編集/却下でき、担当セレクトに**管理者が出ない**。
3. 該当スキル保持者がいない/工数不足のとき、**要員提言**が表示される。
4. 教訓由来の予防タスクが提案され、ワンクリックで下案に追加できる。
5. 「WBSへ登録」で、承認済みノードが②の階層（parent_id/node_type/estimated_hours/依存）に作成され、ガント/一覧に反映される。
6. 管理者を担当指定した apply は 400 で拒否される。
7. LLM 接続不可時もフォールバック下案が返り、画面が壊れない。

## 10. スコープ外（本フェーズ）
- 音声文字起こし、下案のサーバ永続/再開、対話的リファイン。
- ③ Gitea 連携・成果物レビュー・ナレッジ自己生成（次フェーズ）。
- 開発標準/業務知識のRAG登録（③/RAGフェーズで扱う。本フェーズは教訓検索の流用まで）。
