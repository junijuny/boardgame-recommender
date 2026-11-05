# BoardGame Recommender — Frontend

보드게임 추천 서비스의 React 웹 화면입니다. 전체 프로젝트 설명은 [루트 README](../README.md)를 참고하세요.

- **스택**: React 19, Vite 8, Tailwind CSS 4, Axios, lucide-react, oxlint
- **필요 버전**: Node.js v20.19 이상

## 실행

```bash
npm install
npm run dev       # 개발 서버 http://localhost:5173
npm run lint      # oxlint 검사
npm run build     # 배포용 빌드 → dist/
npm run preview   # 빌드 결과 미리보기
```

검색·추천을 쓰려면 백엔드를 먼저 실행해야 합니다 (프로젝트 루트에서 `uv run uvicorn backend.main:app --reload --port 8000`).

## 백엔드 주소 (`VITE_API_URL`)

| 상황 | 설정 |
| :--- | :--- |
| 로컬 개발 | 설정하지 않음 → `http://localhost:8000` 사용 |
| 다른 백엔드 사용 | `.env.example`을 참고해 `.env.local`에 `VITE_API_URL=...` 지정 (끝에 `/` 없이) |
| Vercel 배포 | 프로젝트 환경변수에 Render 주소 지정 후 Redeploy ([deploy.md](../docs/deploy.md)) |

`VITE_API_URL`은 빌드할 때 코드에 들어가므로, 값을 바꾸면 다시 빌드해야 합니다.

## 화면 구성

```text
App.jsx
├── StartScreen       시작 화면: 추천받기 / 장르별로 둘러보기
├── RecommendScreen   게임 검색 → 인원·시간 선택 → 추천 Top 5
├── GenreScreen       8개 장르별 대표 게임
└── GameDetailModal   게임 상세 팝업 (어느 화면에서든 열림, "비슷한 게임 추천받기"로 이동)
```

| 파일 | 역할 |
| :--- | :--- |
| `src/screens/` | 화면 단위 컴포넌트 |
| `src/components/GameSearch.jsx` | 게임 이름 자동완성 검색 (입력이 바뀌면 이전 요청 취소) |
| `src/components/SelectedGameCard.jsx` | 선택한 기준 게임 표시 |
| `src/components/OptionGroup.jsx` | 인원·시간 선택 버튼 묶음 |
| `src/components/GameThumb.jsx` | 게임 표지 이미지 (없으면 대체 표시) |
| `src/api.js` | 백엔드 요청 함수 모음. 화면 코드는 axios를 직접 쓰지 않고 이 함수만 사용 |
| `src/format.js` | 플레이 시간 표시, 조사(와/과) 처리 등 글자 변환 |
| `src/styles.js` | 공통 버튼 스타일 |
| `src/index.css` | Tailwind 불러오기, `@theme`의 색 이름(`page`, `card`, `line`, `primary` 등) |

사용하는 API는 `GET /games/search`, `POST /recommend`, `GET /games/{bgg_id}`, `GET /genres`입니다. 요청·응답 형식은 [backend_api.md](../docs/backend_api.md)를 참고하세요.
