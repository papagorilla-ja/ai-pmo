import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.router import api_router
from app.core.exceptions import setup_exception_handlers
from app.database import engine, Base

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
