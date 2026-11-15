"""게임 프로필 파일(data/game_profiles.json) 읽기. 프로필·franchise·designers 메타데이터는 검색에만 쓴다."""

import json
from pathlib import Path

try:
    from backend import features
except ImportError:  # Docker image runs from backend/
    import features

PROFILES_PATH = features.DATA_DIR / "game_profiles.json"


def load(path: Path = PROFILES_PATH) -> dict[int, dict]:
    """{BGGId: {profile, franchise, base_game, designers, designer_countries}}. 파일이 없거나 깨지면 빈 dict"""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return {int(k): v for k, v in raw["profiles"].items() if isinstance(v, dict)}
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        if Path(path).exists():
            print(f"Warning: could not load game profiles from {path}: {exc}")
        return {}


PROFILES: dict[int, dict] = load()
