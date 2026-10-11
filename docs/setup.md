# ⚙️ 개발 환경 세팅 가이드 (Setup Guide)

<div align="center">

![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![uv](https://img.shields.io/badge/uv-0.13+-DE5FE9?style=flat-square&logo=uv&logoColor=white)
![Node.js](https://img.shields.io/badge/Node.js-v18+-339933?style=flat-square&logo=node.js&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18+-61DAFB?style=flat-square&logo=react&logoColor=black)
![Antigravity](https://img.shields.io/badge/Built%20with-Antigravity-4285F4?style=flat-square&logo=google)

<br/>

**보드게임 추천 시스템 팀 프로젝트를 원활하게 진행하기 위한 공통 개발 환경 구축 가이드입니다.**  
팀원 4명 모두 동일한 환경을 구성하여 버전 차이로 인한 버그를 미연에 방지합니다.

[🏠 메인 README로 이동](../README.md) • [📖 상세 프로젝트 계획서 보기](project_plan.md)

</div>

---

## 📌 목차
1. [사전 필수 프로그램 설치](#1-사전-필수-프로그램-설치)
2. [uv 가상환경 및 의존성 동기화 (팀원 온보딩)](#2-uv-가상환경-및-의존성-동기화-팀원-온보딩)
3. [패키지 추가 및 코드 품질 관리 (필요 시)](#3-패키지-추가-및-코드-품질-관리-필요-시)
4. [VS Code & Jupyter 개발 환경 연동](#4-vs-code--jupyter-개발-환경-연동)
5. [백엔드 환경 설정 (FastAPI, 5주차)](#5-백엔드-환경-설정-fastapi-5주차)
6. [프론트엔드 환경 설정 (React + Vite, 6주차)](#6-프론트엔드-환경-설정-react--vite-6주차)
7. [자주 묻는 질문 및 트러블슈팅 (FAQ)](#7-자주-묻는-질문-및-트러블슈팅-faq)
8. [유용한 참고 링크](#8-유용한-참고-링크)

---

## 1. 사전 필수 프로그램 설치

프로젝트 시작 전, 다음 도구들이 설치되어 있어야 합니다.

| 프로그램 | 권장 버전 | 설명 및 다운로드 |
| :--- | :--- | :--- |
| **uv** | 최신 버전 | 초고속 파이썬 패키지 및 가상환경 관리자 ([공식 문서/설치](https://docs.astral.sh/uv/)) |
| **VS Code** | 최신 버전 | 메인 코드 에디터 ([다운로드](https://code.visualstudio.com/)) |
| **Git** | 2.x 이상 | 형상 관리 및 GitHub 협업 도구 ([다운로드](https://git-scm.com/)) |
| **Node.js** | v18 이상 (LTS) | 6주차 프론트엔드 빌드 및 실행 도구 ([다운로드](https://nodejs.org/)) |

> [!NOTE]
> Rust 기반 초고속 패키지 관리자인 **`uv`**를 사용합니다. Python 3.12 바이너리 다운로드부터 가상환경 격리까지 모두 자동으로 처리됩니다.

---

## 2. uv 가상환경 및 의존성 동기화 (팀원 온보딩)

새로 저장소를 클론한 팀원은 복잡한 설정 없이 **단 한 줄의 명령어로 동일한 Python 3.12 가상환경 및 패키지를 세팅**할 수 있습니다.

```bash
# 프로젝트 루트 디렉터리(boardgame-recommender)에서 실행
uv sync
```

> [!TIP]
> - `uv sync`를 실행하면 시스템에 Python 3.12가 설치되어 있지 않아도 `uv`가 필요한 버전을 자동으로 다운로드하고 `.venv`를 생성하여 `uv.lock`에 정의된 패키지를 정확한 버전으로 설치합니다.
> - 프로젝트에 이미 `pyproject.toml`과 `uv.lock`이 구성되어 있으므로 **`uv init`은 다시 실행하지 않습니다.**
> - 가상환경을 수동 활성화(activate)하지 않아도 `uv run <명령어>`를 통해 가상환경 내에서 안전하게 스크립트를 실행할 수 있습니다.

---

## 3. 패키지 추가 및 코드 품질 관리 (필요 시)

### 3.1 신규 패키지 추가
새로운 라이브러리가 필요할 때만 아래 명령어를 사용합니다 (설치 시 `pyproject.toml`과 `uv.lock`이 자동 갱신됩니다):

```bash
# 일반 런타임 패키지 추가
uv add <패키지명>

# 개발/분석용 패키지 추가 (--dev)
uv add --dev <패키지명>
```

### 3.2 코드 품질 및 린트/포맷 검사 (Ruff)
코드 스타일 통일을 위해 초고속 린터/포매터인 `ruff`가 개발 그룹에 포함되어 있습니다:

```bash
# 코드 린트 검사
uv run ruff check .

# 코드 자동 수정 (린트 오류 자동 수정)
uv run ruff check --fix .

# 코드 포맷팅 (Black 스타일 코드 정렬)
uv run ruff format .
```

### 3.3 설치 정상 확인
아래 단일 명령어로 필수 패키지 임포트와 파이썬 버전을 테스트합니다:

```bash
uv run python -c "import pandas as pd, numpy as np, sklearn, matplotlib; print(f'Python: 3.12 | Pandas: {pd.__version__} | Scikit-Learn: {sklearn.__version__} - 환경 설정 완료!')"
```

출력 예시:
```text
Python: 3.12 | Pandas: 3.0.x | Scikit-Learn: 1.9.x - 환경 설정 완료!
```

---

## 4. VS Code & Jupyter 개발 환경 연동

### 4.1 필수 VS Code 확장 프로그램
VS Code 왼쪽 확장 탭(`Ctrl + Shift + X`)에서 아래 익스텐션을 설치합니다:
- **Python** (`ms-python.python`)
- **Jupyter** (`ms-toolsai.jupyter`)

### 4.2 주피터 노트북 커널 지정
1. VS Code에서 새 주피터 노트북(`.ipynb`)을 생성하거나 엽니다.
2. 노트북 우측 상단의 **[Select Kernel]** 버튼을 클릭합니다.
3. **[Python Environments...]** 선택 $\rightarrow$ 프로젝트 루트의 **`.venv (Python 3.12.x)`** 가상환경을 선택합니다.
4. 코드 셀을 실행(`Shift + Enter`)하여 정상 구동되는지 확인합니다.

> 💡 별도의 웹 브라우저에서 주피터 랩을 띄우려면 터미널에 `uv run jupyter lab`을 입력하세요.

---

## 5. 백엔드 환경 설정 (FastAPI, 5주차)

추천 알고리즘 함수(`recommend_games`)를 웹 API로 서빙하기 위한 프레임워크(`FastAPI`, `Uvicorn`)는 이미 `pyproject.toml`에 포함되어 있어 `uv sync` 시 함께 설치됩니다.

### 5.1 백엔드 구동 테스트 (미리보기)
프로젝트 루트 또는 `backend` 디렉토리에서 Uvicorn 서버를 실행합니다:

```bash
# 옵션 1: 프로젝트 루트에서 바로 실행 (권장)
uv run uvicorn backend.main:app --reload --port 8000

# 옵션 2: backend 디렉토리로 이동 후 실행
cd backend
uv run uvicorn main:app --reload --port 8000
```
- **서버 주소**: `http://localhost:8000`
- **인터랙티브 API 문서 (Swagger UI)**: `http://localhost:8000/docs`

---

## 6. 프론트엔드 환경 설정 (React + Vite, 6주차)

추천 웹 화면 구성을 위한 Node.js 기반 프론트엔드 세팅입니다.

### 6.1 Node.js 설치 확인
```bash
node -v   # v18.x.x 이상 확인
npm -v    # v9.x.x 이상 확인
```

### 6.2 프론트엔드 프로젝트 구동 (6주차 예정)
```bash
cd frontend
npm install
npm run dev
```
- **로컬 웹 접속 주소**: `http://localhost:5173`

---

## 7. 자주 묻는 질문 및 트러블슈팅 (FAQ)

### Q. 팀원과 동일한 패키지 버전을 유지하려면 어떻게 하나요?
**해결법**:
`uv add`로 패키지를 설치하면 `uv.lock` 파일에 정확한 의존성 버전이 기록됩니다. `uv.lock`을 Git에 커밋하고, 다른 팀원은 프로젝트 클론 후 아래 명령어를 실행하면 완벽하게 동일한 환경이 구성됩니다:
```bash
uv sync
```

### Q. Windows PowerShell에서 가상환경 활성화 시 스크립트 실행 오류가 발생해요.
**해결법**:
가상환경 활성화(`Activate.ps1`) 대신 **`uv run <명령어>`** (예: `uv run python script.py`, `uv run uvicorn main:app --reload`) 방식을 사용하면 가상환경 활성화 없이도 격리된 환경에서 안전하게 실행됩니다.

---

## 8. 유용한 참고 링크

- [uv 공식 문서](https://docs.astral.sh/uv/)
- [Pandas 공식 가이드](https://pandas.pydata.org/docs/getting_started/index.html)
- [Scikit-learn 공식 문서](https://scikit-learn.org/stable/)
- [FastAPI 공식 튜토리얼](https://fastapi.tiangolo.com/tutorial/)
- [마크다운(Markdown) 문법 정리 가이드](https://gist.github.com/ihoneymon/652be052a0727ad59601)