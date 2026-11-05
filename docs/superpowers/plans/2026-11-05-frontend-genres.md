# 제목 변경 · 상세 모달 · 장르별 둘러보기 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 시작 화면 제목을 바꾸고, 추천 결과 상세 모달과 장르별 대표 게임 둘러보기를 추가한다.

**Architecture:** 백엔드에 `backend/genres.py`(서버 시작 시 장르별 상위 게임 계산)와 `GET /genres`를 추가한다. 프론트는 `App.jsx`를 화면·컴포넌트 파일로 나누고, 공용 `GameDetailModal`(기존 `GET /games/{id}` 사용)을 추천 화면과 장르 화면에서 함께 쓴다.

**Tech Stack:** FastAPI, pandas, unittest(TestClient) / React 19, Vite, Tailwind v4, axios, lucide-react

**Spec:** `docs/superpowers/specs/2026-11-05-frontend-genres-design.md`

## Global Constraints

- 게임 이름·설명은 영어 원문 그대로 보여준다. 번역은 하지 않는다. 화면 문구는 한글로 쓴다.
- 장르 label은 "전략", "가족", "파티", "테마", "워게임", "어린이", "카드게임", "추리" (전략에 "(추상 포함)"을 붙이지 않는다).
- 장르 대상: `NumUserRatings >= 1000`, 정렬: `BayesAvgRating` 내림차순, 장르당 최대 6개.
- 색은 `index.css`의 `@theme` 토큰(page, card, line, primary, primary-dark, ink, danger)만 사용한다.
- 기존 코드처럼 초보자도 읽을 수 있는 한글 주석을 단다.
- 커밋: 사용자 요청에 따라 기존 미커밋 변경과 함께 **마지막에 `main`에 한 번** 커밋한다(태스크별 커밋 없음).

## Review Focus

1. 설명(Description)이 빈 문자열인 게임 → 모달에 "설명이 없습니다"를 보여주고 오류 없이 렌더링한다.
2. 설명에 `&amp;quot;`처럼 이중 인코딩된 엔티티나 `<b>` 같은 문자열 → HTML로 렌더링하지 않고 텍스트로만 보여준다(XSS 없음).
3. `BestPlayers`가 0/NaN이거나 `ComMinPlaytime`이 0 → "최적 인원" 생략, "시간 정보 없음" 표시. 상세 API가 NaN 때문에 500을 내지 않는다.
4. 모달이 열린 상태에서 다른 게임을 빠르게 연달아 열기 → 늦게 도착한 이전 응답이 새 게임 정보를 덮지 않는다(AbortController).
5. 모달에서 "비슷한 게임 추천받기"로 추천 화면에 갔을 때 → 검색창에 게임 이름이 채워지고 바로 "추천받기"를 누를 수 있다. 인원·시간은 기본값이다.

---

### Task 1: 백엔드 `GET /genres`

**Files:**
- Create: `backend/genres.py`
- Modify: `backend/main.py` (import, 엔드포인트), `docs/backend_api.md` (엔드포인트 설명 추가)
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `recommend_engine.df`(이미 `Cat:*` 컬럼이 붙어 있음), `recommend_engine.mechanics: BinaryFeatures`(`names`, `binary`가 `df` 행 순서와 같음)
- Produces:
  - `GENRES: list[dict]` — 각 항목 `{"key", "label", "description"}`, 순서 strategy, family, party, thematic, war, childrens, cgs, deduction
  - `genre_mask(df: pd.DataFrame, mechanics: BinaryFeatures, key: str) -> np.ndarray[bool]`
  - `build_genres(df, mechanics, limit: int = 6, min_ratings: int = 1000) -> list[dict]` — 각 항목에 `games: list[dict]` 추가. 게임 필드: `BGGId, Name, YearPublished, ImagePath, GameWeight, ComMinPlaytime, ComMaxPlaytime, BayesAvgRating`
  - `GET /genres` → `build_genres` 결과(서버 시작 시 1회 계산해 둔 값)

- [ ] **Step 1: 실패하는 테스트 작성** (`tests/test_api.py`에 추가)

```python
GENRE_KEYS = ["strategy", "family", "party", "thematic", "war", "childrens", "cgs", "deduction"]

def test_genres_lists_eight_genres_in_order(self):
    response = self.client.get("/genres")
    self.assertEqual(response.status_code, 200)
    genres = response.json()
    self.assertEqual([g["key"] for g in genres], GENRE_KEYS)
    self.assertEqual(genres[0]["label"], "전략")
    for genre in genres:
        self.assertTrue(genre["label"] and genre["description"])

def test_genre_games_are_popular_sorted_and_limited(self):
    for genre in self.client.get("/genres").json():
        with self.subTest(genre=genre["key"]):
            games = genre["games"]
            self.assertTrue(0 < len(games) <= 6)
            ratings = [g["BayesAvgRating"] for g in games]
            self.assertEqual(ratings, sorted(ratings, reverse=True))
            ids = [g["BGGId"] for g in games]
            self.assertTrue(all(df.loc[df["BGGId"] == i, "NumUserRatings"].iloc[0] >= 1000 for i in ids))

def test_strategy_genre_includes_abstract_games(self):
    mask = genre_mask(df, mechanics, "strategy")
    abstract_only = (df["Cat:Abstract"] == 1) & (df["Cat:Strategy"] == 0)
    self.assertTrue(abstract_only.any())
    self.assertTrue(mask[abstract_only.to_numpy()].all())

def test_deduction_genre_uses_deduction_mechanic(self):
    col = list(mechanics.names).index("Deduction")
    expected = mechanics.binary[:, col].toarray().ravel() > 0
    self.assertTrue((genre_mask(df, mechanics, "deduction") == expected).all())
```

필요한 import: `from backend.genres import genre_mask`, `from backend.recommend_engine import df, mechanics`.

- [ ] **Step 2: 실패 확인**

Run: `uv run python -m unittest tests.test_api -v`
Expected: `ModuleNotFoundError: backend.genres` 또는 `/genres` 404로 FAIL

- [ ] **Step 3: `backend/genres.py` 구현**

`genre_mask`: `strategy`는 `(Cat:Strategy == 1) | (Cat:Abstract == 1)`, `deduction`은 `mechanics`의 `Deduction` 열 > 0, 나머지는 `GENRE_CATEGORY = {"family": "Cat:Family", "party": "Cat:Party", "thematic": "Cat:Thematic", "war": "Cat:War", "childrens": "Cat:Childrens", "cgs": "Cat:CGS"}` 컬럼 == 1. 모르는 key는 `ValueError`.
`build_genres`: 마스크 & `NumUserRatings >= min_ratings`로 거르고 `BayesAvgRating` 내림차순 정렬 후 `head(limit)`를 `to_dict(orient="records")`.
설명 문구는 스펙 표의 문구를 그대로 쓴다. `main.py`와 같은 `try/except ImportError` import 패턴을 따른다.

- [ ] **Step 4: `backend/main.py`에 엔드포인트 추가**

모듈 로드 시 `GENRE_LIST = build_genres(df, mechanics)`를 계산하고 `@app.get("/genres")`에서 반환. `mechanics`를 `recommend_engine`에서 import에 추가.
상세 API(`get_game_detail`)가 `BestPlayers` 등의 NaN 때문에 500을 내지 않도록, 반환 직전에 NaN을 `None`으로 바꾼다(Review Focus 3). 테스트 추가: `NumUserRatings`가 가장 많은 게임 하나와 `BestPlayers`가 NaN인 게임 하나(있으면)에 대해 `/games/{id}`가 200을 반환하는지 확인.

- [ ] **Step 5: 테스트 통과 확인**

Run: `uv run python -m unittest discover -s tests -v`
Expected: 전부 OK

- [ ] **Step 6: `docs/backend_api.md`에 `GET /genres` 요청·응답 예시 추가**

---

### Task 2: `App.jsx` 파일 분리 + 제목 변경

동작은 그대로 두고 구조만 바꾼다(제목 변경만 예외).

**Files:**
- Create: `frontend/src/api.js`, `frontend/src/format.js`, `frontend/src/screens/StartScreen.jsx`, `frontend/src/screens/RecommendScreen.jsx`, `frontend/src/components/GameSearch.jsx`, `frontend/src/components/OptionGroup.jsx`, `frontend/src/components/GameThumb.jsx`
- Modify: `frontend/src/App.jsx`(화면 전환만 남김), `frontend/index.html`

**Interfaces:**
- Produces:
  - `api.js`: `searchGames(query, signal) -> Promise<Game[]>`, `recommend({game_name, players, max_time}) -> Promise<Game[]>`, `getGameDetail(bggId, signal) -> Promise<GameDetail>`, `getGenres() -> Promise<Genre[]>`. 모두 axios 응답의 `data`를 돌려주고, 오류는 axios 오류를 그대로 던진다(기존 상태 코드 분기 유지). 타임아웃 15000.
  - `format.js`: `formatMinutes(min)`, `withWa(word)`, `formatPlaytime(game) -> string`(기존 `GameRow`의 시간 로직), `decodeEntities(text) -> string`(`DOMParser`로 `text/html` 파싱 후 `textContent`, 반복 디코딩은 하지 않음)
  - `GameThumb({ src, className, iconClassName })`: 이미지, 없거나 실패하면 `Dices` 아이콘
  - `GameSearch({ value, onChange, disabled })`: `value`가 바깥에서 주어지면 입력창 `query`를 그 값으로 초기화한다(`useState(value)`)

- [ ] **Step 1: 위 파일로 코드 이동**, 각 파일 상단에 역할 주석
- [ ] **Step 2: 제목 변경** — `StartScreen` `h1`을 `Boardgame Recommender`로, `index.html` `<title>`을 `Boardgame Recommender`로
- [ ] **Step 3: 확인**

Run: `cd frontend && npm run lint && npm run build`
Expected: lint 경고/오류 0, build 성공

---

### Task 3: 상세 모달 + 추천 결과 클릭

**Files:**
- Create: `frontend/src/components/GameDetailModal.jsx`
- Modify: `frontend/src/screens/RecommendScreen.jsx`, `frontend/src/App.jsx`

**Interfaces:**
- Consumes: `getGameDetail`, `decodeEntities`, `formatPlaytime`, `GameThumb`
- Produces:
  - `GameDetailModal({ bggId, onClose, onRecommendSimilar })` — `bggId`가 null이면 렌더링하지 않는다. `onRecommendSimilar(name: string)`
  - `App` 상태: `screen`(`"start" | "recommend" | "genres"`), `initialGame: string`. `openRecommend(name = "")`가 `initialGame`을 바꾸고 화면을 `recommend`로 전환한다. `RecommendScreen`에는 `key={initialGame}`과 `initialGame`을 넘겨서, 게임이 바뀌면 화면 상태를 새로 초기화한다.

- [ ] **Step 1: `GameDetailModal` 구현**

`<dialog>` + `useEffect`에서 `showModal()`. 닫기: X 버튼, `cancel` 이벤트(ESC), 바깥 클릭(`event.target === dialog`). `bggId`가 바뀌면 이전 요청을 abort한다(Review Focus 4).
항목: 이미지, 이름 + `(연도)`(0 초과일 때), 인원 `Min~Max명`(같으면 `N명`), `BestPlayers > 0`이면 `최적 N명`, `formatPlaytime`, `난이도 x.x / 5`, `평점 x.x (리뷰 N개)`.
설명은 `decodeEntities` 결과를 `whitespace-pre-line`인 `<p>`에 텍스트로 넣고, 비어 있으면 "설명이 없습니다"(Review Focus 1·2). `dangerouslySetInnerHTML`는 쓰지 않는다.
상태 문구: 로딩 "게임 정보를 불러오는 중...", 404 "게임을 찾을 수 없습니다.", 그 외 "게임 정보를 불러오지 못했습니다." + "다시 시도" 버튼.
하단 버튼: "이 게임과 비슷한 게임 추천받기" → `onRecommendSimilar(detail.Name)`.

- [ ] **Step 2: 추천 결과 연결** — `GameRow` 내용을 `<button>`으로 감싸고(`aria-haspopup="dialog"`), 누르면 `RecommendScreen`의 `selectedId`를 설정한다. `RecommendScreen`은 `onRecommendSimilar`를 prop으로 받아 모달에 넘긴다.
- [ ] **Step 3: 확인** — `npm run lint && npm run build` 통과. 앱을 실행해 Catan 4명 90분 추천 → 결과 클릭 → 모달 내용, ESC/바깥 클릭/X로 닫기, "비슷한 게임 추천받기" → 검색창에 이름이 채워지고 추천받기 활성화(Review Focus 5).

---

### Task 4: 장르 화면 + 시작 화면 버튼

**Files:**
- Create: `frontend/src/screens/GenreScreen.jsx`
- Modify: `frontend/src/screens/StartScreen.jsx`, `frontend/src/App.jsx`

**Interfaces:**
- Consumes: `getGenres`, `GameDetailModal`, `GameThumb`, `formatPlaytime`
- Produces: `GenreScreen({ onBack, onRecommendSimilar })`, `StartScreen({ onStart, onBrowse })`

- [ ] **Step 1: 시작 화면** — 기존 "시작하기" 버튼을 "비슷한 게임 추천받기"(`onStart`, 진한 버튼)로 바꾸고, 옆에 "장르별로 둘러보기"(`onBrowse`, 테두리 버튼, `LayoutGrid` 아이콘)를 둔다. 좁은 화면에서는 세로로 쌓는다.
- [ ] **Step 2: `GenreScreen`** — 마운트 시 `getGenres()` 1회 호출. 상태: 로딩, 에러("장르 정보를 불러오지 못했습니다." + 다시 시도), 성공. 첫 장르(strategy)를 선택한 상태로 시작한다. 장르 칩(`aria-pressed`, `OptionGroup`과 같은 선택 스타일), 선택한 장르의 `description`, 카드 그리드 `grid-cols-2 sm:grid-cols-3`. 카드는 버튼이고 정사각 `GameThumb`, 이름(2줄까지 자름), 시간·난이도를 넣는다. 누르면 `GameDetailModal`을 연다.
- [ ] **Step 3: `App` 연결** — `screen === "genres"`일 때 `GenreScreen`, `onRecommendSimilar={openRecommend}`.
- [ ] **Step 4: 확인** — `npm run lint && npm run build` 통과. 앱 실행: 시작 → 장르별로 둘러보기 → 8개 탭 전환(추가 요청 없음) → 카드 클릭 → 모달 → 비슷한 게임 추천받기 → 추천 화면에 이름이 채워짐. 백엔드를 끈 상태에서 에러와 다시 시도를 확인.

---

### Task 5: 최종 검증과 커밋

- [ ] **Step 1:** `uv run python -m unittest discover -s tests -v` 전부 OK, `cd frontend && npm run lint && npm run build` 성공
- [ ] **Step 2:** `README.md`에 장르 둘러보기와 상세 보기 기능을 한 줄씩 추가
- [ ] **Step 3:** `git status`로 커밋 대상 확인. 기존 미커밋 변경(백엔드 추천 파이프라인, `data/mechanics.csv`, `data/themes.csv`, docs)과 이번 작업을 함께 `main`에 한 번 커밋한다. `.gitignore`가 막는 `data/*.npz`, `data/user_ratings.csv`, `*.joblib`는 포함하지 않는다.
