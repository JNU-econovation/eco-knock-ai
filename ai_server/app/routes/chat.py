import os
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from app.models.schemas import RetrieveRequest, RetrieveResponse, ChatResponse
from app.services.retriever import retriever
from app.services.llm import needs_retrieval, rewrite_query, generate_answer

router = APIRouter(tags=["chat"])

RELEVANCE_THRESHOLD = 0.4

_ALLOWED_EXTENSIONS = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".pdf": "application/pdf",
}


@router.post("/retrieve", response_model=RetrieveResponse)
def retrieve(request: RetrieveRequest):
    if not retriever.is_ready():
        raise HTTPException(status_code=400, detail="document index is not ready")

    try:
        results = retriever.search(query=request.question, top_k=request.top_k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"question": request.question, "results": results}


@router.post("/chat", response_model=ChatResponse)
async def chat(
    question: str = Form(...),
    file: Optional[UploadFile] = File(None),
):
    file_data: Optional[tuple[bytes, str]] = None
    if file:
        ext = os.path.splitext(file.filename or "")[1].lower()
        mime_type = _ALLOWED_EXTENSIONS.get(ext)
        if not mime_type:
            raise HTTPException(
                status_code=400,
                detail="지원하지 않는 파일 형식입니다. 지원 형식: jpg, png, webp, gif, pdf",
            )
        file_data = (await file.read(), mime_type)

    use_retrieval = await needs_retrieval(question)

    if not use_retrieval:
        answer = await generate_answer(question, chunks=[], file_data=file_data)
        return {"answer": answer, "sources": [], "used_retrieval": False}

    if not retriever.is_ready():
        raise HTTPException(status_code=400, detail="document index is not ready")

    try:
        rewritten = await rewrite_query(question)
        chunks1 = retriever.search(query=rewritten, top_k=5)
        chunks2 = retriever.keyword_search(query=question, top_k=3)

        seen = set()
        merged = []
        for chunk in chunks1 + chunks2:
            uid = f"{chunk['source']}::{chunk['chunk_id']}"
            if uid not in seen:
                seen.add(uid)
                merged.append(chunk)

        merged.sort(key=lambda x: x["score"], reverse=True)
        relevant_chunks = [c for c in merged if c["score"] >= RELEVANCE_THRESHOLD]
        answer = await generate_answer(
            question,
            chunks=relevant_chunks,
            is_club_related=True,
            file_data=file_data,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    sources = list({c["source"] for c in relevant_chunks})
    return {"answer": answer, "sources": sources, "used_retrieval": True}
