# 자연어 게임 검색 + "왜 이 게임인지" 설명 설계

- 작성일: 2026-11-14
- 상태: 승인됨 (2026-11-15)

## 1. 의도와 이유

사용자가 보드게임 **이름을 몰라도**, "이런 특징의 게임을 하고 싶다"는 추상적인 생각만으로 알맞은 게임을 찾을 수 있게 한다.
예: "4명이서 1시간 안에 끝나는, 주사위 없는 협력 게임", "a tense game where players secretly betray each other".

또한 추천 결과마다 **"왜 이 게임인지" 한 문장**을 붙여, 결과를 믿고 고를 수 있게 한다. 이 설명은 새 자연어 검색과 기존 "Find similar games" 추천 양쪽에 붙는다.

대상 사용자는 **서양 문화권 사용자**다 (데이터셋 원본이 BoardGameGeek). 그래서 화면과 설명 문장은 모두 **영어**다. 단 검색어는 **한국어와 영어 모두** 받는다.

## 2. 목표 / 비목표 / 실패 기준

### 목표
1. 추천 화면에 자연어 검색 추가: 검색어 칸 + 인원·시간 선택 (지금 추천 화면과 같은 선택지)
2. 자연어 검색 결과 5개와 "Find similar games" 결과 5개 모두에 영어 설명 한 문장 표시
3. 한국어·영어 검색어 모두 동작
4. 배포 서버(Cloud Run)를 지금처럼 가볍게 유지 (torch 등 무거운 패키지 추가 없음)

### 비목표 (이번 범위 밖)
- 검색어 안의 기준 게임 인식 ("카탄 같은데 더 가벼운"). 기준 게임이 있으면 "By game" 탭을 쓰면 된다
- 장르 화면 결과에 설명 붙이기
- 대화형(여러 턴) 검색, 검색 기록 저장
- 기존 `GET /games/semantic-search`(e5 기반) 수정 또는 삭제. 그대로 둔다
- 외부 웹 검색이나 BGG 리뷰 크롤링 같은 추가 지식 소스

### 실패 기준 (동작은 해도 실패로 보는 경우)
- Gemini API 키가 프론트엔드 코드나 브라우저에 노출됨
- Gemini 키가 없거나 Gemini가 장애일 때 **기존 기능**(게임 이름 검색, 비슷한 게임 추천, 장르 화면)이 깨짐
- 설명 문장이 데이터에 없는 사실을 지어냄 (예: 없는 메커니즘 언급)
- 화면에 한국어 문장이 섞여 나옴
- 공개 API가 무제한 호출되어 Gemini 요금이 통제 없이 늘어남

## 3. 제약

- 백엔드: Python 3.12, FastAPI, uv. Cloud Run (메모리 1Gi, CPU 1, 최대 인스턴스 2, 최소 0)
- 프론트엔드: React 19 + Vite + Tailwind 4 + TanStack Query, Vercel 배포
- 데이터: 게임 21,125개 (`data/clean_games.csv`), 메커니즘 160개·테마 219개 이진 행렬 (`mechanics.csv`, `themes.csv`)
- 데이터 파일은 git에 커밋되어 배포 이미지에 들어감 (GitHub 파일당 100MB 제한)
- CI(`.github/workflows/test.yml`)에는 Gemini 키가 없음. 테스트는 Gemini 없이 통과해야 함
- LLM 제공자는 **Gemini API** (사용자 결정)

## 4. 검토한 방법

| 방법 | 내용 | 장점 | 단점 |
| --- | --- | --- | --- |
| A. 조건 추출 + 기존 e5 임베딩 | Gemini가 조건을 뽑고, 질의는 서버에 올린 e5 모델로 벡터화 | 기존 `embeddings.npz` 재사용 | Cloud Run에 torch 탑재 → 이미지·메모리·콜드스타트 증가 |
| **B. 조건 추출 + Gemini 임베딩 (선택)** | Gemini가 조건을 뽑고, 질의·문서 모두 Gemini 임베딩으로 벡터화. 문서 임베딩은 한 번 일괄 계산해 저장 | 서버 가벼움 유지, RAG 구조가 가장 깔끔, 다국어 질의에 강함 | 처음에 21,125개 일괄 임베딩 필요, 검색 1회에 Gemini 호출 3번 |
| C. 조건 추출만 | Gemini가 문장을 메커니즘·테마 태그로만 변환 | 가장 단순, 호출 1번 | 태그로 표현 안 되는 "느낌"을 놓침 → 목표에 가장 약함 |

**사용자가 B를 선택.** 이유: 추상적 표현은 임베딩이, 명확한 조건(제외 메커니즘, 난이도)은 필터가 맡아 목표에 가장 맞고, 배포 부담이 늘지 않는다.

## 5. 결정된 동작

### 5.1 화면 (추천 화면에 탭 추가)

추천 화면(`RecommendScreen`) 상단에 탭 두 개를 둔다. 메뉴에 화면을 늘리지 않고, 결과 카드·Refresh·상세 팝업을 재사용한다.

```
[ By game ]  [ By description ]
┌──────────────────────────────────────────────────┐
│ e.g. a cooperative game with no dice, under 1 hour│
└──────────────────────────────────────────────────┘
Players  (2)(3)(4)(5)(6)     Time  (30m)(1h)(1.5h)(2h)
[ Get recommendations ]

┌ 🖼 Spirit Island ─────────────────────────────────┐
│ 1-4p · 90-120m · ●●●○○ · 8.1                       │
│ "A fully cooperative island-defense game with no   │
│  dice, where the team plans every move together."  │  ← 설명 한 문장
└────────────────────────────────────────────────────┘
```

- "By game" 탭: 지금 화면 그대로 + 각 카드에 설명 한 문장 추가
- "By description" 탭: 검색어 칸(여러 줄 아님, 한 줄 입력) + 인원·시간 선택(`PLAYER_OPTIONS`, `TIME_OPTIONS` 그대로) + 버튼
- 두 탭 모두 결과 5개, "Refresh"로 본 게임을 빼고 다음 5개
- 화면의 모든 글자는 영어

### 5.2 자연어 검색 흐름 (`POST /search/natural`)

요청: `{ query: str, players: int, max_time: int, exclude_ids?: int[] }`

1. **질의 이해 (Gemini 생성 모델, 구조화 출력)**
   검색어(한국어/영어)를 아래 JSON으로 변환. 메커니즘·테마 이름은 우리 데이터의 이름 목록 안에서만 고르도록 스키마의 enum으로 제한한다.
   ```json
   {
     "search_text": "English description of the desired play experience",
     "include_mechanics": ["Cooperative Game"],
     "exclude_mechanics": ["Dice Rolling"],
     "include_themes": [],
     "exclude_themes": [],
     "weight_min": null,
     "weight_max": 2.5
   }
   ```
   - 인원·시간은 **화면 선택값만** 쓴다 (화면이 항상 값을 보내므로 질의에서 뽑지 않는다)
   - `weight`는 BGG 난이도 1~5. "가벼운/light" 같은 표현을 범위로 바꾼다
   - 같은 검색어의 결과는 캐시해서 Refresh 때 다시 호출하지 않는다
2. **하드 필터**: 기존 조건(`_condition_mask`: 인원, 최대 시간, 평점 ≥ 5.5) + `exclude_mechanics`/`exclude_themes`를 가진 게임 제외 + 난이도 범위 + `exclude_ids` 제외
3. **질의 임베딩 (Gemini 임베딩 모델)**: `search_text`를 검색 질의용으로 벡터화 → 후보 문서 벡터와 코사인 유사도
4. **점수**: 임베딩 유사도(후보 중앙값~최댓값을 0~1로 환산, 기존 `semantic_search`와 같은 방식)에 `include_*` 태그 일치 비율을 더해 유사도를 만들고, 기존과 같이 `0.75·유사도 + 0.25·평점`. 시작 가중치는 `유사도 = 0.8·임베딩 + 0.2·태그 일치`(태그 조건이 없으면 임베딩만). 튜닝은 구현자 판단
5. **다양성 재정렬**: 기존 `diversify`(MMR)로 5개 선택
6. 응답: 기존 추천 결과와 같은 게임 필드 + `Similarity`, `Score`, `MatchedMechanics`, `MatchedThemes`(질의의 include 태그 중 이 게임이 가진 것, 설명 실패 시 칩으로 표시). 결과가 없으면 `404 "No games match the selected conditions"` (기존 `/recommend`와 같음)

### 5.3 설명 문장 (`POST /explain`)

결과 카드가 먼저 보이고, 설명은 별도 요청으로 받아 1~2초 뒤 채운다.

요청: `{ mode: "similar" | "query", basis: str, game_ids: int[] }`
- `mode="similar"`: `basis`는 기준 게임 이름. "기준 게임과 무엇이 닮았는지"를 근거로 설명
- `mode="query"`: `basis`는 사용자 검색어. "검색어의 어떤 바람에 맞는지"를 근거로 설명

응답: `{ reasons: { "<BGGId>": "One English sentence." } }`

- Gemini 한 번 호출로 5개 설명을 구조화 JSON으로 받는다
- 프롬프트에는 각 게임의 이름, 메커니즘, 테마, 난이도, 인원, 시간, 설명글 앞부분만 넣고 **주어진 정보만 근거로** 쓰도록 지시한다 (지어내기 방지). `similar` 모드는 기준 게임의 같은 정보도 넣는다
- 출력은 항상 영어, 한 문장, 약 25단어 이내
- `(mode, basis, BGGId)` 단위로 캐시
- 실패하면 프론트는 설명 없이 결과를 그대로 두고, 기존 공통 메커니즘 칩(`SharedMechanics` 또는 `MatchedMechanics`)으로 대신한다

### 5.4 데이터 준비 (일괄 임베딩)

- 새 스크립트 `backend/build_gemini_embeddings.py` → `data/gemini_embeddings.npz` (`ids`, `vectors`, `model_name`, 차원)
- 문서 내용은 기존 `semantic.build_passages`와 같은 "이름 + 메커니즘 + 테마 + 설명글" (e5용 `passage: ` 접두어는 빼고)
- `gemini-embedding-2`는 `task_type` 파라미터를 지원하지 않는다. 대신 텍스트 앞 접두어로 질의와 문서를 구분한다 (공식 문서의 비대칭 검색 형식):
  - 문서: `title: {게임 이름} | text: {메커니즘·테마·설명글}`
  - 질의: `task: search result | query: {search_text}`
- 문서와 질의는 **반드시 같은 모델·같은 차원**이어야 한다. 모델 ID와 차원을 npz에 저장하고, 서버 시작 시 상수와 다르면 자연어 검색을 끈다
- 여러 문서를 한 요청으로 보낼 때는 문서마다 별도 `Content`로 감싸야 한다 (한 `contents` 배열에 문자열을 나열하면 하나로 합쳐진 임베딩이 나옴)
- 차원은 768로 줄여 저장 (파일 크기 약 32~65MB, float16/float32에 따라). `gemini-embedding-2`는 줄인 차원을 자동 정규화하지만, 저장 전 한 번 더 정규화해도 무방
- 일괄 임베딩 예상 비용: 약 850만 토큰 × $0.20/1M ≈ $1.7 (Batch API 사용 시 절반)
- 기존 `embeddings.npz`(e5)는 "Find similar games"용으로 그대로 둔다
- 개발 중 실제 Gemini 키를 쓸 수 있다 (사용자 확인). 구현 과정에서 일괄 임베딩을 실제로 실행하고, 결과 파일을 **기능과 같은 PR에** 커밋한다. 그래서 main에 합쳐질 때 파일이 없는 상태로 배포되는 일이 없다
- 스크립트는 속도 제한에 맞게 배치·재시도·중간 저장(이어서 실행)을 지원

### 5.5 Gemini 연동과 운영

- Python 패키지는 Google 공식 `google-genai` SDK를 쓴다
- **모델 (사용자 결정, 2026-11-15 공식 문서 기준 확인):**
  - 조건 추출·설명 문장: `gemini-3.5-flash-lite` (Stable, 입력 $0.30 / 출력 $2.50 per 1M). 작업별 상수(`EXTRACT_MODEL`, `EXPLAIN_MODEL`)로 따로 둬서, 품질이 부족한 작업만 `gemini-3.8-flash`로 바꿀 수 있게 한다
  - 임베딩: `gemini-embedding-2` (Stable, 텍스트 $0.20 per 1M)
  - 사고(thinking) 토큰도 출력 요금이므로 두 생성 작업 모두 사고 수준을 최소로 설정
  - 쓰지 않을 모델: `gemini-2.5-flash` (deprecated, 2026-12-01부터 자동 전환), `gemini-embedding-001` (2028-05 종료 예정)
- 구조화 출력에서 메커니즘·테마 379개 enum 스키마가 받아들여지는지 개발 첫 단계에서 실제 키로 확인한다. 안 되면 태그 목록을 프롬프트에 넣고, 응답의 태그 이름을 서버에서 검증해 목록에 없는 것은 버린다
- 예상 비용: 검색 1회(추출 + 질의 임베딩 + 설명) 약 $0.003 (추정)
- **요금제: 유료 결제 (사용자 결정).** 무료 등급 한도를 전제로 설계하지 않는다
- API 키는 백엔드 환경 변수 `GEMINI_API_KEY`에만 둔다. 프론트에는 절대 넣지 않는다
- **배포 시 키 전달: GitHub Actions 시크릿 (사용자 결정, 방법 b).**
  - 저장소 시크릿 이름 `GEMINI_API_KEY`
  - `deploy-backend.yml`의 `--set-env-vars`에 `GEMINI_API_KEY=${{ secrets.GEMINI_API_KEY }}`를 `ALLOWED_ORIGINS`와 함께 넣는다. 이 플래그는 기존 환경 변수를 모두 덮어쓰므로, 콘솔에서 손으로 넣은 값은 유지되지 않는다
  - 사용자가 GitHub 저장소 설정에서 시크릿을 먼저 등록해야 한다. 등록 전에 배포되면 키가 비어서 새 기능만 `503`이고, 기존 기능은 정상이다
  - 키는 Cloud Run 서비스에 일반 환경 변수로 보인다는 점을 받아들인다
- 키가 없거나 `gemini_embeddings.npz`가 없으면 `/search/natural`, `/explain`은 `503`을 돌려주고, 나머지 API는 그대로 동작. `GET /`의 응답에 `natural_search: bool` 추가. 프론트는 이 값이 `false`이면 "By description" 탭을 숨기고 설명 요청도 보내지 않는다
- Gemini 호출 실패(타임아웃, 한도 초과): `/search/natural`은 `503`과 영어 메시지, `/explain`은 `503` (프론트가 조용히 대체)
- 남용·비용 방지 (둘 다 서버 메모리 기반, 초과 시 `429`):
  - IP별 제한: `/search/natural` 분당 10회, `/explain` 분당 30회. Cloud Run에서는 `X-Forwarded-For`로 IP 확인
  - **전체 일일 상한**: 인스턴스당 Gemini 호출 하루 2,000회 (UTC 자정 초기화, 환경 변수로 조정 가능). 인스턴스가 최대 2개라 전체로는 하루 약 4,000회 이하. 상한에 닿으면 새 기능만 `429`/`503`, 기존 기능은 정상 *(구현자 판단으로 정한 시작값. 사용자가 바꿀 수 있음)*
- 캐시: 서버 메모리 LRU (질의 이해 결과, 설명). 인스턴스가 최대 2개라 메모리 캐시로 충분
- 타임아웃: Gemini 호출당 약 10초

### 5.6 테스트

- Gemini 호출부는 한 모듈(예: `backend/gemini.py`)에 모으고, 테스트에서는 가짜(fake) 클라이언트로 바꿔 끼운다. CI에서 실제 호출 없음
- 개발 중에는 실제 키로 확인한다: 메커니즘·테마 enum 스키마가 받아들여지는지, 한국어·영어 질의의 조건 추출, 설명이 영어 한 문장이고 데이터에 근거하는지, 모델 ID
- 백엔드 테스트: 필터·제외 조건 적용, 결과 5개·`exclude_ids`, 키 없을 때 503, 기존 API 무영향, 호출 제한 429, 설명 응답 형식, Gemini 실패 시 동작
- 테스트용 작은 가짜 임베딩 파일 또는 메모리상 벡터 사용

### 5.7 문서

- `docs/backend_api.md`: 새 엔드포인트 2개
- `docs/recommendation_pipeline.md`: 자연어 검색 단계
- `docs/setup.md`, `docs/deploy.md`: `GEMINI_API_KEY`, 일괄 임베딩 실행 방법, Cloud Run 설정
- `README.md` 주요 기능 표

## 6. 구현자에게 맡기는 것

- 점수 가중치의 세부 튜닝 (시작값은 5.2)
- 질의 이해·설명 프롬프트 문구
- 호출 제한 수치, 캐시 크기
- 탭 UI의 세부 모양 (기존 디자인 토큰과 컴포넌트 재사용)
- 질의 이해 결과(뽑힌 조건)를 응답에 디버그용으로 포함할지 여부
- 난이도 정보가 없는 게임의 처리 (시작안: 난이도 조건이 있어도 제외하지 않음)
- `/explain` 입력 검증 (`game_ids` 최대 개수, `basis` 길이 제한), `X-Forwarded-For`에서 어느 값을 믿을지
- 임베딩 저장 형식 (float16/float32)
