from pathlib import Path
from typing import List, Dict
import json
import re
import chromadb
from sentence_transformers import SentenceTransformer


class HybridRetriever:
    def __init__(
        self,
        persist_path: str = "vectorstore/chroma",
        collection_name: str = "club_docs",
        model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    ):
        Path(persist_path).mkdir(parents=True, exist_ok=True)
        self.persist_path = persist_path
        self.collection_name = collection_name
        self.model = SentenceTransformer(model_name)
        self.client = chromadb.PersistentClient(path=persist_path)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self.aliases = self._load_aliases()

    def _load_aliases(self) -> Dict[str, List[str]]:
        aliases_path = Path(__file__).resolve().parents[1] / "core" / "aliases.json"

        if not aliases_path.exists():
            return {}

        data = json.loads(aliases_path.read_text(encoding="utf-8"))
        normalized = {}

        for canonical, variants in data.items():
            values = [canonical] + variants
            deduped = []
            seen = set()

            for value in values:
                v = value.strip()
                if not v:
                    continue
                key = v.lower()
                if key not in seen:
                    seen.add(key)
                    deduped.append(v)

            normalized[canonical] = deduped

        return normalized

    def _normalize(self, text: str) -> str:
        return text.lower().strip()

    def _matched_alias_groups(self, query: str) -> Dict[str, List[str]]:
        query_lower = self._normalize(query)
        matched = {}

        for canonical, variants in self.aliases.items():
            if any(self._normalize(term) in query_lower for term in variants):
                matched[canonical] = variants

        return matched

    _JOSA_SUFFIXES = [
        "에서", "에게", "한테", "으로서", "로서", "으로", "이랑", "하고",
        "부터", "까지", "에", "은", "는", "이", "가", "을", "를", "의",
        "도", "로", "와", "과", "야", "아", "랑", "만",
    ]

    def _strip_josa(self, token: str) -> str:
        while True:
            stripped = token
            for josa in self._JOSA_SUFFIXES:
                if token.endswith(josa) and len(token) > len(josa):
                    token = token[: -len(josa)]
                    break
            if token == stripped:
                return token

    def _extract_keywords(self, query: str) -> List[str]:
        tokens = re.findall(r"[A-Za-z]+|[0-9]+|[가-힣]+", query)

        stopwords = {
            "뭐", "뭐야", "무엇", "설명", "알려줘", "알려", "해줘", "해",
            "이", "가", "은", "는", "을", "를", "어떻게", "인가요", "인가",
            "좀", "대한", "대해", "관련", "뜻", "의미"
        }

        keywords = []
        seen = set()

        for token in tokens:
            stripped = self._strip_josa(token)
            lower = stripped.lower()
            if lower in stopwords:
                continue
            if len(lower) == 1 and not lower.isupper():
                continue
            if lower not in seen:
                seen.add(lower)
                keywords.append(stripped)

        return keywords

    def _keyword_bonus(self, query: str, title: str, text: str) -> float:
        title_lower = self._normalize(title)
        text_lower = self._normalize(text)
        bonus = 0.0

        matched_groups = self._matched_alias_groups(query)
        for terms in matched_groups.values():
            if any(self._normalize(term) in title_lower for term in terms):
                bonus += 0.35
            elif any(self._normalize(term) in text_lower for term in terms):
                bonus += 0.20

        keywords = self._extract_keywords(query)
        for keyword in keywords:
            key = self._normalize(keyword)
            if key in title_lower:
                bonus += 0.12
            elif key in text_lower:
                bonus += 0.06

        return min(bonus, 0.8)

    def is_ready(self) -> bool:
        return self.collection.count() > 0

    def build_index(self, chunks: List[Dict], source: str) -> int:
        if not chunks:
            raise ValueError("no chunks to index")

        try:
            self.collection.delete(where={"source": source})
        except Exception:
            pass

        ids = [f"{source}::{chunk['chunk_id']}" for chunk in chunks]
        documents = [chunk["text"] for chunk in chunks]
        metadatas = [
            {
                "chunk_id": int(chunk["chunk_id"]),
                "title": str(chunk["title"]),
                "source": str(chunk["source"]),
            }
            for chunk in chunks
        ]
        embedding_inputs = [
            f'{chunk["title"]}\n{chunk["text"]}'.strip()
            for chunk in chunks
        ]

        embeddings = self.model.encode(
            embedding_inputs,
            convert_to_numpy=True,
            normalize_embeddings=True,
        ).tolist()

        self.collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )

        return len(chunks)

    def search(self, query: str, top_k: int = 3) -> List[Dict]:
        if not self.is_ready():
            raise ValueError("index is not built")

        query_embedding = self.model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
        ).tolist()

        candidate_k = min(max(top_k * 5, 10), self.collection.count())

        result = self.collection.query(
            query_embeddings=query_embedding,
            n_results=candidate_k,
            include=["documents", "metadatas", "distances"],
        )

        documents = result["documents"][0]
        metadatas = result["metadatas"][0]
        distances = result["distances"][0]

        rescored = []

        for document, metadata, distance in zip(documents, metadatas, distances):
            vector_score = max(0.0, 1 - float(distance))
            keyword_score = self._keyword_bonus(query, metadata["title"], document)
            final_score = round(vector_score + keyword_score, 6)

            rescored.append(
                {
                    "chunk_id": int(metadata["chunk_id"]),
                    "title": metadata["title"],
                    "score": final_score,
                    "text": document,
                    "source": metadata["source"],
                }
            )

        rescored.sort(key=lambda x: x["score"], reverse=True)

        return rescored[:top_k]

    def keyword_search(self, query: str, top_k: int = 5) -> List[Dict]:
        keywords = self._extract_keywords(query)
        if not keywords:
            return []

        all_data = self.collection.get(include=["documents", "metadatas"])

        results = []
        seen = set()

        for keyword in keywords:
            if len(keyword) < 2:
                continue
            keyword_lower = keyword.lower()

            for doc, meta in zip(all_data["documents"], all_data["metadatas"]):
                if keyword_lower not in doc.lower() and keyword_lower not in meta["title"].lower():
                    continue

                uid = f"{meta['source']}::{meta['chunk_id']}"
                if uid in seen:
                    continue
                seen.add(uid)

                results.append({
                    "chunk_id": int(meta["chunk_id"]),
                    "title": meta["title"],
                    "score": 0.8,
                    "text": doc,
                    "source": meta["source"],
                })

        return results[:top_k]


retriever = HybridRetriever()