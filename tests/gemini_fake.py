"""Gemini 클라이언트 테스트 대역. 실제 API를 호출하지 않는다."""

import numpy as np

try:
    from backend.gemini import EMBED_DIM, GameProfile, QueryIntent, RerankResult, WebAnswer
except ImportError:
    from gemini import EMBED_DIM, GameProfile, QueryIntent, RerankResult, WebAnswer


class FakeGeminiClient:
    def __init__(
        self,
        intent: QueryIntent | None = None,
        query_vector: np.ndarray | None = None,
        reasons: dict[int, str] | None = None,
        error: Exception | None = None,
        extra_profiles: list[GameProfile] | None = None,
        rerank_result: RerankResult | None = None,
        rerank_error: Exception | None = None,
        web_answer: WebAnswer | None = None,
        web_error: Exception | None = None,
    ):
        self.web_answer = web_answer
        self.web_error = web_error
        self.rerank_result = rerank_result
        self.rerank_error = rerank_error
        self.extra_profiles = extra_profiles or []
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

    def embed_queries(self, texts):
        self._record("embed_queries", tuple(texts))
        if self.query_vector is not None:
            return np.tile(self.query_vector, (len(texts), 1))
        out = np.zeros((len(texts), EMBED_DIM), dtype=np.float32)
        out[:, 0] = 1.0
        return out

    def embed_documents(self, docs):
        self._record("embed_documents", docs)
        out = np.zeros((len(docs), EMBED_DIM), dtype=np.float32)
        out[:, 0] = 1.0
        return out

    def explain(self, mode, basis, basis_facts, games, weak_match=False):
        self._record("explain", mode, basis, basis_facts, games, weak_match)
        return self.reasons if self.reasons is not None else {}

    def write_profiles(self, games):
        self._record("write_profiles", list(games))
        out = [
            GameProfile(
                bgg_id=int(g["bgg_id"]),
                profile=" ".join(["calm"] * 60),
                franchise=("Fake Franchise",),
                base_game=None,
                designers=("Fake Designer",),
                designer_countries=("Germany",),
            )
            for g in games
        ]
        return out + list(self.extra_profiles)

    def rerank(self, query, games, players=None, max_time=None):
        self._record("rerank", query, games, players, max_time)
        if self.rerank_error is not None:
            raise self.rerank_error
        if self.rerank_result is not None:
            return self.rerank_result
        return RerankResult("Read as: fake.", tuple(int(g["bgg_id"]) for g in games), False)

    def web_search(self, query):
        self._record("web_search", query)
        if self.web_error is not None:
            raise self.web_error
        if self.web_answer is not None:
            return self.web_answer
        return WebAnswer("Catan\n\nFake summary.", "<div>fake suggestions</div>", 1)
