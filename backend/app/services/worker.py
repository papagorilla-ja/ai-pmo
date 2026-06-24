import os
import uuid
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.llm import llm_service
from app.config import settings
from app.models.subtask import SubTask
from app.models.comment import Comment

logger = logging.getLogger(__name__)

class WorkerService:
    async def execute_subtask(self, db: AsyncSession, subtask: SubTask) -> str:
        """
        Executes a single microtask:
        1. Calls LLM to generate the actual code/content.
        2. Writes the generated artifact file to local disk.
        3. Generates inline comments (e.g. reviews/warnings) if applicable.
        4. Updates subtask status to REVIEW.
        """
        logger.info(f"Worker starting execution of subtask: {subtask.id} - {subtask.title}")
        subtask.status = "IN_PROGRESS"
        await db.commit()
        
        system_prompt = (
            "You are the AI Worker Agent. You specialize in executing precise technical microtasks.\n"
            "Your task is to write the actual file content (code, mock data, configuration, or markdown document) "
            "requested by the microtask description.\n"
            "Return ONLY the raw content of the file. Do not write any markdown code fences (like ```python) "
            "or conversational filler. Just return the code or document content directly."
        )
        
        user_prompt = (
            f"Microtask: {subtask.title}\n"
            f"Description: {subtask.description}\n\n"
            f"Please write the file contents that fulfills this task."
        )
        
        try:
            content = await llm_service.get_response(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.3
            )
            
            # Determine file extension based on title
            ext = ".txt"
            title_lower = subtask.title.lower()
            if any(w in title_lower for w in ["api", "mock", "code", "python", "script"]):
                ext = ".py"
            elif any(w in title_lower for w in ["document", "doc", "spec", "markdown", "design"]):
                ext = ".md"
            elif any(w in title_lower for w in ["config", "json", "settings"]):
                ext = ".json"
            elif any(w in title_lower for w in ["yaml", "yml"]):
                ext = ".yaml"
                
            filename = f"subtask_{subtask.id}{ext}"
            os.makedirs(settings.ARTIFACT_STORAGE_PATH, exist_ok=True)
            filepath = os.path.join(settings.ARTIFACT_STORAGE_PATH, filename)
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
                
            logger.info(f"Successfully wrote worker output to {filepath}")
            subtask.output_mock_path = filepath
            subtask.status = "REVIEW"
            subtask.completed_at = datetime.now(timezone.utc)
            
            # Generate an AI review comment on the parent task
            # Example: "Worker completed this subtask. Here is a note."
            review_comment = Comment(
                task_id=subtask.task_id,
                content=f"AIワーカーがサブタスク「{subtask.title}」の成果物を生成しました。成果物パス: {filename}\nレビューをお願いします。",
                author="AI_WORKER",
                line_number=None
            )
            db.add(review_comment)
            await db.commit()
            return filepath
            
        except Exception as e:
            logger.error(f"Worker execution failed for subtask {subtask.id}: {str(e)}")
            # Fallback output in case of error
            filename = f"subtask_{subtask.id}_failed.txt"
            os.makedirs(settings.ARTIFACT_STORAGE_PATH, exist_ok=True)
            filepath = os.path.join(settings.ARTIFACT_STORAGE_PATH, filename)
            
            error_content = f"Error during automated execution: {str(e)}"
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(error_content)
                
            subtask.output_mock_path = filepath
            subtask.status = "REVIEW" # Set to review even if failed, so human can see failure
            subtask.completed_at = datetime.now(timezone.utc)
            
            review_comment = Comment(
                task_id=subtask.task_id,
                content=f"⚠️ AIワーカーによるサブタスク「{subtask.title}」の実行中にエラーが発生しました。\nエラー内容: {str(e)}",
                author="AI_WORKER",
                line_number=None
            )
            db.add(review_comment)
            await db.commit()
            return filepath

worker_service = WorkerService()
