# BoardGame Recommender — Frontend

보드게임 추천 서비스의 React 웹 화면입니다. 전체 프로젝트 설명은 [루트 README](../README.md)를 참고하세요.

- **스택**: React 19, TypeScript, Vite 8, Tailwind CSS 4, TanStack Query 5, Axios, lucide-react, oxlint
- **폰트**: Bricolage Grotesque(제목), IBM Plex Sans(본문) — `index.html`에서 Google Fonts로 불러옴
- **화면 글자**: 영어
- **필요 버전**: Node.js v20.19 이상

## 실행

```bash
npm install
npm run dev       # 개발 서버 http://localhost:5173
npm run lint      # oxlint 검사
npm run typecheck # TypeScript 타입 검사 (build에도 포함)
npm run build     # 배포용 빌드 → dist/
npm run preview   # 빌드 결과 미리보기
```

`.env`에 배포된 백엔드 주소가 있으면 그 서버를 쓰고, 없으면 로컬 백엔드(`http://localhost:8000`)를 씁니다. 로컬 백엔드는 프로젝트 루트에서 `uv run uvicorn backend.main:app --reload --port 8000`으로 실행합니다.

## 백엔드 주소 (`VITE_BASE_URL`)

| 상황 | 설정 |
| :--- | :--- |
| 로컬 백엔드 사용 | `.env`에 지정하지 않음 → `http://localhost:8000` 사용 |
| 배포된 백엔드 사용 | `.env.example`을 참고해 `.env`에 `VITE_BASE_URL=...` 지정 (끝에 `/` 없이) |
| 프론트 배포 | 배포 플랫폼 환경변수에 Google Cloud Run 백엔드 주소를 `VITE_BASE_URL`로 지정 후 다시 빌드 ([deploy.md](../docs/deploy.md)) |

- 예전 이름 `VITE_API_URL`도 인식합니다. 둘 다 있으면 `VITE_BASE_URL`을 씁니다.
- `npm run dev`로 실행할 때는 요청을 `/api`로 보내고, Vite 개발 서버가 배포된 백엔드로 대신 전달합니다 (`vite.config.js`의 `proxy`). 배포된 백엔드의 CORS 허용 목록에 `localhost`가 없어도 로컬에서 쓸 수 있습니다.
- 빌드한 화면(`npm run build`)은 프록시 없이 백엔드 주소로 직접 요청합니다. 그래서 배포된 프론트 주소가 백엔드의 `ALLOWED_ORIGINS`에 들어 있어야 합니다.
- `.env` 값은 개발 서버를 켤 때와 빌드할 때 읽으므로, 바꾸면 개발 서버를 다시 켜거나 다시 빌드해야 합니다.

## 화면 구성

```text
App.tsx
├── Header            모든 화면 위의 헤더: 로고(시작 화면으로) + 메뉴 2개
├── StartScreen       시작 화면: 제목, 버튼 2개, 위에서 아래로 흐르는 무작위 게임 사진 두 줄
├── RecommendScreen   게임 검색 → 인원·시간 선택 → 추천 Top 5 (Refresh: 본 게임을 exclude_ids로 빼고 다른 5개)
├── GenreScreen       8개 장르별 대표 게임 (Refresh: 본 게임을 exclude_ids로 빼고 같은 장르의 다른 게임)
└── GameDetailModal   게임 상세 팝업 (어느 화면에서든 열림, "Find similar games"로 이동)
```

화면 폭이 640px 이하(휴대폰)이면 조건 입력과 결과가 위아래로 쌓이고, 상세 팝업은 화면 아래에 붙는 시트 모양이 됩니다.

| 파일 | 역할 |
| :--- | :--- |
| `public/favicon.png` | 주사위 파비콘 이미지 (`index.html`에서 연결) |
| `src/screens/` | 화면 단위 컴포넌트 |
| `src/components/Header.tsx` | 헤더. 데이터가 있는 상태에서 다시 불러오는 동안 아래에 진행 막대 표시 |
| `src/components/GameSearch.tsx` | 게임 이름 자동완성 검색 (입력이 멈추면 검색, 검색어가 바뀌면 이전 요청 취소) |
| `src/components/SelectedGameCard.tsx` | 선택한 기준 게임 표시 |
| `src/components/ChoicePickers.tsx` | 인원(숫자 + players)·플레이 시간(막대) 선택 버튼 묶음 |
| `src/components/GameDetailModal.tsx` | 게임 상세 팝업 |
| `src/components/LoadingParts.tsx` | 로딩 뼈대, "Starting the server" 안내, 오류 안내 |
| `src/components/GameThumb.tsx` | 게임 표지 이미지 (없으면 이름 첫 글자) |
| `src/components/DiceBadge.tsx` | 주사위 로고 |
| `src/components/DifficultyPips.tsx` | 난이도 5칸 표시 |
| `src/api.ts` | axios로 백엔드에 요청하는 함수 모음. 시작 화면 사진용 `getRandomPhotos`(무작위 인원·시간으로 `/games/filter`를 불러 표지 사진 주소만 남김)도 여기 있음 |
| `src/queries.ts` | TanStack Query 훅 모음. 화면 코드는 이 훅으로 서버 데이터를 불러옴 |
| `src/filters.ts` | 인원·시간으로 고를 수 있는 값 (추천 화면과 무작위 사진에서 같이 씀) |
| `src/format.ts` | 플레이 시간·인원·점수 표시 등 글자 변환 |
| `src/styles.ts` | 공통 버튼 스타일, 화면 폭 |
| `src/types.ts` | 백엔드 응답 데이터의 타입 (검색 결과, 추천 결과, 상세 정보, 장르) |
| `src/index.css` | Tailwind 불러오기, `@theme`의 색 이름(`page`, `card`, `line`, `primary` 등)과 움직임 |

### 로딩 상태 (TanStack Query)

| 상태 | 화면 |
| :--- | :--- |
| 처음 불러오는 중 (`isPending`) | 내용이 들어올 자리에 회색 로딩 뼈대 |
| 4초 넘게 처음 불러오는 중 | 뼈대 위에 "Starting the server" 안내 (배포 서버가 잠에서 깨는 데 최대 1분) |
| 데이터가 있는 상태에서 다시 불러오는 중 (`isFetching`) | 기존 내용은 그대로, 헤더 아래 진행 막대 |
| 실패 (`isError`) | 오류 안내와 "Try again" 버튼 |

움직이는 효과(뼈대 반짝임, 사진 흐름, 주사위 흔들림, 진행 막대)는 운영체제의 "동작 줄이기" 설정을 켜면 멈춥니다.

사용하는 API는 `GET /games/search`, `GET /games/filter`, `POST /recommend`, `GET /games/{bgg_id}`, `GET /genres`, `GET /genres/{key}/games`입니다. 요청·응답 형식은 [backend_api.md](../docs/backend_api.md)를 참고하세요.
