import hmac, hashlib, uuid, re, logging, json
import httpx
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any
from app.config import settings
from app.models.task import Task
from app.models.knowledge import Knowledge
from app.services.llm import llm_service
from app.services.rag import rag_service

logger = logging.getLogger(__name__)


class GiteaService:

    def verify_signature(self, body: bytes, signature: str) -> bool:
        """X-Gitea-Signature の HMAC-SHA256 検証"""
        expected = "sha256=" + hmac.new(
            settings.GITEA_WEBHOOK_SECRET.encode(), body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature or "")

    async def handle_webhook(self, event: str, payload: dict, db: AsyncSession):
        if event == "push":
            await self.handle_push(payload, db)
        elif event == "pull_request":
            pr = payload.get("pull_request", {})
            if payload.get("action") == "closed" and pr.get("merged"):
                await self.handle_pr_merged(payload, db)

    async def handle_push(self, payload: dict, db: AsyncSession):
        """
        コミットメッセージ記法:
          [PMO:{task_id先頭8文字以上}] タイトル #完了 [3h]
        ステータスキーワード: #完了/#done/#fix/#close → DONE
                             #進行中/#wip/#start → IN_PROGRESS
                             #レビュー/#review → REVIEW
        工数記法: [Nh] → N時間加算 / [Nm] → N分加算（上書きでなく加算）
        """
        commits = payload.get("commits") or []
        for commit in commits:
            msg = commit.get("message") or ""
            m = re.search(r'\[PMO:([a-f0-9\-]{8,})\]', msg, re.IGNORECASE)
            if not m:
                continue
            prefix = m.group(1).lower().replace("-", "")

            result = await db.execute(select(Task))
            tasks = result.scalars().all()
            target = next(
                (t for t in tasks if str(t.id).replace("-", "").startswith(prefix)),
                None
            )
            if not target:
                logger.warning(f"Gitea push: no task matched prefix '{prefix}'")
                continue

            status_map = {
                r'#完了|#done|#fix|#close': "DONE",
                r'#進行中|#wip|#start': "IN_PROGRESS",
                r'#レビュー|#review': "REVIEW",
            }
            for pattern, new_status in status_map.items():
                if re.search(pattern, msg, re.IGNORECASE):
                    target.status = new_status
                    if new_status == "DONE" and target.actual_end is None:
                        target.actual_end = datetime.now(timezone.utc)
                    break

            h_match = re.search(r'\[(\d+(?:\.\d+)?)h\]', msg, re.IGNORECASE)
            m_match = re.search(r'\[(\d+)m\]', msg, re.IGNORECASE)
            if h_match:
                target.actual_hours = (target.actual_hours or 0.0) + float(h_match.group(1))
            if m_match:
                target.actual_hours = (target.actual_hours or 0.0) + float(m_match.group(1)) / 60.0

            await db.commit()
            logger.info(f"Gitea push: task {target.id} status={target.status} actual_hours={target.actual_hours}")

    async def handle_pr_merged(self, payload: dict, db: AsyncSession):
        pr = payload.get("pull_request", {})
        title = pr.get("title") or ""
        body = pr.get("body") or ""
        full_text = f"{title}\n{body}"

        # PR本文に [PMO:...] があればタスクを完了に
        m = re.search(r'\[PMO:([a-f0-9\-]{8,})\]', full_text, re.IGNORECASE)
        if m:
            prefix = m.group(1).lower().replace("-", "")
            result = await db.execute(select(Task))
            tasks = result.scalars().all()
            target = next(
                (t for t in tasks if str(t.id).replace("-", "").startswith(prefix)),
                None
            )
            if target:
                target.status = "DONE"
                if target.actual_end is None:
                    target.actual_end = datetime.now(timezone.utc)
                await db.commit()

        # 本文が短すぎる場合は教訓抽出しない
        if len(full_text) < 100:
            return

        try:
            system_prompt = (
                "あなたはプロジェクト管理の教訓(Lessons-Learned)抽出AIです。"
                "GitのPRの内容から今後のプロジェクトで活かせる教訓・注意点・ベストプラクティスを抽出してください。"
                '出力は JSON 配列のみ: [{"title": "30字以内", "content": "200字以内"}]'
                "該当なければ空配列 []。解説不要、JSONのみ出力。"
            )
            raw = await llm_service.get_response(system_prompt, full_text, temperature=0.3)

            # コードフェンス除去（planning_service._clean_json_string と同じ処理）
            cleaned = re.sub(r'^```(?:json)?\s*', '', raw.strip(), flags=re.MULTILINE)
            cleaned = re.sub(r'\s*```$', '', cleaned.strip(), flags=re.MULTILINE)
            lessons = json.loads(cleaned.strip())
            if not isinstance(lessons, list):
                return

            documents, metadatas = [], []
            for lesson in lessons:
                t = (lesson.get("title") or "").strip()
                c = (lesson.get("content") or "").strip()
                if not t or not c:
                    continue
                documents.append(f"{t}\n{c}")
                metadatas.append({"type": "gitea_pr", "title": t, "source": "gitea_pr"})

            if documents:
                doc_ids = [str(uuid.uuid5(uuid.NAMESPACE_DNS, f"gitea_pr_{d[:60]}")) for d in documents]
                registered = await rag_service.add_documents(documents, metadatas, doc_ids)
                for i, doc_id in enumerate(registered):
                    existing = (await db.execute(
                        select(Knowledge).where(Knowledge.qdrant_id == doc_id)
                    )).scalar_one_or_none()
                    if not existing:
                        db.add(Knowledge(
                            qdrant_id=doc_id,
                            content=documents[i],
                            source="gitea_pr",
                            confidence_score=0.8,
                            status="ACTIVE"
                        ))
                await db.commit()
                logger.info(f"Gitea PR: registered {len(registered)} lessons")
        except Exception as e:
            logger.error(f"Gitea PR lesson extraction failed: {e}")

    async def crawl_repository(self, repo: str, db: AsyncSession) -> dict:
        """
        repo: "{owner}/{repo}" 形式。
        .md/.txt/.rst を最大50件取得して Qdrant / Knowledge に登録。
        """
        if not settings.GITEA_ADMIN_TOKEN:
            logger.warning("GITEA_ADMIN_TOKEN not set. Skipping crawl.")
            return {"crawled": 0}

        headers = {"Authorization": f"token {settings.GITEA_ADMIN_TOKEN}"}
        EXTENSIONS = {".md", ".txt", ".rst"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{settings.GITEA_BASE_URL}/api/v1/repos/{repo}/git/trees/HEAD?recursive=true",
                headers=headers
            )
            if resp.status_code != 200:
                logger.error(f"Gitea tree API failed: {resp.status_code} for {repo}")
                return {"crawled": 0}

            targets = [
                f for f in (resp.json().get("tree") or [])
                if f.get("type") == "blob"
                and any(f.get("path", "").endswith(ext) for ext in EXTENSIONS)
            ][:50]

            documents, metadatas = [], []
            for f in targets:
                path = f["path"]
                raw_resp = await client.get(
                    f"{settings.GITEA_BASE_URL}/api/v1/repos/{repo}/raw/{path}?ref=HEAD",
                    headers=headers
                )
                if raw_resp.status_code != 200:
                    continue
                documents.append(f"{path}\n{raw_resp.text[:2000]}")
                metadatas.append({"type": "gitea_doc", "title": path, "source": "gitea_doc", "repo": repo})

        if not documents:
            return {"crawled": 0}

        doc_ids = [
            str(uuid.uuid5(uuid.NAMESPACE_DNS, f"gitea_doc_{repo}_{meta['title']}"))
            for meta in metadatas
        ]
        registered = await rag_service.add_documents(documents, metadatas, doc_ids)
        for i, doc_id in enumerate(registered):
            existing = (await db.execute(
                select(Knowledge).where(Knowledge.qdrant_id == doc_id)
            )).scalar_one_or_none()
            if not existing:
                db.add(Knowledge(
                    qdrant_id=doc_id,
                    content=documents[i],
                    source="gitea_doc",
                    confidence_score=1.0,
                    status="ACTIVE"
                ))
        await db.commit()
        logger.info(f"Gitea crawl: indexed {len(registered)} docs from {repo}")
        return {"crawled": len(registered)}

    async def list_repos(self) -> dict:
        if not settings.GITEA_ADMIN_TOKEN:
            return {"repos": [], "configured": False}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{settings.GITEA_BASE_URL}/api/v1/repos/search?limit=50",
                    headers={"Authorization": f"token {settings.GITEA_ADMIN_TOKEN}"}
                )
                if resp.status_code != 200:
                    return {"repos": [], "configured": True}
                repos = [
                    {"full_name": r["full_name"], "description": r.get("description", ""), "html_url": r.get("html_url", "")}
                    for r in (resp.json().get("data") or [])
                ]
                return {"repos": repos, "configured": True}
        except Exception as e:
            logger.error(f"Gitea list_repos failed: {e}")
            return {"repos": [], "configured": True}


gitea_service = GiteaService()
