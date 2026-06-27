# Antigravity 作業指示: ⑥ エグゼクティブサマリー強化

## 役割と制約

あなたはバックエンドエンジニアとフロントエンドエンジニアの両方の役割を担います。  
以下に指示された変更のみを実施してください。指示外の変更・リファクタ・新規ファイル作成は禁止です。

---

## 背景と課題

現在の `GET /api/v1/pmo/executive-report/summary` は以下の課題を抱えている：

1. **根拠の説明が薄い**: LLM に SPI/CPI 数値と遅延タスク名しか渡していない。経営層を説得できる具体的な根拠（円換算コスト、超過工数、プロジェクト別内訳）が欠如している
2. **遅延タスク詳細不足**: テキスト文字列のみ（担当者・進捗率・超過時間なし）
3. **プロジェクト別分析なし**: ポートフォリオ全体の SPI/CPI のみで、どのプロジェクトが問題かが不明
4. **RAG 連携なし**: `lessons_learned` コレクションの教訓が活用されていない
5. **LLM プロンプト**: 「数値を必ず引用すること」という制約指示がない

---

## 変更対象ファイル（2ファイルのみ）

1. `backend/app/api/v1/endpoints/pmo.py` — `get_executive_summary` 関数の全置換
2. `frontend/src/views/Dashboard.vue` — EVM 金額カード追加 + プロジェクト別テーブル追加

---

## 変更 1: backend/app/api/v1/endpoints/pmo.py

### 対象範囲

**L190〜L285 の `get_executive_summary` 関数を全て以下のコードに置換する**。  
関数シグネチャのデコレータ `@router.get("/executive-report/summary", ...)` から最後の `}` まで。

### 置換後コード

```python
@router.get("/executive-report/summary", response_model=Dict[str, Any])
async def get_executive_summary(
    current_user: Resource = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Assembles portfolio metrics (EVM) and translates technical status into business terms.
    Enhanced: project-level breakdown, detailed delay data, RAG lessons, evidence-driven LLM prompt.
    """
    result = await db.execute(
        select(Project).options(
            selectinload(Project.tasks).selectinload(Task.children)
        )
    )
    projects = result.scalars().all()

    # Fetch resource rates from DB
    res_result = await db.execute(select(Resource))
    resources = res_result.scalars().all()
    resource_rates = {r.name: r.hourly_cost_jpy for r in resources}

    # EVM aggregates (leaf tasks only)
    total_pv = 0.0
    total_ev = 0.0
    total_ac = 0.0

    unmapped_assignees = set()
    delayed_tasks_detail = []
    project_breakdown = []

    for proj in projects:
        proj_pv = 0.0
        proj_ev = 0.0
        proj_ac = 0.0

        for t in proj.tasks:
            if len(t.children) == 0:
                name = t.assignee_name.strip() if t.assignee_name else ""
                if name in resource_rates:
                    rate = resource_rates[name]
                else:
                    rate = 0
                    if name:
                        unmapped_assignees.add(name)
                    else:
                        unmapped_assignees.add("未アサイン")

                task_pv = t.estimated_hours * rate
                task_ev = (t.progress / 100.0) * task_pv
                task_ac = t.actual_hours * rate

                total_pv += task_pv
                total_ev += task_ev
                total_ac += task_ac
                proj_pv += task_pv
                proj_ev += task_ev
                proj_ac += task_ac

            if t.delay_days > 0:
                over_hours = round(t.actual_hours - t.estimated_hours, 1)
                delayed_tasks_detail.append({
                    "project": proj.name,
                    "task": t.title,
                    "delay_days": t.delay_days,
                    "assignee": t.assignee_name or "未アサイン",
                    "progress_pct": t.progress,
                    "estimated_hours": t.estimated_hours,
                    "actual_hours": t.actual_hours,
                    "over_hours": over_hours,
                })

        proj_spi = proj_ev / proj_pv if proj_pv > 0 else 1.0
        proj_cpi = proj_ev / proj_ac if proj_ac > 0 else 1.0
        delayed_in_proj = sum(1 for d in delayed_tasks_detail if d["project"] == proj.name)
        project_breakdown.append({
            "project": proj.name,
            "status": proj.status,
            "pv_jpy": round(proj_pv),
            "ev_jpy": round(proj_ev),
            "ac_jpy": round(proj_ac),
            "spi": round(proj_spi, 2),
            "cpi": round(proj_cpi, 2),
            "delayed_task_count": delayed_in_proj,
        })

    # Portfolio SPI / CPI
    spi = total_ev / total_pv if total_pv > 0 else 1.0
    cpi = total_ev / total_ac if total_ac > 0 else 1.0

    # RAG: lessons_learned で遅延タスク名から過去教訓を検索
    past_lessons_text = ""
    if delayed_tasks_detail:
        delay_query = " ".join([d["task"] for d in delayed_tasks_detail[:3]])
        try:
            lesson_hits = await rag_service.search(
                delay_query,
                limit=3,
                collection_name=settings.QDRANT_LESSONS_COLLECTION_NAME
            )
            if lesson_hits:
                past_lessons_text = "\n".join([
                    f"- 教訓: {hit['content']} → 推奨対策: {hit['metadata'].get('mitigation_task', '不明')}"
                    for hit in lesson_hits
                ])
        except Exception:
            pass

    # LLM に渡す遅延タスク詳細テキスト
    if delayed_tasks_detail:
        delayed_detail_text = "\n".join([
            f"  ・[{d['project']}] {d['task']}: {d['delay_days']}日遅延 / "
            f"担当: {d['assignee']} / 進捗: {d['progress_pct']}% / "
            f"見積: {d['estimated_hours']}h 実績: {d['actual_hours']}h "
            f"({'超過 ' + str(abs(d['over_hours'])) + 'h' if d['over_hours'] > 0 else '余裕あり'})"
            for d in delayed_tasks_detail
        ])
    else:
        delayed_detail_text = "  (現在遅延タスクなし)"

    # LLM に渡すプロジェクト別内訳テキスト
    project_breakdown_text = "\n".join([
        f"  ・{p['project']}: SPI={p['spi']} / CPI={p['cpi']} / "
        f"PV={p['pv_jpy']:,}円 EV={p['ev_jpy']:,}円 AC={p['ac_jpy']:,}円 / "
        f"遅延タスク数: {p['delayed_task_count']}"
        for p in project_breakdown
    ])

    system_prompt = (
        "You are the Chief PMO Officer reporting directly to the Board of Directors and CFO.\n"
        "Translate technical issues (Git errors, database configs, minor bugs) into high-level business impacts "
        "concerning cost, delivery, ROI timing, and DX benefits release.\n"
        "Write a concise, professional report in Japanese.\n"
        "CRITICAL REQUIREMENT: Every claim MUST be backed by specific numbers from the data provided. "
        "Always cite actual figures (SPI, CPI, JPY amounts, hours, delay days, task names). "
        "Never make vague statements — if you cannot cite a number, do not make the claim.\n"
        "Structure:\n"
        "1. 【総合ステータス評価】(SPI/CPIと円換算PV/EV/ACを引用して総評)\n"
        "2. 【納期・DX効果発現への影響】(具体的な遅延日数・タスク名・担当者を引用)\n"
        "3. 【コストおよびリソース効率】(AC vs EV 差額・超過工数・プロジェクト別CPIを引用)\n"
        "4. 【過去事例との比較と教訓】(過去教訓が提供された場合は必ず言及)\n"
        "5. 【PMO推奨アクション】(数値根拠に基づく具体的かつ実行可能な推奨アクション)"
    )

    ev_pv_diff = round(total_ev - total_pv)
    ac_ev_diff = round(total_ac - total_ev)
    user_prompt = (
        f"=== ポートフォリオEVM指標 ===\n"
        f"- SPI (スケジュール効率指数): {spi:.2f}\n"
        f"- CPI (コスト効率指数): {cpi:.2f}\n"
        f"- PV (計画価値合計): {round(total_pv):,}円\n"
        f"- EV (出来高合計): {round(total_ev):,}円\n"
        f"- AC (実績コスト合計): {round(total_ac):,}円\n"
        f"- EV-PV差異: {ev_pv_diff:,}円 ({'スケジュール遅れ' if ev_pv_diff < 0 else 'スケジュール前倒し'})\n"
        f"- AC-EV差異: {ac_ev_diff:,}円 ({'コスト超過' if ac_ev_diff > 0 else 'コスト節約'})\n\n"
        f"=== プロジェクト別内訳 ===\n{project_breakdown_text}\n\n"
        f"=== 遅延タスク詳細 ===\n{delayed_detail_text}\n\n"
        + (f"=== 過去の類似トラブル教訓 ===\n{past_lessons_text}\n\n" if past_lessons_text else "")
        + "上記データの数値を必ず引用しながら経営報告書を作成してください:"
    )

    try:
        report_text = await llm_service.get_response(system_prompt, user_prompt, temperature=0.4)
    except Exception as e:
        logger.error(f"Executive summary LLM failed: {str(e)}")
        report_text = (
            f"【総合ステータス評価】ポートフォリオ全体のSPI={spi:.2f}、CPI={cpi:.2f}。"
            f"計画価値(PV){round(total_pv):,}円に対し出来高(EV){round(total_ev):,}円（差異:{ev_pv_diff:,}円）。\n"
            f"【納期・DX効果発現への影響】遅延タスク{len(delayed_tasks_detail)}件を確認。"
            f"DX成果発現タイミングへの影響リスクが生じています。\n"
            f"【コストおよびリソース効率】実績コスト(AC){round(total_ac):,}円 vs 出来高(EV){round(total_ev):,}円"
            f"（{'コスト超過' if ac_ev_diff > 0 else 'コスト節約'} {abs(ac_ev_diff):,}円）。\n"
            f"【過去事例との比較と教訓】過去教訓DBとの照合を推奨します。\n"
            f"【PMO推奨アクション】遅延プロジェクトへの優先リソース再配分と週次EVM進捗レビューの実施を推奨します。"
        )

    return {
        "spi": round(spi, 2),
        "cpi": round(cpi, 2),
        "cpi_status": "UNDER_BUDGET" if cpi >= 1.0 else "OVER_RUN",
        "spi_status": "ON_SCHEDULE" if spi >= 1.0 else "DELAY",
        "total_pv_jpy": round(total_pv),
        "total_ev_jpy": round(total_ev),
        "total_ac_jpy": round(total_ac),
        "project_breakdown": project_breakdown,
        "delayed_tasks": delayed_tasks_detail,
        "summary_report": report_text,
        "unmapped_assignees": list(unmapped_assignees)
    }
```

### 重要注意事項

- `import` は既存のまま変更不要（`rag_service`, `settings`, `llm_service` はすでにインポート済み）
- `from app.models.task import Task` もすでに `L14` にインポート済み
- `delayed_tasks_text` 変数（旧変数名）は完全に削除し `delayed_tasks_detail` に置換
- 行番号はファイル変更により前後する可能性があるため、関数名で対象箇所を特定すること

---

## 変更 2: frontend/src/views/Dashboard.vue

### 変更 2-1: EVM 金額カードの追加

**対象箇所**: L85〜L87 の `※ SPI/CPI...` の div の直前（L83 の `</v-row>` の直後、L85 の前）に以下を挿入する。

```html
          <!-- EVM JPY amounts row -->
          <v-row class="mt-4" dense>
            <v-col cols="4">
              <div class="pa-3 bg-glass rounded-lg border-subtle text-center">
                <div class="text-caption text-grey">PV (計画価値)</div>
                <div class="text-body-2 font-weight-bold text-white">
                  {{ store.executiveSummary?.total_pv_jpy != null
                    ? '¥' + store.executiveSummary.total_pv_jpy.toLocaleString()
                    : '---' }}
                </div>
              </div>
            </v-col>
            <v-col cols="4">
              <div class="pa-3 bg-glass rounded-lg border-subtle text-center">
                <div class="text-caption text-grey">EV (出来高)</div>
                <div
                  class="text-body-2 font-weight-bold"
                  :class="(store.executiveSummary?.total_ev_jpy ?? 0) >= (store.executiveSummary?.total_pv_jpy ?? 0) ? 'text-success' : 'text-error'"
                >
                  {{ store.executiveSummary?.total_ev_jpy != null
                    ? '¥' + store.executiveSummary.total_ev_jpy.toLocaleString()
                    : '---' }}
                </div>
              </div>
            </v-col>
            <v-col cols="4">
              <div class="pa-3 bg-glass rounded-lg border-subtle text-center">
                <div class="text-caption text-grey">AC (実績コスト)</div>
                <div
                  class="text-body-2 font-weight-bold"
                  :class="(store.executiveSummary?.total_ac_jpy ?? 0) <= (store.executiveSummary?.total_ev_jpy ?? 0) ? 'text-success' : 'text-error'"
                >
                  {{ store.executiveSummary?.total_ac_jpy != null
                    ? '¥' + store.executiveSummary.total_ac_jpy.toLocaleString()
                    : '---' }}
                </div>
              </div>
            </v-col>
          </v-row>
```

### 変更 2-2: プロジェクト別内訳テーブルの追加

**対象箇所**: L108 の `</v-row>` の直後（`<!-- Normal View Content -->` の直前）に以下の `<v-row>` ブロックを挿入する。

```html
    <!-- Executive View: project breakdown table -->
    <v-row v-if="isExecutiveView && store.executiveSummary?.project_breakdown?.length" class="mb-4">
      <v-col cols="12">
        <v-card class="glass-card pa-4">
          <v-card-title class="text-subtitle-2 font-weight-bold text-neon-blue pb-2 d-flex align-center">
            <v-icon start color="primary" size="18">mdi-table-eye</v-icon>
            プロジェクト別 EVM 内訳
          </v-card-title>
          <v-table density="compact" class="bg-transparent">
            <thead>
              <tr>
                <th class="text-caption text-grey">プロジェクト</th>
                <th class="text-caption text-grey text-right">SPI</th>
                <th class="text-caption text-grey text-right">CPI</th>
                <th class="text-caption text-grey text-right">PV (円)</th>
                <th class="text-caption text-grey text-right">EV (円)</th>
                <th class="text-caption text-grey text-right">AC (円)</th>
                <th class="text-caption text-grey text-right">遅延タスク</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="p in store.executiveSummary.project_breakdown" :key="p.project">
                <td class="text-body-2 text-white">{{ p.project }}</td>
                <td
                  class="text-body-2 text-right font-weight-bold"
                  :class="p.spi >= 1.0 ? 'text-success' : 'text-error'"
                >{{ p.spi }}</td>
                <td
                  class="text-body-2 text-right font-weight-bold"
                  :class="p.cpi >= 1.0 ? 'text-success' : 'text-error'"
                >{{ p.cpi }}</td>
                <td class="text-body-2 text-grey text-right">¥{{ p.pv_jpy.toLocaleString() }}</td>
                <td class="text-body-2 text-white text-right">¥{{ p.ev_jpy.toLocaleString() }}</td>
                <td
                  class="text-body-2 text-right"
                  :class="p.ac_jpy > p.ev_jpy ? 'text-error' : 'text-success'"
                >¥{{ p.ac_jpy.toLocaleString() }}</td>
                <td class="text-body-2 text-right">
                  <v-chip
                    v-if="p.delayed_task_count > 0"
                    color="error"
                    size="x-small"
                    label
                  >{{ p.delayed_task_count }}件</v-chip>
                  <span v-else class="text-success text-caption">なし</span>
                </td>
              </tr>
            </tbody>
          </v-table>
        </v-card>
      </v-col>
    </v-row>
```

---

## 動作確認手順

### 1. バックエンド起動

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

### 2. ログイン トークン取得

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "TOKEN: $TOKEN"
```

### 3. エグゼクティブサマリー API 呼び出し

```bash
curl -s http://localhost:8000/api/v1/pmo/executive-report/summary \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

### 4. 確認チェックリスト

以下を全て確認すること：

- [ ] レスポンスに `total_pv_jpy`, `total_ev_jpy`, `total_ac_jpy` の数値フィールドが存在する
- [ ] レスポンスに `project_breakdown` 配列が存在し、各要素に `spi`, `cpi`, `pv_jpy`, `ev_jpy`, `ac_jpy`, `delayed_task_count` が含まれる
- [ ] レスポンスに `delayed_tasks` 配列が存在し、各遅延タスクに `project`, `task`, `delay_days`, `assignee`, `progress_pct`, `estimated_hours`, `actual_hours`, `over_hours` が含まれる
- [ ] `summary_report` テキストに具体的な数値（円、SPI/CPI、日数）が含まれている（根拠の明示）
- [ ] バックエンドログに `lessons_learned` 検索ログが出力される（遅延タスクが存在する場合）
- [ ] フロントエンドのエグゼクティブビュー切替で PV/EV/AC の金額カードが表示される
- [ ] フロントエンドにプロジェクト別 EVM テーブルが表示される
- [ ] SPI < 1.0 のプロジェクトの SPI セルが赤色で表示される

---

## 禁止事項

- `backend/app/models/` 配下のファイルの変更は禁止
- `backend/app/services/rag.py` の変更は禁止
- `backend/app/main.py` の変更は禁止（シーディングは既存のまま）
- `backend/app/config.py` の変更は禁止（設定は既存のまま）
- `pmo.py` 内の他エンドポイント（`/portfolio`, `/audit-conflict`, `/audit-document`, `/search-lesson`）の変更は禁止
- `Dashboard.vue` 内のエグゼクティブビュー以外（Normal View）の変更は禁止
- 新規ファイルの作成は禁止
