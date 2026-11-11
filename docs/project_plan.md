# 🎲 보드게임 추천 시스템 프로젝트 계획서

* **프로젝트 목표**: `games.csv` 데이터를 활용하여 파이썬 기초부터 웹 서비스(FastAPI + React) 구현까지 완성하는 프로젝트
* **수행 기간**: 총 7주 (주당 6\~8시간 학습 및 실습)
* **참여 인원**: 4명
* **개발 환경**:
  * **언어**: Python 3.12, JavaScript
  * **가상환경 및 패키지 관리**: uv (Python 3.12)
  * **분석/백엔드 도구**: VS Code, Jupyter Notebook, Pandas, Scikit-learn, FastAPI, Uvicorn
  * **프론트엔드 도구**: Node.js (v20.19+), React 19 (Vite 8), Tailwind CSS 4
  * **배포**: Render (백엔드, Docker), Vercel (프론트엔드)

---

## 📊 프로젝트 진행 현황 (Progress Overview)

* **현재 상태**: **7주차 완료 + 추천 품질 개선 완료, 배포 완료**
* **전체 진행률**: **100%** (7주차 / 7주차 완료)

| 주차 | 주요 내용 | 상태 | 주요 산출물 |
| :--- | :--- | :---: | :--- |
| **1주차** | 가상환경 구축 & EDA(데이터 탐색) | ✅ 완료 | `notebooks/read_game_csv.ipynb` |
| **2주차** | 결측치/이상치 정제 & `clean_games.csv` 생성 | ✅ 완료 | `data/clean_games.csv`, `notebooks/read_game_csv.ipynb` |
| **3주차** | TF-IDF 키워드 벡터화 & 코사인 유사도 실습 | ✅ 완료 | `notebooks/cosine_similarity.ipynb` |
| **4주차** | 조건 필터링 + 유사도 통합 추천 파이프라인 구현 | ✅ 완료 | `backend/recommend_engine.py` |
| **5주차** | FastAPI 백엔드 REST API 서버 구축 | ✅ 완료 | `backend/main.py`, `tests/test_api.py` |
| **6주차** | React 프론트엔드 UI 화면 개발 | ✅ 완료 | `frontend/src/` |
| **7주차** | 프론트-백엔드 연동, 예외 처리 및 배포 | ✅ 완료 | `Dockerfile`, `docs/deploy.md` |
| **추가** | 하이브리드 추천 파이프라인 & 오프라인 평가 | ✅ 완료 | `backend/features.py`, `backend/evaluate.py` 등 |

---

## 🛠️ 기술 스택 및 도구

| 영역 | 도구 / 라이브러리 |
| ----- | ----- |
| **환경 관리** | `uv (Python 3.12)` |
| **데이터 처리** | `pandas`, `numpy`, `scipy` |
| **키워드 분석/유사도** | `scikit-learn` (`TfidfVectorizer`, `TruncatedSVD`), 희소 행렬 코사인 유사도 |
| **문장 임베딩 (선택)** | `sentence-transformers` (`intfloat/multilingual-e5-small`) |
| **백엔드 API** | `fastapi`, `uvicorn` |
| **프론트엔드 UI** | `React` (Vite), `Tailwind CSS`, `axios`, `lucide-react` |
| **테스트/린트** | `unittest` + `httpx`, `ruff`, `oxlint` |
| **배포** | `Docker`, Render, Vercel |

---

## 📅 주차별 상세 일정

### ✅ 1주차: uv 가상환경 구축 & 파이썬/판다스 기초 탐색 (EDA) [완료]

> **주요 목표**: 4명 모두 동일한 uv 가상환경을 구축하고, 엑셀 열어보듯 데이터셋 파악하기

* **사용 도구**: `uv`, `Python 3.12`, `Jupyter Notebook`, `pandas`
* **주요 산출물**: `notebooks/read_game_csv.ipynb`
* **설치 가이드**:
  ```bash
  uv init --python 3.12
  uv venv
  uv add pandas numpy scikit-learn matplotlib
  uv add --dev jupyterlab ipykernel
  ```

* **세부 작업 현황**:
  - [x] 1. `games.csv` 파일을 주피터 노트북에서 `pd.read_csv()`로 불러오기.
  - [x] 2. 행(Row)과 열(Column) 개수 및 데이터 정보 확인 (`df.shape`, `df.info()`, `df.describe()`).
  - [x] 3. 핵심 컬럼 선별 (최종 13개 컬럼 확정):
    * **기본 식별 및 정보**: `BGGId`, `Name`, `YearPublished`, `ImagePath`
    * **게임 특성 및 난이도**: `GameWeight`, `Description`
    * **플레이 인원 및 시간**: `MinPlayers`, `MaxPlayers`, `BestPlayers`, `ComMinPlaytime`, `ComMaxPlaytime`
    * **평점 및 인기도 지표**: `BayesAvgRating`, `NumUserRatings`
  - [x] 4. 인원수 컬럼(`BestPlayers`, `GoodPlayers`)의 값 분포 및 투표 부재(`0`값) 데이터 형태 관찰하기.

---

### ✅ 2주차: 필수 데이터 정제 (이상치 및 결측치 정리) [완료]

> **주요 목표**: 추천에 방해되는 결측치(비어있는 값)와 말도 안 되는 숫자 제거하기

* **사용 도구**: `pandas`
* **주요 산출물**: `notebooks/read_game_csv.ipynb`, `notebooks/clean_data.py`, `data/clean_games.csv`
* **세부 작업 현황**:
  - [x] 1. **결측치(NaN 및 공백) 제거**:
    * 설명글(`Description`)이나 게임 이름(`Name`)이 비어 있는 데이터(`isna()`, 공백 문자열) 제거 및 인덱스 리셋 (`reset_index`).
  - [x] 2. **말도 안 되는 수치 필터링 (이상치 제거 조건문 적용)**:
    * 플레이 타임 이상치 제외: `ComMinPlaytime > 0` 및 `ComMaxPlaytime < 1000` 조건 만족.
    * 플레이 인원 이상치 제외: `MinPlayers >= 1` 및 `MinPlayers <= 10` 조건 만족.
  - [x] 3. **인원수 컬럼 결측치(`0`값) 처리**:
    * `BestPlayers`가 `0`(유저 투표 부재)인 데이터를 제조사 공식 인원 기준(`(MinPlayers + MaxPlayers) // 2`)으로 대체 보정 완료.
  - [x] 4. 선별된 13개 핵심 컬럼 중심으로 정제 완료된 데이터를 `data/clean_games.csv`로 저장 완료 (이후 주차부터 이 정제 데이터 사용).

---

### ✅ 3주차: 키워드 기반 유사도(TF-IDF) 계산하기 [완료]

> **주요 목표**: Scikit-learn 기본 도구로 "설명이 비슷한 게임" 찾아보기

* **사용 도구**: `scikit-learn` (`TfidfVectorizer`, `cosine_similarity`), `pandas`, `numpy`
* **주요 산출물**: `notebooks/cosine_similarity.ipynb`
* **개념**:
  * **TF-IDF**: 설명글에서 "dice", "card", "war", "trade"처럼 게임 특징을 나타내는 단어에 높은 점수를 매겨 숫자로 바꾸는 기법.
* **세부 작업 현황**:
  - [x] 1. `data/clean_games.csv`의 `Description` 컬럼에 `TfidfVectorizer(max_features=1000, stop_words='english')` 적용.
  - [x] 2. 전체 게임에 대해 1,000개의 핵심 단어 점수표(희소 행렬, Sparse Matrix) 생성 완료.
  - [x] 3. 두 게임 간의 코사인 유사도를 구하는 기본 코드 실습:
    ```python
    # 카탄(Catan)과 다른 모든 게임 사이의 텍스트 유사도 구하기
    similarity_scores = cosine_similarity(target_game_vector, tfidf_matrix)[0]
    ```
  - [x] 4. 코사인 유사도 상위 인덱스 정렬(`np.argsort`)을 통해 'Catan' 기준 유사 키워드 상위 5개(Top 5) 추천 게임 도출 및 결과 검증 완료.

---

### ✅ 4주차: 추천 함수(규칙 + 유사도) 로직 완성 [완료]

> **주요 목표**: "인원수 필터"와 "유사도 정렬"을 묶은 하나의 파이썬 함수 만들기

* **사용 도구**: `pandas`, `scikit-learn`
* **주요 산출물**: `backend/recommend_engine.py`
* **세부 작업 현황**:
  - [x] 1. **1차 하드 필터링 (내가 원하는 조건만 거르기)**:
    * 예: "4명이서 할 거다" → `MinPlayers ~ MaxPlayers` 범위에 4가 포함된 게임만 남김.
    * 예: "플레이 시간 60분 이하" → 조건 만족 행만 추출.
  - [x] 2. **2차 유사도 랭킹 (남은 후보군 중 가장 비슷한 순 정렬)**:
    * 기준 게임(예: '스플렌더')과 1차 필터링을 통과한 후보 게임들 간의 코사인 유사도 계산.
  - [x] 3. **3차 보정 (평점이 너무 낮은 게임 제외)**:
    * `BayesAvgRating`이 최소 5.5 이상인 게임만 최종 추천.
  - [x] 4. **최종 함수 입출력 정의**:
    * 입력: `(기준게임명, 인원수, 최대시간)`
    * 출력: 추천 게임 5개의 딕셔너리 리스트 (이름, 이미지URL, 난이도, 예상시간).

---

### ✅ 5주차: FastAPI 백엔드 서버 띄우기 [완료]

> **주요 목표**: 4주차에 만든 파이썬 함수를 웹 주소(API)로 호출할 수 있게 만들기

* **사용 도구**: `fastapi`, `uvicorn`, `httpx`(테스트)
* **주요 산출물**: `backend/main.py`, `backend/genres.py`, `tests/test_api.py`, `docs/backend_api.md`
* **세부 작업 현황**:
  - [x] 1. `main.py` 작성 및 서버 실행 (`uv run uvicorn backend.main:app --reload`).
  - [x] 2. 엔드포인트 작성:
    * `GET /games/search`: 게임 이름 자동완성 검색 (최대 10개).
    * `GET /games/filter`: 인원·시간 조건만으로 평점 상위 게임 조회.
    * `POST /recommend`: 기준 게임·인원·시간을 받아 추천 Top 5 반환.
    * `GET /games/{bgg_id}`: 게임 한 개의 상세 정보 (상세 팝업용).
    * `GET /genres`: 장르 8개와 장르별 대표 게임 6개.
  - [x] 3. 입력 검증과 오류 응답 정리 (빈 입력 `400`, 없는 게임·후보 없음 `404`, 자료형 오류 `422`).
  - [x] 4. Swagger UI(`http://localhost:8000/docs`) 수동 확인 + `unittest`/`TestClient` 자동 테스트 작성.

---

### ✅ 6주차: React 프론트엔드 UI 만들기 [완료]

> **주요 목표**: 웹 브라우저에서 조작할 수 있는 직관적인 웹 화면 구성

* **사용 도구**: `Node.js`, `React (Vite)`, `Tailwind CSS`, `axios`, `lucide-react`
* **주요 산출물**: `frontend/src/`
* **세부 작업 현황**:
  - [x] 1. Vite 기반 React 앱 생성, Tailwind CSS 4 적용 (색상은 `index.css`의 `@theme`에서 관리).
  - [x] 2. **화면 구성**:
    * **시작 화면** (`StartScreen`): 이용 방법 안내, 추천받기 / 장르별 둘러보기 선택.
    * **추천 화면** (`RecommendScreen`): 게임 이름 자동완성 검색(`GameSearch`), 인원(2\~6명)·플레이 시간(30·60·90·120분 이하) 선택(`OptionGroup`), 결과 카드에 표지·난이도·시간·공통 메커니즘 표시.
    * **장르 화면** (`GenreScreen`): 8개 장르별 대표 게임 목록.
    * **게임 상세 팝업** (`GameDetailModal`): 어느 화면에서든 게임을 누르면 상세 정보를 보여 주고 그 게임 기준으로 바로 추천.
  - [x] 3. 백엔드 요청은 `api.js`에 모아 화면 코드에서 axios를 직접 쓰지 않도록 정리.

---

### ✅ 7주차: 화면-서버 연동, 예외 처리 및 배포 [완료]

> **주요 목표**: 연동 오류 해결, 예외 상황 처리, 누구나 접속할 수 있도록 배포

* **사용 도구**: `Git`, `GitHub`, `Docker`, Render, Vercel
* **주요 산출물**: `Dockerfile`, `frontend/.env.example`, `docs/deploy.md`
* **세부 작업 현황**:
  - [x] 1. **CORS 설정**: 개발 화면 주소(`localhost:5173`)는 기본 허용, 배포 주소는 환경변수 `ALLOWED_ORIGINS`로 지정.
  - [x] 2. **예외 처리**: 조건에 맞는 게임 없음, 게임을 찾을 수 없음, 입력 오류, 서버 연결 실패를 구분해 안내 메시지 표시.
  - [x] 3. **배포**: 백엔드는 Render(Docker, 무료), 프론트엔드는 Vercel. 백엔드 주소는 빌드 환경변수 `VITE_API_URL`로 지정.
  - [x] 4. README 및 문서 정리.

---

### ✅ 추가: 추천 품질 개선 [완료]

> **주요 목표**: 설명글 단어만 비교하던 방식의 한계(예: Catan 추천 5개가 모두 Catan 변형판)를 해결하고, 개선 여부를 숫자로 확인하기

* **주요 산출물**: `backend/features.py`, `backend/build_embeddings.py`, `backend/build_cf.py`, `backend/evaluate.py`, `docs/recommendation_pipeline.md`
* **세부 작업 현황**:
  - [x] 1. **하이브리드 유사도**: 메커니즘·테마(IDF 가중), 카테고리·난이도, 설명글(문장 임베딩 또는 TF-IDF), 협업 필터링(Truncated SVD)을 가중 결합.
  - [x] 2. **점수 보정**: 평점을 최종 점수의 25%로 반영, 같은 시리즈 변형판 감점, 다양성 재정렬(MMR).
  - [x] 3. **추천 이유 표시**: 기준 게임과 공통인 메커니즘·테마를 응답에 포함.
  - [x] 4. **오프라인 평가**: 학습에서 제외한 사용자 1,000명 기준 HitRate@10이 TF-IDF 0.134 → 하이브리드 0.450.
  - [x] 5. **자연어 검색 API** (`GET /games/semantic-search`, 선택 기능): 한국어 문장으로 게임 검색.

---

## 💡 프로젝트 추진 가이드 & 회고

1. **단순한 방법부터 시작하고, 평가로 개선 여부 확인하기**:
   * 초기에는 딥러닝 환경 설정에 시간을 쓰지 않도록 `TfidfVectorizer`와 `Pandas 조건문`으로 동작하는 추천을 먼저 완성함.
   * 이후 오프라인 평가(`backend/evaluate.py`)를 만든 뒤에 임베딩·협업 필터링을 추가하여, 바뀐 점을 수치로 비교함.
   * 무거운 기능(`sentence-transformers`)은 선택 설치로 분리하여, 기본 설치와 배포 서버는 가볍게 유지함.

2. **함수 단위로 역할 쪼개기**:
   * 추천 엔진 함수(`recommend_games(...)`)를 FastAPI 내부에서 그대로 호출하는 구조를 취해 협업 시 코드 충돌 최소화.
