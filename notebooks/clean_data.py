import pandas as pd
from pathlib import Path

# 프로젝트 경로 설정
BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_PATH = BASE_DIR / "data" / "games.csv"
OUTPUT_PATH = BASE_DIR / "data" / "clean_games.csv"

# 원본 데이터 불러오기
df = pd.read_csv(INPUT_PATH)

print("원본 데이터 개수:", len(df))


# 사용할 핵심 컬럼
columns = [
    "BGGId",
    "Name",
    "YearPublished",
    "GameWeight",
    "MinPlayers",
    "MaxPlayers",
    "BestPlayers",
    "ComMinPlaytime",
    "ComMaxPlaytime",
    "BayesAvgRating",
    "Description",
    "NumUserRatings",
    "ImagePath"
]

df = df[columns].copy()


# Name, Description 결측치 제거
df = df.dropna(
    subset=["Name", "Description"]
)


# 플레이 인원 이상치 제거
df = df[
    (df["MinPlayers"] > 0) &
    (df["MaxPlayers"] >= df["MinPlayers"])
]


# 플레이 시간 이상치 제거
df = df[
    (df["ComMinPlaytime"] > 0) &
    (df["ComMaxPlaytime"] >= df["ComMinPlaytime"])
]


# BestPlayers의 0값을 결측치로 처리
df["BestPlayers"] = df["BestPlayers"].replace(0, pd.NA)


# 인덱스 다시 정리
df = df.reset_index(drop=True)


# 정제된 데이터 저장
df.to_csv(
    OUTPUT_PATH,
    index=False
)

print("정제 후 데이터 개수:", len(df))
print("저장 위치:", OUTPUT_PATH)