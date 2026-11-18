# 📊 데이터셋 (Dataset)

[🏠 메인 README로 이동](../README.md) • [🧠 추천 파이프라인](recommendation_pipeline.md) • [🔎 자연어 검색](natural_search.md)

[Kaggle의 BoardGameGeek 데이터셋](https://www.kaggle.com/datasets/threnjen/board-games-database-from-boardgamegeek)을 사용합니다. 원본 `games.csv` 21,925개 게임 중 정제 후 **21,125개**가 추천 대상입니다. 정제 과정은 `notebooks/clean_data.py`와 [프로젝트 계획서](project_plan.md)의 2주차 내용을 참고하세요.

## 1. 데이터 파일

| 파일 | 내용 | 만드는 방법 | git 포함 |
| :--- | :--- | :--- | :---: |
| `data/games.csv` | BGG 원본 게임 메타데이터 (카테고리 `Cat:*` 컬럼 포함) | Kaggle | ✅ |
| `data/clean_games.csv` | 정제된 13개 핵심 컬럼 (추천 엔진의 기본 데이터) | `notebooks/clean_data.py` | ✅ |
| `data/mechanics.csv`, `data/themes.csv` | 게임별 메커니즘·테마 (0/1 행렬) | Kaggle | ✅ |
| `data/embeddings.npz` | 설명글 e5 문장 임베딩 (비슷한 게임 추천용) | `backend/build_embeddings.py` | ✅ |
| `data/cf_factors.npz` | 협업 필터링 게임 벡터 | `backend/build_cf.py` | ✅ |
| `data/gemini_embeddings.npz` | 설명글 Gemini 임베딩 (자연어 검색용, 768차원) | `backend/build_gemini_embeddings.py` | ✅ |
| `data/game_profiles.json` | Gemini가 쓴 플레이 경험 프로필 + 시리즈·제작자·국가 정보 (리뷰 1,000개 이상 게임) | `backend/build_game_profiles.py` | ✅ |
| `data/profile_embeddings.npz` | 게임 프로필 임베딩 | `backend/build_profile_embeddings.py` | ✅ |
| `data/natural_eval_queries.json` | 자연어 검색 평가 질의 40개와 정답·오답 게임 | 직접 작성 | ✅ |
| `data/natural_eval_results/*.json` | 자연어 검색 평가 결과 | `backend/evaluate_natural.py` | ✅ |
| `data/user_ratings.csv` | 사용자별 평점 (수백 MB). 협업 필터링 재학습·성능 평가에만 필요 | Kaggle | ❌ 각자 다운로드 |
| `data/natural_eval_cache.json` | 평가용 의도·질의 벡터 캐시 | `evaluate_natural` 실행 시 자동 | ❌ |

- 서버는 시작할 때 있는 파일에 맞춰 기능을 켭니다. 예를 들어 `gemini_embeddings.npz`가 없으면 자연어 검색만 꺼집니다.
- 게임 데이터를 바꿨다면 위 산출물을 다시 만들어 함께 커밋해야 배포에 반영됩니다 (배포 이미지에 `data/`가 통째로 들어감).
- 각 파일을 다시 만드는 방법은 [추천 파이프라인](recommendation_pipeline.md)과 [자연어 검색](natural_search.md)을 참고하세요.

## 2. `clean_games.csv` 주요 컬럼

| 컬럼명 | 설명 | 사용처 |
| :--- | :--- | :--- |
| `BGGId` | BoardGameGeek 고유 식별자 | 게임 식별, 상세 조회 (`/games/{bgg_id}`) |
| `Name` | 보드게임 이름 (영어) | 검색, 기준 게임 지정, 자연어 검색어 속 게임 이름 감지 |
| `YearPublished` | 출시 연도 | 화면 표시, "최신" 순위 질의 |
| `GameWeight` | 체감 난이도 (1\~5) | 화면 표시, 카테고리 유사도, 자연어 검색 난이도 범위 |
| `MinPlayers` / `MaxPlayers` | 최소/최대 인원 | 인원 필터 |
| `BestPlayers` | 최적 인원 (투표 없으면 공식 인원 중간값으로 보정) | 상세 팝업 표시 |
| `ComMinPlaytime` / `ComMaxPlaytime` | 최소/최대 플레이 시간 (분) | 시간 필터 (`ComMaxPlaytime`이 0인 게임은 제외) |
| `BayesAvgRating` | 베이지안 평균 평점 | 최소 평점 필터(5.5), 최종 점수의 평점 항목, "평점 높은" 순위 질의 |
| `NumUserRatings` | 평가 참여 유저 수 | 장르 대표 게임·자연어 검색 후보 기준(1,000개 이상), "유명한" 순위 질의 |
| `Description` | 게임 설명글 (영어, 전처리됨) | TF-IDF, 임베딩, 상세 팝업 |
| `ImagePath` | 표지 이미지 URL | 카드·썸네일·시작 화면 사진 |

원본 컬럼 설명은 `data/bgg_data_documentation.txt`에 있습니다.
