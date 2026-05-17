from datetime import datetime
from typing import Optional
import json
from sqlmodel import SQLModel, Field


class Template(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="document.id")
    name: str
    description: Optional[str] = None
    # JSON: list of TemplateField dicts
    fields_json: str = Field(default="[]")
    # JSON: the template body with {{FIELD_KEY}} placeholders
    template_body: str = Field(default="")
    document_type: str = "general"  # contract | agreement | allotment | invoice | general
    status: str = "draft"  # draft | confirmed
    extraction_warnings: Optional[str] = None  # JSON list of warning strings
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def fields(self):
        return json.loads(self.fields_json)

    @fields.setter
    def fields(self, value):
        self.fields_json = json.dumps(value)


class TemplateField(SQLModel):
    """A dynamic field extracted from the document."""
    key: str             # machine key: BUYER_NAME, DEAL_DATE, etc.
    label: str           # human label: "Buyer Name"
    description: str     # what this field represents
    field_type: str      # text | date | currency | number | address | identifier
    example_value: str   # extracted example from original doc
    required: bool = True


class TemplateRead(SQLModel):
    id: int
    document_id: int
    name: str
    description: Optional[str]
    fields_json: str
    template_body: str
    document_type: str
    status: str
    extraction_warnings: Optional[str]
    created_at: datetime
    updated_at: datetime


class TemplateUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    fields_json: Optional[str] = None
    template_body: Optional[str] = None
    document_type: Optional[str] = None
    status: Optional[str] = None