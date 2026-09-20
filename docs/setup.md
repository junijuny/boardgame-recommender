# ⚙️ 개발 환경 세팅 가이드 (Setup Guide)

<div align="center">

![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![Conda](https://img.shields.io/badge/Conda-bg__rec-44A833?style=flat-square&logo=anaconda&logoColor=white)
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
2. [Conda 가상환경 구축 (Python 3.12)](#2-conda-가상환경-구축-python-312)
3. [데이터 분석 및 머신러닝 패키지 설치 (1~4주차)](#3-데이터-분석-및-머신러닝-패키지-설치-14주차)
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
| **Miniconda** (또는 Anaconda) | 최신 버전 | 가벼운 파이썬 패키지 및 가상환경 관리자 ([다운로드](https://docs.conda.io/en/latest/miniconda.html)) |
| **VS Code** | 최신 버전 | 메인 코드 에디터 ([다운로드](https://code.visualstudio.com/)) |
| **Git** | 2.x 이상 | 형상 관리 및 GitHub 협업 도구 ([다운로드](https://git-scm.com/)) |
| **Node.js** | v18 이상 (LTS) | 6주차 프론트엔드 빌드 및 실행 도구 ([다운로드](https://nodejs.org/)) |

> [!NOTE]
> Anaconda 전체 설치 파일(약 3GB+) 대신, 핵심 기능만 담긴 가벼운 **Miniconda**(약 100MB) 설치를 적극 권장합니다.

---

## 2. Conda 가상환경 구축 (Python 3.12)

터미널(Windows: PowerShell 또는 Anaconda Prompt, macOS: Terminal)을 열고 아래 명령어를 순서대로 실행합니다.

### 2.1 가상환경 생성
가상환경 이름은 일관성을 위해 `bg_rec`으로 통일합니다.

```bash
# Python 3.12 기반 bg_rec 가상환경 생성
conda create -n bg_rec python=3.12 -y
```

### 2.2 가상환경 활성화
```bash
conda activate bg_rec
```

> [!TIP]
> 활성화가 정상적으로 이루어지면 터미널 프롬프트 앞부분이 `(base)`에서 `(bg_rec)`으로 변경됩니다.

---

## 3. 데이터 분석 및 머신러닝 패키지 설치 (1~4주차)

`clean_games.csv` 전처리, EDA, 그리고 TF-IDF 코사인 유사도 분석에 필요한 핵심 패키지를 설치합니다.

```bash
# 가상환경 활성화 확인 후 실행
conda activate bg_rec

# conda-forge 채널을 통한 핵심 패키지 일괄 설치
conda install -c conda-forge pandas numpy matplotlib scikit-learn jupyterlab -y
```

### 3.1 설치 정상 확인
아래 단일 명령어로 필수 패키지 임포트와 파이썬 버전을 테스트합니다:

```bash
python -c "import pandas as pd, numpy as np, sklearn, matplotlib; print(f'Python: 3.12 | Pandas: {pd.__version__} | Scikit-Learn: {sklearn.__version__} - 환경 설정 완료!')"
```

출력 예시:
```text
Python: 3.12 | Pandas: 2.2.x | Scikit-Learn: 1.4.x - 환경 설정 완료!
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
3. **[Python Environments...]** 선택 $\rightarrow$ 위에서 생성한 **`bg_rec (Python 3.12.x)`** 가상환경을 선택합니다.
4. 코드 셀을 실행(`Shift + Enter`)하여 정상 구동되는지 확인합니다.

> 💡 별도의 웹 브라우저에서 주피터 랩을 띄우려면 터미널에 `jupyter lab`을 입력하세요.

---

## 5. 백엔드 환경 설정 (FastAPI, 5주차)

추천 알고리즘 함수(`recommend_games`)를 웹 API로 서빙하기 위한 프레임워크를 설치합니다.

```bash
# 가상환경 활성화
conda activate bg_rec

# FastAPI 및 ASGI 서버 Uvicorn 설치
conda install -c conda-forge fastapi uvicorn -y
```

### 5.1 백엔드 구동 테스트 (미리보기)
```bash
# 추후 backend 디렉토리 이동 후 실행
cd backend
uvicorn main:app --reload --port 8000
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

### Q. 패키지 설치 시 `PackagesNotFoundError` 또는 충돌이 발생해요.
**해결법**:
`pip`와 `conda`를 무분별하게 혼용하면 의존성이 꼬일 수 있습니다. 본 프로젝트에서는 가급적 **`-c conda-forge`** 옵션을 통한 conda 설치를 우선해 주세요.

---

## 8. 유용한 참고 링크

- [Miniconda 공식 설치 문서](https://docs.conda.io/projects/miniconda/en/latest/)
- [Pandas 공식 가이드](https://pandas.pydata.org/docs/getting_started/index.html)
- [Scikit-learn 공식 문서](https://scikit-learn.org/stable/)
- [FastAPI 공식 튜토리얼](https://fastapi.tiangolo.com/tutorial/)
- [마크다운(Markdown) 문법 정리 가이드](https://gist.github.com/ihoneymon/652be052a0727ad59601)