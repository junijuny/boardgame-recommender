"""
backend/evaluate.py
추천 방식별 성능을 실제 사용자 평점으로 비교하는 오프라인 평가 스크립트

방법 (leave-one-out):
- 협업 필터링 학습에서 제외된 평가용 사용자(features.is_eval_user) 중
  8점 이상 준 게임이 5개 이상인 사용자를 뽑음
- 그중 게임 하나를 '기준 게임'으로 주고 Top K 추천을 받음
- 그 사용자가 8점 이상 준 나머지 게임이 추천에 얼마나 들어있는지 측정

지표:
- HitRate@K : 추천 K개 중 하나라도 맞힌 사용자 비율
- Recall@K  : 맞힌 개수 / min(K, 정답 개수)
- NDCG@K    : 맞힌 게임이 위쪽에 있을수록 높은 점수
- Coverage  : 전체 사용자에게 추천된 서로 다른 게임 수 / 후보 게임 수 (낮으면 인기 게임만 반복)

실행 (프로젝트 루트):
    uv run python -m backend.evaluate --users 1000 --k 10
"""

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd

from backend import build_cf, features
from backend import recommend_engine as engine

LIKE_THRESHOLD = 8.0
MIN_LIKED = 5
MIN_RATING = 5.5  # 실제 서비스와 같은 최소 평점 후보 조건


def strategies() -> dict:
    """비교할 추천 방식. 데이터가 준비된 단계까지만 포함"""
    w = engine.SIGNAL_WEIGHTS
    stage1 = {k: w[k] for k in ("mechanics", "themes", "category")} | {"tfidf": w["text"]}
    result = {
        "popular (평점순)": None,
        "tfidf (기존 방식)": {"weights": {"tfidf": 1.0}, "rating_weight": 0.0,
                              "variant_penalty": 0.0, "diversity": 0.0},
        "stage1 (+메커니즘/테마)": {"weights": stage1},
    }
    if engine.embeddings is not None:
        stage2 = {k: v for k, v in stage1.items() if k != "tfidf"} | {"embedding": w["text"]}
        result["stage2 (+임베딩)"] = {"weights": stage2}
    if engine.cf is not None:
        base = result.get("stage2 (+임베딩)", result["stage1 (+메커니즘/테마)"])["weights"]
        result["stage3 (+협업필터링)"] = {"weights": base | {"cf": w["cf"]}}
        result["cf only"] = {"weights": {"cf": 1.0}, "rating_weight": 0.0,
                                 "variant_penalty": 0.0, "diversity": 0.0}
    return result


def recommend_for_eval(seed_idx, cand_idx, k, config):
    pool = cand_idx[cand_idx != seed_idx]
    if config is None:  # 평점순 기준선
        order = np.argsort(-engine._ratings[pool], kind="stable")[:k]
        return pool[order]
    _, score = engine.score_candidates(
        seed_idx, pool, config["weights"],
        rating_weight=config.get("rating_weight", engine.RATING_WEIGHT),
        variant_penalty=config.get("variant_penalty", engine.VARIANT_PENALTY),
    )
    picked = engine.diversify(pool, score, k, diversity=config.get("diversity", engine.DIVERSITY))
    return pool[picked]


def build_eval_cases(ratings_path: Path, n_users: int, seed: int):
    ratings = build_cf.load_ratings(ratings_path)
    ratings = ratings[ratings["Rating"] >= LIKE_THRESHOLD]
    ratings = ratings[features.is_eval_user(ratings["Username"])]

    position = pd.Series(np.arange(len(engine.df)), index=engine.df["BGGId"])
    ratings = ratings[ratings["BGGId"].isin(position.index)]
    ratings["idx"] = position.reindex(ratings["BGGId"]).to_numpy()

    candidate = engine._ratings >= MIN_RATING
    liked_by_user = ratings.groupby("Username")["idx"].apply(np.array)
    liked_by_user = liked_by_user[liked_by_user.map(len) >= MIN_LIKED]

    rng = np.random.default_rng(seed)
    users = rng.permutation(len(liked_by_user))[:n_users]
    cases = []
    for u in users:
        liked = liked_by_user.iloc[u]
        seed_idx = int(rng.choice(liked))
        relevant = {int(i) for i in liked if i != seed_idx and candidate[i]}
        if relevant:
            cases.append((seed_idx, relevant))
    return cases, np.flatnonzero(candidate)


def evaluate(cases, cand_idx, k, config):
    hits, recalls, ndcgs = [], [], []
    recommended = set()
    discounts = 1.0 / np.log2(np.arange(2, k + 2))
    for seed_idx, relevant in cases:
        recs = recommend_for_eval(seed_idx, cand_idx, k, config)
        recommended.update(int(i) for i in recs)
        gains = np.array([1.0 if int(i) in relevant else 0.0 for i in recs])
        n_hit = gains.sum()
        hits.append(n_hit > 0)
        recalls.append(n_hit / min(k, len(relevant)))
        ideal = discounts[: min(k, len(relevant))].sum()
        ndcgs.append((gains * discounts[: len(gains)]).sum() / ideal)
    return {
        f"HitRate@{k}": np.mean(hits),
        f"Recall@{k}": np.mean(recalls),
        f"NDCG@{k}": np.mean(ndcgs),
        "Coverage": len(recommended) / len(cand_idx),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ratings", type=Path, default=features.USER_RATINGS_PATH)
    parser.add_argument("--users", type=int, default=1000)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    if not args.ratings.exists():
        raise SystemExit(
            f"{args.ratings} 가 없습니다. Kaggle BGG 데이터셋의 user_ratings.csv 를 data/ 에 넣어 주세요."
        )

    cases, cand_idx = build_eval_cases(args.ratings, args.users, args.seed)
    print(f"평가 사용자 {len(cases)}명, 후보 게임 {len(cand_idx)}개, K={args.k}\n")

    rows = {}
    for name, config in strategies().items():
        start = time.time()
        rows[name] = evaluate(cases, cand_idx, args.k, config)
        print(f"- {name}: {time.time() - start:.1f}초")

    table = pd.DataFrame(rows).T
    print()
    print(table.to_string(float_format=lambda x: f"{x:.4f}"))


if __name__ == "__main__":
    main()
