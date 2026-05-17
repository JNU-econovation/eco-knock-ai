import os
from functools import lru_cache
from google import genai
from dotenv import load_dotenv

load_dotenv()

_MODEL = "gemini-2.5-flash"


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


async def generate_answer(query: str, chunks: list[dict]) -> str:
    if chunks:
        context = "\n\n".join(f"[{c['title']}]\n{c['text']}" for c in chunks)
        prompt = (
            "당신은 동아리 운영 어시스턴트입니다.\n"
            "아래 참고 문서를 바탕으로 질문에 친절하고 정확하게 답하세요.\n"
            "문서에 없는 내용은 '문서에서 확인할 수 없습니다'라고 말하세요.\n\n"
            f"=== 참고 문서 ===\n{context}\n\n"
            f"질문: {query}"
        )
    else:
        prompt = f"당신은 동아리 운영 어시스턴트입니다. 친절하게 대화하세요.\n\n질문: {query}"

    response = await _get_client().aio.models.generate_content(
        model=_MODEL,
        contents=prompt,
    )
    return response.text.strip()
