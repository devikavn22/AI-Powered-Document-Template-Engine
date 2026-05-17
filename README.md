# DocTemplAI — AI-Powered Document Template Engine

A full-stack service that lets you upload a PDF contract or legal document, have AI extract a reusable template, map the dynamic fields to your transaction data model, and generate filled documents on demand.

---

## Quick Start

```bash
# 1. Clone / unzip the project
cd doc-template-engine

# 2. Set your Google Gemini API key
cp .env.example .env
# Edit .env and set GEMINI_API_KEY=your_key_here

# 3. Start everything
docker-compose up --build

# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API docs:    http://localhost:8000/docs
```

---

## End-to-End Workflow

### 1. Upload a PDF
- Upload any PDF: contracts, sale agreements, allotment letters, invoices
- The service extracts text using `pdfplumber` and passes it to LLM

### 2. AI Template Extraction
- The Gemini 2.5 Flash model analyzes the document and identifies every dynamic field
- Each field is given a typed key (text, date, currency, number, address, identifier)
- The template body is returned with `{{FIELD_KEY}}` placeholders
- **Any LLM output that is incomplete or unparseable raises an explicit error** — no silent failures
- Warnings from extraction are stored and shown in the review UI

### 3. Review & Confirm
- Review all extracted fields and the template body
- Edit the template name if needed
- Click **Confirm Template** to proceed

### 4. Map Fields
- Map each `{{FIELD_KEY}}` to one of three source types:
  - **Entity Field**: a property of a known entity (buyer, seller, property, deal, agent, bank, witness, system)
  - **Literal Value**: a static string that never changes
  - **Unmapped**: explicitly left for flagging at generation time

### 5. Generate Documents
- Submit a transaction payload (fill in entity data in the UI)
- The service resolves every field:
  - Mapped fields are filled from the payload
  - **Any unmapped or missing field is flagged with `[MISSING: KEY]`** — never silently blank
  - Missing fields are listed in the generation response
- Download the generated PDF

---

## Data Model

### Entity Schema

The mapping system supports these canonical entities:

| Entity | Description |
|--------|-------------|
| `buyer` | Buyer / Client (name, contact, address, PAN, etc.) |
| `seller` | Seller / Vendor Company (registration, GST, signatory, etc.) |
| `property` | Property / Unit (unit number, area, address, etc.) |
| `deal` | Deal / Order (dates, amounts, payment plan, etc.) |
| `agent` | Agent / Representative (name, RERA, branch, etc.) |
| `bank` | Bank / Financier (loan details, IFSC, etc.) |
| `witness` | Witnesses (names, addresses) |
| `system` | Auto-generated (today's date, year, document number) |

The schema is fully extensible — the backend exposes `/api/templates/entity-schema` so the frontend always reflects the current model.

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| AI returns malformed JSON | Raises `AIExtractionError` with raw response; document status set to `failed` with explicit message |
| AI response is empty | Raises `AIExtractionError` — never silently ignored |
| AI output fails validation | Validation errors appended as warnings; not silently discarded |
| Field is unmapped at generation | Replaced with `[MISSING: KEY]`; listed in `flagged_fields` |
| Field entity not in payload | Replaced with `[MISSING: KEY]`; listed in `flagged_fields` |
| PDF has no extractable text | `PDFExtractionError` raised; status set to `failed` |
| File too large | HTTP 413 returned immediately |
| Non-PDF uploaded | HTTP 400 returned immediately |

---

## Architecture

```
┌─────────────────────────────────────┐
│           Frontend (React)          │
│  Upload → Review → Map → Generate   │
│         nginx + SPA routing         │
└──────────────┬──────────────────────┘
               │ /api/* (proxied)
┌──────────────▼──────────────────────┐
│         Backend (FastAPI)           │
│                                     │
│  /api/documents   — upload + status │
│  /api/templates   — CRUD + confirm  │
│  /api/mappings    — field mappings  │
│  /api/generations — PDF generation  │
│                                     │
│  Services:                          │
│   pdf_extractor  (pdfplumber)       │
│   ai_extractor   (Claude API)       │
│   pdf_generator  (reportlab)        │
│                                     │
│  SQLite (SQLModel ORM)              │
└─────────────────────────────────────┘
```

---

## API Reference

Full interactive docs at `http://localhost:8000/docs`

### Key Endpoints

```
POST   /api/documents/upload              Upload a PDF
GET    /api/documents/{id}                Poll document status

GET    /api/templates/                    List all templates
GET    /api/templates/{id}               Get template + fields
PATCH  /api/templates/{id}              Edit template
POST   /api/templates/{id}/confirm       Confirm template
GET    /api/templates/entity-schema      Get entity schema

GET    /api/mappings/{template_id}        Get all field mappings
POST   /api/mappings/{template_id}        Upsert batch of mappings

POST   /api/generations/{template_id}     Generate a filled PDF
GET    /api/generations/download/{id}     Download generated PDF
```

---

## Development (without Docker)

```bash
# Backend
cd backend
pip install -r requirements.txt
mkdir -p data/uploads data/generated
GEMINI_API_KEY=your_key_here uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev   # proxies /api to localhost:8000
```

---

## Design Decisions

- **Gemini 2.5 Flash** as the LLM engine — chosen for its high speed, massive context window (ideal for long legal documents), and excellent native support for structured JSON schema outputs.
- **SQLite** for zero-setup persistence — swap `DATABASE_URL` for Postgres in production
- **Background tasks** for AI extraction — upload returns immediately; UI polls for status
- **Explicit error propagation** — every failure surface is named and stored, never swallowed
- **`{{SCREAMING_SNAKE_CASE}}`** placeholders — unambiguous, parseable with regex
- **Entity schema as a service** — frontend fetches schema from backend, keeping them in sync
- **ReportLab** for PDF generation — pure Python, no external binary dependencies