# 프론트엔드 개선: 제목 변경 · 상세 보기 · 장르별 둘러보기

작성일: 2026-11-05

## 목표

1. 시작 화면 제목을 "Boardgame Recommender"로 바꾼다.
2. 추천 결과(5개)를 클릭하면 게임 상세 정보를 볼 수 있다.
3. 게임 이름을 몰라도 장르별 대표 게임을 둘러볼 수 있다.

## 범위 밖

- 한글 번역, 한글 게임 이름 검색: 비용 문제로 제외. 게임 이름과 설명은 영어 원문 그대로 보여준다.
  화면 문구(버튼, 안내문, 장르 이름, 장르 설명)는 지금처럼 한글로 쓴다.

## 1. 제목 변경

- `StartScreen`의 `h1` "뭐 하고 놀지 고민될 때" → "Boardgame Recommender". 아래 설명 문구는 유지한다.
- `frontend/index.html`의 `<title>`("frontend") → "Boardgame Recommender".

## 2. 게임 상세 모달

- 추천 결과의 각 줄(`GameRow`)을 버튼으로 바꾸고, 누르면 `GameDetailModal`을 연다.
- 모달을 열면 `GET /games/{bgg_id}`(기존 API)를 호출한다.
- 표시 항목: 이미지(없으면 주사위 아이콘), 이름, 출시 연도, 인원(`MinPlayers`\~`MaxPlayers`, `BestPlayers`가 있으면 최적 인원),
  플레이 시간, 난이도(`GameWeight` / 5), 평점(`BayesAvgRating`, 리뷰 수), 설명 전문.
- 설명에 들어 있는 HTML 엔티티(`&quot;`, `&#10;` 등)는 디코딩한다(DOMParser나 textarea 이용, HTML로 렌더링하지 않음).
  `&#10;`는 줄바꿈으로 보여준다(`whitespace-pre-line`).
- 닫기: X 버튼, ESC, 바깥 영역 클릭. 열려 있는 동안 포커스를 모달 안에 두고, 닫으면 원래 버튼으로 포커스를 돌려준다.
  `<dialog>` 요소의 `showModal()`을 사용한다.
- 상태: 로딩 중, 에러("게임 정보를 불러오지 못했습니다" + 다시 시도), 404.
- 모달 하단에 "이 게임과 비슷한 게임 추천받기" 버튼을 둔다. 누르면 추천 화면으로 이동하고 해당 게임이 선택된 상태가 된다.
  추천 화면 안에서 연 경우에도 같은 동작이다(기준 게임이 바뀌고 이전 결과는 지워진다).

## 3. 장르별 둘러보기

### 백엔드: `GET /genres`

응답:

```json
[
  {
    "key": "strategy",
    "label": "전략",
    "description": "깊이 있는 계획과 수 싸움",
    "games": [ { "BGGId": 0, "Name": "", "YearPublished": 0, "ImagePath": "", "GameWeight": 0,
                 "ComMinPlaytime": 0, "ComMaxPlaytime": 0, "BayesAvgRating": 0 } ]
  }
]
```

장르 8개와 판정 기준:

| key | label | 기준 |
|---|---|---|
| strategy | 전략 | `Cat:Strategy` 또는 `Cat:Abstract` |
| family | 가족 | `Cat:Family` |
| party | 파티 | `Cat:Party` |
| thematic | 테마 | `Cat:Thematic` |
| war | 워게임 | `Cat:War` |
| childrens | 어린이 | `Cat:Childrens` |
| cgs | 카드게임 | `Cat:CGS` |
| deduction | 추리 | `mechanics.csv`의 `Deduction` |

설명 문구(최종 문구는 구현할 때 다듬는다):
전략 "깊이 있는 계획과 수 싸움", 가족 "누구나 쉽게 함께", 파티 "여럿이 왁자지껄",
테마 "이야기와 세계관에 몰입", 워게임 "전투와 역사 시뮬레이션", 어린이 "아이와 함께 즐기는",
카드게임 "카드를 모으고 덱을 짜는", 추리 "단서를 모아 정답을 맞히는".

- 대상: `clean_games.csv`에 있는 게임 중 `NumUserRatings >= 1000`인 게임.
- 정렬: 모든 장르를 `BayesAvgRating` 내림차순으로 정렬하고 상위 6개를 반환한다.
- 장르별 목록은 서버가 시작할 때 한 번 계산해 메모리에 둔다. `Cat:*` 컬럼은 `data/games.csv`에서 `BGGId`로 붙인다.
- 계산 로직은 `backend/genres.py`에 두고, `main.py`에는 엔드포인트만 추가한다.
- 라우트 순서: `/genres`는 `/games/{bgg_id}`와 경로가 겹치지 않으므로 순서에 제약이 없다.

### 프론트: 장르 화면

- 시작 화면에 버튼 두 개: "비슷한 게임 추천받기"(기존 추천 화면), "장르별로 둘러보기"(새 화면).
- `GenreScreen`: 처음으로 버튼, 제목, 장르 칩 8개(선택 상태는 `aria-pressed`), 선택한 장르의 설명,
  게임 카드 그리드(모바일 2열, 넓은 화면 3열). 카드에는 이미지, 이름, 시간, 난이도를 넣는다.
- `/genres`는 화면에 들어올 때 한 번 호출하고, 장르를 바꿀 때는 다시 요청하지 않는다. 로딩·에러(다시 시도) 상태를 둔다.
- 카드를 누르면 `GameDetailModal`이 열리고, "비슷한 게임 추천받기"를 누르면 그 게임이 선택된 추천 화면으로 이동한다.

## 구조

`App.jsx`(642줄)를 아래처럼 나눈다. 기존 스타일 토큰(`index.css`의 `@theme`)과 주석 스타일은 유지한다.

- `src/api.js`: `API_URL`, axios 호출 함수(`searchGames`, `recommend`, `getGameDetail`, `getGenres`)
- `src/format.js`: `formatMinutes`, `withWa`, 시간 범위 문자열, 엔티티 디코딩
- `src/App.jsx`: 화면 전환(`start` / `recommend` / `genres`)과 추천 화면에 넘길 초기 게임 상태
- `src/screens/StartScreen.jsx`, `RecommendScreen.jsx`, `GenreScreen.jsx`
- `src/components/GameSearch.jsx`, `OptionGroup.jsx`, `GameDetailModal.jsx`, `GameThumb.jsx`(이미지 + 실패 시 주사위)

`RecommendScreen`은 `initialGame` prop을 받는다. `GameSearch`는 바깥에서 선택된 게임을 받아 입력창에 보여줄 수 있어야 한다.

## 테스트

- `tests/test_api.py`에 `/genres` 테스트 추가:
  장르 8개와 key 순서, 각 장르의 게임 수가 6개 이하, 평점 내림차순 정렬, 모든 게임이 `NumUserRatings >= 1000`,
  `strategy`에 `Cat:Abstract`만 해당하는 게임도 포함될 수 있음(판정 함수 단위 테스트).
- 프론트: `npm run lint`, `npm run build` 통과. 앱을 실행해 확인할 항목:
  시작 → 추천 → 결과 클릭 → 모달, 장르 탭 전환, 모달에서 추천 화면으로 이동, ESC로 닫기.
