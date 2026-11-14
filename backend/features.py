"""
backend/features.py
추천에 사용하는 게임 특징(feature) 행렬을 만들고 불러오는 모듈

- 메커니즘 / 테마: data/mechanics.csv, data/themes.csv 의 0/1 표를 IDF 가중치로 변환
  (흔한 메커니즘인 'Dice Rolling'보다 드문 'Worker Placement'가 더 큰 의미를 갖게 함)
- 카테고리: games.csv 의 Cat:* 컬럼 + 난이도(GameWeight)
- 설명글 TF-IDF: 기존 방식 (임베딩이 없을 때의 대체 수단)
- 문장 임베딩(선택): backend/build_embeddings.py 로 미리 만든 data/embeddings.npz
- 협업 필터링(선택): backend/build_cf.py 로 미리 만든 data/cf_factors.npz

모든 행렬의 행 순서는 load_games()가 돌려주는 DataFrame의 행 순서와 같다.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

CLEAN_GAMES_PATH = DATA_DIR / "clean_games.csv"
RAW_GAMES_PATH = DATA_DIR / "games.csv"
MECHANICS_PATH = DATA_DIR / "mechanics.csv"
THEMES_PATH = DATA_DIR / "themes.csv"
USER_RATINGS_PATH = DATA_DIR / "user_ratings.csv"

TFIDF_CACHE_PATH = DATA_DIR / "tfidf_cache.joblib"
EMBEDDINGS_PATH = DATA_DIR / "embeddings.npz"
GEMINI_EMBEDDINGS_PATH = DATA_DIR / "gemini_embeddings.npz"
CF_PATH = DATA_DIR / "cf_factors.npz"

CATEGORY_COLUMNS = [
    "Cat:Thematic", "Cat:Strategy", "Cat:War", "Cat:Family",
    "Cat:CGS", "Cat:Abstract", "Cat:Party", "Cat:Childrens",
]

# 협업 필터링 학습에서 빼 두고 평가(evaluate.py)에만 쓰는 사용자 비율 (1/10)
EVAL_USER_MODULO = 10


def load_games() -> pd.DataFrame:
    """정제 데이터(clean_games.csv)에 원본(games.csv)의 Family·카테고리 컬럼을 붙여 반환"""
    df = pd.read_csv(CLEAN_GAMES_PATH)
    df["Description"] = df["Description"].fillna("")
    # 이미지 주소가 없는 게임(15개)이 NaN이면 JSON 변환 실패로 500 오류가 나므로 빈 문자열로 채움
    df["ImagePath"] = df["ImagePath"].fillna("")

    raw = pd.read_csv(RAW_GAMES_PATH, usecols=["BGGId", "Family", *CATEGORY_COLUMNS])
    df = df.merge(raw, on="BGGId", how="left")
    df["Family"] = df["Family"].fillna("")
    df[CATEGORY_COLUMNS] = df[CATEGORY_COLUMNS].fillna(0).astype(np.float32)
    return df.reset_index(drop=True)


def is_eval_user(usernames: pd.Series) -> np.ndarray:
    """사용자 이름으로 평가용 사용자 여부를 결정 (실행할 때마다 같은 결과)"""
    hashes = pd.util.hash_pandas_object(usernames.astype("string"), index=False)
    return (hashes.to_numpy() % EVAL_USER_MODULO) == 0


@dataclass
class BinaryFeatures:
    """0/1 특징(메커니즘·테마)과 IDF 가중치를 적용해 정규화한 행렬"""
    names: np.ndarray            # 특징 이름 (열 순서)
    binary: sparse.csr_matrix    # 게임 x 특징, 0/1
    weighted: sparse.csr_matrix  # IDF 가중 + L2 정규화 (행끼리 내적 = 코사인 유사도)
    idf: np.ndarray              # 특징별 IDF (추천 이유를 드문 특징 순으로 보여줄 때 사용)

    def shared(self, target_idx: int, other_idx: int, limit: int = 3) -> list[str]:
        """두 게임이 공통으로 가진 특징 이름을 드문 것부터 반환"""
        common = self.binary[target_idx].multiply(self.binary[other_idx]).indices
        if len(common) == 0:
            return []
        order = np.argsort(-self.idf[common])
        return [str(self.names[common[i]]) for i in order[:limit]]


def load_binary_features(path: Path, bgg_ids: pd.Series) -> BinaryFeatures:
    table = pd.read_csv(path).set_index("BGGId").reindex(bgg_ids, fill_value=0)
    binary = sparse.csr_matrix((table.to_numpy() > 0).astype(np.float32))
    # TfidfTransformer(norm="l2", smooth_idf=True)와 동일한 계산을 sklearn import 없이 수행
    n_samples = binary.shape[0]
    doc_freq = np.asarray(binary.sum(axis=0)).ravel()
    idf = np.log((1.0 + n_samples) / (1.0 + doc_freq)) + 1.0
    weighted = (binary @ sparse.diags(idf)).tocsr()
    row_norms = np.sqrt(weighted.multiply(weighted).sum(axis=1)).A1
    inv_norms = np.divide(1.0, row_norms, out=np.zeros_like(row_norms), where=row_norms > 0)
    weighted = (sparse.diags(inv_norms) @ weighted).tocsr().astype(np.float32)
    return BinaryFeatures(
        names=table.columns.to_numpy(),
        binary=binary,
        weighted=weighted,
        idf=idf,
    )


def build_category_matrix(df: pd.DataFrame) -> np.ndarray:
    """Cat:* 0/1 값을 L2 정규화 (카테고리가 없는 게임은 0 벡터)"""
    arr = df[CATEGORY_COLUMNS].to_numpy(dtype=np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    return np.divide(arr, norms, out=np.zeros_like(arr), where=norms > 0)


def load_or_compute_tfidf(df: pd.DataFrame):
    """설명글 TF-IDF 행렬 (디스크 캐시가 CSV보다 최신이면 재사용)"""
    import joblib
    from sklearn.feature_extraction.text import TfidfVectorizer

    if TFIDF_CACHE_PATH.exists():
        try:
            if TFIDF_CACHE_PATH.stat().st_mtime >= CLEAN_GAMES_PATH.stat().st_mtime:
                cached = joblib.load(TFIDF_CACHE_PATH)
                matrix = cached["tfidf_matrix"]
                if matrix.shape[0] == len(df):
                    return cached["tfidf"], matrix
        except Exception:
            pass

    vectorizer = TfidfVectorizer(stop_words="english", max_features=3000)
    matrix = vectorizer.fit_transform(df["Description"])
    try:
        joblib.dump({"tfidf": vectorizer, "tfidf_matrix": matrix}, TFIDF_CACHE_PATH)
    except Exception:
        pass
    return vectorizer, matrix


@dataclass
class Embeddings:
    vectors: np.ndarray   # 게임 x 차원, L2 정규화 (없는 게임은 0 벡터)
    baseline: float       # 임의의 두 게임 사이 평균 유사도 (이 값 이하는 0으로 봄)
    model_name: str
    present: np.ndarray   # 게임별 임베딩 존재 여부

    def rescale(self, raw: np.ndarray) -> np.ndarray:
        """임베딩 코사인은 대부분 0.7~0.9 에 몰려 있으므로 baseline~1 구간을 0~1로 펼침"""
        return np.clip((raw - self.baseline) / (1.0 - self.baseline), 0.0, 1.0)


def load_embeddings(bgg_ids: pd.Series, path: Path = EMBEDDINGS_PATH) -> Embeddings | None:
    if not path.exists():
        return None
    data = np.load(path, allow_pickle=False)
    position = pd.Series(np.arange(len(data["ids"])), index=data["ids"])
    rows = position.reindex(bgg_ids.to_numpy())
    present = rows.notna().to_numpy()
    vectors = np.zeros((len(bgg_ids), data["vectors"].shape[1]), dtype=np.float32)
    vectors[present] = data["vectors"][rows[present].astype(int).to_numpy()]
    return Embeddings(
        vectors=vectors,
        baseline=float(data["baseline"]),
        model_name=str(data["model_name"]),
        present=present,
    )


@dataclass
class CollaborativeFactors:
    factors: np.ndarray     # 게임 x 잠재요인, L2 정규화 (평점 데이터가 없는 게임은 0 벡터)
    confidence: np.ndarray  # 평점 수에 따른 신뢰도 0~1 (평점이 적으면 CF 유사도를 덜 믿음)


# 평점이 이 개수 이상이면 CF 유사도를 온전히 신뢰
CF_FULL_CONFIDENCE_RATINGS = 200


def load_cf(bgg_ids: pd.Series, path: Path = CF_PATH) -> CollaborativeFactors | None:
    if not path.exists():
        return None
    data = np.load(path, allow_pickle=False)
    position = pd.Series(np.arange(len(data["ids"])), index=data["ids"])
    rows = position.reindex(bgg_ids.to_numpy())
    present = rows.notna().to_numpy()
    picked = rows[present].astype(int).to_numpy()

    factors = np.zeros((len(bgg_ids), data["factors"].shape[1]), dtype=np.float32)
    factors[present] = data["factors"][picked]
    counts = np.zeros(len(bgg_ids), dtype=np.float32)
    counts[present] = data["counts"][picked]
    confidence = np.clip(counts / CF_FULL_CONFIDENCE_RATINGS, 0.0, 1.0)
    return CollaborativeFactors(factors=factors, confidence=confidence)
