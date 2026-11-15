# Natural Search Accuracy (Stages 1–3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make natural-language search return results that fit the meaning of most human queries, and measure the improvement: an evaluation set (stage 1), unused audience data and proper-noun keywords (stage 2), and Gemini re-ranking with a shown interpretation plus one-per-series results (stage 3).

**Architecture:** The current pipeline (Gemini intent → hard filter → embedding + tag score) becomes the *retriever*. Its scored candidates are collapsed to one game per series, the top 40 go to a Gemini re-rank call that returns an ordered id list, a one-line interpretation and a weak-match flag, and the server pages through that order. Ranking queries (`sort != relevance`) skip re-ranking. Any re-rank failure falls back to today's ordering. A new offline script scores every change against a fixed query set.

**Tech Stack:** Python 3.12, FastAPI, numpy/pandas, `google-genai`, unittest; React 19 + TypeScript + TanStack Query + Tailwind 4.

**Spec:** `docs/superpowers/specs/2026-11-15-natural-search-accuracy-design.md` (builds on `docs/superpowers/specs/2026-11-14-natural-language-search-design.md`)

**Out of this plan:** Spec stage 4 (BGG XML API metadata, `OtherVersions` in the detail popup, franchise/designer hard filters, BGG-based series keys). It gets its own plan once the user has a BGG API token and the real XML has been inspected — the family-prefix rules depend on that data. Task 1's `series_keys` is the temporary grouping the spec calls for until then.

## Global Constraints

- Ship as three PRs: stage 1 = Tasks 1–2, stage 2 = Task 3, stage 3 = Tasks 4–9. Branch each stage from the previous stage's branch (stage 1 from `feat/natural-search-sort`, which holds the spec commit).
- Candidate pool unchanged: `_condition_mask(players, max_time, 5.5)` and `NumUserRatings >= MIN_REVIEWS` (1000).
- Re-rank model constant `RERANK_MODEL = "gemini-3.5-flash-lite"`, own timeout `RERANK_TIMEOUT_SECONDS = 5`. Shortlist size `SHORTLIST_SIZE = 40`, re-rank returns at most `RERANK_MAX_IDS = 20` ids. Each re-rank call goes through `gemini.charge()`.
- Ranking queries (`sort` in popularity/rating/newest) never call re-rank; their interpretation is fixed copy: popularity `"Ranked by number of BGG reviews."`, rating `"Ranked by BGG rating."`, newest `"Ranked by release year."`
- Re-rank failure (any `gemini.GeminiError`, including `BudgetExceeded`, timeout, bad JSON) → today's ordering, `interpretation = None`, never 503. Intent-extraction and embedding failures stay 503 as today.
- Results always fill to 5 when candidates exist; no candidates → `404 "No games match the selected conditions"`.
- One game per series in every result page (series = Task 1 `series_keys`).
- All user-visible text English. Interpretation and reasons containing Hangul are dropped.
- Weak-match copy (frontend): `"We couldn't find a close match. These are the nearest games."`
- Tests: `uv run python -m unittest discover -s tests -v`; CI has no keys, no test calls Gemini. Frontend checks: `cd frontend && npm run typecheck && npm run lint`.
- Real-key commands: `uv run --env-file .env <command>`. Never print or commit the key.
- Backend modules keep the dual import pattern (`try: from backend import x` / `except ImportError: import x`).

## Review Focus

1. **Gemini returns Hangul or junk in `keywords`** (e.g. `["스타워즈"]`, `[""]`, a 200-char string) → dropped by sanitize, search still works. Test in Task 3.
2. **A ranking query whose keyword matches nothing under the chosen players/time** ("가장 유명한 스타워즈 게임", 6 players, 30 min) → empty result → 404, not unrelated popular games. Test in Task 3.
3. **Re-rank returns duplicate ids, ids outside the shortlist, or two games of the same series** → deduped and filtered; page still has 5 distinct-series games. Test in Task 6.
4. **Refresh after every candidate has been shown** → 404 as today (no infinite padding, no repeats). Test in Task 6.
5. **Games with missing `GoodPlayers` / `ComAgeRec` / `LanguageEase`** → treated as unknown (no fit bonus, pass the age filter, neutral text score), never a crash. Test in Task 3.

---

### Task 1: Temporary series keys

**Files:**
- Create: `backend/series.py`
- Test: `tests/test_series.py`

**Interfaces:**
- Produces: `series_keys(df: pd.DataFrame, min_reviews: int) -> np.ndarray` (dtype object, one key string per row, rows in `df` order); module-level `KEYS: np.ndarray = series_keys(eng.df, MIN_REVIEWS)` computed at import from `recommend_engine.df` with `MIN_REVIEWS = 1000`.

- [ ] **Step 1: Write the failing tests** in `tests/test_series.py` (unittest, real `eng.df`, helper `key(name)` = `series.KEYS[idx_of(name)]`):
  - `test_family_groups_versions`: `key("Carcassonne") == key("Carcassonne: Hunters and Gatherers") == key("New World: A Carcassonne Game") == key("Carcassonne: Star Wars")`; `key("Ticket to Ride") == key("Ticket to Ride: Europe")`; `key("Pandemic") == key("Pandemic Legacy: Season 1")`.
  - `test_publisher_line_family_does_not_group`: games whose `Family` is `"Two-player games (Kosmos)"` do not all share one key (pick two members with different name stems; assert keys differ). Same for `"Harvest (Uwe Rosenberg)"`.
  - `test_name_prefix_joins_base_game`: synthetic `df` (3 rows: `"Foo"` 2000 reviews no family, `"Foo: Big Box"` 1500 no family, `"Star Wars: Bar"` 1500 no family) → first two share a key; the third's key differs from both and is not `"star wars"` grouping anything else.
  - `test_unrelated_games_have_distinct_keys`: `key("Catan") != key("Pandemic")`.

- [ ] **Step 2: Run** `uv run python -m unittest tests.test_series -v` → FAIL (`No module named 'backend.series'`).

- [ ] **Step 3: Implement `series_keys`** in `backend/series.py`:

```text
norm(s)  = lowercase, keep letters/digits/spaces, collapse spaces
label(f) = norm(text before " (" in Family f)
pass 1, each row:
  if Family f non-empty and f" {label(f)}" in f" {norm(Name)}"
      (label starts at a word boundary; prefix match so truncated labels like "carcassonn" still hit)
      → key = "f:" + label(f)
  else key = None
pass 2, rows with key None:
  base = norm(Name before first ":")
  if ":" in Name and some row with NumUserRatings >= min_reviews has norm(Name) == base → key = that row's key (or "n:" + base if it has none)
  else key = "n:" + norm(Name)
```

- [ ] **Step 4: Run** `uv run python -m unittest tests.test_series -v` → PASS.

- [ ] **Step 5: Commit** `git add backend/series.py tests/test_series.py && git commit -m "feat(search): add temporary series keys for grouping game versions"`

---

### Task 2: Evaluation set, metrics script, baseline

**Files:**
- Create: `data/natural_eval_queries.json`, `backend/evaluate_natural.py`, `data/natural_eval_results/baseline.json` (generated)
- Test: `tests/test_evaluate_natural.py`
- Modify: `docs/setup.md` (how to run the evaluation)

**Interfaces:**
- Consumes: `series.KEYS` (Task 1); `natural_search.natural_search(query, players, max_time, exclude_ids=None, top_n=5) -> list[dict]` (today's signature).
- Produces:
  - Query file format — a JSON array of `{"query": str, "type": "audience"|"mood"|"genre"|"ranking"|"external"|"no_answer"|"series", "players": int, "max_time": int, "good": [int], "bad": [int], "expect_weak_match": bool}`.
  - `hit_at_k(ids: list[int], good: set[int], k: int) -> bool`, `precision_at_k(ids, good, k) -> float`, `has_series_duplicate(ids: list[int]) -> bool`, `unreachable(entry: dict) -> list[int]` (good ids that fail the candidate pool for that entry's players/time), `run(entries, label: str, search=natural_search) -> dict` (summary + per-query rows; `search` is injectable for tests).
  - CLI: `uv run --env-file .env python -m backend.evaluate_natural --label <name>` writes `data/natural_eval_results/<name>.json` and prints Hit@5, Precision@5, Recall@40, duplicate rate, bad count, weak-match rate on `no_answer` — overall and per `type`.

- [ ] **Step 1: Write the failing tests** in `tests/test_evaluate_natural.py`:
  - `test_hit_and_precision`: `hit_at_k([1,2,3], {3}, 5) is True`; `hit_at_k([1,2], {9}, 5) is False`; `precision_at_k([1,2,3,4,5], {1,2}, 5) == 0.4`.
  - `test_series_duplicate`: ids of `"Pandemic"` and `"Pandemic Legacy: Season 1"` → `True`; `"Pandemic"` and `"Catan"` → `False`.
  - `test_unreachable_flags_games_outside_pool`: a 1–2 player game in `good` with `players=5` is returned by `unreachable`.
  - `test_run_with_fake_search`: `run([...one entry...], "t", search=lambda q, p, t, top_n: rows)` returns `summary["hit_at_5"] == 1.0` when rows contain a good id; `per_query[0]["names"]` lists names.
  - `test_query_file_is_valid`: every entry in `data/natural_eval_queries.json` has the keys above, a known `type`, 40 ≤ entries ≤ 60, every type present at least 4 times, both Hangul and Latin queries present, and `unreachable(entry) == []` for all entries.

- [ ] **Step 2: Run** `uv run python -m unittest tests.test_evaluate_natural -v` → FAIL (module missing).

- [ ] **Step 3: Implement the metric functions, `run` and the CLI** in `backend/evaluate_natural.py`. Recall@40 for this stage: call `search(query, players, max_time, top_n=40)` (intent and vector are cached, so no extra Gemini calls) and check `good` against those ids. `no_answer` weak-match rate is reported as `null` while results carry no `weak_match`.

- [ ] **Step 4: Draft `data/natural_eval_queries.json`**: 40–60 queries, Korean and English mixed, each type ≥ 4, including the spec's examples ("할머니, 할아버지와 함께하기 좋은 게임", "동물들도 이해하기 쉬운 게임", "스타워즈 테마의 보드게임", "한국인이 만든 보드게임", "가장 유명한 게임", a co-op disease query for the series type). `good` lists 3–15 BGG ids that are in the pool for that entry's players/time. `external` entries for Korean-made games may have `good` drawn from what the data supports today (likely few). `no_answer` entries set `expect_weak_match: true` and may have empty `good`.

- [ ] **Step 5: Run** `uv run python -m unittest tests.test_evaluate_natural -v` → PASS.

- [ ] **Step 6: Stop for user review of the query set.** Show the user the queries with `good` game names (not ids) per entry and wait for their corrections. Apply them and re-run Step 5.

- [ ] **Step 7: Record the baseline**: `uv run --env-file .env python -m backend.evaluate_natural --label baseline` → writes `data/natural_eval_results/baseline.json`, prints the metric table without errors.

- [ ] **Step 8: Add a "Natural search evaluation" section to `docs/setup.md`** (command, needs `GEMINI_API_KEY`, about 4 Gemini calls per query, results folder).

- [ ] **Step 9: Commit** `git add backend/evaluate_natural.py tests/test_evaluate_natural.py data/natural_eval_queries.json data/natural_eval_results/baseline.json docs/setup.md && git commit -m "feat(search): add natural search evaluation set and baseline"`

---

### Task 3: Audience data, categories and keywords (stage 2)

**Files:**
- Modify: `backend/features.py` (`load_games`), `backend/gemini.py` (`QueryIntent`, `EXTRACT_PROMPT`, extract schema, `_intent_from_dict`), `backend/natural_search.py` (`sanitize_intent`, `natural_search` scoring)
- Test: `tests/test_natural_search.py`, `tests/test_gemini.py`
- Create: `data/natural_eval_results/stage2.json` (generated)

**Interfaces:**
- Produces:
  - `load_games()` also adds `ComAgeRec: float` (missing → 0.0 = unknown), `LanguageEase: float` (missing → NaN = unknown), `GoodPlayers: tuple[int, ...]` (parsed from strings like `"['2', '3']"`; unparseable/missing → `()`).
  - `QueryIntent` new fields: `age_max: float | None = None`, `categories: tuple[str, ...] = ()` (values from `CATEGORY_NAMES = ("Thematic", "Strategy", "War", "Family", "CGS", "Abstract", "Party", "Childrens")`, column `f"Cat:{name}"`), `low_text: bool = False`, `keywords: tuple[str, ...] = ()`.
  - Score constants in `natural_search.py`: `SIMILARITY_WEIGHT = 0.65`, `RATING_WEIGHT = 0.2`, `SOFT_WEIGHT = 0.15` (starting values; tune with the evaluation).

- [ ] **Step 1: Write the failing tests**:
  - `tests/test_gemini.py::test_intent_from_dict_reads_new_fields`: `_intent_from_dict({"search_text": "x", "age_max": 8, "categories": ["Family"], "low_text": True, "keywords": ["Star Wars"]})` has those values; missing fields → defaults.
  - `tests/test_natural_search.py`:
    - `test_sanitize_keywords`: `keywords=("Star Wars", "스타워즈", "", "x"*200, "star wars", "A", "B", "C")` → `("Star Wars", "A", "B")` (Hangul/empty/over-40-char dropped, case-insensitive dedupe, max 3).
    - `test_sanitize_age_and_categories`: `age_max=40` → `18.0`; `age_max=0` → `2.0`; `categories=("family", "Nope")` → `("Family",)`.
    - `test_age_max_filters_known_ages`: intent `age_max=8` → every result has `ComAgeRec == 0 or ComAgeRec <= 8`.
    - `test_keyword_matches_name_or_description`: intent `QueryIntent("space war", keywords=("Star Wars",), sort="popularity")`, players 2, time 180 → every result's Name or Description contains "star wars" (case-insensitive, whole words), first result has the most reviews among them.
    - `test_ranking_keyword_with_no_match_is_empty`: `QueryIntent("", keywords=("Zzyzx Qwerty",), sort="popularity")` → `[]`.
    - `test_category_counts_as_include_tag`: intent `categories=("Party",)` → top result has `Cat:Party == 1`.
    - `test_missing_audience_data_is_safe`: set one candidate's `GoodPlayers=()`, `ComAgeRec=0`, `LanguageEase=NaN` on a copy of `eng.df` patched for the test, intent `low_text=True, age_max=10` → search returns results without error and that game is not excluded by the age filter.
  - Keep all existing tests passing (update expected orders only where the new weights legitimately change them, and say so in the commit message).

- [ ] **Step 2: Run** `uv run python -m unittest tests.test_natural_search tests.test_gemini -v` → new tests FAIL.

- [ ] **Step 3: Extend `load_games`** to merge the three raw columns (same `raw` read, add to `usecols`) and parse `GoodPlayers` with `ast.literal_eval` inside a try.

- [ ] **Step 4: Extend `QueryIntent`, the extract schema (`age_max` nullable NUMBER, `categories`/`keywords` STRING arrays, `low_text` BOOLEAN) and `EXTRACT_PROMPT`.** Prompt rules to add, one line each: `age_max` only when children or an age is mentioned; `categories` only from the listed names; `low_text` for "no reading / language-independent"; `keywords` = proper nouns in the request (franchise, designer, publisher, country) in their official English form (e.g. 스타워즈 → "Star Wars", 한국 → "Korea"), still never in `search_text`.

- [ ] **Step 5: Implement in `natural_search.py`**:
  - `sanitize_intent`: rules from the tests (`age_max` clamped to 2–18, categories canonicalised, keywords cleaned with the existing `_HANGUL`-style regex, ≤ 40 chars, ≤ 3).
  - Hard filter: `age_max` → `~(ComAgeRec > 0) | (ComAgeRec <= age_max)`.
  - Include tags: categories (`Cat:X > 0`) and keywords (regex `\b{re.escape(kw)}\b`, case-insensitive, on `Name + " " + Description`) count toward `include_total` and `tag_hits` exactly like mechanics/themes, including the ranking-query "must have a tag" restriction.
  - Soft score in [0, 1], the mean of the active signals: player fit (`players in GoodPlayers` → 1, else 0, `()` → 0), always active; `low_text` → `1 − percentile rank of LanguageEase among candidates` (NaN → 0.5).
  - `score = SIMILARITY_WEIGHT·similarity + RATING_WEIGHT·rating_score + SOFT_WEIGHT·soft` for relevance queries; ranking queries unchanged.

- [ ] **Step 6: Run** the full suite `uv run python -m unittest discover -s tests -v` → PASS.

- [ ] **Step 7: Evaluate**: `uv run --env-file .env python -m backend.evaluate_natural --label stage2`. Compare to `baseline.json`. If Hit@5 drops overall, adjust the three weights and re-run (at most a few rounds); record the final weights.

- [ ] **Step 8: Commit** `git add backend/features.py backend/gemini.py backend/natural_search.py tests/ data/natural_eval_results/stage2.json && git commit -m "feat(search): use age, language, player-fit, category and keyword signals"`

---

### Task 4: Gemini re-rank call

**Files:**
- Modify: `backend/gemini.py`, `tests/gemini_fake.py`
- Create: `backend/rerank.py`
- Test: `tests/test_rerank.py`, `tests/test_gemini.py`

**Interfaces:**
- Produces:
  - `gemini.RerankResult` frozen dataclass: `interpretation: str`, `ranked_ids: tuple[int, ...]`, `weak_match: bool`.
  - `GeminiClient.rerank(self, query: str, games: Sequence[dict]) -> RerankResult` (Protocol + `GoogleGeminiClient`); `GoogleGeminiClient._generate` gains `timeout_seconds: int = TIMEOUT_SECONDS`, re-rank passes `RERANK_TIMEOUT_SECONDS`.
  - `FakeGeminiClient(rerank_result: RerankResult | None = None, rerank_error: Exception | None = None)`; `rerank` records `("rerank", query, games)` and returns `rerank_result` or `RerankResult("Read as: fake.", tuple(g["bgg_id"] for g in games), False)`.
  - `rerank.rerank_facts(idx: int) -> dict`: keys `bgg_id, name, year, mechanics, themes, categories, weight, age, players, good_players, playtime, reviews, rating, description` (description first 300 chars).
  - Constants in `rerank.py`: `RERANK_MAX_IDS = 20`, `DESCRIPTION_CHARS = 300`, `MAX_INTERPRETATION_CHARS = 200`. `RERANK_MODEL`, `RERANK_TIMEOUT_SECONDS`, `RERANK_MAX_TOKENS` live in `gemini.py`; `SHORTLIST_SIZE = 40` in `natural_search.py`.
  - `rerank.rerank(query: str, cand_rows: list[int]) -> gemini.RerankResult`: charges the budget, calls the client, returns a cleaned result — ids filtered to the given rows' BGG ids, deduped, ≤ `RERANK_MAX_IDS`; interpretation stripped, `"Read as: "` prefixed if missing, set to `""` when it contains Hangul or exceeds 200 chars. Raises `gemini.GeminiError` on client failure.

- [ ] **Step 1: Write the failing tests**:
  - `tests/test_gemini.py::test_rerank_result_parsing`: the dict→`RerankResult` helper turns `{"interpretation": "Read as: x", "ranked_ids": [3, "4"], "weak_match": true}` into `RerankResult("Read as: x", (3, 4), True)`; missing `ranked_ids` → `GeminiError`.
  - `tests/test_rerank.py`:
    - `test_facts_fields`: `rerank_facts(idx_of("Pandemic"))` has all listed keys, `len(description) <= 300`.
    - `test_filters_unknown_and_duplicate_ids`: fake returns `ranked_ids=(id_a, 999999, id_a, id_b)` → `(id_a, id_b)`.
    - `test_caps_at_max_ids`: fake returns 30 valid ids → 20.
    - `test_interpretation_cleaned`: Hangul interpretation → `""`; `"Simple rules."` → `"Read as: Simple rules."`.
    - `test_charges_budget_and_propagates_errors`: exhausted `gemini.budget` → `BudgetExceeded`; fake `rerank_error=GeminiError("x")` → raises `GeminiError`.

- [ ] **Step 2: Run** `uv run python -m unittest tests.test_rerank tests.test_gemini -v` → FAIL.

- [ ] **Step 3: Implement** `RerankResult`, the parsing helper, `GoogleGeminiClient.rerank` (schema: `interpretation` STRING, `ranked_ids` INTEGER array, `weak_match` BOOLEAN; `RERANK_MAX_TOKENS = 1024`; prompt rules: order games by how well they fit the request, omit poor fits, at most 20 ids; one English sentence starting "Read as:" saying how the request was understood, no game names; `weak_match` true when fewer than 3 games fit well; judge only from the given facts), the fake, and `backend/rerank.py`.

- [ ] **Step 4: Run** `uv run python -m unittest discover -s tests -v` → PASS.

- [ ] **Step 5: Smoke check with the real key** (not committed): a short script calling `rerank.rerank("할머니, 할아버지와 함께하기 좋은 게임", <first 40 candidate rows>)` returns ≥ 5 ids, an English interpretation, within 5 s.

- [ ] **Step 6: Commit** `git add backend/gemini.py backend/rerank.py tests/gemini_fake.py tests/test_rerank.py tests/test_gemini.py && git commit -m "feat(search): add Gemini re-rank call"`

---

### Task 5: One game per series in the retriever

**Files:**
- Modify: `backend/natural_search.py`
- Test: `tests/test_natural_search.py`

**Interfaces:**
- Consumes: `series.KEYS` (Task 1).
- Produces: `group_series(cand_idx: np.ndarray, score: np.ndarray, tag_hits: np.ndarray, prefer_col: str) -> np.ndarray` — positions into `cand_idx`, one per series, ordered by the series' best `score` descending. Representative: among the series' members with the maximum `tag_hits`, the one with the largest `df[prefer_col]` (ties → more reviews). `prefer_col` is `"NumUserRatings"` for relevance queries and the sort column for ranking queries.

- [ ] **Step 1: Write the failing tests**:
  - `test_group_series_keeps_most_reviewed`: candidates = Pandemic, Pandemic Legacy S1, Catan with Legacy scoring highest, equal `tag_hits` → returns [Pandemic, Catan] positions, Pandemic first.
  - `test_group_series_prefers_tag_match`: Carcassonne and Carcassonne: Star Wars, only Star Wars has `tag_hits = 1` → Star Wars kept.
  - `test_group_series_ranking_uses_sort_column`: `prefer_col="BayesAvgRating"` over Pandemic family members → the highest-rated member kept.
  - `test_search_results_have_one_per_series`: a co-op query whose embedding favors Pandemic (`make_index(idx_of("Pandemic"))`) → no two results share `series.KEYS`.
  - `test_ranking_results_have_one_per_series`: `QueryIntent("", sort="popularity")` → no two results share a series key.

- [ ] **Step 2: Run** `uv run python -m unittest tests.test_natural_search -v` → new tests FAIL.

- [ ] **Step 3: Implement `group_series`** and apply it in `natural_search` before `diversify` (relevance) and inside `_sorted_positions` before taking `top_n` (ranking). `tag_hits` is the per-candidate include-tag hit count already computed (zeros when no include tags).

- [ ] **Step 4: Run** `uv run python -m unittest discover -s tests -v` → PASS.

- [ ] **Step 5: Commit** `git add backend/natural_search.py tests/test_natural_search.py && git commit -m "feat(search): show one game per series in natural search"`

---

### Task 6: Re-ranked search with interpretation and weak match

**Files:**
- Modify: `backend/natural_search.py`, `backend/evaluate_natural.py`, `backend/main.py` (`search_natural` only: return the object shape below)
- Test: `tests/test_natural_search.py`, `tests/test_evaluate_natural.py`, `tests/test_natural_api.py` (existing tests read `body["games"]`)

**Interfaces:**
- Consumes: `rerank.rerank` (Task 4), `group_series` (Task 5).
- Produces:
  - `NaturalResult` dataclass: `games: list[dict]`, `interpretation: str | None`, `weak_match: bool`, `shortlist_ids: list[int]`.
  - `natural_search(query, players, max_time, exclude_ids=None, top_n=5) -> NaturalResult` (return type changes; callers updated in Tasks 6–7).
  - Re-rank cache `_rerank_cache = _LRU()` keyed `(query.strip().lower(), players, max_time)`, cleared by `clear_caches()`.

- [ ] **Step 1: Write the failing tests** (fake client):
  - `test_rerank_order_is_used`: fake `rerank_result` ranks the 3rd-scored shortlist game first → `games[0]` is that game; `interpretation == "Read as: …"` from the fake.
  - `test_pads_to_five_and_flags_weak`: fake ranks 2 ids, `weak_match=False` → 5 games, first two are the ranked ones, `weak_match is True`.
  - `test_model_weak_flag_passes_through`: fake ranks 10 ids with `weak_match=True` → `weak_match is True`.
  - `test_dedupes_series_in_rerank_output`: fake ranks Pandemic and another member of its series → at most one of them in `games`. (Shortlist is already one-per-series; also assert re-rank never sees two same-series games in `games` arg.)
  - `test_refresh_uses_cache`: first call, then call with `exclude_ids` = first page → second page is ranked ids 6–10, `rerank` called once in total.
  - `test_refresh_cache_miss_calls_again_without_storing`: clear caches, call with `exclude_ids` → `rerank` called; a following call without `exclude_ids` calls `rerank` again.
  - `test_rerank_failure_falls_back`: fake `rerank_error=GeminiError("x")` → 5 games, `interpretation is None`, `weak_match is False`, no exception.
  - `test_ranking_query_skips_rerank`: `sort="popularity"` → no `rerank` call, `interpretation == "Ranked by number of BGG reviews."`.
  - `test_exhausted_candidates_returns_empty`: keep calling with growing `exclude_ids` until `games == []`; no id appears twice across pages.
  - Update existing tests to read `.games`.
  - `tests/test_evaluate_natural.py`: fake search returning `NaturalResult` → Recall@40 uses `shortlist_ids`; `no_answer` weak-match rate is a number.

- [ ] **Step 2: Run** `uv run python -m unittest tests.test_natural_search tests.test_evaluate_natural -v` → FAIL.

- [ ] **Step 3: Implement** in `natural_search`:
  - Relevance path: score → `group_series` → `ordered` (all one-per-series positions by score) → `shortlist = ordered[:SHORTLIST_SIZE]`.
  - Cache lookup; on miss call `rerank.rerank(query, [cand_idx[p] for p in shortlist])`; store only when `exclude_ids` is empty. On `GeminiError` → fallback: `diversify` over the `ordered` candidates, `interpretation=None`, `weak_match=False`.
  - Page order = ranked ids still among candidates (in ranked order) + remaining `ordered` positions; take `top_n`. `weak_match = result.weak_match or any picked game came from the padding`.
  - Ranking path unchanged apart from Task 5, plus the fixed interpretation copy.
  - `shortlist_ids` = BGG ids of `shortlist` (ranking path: the sorted pool's first 40).
  - Update `evaluate_natural.run` to use `NaturalResult`.
  - `main.search_natural` returns `{"games": result.games, "interpretation": result.interpretation, "weak_match": result.weak_match}`; empty `games` → 404 as today. Existing API tests switch to `body["games"]`.

- [ ] **Step 4: Run** `uv run python -m unittest discover -s tests -v` → PASS.

- [ ] **Step 5: Commit** `git add backend/natural_search.py backend/evaluate_natural.py backend/main.py tests/ && git commit -m "feat(search): re-rank natural search with Gemini and report interpretation"`

---

### Task 7: API shape and weak-match-aware reasons

**Files:**
- Modify: `backend/main.py` (`ExplainRequest`, `explain`), `backend/explain.py` (`explain_games`), `backend/gemini.py` (`explain`, `MODE_RULES`), `tests/gemini_fake.py`, `docs/backend_api.md`
- Test: `tests/test_natural_api.py`, `tests/test_explain.py`

**Interfaces:**
- Consumes: `NaturalResult` (Task 6).
- Produces:
  - `POST /search/natural` → `{"games": [...], "interpretation": str | null, "weak_match": bool}`; empty `games` → 404 as today.
  - `ExplainRequest.weak_match: bool = False`; `explain_games(mode, basis, game_ids, weak_match: bool = False)`; cache key `(mode, basis_key, weak_match, bgg_id)`; `GeminiClient.explain(..., weak_match: bool = False)`; when true the prompt adds: "These games are only the nearest matches; do not claim they fully deliver the request. Say which aspect comes closest."

- [ ] **Step 1: Write the failing tests**:
  - `test_natural_api.py::test_search_returns_object`: 200 body has `games` (len 5), `interpretation`, `weak_match`.
  - `test_natural_api.py::test_rerank_failure_still_200`: fake with `rerank_error` → 200, `interpretation is None`.
  - `test_explain.py::test_weak_match_reaches_client_and_cache`: `explain_games("query", "q", [id], weak_match=True)` → fake recorded `weak_match=True`; a second call with `weak_match=False` calls the client again (separate cache entry).
  - `test_natural_api.py`: `POST /explain` with `"weak_match": true` → 200.

- [ ] **Step 2: Run** `uv run python -m unittest tests.test_natural_api tests.test_explain -v` → FAIL.

- [ ] **Step 3: Implement** the endpoint changes and `weak_match` plumbing; update `docs/backend_api.md` for both endpoints.

- [ ] **Step 4: Run** `uv run python -m unittest discover -s tests -v` → PASS.

- [ ] **Step 5: Commit** `git add backend/main.py backend/explain.py backend/gemini.py tests/ docs/backend_api.md && git commit -m "feat(api): return interpretation and weak match, soften reasons for weak matches"`

---

### Task 8: Frontend — interpretation line and weak-match notice

**Files:**
- Modify: `frontend/src/types.ts`, `frontend/src/api.ts`, `frontend/src/components/DescriptionSearch.tsx`

**Interfaces:**
- Consumes: the Task 7 response shape.
- Produces: `NaturalSearchResponse { games: NaturalGame[]; interpretation: string | null; weak_match: boolean }`; `ExplainRequest.weak_match?: boolean`; `naturalSearch(...) -> Promise<NaturalSearchResponse>`.

- [ ] **Step 1: Update types and `naturalSearch`.**

- [ ] **Step 2: Update `DescriptionSearch`**: results come from `search.data.games` (results list, `shownIds`, explain `game_ids`, the "newest" note check); explain request passes `weak_match: search.data.weak_match`; under the `summarize(...)` line render `search.data.interpretation` when non-null, same `text-[15px] text-ink/70` style; when `weak_match` render the notice box (same classes as the existing "newest" note) with the Global Constraints copy, above the results.

- [ ] **Step 3: Run** `cd frontend && npm run typecheck && npm run lint` → no errors.

- [ ] **Step 4: Check in the running app** (backend with key + `npm run dev`): "할머니, 할아버지와 함께하기 좋은 게임" shows an interpretation line and 5 cards with reasons; "동물들도 이해하기 쉬운 게임" shows the weak-match notice; "가장 유명한 게임" shows "Ranked by number of BGG reviews."; Refresh gives 5 new games with no duplicates of a series already shown on that page.

- [ ] **Step 5: Commit** `git add frontend/src && git commit -m "feat(frontend): show search interpretation and weak-match notice"`

---

### Task 9: Stage 3 evaluation and pipeline docs

**Files:**
- Create: `data/natural_eval_results/stage3.json` (generated)
- Modify: `docs/recommendation_pipeline.md`

- [ ] **Step 1: Evaluate**: `uv run --env-file .env python -m backend.evaluate_natural --label stage3` → completes; Hit@5 overall ≥ `stage2.json`, duplicate rate 0.

- [ ] **Step 2: If Hit@5 fell or a type regressed**, inspect that type's per-query rows, adjust the re-rank prompt or `SHORTLIST_SIZE` once, re-run, and keep the better of the two.

- [ ] **Step 3: Update `docs/recommendation_pipeline.md`**: retriever → series grouping → re-rank → paging/fallback, new signals and weights, and a table of baseline / stage2 / stage3 metrics per type. Note which types remain weak (expected: `external` Korean-made → stage 4, BGG data).

- [ ] **Step 4: Run** `uv run python -m unittest discover -s tests -v` and `cd frontend && npm run typecheck && npm run lint` → all pass.

- [ ] **Step 5: Commit** `git add data/natural_eval_results/stage3.json docs/recommendation_pipeline.md && git commit -m "docs(search): record re-ranking evaluation results"`
