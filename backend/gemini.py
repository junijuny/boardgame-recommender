"""Gemini 호출의 단일 창구: 의도 추출, 임베딩, 추천 이유 생성.

Smoke check (real key, gemini-3.5-flash-lite): the per-field enum schema was
REJECTED with 400 INVALID_ARGUMENT (an enum of 50 names was accepted, 100 was
not; our vocab is 157 mechanics + 217 themes). Path taken: the FALLBACK. Tag
fields are plain string arrays, the allowed names are listed in the prompt, and
the caller (Task 4) must sanitize returned names against the vocab.
Thinking: ThinkingLevel.MINIMAL is accepted; thinking_budget=0 is rejected.
"""

import json
import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

import numpy as np

try:
    from backend import limits
except ImportError:
    import limits

EXTRACT_MODEL = "gemini-3.5-flash-lite"
EXPLAIN_MODEL = "gemini-3.5-flash-lite"
EMBED_MODEL = "gemini-embedding-2"
EMBED_DIM = 768
TIMEOUT_SECONDS = 10


class GeminiError(Exception):
    """Gemini 호출 실패 (SDK 예외, 응답 파싱 실패 등)."""


class BudgetExceeded(GeminiError):
    """일일 호출 예산 소진."""


@dataclass(frozen=True)
class QueryIntent:
    search_text: str
    include_mechanics: tuple[str, ...] = ()
    exclude_mechanics: tuple[str, ...] = ()
    include_themes: tuple[str, ...] = ()
    exclude_themes: tuple[str, ...] = ()
    weight_min: float | None = None
    weight_max: float | None = None


def query_text(search_text: str) -> str:
    return f"task: search result | query: {search_text}"


def document_text(title: str, body: str) -> str:
    return f"title: {title or 'none'} | text: {body}"


class GeminiClient(Protocol):
    def extract_intent(
        self, query: str, mechanic_names: Sequence[str], theme_names: Sequence[str]
    ) -> QueryIntent: ...

    def embed_query(self, search_text: str) -> np.ndarray: ...

    def embed_documents(self, docs: Sequence[tuple[str, str]]) -> np.ndarray: ...

    def explain(
        self,
        mode: Literal["similar", "query"],
        basis: str,
        basis_facts: dict | None,
        games: Sequence[dict],
    ) -> dict[int, str]: ...


EXTRACT_PROMPT = """\
You convert a board-game search request (any language, often Korean) into structured filters.
Rules:
- search_text: English text describing the play experience the user wants. Translate Korean to English.
- Ignore player counts and play time; the UI supplies them.
- Weight is BGG complexity on a 1-5 scale. Map "light/easy" (e.g. 가벼운) to a low range such as 1.0-2.5,
  and "heavy/complex" to a high range such as 3.5-5.0. Leave weight_min/weight_max null if not implied.
- include_*/exclude_*: only tags clearly implied by the request. "No dice" means exclude Dice Rolling.
  Use only names from the allowed lists.
Allowed mechanics: {mechanics}
Allowed themes: {themes}
Request: {query}
"""

EXPLAIN_PROMPT = """\
You write short reasons why recommended board games fit.
Always write in English, even when the basis is in another language (translate its meaning).
Write exactly one English sentence (at most 25 words) per game, using only the facts given.
Never mention facts that are not in the input.
{mode_rule}
Return one entry per game, keyed by its bgg_id.
Basis: {basis}
Basis facts: {basis_facts}
Games: {games}
"""

MODE_RULES = {
    "similar": "For each game, say what it shares with the basis game.",
    "query": "For each game, say which part of the user's request it fits.",
}


def _normalize_rows(arr: np.ndarray) -> np.ndarray:
    arr = np.asarray(arr, dtype=np.float32)
    norms = np.linalg.norm(arr, axis=-1, keepdims=True)
    return (arr / np.where(norms > 0, norms, 1.0)).astype(np.float32)


def _tag_array() -> dict:
    # 어휘가 enum 크기 한도(약 50~100개)를 넘어 일반 문자열 배열 사용. 검증은 호출 측에서 한다.
    return {"type": "ARRAY", "items": {"type": "STRING"}}


def _opt_float(value) -> float | None:
    return None if value is None else float(value)


def _tags(value) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(v) for v in value if v is not None)


def _intent_from_dict(data: dict) -> QueryIntent:
    try:
        search_text = data.get("search_text")
        return QueryIntent(
            search_text="" if search_text is None else str(search_text),
            include_mechanics=_tags(data.get("include_mechanics")),
            exclude_mechanics=_tags(data.get("exclude_mechanics")),
            include_themes=_tags(data.get("include_themes")),
            exclude_themes=_tags(data.get("exclude_themes")),
            weight_min=_opt_float(data.get("weight_min")),
            weight_max=_opt_float(data.get("weight_max")),
        )
    except (TypeError, ValueError, AttributeError) as exc:
        raise GeminiError(f"Unexpected intent response: {exc}") from exc


class GoogleGeminiClient:
    def __init__(self, api_key: str):
        from google import genai

        self._types = genai.types
        self._client = genai.Client(api_key=api_key)

    def _http_options(self):
        # HttpOptions.timeout 단위는 밀리초
        return self._types.HttpOptions(timeout=TIMEOUT_SECONDS * 1000)

    def _generate(self, model: str, prompt: str, schema: dict) -> dict:
        t = self._types
        try:
            resp = self._client.models.generate_content(
                model=model,
                contents=prompt,
                config=t.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    thinking_config=t.ThinkingConfig(thinking_level=t.ThinkingLevel.MINIMAL),
                    http_options=self._http_options(),
                ),
            )
            return json.loads(resp.text)
        except Exception as exc:
            raise GeminiError(f"Gemini request failed: {exc}") from exc

    def extract_intent(self, query, mechanic_names, theme_names) -> QueryIntent:
        schema = {
            "type": "OBJECT",
            "properties": {
                "search_text": {"type": "STRING"},
                "include_mechanics": _tag_array(),
                "exclude_mechanics": _tag_array(),
                "include_themes": _tag_array(),
                "exclude_themes": _tag_array(),
                "weight_min": {"type": "NUMBER", "nullable": True},
                "weight_max": {"type": "NUMBER", "nullable": True},
            },
            "required": ["search_text"],
        }
        data = self._generate(EXTRACT_MODEL, EXTRACT_PROMPT.format(
                query=query,
                mechanics=json.dumps(list(mechanic_names), ensure_ascii=False),
                themes=json.dumps(list(theme_names), ensure_ascii=False),
            ), schema)
        return _intent_from_dict(data)

    def _embed(self, texts: list[str]) -> np.ndarray:
        t = self._types
        try:
            resp = self._client.models.embed_content(
                model=EMBED_MODEL,
                # 문서마다 별도 Content: 문자열 리스트를 그대로 넣으면 하나로 합쳐진 벡터가 나온다
                contents=[t.Content(parts=[t.Part(text=text)]) for text in texts],
                config=t.EmbedContentConfig(
                    output_dimensionality=EMBED_DIM, http_options=self._http_options()
                ),
            )
            arr = np.array([e.values for e in resp.embeddings], dtype=np.float32)
        except Exception as exc:
            raise GeminiError(f"Gemini embedding failed: {exc}") from exc
        if arr.shape != (len(texts), EMBED_DIM):
            raise GeminiError(f"Unexpected embedding shape {arr.shape}")
        return _normalize_rows(arr)

    def embed_query(self, search_text: str) -> np.ndarray:
        return self._embed([query_text(search_text)])[0]

    def embed_documents(self, docs) -> np.ndarray:
        if not docs:
            return np.zeros((0, EMBED_DIM), dtype=np.float32)
        return self._embed([document_text(title, body) for title, body in docs])

    def explain(self, mode, basis, basis_facts, games) -> dict[int, str]:
        schema = {
            "type": "OBJECT",
            "properties": {
                "reasons": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "bgg_id": {"type": "INTEGER"},
                            "reason": {"type": "STRING"},
                        },
                        "required": ["bgg_id", "reason"],
                    },
                }
            },
            "required": ["reasons"],
        }
        prompt = EXPLAIN_PROMPT.format(
            mode_rule=MODE_RULES[mode],
            basis=basis,
            basis_facts=json.dumps(basis_facts, ensure_ascii=False),
            games=json.dumps(list(games), ensure_ascii=False),
        )
        data = self._generate(EXPLAIN_MODEL, prompt, schema)
        try:
            return {int(r["bgg_id"]): str(r["reason"]) for r in data["reasons"]}
        except (KeyError, TypeError, ValueError) as exc:
            raise GeminiError(f"Unexpected explanation response: {exc}") from exc


_UNSET = object()
_client = _UNSET

budget = limits.DailyBudget(int(os.environ.get("GEMINI_DAILY_CALL_LIMIT", "2000")))


def get_client() -> GeminiClient | None:
    global _client
    if _client is _UNSET:
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        _client = GoogleGeminiClient(key) if key else None
    return _client


def set_client(client: GeminiClient | None) -> None:
    global _client
    _client = client


def charge(n: int = 1) -> None:
    if not budget.try_spend(n):
        raise BudgetExceeded("Daily Gemini call budget exhausted")


def _smoke() -> None:
    try:
        from backend import recommend_engine as eng  # 데이터 로딩 재사용
    except ImportError:
        import recommend_engine as eng

    mech = [str(n) for n in eng.mechanics.names]
    themes = [str(n) for n in eng.themes.names]
    client = get_client()
    if client is None:
        raise SystemExit("GEMINI_API_KEY is not set")
    print(f"vocab: {len(mech)} mechanics, {len(themes)} themes")
    for q in (
        "4명이서 1시간 안에 끝나는, 주사위 없는 가벼운 협력 게임",
        "a tense game where players secretly betray each other",
    ):
        print(q, "->", client.extract_intent(q, mech, themes))
    vec = client.embed_query("cooperative")
    print("embed_query:", vec.shape, vec.dtype, float(np.linalg.norm(vec)))
    docs = client.embed_documents(
        [("Catan", "Trading and building."), ("Pandemic", "Cooperative disease fighting.")]
    )
    print("embed_documents:", docs.shape, np.linalg.norm(docs, axis=1))
    games = [
        {"bgg_id": 1, "name": "Pandemic", "mechanics": ["Cooperative Game"], "weight": 2.4},
        {"bgg_id": 2, "name": "Secret Hitler", "mechanics": ["Hidden Roles"], "weight": 1.8},
    ]
    print(client.explain("query", "a cooperative game", None, games))


if __name__ == "__main__":
    _smoke()
