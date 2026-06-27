# 【Antigravity作業指示】④ ポートフォリオ管理 機能強化

## 概要

ポートフォリオ管理の強化として、以下3点を実装する。
**既存のAPI・モデル・ストアは全て動作済みのため改変しない。差分のみ実装すること。**

---

## 前提知識（必ず読んでから作業すること）

### プロジェクト構成
- バックエンド起動: `/Users/nhigashira/Documents/dev/ai-pmo/backend/run.py`
- フロントエンド: `/Users/nhigashira/Documents/dev/ai-pmo/frontend/src/`

### データフローの理解

```
POST /pmo/portfolio/apply-allocation-shift
  → PortfolioService.apply_allocation_shift()
    → Task.plan_b_end を更新（遅延タスクのスケジュールを繰り上げ）
    → DB commit
  → store.applyAllocationShift() が fetchPortfolio() を呼ぶ
    → store.portfolioProjects が更新される
      → 各 project.tasks[].plan_b_end に新しい日付が入る
  → GanttView.vue の handleApplyShift が store.planBGhostActive = true を手動セット
```

### 既実装の確認ポイント

**`store/project.js`**
- `state.planBGhostActive` — boolean、true のとき Ghost Schedule を表示すべき
- `state.portfolioProjects` — `{ id, name, tasks: TaskResponse[], allocations: [] }[]`
- `TaskResponse` には `plan_b_start`, `plan_b_end` が含まれる

**`components/GanttChart.vue`**
- `props.isPortfolio` — true のとき全プロジェクト横断表示
- `mapNode(n)` — 単一プロジェクト WBS 用マッパー（L115）
- portfolio 用タスクマッピングは `ganttTasks` computed 内 L133〜155

**`views/GanttView.vue`**
- Portfolio タブは `<v-window-item value="portfolio">` （L309）
- `store.planBGhostActive` が true のときバナーを表示中（L321）
- `handleApplyShift()` が `store.planBGhostActive = true` をセット（L1642）

---

## 実装 1: Ghost Schedule ガントチャート可視化

### ファイル
`frontend/src/components/GanttChart.vue`

### 現状の問題
`mapNode` 関数は `plan_b_start/end` を無視し常に `planned_start/end` でバーを描画する。
`store.planBGhostActive` が true になっても Gantt バーは変化しない。

### 変更内容

**`mapNode` 関数（現在 L115）を以下に置き換える：**

```javascript
const mapNode = (n) => {
  const usePlanB = store.planBGhostActive &&
    n.plan_b_end &&
    n.plan_b_end !== n.planned_end

  const task = {
    id: String(n.id),
    name: usePlanB ? `${n.title} 🔄` : n.title,
    startDate: fmt(usePlanB ? (n.plan_b_start || n.planned_start) : n.planned_start),
    endDate: fmt(usePlanB ? n.plan_b_end : n.planned_end),
    progress: n.progress || 0,
    assignee: n.assignee_name || '',
    predecessor: depsOf(n)
  }
  if (n.children && n.children.length > 0) {
    task.children = n.children.map(mapNode)
    task.collapsed = false
  }
  return task
}
```

**`ganttTasks` computed 内の portfolio タスクマッピング（現在 L145〜153）を以下に置き換える：**

```javascript
children: ts.map((t) => {
  const usePlanB = store.planBGhostActive &&
    t.plan_b_end &&
    t.plan_b_end !== t.planned_end
  return {
    id: String(t.id),
    name: usePlanB ? `${t.title} 🔄` : t.title,
    startDate: fmt(usePlanB ? (t.plan_b_start || t.planned_start) : t.planned_start),
    endDate: fmt(usePlanB ? t.plan_b_end : t.planned_end),
    progress: t.progress || 0,
    assignee: t.assignee_name || '',
    predecessor: depsOf(t)
  }
})
```

### 期待動作
- 「調停案を承認（一括シフト）」クリック後、ガントバーが `plan_b_end` の日程に変わりタイトルに 🔄 が付く
- 「Ghost表示を閉じる」クリックで 🔄 が消え元の `planned_end` に戻る

---

## 実装 2: LLM-Enhanced 競合分析

### ファイル
`backend/app/services/portfolio_service.py`

### 現状の問題
`audit_conflicts()` の `description` はテンプレート文字列で生成されており、LLM による分析を行っていない。
また skill の判定がタイトルのキーワードマッチのみ（`"フロント" in dt.title`）で粗い。

### 変更内容

**① ファイル冒頭のインポートに追加：**

```python
from app.services.llm import llm_service
import re, json
```

**② `audit_conflicts` メソッド内、`proposals.append(...)` のディクショナリに `delay_info` フィールドを追加：**

現在の `proposals.append({...})` を以下のように変更する（既存フィールドはそのまま、`delay_info` だけ追加）：

```python
proposals.append({
    "id": f"shift_{alloc.id}_{dt.id}",
    "delayed_project_id": str(proj.id),
    "delayed_project_name": proj.name,
    "delayed_task_id": str(dt.id),
    "delayed_task_title": dt.title,
    "donor_project_id": str(other_proj.id),
    "donor_project_name": other_proj.name,
    "resource_name": alloc.resource_name,
    "skill": needed_skill,
    "shift_percent": 20,
    "substitute_ai_name": "AI_WORKER_BACKFILL",
    "delay_info": f"{dt.delay_days}日遅延中",
    "description": (
        f"プロジェクト「{other_proj.name}」の進捗には現在余裕があるため、"
        f"同等スキルを持つ【{alloc.resource_name}】の稼働を 20% シフトし、"
        f"遅延している「{dt.title}」を補強します。また、「{other_proj.name}」側の"
        f"定型業務の穴埋めとして AIワーカー（{needed_skill} 補填）を追加します。"
    )
})
```

**③ `return proposals` の直前（競合検出ループの後）に以下の LLM 呼び出しブロックを追加：**

```python
# LLM でより豊かな説明文を再生成（失敗時はテンプレート文を維持）
if proposals:
    context_lines = [
        f"- 案{i+1}: {p['delayed_project_name']}のタスク「{p['delayed_task_title']}」が{p['delay_info']}。"
        f"{p['donor_project_name']}の{p['resource_name']}（{p['skill']}スキル）を{p['shift_percent']}%シフト提案。"
        for i, p in enumerate(proposals)
    ]
    system_prompt = (
        "あなたはPMOのリソース調停アナリストです。"
        "以下のリソース競合・遅延状況を分析し、各調停案を経営層向けに端的な日本語で説明してください。"
        "出力は JSON 配列のみ。各要素は提示された案の番号（1始まり）に対応させること。"
        '形式: [{"index": 1, "description": "50字以内の説明文"}]'
        "解説不要。JSONのみ出力。"
    )
    try:
        raw = await llm_service.get_response(system_prompt, "\n".join(context_lines), temperature=0.3)
        cleaned = re.sub(r'^```(?:json)?\s*', '', raw.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r'\s*```$', '', cleaned.strip(), flags=re.MULTILINE)
        llm_results = json.loads(cleaned.strip())
        for item in llm_results:
            idx = item.get("index", 0) - 1
            desc = item.get("description", "")
            if 0 <= idx < len(proposals) and desc:
                proposals[idx]["description"] = desc
    except Exception as e:
        logger.warning(f"LLM conflict description generation failed (using template): {e}")

return proposals
```

### 期待動作
- 競合が検出されたとき、LLM が状況を分析した自然な説明文が `description` に入る
- LLM が失敗（タイムアウト・オフラインなど）してもテンプレート文でフォールバックする

---

## 実装 3: ポートフォリオ KPI カード

### ファイル
`frontend/src/views/GanttView.vue`

### 現状の問題
ポートフォリオタブに「プロジェクト別リソース稼働状況」カードはあるが、
プロジェクトごとの完了率・遅延タスク数が一目でわからない。

### 変更内容

**① `<script setup>` 内（`portfolioKpi` 関数の追加）**

`const handleApplyShift` 関数の近くに以下を追加する：

```javascript
const portfolioKpi = (proj) => {
  const tasks = proj.tasks || []
  if (!tasks.length) return { doneRate: 0, delayCount: 0 }
  const doneCount = tasks.filter(t => t.status === 'DONE').length
  const delayCount = tasks.filter(t => t.delay_days > 0).length
  const doneRate = Math.round((doneCount / tasks.length) * 100)
  return { doneRate, delayCount }
}
```

**② Portfolio タブのテンプレート内（`<!-- Projects & Resource Allocations -->` カードの直前）に KPI カードを挿入する：**

挿入位置は以下のコメントのすぐ前（L332 付近）：
```html
<!-- Projects & Resource Allocations -->
```

挿入するコード：

```html
<!-- Portfolio KPI サマリー -->
<v-card class="glass-panel border-neon-glow pa-4">
  <v-card-title class="text-subtitle-1 font-weight-bold text-white d-flex align-center pb-3">
    <v-icon start color="primary">mdi-gauge</v-icon>
    ポートフォリオ健康指標
  </v-card-title>
  <v-row>
    <v-col
      cols="12"
      sm="6"
      v-for="proj in store.portfolioProjects"
      :key="'kpi-' + proj.id"
    >
      <div class="d-flex align-center justify-between pa-3 bg-glass rounded-lg border-subtle">
        <div>
          <div class="text-caption text-grey mb-1 font-weight-bold text-truncate" style="max-width: 180px;">
            {{ proj.name }}
          </div>
          <div class="d-flex align-center gap-2 mt-1">
            <v-chip
              :color="portfolioKpi(proj).delayCount > 0 ? 'error' : 'success'"
              size="x-small"
              variant="flat"
            >
              {{ portfolioKpi(proj).delayCount > 0 ? `遅延 ${portfolioKpi(proj).delayCount}件` : '遅延なし' }}
            </v-chip>
            <span class="text-caption text-grey">完了率 {{ portfolioKpi(proj).doneRate }}%</span>
          </div>
        </div>
        <v-progress-circular
          :model-value="portfolioKpi(proj).doneRate"
          :size="48"
          :width="5"
          :color="portfolioKpi(proj).doneRate >= 80 ? 'success' : portfolioKpi(proj).doneRate >= 40 ? 'warning' : 'error'"
        >
          <span class="text-caption font-weight-bold text-white">{{ portfolioKpi(proj).doneRate }}%</span>
        </v-progress-circular>
      </div>
    </v-col>
  </v-row>
</v-card>
```

### 期待動作
- ポートフォリオタブに各プロジェクトの完了率（円形プログレス）と遅延タスク数チップが表示される
- 完了率 80%以上 → 緑 / 40%以上 → 黄 / 未満 → 赤

---

## 実装後の確認手順

### バックエンド確認
```bash
# 再起動
kill $(ps aux | grep "run.py" | grep -v grep | awk '{print $2}')
cd /Users/nhigashira/Documents/dev/ai-pmo/backend
./venv/bin/python run.py > backend.log 2>&1 &

# 起動確認
sleep 4 && tail -5 backend.log

# 競合分析 API テスト
TOKEN=$(curl -s -X POST http://localhost:8008/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"nhigashira@example.com","password":"password"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s -X POST http://localhost:8008/api/v1/pmo/portfolio/audit-conflict \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

期待: `description` フィールドに LLM が生成した自然な説明文が入っている（失敗時はテンプレート文）。

### フロントエンド確認（ブラウザ目視確認）

1. `http://localhost:5174` を開く
2. **WBS / ガントチャート** → **ポートフォリオ・オーケストレーター** タブを選択
3. **[確認1]** 「ポートフォリオ健康指標」カードが表示され、各プロジェクトの完了率と遅延件数が表示される
4. **[確認2]** 「リソース競合・調停アラート」に競合が表示されている場合、「調停案を承認（一括シフト）」をクリック
5. **[確認3]** ガントチャートのバーが変化し、遅延タスクのタイトルに `🔄` が付いて日程がシフトする
6. **[確認4]** 「Ghost表示を閉じる」ボタンをクリックすると `🔄` が消え、元の日程に戻る

---

## 禁止事項

- `backend/app/models/` 配下のモデルファイルは変更しない（マイグレーション不要）
- `backend/app/api/v1/endpoints/pmo.py` のエンドポイント定義は変更しない
- `frontend/src/store/project.js` の state や actions は変更しない
- 新規ファイルは作成しない（既存ファイルの差分修正のみ）
