"""
backend/korean_names.py
한글 게임 이름 검색 (data/korean_names.csv)

데이터의 게임 이름은 영어뿐이라 "카탄"으로 검색하면 Catan이 나오지 않음.
인기 게임 위주로 BGGId ↔ 한글 이름 표를 만들어 두고, 검색할 때 같이 찾는다.
- 한 게임에 한글 이름을 여러 개 둘 수 있음 (예: 카탄, 카탄의 개척자)
- 띄어쓰기와 대소문자는 무시함 (예: "티켓투라이드" = "티켓 투 라이드")
- 표에 없는 게임은 지금처럼 영어 이름으로만 검색됨
- 새 게임을 추가하려면 CSV에 BGGId, Name(영어 이름), KoreanName 한 줄을 넣으면 됨
"""

from pathlib import Path

import pandas as pd

KOREAN_NAMES_PATH = Path(__file__).resolve().parent.parent / "data" / "korean_names.csv"


def normalize(text: str) -> str:
    """비교용으로 띄어쓰기를 없애고 소문자로 바꿈"""
    return "".join(str(text).split()).lower()


def load_korean_names(path: Path = KOREAN_NAMES_PATH) -> pd.DataFrame:
    """한글 이름 표를 읽고, 비교용 열(Key)을 붙여 반환 (파일이 없으면 빈 표)"""
    if not path.exists():
        return pd.DataFrame(columns=["BGGId", "Name", "KoreanName", "Key"])
    table = pd.read_csv(path)
    table["Key"] = table["KoreanName"].map(normalize)
    return table


def match_ranks(table: pd.DataFrame, query: str) -> dict[int, int]:
    """검색어가 들어간 한글 이름을 찾아 게임별 순위를 반환

    순위: 0 = 이름이 정확히 같음, 1 = 이름이 검색어로 시작함, 2 = 이름 중간에 포함됨
    한 게임에 별칭이 여러 개면 가장 좋은(작은) 순위를 사용
    """
    key = normalize(query)
    ranks: dict[int, int] = {}
    if not key:
        return ranks

    for bgg_id, name in zip(table["BGGId"], table["Key"]):
        if key not in name:
            continue
        rank = 0 if name == key else 1 if name.startswith(key) else 2
        bgg_id = int(bgg_id)
        ranks[bgg_id] = min(rank, ranks.get(bgg_id, 2))
    return ranks
