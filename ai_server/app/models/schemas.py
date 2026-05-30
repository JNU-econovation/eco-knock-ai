from pydantic import BaseModel
from typing import List


class IndexAllRequest(BaseModel):
    file_paths: list[str]


class IndexAllResult(BaseModel):
    file_path: str
    chunks: int
    error: str | None = None


class IndexAllResponse(BaseModel):
    total_files: int
    total_chunks: int
    results: list[IndexAllResult]


class RetrieveRequest(BaseModel):
    question: str
    top_k: int = 3


class RetrieveResult(BaseModel):
    chunk_id: int
    title: str
    score: float
    text: str
    source: str


class RetrieveResponse(BaseModel):
    question: str
    results: List[RetrieveResult]


class ChatResponse(BaseModel):
    answer: str
    sources: List[str]
    used_retrieval: bool
