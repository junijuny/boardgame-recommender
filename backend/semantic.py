"""
backend/semantic.py
문장 임베딩 모델 관련 공통 코드 (임베딩 생성 스크립트와 자연어 검색 API가 함께 사용)

sentence-transformers 는 선택 설치 패키지이므로 이 모듈은 필요할 때만 import 한다.
설치: uv sync --extra semantic
"""

import importlib.util
import threading

import numpy as np
import pandas as pd

MODEL_NAME = "intfloat/multilingual-e5-small"
PASSAGE_PREFIX = "passage: "
QUERY_PREFIX = "query: "
MAX_DESCRIPTION_CHARS = 1500

_model = None
_model_lock = threading.Lock()


def is_installed() -> bool:
    return importlib.util.find_spec("sentence_transformers") is not None


def game_documents(df: pd.DataFrame, mechanics, themes) -> list[tuple[str, str]]:
    mech_names = mechanics.names
    theme_names = themes.names
    docs = []
    for i, row in enumerate(df.itertuples(index=False)):
        mech = ", ".join(mech_names[mechanics.binary[i].indices])
        theme = ", ".join(theme_names[themes.binary[i].indices])
        parts = []
        if mech:
            parts.append(f"Mechanics: {mech}.")
        if theme:
            parts.append(f"Themes: {theme}.")
        parts.append(str(row.Description)[:MAX_DESCRIPTION_CHARS])
        docs.append((row.Name, " ".join(parts)))
    return docs


def build_passages(df: pd.DataFrame, mechanics, themes) -> list[str]:
    return [
        f"{PASSAGE_PREFIX}{name}. {body}"
        for name, body in game_documents(df, mechanics, themes)
    ]


def load_model(device: str | None = None):
    global _model
    with _model_lock:
        if _model is None:
            from sentence_transformers import SentenceTransformer

            if device is None:
                import torch

                device = "cuda" if torch.cuda.is_available() else "cpu"
            _model = SentenceTransformer(MODEL_NAME, device=device)
        return _model


def encode_passages(passages: list[str], batch_size: int = 64) -> np.ndarray:
    model = load_model()
    vectors = model.encode(
        passages,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=True,
        convert_to_numpy=True,
    )
    return vectors.astype(np.float32)


def encode_query(query: str) -> np.ndarray:
    model = load_model()
    vector = model.encode(
        [QUERY_PREFIX + query],
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return vector[0].astype(np.float32)
