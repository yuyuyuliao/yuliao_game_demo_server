from __future__ import annotations

from app.command.database import CHROMA_PATH
from app.knowledge_parser import KnowledgeParser

try:
    import chromadb
except Exception:  # pragma: no cover - fallback when chromadb is unavailable
    chromadb = None


class KnowledgeStore:
    """知识检索封装：优先使用 Chroma，失败时回退到关键词匹配。"""

    def __init__(self) -> None:
        """加载知识文档并尝试初始化向量检索集合。"""
        self._docs = KnowledgeParser().load_documents()
        self._collection = None
        if chromadb is not None:
            try:
                client = chromadb.PersistentClient(path=CHROMA_PATH)
                self._collection = client.get_or_create_collection("game_knowledge")
                if self._collection.count() == 0 and self._docs:
                    ids = list(self._docs.keys())
                    docs = [self._docs[i] for i in ids]
                    self._collection.add(ids=ids, documents=docs)
            except Exception:
                self._collection = None

    def search(self, query: str, n_results: int = 2) -> list[str]:
        """根据查询语句返回最相关的知识文本。"""
        if self._collection is not None:
            try:
                result = self._collection.query(query_texts=[query], n_results=n_results)
                documents = result.get("documents", [[]])
                return documents[0] if documents else []
            except Exception:
                pass

        keywords = set(query.lower().split())
        ranked = sorted(
            self._docs.values(),
            key=lambda doc: sum(1 for keyword in keywords if keyword and keyword in doc.lower()),
            reverse=True,
        )
        return ranked[:n_results]


knowledge_store = KnowledgeStore()
