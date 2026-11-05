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

# 한국어 등 다국어 질의를 영어 게임 설명과 비교할 수 있는 작은(118M) 임베딩 모델
MODEL_NAME = "intfloat/multilingual-e5-small"
# e5 계열 모델은 문서/질의 앞에 아래 접두어를 붙여야 성능이 제대로 나옴
PASSAGE_PREFIX = "passage: "
QUERY_PREFIX = "query: "
MAX_DESCRIPTION_CHARS = 1500

_model = None
_model_lock = threading.Lock()


def is_installed() -> bool:
    return importlib.util.find_spec("sentence_transformers") is not None


def build_passages(df: pd.DataFrame, mechanics, themes) -> list[str]:
    """게임 이름 + 메커니즘 + 테마 + 설명글을 하나의 문서로 만듦"""
    mech_names = mechanics.names
    theme_names = themes.names
    passages = []
    for i, row in enumerate(df.itertuples(index=False)):
        mech = ", ".join(mech_names[mechanics.binary[i].indices])
        theme = ", ".join(theme_names[themes.binary[i].indices])
        parts = [f"{row.Name}."]
        if mech:
            parts.append(f"Mechanics: {mech}.")
        if theme:
            parts.append(f"Themes: {theme}.")
        parts.append(str(row.Description)[:MAX_DESCRIPTION_CHARS])
        passages.append(PASSAGE_PREFIX + " ".join(parts))
    return passages


def load_model(device: str | None = None):
    """모델을 한 번만 불러와 재사용 (첫 호출 시 Hugging Face에서 내려받음)"""
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
