from fastapi import APIRouter, HTTPException
from app.models.schemas import IndexRequest, IndexResponse
from app.services.loader import load_document
from app.services.chunker import chunk_markdown_text
from app.services.retriever import retriever

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/index", response_model=IndexResponse)
def index_document(request: IndexRequest):
    try:
        text = load_document(request.file_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"failed to load document: {str(e)}")

    chunks = chunk_markdown_text(text=text, source=request.file_path)

    if not chunks:
        raise HTTPException(status_code=400, detail="no valid chunks created from document")

    try:
        chunk_count = retriever.build_index(chunks, source=request.file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"failed to build vector index: {str(e)}")

    return {
        "message": "indexed successfully",
        "chunks": chunk_count,
    }