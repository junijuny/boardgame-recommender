"""
backend/build_profile_embeddings.py
게임 프로필(data/game_profiles.json)의 Gemini 임베딩을 계산해 data/profile_embeddings.npz 로 저장 (오프라인 작업)

실행 (프로젝트 루트, GEMINI_API_KEY 필요):
    uv run --env-file .env python -m backend.build_profile_embeddings

문서 = 프로필 + 메커니즘 + 테마 + 설명글 앞 600자. 배치·재시도·부분 저장은 build_gemini_embeddings 와 같다.
"""

import argparse
import os
from pathlib import Path

import numpy as np

from backend import features, gemini, profiles
from backend.build_gemini_embeddings import embed_all

DOC_VERSION = 1
DESCRIPTION_CHARS = 600


def profile_documents(game_profiles: dict[int, dict]) -> tuple[np.ndarray, list[tuple[str, str]]]:
    """프로필이 있는 게임(리뷰 많은 순서는 무관, df 순서)의 (ids, [(이름, 본문)])"""
    df = features.load_games()
    df = df[df["BGGId"].isin(game_profiles.keys())].reset_index(drop=True)
    mechanics = features.load_binary_features(features.MECHANICS_PATH, df["BGGId"])
    themes = features.load_binary_features(features.THEMES_PATH, df["BGGId"])
    docs = []
    for i, row in enumerate(df.itertuples(index=False)):
        mech = ", ".join(mechanics.names[mechanics.binary[i].indices])
        theme = ", ".join(themes.names[themes.binary[i].indices])
        body = f"{game_profiles[int(row.BGGId)]['profile']} Mechanics: {mech}. Themes: {theme}. {str(row.Description)[:DESCRIPTION_CHARS]}"
        docs.append((row.Name, body))
    return df["BGGId"].to_numpy().astype(np.int64), docs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="앞쪽 N개만 처리 (테스트용)")
    parser.add_argument("--out", type=Path, default=features.PROFILE_EMBEDDINGS_PATH)
    args = parser.parse_args()
    if args.limit and args.out == features.PROFILE_EMBEDDINGS_PATH:
        parser.error("--limit requires --out so the committed embeddings are not overwritten")
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("GEMINI_API_KEY is not set. Put it in .env and run with `uv run --env-file .env ...`.")
    if not profiles.PROFILES:
        raise SystemExit("data/game_profiles.json is missing or empty. Run backend.build_game_profiles first.")
    client = gemini.GoogleGeminiClient(api_key)

    ids, docs = profile_documents(profiles.PROFILES)
    if args.limit:
        ids, docs = ids[: args.limit], docs[: args.limit]
    embed_all(client, ids, docs, args.out, extra={"doc_version": np.int32(DOC_VERSION)})


if __name__ == "__main__":
    main()
