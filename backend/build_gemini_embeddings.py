"""
backend/build_gemini_embeddings.py
게임 문서의 Gemini 임베딩을 미리 계산해 data/gemini_embeddings.npz 로 저장 (오프라인 작업)

실행 (프로젝트 루트, GEMINI_API_KEY 필요):
    uv run --env-file .env python -m backend.build_gemini_embeddings

100개씩 요청하고, 실패하면 최대 5번 재시도하며, 10배치마다 부분 결과를
data/gemini_embeddings.partial.npz 에 저장함. 중단 후 다시 실행하면 이어서 진행함.
"""

import argparse
import os
import time
from pathlib import Path

import numpy as np

from backend import features, gemini, semantic

BATCH_SIZE = 100
MAX_RETRIES = 5
SAVE_EVERY = 10
BACKOFF_SECONDS = 2.0


def _save(path: Path, ids: np.ndarray, vectors: np.ndarray) -> None:
    # np.savez 는 확장자가 .npz 가 아니면 덧붙이므로 파일 객체로 저장
    with open(path, "wb") as f:
        np.savez(
            f,
            ids=ids.astype(np.int64),
            vectors=vectors.astype(np.float16),
            model_name=np.str_(gemini.EMBED_MODEL),
            dim=np.int32(gemini.EMBED_DIM),
        )


def _embed_with_retry(client, docs, sleep=time.sleep) -> np.ndarray:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return client.embed_documents(docs)
        except gemini.GeminiError as e:
            if attempt == MAX_RETRIES:
                raise
            wait = BACKOFF_SECONDS * 2 ** (attempt - 1)
            print(f"  실패({e}); {wait:.0f}초 후 재시도 {attempt}/{MAX_RETRIES - 1}")
            sleep(wait)
    raise AssertionError("unreachable")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="앞쪽 N개만 처리 (테스트용)")
    parser.add_argument("--out", type=Path, default=features.GEMINI_EMBEDDINGS_PATH)
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("GEMINI_API_KEY is not set. Put it in .env and run with `uv run --env-file .env ...`.")
    client = gemini.GoogleGeminiClient(api_key)

    df = features.load_games()
    if args.limit:
        df = df.head(args.limit).reset_index(drop=True)
    mechanics = features.load_binary_features(features.MECHANICS_PATH, df["BGGId"])
    themes = features.load_binary_features(features.THEMES_PATH, df["BGGId"])
    docs = semantic.game_documents(df, mechanics, themes)
    ids = df["BGGId"].to_numpy().astype(np.int64)
    partial_path = args.out.with_suffix(".partial.npz")

    done_ids = np.empty(0, dtype=np.int64)
    done_vecs = np.empty((0, gemini.EMBED_DIM), dtype=np.float16)
    if partial_path.exists():
        with np.load(partial_path) as p:
            done_ids, done_vecs = p["ids"], p["vectors"]
        print(f"부분 결과 {len(done_ids)}개 이어서 진행")
    done_set = set(done_ids.tolist())
    todo = [i for i in range(len(ids)) if int(ids[i]) not in done_set]
    print(f"게임 {len(ids)}개 중 {len(todo)}개 임베딩 계산 (모델: {gemini.EMBED_MODEL})")

    new_ids: list[np.ndarray] = []
    new_vecs: list[np.ndarray] = []
    start = time.time()
    n_batches = (len(todo) + BATCH_SIZE - 1) // BATCH_SIZE
    for b in range(n_batches):
        chunk = todo[b * BATCH_SIZE : (b + 1) * BATCH_SIZE]
        vecs = _embed_with_retry(client, [docs[i] for i in chunk])
        if vecs.shape != (len(chunk), gemini.EMBED_DIM):
            raise SystemExit(f"Unexpected embedding shape {vecs.shape} for batch {b}")
        new_ids.append(ids[chunk])
        new_vecs.append(vecs.astype(np.float32))
        print(f"배치 {b + 1}/{n_batches} 완료 ({time.time() - start:.0f}초)")
        if (b + 1) % SAVE_EVERY == 0 and b + 1 < n_batches:
            _save(
                partial_path,
                np.concatenate([done_ids, *new_ids]),
                np.concatenate([done_vecs.astype(np.float32), *new_vecs]),
            )
            print(f"  부분 저장: {partial_path}")

    all_ids = np.concatenate([done_ids, *new_ids])
    all_vecs = np.concatenate([done_vecs.astype(np.float32), *new_vecs])
    # 원래 게임 순서로 정렬 후 L2 정규화 (float16 변환 전)
    pos = {int(g): k for k, g in enumerate(ids)}
    perm = np.argsort([pos[int(g)] for g in all_ids])
    all_ids, all_vecs = all_ids[perm], all_vecs[perm]
    all_vecs /= np.linalg.norm(all_vecs, axis=1, keepdims=True)
    assert len(all_ids) == len(ids) and np.array_equal(all_ids, ids)

    _save(args.out, all_ids, all_vecs)
    partial_path.unlink(missing_ok=True)
    print(f"저장: {args.out} ({len(all_ids)}개, {time.time() - start:.1f}초)")


if __name__ == "__main__":
    main()
