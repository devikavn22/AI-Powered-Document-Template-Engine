"""
Mappings API
────────────
GET  /api/mappings/{template_id}         — get all mappings for a template
POST /api/mappings/{template_id}         — upsert a batch of field mappings
PUT  /api/mappings/{template_id}/{key}   — update a single field mapping
"""
import json
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.database import get_session
from app.models.template import Template
from app.models.mapping import FieldMapping, FieldMappingCreate, FieldMappingRead, ENTITY_SCHEMA

router = APIRouter()


def _validate_mapping(m: FieldMappingCreate, template_fields: list) -> str | None:
    """Return an error string if the mapping is invalid, else None."""
    valid_keys = {f["key"] for f in template_fields}
    if m.field_key not in valid_keys:
        return f"Field key '{m.field_key}' not found in template"

    if m.mapping_type not in ("entity", "literal", "unmapped"):
        return f"mapping_type must be entity | literal | unmapped, got '{m.mapping_type}'"

    if m.mapping_type == "entity":
        if not m.entity or not m.attribute:
            return "entity and attribute are required for entity mappings"
        if m.entity not in ENTITY_SCHEMA:
            return f"Unknown entity '{m.entity}'"
        if m.attribute not in ENTITY_SCHEMA[m.entity]["attributes"]:
            return f"Unknown attribute '{m.attribute}' for entity '{m.entity}'"

    if m.mapping_type == "literal" and not m.literal_value:
        return "literal_value is required for literal mappings"

    return None


@router.get("/{template_id}", response_model=list[FieldMappingRead])
def get_mappings(template_id: int, session: Session = Depends(get_session)):
    t = session.get(Template, template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template not found.")

    mappings = session.exec(
        select(FieldMapping).where(FieldMapping.template_id == template_id)
    ).all()
    return mappings


@router.post("/{template_id}", response_model=list[FieldMappingRead], status_code=200)
def upsert_mappings(
    template_id: int,
    mappings: List[FieldMappingCreate],
    session: Session = Depends(get_session),
):
    """Upsert a batch of mappings for a template. Existing mappings for the same key are replaced."""
    t = session.get(Template, template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template not found.")

    template_fields = json.loads(t.fields_json)
    errors = []

    for m in mappings:
        err = _validate_mapping(m, template_fields)
        if err:
            errors.append(err)

    if errors:
        raise HTTPException(status_code=422, detail={"errors": errors})

    results = []
    for m in mappings:
        # Check if exists
        existing = session.exec(
            select(FieldMapping).where(
                FieldMapping.template_id == template_id,
                FieldMapping.field_key == m.field_key,
            )
        ).first()

        if existing:
            existing.mapping_type = m.mapping_type
            existing.entity = m.entity
            existing.attribute = m.attribute
            existing.literal_value = m.literal_value
            existing.updated_at = datetime.utcnow()
            session.add(existing)
            results.append(existing)
        else:
            new_m = FieldMapping(
                template_id=template_id,
                field_key=m.field_key,
                mapping_type=m.mapping_type,
                entity=m.entity,
                attribute=m.attribute,
                literal_value=m.literal_value,
            )
            session.add(new_m)
            results.append(new_m)

    session.commit()
    for r in results:
        session.refresh(r)

    return results