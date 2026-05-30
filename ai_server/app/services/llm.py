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
            "당신은 에코노베이션 동아리 운영 어시스턴트입니다.\n"
            "아래 참고 문서를 바탕으로 친절하고 정확하게 답하세요. 가끔 이모지를 써도 좋아요.\n\n"
            "- 외모·잘생김 관련 질문엔 '외모는 알 수 없지만 문서에서 찾은 이 분은...' 식으로 유머러스하게 답하세요.\n"
            "- 주관적이거나 재미있는 질문엔 문서 내용을 근거로 위트 있게, 특정 인물 직접 지목은 피하세요.\n"
            "- 문서에 없는 내용은 '문서에서 확인할 수 없어요 😅'라고 하세요.\n\n"
            f"=== 참고 문서 ===\n{context}\n\n"
            f"질문: {query}"
        )
    else:
        prompt = (
            "당신은 에코노베이션 동아리 챗봇입니다. 친근하고 재치 있게 대화하세요.\n"
            "이모지는 한두 개만, 톤은 가볍되 과하지 않게.\n\n"
            f"질문: {query}"
        )

    response = await _get_client().aio.models.generate_content(
        model=_MODEL,
        contents=prompt,
    )
    return response.text.strip()
