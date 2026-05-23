from fastapi import APIRouter
from app.models.schemas import IndexAllRequest, IndexAllResponse, IndexAllResult
from app.services.loader import load_document
from app.services.chunker import chunk_markdown_text
from app.services.retriever import retriever

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/index-all", response_model=IndexAllResponse)
def index_all_documents(request: IndexAllRequest):
    results = []
    total_chunks = 0

    for file_path in request.file_paths:
        try:
            text = load_document(file_path)
            chunks = chunk_markdown_text(text=text, source=file_path)
            chunk_count = retriever.build_index(chunks, source=file_path)
            results.append(IndexAllResult(file_path=file_path, chunks=chunk_count))
            total_chunks += chunk_count
        except Exception as e:
            results.append(IndexAllResult(file_path=file_path, chunks=0, error=str(e)))

    return IndexAllResponse(
        total_files=len(request.file_paths),
        total_chunks=total_chunks,
        results=results,
    )