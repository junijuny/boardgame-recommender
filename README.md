# 🎲 BoardGame Recommender (보드게임 추천 시스템)

<div align="center">

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-8-646CFF?style=flat-square&logo=vite&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-4-38B2AC?style=flat-square&logo=tailwind-css&logoColor=white)
![Scikit-Learn](https://img.shields.io/badge/scikit--learn-F7931E?style=flat-square&logo=scikit-learn&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini_API-8E75B2?style=flat-square&logo=googlegemini&logoColor=white)
![uv](https://img.shields.io/badge/uv-DE5FE9?style=flat-square&logo=uv&logoColor=white)
![Google Cloud Run](https://img.shields.io/badge/Backend-Cloud_Run-4285F4?style=flat-square&logo=google-cloud&logoColor=white)
![Vercel](https://img.shields.io/badge/Frontend-Vercel-000000?style=flat-square&logo=vercel&logoColor=white)

<br/>

**좋아하는 보드게임 하나, 또는 원하는 게임을 설명하는 문장 하나로 딱 맞는 보드게임을 찾아 주는 추천 웹 서비스**

</div>

---

## 🎯 프로젝트 개요

* **목표**: BoardGameGeek(BGG) 데이터를 정제하고, 메커니즘·테마·설명글·사용자 평점을 결합한 하이브리드 추천 엔진과 Gemini 기반 자연어 검색을 FastAPI 백엔드와 React 프론트엔드로 서비스
* **수행 기간**: 7주 (주당 6\~8시간) + 추가 고도화
* **참여 인원**: 4명
* **배포**: 백엔드 Google Cloud Run (Docker, GitHub Actions), 프론트엔드 Vercel

---

## 💡 주요 기능

| 화면 | 기능 |
| :--- | :--- |
| **시작 화면** | "Find similar games" / "Browse by genre" 선택, 무작위 게임 표지 사진이 흐르는 배경 |
| **Find games — By game** | 게임 이름 자동완성 → 인원(2\~6명)·플레이 시간 구간(0\~2시간, 30분 단위 슬라이더) 선택 → 비슷한 게임 Top 5. "Refresh"로 본 게임을 빼고 다른 5개 |
| **Find games — By description** | 원하는 게임을 한국어·영어 문장으로 설명하면 Gemini가 이해해 Top 5 추천. 검색어 해석 한 줄, 약한 일치 안내, 필요하면 웹 검색 요약("From the web") 표시. "games like Catan"처럼 쓰면 By game 탭으로 바로 전환 |
| **장르 화면** | 전략·가족·파티·테마·워게임·어린이·카드게임·추리 8개 장르별 대표 게임 6개, "Refresh"로 같은 장르의 다른 게임 |
| **게임 상세 팝업** | 어느 화면에서든 게임을 누르면 인원·시간·난이도·평점·설명·BGG 링크를 보여 주고, 그 게임 기준으로 바로 추천 |

추천 결과마다 Gemini가 쓴 영어 한 문장 이유가 붙습니다. `GEMINI_API_KEY`가 없으면 By description 탭은 숨겨지고, 이유 대신 공통 메커니즘 칩을 보여 줍니다.

---

## 🧠 추천 방식 한눈에 보기

**비슷한 게임 추천** (`POST /recommend`) — 인원·시간·평점으로 후보를 거른 뒤, 메커니즘·테마·카테고리·설명글 임베딩·협업 필터링을 합친 하이브리드 유사도에 평점을 더해 순위를 매기고, 변형판 감점과 다양성 재정렬(MMR)로 Top 5를 고릅니다. 오프라인 평가에서 초기 TF-IDF 방식 대비 HitRate@10이 **0.134 → 0.450 (약 3.4배)** 로 올랐습니다. → [추천 파이프라인](docs/recommendation_pipeline.md)

**자연어 검색** (`POST /search/natural`) — Gemini가 검색어를 조건(태그·난이도·나이·순위 기준 등)과 영어 묘사로 바꾸고, 게임 설명·프로필 임베딩과 비교한 뒤 Gemini가 상위 25개를 다시 정렬합니다. 수상 목록처럼 바깥 사실이 필요한 질문은 Google 검색 근거를 씁니다. 질의 40개 평가에서 Hit@5 **0.82 → 0.97**. → [자연어 검색](docs/natural_search.md)

---

## 🚀 빠른 시작

필요한 프로그램: [uv](https://docs.astral.sh/uv/), [Node.js](https://nodejs.org/) v20.19 이상. 자세한 절차는 [개발 환경 세팅](docs/setup.md)을 참고하세요.

```bash
# 1. Python 의존성 설치 (프로젝트 루트)
uv sync

# 2. 백엔드 실행 → http://localhost:8000 (Swagger: /docs)
uv run uvicorn backend.main:app --reload --port 8000
#    자연어 검색·추천 이유까지 쓰려면 루트 .env에 GEMINI_API_KEY=... 를 넣고
uv run --env-file .env uvicorn backend.main:app --reload --port 8000

# 3. 프론트엔드 실행 (새 터미널) → http://localhost:5173
cd frontend
npm install
npm run dev

# 4. 테스트
uv run python -m unittest discover -s tests -v
```

추천에 필요한 데이터 파일은 모두 저장소에 들어 있어 따로 준비할 필요가 없습니다.

---

## 📚 문서

| 문서 | 내용 |
| :--- | :--- |
| [개발 환경 세팅](docs/setup.md) | uv·Node.js 설치, 백엔드·프론트엔드 실행, 환경 변수, FAQ |
| [시스템 구조](docs/architecture.md) | 아키텍처 다이어그램, 기술 스택, 폴더·파일 구성 |
| [데이터셋](docs/dataset.md) | BGG 데이터 출처, 데이터 파일 목록, 주요 컬럼 |
| [추천 파이프라인](docs/recommendation_pipeline.md) | 비슷한 게임 추천 알고리즘, 협업 필터링, 오프라인 평가 |
| [자연어 검색](docs/natural_search.md) | Gemini 질의 이해, 재순위, 웹 검색, 게임 프로필, 검색 평가 |
| [백엔드 API](docs/backend_api.md) | 엔드포인트 명세, 오류 응답, CORS, 자동 테스트 |
| [배포 가이드](docs/deploy.md) | Google Cloud Run·Vercel 배포, Gemini 키·비용 한도 |
| [프로젝트 계획서](docs/project_plan.md) | 주차별 계획과 진행 내역, 회고 |
| [프론트엔드](frontend/README.md) | 화면·컴포넌트 구성, 로딩 상태, 백엔드 주소 설정 |

---

## 📜 데이터 출처
* [BoardGameGeek (BGG)](https://boardgamegeek.com/)
* [Kaggle — Board Games Database from BoardGameGeek](https://www.kaggle.com/datasets/threnjen/board-games-database-from-boardgamegeek)

---

## ⚖️ 라이선스 (License)
* **코드**: [MIT License](LICENSE) © 2026 JIWON LEE (이지원)
* **데이터**: BGG에서 온 게임 데이터와 이를 가공한 산출물(`data/` 폴더)은 MIT License 대상이 **아니며**, 원본 조건을 따릅니다.
    * Kaggle 원본(`games.csv`, `mechanics.csv`, `themes.csv`)과 이를 가공해 만든 파일(`clean_games.csv`, 임베딩, `game_profiles.json` 등)은 [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/)을 따릅니다.
    * 게임 정보와 표지 이미지는 BoardGameGeek의 데이터로, [BGG XML API 이용 약관](https://boardgamegeek.com/wiki/page/XML_API_Terms_of_Use)에 따라 **비상업적 용도로만** 사용할 수 있습니다. 표지 이미지의 저작권은 각 권리자에게 있습니다.
