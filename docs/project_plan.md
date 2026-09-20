# 🎲 보드게임 추천 시스템 프로젝트 계획서

* **프로젝트 목표**: `games.csv` 데이터를 활용하여 파이썬 기초부터 웹 서비스(FastAPI + React) 구현까지 완성하는 프로젝트

* **수행 기간**: 총 7주 (주당 6\~8시간 학습 및 실습)

* **참여 인원**: 4명

* **개발 환경**:

  * **언어**: Python 3.12, JavaScript

  * **가상환경 및 패키지 관리**: Anaconda (Conda)

  * **분석/백엔드 도구**: VS Code, Jupyter Notebook, Pandas, Scikit-learn, FastAPI, Uvicorn

  * **프론트엔드 도구**: Node.js (v18+), React (Vite), Tailwind CSS

## 🛠️ 기술 스택 및 도구

| 영역 | 도구 / 라이브러리 | 
 | ----- | ----- | 
| **환경 관리** | `Anaconda (Python 3.12)` | 
| **데이터 처리** | `pandas`, `numpy` | 
| **키워드 분석/유사도** | `scikit-learn` (`TfidfVectorizer`, `cosine_similarity`) | 
| **백엔드 API** | `fastapi`, `uvicorn` | 
| **프론트엔드 UI** | `React` (Vite), `Tailwind CSS`, `axios` |

## 📅 주차별 상세 일정

### 📌 1주차: 아나콘다 환경 구축 & 파이썬/판다스 기초 탐색 (EDA)

> **주요 목표**: 4명 모두 동일한 아나콘다 환경을 구축하고, 엑셀 열어보듯 데이터셋 파악하기

* **사용 도구**: `Anaconda`, `Python 3.12`, `Jupyter Notebook`, `pandas`

* **설치 가이드**:

  ```
  conda create -n bg_rec python=3.12
  conda activate bg_rec
  conda install pandas numpy scikit-learn jupyterlab -c conda-forge
  
  ```

* **세부 작업**:

  1. `games.csv` 파일을 주피터 노트북에서 `pd.read_csv()`로 불러오기.

  2. 행(Row)과 열(Column) 개수 확인 (`df.shape`, `df.info()`).

  3. 핵심 컬럼 선별:

     * 이름(`Name`), 발매년도(`YearPublished`), 게임 난이도(`GameWeight`), 플레이 인원(`MinPlayers`, `MaxPlayers`, `BestPlayers`), 플레이 시간(`ComMinPlaytime`), 평점(`BayesAvgRating`), 설명(`Description`), 표지 이미지(`ImagePath`).

  4. 인원수 컬럼(`BestPlayers`)이 텍스트 형태(`"['3', '4']"`)로 들어있는 형태 관찰하기.

### 📌 2주차: 필수 데이터 정제 (이상치 및 결측치 정리)

> **주요 목표**: 추천에 방해되는 결측치(비어있는 값)와 말도 안 되는 숫자 제거하기

* **사용 도구**: `pandas`

* **세부 작업**:

  1. **결측치(NaN) 제거 및 채우기**:

     * 설명글(`Description`)이나 게임 이름(`Name`)이 비어 있는 데이터 제거.

  2. **말도 안 되는 수치 필터링 (간단한 조건문 사용)**:

     * 플레이 타임이 0분 이하이거나 1,000분 이상인 이상치 제외.

     * 최소 인원이 0명이거나 10명 초과인 데이터 제외.

  3. **인원수 컬럼 다듬기**:

     * 텍스트로 된 `"['3', '4']"`를 파이썬 리스트 `[3, 4]`로 쉽게 바꾸는 함수 작성 (`eval()` 또는 문자열 치환).

  4. 정제 완료된 데이터를 `clean_games.csv`로 저장 (다음 주차부터 이 파일만 불러와 사용).

### 📌 3주차: 키워드 기반 유사도(TF-IDF) 계산하기

> **주요 목표**: Scikit-learn 기본 도구로 "설명이 비슷한 게임" 찾아보기

* **사용 도구**: `scikit-learn` (`TfidfVectorizer`, `cosine_similarity`)

* **초보자 눈높이 개념**:

  * **TF-IDF**: 설명글에서 "dice", "card", "war", "trade"처럼 게임 특징을 나타내는 단어에 높은 점수를 매겨 숫자로 바꾸는 기법.

* **세부 작업**:

  1. `clean_games.csv`의 `Description` 컬럼에 `TfidfVectorizer(max_features=1000, stop_words='english')` 적용.

  2. 전체 게임에 대해 1000개의 핵심 단어 점수표(희소 행렬) 생성.

  3. 두 게임 간의 코사인 유사도를 구하는 기본 코드 실습:

     ```
     # 예: 카탄(Catan)과 다른 모든 게임 사이의 텍스트 유사도 구하기
     similarity = cosine_similarity(game_vector, all_game_vectors)
     
     ```

  4. 결과를 검증하며 특정 게임을 넣었을 때 유사한 키워드를 가진 게임 5개가 잘 나오는지 눈으로 확인.

### 📌 4주차: 추천 함수(규칙 + 유사도) 로직 완성

> **주요 목표**: "인원수 필터"와 "유사도 정렬"을 묶은 하나의 파이썬 함수 만들기

* **사용 도구**: `pandas`, `scikit-learn`

* **세부 작업**:

  1. **1차 하드 필터링 (내가 원하는 조건만 거르기)**:

     * 예: "4명이서 할 거다" -> `BestPlayers` 또는 `Min/MaxPlayers` 범위에 4가 포함된 게임만 남김.

     * 예: "플레이 시간 60분 이하" -> 조건 만족 행만 추출.

  2. **2차 유사도 랭킹 (남은 후보군 중 가장 비슷한 순 정렬)**:

     * 기준 게임(예: '스플렌더')과 1차 필터링을 통과한 후보 게임들 간의 코사인 유사도 계산.

  3. **3차 보정 (평점이 너무 낮은 게임 제외)**:

     * `BayesAvgRating`이 최소 5.5 이상인 게임만 최종 추천.

  4. 최종 함수 입출력 정의:

     * 입력: `(기준게임명, 인원수, 최대시간)`

     * 출력: 추천 게임 5개의 딕셔너리 리스트 (이름, 이미지URL, 난이도, 예상시간).

### 📌 5주차: FastAPI 백엔드 서버 띄우기

> **주요 목표**: 4주차에 만든 파이썬 함수를 웹 주소(API)로 호출할 수 있게 만들기

* **사용 도구**: `fastapi`, `uvicorn`

* **설치**:

  ```
  conda install fastapi uvicorn -c conda-forge
  
  ```

* **세부 작업**:

  1. 가장 단순한 `main.py` 작성 및 서버 실행 (`uvicorn main:app --reload`).

  2. 두 개의 핵심 URL(엔드포인트) 작성:

     * `GET /games/search`: 게임 이름 자동완성 및 목록 검색용.

     * `POST /recommend`: 사용자가 인원, 시간, 기준 게임을 보내면 4주차 함수를 실행해 추천 결과(JSON)를 반환.

  3. 웹 브라우저에서 `http://localhost:8000/docs` (Swagger UI)를 열고, 직접 버튼을 눌러가며 정상 작동하는지 눈으로 테스트.

### 📌 6주차: React 프론트엔드 UI 만들기

> **주요 목표**: 웹 브라우저에서 조작할 수 있는 직관적인 웹 화면 구성

* **사용 도구**: `Node.js`, `React (Vite)`, `Tailwind CSS`, `axios`

* **세부 작업**:

  1. Vite로 기본 리액트 앱 생성 (`npm create vite@latest frontend -- --template react`).

  2. Tailwind CSS 기본 스타일 적용 (버튼, 카드, 레이아웃).

  3. **3대 핵심 화면 구성요소**:

     * **입력 폼**: 기준 보드게임 선택(드롭다운), 인원수 입력창(2\~6명), 플레이 시간 선택.

     * **추천받기 버튼**: 클릭 시 Axios를 통해 백엔드(`http://localhost:8000/recommend`)로 요청 전송.

     * **결과 카드 뷰**: 전달받은 JSON 데이터를 바탕으로 보드게임 표지(`ImagePath`), 이름, 난이도(`GameWeight`), 플레이 시간 렌더링.

### 📌 7주차: 화면-서버 연동, 점검 및 시연 준비

> **주요 목표**: 버그 수정, 4인 시연 및 포트폴리오용 깃허브(README) 정리

* **사용 도구**: `Git`, `GitHub`

* **세부 작업**:

  1. **연동 디버깅**: React에서 요청을 보냈을 때 백엔드 CORS 에러(도메인 차단) 처리하기.

  2. **예외 처리**: 검색 결과가 없을 때 "조건에 맞는 게임이 없습니다" 메시지 띄우기.

  3. **팀 발표/포트폴리오용 README 작성**:

     * 시스템 동작 구조 (React $\rightarrow$ FastAPI $\rightarrow$ TF-IDF/Pandas).

     * 4명의 역할 분담 내역 명시.

     * 아나콘다 실행 명령어 및 구동 스크린샷 첨부.

## 💡 프로젝트 추진 가이드 & 팁

1. **딥러닝(BERT/LLM)에 욕심내지 않기**:

   * 초기 단계에서 딥러닝 임베딩 시도 시 환경 설정 및 GPU 에러 해결로 인한 시간 낭비 방지 $\rightarrow$ `TfidfVectorizer`와 `Pandas 조건문` 활용.

2. **함수 단위로 역할 쪼개기**:

   * 파이썬 함수(`recommend_games(...)`)를 FastAPI 내부에서 그대로 호출하는 구조를 취해 협업 시 코드 충돌 최소화.