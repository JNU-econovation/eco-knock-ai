from pydantic import BaseModel
from typing import List


class IndexRequest(BaseModel):
    file_path: str


class IndexResponse(BaseModel):
    message: str
    chunks: int


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


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str
    sources: List[str]
    used_retrieval: bool