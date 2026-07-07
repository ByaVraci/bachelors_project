import sqlite_utils

DB_PATH = "data/thesis.db"

def get_db():
    db = sqlite_utils.Database(DB_PATH)
    db["repositories"].create({
        "id": str, "type": str,
        "ai_transition_date": str,
        "detection_method": str,
    }, pk="id", ignore=True)
    db["pull_requests"].create({
        "id": int, "repo_id": str, "number": int,
        "created_at": str, "merged_at": str,
        "period": str, "author_login": str,
        "body": str, "additions": int, "deletions": int,
    }, pk="id",
    foreign_keys=[("repo_id", "repositories", "id")],
    ignore=True)
    db["comments"].create({
        "id": int, "pr_id": int, "repo_id": str,
        "body": str, "author_login": str,
        "is_bot": int, "created_at": str,
        "thread_id": str, "comment_type": str,
    }, pk="id",
    foreign_keys=[
        ("pr_id",   "pull_requests", "id"),
        ("repo_id", "repositories",  "id"),
    ], ignore=True)
    return db

def is_bot(author):
    if not author:
        return False
    if author.get("__typename") == "Bot":
        return True
    keywords = ["bot", "robot", "coderabbit", "copilot",
                "sourcery", "deepsource", "dependabot", "renovate"]
    return any(k in author.get("login", "").lower() for k in keywords)