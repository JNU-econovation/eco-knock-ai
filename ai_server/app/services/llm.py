import os
from functools import lru_cache
from pathlib import Path
from typing import Optional
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

_MODEL = "gemini-2.5-flash"
_PROMPTS_DIR = Path(__file__).parent.parent / "core" / "prompts"


@lru_cache(maxsize=None)
def _load_prompt(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _get_client() -> genai.Client:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set")
    return genai.Client(api_key=api_key)


async def needs_retrieval(query: str) -> bool:
    prompt = (
        "사용자의 질문이 동아리 문서 검색이 필요한지 판단해.\n"
        "동아리 규정, 회원 등급(AM/CM/RM), 활동, 구조, 운영 등에 관한 질문이면 YES.\n"
        "인사, 일반 대화, 단순 계산 등 문서와 무관한 질문이면 NO.\n"
        "반드시 YES 또는 NO만 답해.\n\n"
        f"질문: {query}"
    )
    response = await _get_client().aio.models.generate_content(
        model=_MODEL,
        contents=prompt,
    )
    return response.text.strip().upper().startswith("YES")


async def rewrite_query(query: str) -> str:
    prompt = (
        "동아리 문서 벡터 검색에 최적화된 쿼리로 재작성해.\n"
        "약어(AM, CM, RM, DEV, TF 등)는 풀어쓰고, 핵심 키워드를 포함시켜.\n"
        "재작성된 쿼리 한 줄만 출력해. 설명 없이.\n\n"
        f"질문: {query}"
    )
    response = await _get_client().aio.models.generate_content(
        model=_MODEL,
        contents=prompt,
    )
    return response.text.strip()


async def generate_answer(
    query: str,
    chunks: list[dict],
    file_data: Optional[tuple[bytes, str]] = None,
) -> str:
    if chunks:
        context = "\n\n".join(f"[{c['title']}]\n{c['text']}" for c in chunks)
        prompt = _load_prompt("with_context.md").format(context=context, query=query)
    else:
        prompt = _load_prompt("no_context.md").format(query=query)

    if file_data:
        file_bytes, mime_type = file_data
        contents = [
            types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
            types.Part.from_text(text=prompt),
        ]
    else:
        contents = prompt

    response = await _get_client().aio.models.generate_content(
        model=_MODEL,
        contents=contents,
    )
    return response.text.strip()
