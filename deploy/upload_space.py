# /// script
# requires-python = ">=3.12"
# dependencies = ["huggingface_hub>=0.34"]
# ///
"""
deploy/upload_space.py
백엔드를 Hugging Face Space(Docker)에 업로드한다. 자세한 순서는 docs/deploy.md

사용법 (프로젝트 루트에서):
    uv run deploy/upload_space.py <허깅페이스아이디>/<스페이스이름> [--origins https://내앱.vercel.app]

- git에 올리지 않는 data/embeddings.npz, data/cf_factors.npz 도 내 컴퓨터에서 바로 업로드한다.
- Space가 없으면 새로 만든다 (Docker SDK, 공개).
- --origins 를 주면 Space 환경변수 ALLOWED_ORIGINS(CORS 허용 주소)도 함께 설정한다.
- 로그인: 먼저 `uvx --from huggingface_hub hf auth login` 을 실행하거나 환경변수 HF_TOKEN 에 쓰기 권한 토큰을 넣는다.
"""

import argparse
import sys
from pathlib import Path

from huggingface_hub import CommitOperationAdd, HfApi

ROOT = Path(__file__).resolve().parent.parent

# (내 컴퓨터 경로, Space 안의 경로)
REQUIRED_FILES = [
    ("Dockerfile", "Dockerfile"),
    (".dockerignore", ".dockerignore"),
    ("deploy/huggingface/README.md", "README.md"),  # Space 설정(sdk: docker 등)
    ("pyproject.toml", "pyproject.toml"),
    ("uv.lock", "uv.lock"),
    (".python-version", ".python-version"),
    ("data/clean_games.csv", "data/clean_games.csv"),
    ("data/games.csv", "data/games.csv"),
    ("data/mechanics.csv", "data/mechanics.csv"),
    ("data/themes.csv", "data/themes.csv"),
]
# 없어도 서버는 동작하지만 추천 품질이 떨어지는 파일
OPTIONAL_FILES = [
    ("data/embeddings.npz", "data/embeddings.npz"),  # backend/build_embeddings.py 로 생성
    ("data/cf_factors.npz", "data/cf_factors.npz"),  # backend/build_cf.py 로 생성
]


def collect_files() -> list[tuple[Path, str]]:
    files = []
    missing = [local for local, _ in REQUIRED_FILES if not (ROOT / local).exists()]
    if missing:
        sys.exit(f"필수 파일이 없습니다: {', '.join(missing)}")
    for local, remote in REQUIRED_FILES:
        files.append((ROOT / local, remote))
    for local, remote in OPTIONAL_FILES:
        if (ROOT / local).exists():
            files.append((ROOT / local, remote))
        else:
            print(f"[경고] {local} 이 없어 이 신호 없이 추천합니다.")
    for path in sorted((ROOT / "backend").glob("*.py")):
        files.append((path, f"backend/{path.name}"))
    return files


def main():
    parser = argparse.ArgumentParser(description="백엔드를 Hugging Face Space에 업로드")
    parser.add_argument("space_id", help="예: myname/boardgame-recommender-api")
    parser.add_argument("--origins", help="CORS 허용 프론트엔드 주소 (쉼표로 구분)")
    args = parser.parse_args()

    api = HfApi()
    api.create_repo(args.space_id, repo_type="space", space_sdk="docker", exist_ok=True)

    files = collect_files()
    operations = [CommitOperationAdd(path_in_repo=remote, path_or_fileobj=str(local)) for local, remote in files]
    print(f"{len(operations)}개 파일 업로드 중...")
    api.create_commit(
        repo_id=args.space_id,
        repo_type="space",
        operations=operations,
        commit_message="Deploy backend",
    )

    if args.origins:
        api.add_space_variable(args.space_id, "ALLOWED_ORIGINS", args.origins)
        print(f"ALLOWED_ORIGINS = {args.origins}")

    owner, name = args.space_id.split("/", 1)
    print("업로드 완료. Space 페이지에서 빌드 진행 상황을 확인하세요.")
    print(f"  Space:   https://huggingface.co/spaces/{args.space_id}")
    host = f"{owner}-{name}".lower().replace("_", "-").replace(".", "-")
    print(f"  API 주소: https://{host}.hf.space")


if __name__ == "__main__":
    main()
