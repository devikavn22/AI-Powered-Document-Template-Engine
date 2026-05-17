from datetime import datetime
from typing import Optional
import json
from sqlmodel import SQLModel, Field


class Generation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    template_id: int = Field(foreign_key="template.id")
    transaction_payload: str   # JSON: the raw data payload submitted
    resolved_values: Optional[str] = None  # JSON: field_key -> resolved value
    missing_fields: Optional[str] = None   # JSON: list of unmapped/missing field keys
    flagged_fields: Optional[str] = None   # JSON: list of flagged field keys with reasons
    output_filename: Optional[str] = None
    output_path: Optional[str] = None
    status: str = "pending"  # pending | generating | completed | failed
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class GenerationRequest(SQLModel):
    """The transaction payload sent by the user to fill a template."""
    buyer: Optional[dict] = None
    seller: Optional[dict] = None
    property: Optional[dict] = None
    deal: Optional[dict] = None
    agent: Optional[dict] = None
    bank: Optional[dict] = None
    witness: Optional[dict] = None
    system: Optional[dict] = None
    # Direct field-key overrides entered by the user at generation time.
    # These take highest priority and override any mapping-based resolution.
    field_overrides: Optional[dict] = None


class GenerationRead(SQLModel):
    id: int
    template_id: int
    missing_fields: Optional[str]
    flagged_fields: Optional[str]
    output_filename: Optional[str]
    status: str
    error_message: Optional[str]
    created_at: datetime