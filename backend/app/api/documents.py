"""
Documents API
─────────────
POST /api/documents/upload  — upload a PDF
GET  /api/documents/{id}    — get document status
GET  /api/documents/        — list all documents
"""
import os
import uuid
import json
from datetime import datetime

# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, BackgroundTasks
# pyrefly: ignore [missing-import]
from sqlmodel import Session, select
import aiofiles

from app.core.database import get_session
from app.core.config import UPLOAD_DIR, MAX_UPLOAD_MB
from app.models.document import Document, DocumentRead
from app.models.template import Template
from app.models.mapping import FieldMapping
from app.services.pdf_extractor import extract_text_from_pdf, PDFExtractionError
from app.services.ai_extractor import extract_template_with_ai, AIExtractionError

router = APIRouter()

MAX_BYTES = MAX_UPLOAD_MB * 1024 * 1024


async def _process_document(document_id: int, file_path: str, db_url: str):
    """Background task: extract text and run AI template extraction."""
    # pyrefly: ignore [missing-import]
    from sqlmodel import create_engine, Session as S

    engine = create_engine(db_url, connect_args={"check_same_thread": False})

    with S(engine) as session:
        doc = session.get(Document, document_id)
        if not doc:
            return

        # Step 1: Extract text from PDF
        try:
            raw_text, page_count = extract_text_from_pdf(file_path)
            doc.raw_text = raw_text
            doc.page_count = page_count
            doc.status = "extracting"
            doc.updated_at = datetime.utcnow()
            session.add(doc)
            session.commit()
        except PDFExtractionError as e:
            doc.status = "failed"
            doc.error_message = f"PDF extraction failed: {str(e)}"
            doc.updated_at = datetime.utcnow()
            session.add(doc)
            session.commit()
            return

        # Step 2: AI template extraction
        try:
            result = extract_template_with_ai(raw_text)
        except AIExtractionError as e:
            doc.status = "failed"
            doc.error_message = f"AI extraction failed: {str(e)}"
            doc.updated_at = datetime.utcnow()
            session.add(doc)
            session.commit()
            return
        except Exception as e:
            doc.status = "failed"
            doc.error_message = f"Unexpected error during AI extraction: {str(e)}"
            doc.updated_at = datetime.utcnow()
            session.add(doc)
            session.commit()
            return

        # Step 3: Save the extracted template
        import json as _json
        fields = result.get("fields", [])
        template = Template(
            document_id=document_id,
            name=result.get("template_name", "Untitled Template"),
            description=result.get("description", ""),
            fields_json=_json.dumps(fields),
            template_body=result.get("template_body", ""),
            document_type=result.get("document_type", "general"),
            status="draft",
            extraction_warnings=_json.dumps(result.get("warnings", [])),
        )
        session.add(template)
        session.flush()  # get template.id before committing

        # Step 4: Auto-create literal mappings for author (issuing-party) fields
        # These are fields whose values are already known from the source document.
        author_mappings_created = 0
        for field in fields:
            if not field.get("is_author_field", False):
                continue
            example = str(field.get("example_value") or "").strip()
            if not example:
                continue  # skip if AI didn't provide a value
            mapping = FieldMapping(
                template_id=template.id,
                field_key=field["key"],
                mapping_type="literal",
                literal_value=example,
            )
            session.add(mapping)
            author_mappings_created += 1

        doc.status = "extracted"
        doc.updated_at = datetime.utcnow()
        session.add(doc)
        session.commit()


@router.post("/upload", response_model=DocumentRead, status_code=201)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"File exceeds {MAX_UPLOAD_MB}MB limit.")

    safe_name = f"{uuid.uuid4().hex}.pdf"
    file_path = os.path.join(UPLOAD_DIR, safe_name)

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    doc = Document(
        filename=safe_name,
        original_filename=file.filename,
        file_path=file_path,
        file_size=len(content),
        status="uploaded",
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)

    from app.core.config import UPLOAD_DIR as _  # noqa
    import os as _os
    db_url = _os.getenv("DATABASE_URL", "sqlite:///./data/app.db")
    background_tasks.add_task(_process_document, doc.id, file_path, db_url)

    return doc


@router.get("/", response_model=list[DocumentRead])
def list_documents(session: Session = Depends(get_session)):
    docs = session.exec(select(Document).order_by(Document.created_at.desc())).all()
    return docs


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(document_id: int, session: Session = Depends(get_session)):
    doc = session.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc