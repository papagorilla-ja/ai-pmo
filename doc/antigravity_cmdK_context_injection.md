# Antigravity 作業指示: 画面コンテキスト自動インジェクション (Cmd+K)

## 役割と制約

バックエンドエンジニアおよびフロントエンドエンジニアとして実装を行ってください。  
以下に指示された変更のみを実施してください。指示外の変更・リファクタ・新規ファイル作成は禁止です。

---

## 背景と目的

現在の Cmd+K コマンドパレットはコマンドテキストのみをバックエンドに送信している。  
「このスケジュールを最適化して」のような自然言語コマンドを入力した時、**ユーザーがどの画面を開いていて、どのプロジェクト・タスクを見ているか**がバックエンドには伝わらない。

これにより：
- ヒアリングコマンドで「どのタスクをヒアリングするか」を AI が推測するしかない
- 「このスケジュール」「このタスク」などの指示語が文脈なしに解釈される
- 画面ごとに適切なアクションの提案ができない

**目標**: Cmd+K 起動時に現在の画面名・プロジェクト ID・選択中タスク ID を自動収集してバックエンドに送信し、AI が画面コンテキストを理解した上で応答できるようにする。

---

## コンテキストペイロードの設計

フロントエンドが送信する `screen_context` の構造：

```json
{
  "screen": "GanttView",
  "screen_label": "ガントチャート",
  "project_id": "uuid-xxxx",
  "project_name": "プロジェクト Alpha",
  "task_id": "uuid-yyyy",
  "task_title": "フロントエンド要件定義とUXモック作成"
}
```

- `screen` / `screen_label`: Vue Router のルート名から自動取得
- `project_id` / `project_name`: Pinia ストアの `currentProjectId` + `portfolioProjects` から自動取得
- `task_id` / `task_title`: ガントチャート画面でタスクをクリック選択した場合のみ付与

---

## 変更対象ファイル（4ファイル）

1. `backend/app/api/v1/endpoints/command.py` — `screen_context` フィールド追加・活用
2. `frontend/src/store/project.js` — `selectedTaskId` state 追加・`executeCommand` 更新
3. `frontend/src/views/GanttView.vue` — `selectedTaskId` を store に同期
4. `frontend/src/components/CommandPalette.vue` — コンテキスト構築・UI バッジ・動的サジェスチョン

---

## 変更 1: backend/app/api/v1/endpoints/command.py

### 1-1. インポート追加（ファイル冒頭）

現在の `from typing import Dict, Any, List` を以下に置き換える：

```python
import uuid
from typing import Dict, Any, List, Optional
```

### 1-2. `CommandRequest` モデルを更新

現在の：
```python
class CommandRequest(BaseModel):
    command: str
```

以下に置き換える：
```python
class CommandRequest(BaseModel):
    command: str
    screen_context: Optional[Dict[str, Any]] = None
```

### 1-3. ヒアリングコマンドのブロックを全置換

現在の L30〜L64（`if "ヒアリング" in cmd_text or "hearing" in cmd_text:` ブロック全体）を以下に置き換える：

```python
    # 1. Trigger Hearing Command
    if "ヒアリング" in cmd_text or "hearing" in cmd_text:
        ctx = payload.screen_context or {}
        ctx_task_id = ctx.get("task_id")
        ctx_project_id = ctx.get("project_id")

        target_task = None

        # Priority 1: use task_id from screen context (user had a task selected)
        if ctx_task_id:
            try:
                res = await db.execute(select(Task).where(Task.id == uuid.UUID(ctx_task_id)))
                target_task = res.scalars().first()
            except Exception:
                pass

        # Priority 2: search by name mention in command text, filtered by project if available
        if not target_task:
            query = select(Task)
            if ctx_project_id:
                try:
                    query = query.where(Task.project_id == uuid.UUID(ctx_project_id))
                except Exception:
                    pass
            result = await db.execute(query)
            tasks = result.scalars().all()
            for t in tasks:
                if str(t.id) in cmd_text or t.title in cmd_text:
                    target_task = t
                    break
            # Fallback: first TODO/IN_PROGRESS task in project scope
            if not target_task and tasks:
                target_task = next(
                    (t for t in tasks if t.status in ("TODO", "IN_PROGRESS")),
                    tasks[0]
                )

        if target_task:
            ai_msg = Message(
                sender_type="AI_PMO",
                sender_name="AI_PMO",
                content=(
                    f"【アラートヒアリング】タスク「{target_task.title}」についてヒアリングを開始します。\n"
                    f"現在、予定期間から進捗遅れが懸念されています。完了までの『リアルな残工数（例: あと3時間、1.5人日）』をお答えください。"
                ),
                task_id=target_task.id
            )
            db.add(ai_msg)
            await db.commit()
            return {
                "success": True,
                "action": "TRIGGER_HEARING",
                "target_task_id": str(target_task.id),
                "message": f"タスク「{target_task.title}」への残工数ヒアリングを開始しました。"
            }
```

### 1-4. LLM フォールバックのシステムプロンプトを更新

現在の L94〜L105（`system_prompt` と `user_prompt` の定義部分）を以下に置き換える：

```python
    # Build screen context string for LLM
    screen_ctx_parts = []
    if payload.screen_context:
        ctx = payload.screen_context
        label = ctx.get("screen_label") or ctx.get("screen") or "不明"
        screen_ctx_parts.append(f"現在の画面: {label}")
        if ctx.get("project_name"):
            screen_ctx_parts.append(f"参照中プロジェクト: {ctx['project_name']}")
        if ctx.get("task_title"):
            screen_ctx_parts.append(f"選択中タスク: {ctx['task_title']}")
    screen_ctx_text = " / ".join(screen_ctx_parts)

    system_prompt = (
        "You are the AI-PMO Project Management Advisor. You have access to the project knowledge base "
        "indexed via semantic search.\n"
        + (f"User's current screen context — {screen_ctx_text}\n" if screen_ctx_text else "")
        + "Use the screen context to give a focused, relevant answer about what the user is currently looking at.\n"
        "Please answer the user's query clearly and concisely using the provided context if relevant.\n"
        "Answer in Japanese."
    )

    user_prompt = (
        f"Context from project records:\n{rag_context}\n\n"
        f"User Query: {cmd_text}\n"
        f"Answer:"
    )
```

---

## 変更 2: frontend/src/store/project.js

### 2-1. state に `selectedTaskId` を追加

現在の state（L62 付近）：
```javascript
    currentProjectId: null,
    wbsTreeRevision: 0
```

以下に置き換える：
```javascript
    currentProjectId: null,
    selectedTaskId: null,
    wbsTreeRevision: 0
```

### 2-2. `executeCommand` 関数を更新

現在の `executeCommand`（L295〜L307）：
```javascript
    async executeCommand(commandText) {
      try {
        const response = await axios.post(`${API_BASE}/command/execute`, {
          command: commandText
        })
        await this.fetchTasks()
        await this.fetchStandupSummary()
        return response.data
      } catch (err) {
        this.error = err.message
        return { success: false, message: `コマンド実行エラー: ${err.message}` }
      }
    },
```

以下に置き換える：
```javascript
    async executeCommand(commandText, screenContext = null) {
      try {
        const payload = { command: commandText }
        if (screenContext) payload.screen_context = screenContext
        const response = await axios.post(`${API_BASE}/command/execute`, payload)
        await this.fetchTasks()
        await this.fetchStandupSummary()
        return response.data
      } catch (err) {
        this.error = err.message
        return { success: false, message: `コマンド実行エラー: ${err.message}` }
      }
    },
```

---

## 変更 3: frontend/src/views/GanttView.vue

### 3-1. `selectedTaskId` を store に同期するウォッチャーを追加

**挿入位置**: L1704 の `watch(selectedProjectId, ...)` ブロックの直後、L1706 の `watch(() => store.portfolioProjects, ...)` の前に以下を追加する。

```javascript
// Sync selected task to store so CommandPalette can inject it as screen context
watch(selectedTaskId, (newId) => {
  store.selectedTaskId = newId
})
```

---

## 変更 4: frontend/src/components/CommandPalette.vue

### 4-1. `<script setup>` のインポート行を更新

現在の L78：
```javascript
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useProjectStore } from '../store/project'
```

以下に置き換える：
```javascript
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { useProjectStore } from '../store/project'
```

### 4-2. `store` 定義の直後に以下を追加

現在の L81〜L86 付近（`const store = useProjectStore()` の直後）：
```javascript
const store = useProjectStore()
const visible = ref(false)
```

以下に置き換える：
```javascript
const store = useProjectStore()
const route = useRoute()
const visible = ref(false)
```

### 4-3. `suggestions` の定数定義を削除して動的に変更

現在の L88〜L93（`const suggestions = [...]` の定義）を削除し、以下の `computed` に置き換える：

```javascript
const SCREEN_LABELS = {
  Dashboard: 'ダッシュボード',
  GanttView: 'ガントチャート',
  KnowledgeView: 'ナレッジ管理',
  ArtifactsView: '成果物管理',
  AdminView: 'システム管理',
}

const suggestions = computed(() => {
  const routeName = route.name
  if (routeName === 'GanttView') {
    const base = [
      '@AI このスケジュールを最適化して',
      '@AI 遅延タスクの残工数をヒアリングして',
      '@AI プランBを適用して',
    ]
    if (store.selectedTaskId) base.unshift('@AI このタスクをヒアリングして')
    return base
  }
  if (routeName === 'Dashboard') {
    return [
      '@AI EVM分析の根拠を詳しく説明して',
      '@AI 遅延タスクの残工数をヒアリングして',
      'タスク一覧の進捗をチェックして',
    ]
  }
  if (routeName === 'ArtifactsView') {
    return [
      '@AI この成果物のリスクを説明して',
      'タスク一覧の進捗をチェックして',
    ]
  }
  return [
    '@AI 遅延タスクの残工数をヒアリングして',
    '@AI 夜間クロールを起動',
    '@AI プランBを適用して',
    'タスク一覧の進捗をチェックして',
  ]
})
```

### 4-4. `buildScreenContext` 関数を追加

`suggestions` の computed 定義の直後に以下を追加する：

```javascript
const buildScreenContext = () => {
  const ctx = {
    screen: route.name || 'Unknown',
    screen_label: SCREEN_LABELS[route.name] || route.name || '不明',
  }
  if (store.currentProjectId) {
    const proj = store.portfolioProjects.find(p => p.id === store.currentProjectId)
    ctx.project_id = store.currentProjectId
    ctx.project_name = proj?.name || null
  }
  if (store.selectedTaskId) {
    const task = store.tasks.find(t => t.id === store.selectedTaskId)
    ctx.task_id = store.selectedTaskId
    ctx.task_title = task?.title || null
  }
  return ctx
}
```

### 4-5. `submit` 関数内でコンテキストを渡すよう更新

現在の L124：
```javascript
    const res = await store.executeCommand(cmdText.value)
```

以下に置き換える：
```javascript
    const res = await store.executeCommand(cmdText.value, buildScreenContext())
```

### 4-6. テンプレートにコンテキストバッジを追加

**挿入位置**: `<!-- Command suggestions -->` div（L25）の直前に以下を追加する：

```html
        <!-- Screen context badge -->
        <div v-if="store.currentProjectId || store.selectedTaskId" class="mb-3 d-flex align-center gap-2 flex-wrap">
          <v-chip size="x-small" color="info" label prepend-icon="mdi-map-marker">
            {{ SCREEN_LABELS[route.name] || route.name }}
          </v-chip>
          <v-chip
            v-if="store.currentProjectId"
            size="x-small"
            color="primary"
            label
            prepend-icon="mdi-folder-outline"
          >
            {{ store.portfolioProjects.find(p => p.id === store.currentProjectId)?.name || store.currentProjectId }}
          </v-chip>
          <v-chip
            v-if="store.selectedTaskId"
            size="x-small"
            color="secondary"
            label
            prepend-icon="mdi-checkbox-marked-outline"
          >
            {{ store.tasks.find(t => t.id === store.selectedTaskId)?.title || store.selectedTaskId }}
          </v-chip>
        </div>
```

---

## 動作確認手順

### 1. バックエンド起動確認

```bash
# バックエンドが起動していることを確認
curl -s http://localhost:8008/api/v1/health || echo "起動していない場合は python run.py で起動"
```

### 2. フロントエンド起動確認

```bash
# フロントエンドが起動していることを確認（port 5175）
curl -s -o /dev/null -w "%{http_code}" http://localhost:5175
```

### 3. API 単体テスト

```bash
TOKEN=$(curl -s -X POST http://localhost:8008/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"nhigashira@example.com","password":"password"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token',''))")

# ① コンテキストなし（従来動作の互換確認）
curl -s -X POST http://localhost:8008/api/v1/command/execute \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"command": "プロジェクトの状況を教えて"}' | python3 -m json.tool

# ② screen_context あり（ガントチャート・プロジェクト指定）
curl -s -X POST http://localhost:8008/api/v1/command/execute \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "command": "このスケジュールの課題を分析して",
    "screen_context": {
      "screen": "GanttView",
      "screen_label": "ガントチャート",
      "project_id": null,
      "project_name": "プロジェクト Alpha",
      "task_id": null,
      "task_title": null
    }
  }' | python3 -m json.tool

# ③ ヒアリングコマンド＋タスク context
# (TASK_ID は実際のDBのタスクIDに置き換えること)
TASK_ID=$(curl -s http://localhost:8008/api/v1/tasks/ \
  -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; tasks=json.load(sys.stdin); print(tasks[0]['id'])" 2>/dev/null)

curl -s -X POST http://localhost:8008/api/v1/command/execute \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"command\": \"@AI このタスクをヒアリングして\",
    \"screen_context\": {
      \"screen\": \"GanttView\",
      \"screen_label\": \"ガントチャート\",
      \"project_id\": null,
      \"project_name\": \"WBS Test Project\",
      \"task_id\": \"$TASK_ID\",
      \"task_title\": \"テストタスク\"
    }
  }" | python3 -m json.tool
```

### 4. 確認チェックリスト

- [ ] テスト①：`screen_context` なしで正常応答（後方互換）
- [ ] テスト②：`screen_context.project_name` が LLM の応答に反映されている（「プロジェクト Alpha のガントチャートを参照中」等）
- [ ] テスト③：`screen_context.task_id` を持つヒアリングコマンドで、指定タスクが `target_task_id` に返る
- [ ] フロントエンド: ガントチャート画面で Cmd+K を開くと画面名バッジが表示される
- [ ] フロントエンド: タスクをクリック後に Cmd+K を開くとタスク名バッジも表示される
- [ ] フロントエンド: ガントチャート画面ではサジェスチョンに「このスケジュールを最適化して」が含まれる
- [ ] フロントエンド: ダッシュボード画面では「EVM分析の根拠を詳しく説明して」が含まれる

---

## 禁止事項

- `backend/app/api/v1/endpoints/pmo.py` の変更は禁止
- `backend/app/models/` 配下の変更は禁止
- `frontend/src/views/` の CommandPalette 以外のページコンポーネントのロジック変更は禁止（GanttView.vue への watcher 追加のみ可）
- 新規ファイルの作成は禁止
- router/index.js の変更は禁止
