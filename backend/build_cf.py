"""
backend/build_cf.py
사용자 평점(data/user_ratings.csv)으로 협업 필터링 게임 벡터를 학습해 data/cf_factors.npz 로 저장

아이디어: "이 게임을 좋게 평가한 사람들이 다른 게임도 좋게 평가했는가"를 게임 벡터로 압축
1. 사용자별 평균 평점을 빼서 '그 사람 기준으로 좋았는지/별로였는지'로 바꿈 (평점 성향 제거)
2. 게임 x 사용자 희소 행렬을 Truncated SVD 로 64차원 게임 벡터로 압축
3. 두 게임 벡터의 코사인 유사도 = 취향이 겹치는 정도

평가 공정성: 사용자의 1/10 (features.is_eval_user) 은 학습에서 빼고 evaluate.py 에서만 사용

실행 (프로젝트 루트):
    uv run python -m backend.build_cf
    uv run python -m backend.build_cf --ratings 다른경로.csv --components 64
"""

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize

from backend import features

MIN_USER_RATINGS = 5  # 평점이 너무 적은 사용자는 취향 신호가 약해 제외


def load_ratings(path: Path) -> pd.DataFrame:
    ratings = pd.read_csv(
        path,
        usecols=["BGGId", "Rating", "Username"],
        dtype={"BGGId": "int32", "Rating": "float32", "Username": "string"},
    )
    return ratings.dropna()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ratings", type=Path, default=features.USER_RATINGS_PATH)
    parser.add_argument("--output", type=Path, default=features.CF_PATH)
    parser.add_argument("--components", type=int, default=64)
    args = parser.parse_args()

    if not args.ratings.exists():
        raise SystemExit(
            f"{args.ratings} 가 없습니다. Kaggle BGG 데이터셋의 user_ratings.csv 를 data/ 에 넣어 주세요."
        )

    start = time.time()
    df = features.load_games()
    ratings = load_ratings(args.ratings)
    print(f"평점 {len(ratings):,}건 로드 ({time.time() - start:.1f}초)")

    ratings = ratings[ratings["BGGId"].isin(df["BGGId"])]
    ratings = ratings[~features.is_eval_user(ratings["Username"])]
    user_counts = ratings["Username"].map(ratings["Username"].value_counts())
    ratings = ratings[user_counts.to_numpy() >= MIN_USER_RATINGS]

    item_codes = pd.Index(df["BGGId"]).get_indexer(ratings["BGGId"])
    user_codes, users = pd.factorize(ratings["Username"])
    print(f"학습 사용 평점 {len(ratings):,}건, 사용자 {len(users):,}명")

    rating_values = ratings["Rating"].to_numpy(dtype=np.float32)
    user_mean = np.bincount(user_codes, weights=rating_values) / np.bincount(user_codes)
    centered = rating_values - user_mean[user_codes].astype(np.float32)

    matrix = sparse.csr_matrix(
        (centered, (item_codes, user_codes)), shape=(len(df), len(users))
    )
    n_components = min(args.components, min(matrix.shape) - 1)
    svd = TruncatedSVD(n_components=n_components, random_state=0)
    factors = normalize(svd.fit_transform(matrix)).astype(np.float32)
    counts = np.bincount(item_codes, minlength=len(df)).astype(np.int32)
    print(f"SVD 완료: 설명 분산 {svd.explained_variance_ratio_.sum():.3f} ({time.time() - start:.1f}초)")

    rated = counts > 0
    np.savez(
        args.output,
        ids=df["BGGId"].to_numpy()[rated],
        factors=factors[rated],
        counts=counts[rated],
    )
    print(f"저장: {args.output} (게임 {rated.sum():,}개)")


if __name__ == "__main__":
    main()
