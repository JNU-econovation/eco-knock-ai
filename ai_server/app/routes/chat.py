from fastapi import APIRouter, HTTPException
from app.models.schemas import (
    RetrieveRequest,
    RetrieveResponse,
    ChatRequest,
    ChatResponse,
)
from app.services.retriever import retriever
from app.services.llm import needs_retrieval, rewrite_query, generate_answer

router = APIRouter(tags=["chat"])


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
async def chat(request: ChatRequest):
    use_retrieval = await needs_retrieval(request.question)

    if not use_retrieval:
        answer = await generate_answer(request.question, chunks=[])
        return {"answer": answer, "sources": [], "used_retrieval": False}

    if not retriever.is_ready():
        raise HTTPException(status_code=400, detail="document index is not ready")

    try:
        rewritten = await rewrite_query(request.question)
        chunks = retriever.search(query=rewritten, top_k=3)
        answer = await generate_answer(request.question, chunks)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    sources = list({c["source"] for c in chunks})
    return {"answer": answer, "sources": sources, "used_retrieval": True}
