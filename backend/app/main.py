import uuid
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.router import api_router
from app.core.exceptions import setup_exception_handlers
from app.database import engine, Base

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

_SEED_LESSONS = [
    {
        "title": "外部決済API接続トラブル",
        "content": "外部決済API連携時にテスト用サンドボックスの発行申請に2週間要し、WBS全体が遅延した教訓。事前にベンダーへのテストアカウント申請手続きを計画に組み込むこと。",
        "mitigation_task": "決済プロバイダーへのテストアカウント申請・事前審査手続き"
    },
    {
        "title": "フロントエンド・ブラウザ互換性の罠",
        "content": "Vuetify 3 の一部コンポーネントが古いSafariで描画エラーになり、UI調整工数が発生した。CIでのクロスブラウザテスト自動化が予防に有効。",
        "mitigation_task": "クロスブラウザテスト環境の準備とCI自動チェックの設定"
    },
    {
        "title": "DBマイグレーション本番失敗",
        "content": "Alembic auto-generateで生成したスキーマをStagingのみでテストし、本番の大容量テーブルでTIMEOUTが発生した教訓。本番相当データ量でのリハーサルが必要。",
        "mitigation_task": "本番相当データ量でのマイグレーションリハーサル実施"
    },
    {
        "title": "認証情報のハードコーディング漏洩",
        "content": "開発段階でAPIキーをコードに直書きし、誤ってGitにプッシュして漏洩したインシデント。環境変数管理と.gitignoreの徹底が必要。",
        "mitigation_task": "シークレットスキャンCI導入と環境変数への移行"
    },
    {
        "title": "非同期処理でのMissingGreenletエラー",
        "content": "async/await環境でSQLAlchemyの遅延ロード(lazy='select')を使用し、greenletエラーによりサーバーが500を返した教訓。selectinloadによる事前ロードを徹底すること。",
        "mitigation_task": "asyncio互換性チェックリストの整備とselectinload適用確認"
    },
    {
        "title": "要件定義の曖昧さによる手戻り",
        "content": "UI仕様が未確定のままAPIを実装し、後から大幅な設計変更が発生した。Plan-Firstアプローチで実装前にUI/APIインタフェースを固めることで回避可能。",
        "mitigation_task": "実装着手前のUI/APIインタフェース設計レビュー実施"
    },
    {
        "title": "Docker環境と本番環境の差異",
        "content": "ローカルのDocker ComposeとクラウドOSバージョンが異なり動作差異が発生した。CI/CDパイプラインを本番同一のイメージで実行することで防止できる。",
        "mitigation_task": "本番同一DockerイメージでのCIパイプライン整備"
    },
    {
        "title": "外部ライブラリの突然の破壊的変更",
        "content": "外部ライブラリのメジャーアップデートにより互換性が破壊され、リリース前の急ぎ対応が発生した。依存バージョン固定と定期的な更新計画が有効。",
        "mitigation_task": "package-lock固定とdependabotによる定期更新の仕組み整備"
    },
    {
        "title": "テスト環境と本番環境の接続先誤設定",
        "content": "テスト環境のDBURLが誤って本番を向いており、テストデータが本番に流入したインシデント。環境変数のバリデーションと環境ごとのCI分離が必要。",
        "mitigation_task": "環境変数バリデーションとCI環境分離の設定"
    },
]

async def _seed_lessons_learned():
    from app.services.rag import rag_service
    col = settings.QDRANT_LESSONS_COLLECTION_NAME
    if rag_service.count_documents(col) > 0:
        logger.info(f"Lessons Learned collection '{col}' already seeded. Skipping.")
        return
    documents = [f"{l['title']}\n{l['content']}" for l in _SEED_LESSONS]
    metadatas = [
        {"type": "lesson_seed", "title": l["title"], "mitigation_task": l["mitigation_task"], "source": "seed"}
        for l in _SEED_LESSONS
    ]
    ids = [str(uuid.uuid5(uuid.NAMESPACE_DNS, f"lesson_seed_{l['title']}")) for l in _SEED_LESSONS]
    registered = await rag_service.add_documents(documents, metadatas, ids, col)
    logger.info(f"Seeded {len(registered)} lessons into '{col}' collection.")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up backend server and verifying database connection...")
    
    # Auto-create tables on startup for ease of initial development/testing
    async with engine.begin() as conn:
        logger.info("Creating database tables if not exist...")
        await conn.run_sync(Base.metadata.create_all)
        
    # Seed data if empty
    from app.database import AsyncSessionLocal
    from app.models.project import Project
    from app.models.resource_allocation import ResourceAllocation
    from app.models.task import Task
    from app.models.subtask import SubTask
    from app.models.plan import Plan
    from app.models.message import Message
    from app.models.comment import Comment
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        project_count = await db.execute(select(Project))
        if not project_count.scalars().first():
            logger.info("Seeding initial demonstration Projects, Resources, ResourceAllocations, and WBS Tasks...")
            now = datetime.now(timezone.utc)
            
            # 0. Seed Resource Master / Users
            from app.models.resource import Resource
            from app.models.calendar import CalendarHoliday
            from app.core.security import hash_password
            
            hashed_default = hash_password("password")
            
            r_admin = Resource(
                name="nhigashira",
                email="nhigashira@example.com",
                password_hash=hashed_default,
                role="SV",
                start_time="09:00",
                end_time="17:45",
                break_hours=1.0,
                daily_working_hours=7.75,
                hourly_cost_jpy=12000,
                system_role="管理者",
                is_active=True,
                skills_phase=["企画", "要件定義", "設計", "実装", "テスト", "運用"],
                skills_domain=["アプリ領域", "インフラ領域", "ユーザサポート領域"],
                skills_free="System Architecture, DevOps, AWS, Security",
                department="PMO推進室"
            )
            r_manager = Resource(
                name="Manager",
                email="manager@example.com",
                password_hash=hashed_default,
                role="PM",
                start_time="09:00",
                end_time="18:00",
                break_hours=1.0,
                daily_working_hours=8.0,
                hourly_cost_jpy=8000,
                system_role="マネージャ",
                is_active=True,
                skills_phase=["企画", "要件定義", "設計"],
                skills_domain=["アプリ領域"],
                skills_free="Project Management, Agile, Scrum",
                department="プロジェクト管理部"
            )
            r_frontend = Resource(
                name="Lead Frontend Engineer",
                email="frontend@example.com",
                password_hash=hashed_default,
                role="SE",
                start_time="10:00",
                end_time="19:00",
                break_hours=1.0,
                daily_working_hours=8.0,
                hourly_cost_jpy=6500,
                system_role="メンバー",
                is_active=True,
                skills_phase=["設計", "実装", "テスト"],
                skills_domain=["アプリ領域"],
                skills_free="Vue.js, Vue3, Vuetify3, TailwindCSS, CSS, TypeScript",
                department="フロントエンド開発課"
            )
            r_ai = Resource(
                name="AI_WORKER",
                email="ai_worker@example.com",
                password_hash=hashed_default,
                role="AI Agent",
                start_time="00:00",
                end_time="24:00",
                break_hours=0.0,
                daily_working_hours=24.0,
                hourly_cost_jpy=100,
                system_role="メンバー",
                is_active=False, # Pure resource, not a logged in user
                skills_phase=["実装", "テスト"],
                skills_domain=["アプリ領域"],
                skills_free="FastAPI, Python, Qdrant, AI Agent",
                department="AI自動化課"
            )
            db.add(r_admin)
            db.add(r_manager)
            db.add(r_frontend)
            db.add(r_ai)
            await db.flush()
            
            # Seed default holidays
            holiday1 = CalendarHoliday(
                date="2026-01-01",
                name="元日",
                is_company_holiday=False,
                year=2026
            )
            holiday2 = CalendarHoliday(
                date="2026-06-15",
                name="AI-PMO創立記念日",
                is_company_holiday=True,
                year=2026
            )
            db.add(holiday1)
            db.add(holiday2)
            
            # 1. Seed Projects
            proj1 = Project(
                name="プロジェクトAlpha (自律協働型管理プラットフォーム)",
                status="ACTIVE"
            )
            proj2 = Project(
                name="プロジェクトBeta (DX基幹業務システム刷新)",
                status="ACTIVE"
            )
            db.add(proj1)
            db.add(proj2)
            await db.flush()
            
            # 2. Seed Resource Allocations
            # Lead Frontend Engineer is shared: 80% on Project Alpha, 20% on Project Beta
            alloc1 = ResourceAllocation(
                project_id=proj1.id,
                resource_id=r_frontend.id,
                resource_name=r_frontend.name,
                skill_tags=["Vue3", "Vuetify3", "CSS"],
                allocation_percent=80,
                is_ai=False
            )
            alloc2 = ResourceAllocation(
                project_id=proj2.id,
                resource_id=r_frontend.id,
                resource_name=r_frontend.name,
                skill_tags=["Vue3", "Vuetify3", "CSS"],
                allocation_percent=20,
                is_ai=False
            )
            # AI Worker on Project Alpha
            alloc_ai = ResourceAllocation(
                project_id=proj1.id,
                resource_id=r_ai.id,
                resource_name=r_ai.name,
                skill_tags=["FastAPI", "Python", "Qdrant"],
                allocation_percent=100,
                is_ai=True
            )
            db.add(alloc1)
            db.add(alloc2)
            db.add(alloc_ai)
            
            # 3. Seed WBS Tasks for Project Alpha
            # Task 1 (Done)
            t1 = Task(
                project_id=proj1.id,
                title="データベースインフラ構築 (PostgreSQL/Qdrant)",
                description="開発用の PostgreSQL および Qdrant コンテナの立ち上げ、および疎通確認。",
                status="DONE",
                priority="HIGH",
                assignee_type="HUMAN",
                assignee_name="Manager",
                planned_start=now - timedelta(days=5),
                planned_end=now - timedelta(days=3),
                actual_start=now - timedelta(days=5),
                actual_end=now - timedelta(days=3),
                progress=100,
                delay_days=0
            )
            db.add(t1)
            
            # Task 2 (Pending AI approval)
            t2 = Task(
                project_id=proj1.id,
                title="APIエンドポイント自動実装とモックアップ",
                description="オーケストレーターがサブタスクを分解し、ワーカーがエンドポイントとデータを生成する。",
                status="TODO",
                priority="MEDIUM",
                assignee_type="AI",
                assignee_name="AI_WORKER",
                planned_start=now + timedelta(days=1),
                planned_end=now + timedelta(days=4),
                progress=0,
                delay_days=0
            )
            db.add(t2)
            await db.flush()
            
            # Seed Plan and subtasks for Task 2
            plan2 = Plan(
                task_id=t2.id,
                approach_summary="FastAPI API Router を作成し、Pydantic v2 スキーマを用いた型安全な CRUD エンドポイントを実装します。成果物はローカルフォルダ artifacts/ に書き出します。",
                status="DRAFT"
            )
            db.add(plan2)
            
            sub1 = SubTask(
                task_id=t2.id,
                title="FastAPI routerとスキーマ定義の作成",
                description="Pydantic モデルを用いたリクエスト・レスポンススキーマの実装と検証。",
                status="PENDING",
                agent_id="AI_WORKER"
            )
            sub2 = SubTask(
                task_id=t2.id,
                title="モックデータ用エンドポイントの作成",
                description="フロントエンド結合用の擬似データを返すエンドポイントのモック作成。",
                status="PENDING",
                agent_id="AI_WORKER"
            )
            db.add(sub1)
            db.add(sub2)
            
            # Task 3 (Delayed Human Task)
            t3 = Task(
                project_id=proj1.id,
                title="フロントエンド UI デザイン (ダークモード・グラスモーフィズム)",
                description="Vuetify 3 と CSS backdrop-filter を用いたすりガラス効果画面の開発。",
                status="IN_PROGRESS",
                priority="HIGH",
                assignee_type="HUMAN",
                assignee_name="Lead Frontend Engineer",
                planned_start=now - timedelta(days=2),
                planned_end=now + timedelta(days=1),
                progress=45,
                delay_days=2
            )
            db.add(t3)
            await db.flush()
            
            # 4. Seed WBS Tasks for Project Beta
            tb1 = Task(
                project_id=proj2.id,
                title="要件定義とUXモック作成",
                description="事業部門へのヒアリングおよびFigmaを使用した画面遷移設計の作成。",
                status="DONE",
                priority="MEDIUM",
                assignee_type="HUMAN",
                assignee_name="Manager",
                planned_start=now - timedelta(days=4),
                planned_end=now - timedelta(days=2),
                actual_start=now - timedelta(days=4),
                actual_end=now - timedelta(days=2),
                progress=100,
                delay_days=0
            )
            db.add(tb1)
            
            tb2 = Task(
                project_id=proj2.id,
                title="決済ゲートウェイ連携API開発",
                description="外部のクレジットカード決済プロバイダー（Stripe等）とシステムを連携するAPIの実装。",
                status="IN_PROGRESS",
                priority="HIGH",
                assignee_type="HUMAN",
                assignee_name="Lead Frontend Engineer",
                planned_start=now,
                planned_end=now + timedelta(days=4),
                progress=10,
                delay_days=0
            )
            db.add(tb2)
            await db.flush()
            
            # Establish dependencies by direct insert
            from app.models.task import task_dependency
            # Project Alpha: Task 3 depends on Task 1, Task 2 depends on Task 3
            await db.execute(task_dependency.insert().values(task_id=t3.id, depends_on_id=t1.id))
            await db.execute(task_dependency.insert().values(task_id=t2.id, depends_on_id=t3.id))
            # Project Beta: Task 2 depends on Task 1
            await db.execute(task_dependency.insert().values(task_id=tb2.id, depends_on_id=tb1.id))
            
            # Seed hearing messages for Task 3 (Project Alpha)
            msg1 = Message(
                sender_type="AI_PMO",
                sender_name="AI_PMO",
                content=(
                    f"【遅延警告】タスク「{t3.title}」の完了予定が期限を過ぎています。現在、約 2日の遅延アラートが出ています。\n"
                    "完了までの『リアルな残工数（例: あと5時間、1.5人日）』をこのチャットにてお答えください。"
                ),
                task_id=t3.id
            )
            db.add(msg1)
            
            # Seed an inline review comment on Task 3
            comment1 = Comment(
                task_id=t3.id,
                line_number=7,
                content="インラインレビュー: この行で使用されている背景透明度の指定 (rgba(255, 255, 255, 0.5)) は、コントラストが低くアクセシビリティ基準に適合していません。rgba(255, 255, 255, 0.05) と backdrop-filter blur を組み合わせてください。",
                author="AI_PMO"
            )
            db.add(comment1)
            
            await db.commit()
            logger.info("Demo database seeding finished successfully.")

    logger.info("Database initialized successfully.")

    # Seed Lessons Learned Qdrant collection
    await _seed_lessons_learned()
    # Seed Governance Rules Qdrant collection
    await _seed_governance_rules()

    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup Exception Handlers
setup_exception_handlers(app)

# Include Router
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {
        "message": f"Welcome to the {settings.PROJECT_NAME}",
        "docs": "/docs",
        "api_version": "v1"
    }
