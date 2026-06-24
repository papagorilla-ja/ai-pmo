import uuid
from sqlalchemy import String, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class Repository(Base):
    __tablename__ = "repositories"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(50), default="LOCAL") # LOCAL, GITHUB
    path: Mapped[str] = mapped_column(String, nullable=False)      # Local path or GitHub url
    config: Mapped[dict] = mapped_column(JSON, default=dict)       # Configuration options
