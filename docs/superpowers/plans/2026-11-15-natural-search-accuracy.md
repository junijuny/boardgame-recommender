# Natural Search Accuracy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make natural-language search return results that fit the meaning of most human queries, and measure it: evaluation set (stage 1), unused data + keywords + word match + one-per-series (stage 2), Gemini-written game profiles re-embedded (stage 3), Gemini re-ranking with a shown interpretation (stage 4), and live web search only for questions that need outside facts (stage 5).

**Architecture:** The current pipeline (Gemini intent → hard filter → embedding + tag score) stays as the retriever and gains more signals. Offline, Gemini writes a short English play-experience profile plus franchise / base game / designers / designer countries for the 2,906 candidate games; profiles are embedded into a second vector file and used for retrieval and re-ranking only. Online, scored candidates collapse to one per series; the top 25 go to a Gemini re-rank call returning order, interpretation and weak-match. Queries the intent step flags `needs_web` first run a Google-grounded Gemini call whose plain-text answer is matched to our games, shown to the user with Google's search-suggestion widget, and never cached.

**Tech Stack:** Python 3.12, FastAPI, numpy/pandas, scikit-learn TF-IDF (existing), `google-genai`, unittest; React 19 + TypeScript + TanStack Query + Tailwind 4.

**Spec:** `docs/superpowers/specs/2026-11-15-natural-search-accuracy-design.md` (builds on `docs/superpowers/specs/2026-11-14-natural-language-search-design.md`)

## Global Constraints

- Five PRs: stage 1 = Tasks 1–2, stage 2 = Tasks 3–4, stage 3 = Tasks 5–6, stage 4 = Tasks 7–10, stage 5 = Tasks 11–12. Each stage branches from the previous stage's branch (stage 1 from `feat/natural-search-sort`).
- Candidate pool unchanged: `_condition_mask(players, max_time, 5.5)` and `NumUserRatings >= MIN_REVIEWS` (1000).
- Gemini budget about 6,000 KRW total. Every real-key step states its expected cost; stop and tell the user if a step would exceed it. Evaluation uses 40 queries and the intent/vector disk cache.
- Series = whole series, sequels and spin-offs included (Pandemic + Pandemic Legacy, Codenames + Codenames: Duet). One game per series on every result page.
- Profiles are built from Gemini's own knowledge and our data only — **no web search** when building them. Profiles and their metadata feed retrieval and re-rank only; never shown on screen.
- Web search (Grounding with Google Search): plain-text responses only (no JSON schema); grounded text, matched ids and the re-rank result of a `needs_web` query are **never cached, stored, logged, or evaluated**; the grounded summary is always shown with the unmodified search-suggestion HTML; web search is skipped (never 503) on failure, timeout, or when `WEB_SEARCH_DAILY_LIMIT` (default 100) is spent.
- Model constants (all start at `"gemini-3.5-flash-lite"`): `PROFILE_MODEL`, `RERANK_MODEL`, `WEB_MODEL`. Timeouts: re-rank `RERANK_TIMEOUT_SECONDS = 5`, web `WEB_TIMEOUT_SECONDS = 8`. `SHORTLIST_SIZE = 25`, `RERANK_MAX_IDS = 20`.
- Ranking queries (`sort` in popularity/rating/newest) never call re-rank; fixed interpretation copy: popularity `"Ranked by number of BGG reviews."`, rating `"Ranked by BGG rating."`, newest `"Ranked by release year."`
- Re-rank failure → today's ordering, `interpretation = None`, never 503. Intent-extraction and embedding failures stay 503.
- Results fill to 5 when candidates exist; none → `404 "No games match the selected conditions"`.
- All user-visible text English; interpretation/reasons containing Hangul are dropped.
- Weak-match copy: `"We couldn't find a close match. These are the nearest games."` Web box heading: `"From the web"`.
- Tests: `uv run python -m unittest discover -s tests -v` (CI has no key; no test calls Gemini). Frontend: `cd frontend && npm run typecheck && npm run lint`.
- Real-key commands: `uv run --env-file .env <command>`. Never print or commit the key.
- Backend modules keep the dual import pattern (`try: from backend import x` / `except ImportError: import x`).

## Review Focus

1. **Gemini returns Hangul or junk in `keywords`/`terms`** (`["스타워즈"]`, `[""]`, a 200-char string) → dropped by sanitize, search still works. Test in Task 3.
2. **A ranking query whose keyword matches nothing under the chosen players/time** ("가장 유명한 스타워즈 게임", 6 players, 30 min) → 404, not unrelated popular games. Test in Task 3.
3. **Re-rank returns duplicate ids, ids outside the shortlist, or two games of one series** → page still has 5 distinct-series games. Test in Task 8.
4. **A `needs_web` query followed by Refresh** → the second request runs web search again and nothing from the first web response is reused from any cache. Test in Task 11.
5. **Games missing `GoodPlayers` / `ComAgeRec` / `LanguageEase` / a profile** → treated as unknown (no bonus, pass age filter, old vector), never a crash. Tests in Tasks 3 and 6.

---

## Stage 1 — Evaluation

### Task 1: Temporary series keys

**Files:**
- Create: `backend/series.py`
- Test: `tests/test_series.py`

**Interfaces:**
- Produces: `series_keys(df: pd.DataFrame, min_reviews: int, base_games: dict[int, str] | None = None) -> np.ndarray` (object dtype, one key per row, `df` order); module-level `KEYS` computed at import from `recommend_engine.df` with `MIN_REVIEWS = 1000` and no base games; `set_keys(keys: np.ndarray) -> None` (Task 6 replaces `KEYS` after profiles load). `base_games` maps BGGId → base game name (used from Task 6).

- [ ] **Step 1: Write the failing tests** in `tests/test_series.py` (unittest on real `eng.df`; helper `key(name)` = `series.KEYS[idx_of(name)]`):
  - `test_family_groups_versions`: `key("Carcassonne") == key("Carcassonne: Hunters and Gatherers") == key("New World: A Carcassonne Game") == key("Carcassonne: Star Wars")`; `key("Ticket to Ride") == key("Ticket to Ride: Europe")`; `key("Pandemic") == key("Pandemic Legacy: Season 1")`.
  - `test_publisher_line_family_does_not_group`: two members of `Family == "Two-player games (Kosmos)"` with different name stems have different keys; same for `"Harvest (Uwe Rosenberg)"`.
  - `test_name_prefix_joins_base_game`: synthetic df (`"Foo"` 2000 reviews, `"Foo: Big Box"` 1500, `"Star Wars: Bar"` 1500, all without family) → first two share a key, third differs.
  - `test_base_games_join_series`: synthetic df (`"Alpha"`, `"Zeta Quest"`) with `base_games={id_of_zeta: "Alpha"}` → same key.
  - `test_unrelated_games_have_distinct_keys`: `key("Catan") != key("Pandemic")`.

- [ ] **Step 2: Run** `uv run python -m unittest tests.test_series -v` → FAIL (module missing).

- [ ] **Step 3: Implement `series_keys`:**

```text
norm(s)  = lowercase, keep letters/digits/spaces, collapse spaces
label(f) = norm(text before " (" in Family f)
pass 1: Family f non-empty and f" {label(f)}" in f" {norm(Name)}"   → key "f:" + label(f)
pass 2 (rows still without key):
   base = norm(base_games[id]) if base_games has id, else norm(Name before first ":") if ":" in Name
   if base equals norm(Name) of a row with NumUserRatings >= min_reviews → that row's key
       (computing it first; a base row without a key gets "n:" + norm(its Name))
   else key "n:" + norm(Name)
```

- [ ] **Step 4: Run** `uv run python -m unittest tests.test_series -v` → PASS.

- [ ] **Step 5: Commit** `git add backend/series.py tests/test_series.py && git commit -m "feat(search): add temporary series keys for grouping game versions"`

### Task 2: Evaluation set, metrics script, baseline

**Files:**
- Create: `data/natural_eval_queries.json`, `backend/evaluate_natural.py`, `data/natural_eval_results/baseline.json` (generated)
- Modify: `.gitignore` (add `data/natural_eval_cache.json`), `docs/setup.md`
- Test: `tests/test_evaluate_natural.py`

**Interfaces:**
- Consumes: `series.KEYS`; `natural_search.natural_search(query, players, max_time, exclude_ids=None, top_n=5)` (today returns `list[dict]`; Task 8 changes it to `NaturalResult`).
- Produces:
  - Query entry: `{"query": str, "type": "audience"|"mood"|"genre"|"ranking"|"external"|"no_answer"|"series", "players": int, "max_time": int, "good": [int], "bad": [int], "expect_weak_match": bool}`.
  - `hit_at_k(ids: list[int], good: set[int], k: int) -> bool`, `precision_at_k(ids, good, k) -> float`, `has_series_duplicate(ids: list[int]) -> bool`, `unreachable(entry: dict) -> list[int]`, `run(entries: list[dict], label: str, search=natural_search, recall_n: int = 25) -> dict` (`{"label", "summary": {...overall + "by_type"}, "per_query": [...]}`).
  - `DiskCache(path: Path)` used by the CLI to pre-fill `natural_search._intent_cache` / `_vector_cache` from `data/natural_eval_cache.json` and save new entries after the run; `--fresh-intents` ignores stored intents (use after a prompt change).
  - CLI `uv run --env-file .env python -m backend.evaluate_natural --label <name> [--fresh-intents]` → writes `data/natural_eval_results/<name>.json`, prints the metric table.

- [ ] **Step 1: Write the failing tests:**
  - `test_hit_and_precision`: `hit_at_k([1,2,3], {3}, 5)`; not `hit_at_k([1,2], {9}, 5)`; `precision_at_k([1,2,3,4,5], {1,2}, 5) == 0.4`.
  - `test_series_duplicate`: Pandemic + Pandemic Legacy: Season 1 → `True`; Pandemic + Catan → `False`.
  - `test_unreachable_flags_games_outside_pool`: a game with `MaxPlayers < 5` in `good` with `players=5` is returned.
  - `test_run_with_fake_search`: one entry, `search=lambda q, p, t, top_n: rows` containing a good id → `summary["hit_at_5"] == 1.0`; `per_query[0]["names"]` holds names.
  - `test_disk_cache_round_trip`: save an intent + vector to a temp path, load into fresh caches → `_intent_cache.get(key)` equals the saved `QueryIntent`.
  - `test_query_file_is_valid`: exactly 40 entries, known types, each type ≥ 4, Hangul and Latin queries both present, all spec §1 example queries present, `unreachable(e) == []` for all.

- [ ] **Step 2: Run** `uv run python -m unittest tests.test_evaluate_natural -v` → FAIL.

- [ ] **Step 3: Implement** metrics, `run`, `DiskCache` (JSON: intent dataclass fields; vectors as float lists keyed by `search_text`), CLI. Recall@N for now = ids of `search(..., top_n=recall_n)`. Weak-match rate is `null` while results have no `weak_match`.

- [ ] **Step 4: Draft `data/natural_eval_queries.json`** (40 entries, Korean/English mixed, spec §1 examples included, `good` 3–15 pool ids; `no_answer` entries `expect_weak_match: true`, `good` may be empty).

- [ ] **Step 5: Run** `uv run python -m unittest tests.test_evaluate_natural -v` → PASS.

- [ ] **Step 6: Stop for user review of the query set** — show each query with `good` game *names*; apply corrections; re-run Step 5.

- [ ] **Step 7: Baseline** (≈ 200–300 KRW): `uv run --env-file .env python -m backend.evaluate_natural --label baseline` → writes `baseline.json`, prints the table.

- [ ] **Step 8: Docs** — "Natural search evaluation" section in `docs/setup.md` (command, key needed, cache file, `--fresh-intents`, cost per run).

- [ ] **Step 9: Commit** `git add backend/evaluate_natural.py tests/test_evaluate_natural.py data/natural_eval_queries.json data/natural_eval_results/baseline.json .gitignore docs/setup.md && git commit -m "feat(search): add natural search evaluation set and baseline"`

---

## Stage 2 — Data we already have

### Task 3: Audience data, categories, keywords, word match

**Files:**
- Modify: `backend/features.py` (`load_games`), `backend/gemini.py` (`QueryIntent`, extract schema, `EXTRACT_PROMPT`, `_intent_from_dict`), `backend/natural_search.py`
- Test: `tests/test_natural_search.py`, `tests/test_gemini.py`

**Interfaces:**
- Produces:
  - `load_games()` adds `ComAgeRec: float` (missing → 0.0 = unknown), `LanguageEase: float` (missing → NaN), `GoodPlayers: tuple[int, ...]` (parsed from `"['2', '3']"`; bad/missing → `()`).
  - `QueryIntent` new fields: `age_max: float | None = None`, `categories: tuple[str, ...] = ()` (from `CATEGORY_NAMES = ("Thematic", "Strategy", "War", "Family", "CGS", "Abstract", "Party", "Childrens")` → column `f"Cat:{name}"`), `low_text: bool = False`, `keywords: tuple[str, ...] = ()`, `terms: tuple[str, ...] = ()`.
  - `natural_search.keyword_hits(cand_idx: np.ndarray, keywords: tuple[str, ...]) -> np.ndarray` (bool, `len(cand_idx) × len(keywords)`; whole-word, case-insensitive on `Name + " " + Description`; Task 6 extends it to profile metadata).
  - Weights: `EMBEDDING_WEIGHT = 0.7`, `TAG_WEIGHT = 0.15`, `WORD_WEIGHT = 0.15` (inside similarity); `SIMILARITY_WEIGHT = 0.65`, `RATING_WEIGHT = 0.2`, `SOFT_WEIGHT = 0.15` (final). Starting values.

- [ ] **Step 1: Write the failing tests:**
  - `test_gemini.py::test_intent_from_dict_reads_new_fields`: all five new fields parsed; missing → defaults.
  - `test_natural_search.py`:
    - `test_sanitize_keywords_and_terms`: `keywords=("Star Wars", "스타워즈", "", "x"*200, "star wars", "A", "B", "C")` → `("Star Wars", "A", "B")`; same rules for `terms` (max 3, ≤ 40 chars, no Hangul, case-insensitive dedupe).
    - `test_sanitize_age_and_categories`: `age_max=40` → `18.0`; `age_max=0` → `2.0`; `categories=("family", "Nope")` → `("Family",)`.
    - `test_age_max_filters_known_ages`: `age_max=8` → every result has `ComAgeRec == 0 or <= 8`.
    - `test_keyword_ranking_query`: `QueryIntent("", keywords=("Star Wars",), sort="popularity")`, 2 players, 180 min → every result has "star wars" as whole words in Name or Description; sorted by reviews.
    - `test_ranking_keyword_with_no_match_is_empty`: `QueryIntent("", keywords=("Zzyzx Qwerty",), sort="popularity")` → `[]`.
    - `test_category_counts_as_include_tag`: `categories=("Party",)` → top result has `Cat:Party == 1`.
    - `test_terms_word_match_raises_score`: two candidates with equal embedding, one with "zombies" in its description; `terms=("zombies",)` → that one ranks higher.
    - `test_missing_audience_data_is_safe`: patch a candidate to `GoodPlayers=()`, `ComAgeRec=0`, `LanguageEase=NaN`; intent `low_text=True, age_max=10` → no error, that game not excluded by age.
    - `test_word_match_off_without_tfidf`: with `eng.tfidf = None` patched → search still returns 5.
  - Existing tests stay green (adjust expected orders only where new weights legitimately change them; say so in the commit).

- [ ] **Step 2: Run** `uv run python -m unittest tests.test_natural_search tests.test_gemini -v` → new tests FAIL.

- [ ] **Step 3: Extend `load_games`** (same raw read, add the three columns; `ast.literal_eval` in a try for `GoodPlayers`).

- [ ] **Step 4: Extend `QueryIntent`, schema and `EXTRACT_PROMPT`** (`age_max` nullable NUMBER, `low_text` BOOLEAN, three STRING arrays). Prompt rules, one line each: `age_max` only when children or an age is mentioned; `categories` only from the listed names; `low_text` for "no reading / language-independent"; `keywords` = proper nouns (franchise, designer, publisher, country) in official English form (스타워즈 → "Star Wars", 한국 → "Korea"), still never in `search_text`; `terms` = up to 3 concrete subject nouns in English ("animals", "zombies", "trains"), not mechanics.

- [ ] **Step 5: Implement in `natural_search.py`:**
  - `sanitize_intent` per the tests.
  - Age hard filter: `~(ComAgeRec > 0) | (ComAgeRec <= age_max)`.
  - Categories and keywords count as include tags (in `include_total`, `tag_hits`, and the ranking-query "must have a tag" restriction), keywords via `keyword_hits`.
  - Word score: `eng.tfidf.transform([" ".join(terms)])` · `eng._get_tfidf_matrix()[cand_idx].T`, rescaled to [0, 1] by its max over candidates; skipped (weight folded into embedding) when `terms` is empty or `eng.tfidf is None`.
  - Soft score = mean of active signals: player fit (`players in GoodPlayers`) always; `low_text` → `1 − percentile(LanguageEase)` over candidates (NaN → 0.5).
  - Relevance: `similarity = 0.7·embedding + 0.15·tag + 0.15·word` (renormalize over the parts present), `score = 0.65·similarity + 0.2·rating_score + 0.15·soft`. Ranking queries unchanged.

- [ ] **Step 6: Run** `uv run python -m unittest discover -s tests -v` → PASS.

- [ ] **Step 7: Commit** `git add backend/features.py backend/gemini.py backend/natural_search.py tests/ && git commit -m "feat(search): use age, language, player-fit, category, keyword and word-match signals"`

### Task 4: One game per series in results + stage 2 evaluation

**Files:**
- Modify: `backend/natural_search.py`
- Test: `tests/test_natural_search.py`
- Create: `data/natural_eval_results/stage2.json` (generated)

**Interfaces:**
- Consumes: `series.KEYS` (Task 1), `tag_hits` from Task 3.
- Produces: `group_series(cand_idx: np.ndarray, score: np.ndarray, tag_hits: np.ndarray, prefer_col: str) -> np.ndarray` — positions into `cand_idx`, one per series, ordered by the series' best `score` descending; representative = among members with max `tag_hits`, the largest `df[prefer_col]` (ties → more reviews). `prefer_col` = `"NumUserRatings"` (relevance) or the sort column (ranking).

- [ ] **Step 1: Write the failing tests:**
  - `test_group_series_keeps_most_reviewed`: Pandemic, Pandemic Legacy S1 (highest score), Catan, equal `tag_hits` → [Pandemic, Catan], Pandemic first.
  - `test_group_series_prefers_tag_match`: Carcassonne vs Carcassonne: Star Wars with only the latter `tag_hits = 1` → Star Wars kept.
  - `test_group_series_ranking_uses_sort_column`: `prefer_col="BayesAvgRating"` over Pandemic members → highest-rated kept.
  - `test_search_results_have_one_per_series` (relevance, `make_index(idx_of("Pandemic"))`) and `test_ranking_results_have_one_per_series` (`sort="popularity"`): no two results share a key.

- [ ] **Step 2: Run** `uv run python -m unittest tests.test_natural_search -v` → FAIL.

- [ ] **Step 3: Implement `group_series`;** apply before `diversify` (relevance) and in `_sorted_positions` before `top_n` (ranking). Read `series.KEYS` through the module at call time (Task 6 swaps it with `set_keys`).

- [ ] **Step 4: Run** `uv run python -m unittest discover -s tests -v` → PASS.

- [ ] **Step 5: Evaluate** (≈ 200–300 KRW, `--fresh-intents` because the prompt changed): `uv run --env-file .env python -m backend.evaluate_natural --label stage2 --fresh-intents`. Compare with baseline; if overall Hit@5 dropped, adjust the Task 3 weights (re-runs reuse cached intents, ≈ 0 KRW for extraction) and record the final values in the commit message.

- [ ] **Step 6: Commit** `git add backend/natural_search.py tests/test_natural_search.py data/natural_eval_results/stage2.json && git commit -m "feat(search): show one game per series in natural search"`

---

## Stage 3 — Game profiles

### Task 5: Profile builder (pilot, then full run)

**Files:**
- Modify: `backend/gemini.py`, `tests/gemini_fake.py`
- Create: `backend/build_game_profiles.py`, `data/game_profiles.json` (generated)
- Test: `tests/test_game_profiles.py`

**Interfaces:**
- Produces:
  - `gemini.GameProfile` frozen dataclass: `bgg_id: int`, `profile: str`, `franchise: tuple[str, ...]`, `base_game: str | None`, `designers: tuple[str, ...]`, `designer_countries: tuple[str, ...]`.
  - `GeminiClient.write_profiles(self, games: Sequence[dict]) -> list[GameProfile]` (Protocol, Google client with `PROFILE_MODEL`, structured JSON, no tools); fake returns a deterministic profile per input.
  - `build_game_profiles.profile_input(idx: int) -> dict` (name, year, mechanics, themes, categories, weight, age, players, playtime, description first 800 chars); `clean_profile(p: GameProfile) -> GameProfile | None` (drop if profile < 40 or > 200 words or has Hangul; trim lists to 5 items, ≤ 60 chars each; `base_game` equal to own name → None); `build(ids: list[int], out: Path, batch: int = 10, limit: int | None = None)` resumable (skips ids already in `out`, saves after each batch, retries ×5 with backoff).
  - File format: `{"model": str, "created": str, "profiles": {"<BGGId>": {profile fields}}}`.
  - CLI: `uv run --env-file .env python -m backend.build_game_profiles [--limit N] [--sample]` — games with ≥ 1000 reviews, most reviewed first; `--sample` picks the pilot set (25 most-reviewed + 25 from the 1,000–3,000-review band, fixed seed).

- [ ] **Step 1: Write the failing tests** (`tests/test_game_profiles.py`, fake client):
  - `test_profile_input_fields`: keys present, description ≤ 800 chars.
  - `test_clean_profile_rules`: Hangul profile → `None`; 10-word profile → `None`; 8 designers → 5; `base_game == own name` → `None` base.
  - `test_build_resumes`: build 3 ids with `limit=2` → file has 2; build again → 3, fake called only for the missing one.
  - `test_build_skips_bad_batch_items`: fake returns one profile with an unknown `bgg_id` → ignored.
  - `test_gemini.py::test_profiles_parsing`: response dict → `list[GameProfile]`; missing `profile` → item skipped.

- [ ] **Step 2: Run** `uv run python -m unittest tests.test_game_profiles tests.test_gemini -v` → FAIL.

- [ ] **Step 3: Implement** `GameProfile`, `write_profiles` (prompt rules: English; 60–120-word profile covering who it suits — ages, families, couples, parties, experienced players — occasions, mood, interaction, learning curve and how a session feels; never contradict the given data; leave a field empty when not sure; `base_game` only when this game is a version/sequel/spin-off of another game), the fake, and the builder.

- [ ] **Step 4: Run** `uv run python -m unittest discover -s tests -v` → PASS.

- [ ] **Step 5: Pilot** (≈ 30 KRW): `uv run --env-file .env python -m backend.build_game_profiles --sample --limit 50`. Print 20 of them (name + profile + franchise + base_game + designers + countries) for the user.

- [ ] **Step 6: Stop for user review of the pilot.** If the user finds many wrong facts, switch `PROFILE_MODEL` to a larger model only after telling the user its price, regenerate the pilot, and review again.

- [ ] **Step 7: Full run** (≈ 900–2,000 KRW; tell the user the estimate first): `uv run --env-file .env python -m backend.build_game_profiles` → ~2,906 profiles; report how many were dropped by `clean_profile`.

- [ ] **Step 8: Commit** `git add backend/gemini.py backend/build_game_profiles.py tests/ data/game_profiles.json && git commit -m "feat(search): generate play-experience profiles for candidate games"`

### Task 6: Profile embeddings and metadata in search + stage 3 evaluation

**Files:**
- Create: `backend/build_profile_embeddings.py`, `data/profile_embeddings.npz` (generated), `backend/profiles.py`
- Modify: `backend/natural_search.py`, `backend/series.py` (call `set_keys` at load), `docs/setup.md`
- Test: `tests/test_profiles.py`, `tests/test_natural_search.py`
- Create: `data/natural_eval_results/stage3.json` (generated)

**Interfaces:**
- Consumes: `GameProfile` file (Task 5), `series_keys(..., base_games)` (Task 1), `keyword_hits` (Task 3).
- Produces:
  - `profiles.load(path=DATA_DIR / "game_profiles.json") -> dict[int, dict]` (empty dict when missing/broken); `profiles.PROFILES`.
  - `build_profile_embeddings` writes `data/profile_embeddings.npz` with `ids`, `vectors` (float16), `model_name`, `dim`, `doc_version = 1`; document = `gemini.document_text(name, f"{profile} Mechanics: … Themes: … {description[:600]}")`; same retry/partial-save pattern as `build_gemini_embeddings.py`.
  - `natural_search.load_index` merges: rows with a profile vector use it, others keep the old vector (`GeminiIndex` unchanged in shape). Constant `USE_PROFILE_VECTORS = True`.
  - `keyword_hits` also matches `franchise`, `designers`, `designer_countries` (whole words, so "Korea" hits "South Korea"). A keyword that hits metadata for ≥ 1 candidate becomes a **hard filter** (metadata or name/description hit required); otherwise stays a tag.
  - At import, `series.set_keys(series_keys(eng.df, MIN_REVIEWS, base_games={id: p["base_game"] for p if base_game}))`.

- [ ] **Step 1: Write the failing tests:**
  - `test_profiles.py::test_load_missing_file_is_empty`, `test_load_reads_profiles`.
  - `test_natural_search.py::test_profile_vector_preferred`: index built from a temp profile npz where one game's profile vector equals the query vector → that game first; with the file missing → old behavior.
  - `test_metadata_keyword_is_hard_filter`: patch `profiles.PROFILES` so two pool games have `designer_countries=("South Korea",)`; `keywords=("Korea",)` → every result is one of them or has "Korea" in name/description.
  - `test_metadata_keyword_without_hits_is_soft`: `keywords=("Nowhereland",)` relevance query → still 5 results.
  - `test_base_game_joins_series` (via `series.set_keys` with a patched base game) → those two never appear together.

- [ ] **Step 2: Run** `uv run python -m unittest tests.test_profiles tests.test_natural_search -v` → FAIL.

- [ ] **Step 3: Implement** `profiles.py`, the embedding builder, the index merge, metadata keyword matching, and series refresh.

- [ ] **Step 4: Run** `uv run python -m unittest discover -s tests -v` → PASS.

- [ ] **Step 5: Build embeddings** (≈ 400 KRW): `uv run --env-file .env python -m backend.build_profile_embeddings` → file has one vector per profile.

- [ ] **Step 6: Evaluate** (cached intents; ≈ 50 KRW for new query vectors only if `search_text` changed): `--label stage3`. If overall Hit@5 or Recall@25 is below stage 2, set `USE_PROFILE_VECTORS = False`, re-run, and keep the better (metadata keywords stay on either way). Record the choice in the commit.

- [ ] **Step 7: Docs** — `docs/setup.md`: building profiles and profile embeddings, costs, pilot review.

- [ ] **Step 8: Commit** `git add backend/profiles.py backend/build_profile_embeddings.py backend/natural_search.py backend/series.py tests/ data/profile_embeddings.npz data/natural_eval_results/stage3.json docs/setup.md && git commit -m "feat(search): search with game profiles and their franchise/designer metadata"`

---

## Stage 4 — Re-ranking

### Task 7: Gemini re-rank call

**Files:**
- Modify: `backend/gemini.py`, `tests/gemini_fake.py`
- Create: `backend/rerank.py`
- Test: `tests/test_rerank.py`, `tests/test_gemini.py`

**Interfaces:**
- Produces:
  - `gemini.RerankResult(interpretation: str, ranked_ids: tuple[int, ...], weak_match: bool)` frozen dataclass; `GeminiClient.rerank(self, query: str, games: Sequence[dict]) -> RerankResult`; `GoogleGeminiClient._generate(..., timeout_seconds: int = TIMEOUT_SECONDS)`; constants `RERANK_MODEL`, `RERANK_TIMEOUT_SECONDS = 5`, `RERANK_MAX_TOKENS = 1024`.
  - `FakeGeminiClient(rerank_result=None, rerank_error=None)`; records `("rerank", query, games)`; default result ranks the given games in order, `"Read as: fake."`, `weak_match=False`.
  - `rerank.rerank_facts(idx: int, web_ids: frozenset[int] = frozenset()) -> dict`: `bgg_id, name, year, mechanics, themes, categories, weight, age, players, good_players, playtime, reviews, rating, profile` (profile text, or description first 150 chars when no profile), plus `web_mentioned: bool` when `web_ids` is non-empty.
  - `rerank.rerank(query: str, cand_rows: list[int], web_ids: frozenset[int] = frozenset()) -> RerankResult`: `gemini.charge()`, call, clean (ids filtered to the rows' BGG ids, deduped, ≤ `RERANK_MAX_IDS = 20`; interpretation stripped, `"Read as: "` prefixed if missing, `""` if Hangul or > 200 chars). Raises `GeminiError` on failure.

- [ ] **Step 1: Write the failing tests:** `test_gemini.py::test_rerank_result_parsing` (`{"interpretation": "Read as: x", "ranked_ids": [3, "4"], "weak_match": true}` → `RerankResult("Read as: x", (3, 4), True)`; missing ids → `GeminiError`); `test_rerank.py`: `test_facts_fields` (profile used when present, 150-char description otherwise), `test_filters_unknown_and_duplicate_ids`, `test_caps_at_max_ids` (30 → 20), `test_interpretation_cleaned`, `test_charges_budget_and_propagates_errors`.

- [ ] **Step 2: Run** `uv run python -m unittest tests.test_rerank tests.test_gemini -v` → FAIL.

- [ ] **Step 3: Implement** (prompt rules: order by fit to the request, omit poor fits, ≤ 20 ids; one English sentence starting "Read as:" on how the request was understood, no game names; `weak_match` true when fewer than 3 games fit well; judge only from the given facts).

- [ ] **Step 4: Run** `uv run python -m unittest discover -s tests -v` → PASS.

- [ ] **Step 5: Smoke check** (≈ 5 KRW, not committed): `rerank.rerank("할머니, 할아버지와 함께하기 좋은 게임", <25 candidate rows>)` → ≥ 5 ids, English interpretation, < 5 s.

- [ ] **Step 6: Commit** `git add backend/gemini.py backend/rerank.py tests/ && git commit -m "feat(search): add Gemini re-rank call"`

### Task 8: Re-ranked search, interpretation, weak match, API shape

**Files:**
- Modify: `backend/natural_search.py`, `backend/evaluate_natural.py`, `backend/main.py` (`search_natural`)
- Test: `tests/test_natural_search.py`, `tests/test_evaluate_natural.py`, `tests/test_natural_api.py`

**Interfaces:**
- Consumes: `rerank.rerank` (Task 7), `group_series` (Task 4).
- Produces:
  - `NaturalResult` dataclass: `games: list[dict]`, `interpretation: str | None`, `weak_match: bool`, `shortlist_ids: list[int]`, `web: dict | None` (always `None` until Task 11).
  - `natural_search(...) -> NaturalResult`.
  - `_rerank_cache = _LRU()` keyed `(query.strip().lower(), players, max_time)`, cleared by `clear_caches()`.
  - `POST /search/natural` → `{"games", "interpretation", "weak_match", "web"}`; empty `games` → 404.

- [ ] **Step 1: Write the failing tests** (fake client): `test_rerank_order_is_used`; `test_pads_to_five_and_flags_weak` (2 ranked → 5 games, `weak_match`); `test_model_weak_flag_passes_through`; `test_dedupes_series_in_rerank_output`; `test_refresh_uses_cache` (page 2 = ranked 6–10, one `rerank` call total); `test_refresh_cache_miss_calls_again_without_storing`; `test_rerank_failure_falls_back` (`interpretation is None`, `weak_match is False`); `test_ranking_query_skips_rerank` (fixed copy); `test_exhausted_candidates_returns_empty` (no id twice across pages); `test_natural_api.py::test_search_returns_object` and existing API tests read `body["games"]`; `test_evaluate_natural.py`: Recall uses `shortlist_ids`, weak-match rate numeric.

- [ ] **Step 2: Run** the three test modules → FAIL.

- [ ] **Step 3: Implement** — relevance: score → `group_series` → `ordered` → `shortlist = ordered[:SHORTLIST_SIZE]` → cache or `rerank.rerank` (store only when `exclude_ids` is empty) → page = ranked ids still among candidates + remaining `ordered`, `top_n`; `weak_match = result.weak_match or any padded game on the page`; on `GeminiError` → `diversify` over `ordered`, `interpretation=None`. Ranking path: Task 4 behavior + fixed copy; `shortlist_ids` = first 25 sorted. Update `evaluate_natural.run` and `main.search_natural`.

- [ ] **Step 4: Run** `uv run python -m unittest discover -s tests -v` → PASS.

- [ ] **Step 5: Commit** `git add backend/natural_search.py backend/evaluate_natural.py backend/main.py tests/ && git commit -m "feat(search): re-rank natural search with Gemini and report interpretation"`

### Task 9: Weak-match-aware reasons

**Files:**
- Modify: `backend/main.py` (`ExplainRequest`, `explain`), `backend/explain.py`, `backend/gemini.py` (`explain`, `MODE_RULES`), `tests/gemini_fake.py`, `docs/backend_api.md`
- Test: `tests/test_explain.py`, `tests/test_natural_api.py`

**Interfaces:**
- Produces: `ExplainRequest.weak_match: bool = False`; `explain_games(mode, basis, game_ids, weak_match: bool = False)`; cache key `(mode, basis_key, weak_match, bgg_id)`; `GeminiClient.explain(..., weak_match: bool = False)`; when true the prompt adds "These games are only the nearest matches; do not claim they fully deliver the request. Say which aspect comes closest."

- [ ] **Step 1: Write the failing tests:** `test_weak_match_reaches_client_and_cache` (true reaches fake; a false call afterwards calls the client again); `POST /explain` with `"weak_match": true` → 200.
- [ ] **Step 2: Run** `uv run python -m unittest tests.test_explain tests.test_natural_api -v` → FAIL.
- [ ] **Step 3: Implement**; document both endpoint changes (search object shape incl. `web`, explain `weak_match`) in `docs/backend_api.md`.
- [ ] **Step 4: Run** `uv run python -m unittest discover -s tests -v` → PASS.
- [ ] **Step 5: Commit** `git add backend/ tests/ docs/backend_api.md && git commit -m "feat(api): soften reasons for weak matches"`

### Task 10: Frontend interpretation and weak-match notice + stage 4 evaluation

**Files:**
- Modify: `frontend/src/types.ts`, `frontend/src/api.ts`, `frontend/src/components/DescriptionSearch.tsx`, `.github/workflows/deploy-backend.yml`, `docs/recommendation_pipeline.md`, `docs/deploy.md`
- Create: `data/natural_eval_results/stage4.json` (generated)

**Interfaces:**
- Produces: `NaturalSearchResponse { games: NaturalGame[]; interpretation: string | null; weak_match: boolean; web: WebResult | null }`, `WebResult { summary: string; suggestions_html: string }` (rendered in Task 12); `ExplainRequest.weak_match?: boolean`; `naturalSearch(...) -> Promise<NaturalSearchResponse>`.

- [ ] **Step 1: Types and API** updated.
- [ ] **Step 2: `DescriptionSearch`**: read `search.data.games` everywhere results were used (list, `shownIds`, explain ids, "newest" note); pass `weak_match` to explain; render `interpretation` under the summary line (`text-[15px] text-ink/70`); render the weak-match notice (same box classes as the "newest" note) above results.
- [ ] **Step 3: Run** `cd frontend && npm run typecheck && npm run lint` → clean.
- [ ] **Step 4: Deploy limit** — add `GEMINI_DAILY_CALL_LIMIT=300` to the `--set-env-vars` list in `deploy-backend.yml` (keep existing vars); note it and Google budget alerts in `docs/deploy.md`.
- [ ] **Step 5: Evaluate** (≈ 300 KRW): `--label stage4`. Overall Hit@5 ≥ stage 3 and duplicate rate 0; if not, try `SHORTLIST_SIZE` 15 or 40 once and keep the better. Record in `docs/recommendation_pipeline.md` (pipeline stages, weights, table baseline/stage2/stage3/stage4 per type).
- [ ] **Step 6: Check in the app** (backend with key + `npm run dev`): grandparents query shows interpretation + 5 cards with reasons; "동물들도 이해하기 쉬운 게임" shows the weak-match notice; "가장 유명한 게임" shows "Ranked by number of BGG reviews."; Refresh gives 5 new, no series repeated on a page.
- [ ] **Step 7: Commit** `git add frontend/src .github/workflows/deploy-backend.yml docs/ data/natural_eval_results/stage4.json && git commit -m "feat(frontend): show search interpretation and weak-match notice"`

---

## Stage 5 — Live web search for questions that need it

### Task 11: Web search backend

**Files:**
- Modify: `backend/gemini.py`, `backend/natural_search.py`, `backend/limits.py` (reuse `DailyBudget`), `tests/gemini_fake.py`
- Create: `backend/web_search.py`
- Test: `tests/test_web_search.py`, `tests/test_natural_search.py`

**Interfaces:**
- Produces:
  - `QueryIntent.needs_web: bool = False` (schema BOOLEAN; prompt: true only when the request depends on facts that game descriptions and general game knowledge don't hold — awards, designer nationality, a specific publisher, popularity in a specific country or community; false for genre, mood, audience and ranking requests).
  - `gemini.WebAnswer(text: str, suggestions_html: str, search_count: int)`; `GeminiClient.web_search(self, query: str) -> WebAnswer` (`WEB_MODEL`, Google Search tool, **no response schema**, `WEB_TIMEOUT_SECONDS = 8`; prompt asks for official English board game names one per line, at most 15, then a one–two sentence summary; `suggestions_html` from the response's search entry point, `search_count` from its web search queries).
  - `web_search.web_budget = limits.DailyBudget(int(os.environ.get("WEB_SEARCH_DAILY_LIMIT", "100")))`.
  - `web_search.match_names(text: str) -> frozenset[int]` (pool BGG ids whose normalized Name, or Name before ":", equals a normalized line of `text`).
  - `web_search.lookup(query: str) -> tuple[frozenset[int], dict] | None` — `None` when the budget is spent or on `GeminiError`; else `(ids, {"summary": <summary part of text>, "suggestions_html": ...})`; spends `max(1, search_count)` from `web_budget`. Holds nothing after returning.
  - In `natural_search`: when `intent.needs_web`, call `lookup`; web ids count as an include tag; if ≥ 5 web ids pass the filters they are a hard filter, else a tag; pass `web_ids` to `rerank.rerank`; **skip `_rerank_cache` read and write** for this query; `NaturalResult.web` = the dict or `None`.

- [ ] **Step 1: Write the failing tests:**
  - `test_web_search.py`: `test_match_names` ("Catan\nPandemic Legacy: Season 1\nNot A Game" → their ids); `test_budget_spent_returns_none`; `test_error_returns_none`; `test_spends_search_count` (fake `search_count=3` → budget down by 3).
  - `test_natural_search.py`: `test_no_web_call_without_needs_web`; `test_web_ids_hard_filter_when_five_or_more`; `test_web_ids_soft_when_fewer`; `test_web_result_attached` (`result.web["suggestions_html"]` equals the fake's); `test_web_query_never_cached` (two identical `needs_web` calls → `web_search` and `rerank` each called twice; `_rerank_cache` has no entry for the query); `test_web_failure_falls_back` (`web is None`, 5 games).
  - `test_gemini.py::test_web_answer_parsing` from a stubbed SDK response object (text, entry-point HTML, query count).

- [ ] **Step 2: Run** `uv run python -m unittest tests.test_web_search tests.test_natural_search tests.test_gemini -v` → FAIL.

- [ ] **Step 3: Implement.** No logging of web text or ids anywhere.

- [ ] **Step 4: Run** `uv run python -m unittest discover -s tests -v` → PASS.

- [ ] **Step 5: Smoke check** (free tier, not committed, nothing saved): `web_search.lookup("Spiel des Jahres winners")` → some matched ids, non-empty `suggestions_html`, < 8 s. If `WEB_MODEL` rejects the search tool, tell the user and propose the cheapest model that accepts it.

- [ ] **Step 6: Commit** `git add backend/ tests/ && git commit -m "feat(search): live web search for questions that need outside facts"`

### Task 12: Web box in the frontend + docs

**Files:**
- Create: `frontend/src/components/WebResultBox.tsx`
- Modify: `frontend/src/components/DescriptionSearch.tsx`, `docs/recommendation_pipeline.md`, `docs/backend_api.md`, `docs/setup.md`, `docs/deploy.md`, `.github/workflows/deploy-backend.yml`

**Interfaces:**
- Consumes: `WebResult` (Task 10 types).
- Produces: `WebResultBox({ web }: { web: WebResult })` — heading "From the web", `web.summary` as text, then `<iframe sandbox="allow-popups allow-popups-to-escape-sandbox" srcDoc={web.suggestions_html} title="Google search suggestions">` sized to fit (no edits to the HTML).

- [ ] **Step 1: Implement `WebResultBox`** (card styling from existing tokens) and render it in `DescriptionSearch` above the results when `search.data.web` is non-null.
- [ ] **Step 2: Run** `cd frontend && npm run typecheck && npm run lint` → clean.
- [ ] **Step 3: Docs and deploy** — `WEB_SEARCH_DAILY_LIMIT=100` in `deploy-backend.yml`; `docs/deploy.md`: the terms summary (no caching/storing, show suggestions, Google keeps 30 days) and "read the full terms before deploying"; `docs/setup.md`: env var; `docs/backend_api.md`: `web` field; `docs/recommendation_pipeline.md`: stage 5 flow and why it is not in the automated evaluation.
- [ ] **Step 4: Stop for the user** — ask them to read the [Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms) grounding section and confirm before this stage is merged/deployed.
- [ ] **Step 5: Manual check in the app** (free tier): "Spiel des Jahres winners" and "한국인이 만든 보드게임" show the web box with suggestions and matching cards; Refresh on such a query works; "전쟁 게임" shows no web box. Nothing about these results is written to files.
- [ ] **Step 6: Commit** `git add frontend/src docs/ .github/workflows/deploy-backend.yml && git commit -m "feat(frontend): show web search summary with Google search suggestions"`
