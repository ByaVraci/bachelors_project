from config import REPOS
from pipeline.extract import run

if __name__ == "__main__":
    for repo_id in REPOS:
        owner, name = repo_id.split("/")
        run(owner, name)
    print("\nAll repos done.")