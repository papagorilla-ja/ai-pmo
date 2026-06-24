import logging
from openai import AsyncOpenAI
from app.config import settings

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key="lm-studio",  # LM Studio does not require a real API key but needs a placeholder
            # Local models (e.g. 30B+) need a generous timeout, especially for large
            # generations like WBS planning. 5s was far too short and timed out instantly.
            timeout=float(settings.LLM_TIMEOUT_SECONDS),
        )
        self.model = settings.LLM_MODEL_NAME

    async def get_response(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
        logger.info(f"Sending prompt to LLM Model '{self.model}' at url: '{settings.LLM_BASE_URL}'")
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            error_msg = (
                f"Failed to connect to LM Studio model '{self.model}' at {settings.LLM_BASE_URL}. "
                "Please ensure LM Studio is running and the model is fully loaded. "
                f"Error details: {str(e)}"
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)

llm_service = LLMService()
