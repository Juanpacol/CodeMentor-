import uuid
from datetime import datetime

from pydantic import BaseModel


class RagDocumentOut(BaseModel):
    id: uuid.UUID
    title: str
    source_type: str
    topic_id: uuid.UUID | None
    chunk_count: int
    created_at: datetime
