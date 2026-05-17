# keyring-ai-server

`keyring-ai-server`는 에코노베이션 동아리 앱의 AI 백엔드 서버입니다.

동아리 규정 문서를 기반으로 질문에 답하는 RAG(Retrieval-Augmented Generation) 챗봇 API를 제공합니다. 문서를 벡터 DB에 인덱싱하고, 사용자 질문에 대해 관련 문서를 검색한 뒤 Gemini LLM으로 답변을 생성합니다.

## 현재 구현 범위

- FastAPI 기반 비동기 REST API 서버
- 마크다운 문서 로딩 및 헤더 기준 청킹
- ChromaDB 로컬 영속화 벡터 인덱스 구축
- 하이브리드 검색 (벡터 유사도 + 키워드 보너스 점수)
- aliases.json 기반 키워드 보너스 점수 보정 (검색 결과 재점수화 시 약어 그룹 매칭)
- Gemini 2.5 Flash LLM 연결 (약어 풀어쓰기 포함 쿼리 재작성)
- RAG 파이프라인 (`needs_retrieval` → `rewrite_query` → `search` → `generate_answer`)
- `/chat`, `/retrieve`, `/documents/index` API 엔드포인트

## 아직 미완성인 부분

- 문서 추가
- 프론트엔드 연동
- 기타 등등

## 기술 스택

- Python 3.12
- FastAPI
- Gemini 2.5 Flash (`google-genai` SDK)
- ChromaDB
- sentence-transformers (`paraphrase-multilingual-MiniLM-L12-v2`)
- Pydantic

## 프로젝트 구조

```text
KEYRING/
├── .env                        # GOOGLE_API_KEY 보관 (깃 제외)
├── .gitignore
├── ai_server/
│   ├── main.py                 # FastAPI 앱 진입점, 라우터 등록
│   └── app/
│       ├── core/
│       │   └── aliases.json    # 약어 매핑
│       ├── models/
│       │   └── schemas.py      # Pydantic 요청/응답 스키마
│       ├── routes/
│       │   ├── chat.py         # /chat, /retrieve 엔드포인트
│       │   └── documents.py    # 문서 인덱싱 엔드포인트
│       └── services/
│           ├── chunker.py      # 마크다운 청킹 로직
│           ├── loader.py       # 파일 로딩
│           ├── llm.py          # Gemini 연결, RAG 함수들
│           └── retriever.py    # 하이브리드 검색
├── data/
│   ├── raw/                    # 원본 문서
│   └── processed/              # 전처리 결과
└── vectorstore/
    └── chroma/                 # ChromaDB 영속화 데이터
```

## 실행 전 요구사항

- Python 3.12
- Gemini API 키

기본 설정:

- HTTP 서버 포트: `8000`
- ChromaDB 경로: `vectorstore/chroma`
- 임베딩 모델: 최초 실행 시 자동 다운로드 (약 400MB)

## 환경 변수

루트 `.env` 파일 또는 시스템 환경 변수로 값을 주입할 수 있습니다.

필수:

- `GOOGLE_API_KEY`
  - Gemini API 인증 키입니다.
  - [Google AI Studio](https://aistudio.google.com)에서 발급받을 수 있습니다.

예시:

```dotenv
GOOGLE_API_KEY=your_gemini_api_key_here
```

## 실행 방법

의존성 설치:

```bash
pip install -r requirements.txt
```

서버 실행:

```bash
cd ai_server
uvicorn main:app --reload
```

API 문서: `http://localhost:8000/docs`

## RAG 파이프라인 흐름

```
사용자 질문
    ↓
needs_retrieval()  →  NO → 일반 답변 생성 (문서 검색 없음)
    ↓ YES
rewrite_query()    →  "AM이 뭐야?" → "AM Active Member 활동회원 회원 분류 정의"
    ↓
retriever.search() →  ChromaDB 벡터 검색 + aliases.json 키워드 보너스
    ↓
generate_answer()  →  참고 문서 포함 Gemini 답변 생성
    ↓
ChatResponse(answer, sources, used_retrieval)
```

## 문서 인덱싱

챗봇 사용 전 반드시 먼저 실행해야 합니다.
현재 인덱싱된 문서: `data/raw/econovation_rules.md` (동아리 회칙)

```http
POST /documents/index
Content-Type: application/json

{
  "file_path": "data/raw/econovation_rules.md"
}
```

```json
{
  "message": "indexed successfully",
  "chunks": 42
}
```

## 챗봇 질의응답

```http
POST /chat
Content-Type: application/json

{
  "question": "AM이 되려면 어떤 조건을 갖춰야 하나요?"
}
```

```json
{
  "answer": "AM(Active Member)이 되기 위해서는 ...",
  "sources": ["data/raw/econovation_rules.md"],
  "used_retrieval": true
}
```

`used_retrieval`이 `true`이면 문서 검색을 통해 답변을 생성한 것이고, `false`이면 일반 대화로 답변한 것입니다.

## 벡터 검색

LLM 호출 없이 검색 결과만 확인할 때 사용합니다.

```http
POST /retrieve
Content-Type: application/json

{
  "question": "AM 활동 조건",
  "top_k": 3
}
```

```json
{
  "question": "AM 활동 조건",
  "results": [
    {
      "chunk_id": 5,
      "title": "에코노베이션 동아리 회칙 > 제5조 회원의 분류 > 1. AM (Active Member)",
      "score": 0.87,
      "text": "AM은 ...",
      "source": "data/raw/econovation_rules.md"
    }
  ]
}
```

`top_k`의 기본값은 `3`입니다.

## 현재 상태 요약

이 저장소는 에코노베이션 동아리 앱의 AI 챗봇 백엔드를 구현한 것입니다. 문서 인덱싱, 하이브리드 검색, Gemini 기반 RAG 파이프라인, API 엔드포인트는 구현되어 있습니다. 실제 쿼리 정확도 검증 및 프론트엔드 연동은 아직 진행 중입니다.
