# 백엔드 API 실행·연동·검증 가이드

모든 명령어는 `pyproject.toml`이 있는 프로젝트 최상위 폴더에서 실행
(실제 `data/clean_games.csv`와 `backend/recommend_engine.py`를 사용)

## 1. 설치와 실행

```bash
uv sync --locked
uv run --locked uvicorn backend.main:app --reload --port 8000
```

- 서버 상태: http://localhost:8000/
- 클릭해서 요청을 보낼 수 있는 Swagger 문서: http://localhost:8000/docs
- 서버 종료: 실행한 터미널에서 `Ctrl+C`
- `.python-version`에 지정된 Python 3.12와 `uv.lock`의 패키지 버전을 사용함
- `data/embeddings.npz`가 있으면 시작 시 TF-IDF 계산을 건너뛰며, 임베딩이 없을 때만 첫 요청 시 TF-IDF 캐시를 생성함
- 추천 알고리즘과 선택 기능(임베딩, 협업 필터링, 평가) 준비 방법은 [recommendation_pipeline.md](recommendation_pipeline.md) 참고

## 2. 요청과 응답

| 메서드·경로 | 입력 | 성공 응답 |
| --- | --- | --- |
| `GET /` | 없음 | 서버 이름, `total_games`, 사용 중인 추천 신호 `signals`, `GET /games/semantic-search` 사용 가능 여부 `semantic_search`, Gemini 자연어 검색 가능 여부 `natural_search`, 설명 문장 가능 여부 `explanations` (모두 bool) |
| `GET /games/search` | 쿼리 `query` | 최대 10개 게임 목록. 이름이 정확히 같은 게임 → 검색어로 시작하는 게임 → 포함하는 게임 순, 같은 순위는 리뷰 수 순 |
| `GET /games/filter` | 쿼리 `players`, `max_time` | 조건을 만족하는 최대 10개 게임, 평점 내림차순 |
| `POST /recommend` | JSON `game_name`, `players`, `max_time`, 선택 `exclude_ids` | 조건을 만족하는 최대 5개 추천 게임 |
| `GET /games/semantic-search` | 쿼리 `query`, 선택 `players`, `max_time` | 자연어(한국어 가능) 설명에 맞는 최대 10개 게임. 임베딩 미준비 시 `503` |
| `POST /search/natural` | JSON `query`, `players`, `max_time`, 선택 `exclude_ids` | 검색어(한국어·영어)의 장르적 특성에 맞는 최대 5개 게임(리뷰 1,000개 이상, 평점 5.5 이상 중에서). 항목은 게임 필드와 `Similarity`, `Score`, `MatchedMechanics`, `MatchedThemes`. 키·임베딩이 없으면 `503` |
| `POST /explain` | JSON `mode`(`similar` 또는 `query`), `basis`, `game_ids` | `{"reasons": {"<BGGId>": "영어 한 문장"}}`. 키가 없으면 `503` |
| `GET /games/{bgg_id}` | 경로의 게임 ID(`BGGId`) | 게임 한 개의 상세 정보(설명, 난이도, 인원, 시간, 평점) |
| `GET /genres` | 없음 | 장르 8개와 장르별 대표 게임 최대 6개 |
| `GET /genres/{key}/games` | 경로의 장르 `key`, 선택 쿼리 `players`, `max_time`, `exclude_ids` | 조건(최소 평점 5.5, 인원·시간)에 맞는 장르 게임 최대 6개. 리뷰 1,000개 이상 게임 우선, 그 안에서 평점순. `exclude_ids`의 게임은 제외(`?exclude_ids=13&exclude_ids=822`처럼 여러 번 붙임). 없으면 빈 목록 |

게임 이름은 데이터에 저장된 영어 이름을 사용함. 검색 결과의 `Name`을 추천 요청의 `game_name`으로 전달하면 되며, 대소문자와 앞뒤 공백은 무시함.

### 게임 검색

```bash
curl 'http://localhost:8000/games/search?query=Catan'
```

- 검색 결과 항목의 필드: `BGGId`, `Name`, `YearPublished`, `ImagePath`
- 검색 결과가 없으면 `200`과 빈 배열 `[]`을 반환함.

### 조건 필터

```bash
curl 'http://localhost:8000/games/filter?players=4&max_time=90'
```

4명이 플레이할 수 있고 최대 시간이 90분 이내이며 평점이 5.5 이상인 게임을 반환함. 조건에 맞는 게임이 없으면 `200`과 `[]`을 반환함.

### 추천

```bash
curl -X POST 'http://localhost:8000/recommend' \
  -H 'Content-Type: application/json' \
  -d '{"game_name":"Catan","players":4,"max_time":90}'
```

`players`와 `max_time`은 1 이상의 정수이고, 시간 단위는 분.
`exclude_ids`(게임 ID 목록)를 보내면 그 게임들을 빼고 추천함. "다른 게임 5개 추천받기"에서 지금까지 보여준 게임 ID를 쌓아서 보내는 용도이며, 남은 후보가 없으면 `404`.
조건 필터를 통과한 게임을 하이브리드 유사도(메커니즘·테마·카테고리·텍스트·협업 필터링)와 평점을 합친 `Score`로 정렬한 뒤, 서로 너무 비슷한 게임이 몰리지 않게 다양성 재정렬하여 반환함. 기준 게임 자체는 제외하고, 같은 시리즈 변형판은 감점함. 자세한 내용은 [recommendation_pipeline.md](recommendation_pipeline.md).

추천 결과의 각 항목에는 다음 필드가 있으며, 대문자로 시작하는 키 이름을 그대로 사용함.

| 필드 | 의미 |
| --- | --- |
| `BGGId`, `Name` | 게임 ID와 이름 |
| `YearPublished`, `ImagePath` | 출시 연도와 이미지 주소. 이미지가 없으면 빈 문자열 |
| `GameWeight` | 난이도 |
| `MinPlayers`, `MaxPlayers` | 최소·최대 인원 |
| `ComMinPlaytime`, `ComMaxPlaytime` | 최소·최대 플레이 시간(분) |
| `BayesAvgRating`, `NumUserRatings` | 평점과 평가 수 |
| `Similarity` | 기준 게임과의 하이브리드 유사도(0\~1). 추천·자연어 검색 응답에만 포함 |
| `Score` | 유사도와 평점을 합친 최종 점수. 추천·자연어 검색 응답에만 포함 |
| `SharedMechanics`, `SharedThemes` | 기준 게임과 공통인 메커니즘·테마 (드문 것부터 최대 3개). 추천 응답에만 포함 |

### 자연어 검색 (Gemini)

```bash
curl -X POST 'http://localhost:8000/search/natural' \
  -H 'Content-Type: application/json' \
  -d '{"query":"친구들과 가볍게 하는 협력 게임","players":4,"max_time":60}'
```

- Gemini(`gemini-3.5-flash-lite`)가 검색어를 조건(포함·제외 메커니즘/테마, 난이도 범위, 영어 검색 문장)으로 바꾸고, `gemini-embedding-2`(768차원)로 만든 `data/gemini_embeddings.npz`와 비교함. 인원·시간은 요청 값만 사용함
- 응답은 추천과 같은 게임 필드에 `Similarity`, `Score`, `MatchedMechanics`, `MatchedThemes`(검색어에서 뽑은 태그 중 게임이 가진 것)를 더한 5개. `exclude_ids`로 이미 본 게임을 빼고 다시 받을 수 있음
- 검색어는 300자 이하. IP당 60초에 10회까지

### 설명 문장

```bash
curl -X POST 'http://localhost:8000/explain' \
  -H 'Content-Type: application/json' \
  -d '{"mode":"similar","basis":"Catan","game_ids":[822,13]}'
```

- `mode="similar"`는 `basis`를 기준 게임 이름으로, `mode="query"`는 사용자 검색어로 보고 각 게임이 왜 맞는지 영어 한 문장으로 설명함. 게임 정보(메커니즘·테마·난이도·인원·시간·설명글 앞부분)만 근거로 씀
- `basis`는 300자 이하, `game_ids`는 1~10개. IP당 60초에 30회까지
- 응답 예: `{"reasons": {"822": "One English sentence."}}`. 실패하면 화면은 설명 없이 공통 메커니즘 칩을 보여 줌
- Gemini 호출은 `GEMINI_DAILY_CALL_LIMIT`회(기본 2000, UTC 자정 초기화)로 제한하되, 카운터가 인스턴스 메모리에만 있어 인스턴스가 새로 시작되면 0으로 돌아가는 느슨한 안전장치임. 실제 하드 한도는 Google 쪽 쿼터·예산 알림으로 설정함 ([deploy.md](deploy.md) 참고). 같은 검색어·설명은 서버 메모리에 캐시함

### 장르별 대표 게임

```bash
curl 'http://localhost:8000/genres'
```

```json
[
  {
    "key": "strategy",
    "label": "Strategy",
    "description": "Deep planning and clever moves",
    "games": [{"BGGId": 174430, "Name": "Gloomhaven", "YearPublished": 2017, "ImagePath": "...",
               "GameWeight": 3.87, "ComMinPlaytime": 60, "ComMaxPlaytime": 120, "BayesAvgRating": 8.51}]
  }
]
```

장르 순서는 `strategy`(Strategy), `family`(Family), `party`(Party), `thematic`(Thematic), `war`(Wargames), `childrens`(Children's), `cgs`(Card Games), `deduction`(Deduction). 화면이 영어라 `label`, `description`도 영어로 반환함.
전략은 BGG 카테고리 `Cat:Strategy` 또는 `Cat:Abstract`, 추리는 메커니즘 `Deduction`, 나머지는 같은 이름의 `Cat:*` 카테고리로 판정함.
리뷰 1,000개 이상인 게임 중 `BayesAvgRating` 내림차순으로 최대 6개를 담음. 한 게임이 여러 장르에 나올 수 있음. 목록은 서버 시작 시 한 번 계산함.

## 3. 오류 처리

| 상황 | 상태 코드 | 응답의 `detail` |
| --- | --- | --- |
| 검색어가 빈 문자열 또는 공백 | 400 | `Search query cannot be empty` |
| 추천 게임명이 공백 | 400 | `Game name cannot be empty` |
| 인원이 0 이하 | 400 | `Players must be greater than 0` |
| 시간이 0 이하 | 400 | `Max time must be greater than 0` |
| 존재하지 않는 기준 게임 | 404 | `Game not found` |
| 추천 조건에 맞는 후보가 없음 | 404 | `No games match the selected conditions` |
| 필수 필드 누락 또는 잘못된 자료형 | 422 | FastAPI 검증 오류 목록 |
| 추천 주소를 GET으로 호출 | 405 | `Method Not Allowed` |
| 존재하지 않는 게임 ID로 상세 조회 | 404 | `Game not found` |
| 자연어 검색 검색어가 너무 김(300자 초과) | 400 | `Search query is too long` |
| 설명 요청의 `basis`가 비었거나 300자 초과, `game_ids`가 1~10개가 아님 | 400 | `Basis cannot be empty` / `Basis is too long` / `Provide between 1 and 10 game ids` |
| `GEMINI_API_KEY` 또는 `gemini_embeddings.npz`가 없을 때 `POST /search/natural` | 503 | `Natural language search is not available` |
| `GEMINI_API_KEY`가 없을 때 `POST /explain` | 503 | `Explanations are not available` |
| `POST /search/natural`이 IP 제한(분당 10회) 초과 | 429 | `Too many requests` |
| `POST /explain`이 IP 제한(분당 30회) 초과 | 429 | `Too many requests` |
| Gemini 호출 실패(타임아웃 등) 또는 일일 호출 상한(`GEMINI_DAILY_CALL_LIMIT`) 소진 | 503 | `Natural language search is temporarily unavailable` / `Explanations are temporarily unavailable` |
| 자연어 검색 조건에 맞는 게임이 없음 | 404 | `No games match the selected conditions` |
| 설명 요청의 `mode`가 `similar`인데 `basis`가 알려진 게임이 아님 | 404 | `Game not found` (`game_ids`에 없는 ID는 오류 없이 무시되어 `200`) |
| 임베딩 파일이 없거나 `semantic` 패키지 미설치 상태에서 자연어 검색 | 503 | `Semantic search is not available` |
| 존재하지 않는 장르 키로 장르 게임 조회 | 404 | `Genre not found` |

검색·필터의 결과 없음은 `200 + []`, 추천의 결과 없음은 `404`인 기존 API 동작을 유지함. `detail`은 400·404에서는 문자열, 422에서는 배열이므로 프론트에서 구분함.

## 4. 프론트엔드 연결

다음 두 개발 화면 주소를 허용함.

- `http://localhost:5173`
- `http://127.0.0.1:5173`

화면 주소의 프로토콜, 호스트, 포트를 함께 비교함. 프론트 포트가 5174로 바뀌면 5173으로 맞추거나 환경변수 `ALLOWED_ORIGINS`에 실제 주소를 지정해야 함.

`ALLOWED_ORIGINS`를 지정하면 위 기본 목록을 대신하므로, 필요한 주소를 모두 쉼표로 구분해 넣음. 배포 서버(Google Cloud Run)에는 Vercel 주소를 지정함 ([deploy.md](deploy.md) 참고).

```bash
ALLOWED_ORIGINS=https://boardgame-recommender.vercel.app,http://localhost:5173
```

CORS는 브라우저가 응답을 읽을 수 있도록 허용하는 설정이며, 로그인이나 서버 접근 권한을 대신하지 않음. 현재 API는 쿠키 인증을 사용하지 않으므로 `allow_credentials=False`.

```javascript
async function getRecommendations() {
  const response = await fetch("http://localhost:8000/recommend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ game_name: "Catan", players: 4, max_time: 90 }),
  });
  const data = await response.json();
  if (!response.ok) {
    const message = typeof data.detail === "string"
      ? data.detail
      : "게임명, 인원수, 시간을 확인해 주세요.";
    throw new Error(message);
  }
  return data; // [{ Name, ImagePath, Similarity, ... }, ...]
}
```

브라우저는 다른 출처로 JSON을 POST하기 전에 `OPTIONS` 사전 확인 요청을 보냄. `CORSMiddleware`가 이 요청과 실제 응답에 필요한 허용 헤더를 처리함. Swagger는 백엔드와 같은 출처에서 열리므로 Swagger 성공만으로 CORS 연동을 검증할 수는 없음.

## 5. 자동 테스트

서버를 별도로 켜지 않아도 실행됨. Python 기본 `unittest`와 FastAPI의 `TestClient`를 사용하고, 필요한 `httpx`는 개발 의존성에 명시되어 있음. GitHub Actions(`.github/workflows/test.yml`)를 통해 Pull Request 및 `main` 브랜치 push 시에도 자동으로 실행됨.

```bash
uv sync --locked
uv run --locked python -m unittest discover -s tests -v
uv run --locked ruff check backend/main.py tests/test_api.py
```

테스트 메서드가 다음을 검증함. 여러 입력을 확인하는 하위 테스트도 포함.

- 실제 데이터 로딩, 검색(정확히 일치·접두어·포함 순 정렬), 조건 필터, 추천 순위와 기준 게임 제외
- `exclude_ids`를 이용한 중복 없는 재추천("다른 게임 5개 추천받기") 및 남은 후보 없음 처리
- 빈 입력, 누락된 필드, 잘못된 자료형, 존재하지 않는 게임, 후보 없음
- 추천 요청의 POST 사용
- 두 개발 화면 출처의 사전 확인 요청과 정상·오류 응답의 CORS 헤더
- 허용 목록에 없는 출처에는 CORS 허용 헤더를 제공하지 않음
- 장르 8개의 순서, 장르별 인기·정렬·개수 조건, 전략의 추상 게임 포함, 추리의 Deduction 판정
- `GET /genres/{key}/games`의 인원·시간 조건 필터링, 인기 게임 우선 정렬, 잘못된 조건·장르 처리

테스트는 저장소의 실제 데이터에 `Catan`이 존재하는 것을 전제로 함. 데이터셋을 교체하면 해당 기준 게임도 점검해야 함.

## 참고

- [FastAPI CORS 공식 문서](https://fastapi.tiangolo.com/tutorial/cors/)
- [FastAPI 테스트 공식 문서](https://fastapi.tiangolo.com/tutorial/testing/)
- [uv 버전 고정 및 환경 동기화](https://docs.astral.sh/uv/concepts/projects/sync/)
