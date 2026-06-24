# AI-PMO 開発完了ウォークスルー

本ドキュメントは、自律協働型プロジェクト管理ツール「AI-PMO」の実装内容および稼働検証結果をまとめたものである。

---

## 1. 実装成果物と変更概要

### 1.1 インフラ定義 (新規)
- [docker-compose.yml](file:///Users/nhigashira/Documents/dev/ai-pmo/docker-compose.yml): ポート競合を回避するため、孤立ポート `5435` (PostgreSQL 16) および `6335` (Qdrant) をバインドし起動。

### 1.2 バックエンド (FastAPI)
- **非同期 ORM & SQLAlchemy 2.0**: SQLAlchemy の非同期(asyncio)マッパーと `selectinload` を活用し、WBS親子関係および依存関係を型安全かつ `MissingGreenlet` エラーなしで直列化。
- **LM Studio 統合 (`services/llm.py`)**: `qwen3.6-35b-a3b-ud-mlx` モデルに直接接続。
- **ベクトルRAG検索 (`services/rag.py`)**: Qdrant 高レベル API を活用し、`fastembed` によるローカル文章ベクトル化・セマンティック検索と、夜間クロールシミュレーションを実装。
- **ヒアリング・プランB調整エンジン (`services/risk_engine.py`)**: ユーザーの自然言語回答から残工数を抽出し、WBSカスケード遅延計算を実行。低優先度タスクの日程を後方にシフトしてプランBを動的編成。

### 1.3 フロントエンド (Vue 3 + Vuetify 3)
- **グラスモーフィズム・ダークモードテーマ**: CSS backdrop-filter やグラデーションによるすりガラス効果を index.css で定義し、未来感のある極めて美しいダークモードUIを構築。
- **インタラクティブガントチャート (`components/GanttChart.vue`)**: `frappe-gantt` をラップし、通常スケジュールとプランB (ゴースト破線表示) の重ね合わせ描画をサポート。
- **グローバルコマンドパレット (`components/CommandPalette.vue`)**: `Cmd + K` キーボード入力で即時起動し、ChatOps指示の送信やRAGによるドキュメント探索に対応。
- **朝会ポップアップ (`components/DailyStandup.vue`)**: ログイン時の自動実績サマリーと、本日承認が必要なアクション Top 3 の処理。
- **インラインAIコメント成果物レビュー (`views/ArtifactsView.vue`)**: AIワーカーが生成したコード/ドキュメントの閲覧と、行番号に紐づいたバグ・矛盾検知警告の適用。

---

## 2. デザイン・UIモックアップ

開発したツールのインターフェースデザイン案である。ダークモード背景にネオンブルーとパープルのアクセントが光り、すりガラスのサイドナビゲーションやAIアシスタントパネルが浮かび上がる構成となっている。

![AI-PMO UI Mockup](/Users/nhigashira/.gemini/antigravity/brain/de0d6878-8c7f-445a-88e1-79036468b613/aipmo_dashboard_mockup_1780732917626.png)

---

## 3. 動作検証結果

### 3.1 起動疎通テスト
- バックエンド (`http://localhost:8008`) および フロントエンド (`http://localhost:5173`) を同時にローカル起動。
- API 起動時のデータベース自動シーディング機能により、テスト用のWBSタスク（インフラ構築完了タスク、AIアサインTODOタスク、遅延状態の人間担当UIデザインタスク）が自動構築されることを確認。

```json
// GET /api/v1/tasks/
[
  {
    "title": "データベースインフラ構築 (PostgreSQL/Qdrant)",
    "status": "DONE",
    "progress": 100
  },
  {
    "title": "フロントエンド UI デザイン (ダークモード・グラスモーフィズム)",
    "status": "IN_PROGRESS",
    "progress": 45,
    "delay_days": 2
  },
  {
    "title": "APIエンドポイント自動実装とモックアップ",
    "status": "TODO",
    "assignee_type": "AI",
    "plan": {
      "approach_summary": "FastAPI API Router を作成し...",
      "status": "DRAFT"
    }
  }
]
```

### 3.2 協働シナリオ動作確認
1. **朝会サマリー**: ログインと同時にダイアログが開き、昨夜AIが完了した作業と「方針承認」「遅延ヒアリング回答」などのアクションが必要なタスクが提示される。
2. **Plan-First 実行**: AIアサインタスクの「GO (実行)」をクリックすると、バックエンドで非同期にAIワーカーが走り、成果物ファイルを生成して `REVIEW` ステータスへ移行する。
3. **残工数ヒアリングとプランB**: 遅延タスクをクリックしてチャットを開き、「あと5時間」と回答すると、自動で残工数が算出され、ガントチャートに遅延影響を加味したプランB (半透明のゴーストバー) が重ねて描画される。
4. **ナレッジクレンジング**: コントロールパネルにて、AIが過去のチャットの曖昧表現から拾った低信頼度のナレッジがアラート表示され、削除・修正できることを確認。
