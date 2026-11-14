"""Gemini 클라이언트 테스트 대역. 실제 API를 호출하지 않는다."""

import numpy as np

try:
    from backend.gemini import EMBED_DIM, QueryIntent
except ImportError:
    from gemini import EMBED_DIM, QueryIntent


class FakeGeminiClient:
    def __init__(
        self,
        intent: QueryIntent | None = None,
        query_vector: np.ndarray | None = None,
        reasons: dict[int, str] | None = None,
        error: Exception | None = None,
    ):
        self.intent = intent
        self.query_vector = query_vector
        self.reasons = reasons
        self.error = error
        self.calls: list[tuple] = []

    def _record(self, *call):
        self.calls.append(call)
        if self.error is not None:
            raise self.error

    def extract_intent(self, query, mechanic_names, theme_names):
        self._record("extract_intent", query, mechanic_names, theme_names)
        return self.intent or QueryIntent(search_text=query)

    def embed_query(self, search_text):
        self._record("embed_query", search_text)
        if self.query_vector is not None:
            return self.query_vector
        vec = np.zeros(EMBED_DIM, dtype=np.float32)
        vec[0] = 1.0
        return vec

    def embed_documents(self, docs):
        self._record("embed_documents", docs)
        out = np.zeros((len(docs), EMBED_DIM), dtype=np.float32)
        out[:, 0] = 1.0
        return out

    def explain(self, mode, basis, basis_facts, games):
        self._record("explain", mode, basis, basis_facts, games)
        return self.reasons if self.reasons is not None else {}
