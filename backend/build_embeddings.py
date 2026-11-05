"""
backend/build_embeddings.py
게임 문서(이름 + 메커니즘 + 테마 + 설명글)의 문장 임베딩을 미리 계산해 data/embeddings.npz 로 저장

실행 (프로젝트 루트):
    uv sync --extra semantic
    uv run --extra semantic python -m backend.build_embeddings

GPU가 있으면 자동으로 사용하고, 없으면 CPU로 계산함 (CPU 기준 수 분 소요).
저장 후 서버를 다시 시작하면 추천의 텍스트 신호가 TF-IDF 대신 임베딩으로 바뀌고
/games/semantic-search (자연어 검색) 가 활성화됨.
"""

import time

import numpy as np

from backend import features, semantic


def main() -> None:
    if not semantic.is_installed():
        raise SystemExit(
            "sentence-transformers 가 설치되어 있지 않습니다. "
            "먼저 `uv sync --extra semantic` 을 실행하세요."
        )

    df = features.load_games()
    mechanics = features.load_binary_features(features.MECHANICS_PATH, df["BGGId"])
    themes = features.load_binary_features(features.THEMES_PATH, df["BGGId"])
    passages = semantic.build_passages(df, mechanics, themes)
    print(f"게임 {len(passages)}개 임베딩 계산 (모델: {semantic.MODEL_NAME})")

    start = time.time()
    vectors = semantic.encode_passages(passages)
    print(f"완료: {vectors.shape}, {time.time() - start:.1f}초")

    # 임의의 두 게임 사이 평균 유사도 → 추천에서 이 값 이하는 '관련 없음(0)'으로 취급
    rng = np.random.default_rng(0)
    a = rng.integers(0, len(vectors), 50_000)
    b = rng.integers(0, len(vectors), 50_000)
    baseline = float(np.mean(np.sum(vectors[a] * vectors[b], axis=1)))
    print(f"임의 쌍 평균 유사도(baseline): {baseline:.4f}")

    np.savez(
        features.EMBEDDINGS_PATH,
        ids=df["BGGId"].to_numpy(),
        vectors=vectors,
        baseline=np.float32(baseline),
        model_name=np.str_(semantic.MODEL_NAME),
    )
    print(f"저장: {features.EMBEDDINGS_PATH}")


if __name__ == "__main__":
    main()
