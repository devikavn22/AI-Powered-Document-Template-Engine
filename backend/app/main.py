from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.database import init_db
from app.api import documents, templates, mappings, generations


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="AI Document Template Engine",
    description="Upload PDFs, extract templates via AI, map fields, generate filled documents.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(templates.router, prefix="/api/templates", tags=["templates"])
app.include_router(mappings.router, prefix="/api/mappings", tags=["mappings"])
app.include_router(generations.router, prefix="/api/generations", tags=["generations"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "doc-template-engine"}