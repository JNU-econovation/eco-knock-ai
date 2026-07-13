# keyring-ai-server

`keyring-ai-server`는 에코노베이션 동아리 앱의 AI 백엔드 서버입니다.

동아리 규정 문서를 기반으로 질문에 답하는 RAG(Retrieval-Augmented Generation) 챗봇 API를 제공합니다. 문서를 벡터 DB에 인덱싱하고, 사용자 질문에 대해 관련 문서를 검색한 뒤 Gemini LLM으로 답변을 생성합니다.

## 현재 구현 범위

- FastAPI 기반 비동기 REST API 서버
- CORS 미들웨어 (`ALLOWED_ORIGINS` 환경변수로 허용 도메인 제어)
- 마크다운 문서 로딩 및 헤더 기준 청킹 (h1/h2/h3 계층 정확히 추적)
- ChromaDB 로컬 영속화 벡터 인덱스 구축
- 하이브리드 검색: 벡터 검색 + Python 직접 키워드 검색 결합 (중복 제거 후 score 정렬)
- 한국어 조사 제거(`_strip_josa`) 기반 키워드 추출 — 복합 조사("에는", "에서는" 등) 반복 처리
- aliases.json 기반 약어 보너스 점수 보정
- Gemini 3.1 Flash Lite LLM 연결 (약어 풀어쓰기 포함 쿼리 재작성)
- temperature 분리: needs_retrieval/rewrite_query=0.0, with_context=0.4, no_context=0.9
- 503 에러 자동 재시도 (최대 3회, 1초 간격)
- RAG 파이프라인 (`needs_retrieval` → `rewrite_query` → 하이브리드 검색 → `generate_answer`)
- 검색 결과 relevance threshold(0.4) 필터링 — 관련 문서 없을 때 `unknown_context` 분기
- 프롬프트 외부 파일 관리 (`core/prompts/with_context.md`, `no_context.md`, `unknown_context.md`)
- `/chat` 이미지·PDF 파일 첨부 지원 (jpg, png, webp, gif, pdf)
- `/chat`, `/retrieve`, `/documents/index-all`, `/health`, `/api-spec` API 엔드포인트
- 에코노베이션 블로그 크롤러 (`blog_crawler.py`) — 카테고리별 마크다운 저장
- 노션 API 기반 문서 크롤러 (`notion_crawler.py`) — 페이지별 마크다운 저장, weekly/monthly 그룹 관리
- GitHub Actions 자동 크롤링 (블로그: 매일 변경 감지 시, 노션: 매주/매월) — 결과 자동 커밋 및 배포 서버 재인덱싱
- vectorstore 정리 스크립트 (`cleanup_vectorstore.py`) — 유효하지 않은 source 청크 삭제

## 아직 미완성인 부분

- 재인덱싱 후 실제 쿼리 테스트 및 정확도 검증
- 프론트엔드 연동
- 기타 등등

## 기술 스택

- Python 3.12
- FastAPI
- Gemini 3.1 Flash Lite (`google-genai` SDK)
- ChromaDB
- sentence-transformers (`paraphrase-multilingual-MiniLM-L12-v2`)
- Pydantic
- requests + BeautifulSoup4 (블로그 크롤러)
- requests (노션 크롤러, Notion API 직접 호출)

## 프로젝트 구조

```text
KEYRING/
├── .env                        # GOOGLE_API_KEY, NOTION_TOKEN 보관 (깃 제외)
├── .gitignore
├── .github/
│   ├── last_blog_commit        # 블로그 원본 레포 최근 커밋 해시 (변경 감지용)
│   └── workflows/
│       ├── crawl-blog.yml              # 블로그 크롤링 (매일, 원본 레포 변경 시에만 실행)
│       ├── crawl-notion-weekly.yml     # 노션 크롤링 (매주 월요일)
│       └── crawl-notion-monthly.yml    # 노션 크롤링 (매월 1일)
├── ai_server/
│   ├── data/                   # 원본 문서
│   │   ├── econovation_rules.md
│   │   ├── activities.md
│   │   ├── club_intro.md
│   │   ├── members.md          # 회원 정보
│   │   ├── book_list.md        # 동아리방 도서 목록
│   │   ├── project_guide.md    # 프로젝트 진행 가이드
│   │   ├── blog_dev.md         # 크롤링 결과 (SUMMER/WINTER_DEV)
│   │   ├── blog_news.md        # 크롤링 결과 (ECONO_NEWS)
│   │   ├── blog_etc.md         # 크롤링 결과 (기타)
│   │   └── notion_*.md         # 노션 크롤링 결과 (페이지별 1파일)
│   ├── requirements.txt
│   └── app/
│       ├── main.py             # FastAPI 앱 진입점, CORS, 라우터 등록, /health, /api-spec
│       ├── static/
│       │   └── api-docs.html   # /api-spec 에서 서빙하는 API 문서 페이지
│       ├── core/
│       │   ├── aliases.json    # 약어 매핑
│       │   └── prompts/
│       │       ├── with_context.md     # 문서 검색 결과 포함 프롬프트
│       │       ├── no_context.md       # 일반 대화 프롬프트
│       │       └── unknown_context.md  # 동아리 관련이나 문서 없을 때 프롬프트
│       ├── models/
│       │   └── schemas.py      # Pydantic 요청/응답 스키마
│       ├── routes/
│       │   ├── chat.py         # /chat, /retrieve 엔드포인트
│       │   └── documents.py    # /documents/index-all 엔드포인트
│       └── services/
│           ├── chunker.py        # 마크다운 청킹 로직
│           ├── blog_crawler.py   # 에코노베이션 블로그 크롤러
│           ├── notion_crawler.py # 노션 API 기반 문서 크롤러
│           ├── loader.py         # 파일 로딩
│           ├── llm.py            # Gemini 연결, RAG 함수들
│           └── retriever.py      # 하이브리드 검색
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

선택:

- `ALLOWED_ORIGINS`
  - CORS 허용 도메인입니다. 기본값은 `*`(전체 허용)입니다.
  - 여러 도메인은 쉼표로 구분합니다. 예: `https://app.example.com,https://admin.example.com`
- `NOTION_TOKEN`
  - `notion_crawler.py` 실행 시에만 필요합니다.
  - 노션 인테그레이션 토큰이며, 크롤링 대상 페이지에 해당 인테그레이션이 연결되어 있어야 합니다.

예시:

```dotenv
GOOGLE_API_KEY=your_gemini_api_key_here
ALLOWED_ORIGINS=https://app.example.com
NOTION_TOKEN=your_notion_integration_token_here
```

## 실행 방법

의존성 설치:

```bash
pip install -r requirements.txt
```

서버 실행:

```bash
cd ai_server
uvicorn app.main:app --reload
```

API 문서: `http://localhost:8000/docs`

## RAG 파이프라인 흐름

```
사용자 질문
    ↓
needs_retrieval()  →  NO → no_context 답변 (temperature=0.9)
    ↓ YES
rewrite_query()    →  "AM이 뭐야?" → "AM Active Member 활동회원 회원 분류 정의"
    ↓
retriever.search()       →  벡터 검색 (rewritten query, top_k=5)
retriever.keyword_search() →  키워드 직접 검색 (원본 question, top_k=3)
    ↓ 중복 제거 후 score 정렬
relevant_chunks (score >= 0.4 필터링)
    ↓
relevant_chunks 있음 → with_context 답변 (temperature=0.4)
relevant_chunks 없음 → unknown_context 답변 (temperature=0.4)
    ↓
ChatResponse(answer, sources, used_retrieval)
```

## 문서 인덱싱

챗봇 사용 전 반드시 먼저 실행해야 합니다.

> **블로그 데이터 안내**: `data/blog_*.md` 파일은 GitHub Actions(`crawl-blog.yml`)가 매일 자동 생성해 git에 커밋합니다. 로컬에서 직접 최신화하려면 크롤러를 실행하세요.
>
> ```bash
> cd ai_server
> python app/services/blog_crawler.py
> ```

> **노션 데이터 안내**: `data/notion_*.md` 파일도 GitHub Actions(`crawl-notion-weekly.yml`, `crawl-notion-monthly.yml`)가 자동 생성해 git에 커밋합니다. 로컬에서 직접 실행하려면 `notion_crawler.py`를 사용하며, `NOTION_TOKEN` 환경변수가 필요합니다.
>
> ```bash
> cd ai_server
> python app/services/notion_crawler.py            # 전체 페이지
> python app/services/notion_crawler.py --group weekly   # 멘토링, Econovation
> python app/services/notion_crawler.py --group monthly  # Contributors, 동아리방 대청소, 알림아리, 여름 야유회
> ```
>
> GitHub Actions가 각각 매일(블로그, 변경 시에만)/매주 월요일/매월 1일 자동 실행하고 결과를 커밋한 뒤 배포 서버를 재인덱싱합니다.

```http
POST /documents/index-all
Content-Type: application/json

{
  "file_paths": [
    "data/econovation_rules.md",
    "data/activities.md",
    "data/club_intro.md",
    "data/members.md",
    "data/book_list.md",
    "data/project_guide.md",
    "data/blog_dev.md",
    "data/blog_news.md",
    "data/blog_etc.md",
    "data/notion_멘토링.md",
    "data/notion_econovation.md",
    "data/notion_contributors.md",
    "data/notion_동아리방_대청소.md",
    "data/notion_알림아리.md",
    "data/notion_여름_야유회.md"
  ]
}
```

```json
{
  "total_files": 4,
  "total_chunks": 120,
  "results": [
    { "file_path": "data/econovation_rules.md", "chunks": 42, "error": null },
    { "file_path": "data/blog_dev.md", "chunks": 37, "error": null }
  ]
}
```

## 챗봇 질의응답

`/chat`은 `multipart/form-data` 형식으로 요청합니다. `question` 필드는 필수이며, `file` 필드로 이미지나 PDF를 선택적으로 첨부할 수 있습니다.

지원 파일 형식: `jpg`, `jpeg`, `png`, `webp`, `gif`, `pdf`

```http
POST /chat
Content-Type: multipart/form-data

question=AM이 되려면 어떤 조건을 갖춰야 하나요?
file=(선택) 이미지 또는 PDF 파일
```

```json
{
  "answer": "AM(Active Member)이 되기 위해서는 ...",
  "sources": ["data/econovation_rules.md"],
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
      "source": "data/econovation_rules.md"
    }
  ]
}
```

`top_k`의 기본값은 `3`입니다.

## 상태 확인 및 API 문서 페이지

```http
GET /health
```

```json
{ "status": "ok" }
```

```http
GET /api-spec
```

`static/api-docs.html`을 HTML로 렌더링해 반환합니다. API 엔드포인트를 브라우저에서 확인할 때 사용합니다.

배포 서버 API 문서: https://eco-knock-ai.isek-ai.org/api-spec

## 현재 상태 요약

이 저장소는 에코노베이션 동아리 앱의 AI 챗봇 백엔드를 구현한 것입니다. 문서 인덱싱, 하이브리드 검색, Gemini 기반 RAG 파이프라인, API 엔드포인트는 구현되어 있습니다. 나머지 부분은 아직 진행 중입니다.
