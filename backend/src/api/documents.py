import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, Header, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.schemas.document import (
    DocumentCreate,
    DocumentDetailResponse,
    DocumentResponse,
    DocumentsOverviewResponse,
)
from src.services import document_service

router = APIRouter(prefix="/documents", tags=["documents"])

UPLOADS_DIR = Path("uploads")


async def get_organization_id(x_organization_id: uuid.UUID = Header(...)) -> uuid.UUID:
    return x_organization_id


@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    file: UploadFile,
    organization_id: uuid.UUID = Depends(get_organization_id),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    UPLOADS_DIR.mkdir(exist_ok=True)

    unique_filename = f"{uuid.uuid4()}_{file.filename}"
    dest = UPLOADS_DIR / unique_filename

    async with aiofiles.open(dest, "wb") as out:
        while chunk := await file.read(1024 * 1024):  # 1 MB chunks
            await out.write(chunk)

    return await document_service.upload_document(db, organization_id, unique_filename, file_path=dest)


@router.post("", response_model=DocumentResponse, status_code=201)
async def create_document(
    data: DocumentCreate,
    organization_id: uuid.UUID = Depends(get_organization_id),
    db: AsyncSession = Depends(get_db),
):
    return await document_service.create_document(db, organization_id, data)


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    organization_id: uuid.UUID = Depends(get_organization_id),
    db: AsyncSession = Depends(get_db),
):
    return await document_service.list_documents(db, organization_id)


@router.get("/overview", response_model=DocumentsOverviewResponse)
async def documents_overview(
    organization_id: uuid.UUID = Depends(get_organization_id),
    db: AsyncSession = Depends(get_db),
):
    return await document_service.get_documents_overview(db, organization_id)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_organization_id),
    db: AsyncSession = Depends(get_db),
):
    document = await document_service.get_document(db, organization_id, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.get("/{document_id}/detail", response_model=DocumentDetailResponse)
async def get_document_detail(
    document_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_organization_id),
    db: AsyncSession = Depends(get_db),
):
    document = await document_service.get_document_detail(db, organization_id, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_organization_id),
    db: AsyncSession = Depends(get_db),
):
    deleted = await document_service.delete_document(db, organization_id, document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
