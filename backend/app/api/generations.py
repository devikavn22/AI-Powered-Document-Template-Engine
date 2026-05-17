"""
Generations API
───────────────
POST /api/generations/{template_id}          — generate a filled PDF
GET  /api/generations/{template_id}          — list generations for template
GET  /api/generations/{template_id}/{gen_id} — get generation status
GET  /api/generations/download/{gen_id}      — download the PDF
"""
import json
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from app.core.database import get_session
from app.models.template import Template
from app.models.mapping import FieldMapping
from app.models.generation import Generation, GenerationRequest, GenerationRead
from app.services.pdf_generator import generate_pdf, GenerationError

router = APIRouter()


@router.post("/{template_id}", response_model=GenerationRead, status_code=201)
def create_generation(
    template_id: int,
    payload: GenerationRequest,
    session: Session = Depends(get_session),
):
    t = session.get(Template, template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template not found.")

    if t.status != "confirmed":
        raise HTTPException(
            status_code=400,
            detail="Template must be confirmed before generating documents.",
        )

    mappings = session.exec(
        select(FieldMapping).where(FieldMapping.template_id == template_id)
    ).all()

    template_fields = json.loads(t.fields_json)
    all_field_keys = [f["key"] for f in template_fields]

    payload_dict = payload.model_dump(exclude_none=True)

    gen = Generation(
        template_id=template_id,
        transaction_payload=json.dumps(payload_dict),
        status="generating",
    )
    session.add(gen)
    session.commit()
    session.refresh(gen)

    try:
        output_path, filename, flagged = generate_pdf(
            template_body=t.template_body,
            template_name=t.name,
            mappings=list(mappings),
            payload=payload_dict,
            all_field_keys=all_field_keys,
        )

        gen.output_path = output_path
        gen.output_filename = filename
        gen.flagged_fields = json.dumps(flagged)
        gen.missing_fields = json.dumps([f["key"] for f in flagged])
        gen.status = "completed"
        gen.updated_at = datetime.utcnow()

    except GenerationError as e:
        gen.status = "failed"
        gen.error_message = str(e)
        gen.updated_at = datetime.utcnow()

    except Exception as e:
        gen.status = "failed"
        gen.error_message = f"Unexpected error: {str(e)}"
        gen.updated_at = datetime.utcnow()

    session.add(gen)
    session.commit()
    session.refresh(gen)

    if gen.status == "failed":
        raise HTTPException(
            status_code=500,
            detail={"error": gen.error_message},
        )

    return gen


@router.get("/{template_id}", response_model=list[GenerationRead])
def list_generations(template_id: int, session: Session = Depends(get_session)):
    gens = session.exec(
        select(Generation)
        .where(Generation.template_id == template_id)
        .order_by(Generation.created_at.desc())
    ).all()
    return gens


@router.get("/download/{generation_id}")
def download_generation(generation_id: int, session: Session = Depends(get_session)):
    gen = session.get(Generation, generation_id)
    if not gen:
        raise HTTPException(status_code=404, detail="Generation not found.")
    if gen.status != "completed":
        raise HTTPException(status_code=400, detail="Generation is not yet complete.")
    if not gen.output_path or not os.path.exists(gen.output_path):
        raise HTTPException(status_code=404, detail="Generated file not found on disk.")

    return FileResponse(
        path=gen.output_path,
        filename=gen.output_filename,
        media_type="application/pdf",
    )


@router.get("/status/{generation_id}", response_model=GenerationRead)
def get_generation(generation_id: int, session: Session = Depends(get_session)):
    gen = session.get(Generation, generation_id)
    if not gen:
        raise HTTPException(status_code=404, detail="Generation not found.")
    return gen