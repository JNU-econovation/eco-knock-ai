"""
ChromaDB에서 유효하지 않은 청크 삭제 스크립트.
- data/raw/ 경로처럼 더 이상 존재하지 않는 source의 청크 삭제
- ai_server/ 에서 실행: python cleanup_vectorstore.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.retriever import retriever

VALID_SOURCES = {
    f"data/{f.name}"
    for f in Path(__file__).parent.joinpath("data").iterdir()
    if f.suffix == ".md"
}

print(f"유효한 source 목록: {sorted(VALID_SOURCES)}\n")

result = retriever.collection.get(include=["metadatas"])
all_sources = {m["source"] for m in result["metadatas"]}
print(f"ChromaDB에 존재하는 source 목록: {sorted(all_sources)}\n")

stale_sources = all_sources - VALID_SOURCES
if not stale_sources:
    print("삭제할 청크 없음.")
    sys.exit(0)

for source in sorted(stale_sources):
    retriever.collection.delete(where={"source": source})
    print(f"삭제 완료: {source}")

print(f"\n총 {len(stale_sources)}개 source 삭제 완료.")
print(f"남은 청크 수: {retriever.collection.count()}")
