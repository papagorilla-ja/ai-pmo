# Antigravity 作業指示: Giteaリポジトリクロールをコマンドパレットから実行できるようにする

## 背景と目的

現在 `@AI クロール` は内部DBのタスク・メッセージを再インデックスするだけで、
Giteaリポジトリ内の `.md/.txt/.rst` ファイルをクロールする機能が
コマンドパレット（Cmd+K）から呼び出せない。

また Gitea には複数リポジトリが存在しうるため、クロール対象を選択できる必要がある。

**実装するUXフロー:**
```
ユーザーが「@AI Giteaクロール」を送信
  ↓
バックエンドが Gitea API からリポジトリ一覧を取得
  ↓
フロントエンドがリポジトリ名のチップ（ボタン）を表示
  ↓
ユーザーがチップをクリック
  ↓
「@AI Giteaクロール nhigashira/ai-pmo-local」が自動送信
  ↓
クロール実行 → 「X件のドキュメントを登録しました」と表示
```

---

## 変更ファイル一覧

| # | ファイル | 変更種別 |
|---|---|---|
| 1 | `backend/app/api/v1/endpoints/command.py` | 修正 |
| 2 | `frontend/src/components/CommandPalette.vue` | 修正 |

---

## 変更1 — `backend/app/api/v1/endpoints/command.py`

### インポートの追加（ファイル先頭）

現在の imports に `re` と `gitea_service` を追加する。

**現在 (L1-13):**
```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from sqlalchemy import select

from app.database import get_db
from app.models.task import Task
from app.models.message import Message
from app.services.llm import llm_service
from app.services.rag import rag_service
from app.services.risk_engine import risk_engine_service
```

**変更後:**
```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import uuid, re
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from sqlalchemy import select

from app.database import get_db
from app.models.task import Task
from app.models.message import Message
from app.services.llm import llm_service
from app.services.rag import rag_service
from app.services.risk_engine import risk_engine_service
from app.services.gitea_service import gitea_service
```

### Giteaクロールコマンドブロックの追加

既存の「2. Nightly Crawl Command」ブロック（L89〜L96）の**直前**に以下を挿入する。

```python
    # 2-A. Gitea Repository Crawl Command
    if "giteaクロール" in cmd_text.lower() or "gitea crawl" in cmd_text.lower():
        # リポジトリ名が含まれていれば即クロール: "owner/repo" パターンで検出
        repo_match = re.search(r'([a-zA-Z0-9_\-\.]+/[a-zA-Z0-9_\-\.]+)', cmd_text)
        if repo_match:
            repo = repo_match.group(1)
            result = await gitea_service.crawl_repository(repo, db)
            crawled = result.get("crawled", 0)
            return {
                "success": True,
                "action": "GITEA_CRAWL",
                "message": f"リポジトリ「{repo}」のクロール完了: {crawled}件のドキュメントをナレッジベースに登録しました。"
            }
        else:
            # リポジトリ名なし → 一覧を返してフロントに選択させる
            repos_data = await gitea_service.list_repos()
            repos = repos_data.get("repos", [])
            if not repos:
                return {
                    "success": False,
                    "action": "GITEA_CRAWL",
                    "message": "Giteaに接続できないか、リポジトリが存在しません。GITEA_ADMIN_TOKENの設定を確認してください。"
                }
            return {
                "success": True,
                "action": "SELECT_REPO",
                "repos": repos,
                "message": "クロールするリポジトリを選択してください:"
            }
```

### 既存クロールブロックのメッセージ改善

既存の「2. Nightly Crawl Command」ブロック（現在 L89-96）も結果を表示するよう修正する。

**現在:**
```python
    # 2. Nightly Crawl Command
    if "crawl" in cmd_text.lower() or "クロール" in cmd_text:
        crawl_results = await rag_service.run_nightly_crawl(db)
        return {
            "success": True,
            "action": "NIGHTLY_CRAWL",
            "message": "夜間クローリングバッチを手動起動し、ベクトルDBを同期しました。",
            "details": crawl_results
        }
```

**変更後:**
```python
    # 2. Nightly Crawl Command (internal tasks & messages)
    if "crawl" in cmd_text.lower() or "クロール" in cmd_text:
        crawl_results = await rag_service.run_nightly_crawl(db)
        tasks_count = crawl_results.get("crawled_tasks_count", 0)
        msg_count = crawl_results.get("crawled_messages_count", 0)
        chunks = crawl_results.get("indexed_chunks_count", 0)
        return {
            "success": True,
            "action": "NIGHTLY_CRAWL",
            "message": f"内部クロール完了: タスク{tasks_count}件・メッセージ{msg_count}件、計{chunks}チャンクをナレッジベースに登録しました。",
            "details": crawl_results
        }
```

---

## 変更2 — `frontend/src/components/CommandPalette.vue`

### script setup セクションの変更

#### `repoOptions` ref の追加

`executing` の定義の直後（L112付近）に追加する。

**現在:**
```javascript
const executing = ref(false)
const inputField = ref(null)
```

**変更後:**
```javascript
const executing = ref(false)
const inputField = ref(null)
const repoOptions = ref([])
```

#### `close()` 関数の変更

クローズ時に `repoOptions` をリセットする。

**現在:**
```javascript
const close = () => {
  visible.value = false
}
```

**変更後:**
```javascript
const close = () => {
  visible.value = false
  repoOptions.value = []
}
```

#### `submit()` 関数の変更

送信時に `repoOptions` をリセットし、`SELECT_REPO` アクションを処理する。

**現在:**
```javascript
const submit = async () => {
  if (!cmdText.value || executing.value) return
  
  executing.value = true
  responseMsg.value = ''
  
  try {
    const res = await store.executeCommand(cmdText.value, buildScreenContext())
    if (res.success) {
      responseMsg.value = res.message
    } else {
      responseMsg.value = `エラー: ${res.message}`
    }
  } catch (err) {
    responseMsg.value = `実行エラー: ${err.message}`
  } finally {
    executing.value = false
  }
}
```

**変更後:**
```javascript
const submit = async () => {
  if (!cmdText.value || executing.value) return
  
  executing.value = true
  responseMsg.value = ''
  repoOptions.value = []
  
  try {
    const res = await store.executeCommand(cmdText.value, buildScreenContext())
    if (res.action === 'SELECT_REPO') {
      responseMsg.value = res.message
      repoOptions.value = res.repos || []
    } else if (res.success) {
      responseMsg.value = res.message
    } else {
      responseMsg.value = `エラー: ${res.message}`
    }
  } catch (err) {
    responseMsg.value = `実行エラー: ${err.message}`
  } finally {
    executing.value = false
  }
}
```

#### `selectRepo()` 関数の追加

`submit()` の直後に追加する。

```javascript
const selectRepo = (fullName) => {
  cmdText.value = `@AI Giteaクロール ${fullName}`
  submit()
}
```

#### `suggestions` computed の変更

`GanttView` の base 配列と default 配列に `@AI Giteaクロール` を追加する。

**現在:**
```javascript
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
  ...
  return [
    '@AI 遅延タスクの残工数をヒアリングして',
    '@AI 夜間クロールを起動',
    '@AI プランBを適用して',
    'タスク一覧の進捗をチェックして',
  ]
})
```

**変更後:**
```javascript
const suggestions = computed(() => {
  const routeName = route.name
  if (routeName === 'GanttView') {
    const base = [
      '@AI このスケジュールを最適化して',
      '@AI 遅延タスクの残工数をヒアリングして',
      '@AI プランBを適用して',
      '@AI Giteaクロール',
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
    '@AI Giteaクロール',
    '@AI プランBを適用して',
    'タスク一覧の進捗をチェックして',
  ]
})
```

### template セクションの変更

レスポンスエリア（`v-if="responseMsg"` の div）の直後に、リポジトリ選択チップを追加する。

**挿入位置:** 現在の以下のブロックの直後

```html
        <!-- Response Area -->
        <div v-if="responseMsg" class="pa-4 rounded-lg rgba-bg mt-4 glass-card">
          ...
        </div>
```

**追加するHTML:**
```html
        <!-- Repo selection chips (shown after SELECT_REPO action) -->
        <div v-if="repoOptions.length > 0" class="mt-3">
          <div class="text-caption text-grey-darken-1 mb-2">リポジトリを選択:</div>
          <v-chip-group>
            <v-chip
              v-for="repo in repoOptions"
              :key="repo.full_name"
              size="small"
              color="success"
              variant="outlined"
              class="mr-2 mb-2"
              prepend-icon="mdi-source-repository"
              @click="selectRepo(repo.full_name)"
            >
              {{ repo.full_name }}
            </v-chip>
          </v-chip-group>
        </div>
```

---

## 動作確認手順

バックエンド起動後、以下の順で確認する。

### Test 1: Giteaクロール（リポジトリ選択フロー）

```bash
TOKEN=$(curl -s -X POST http://localhost:8008/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"nhigashira@example.com","password":"password"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# ステップ1: リポジトリ一覧取得
curl -s -X POST http://localhost:8008/api/v1/command/execute \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"command": "@AI Giteaクロール"}' | python3 -m json.tool
```

**期待レスポンス:**
```json
{
  "success": true,
  "action": "SELECT_REPO",
  "repos": [{"full_name": "nhigashira/ai-pmo-local", ...}],
  "message": "クロールするリポジトリを選択してください:"
}
```

### Test 2: 特定リポジトリのクロール実行

```bash
curl -s -X POST http://localhost:8008/api/v1/command/execute \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"command": "@AI Giteaクロール nhigashira/ai-pmo-local"}' | python3 -m json.tool
```

**期待レスポンス:**
```json
{
  "success": true,
  "action": "GITEA_CRAWL",
  "message": "リポジトリ「nhigashira/ai-pmo-local」のクロール完了: X件のドキュメントをナレッジベースに登録しました。"
}
```

### Test 3: 内部クロールの件数表示確認

```bash
curl -s -X POST http://localhost:8008/api/v1/command/execute \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"command": "@AI クロール"}' | python3 -m json.tool
```

**期待レスポンス:**
```json
{
  "success": true,
  "action": "NIGHTLY_CRAWL",
  "message": "内部クロール完了: タスクX件・メッセージY件、計Zチャンクをナレッジベースに登録しました。"
}
```

### Test 4: クロール後のナレッジ登録確認

```bash
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8008/api/v1/knowledge/ | python3 -c "
import sys, json
from collections import Counter
data = json.load(sys.stdin)
sources = Counter(k['source'] for k in data)
print('総件数:', len(data))
for src, count in sorted(sources.items()):
    print(f'  {src}: {count}件')
"
```

**期待結果:** `gitea_doc` の件数が 1 以上になっていること。

---

## 確認チェックリスト

- [ ] `@AI Giteaクロール` 送信後に `action: SELECT_REPO` が返る
- [ ] フロントエンドにリポジトリ名のチップが表示される
- [ ] チップクリックで `@AI Giteaクロール nhigashira/ai-pmo-local` が自動送信される
- [ ] クロール完了メッセージに件数が表示される
- [ ] `GET /api/v1/knowledge/` で `gitea_doc` ソースの件数が増加している
- [ ] `@AI クロール`（内部クロール）のメッセージに件数が表示される
- [ ] コマンドパレットのサジェスチョンに `@AI Giteaクロール` が表示される
