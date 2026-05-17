from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class Document(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    original_filename: str
    file_path: str
    file_size: int
    page_count: int = 0
    raw_text: Optional[str] = None
    status: str = "uploaded"  # uploaded | extracting | extracted | failed
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentRead(SQLModel):
    id: int
    filename: str
    original_filename: str
    file_size: int
    page_count: int
    status: str
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime