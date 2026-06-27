import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App Settings
    PROJECT_NAME: str = "AI-PMO API"
    API_V1_STR: str = "/api/v1"
    
    # Database Settings
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql+asyncpg://postgres:postgres@localhost:5435/ai_pmo"
    )
    
    # Vector DB Settings
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6335")
    QDRANT_COLLECTION_NAME: str = "ai_pmo_knowledge"
    QDRANT_LESSONS_COLLECTION_NAME: str = "lessons_learned"
    QDRANT_GOVERNANCE_COLLECTION_NAME: str = "governance_rules"
    
    # LLM Settings (LM Studio)
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "http://localhost:1234/v1")
    LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "qwen3.6-35b-a3b-ud-mlx")
    LLM_TIMEOUT_SECONDS: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "300"))

    # Gitea Settings
    GITEA_BASE_URL: str = os.getenv("GITEA_BASE_URL", "http://localhost:3000")
    GITEA_ADMIN_TOKEN: str = os.getenv("GITEA_ADMIN_TOKEN", "")
    GITEA_WEBHOOK_SECRET: str = os.getenv("GITEA_WEBHOOK_SECRET", "ai_pmo_webhook_secret")
    
    # Artifact Output Storage (Local folder writing)
    ARTIFACT_STORAGE_PATH: str = os.getenv(
        "ARTIFACT_STORAGE_PATH", 
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "artifacts")
    )

    # JWT Auth Settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "b3d8f1e6a4b2c89f5d32e18d6e9382f7c0a9b8d7e6f5a4b3c2d1e0f9a8b7c6d5")
    ACCESS_TOKEN_EXPIRE_HOURS: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "12"))
    ALGORITHM: str = "HS256"

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
