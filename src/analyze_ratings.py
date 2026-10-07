import pandas as pd
from pathlib import Path

# 프로젝트 경로
BASE_DIR = Path(__file__).resolve().parent.parent

# 정제된 데이터 경로
DATA_PATH = BASE_DIR / "data" / "clean_games.csv"

# 데이터 불러오기
df = pd.read_csv(DATA_PATH)

ratings = df["NumUserRatings"]

print("===== NumUserRatings 분석 =====")

print("게임 수:", len(ratings))
print("최솟값:", ratings.min())
print("최댓값:", ratings.max())
print("평균:", ratings.mean())
print("중앙값:", ratings.median())

print("\n===== 평가 수 기준 게임 개수 =====")

print("10개 이상:", (ratings >= 10).sum())
print("50개 이상:", (ratings >= 50).sum())
print("100개 이상:", (ratings >= 100).sum())
print("500개 이상:", (ratings >= 500).sum())
print("1000개 이상:", (ratings >= 1000).sum())