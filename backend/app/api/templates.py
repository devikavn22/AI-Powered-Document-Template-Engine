"""
Templates API
─────────────
GET    /api/templates/                  — list templates
GET    /api/templates/{id}              — get template
PATCH  /api/templates/{id}             — update (edit fields / confirm)
GET    /api/templates/{id}/schema      — return entity schema for mapping UI
"""
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.database import get_session
from app.models.template import Template, TemplateRead, TemplateUpdate
from app.models.mapping import ENTITY_SCHEMA

router = APIRouter()


@router.get("/", response_model=list[TemplateRead])
def list_templates(session: Session = Depends(get_session)):
    templates = session.exec(select(Template).order_by(Template.created_at.desc())).all()
    return templates


@router.get("/entity-schema")
def get_entity_schema():
    """Return the full entity schema so the frontend can build mapping dropdowns."""
    return ENTITY_SCHEMA


@router.get("/{template_id}", response_model=TemplateRead)
def get_template(template_id: int, session: Session = Depends(get_session)):
    t = session.get(Template, template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template not found.")
    return t


@router.patch("/{template_id}", response_model=TemplateRead)
def update_template(
    template_id: int,
    update: TemplateUpdate,
    session: Session = Depends(get_session),
):
    t = session.get(Template, template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template not found.")

    update_data = update.model_dump(exclude_unset=True)

    # Validate fields_json if provided
    if "fields_json" in update_data:
        try:
            parsed = json.loads(update_data["fields_json"])
            if not isinstance(parsed, list):
                raise ValueError("fields_json must be a JSON array")
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(status_code=422, detail=f"Invalid fields_json: {e}")

    for key, val in update_data.items():
        setattr(t, key, val)

    t.updated_at = datetime.utcnow()
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


@router.post("/{template_id}/confirm", response_model=TemplateRead)
def confirm_template(template_id: int, session: Session = Depends(get_session)):
    """Mark a template as confirmed — ready for mapping and generation."""
    t = session.get(Template, template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template not found.")
    t.status = "confirmed"
    t.updated_at = datetime.utcnow()
    session.add(t)
    session.commit()
    session.refresh(t)
    return t