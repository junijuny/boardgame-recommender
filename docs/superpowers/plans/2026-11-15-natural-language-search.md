# Natural Language Search + "Why this game" Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users find board games by describing them in Korean or English, and show a one-sentence English "why this game" reason on every result (natural-language search and "Find similar games").

**Architecture:** Gemini (`gemini-3.5-flash-lite`) turns the query into structured conditions (tags to include/exclude, weight range, an English `search_text`). `gemini-embedding-2` embeds `search_text`, which is matched against pre-computed document vectors in `data/gemini_embeddings.npz`. The existing hard filter, rating blend and MMR `diversify` produce the top 5. A separate `POST /explain` call asks Gemini for one grounded English sentence per game. All Gemini access goes through one module (`backend/gemini.py`) so tests swap in a fake.

**Tech Stack:** Python 3.12, FastAPI, numpy/pandas, `google-genai` SDK, unittest; React 19 + TypeScript + TanStack Query + Tailwind 4.

**Spec:** `docs/superpowers/specs/2026-11-14-natural-language-search-design.md`

## Global Constraints

- Generation model `gemini-3.5-flash-lite` for both extraction and explanation, as two separate constants `EXTRACT_MODEL`, `EXPLAIN_MODEL`. Embedding model `gemini-embedding-2`, `EMBED_DIM = 768`. Thinking set to the minimum level the model accepts.
- No `task_type` with `gemini-embedding-2`. Query text = `task: search result | query: {search_text}`. Document text = `title: {Name} | text: {body}`.
- Each document in a batch embed request is its own `Content` (a plain list of strings in one `contents` yields one aggregated vector).
- `GEMINI_API_KEY` lives only in the backend environment. Never in `frontend/`, never committed.
- Every user-visible string (frontend copy, API `detail` messages, explanation sentences) is English. Queries may be Korean or English.
- Existing endpoints (`/games/search`, `/games/filter`, `/recommend`, `/genres*`, `/games/{id}`, `/games/semantic-search`) must behave identically with no key and no `gemini_embeddings.npz`.
- Existing hard filter for new search: `_condition_mask(players, max_time, 5.5)`.
- Score: `similarity = 0.8·embedding + 0.2·tag_match` (embedding only when the intent has no include tags); `score = 0.75·similarity + 0.25·rating_score`; then `diversify(cand_idx, score, 5)`. Embedding similarity rescaled per query: `clip((raw − median) / max(max − median, 1e-6), 0, 1)` over candidates.
- Per-IP limits: `/search/natural` 10 per 60 s, `/explain` 30 per 60 s → `429 "Too many requests"`. Global budget: `GEMINI_DAILY_CALL_LIMIT` env (default `2000`) Gemini calls per instance per UTC day.
- Gemini timeout ~10 s per call. Explanation: one sentence, about 25 words max.
- `/search/natural` returns 5 results; no results → `404 "No games match the selected conditions"` (same text as `/recommend`).
- Backend modules use the existing dual import pattern (`try: from backend import x` / `except ImportError: import x`) because the Docker image runs from `backend/`.
- Tests: `uv run python -m unittest discover -s tests -v`. CI has no key; no test may call the real API.

## Review Focus

1. **A query that yields no usable tags** (pure mood like "뭔가 신나는 거", gibberish, or a single word) → still returns up to 5 results from embedding similarity, never 500. Test in Task 4.
2. **Gemini returns tag names outside the vocabulary, duplicate tags, `weight_min > weight_max`, or weights outside 1–5** → sanitized silently (unknown names dropped, weights clamped and swapped). Test in Task 4.
3. **Games with unknown difficulty (`GameWeight == 0`, 452 games)** under a weight range → kept, not dropped. Test in Task 4.
4. **An explanation that contains Hangul, is empty, or is keyed by an id that wasn't requested** → dropped; the card falls back to chips. Test in Task 6.
5. **Gemini timeout / SDK exception / budget exhausted mid-request** → `503` with an English detail, not 500, and the existing `/recommend` still works. Tests in Tasks 5 and 6.

---

### Task 1: Rate limiter and daily budget

**Files:**
- Create: `backend/limits.py`
- Test: `tests/test_limits.py`

**Interfaces:**
- Produces:
  - `class RateLimiter(limit: int, window_seconds: float = 60.0, clock: Callable[[], float] = time.monotonic)` with `allow(key: str) -> bool` (records the hit when allowed; sliding window).
  - `class DailyBudget(limit: int, today: Callable[[], datetime.date] = <UTC today>)` with `try_spend(n: int = 1) -> bool` and `remaining() -> int`. Counter resets when `today()` changes.
  - `client_ip(request: fastapi.Request) -> str`: first entry of `X-Forwarded-For` (stripped) if present, else `request.client.host`, else `"unknown"`. (Leftmost is spoofable; accepted because the global `DailyBudget` caps cost regardless. A wrong rightmost choice would put every Cloud Run user behind one proxy IP.)
  - Both classes thread-safe (`threading.Lock`): FastAPI runs sync endpoints in a thread pool.

- [ ] **Step 1: Write failing tests**

```python
class RateLimiterTests(unittest.TestCase):
    def test_allows_up_to_limit_then_blocks(self):
        now = [0.0]
        limiter = RateLimiter(3, 60, clock=lambda: now[0])
        self.assertEqual([limiter.allow("a") for _ in range(4)], [True, True, True, False])
        self.assertTrue(limiter.allow("b"))          # other key unaffected

    def test_window_slides(self):
        now = [0.0]
        limiter = RateLimiter(1, 60, clock=lambda: now[0])
        self.assertTrue(limiter.allow("a"))
        now[0] = 59.9; self.assertFalse(limiter.allow("a"))
        now[0] = 60.1; self.assertTrue(limiter.allow("a"))

class DailyBudgetTests(unittest.TestCase):
    def test_spends_until_limit_and_resets_next_day(self):
        day = [date(2026, 11, 15)]
        budget = DailyBudget(2, today=lambda: day[0])
        self.assertTrue(budget.try_spend()); self.assertTrue(budget.try_spend())
        self.assertFalse(budget.try_spend()); self.assertEqual(budget.remaining(), 0)
        day[0] = date(2026, 11, 16)
        self.assertTrue(budget.try_spend())

    def test_multi_spend_is_all_or_nothing(self):
        budget = DailyBudget(2, today=lambda: date(2026, 11, 15))
        self.assertFalse(budget.try_spend(3)); self.assertEqual(budget.remaining(), 2)

class ClientIpTests(unittest.TestCase):
    # build fake requests with types.SimpleNamespace(headers={...}, client=SimpleNamespace(host=...))
    def test_uses_first_forwarded_entry(self): ...   # "1.2.3.4, 10.0.0.1" -> "1.2.3.4"
    def test_falls_back_to_client_host(self): ...    # no header -> client.host
```

- [ ] **Step 2: Run** `uv run python -m unittest tests.test_limits -v` → FAIL (`ModuleNotFoundError: backend.limits`)
- [ ] **Step 3: Implement `backend/limits.py`** per the Interfaces block (deque of timestamps per key for `RateLimiter`).
- [ ] **Step 4: Run** the same command → PASS
- [ ] **Step 5: Commit** `feat(backend): add per-IP rate limiter and daily call budget`

---

### Task 2: Gemini client module (+ real-key smoke check)

**Files:**
- Modify: `pyproject.toml` (add `google-genai` to `dependencies`; run `uv add google-genai` so `uv.lock` updates)
- Create: `backend/gemini.py`
- Create: `tests/gemini_fake.py` (not a test module; used by later tasks)
- Test: `tests/test_gemini.py`

**Interfaces:**
- Consumes: `limits.DailyBudget`
- Produces (all in `backend/gemini.py`):
  - Constants `EXTRACT_MODEL = "gemini-3.5-flash-lite"`, `EXPLAIN_MODEL = "gemini-3.5-flash-lite"`, `EMBED_MODEL = "gemini-embedding-2"`, `EMBED_DIM = 768`, `TIMEOUT_SECONDS = 10`.
  - `class GeminiError(Exception)`; `class BudgetExceeded(GeminiError)`.
  - `@dataclass(frozen=True) class QueryIntent: search_text: str; include_mechanics: tuple[str, ...] = (); exclude_mechanics: tuple[str, ...] = (); include_themes: tuple[str, ...] = (); exclude_themes: tuple[str, ...] = (); weight_min: float | None = None; weight_max: float | None = None`
  - `def query_text(search_text: str) -> str` → `f"task: search result | query: {search_text}"`
  - `def document_text(title: str, body: str) -> str` → `f"title: {title or 'none'} | text: {body}"`
  - `class GeminiClient(Protocol)`:
    - `extract_intent(query: str, mechanic_names: Sequence[str], theme_names: Sequence[str]) -> QueryIntent`
    - `embed_query(search_text: str) -> np.ndarray` — float32, shape `(EMBED_DIM,)`, L2-normalized
    - `embed_documents(docs: Sequence[tuple[str, str]]) -> np.ndarray` — `(title, body)` pairs → float32 `(n, EMBED_DIM)`, L2-normalized rows
    - `explain(mode: Literal["similar", "query"], basis: str, basis_facts: dict | None, games: Sequence[dict]) -> dict[int, str]` — keys are `BGGId`
  - `class GoogleGeminiClient` implementing the protocol with `google.genai.Client(api_key=...)`. Every SDK exception → `GeminiError`. No sanitization here beyond parsing (Task 4/6 sanitize).
  - Module state + accessors: `get_client() -> GeminiClient | None` (built once from `GEMINI_API_KEY`; `None` when unset/empty), `set_client(client: GeminiClient | None) -> None` (tests), `budget: DailyBudget` (from `GEMINI_DAILY_CALL_LIMIT`, default 2000), `charge(n: int = 1) -> None` (raises `BudgetExceeded` when `budget.try_spend(n)` is False).
  - `tests/gemini_fake.py`: `class FakeGeminiClient` with constructor args `intent: QueryIntent | None = None`, `query_vector: np.ndarray | None = None`, `reasons: dict[int, str] | None = None`, `error: Exception | None = None`; records each call as `(method_name, *args)` in `self.calls: list[tuple]`; raises `error` from every method when set; `extract_intent` returns `intent` or `QueryIntent(search_text=query)`; `explain` returns `reasons` exactly as given (sanitization is tested in Task 6).

SDK usage (confirm exact names against the installed `google-genai` version before writing; do not guess):
- Extraction: `client.models.generate_content(model=EXTRACT_MODEL, contents=..., config=GenerateContentConfig(response_mime_type="application/json", response_schema=<schema>, thinking_config=<minimum>, http_options timeout))`. Schema: the 7 `QueryIntent` fields; `include_*`/`exclude_*` are arrays whose items are `enum` of the vocab names passed in. Prompt states: output English `search_text` describing the desired play experience (translate Korean); map "light/가벼운" etc. to a weight range on BGG's 1–5 scale; ignore player counts and play time (the UI supplies them); only tags clearly implied.
- Explanation: same call shape with `EXPLAIN_MODEL`; response schema `{"reasons": [{"bgg_id": int, "reason": str}]}`. Prompt: write exactly one English sentence (≤25 words) per game, using only the facts given; for `similar`, say what it shares with the basis game; for `query`, say which part of the user's request it fits; never mention facts not in the input.
- Embeddings: `client.models.embed_content(model=EMBED_MODEL, contents=[one Content per doc], config=EmbedContentConfig(output_dimensionality=EMBED_DIM))`; re-normalize with numpy.

- [ ] **Step 1: Write failing tests** (`tests/test_gemini.py`, no network)

```python
def test_prefix_formats(self):
    self.assertEqual(gemini.query_text("co-op"), "task: search result | query: co-op")
    self.assertEqual(gemini.document_text("Catan", "Trading."), "title: Catan | text: Trading.")
    self.assertEqual(gemini.document_text("", "x"), "title: none | text: x")

def test_charge_raises_when_budget_spent(self):
    gemini.budget = DailyBudget(1)            # restore original in tearDown
    gemini.charge()
    with self.assertRaises(gemini.BudgetExceeded):
        gemini.charge()

def test_no_key_means_no_client(self):
    # patch os.environ without GEMINI_API_KEY, reset the cached client, call get_client()
    self.assertIsNone(gemini.get_client())

def test_set_client_overrides(self):
    fake = FakeGeminiClient(); gemini.set_client(fake)
    self.assertIs(gemini.get_client(), fake)
```

- [ ] **Step 2: Run** `uv run python -m unittest tests.test_gemini -v` → FAIL (module missing)
- [ ] **Step 3: `uv add google-genai`, implement `backend/gemini.py` and `tests/gemini_fake.py`** per Interfaces.
- [ ] **Step 4: Run** the same command → PASS; then full suite `uv run python -m unittest discover -s tests -v` → PASS
- [ ] **Step 5: Real-key smoke check.** Add `if __name__ == "__main__":` to `backend/gemini.py` that loads the vocab (`features.load_binary_features` names for mechanics and themes), then prints: `extract_intent` for `"4명이서 1시간 안에 끝나는, 주사위 없는 가벼운 협력 게임"` and `"a tense game where players secretly betray each other"`; `embed_query("cooperative")` shape and norm; `explain("query", ...)` for two hand-written fact dicts.
  Run: `GEMINI_API_KEY=... uv run python -m backend.gemini`
  Expected: the 379-name enum schema is accepted (no 400); Korean query yields English `search_text`, `"Cooperative Game"` in include_mechanics, `"Dice Rolling"` in exclude_mechanics, `weight_max` ≤ ~2.5; vector shape `(768,)`, norm ≈ 1.0; reasons are English single sentences.
  **If the enum schema is rejected:** switch the tag fields to plain string arrays, put the vocab list in the prompt, and rely on Task 4's sanitization. Record which path was taken in the module docstring.
- [ ] **Step 6: Commit** `feat(backend): add Gemini client wrapper with budget and test fake`

---

### Task 3: Batch document embeddings (real run, committed data)

**Files:**
- Modify: `backend/semantic.py` (extract `game_documents(df, mechanics, themes) -> list[tuple[str, str]]` returning `(Name, body)`; `build_passages` reuses it so e5 output is byte-identical)
- Modify: `backend/features.py` (add `GEMINI_EMBEDDINGS_PATH = DATA_DIR / "gemini_embeddings.npz"`)
- Create: `backend/build_gemini_embeddings.py`
- Modify: `.gitignore` (add `data/gemini_embeddings.partial.npz`)
- Create (generated, committed): `data/gemini_embeddings.npz`
- Test: `tests/test_semantic_documents.py`

**Interfaces:**
- Consumes: `gemini.GoogleGeminiClient.embed_documents`, `gemini.EMBED_MODEL`, `gemini.EMBED_DIM`
- Produces: `data/gemini_embeddings.npz` with keys `ids` (int64, BGGId), `vectors` (float16, `(n, 768)`, L2-normalized before cast), `model_name` (`np.str_("gemini-embedding-2")`), `dim` (`np.int32(768)`).
- Body format (same content as today's e5 passage minus name/prefix): `"Mechanics: a, b. Themes: c. {Description[:1500]}"` (omit empty sections).

- [ ] **Step 1: Write failing test** — `build_passages` unchanged and `game_documents` shape:

```python
def test_build_passages_unchanged_and_documents_match(self):
    docs = semantic.game_documents(df.head(3), mech_head, theme_head)  # slice features to first 3 rows
    passages = semantic.build_passages(df.head(3), mech_head, theme_head)
    for (title, body), passage in zip(docs, passages):
        self.assertEqual(passage, f"passage: {title}. {body}")
    self.assertEqual(docs[0][0], df.iloc[0]["Name"])
```
(Before refactoring, capture `build_passages` output for the first 3 rows and assert equality to that captured string list too.)

- [ ] **Step 2: Run** `uv run python -m unittest tests.test_semantic_documents -v` → FAIL (`game_documents` missing)
- [ ] **Step 3: Refactor `semantic.py`; write `build_gemini_embeddings.py`**: batches of 100 docs; up to 5 retries with exponential backoff per batch on `GeminiError`; saves `data/gemini_embeddings.partial.npz` every 10 batches and resumes from it (skip ids already done); at the end writes the final file and deletes the partial. Prints progress and elapsed time. Exits with a clear message if `GEMINI_API_KEY` is unset. Does not call `gemini.charge` (offline job).
- [ ] **Step 4: Run** the unit test → PASS
- [ ] **Step 5: Run the real job.** `GEMINI_API_KEY=... uv run python -m backend.build_gemini_embeddings`
  Expected: 21,125 vectors; final file ≈ 32 MB; `np.load` shows `vectors.shape == (21125, 768)`, `vectors.dtype == float16`, row norms ≈ 1.0. Sanity: the nearest neighbors of Pandemic's vector include other cooperative games.
- [ ] **Step 6: Commit** code + `data/gemini_embeddings.npz`: `feat(data): add Gemini document embeddings and build script`

---

### Task 4: Natural search engine

**Files:**
- Create: `backend/natural_search.py`
- Test: `tests/test_natural_search.py`

**Interfaces:**
- Consumes: `recommend_engine.df`, `.mechanics`, `.themes`, `._condition_mask`, `.rating_score`, `.diversify`, `.DEFAULT_COLUMNS`, `.RATING_WEIGHT`; `gemini.get_client`, `gemini.charge`, `gemini.QueryIntent`, `gemini.EMBED_MODEL`, `gemini.EMBED_DIM`; `features.GEMINI_EMBEDDINGS_PATH`
- Produces:
  - `@dataclass class GeminiIndex: vectors: np.ndarray  # float32 (len(df), dim), zero rows for missing; present: np.ndarray  # bool`
  - `load_index(path: Path = GEMINI_EMBEDDINGS_PATH) -> GeminiIndex | None` — `None` if file missing **or** `model_name != EMBED_MODEL` **or** `dim != EMBED_DIM`; reindexed to `df["BGGId"]` like `features.load_embeddings`.
  - `set_index(index: GeminiIndex | None) -> None` (tests); module loads the real index at import.
  - `natural_search_available() -> bool` — client and index both present.
  - `sanitize_intent(intent: QueryIntent, raw_query: str) -> QueryIntent` — drop names not in `mechanics.names`/`themes.names`, dedupe preserving order, remove any name that is in both include and exclude from include; clamp weights into [1, 5], swap if min > max; empty/whitespace `search_text` → `raw_query`.
  - `natural_search(query: str, players: int, max_time: int, exclude_ids: list[int] | None = None, top_n: int = 5) -> list[dict]` — raises `RuntimeError("Natural language search is not available")` when unavailable; lets `GeminiError` propagate. Each record: `DEFAULT_COLUMNS` + `Similarity`, `Score`, `MatchedMechanics`, `MatchedThemes` (include tags this game has, in intent order).
  - Caches: intent LRU keyed by `query.strip().lower()` (256 entries); query-vector LRU keyed by `search_text` (256). `gemini.charge()` is called only on cache misses, once per Gemini call.

Filter specifics: exclude a game if it has **any** excluded mechanic/theme; weight range applies only to games with `GameWeight > 0` (unknown weight passes); drop `exclude_ids`; drop rows with `present == False`. `tag_match` = (number of include tags the game has) / (number of include tags).

- [ ] **Step 1: Write failing tests.** Fixture helper `make_index(top_idx: int, dim: int = 8) -> GeminiIndex`: row `top_idx` is the unit vector `e0`; every other row is a deterministic random unit vector with component 0 set to 0 (`np.random.default_rng(0)`), so only the chosen game has raw similarity > 0 and it wins regardless of rating. `FakeGeminiClient(query_vector=e0)`. `setUp` installs fake client and `make_index(idx_of("Pandemic"))`; `tearDown` restores both.

```python
def test_returns_five_matching_conditions_with_fields(self):
    games = natural_search("co-op", players=4, max_time=60)
    self.assertEqual(len(games), 5)
    for g in games:
        self.assertLessEqual(g["MinPlayers"], 4); self.assertGreaterEqual(g["MaxPlayers"], 4)
        self.assertLessEqual(g["ComMaxPlaytime"], 60)
        for key in ("Similarity", "Score", "MatchedMechanics", "MatchedThemes"):
            self.assertIn(key, g)
    self.assertEqual(games[0]["Name"], "Pandemic")

def test_exclude_mechanics_removes_games(self):
    fake.intent = QueryIntent("co-op", exclude_mechanics=("Dice Rolling",))
    for g in natural_search("q", 4, 120):
        self.assertFalse(has_mechanic(g["BGGId"], "Dice Rolling"))

def test_weight_range_keeps_unknown_weight(self):
    # intent weight_max=1.5; pick a game with GameWeight == 0 that passes 4p/120m,
    # set_index(make_index(that_idx)) -> it is still returned first

def test_sanitize_drops_unknown_and_fixes_weights(self):
    s = sanitize_intent(QueryIntent(" ", include_mechanics=("Not A Tag", "Cooperative Game", "Cooperative Game"),
                                    weight_min=4.8, weight_max=0.2), "원문")
    self.assertEqual(s.include_mechanics, ("Cooperative Game",))
    self.assertEqual((s.weight_min, s.weight_max), (1.0, 4.8))
    self.assertEqual(s.search_text, "원문")

def test_no_tags_still_returns_results(self):
    fake.intent = QueryIntent("something fun")
    self.assertEqual(len(natural_search("뭔가 신나는 거", 4, 60)), 5)

def test_exclude_ids_and_cache(self):
    first = natural_search("co-op", 4, 60)
    second = natural_search("co-op", 4, 60, exclude_ids=[g["BGGId"] for g in first])
    self.assertFalse({g["BGGId"] for g in first} & {g["BGGId"] for g in second})
    self.assertEqual(sum(c[0] == "extract_intent" for c in fake.calls), 1)   # cached on Refresh

def test_unavailable_without_client(self):
    set_client(None)
    with self.assertRaises(RuntimeError): natural_search("co-op", 4, 60)

def test_index_rejected_on_model_mismatch(self):
    # write a tiny npz to a temp dir with model_name="other"; load_index(path) is None
```

- [ ] **Step 2: Run** `uv run python -m unittest tests.test_natural_search -v` → FAIL (module missing)
- [ ] **Step 3: Implement `backend/natural_search.py`** per Interfaces and Global Constraints scoring.
- [ ] **Step 4: Run** → PASS; full suite → PASS
- [ ] **Step 5: Commit** `feat(backend): add natural language search engine`

---

### Task 5: `/search/natural` endpoint and capability flags

**Files:**
- Modify: `backend/main.py`
- Test: `tests/test_natural_api.py`

**Interfaces:**
- Consumes: `natural_search.natural_search`, `.natural_search_available`; `gemini.get_client`, `GeminiError`; `limits.RateLimiter`, `client_ip`
- Produces:
  - `GET /` adds `"natural_search": bool` and `"explanations": bool` (`gemini.get_client() is not None`). The frontend needs both: explanations for "By game" work without the index.
  - `POST /search/natural`, body `NaturalSearchRequest { query: str; players: int; max_time: int; exclude_ids: list[int] = [] }`, returns the list from `natural_search`.
  - Status mapping, checked in this order:
    1. stripped query empty → 400 `"Search query cannot be empty"`; longer than 300 chars → 400 `"Search query is too long"`; `players <= 0` → 400 `"Players must be greater than 0"`; `max_time <= 0` → 400 `"Max time must be greater than 0"`
    2. not available → 503 `"Natural language search is not available"`
    3. rate limited (`RateLimiter(10, 60)` keyed by `client_ip`) → 429 `"Too many requests"`
    4. `GeminiError` → 503 `"Natural language search is temporarily unavailable"`
    5. empty result → 404 `"No games match the selected conditions"`

- [ ] **Step 1: Write failing tests** (fake client + 8-dim index as in Task 4; reset the endpoint's limiter in `setUp` by replacing the module-level limiter object):

```python
def test_root_reports_flags(self): body = get("/").json(); assert both keys are bool
def test_search_returns_five(self): post {"query": "co-op", "players": 4, "max_time": 60} -> 200, len 5
def test_validation(self): for (" ", 4, 60), ("x"*301, 4, 60), ("q", 0, 60), ("q", 4, 0) -> 400
def test_unavailable_is_503(self): set_client(None) -> 503 "Natural language search is not available"
def test_gemini_error_is_503(self): FakeGeminiClient(error=GeminiError("boom")) -> 503 "...temporarily unavailable"
def test_budget_exhausted_is_503(self): gemini.budget = DailyBudget(0) -> 503
def test_rate_limit_is_429(self): 10 requests 200, 11th 429 "Too many requests"
def test_existing_recommend_unaffected_without_key(self): set_client(None); POST /recommend Catan -> 200
```

- [ ] **Step 2: Run** `uv run python -m unittest tests.test_natural_api -v` → FAIL
- [ ] **Step 3: Implement** in `backend/main.py`; existing endpoints stay untouched. Limiter is a module-level object (`natural_limiter = RateLimiter(10, 60)`) so tests can replace it.
- [ ] **Step 4: Run** → PASS; full suite → PASS (existing `test_root_reports_active_signals` still passes)
- [ ] **Step 5: Commit** `feat(api): add POST /search/natural with rate limiting`

---

### Task 6: Explanations (`/explain`)

**Files:**
- Create: `backend/explain.py`
- Modify: `backend/main.py`
- Test: `tests/test_explain.py`

**Interfaces:**
- Consumes: `recommend_engine.df`, `.mechanics`, `.themes`, `.get_game_by_name`; `gemini.get_client`, `.charge`, `GeminiError`; `limits.RateLimiter`, `client_ip`
- Produces:
  - `game_facts(idx: int) -> dict` — `{"bgg_id", "name", "year", "players": "2-4", "playtime": "30-60 min", "weight": float | None (None when 0), "mechanics": list[str], "themes": list[str], "description": first 600 chars}`.
  - `explain_games(mode: Literal["similar", "query"], basis: str, game_ids: list[int]) -> dict[int, str]` — dedupes ids, ignores ids not in `df`; for `similar` raises `LookupError("Game not found")` if `basis` isn't a known game, and passes `game_facts` of the basis; LRU cache (1024) keyed by `(mode, basis.strip().lower(), bgg_id)`; calls `gemini.charge()` once and the client once only for uncached ids; **sanitizes** output: keep only requested ids, strip, drop empty strings and any string containing Hangul (`[ㄱ-ㆎ가-힣]`), cache only kept reasons.
  - `POST /explain`, body `ExplainRequest { mode: Literal["similar", "query"]; basis: str; game_ids: list[int] }` → `{"reasons": {"<id>": "..."}}`. Order: 400 if `basis` blank or > 300 chars, or `game_ids` empty or > 10 (422 from pydantic for a bad `mode` is fine); 503 `"Explanations are not available"` when no client; 429 via `RateLimiter(30, 60)`; 404 `"Game not found"` from `LookupError`; 503 `"Explanations are temporarily unavailable"` on `GeminiError`.

- [ ] **Step 1: Write failing tests**

```python
def test_returns_reasons_for_requested_ids(self):
    fake.reasons = {catan_like_id: "A trading game with a modular board, like Catan."}
    body = post("/explain", {"mode": "similar", "basis": "Catan", "game_ids": [catan_like_id]}).json()
    self.assertEqual(body["reasons"], {str(catan_like_id): "A trading game with a modular board, like Catan."})

def test_drops_hangul_empty_and_unrequested(self):
    fake.reasons = {a: "협력 게임입니다.", b: "  ", c: "Fine sentence.", 999999999: "Extra."}
    # request [a, b, c] -> only c returned

def test_cache_avoids_second_call(self): same request twice -> fake.calls has one "explain"
def test_unknown_basis_game_is_404(self): mode similar, basis "No Such Game" -> 404
def test_validation(self): blank basis, 301-char basis, [], 11 ids -> 400
def test_no_client_is_503(self) / test_gemini_error_is_503(self) / test_rate_limit_is_429(self)
def test_explanations_work_without_index(self): set_index(None) -> /explain still 200
```

- [ ] **Step 2: Run** `uv run python -m unittest tests.test_explain -v` → FAIL
- [ ] **Step 3: Implement** `backend/explain.py` and the endpoint.
- [ ] **Step 4: Run** → PASS; full suite → PASS
- [ ] **Step 5: Real-key spot check.** Start `GEMINI_API_KEY=... uv run uvicorn backend.main:app --port 8000`; `POST /recommend` for Catan, then `POST /explain` with those 5 ids; `POST /search/natural` with the Korean query from Task 2, then `/explain` in `query` mode. Expected: English single sentences that only cite listed mechanics/themes. Adjust prompts if not.
- [ ] **Step 6: Commit** `feat(api): add POST /explain with grounded one-sentence reasons`

---

### Task 7: Frontend data layer and reasons on "By game" results

**Files:**
- Modify: `frontend/src/types.ts`, `frontend/src/api.ts`, `frontend/src/queries.ts`
- Create: `frontend/src/components/ResultList.tsx` (move `ResultList` and `ResultSkeleton` out of `RecommendScreen.tsx`, generalized)
- Modify: `frontend/src/screens/RecommendScreen.tsx`

**Interfaces:**
- Produces:
  - `types.ts`: `ServerInfo { natural_search: boolean; explanations: boolean }`; `NaturalSearchRequest { query: string; players: number; max_time: number; exclude_ids?: number[] }`; `NaturalGame extends FilteredGame { Similarity: number; Score: number; MatchedMechanics: string[]; MatchedThemes: string[] }`; `ExplainMode = "similar" | "query"`; `ExplainRequest { mode: ExplainMode; basis: string; game_ids: number[] }`; `ExplainResponse { reasons: Record<string, string> }`.
  - `api.ts`: `getServerInfo(): Promise<ServerInfo>` (`GET /`), `naturalSearch(req: NaturalSearchRequest): Promise<NaturalGame[]>` (`POST /search/natural`, omit empty `exclude_ids` like `recommend`), `explain(req: ExplainRequest): Promise<ExplainResponse>`.
  - `queries.ts`: `useServerInfo()` (`staleTime: Infinity`, `retry: 1`); `useNaturalSearch()` (mutation); `useExplanations(req: ExplainRequest | null)` — `useQuery` keyed `["explain", mode, basis, ...game_ids]`, `enabled: req != null`, `staleTime: Infinity`, `retry: false`.
  - `components/ResultList.tsx`: `export interface ResultItem { game: FilteredGame; chips: string[] }`; `export function ResultList({ items, reasons, reasonsLoading, onSelect }: { items: ResultItem[]; reasons?: Record<string, string>; reasonsLoading: boolean; onSelect: (bggId: number) => void })` and `export function ResultSkeleton({ label }: { label: string })`.
  - Row rendering: keep the existing layout; under the meta line show, in order of preference: the reason as `<p className="text-[15px] leading-snug text-ink/85">` → while `reasonsLoading`, a `Skeleton` line (`h-3.5 w-4/5`) → otherwise the chips (existing chip markup).
- "By game" wiring in `RecommendScreen`: after a successful recommend, call `useExplanations({ mode: "similar", basis: variables.game_name, game_ids: data.map(g => g.BGGId) })` only when `useServerInfo().data?.explanations` is true; chips = `SharedMechanics`. Explanation errors are silent (chips remain).

- [ ] **Step 1: Implement** types/api/queries and `ResultList.tsx`; switch `RecommendScreen` to the shared component.
- [ ] **Step 2: Verify** `cd frontend && npm run typecheck && npm run lint && npm run build` → all succeed with no errors.
- [ ] **Step 3: Manual check** (backend with key on :8000, `npm run dev`): recommend for Catan → 5 rows appear, then each gains one English sentence; with the backend started **without** a key → no reason skeleton appears, chips show, and the browser console has no errors.
- [ ] **Step 4: Commit** `feat(frontend): show one-sentence reasons on similar-game results`

---

### Task 8: "By description" tab

**Files:**
- Create: `frontend/src/components/DescriptionSearch.tsx` (form + results panel for natural search)
- Create: `frontend/src/components/SimilarSearch.tsx` (the current form + results panel moved out of `RecommendScreen`, unchanged behavior)
- Modify: `frontend/src/screens/RecommendScreen.tsx` (becomes title + tabs + the two panels)

**Interfaces:**
- Consumes: `useServerInfo`, `useNaturalSearch`, `useExplanations`, `ResultList`, `ResultSkeleton`, `PlayerPicker`, `TimePicker`, `ErrorNotice`, `ServerWakeNotice`, `useIsSlow`, `errorResponse`, `PLAYER_OPTIONS`, `TIME_OPTIONS`, `formatMinutes`
- Produces:
  - `RecommendScreen` props unchanged (`initialGame`, `onRecommendSimilar`). Heading text `Find games`. Tabs (WAI-ARIA `role="tablist"`, two `role="tab"` buttons with `aria-selected`, arrow-key switching) labeled `By game` and `By description`. Both panels stay mounted; the inactive one gets `hidden` so inputs and results survive tab switches. Default tab `By game`. When `useServerInfo().data?.natural_search` is not true, render no tabs, only the "By game" panel (heading stays `Find games`).
  - `DescriptionSearch` state: `query`, `players` (default 4), `maxTime` (default 60), `shownIds`. Same Refresh/exclude behavior as the similar panel. Changing query/players/time clears results.
  - Copy (exact): input label `Describe the game you want`; placeholder `e.g. a cooperative game with no dice, under an hour`; submit `Get recommendations` (disabled while loading or when `query.trim()` is empty); idle `Describe the kind of game you want to play.`; summary `Matching "{query}", {players} players, up to {formatMinutes(max_time)}`; 404 no-match and after-refresh texts reuse the existing ones; 503 → `Description search is unavailable right now. Try "By game" instead.`; 429 → `Too many searches. Wait a minute and try again.`; network → existing `Can't reach the server.` with retry; skeleton sr label `Finding games`.
  - `maxLength={300}` on the input (matches the API limit).
  - Explanations: `useExplanations({ mode: "query", basis: variables.query, game_ids })` when `explanations` is true; chips = `MatchedMechanics` then `MatchedThemes`, max 3.

- [ ] **Step 1: Implement** the three files.
- [ ] **Step 2: Verify** `cd frontend && npm run typecheck && npm run lint && npm run build` → success.
- [ ] **Step 3: Manual check** at phone width (≈375 px) and desktop: switch tabs (inputs preserved), Korean query `4명이서 1시간 안에 끝나는 주사위 없는 협력 게임` → 5 results within the 4p/60m filters, reasons appear in English; Refresh → 5 different games; keyboard: tab focus + arrow keys switch tabs; stop the backend's key → tab disappears after reload.
- [ ] **Step 4: Commit** `feat(frontend): add By description natural language search tab`

---

### Task 9: Deploy wiring and docs

**Files:**
- Modify: `.github/workflows/deploy-backend.yml` (`--set-env-vars "ALLOWED_ORIGINS=${{ env.ALLOWED_ORIGINS }},GEMINI_API_KEY=${{ secrets.GEMINI_API_KEY }}"`)
- Modify: `Dockerfile` comment only (Gemini is an HTTP API; no new heavy deps)
- Modify: `docs/backend_api.md` (both endpoints, `GET /` flags, status table rows), `docs/recommendation_pipeline.md` (natural search pipeline section + rebuild command), `docs/setup.md` (`GEMINI_API_KEY` locally, optional; how to run the build script), `docs/deploy.md` (register GitHub secret `GEMINI_API_KEY` **before** merging; key is visible as a plain env var on the service; `GEMINI_DAILY_CALL_LIMIT`), `README.md` (feature table row for "By description" + reasons)

- [ ] **Step 1: Edit** the workflow and docs.
- [ ] **Step 2: Verify** the workflow YAML parses: `uv run python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/deploy-backend.yml'))"` (use `uvx --from pyyaml python ...` if PyYAML isn't installed) → no error; `grep -n GEMINI_API_KEY .github/workflows/deploy-backend.yml` shows the secret reference; `git grep -n "AIza" -- . ':!uv.lock'` → no matches (no key committed).
- [ ] **Step 3: Full verification:** `uv run python -m unittest discover -s tests -v` → all PASS; `cd frontend && npm run build` → success.
- [ ] **Step 4: Commit** `docs: document natural search, explanations and Gemini deployment`
