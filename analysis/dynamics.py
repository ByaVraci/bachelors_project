import pandas as pd
import numpy as np
import sqlite3

def compute_mttr(prs: pd.DataFrame) -> pd.DataFrame:
    """
    Mean Time to Resolution in hours.
    Only includes merged PRs.
    """
    # all stored PRs are merged; the filter is used as guard here
    merged = prs[prs["merged_at"].notna()].copy()
    merged["hours_to_merge"] = (
        merged["merged_at"] - merged["created_at"]
    ).dt.total_seconds() / 3600

    return merged.groupby(
        ["repo_id", "period"]
    ).agg(
        mttr_hours    =("hours_to_merge", "mean"),
        median_hours  =("hours_to_merge", "median"),
        pr_count      =("id",             "count"),
    ).round(2).reset_index()

def compute_thread_depth(comments: pd.DataFrame) -> pd.DataFrame:
    """
    Number of human comments per PR.
    """
    depth = comments.groupby(
        ["repo_id", "period", "pr_id"]
    ).agg(
        comment_count  =("id",            "count"),
        unique_authors =("author_login",  "nunique"),
    ).reset_index()

    return depth.groupby(
        ["repo_id", "period"]
    ).agg(
        avg_thread_depth  =("comment_count",  "mean"),
        avg_participants  =("unique_authors", "mean"),
        max_thread_depth  =("comment_count",  "max"),
    ).round(2).reset_index()

def pushpull_per_pr(comments: pd.DataFrame) -> pd.DataFrame:
    """Per-PR push-pull."""
    rows = []
    for (repo_id, period, pr_id), group in comments.groupby(["repo_id","period","pr_id"]):
        authors = group.sort_values("created_at")["author_login"].tolist()
        if len(authors) < 2:
            continue
        exchanges = sum(authors[i] != authors[i+1] for i in range(len(authors)-1))
        rows.append({"repo_id": repo_id, "period": period, "pr_id": pr_id,
                     "pushpull_ratio": exchanges / (len(authors)-1),
                     "pushpull_count": exchanges})
    return pd.DataFrame(rows)

def compute_pushpull(comments: pd.DataFrame) -> pd.DataFrame:
    df = pushpull_per_pr(comments)
    if df.empty:
        return pd.DataFrame(columns=["repo_id","period","avg_pushpull_ratio","avg_pushpull_count"])
    return df.groupby(["repo_id","period"]).agg(
        avg_pushpull_ratio=("pushpull_ratio","mean"),
        avg_pushpull_count=("pushpull_count","mean"),
    ).round(4).reset_index()

def run_dynamics_analysis(comments, prs):
    mttr  = compute_mttr(prs)
    depth = compute_thread_depth(comments)
    pp    = compute_pushpull(comments)
    return mttr.merge(depth, on=["repo_id","period"]).merge(pp, on=["repo_id","period"])


def summarise_dynamics_by_type(comments, prs, db_path="data/thesis.db"):
    conn = sqlite3.connect(db_path)
    types = pd.read_sql("SELECT id AS repo_id, type FROM repositories", conn)
    conn.close()

    merged = prs[prs["merged_at"].notna()].copy()
    merged["hours"] = (merged["merged_at"] - merged["created_at"]).dt.total_seconds()/3600
    merged = merged.merge(types, on="repo_id")
    mttr = merged.groupby(["type","period"]).agg(
        mttr_hours=("hours","mean"), median_hours=("hours","median")
    ).reset_index()

    c = comments.merge(types, on="repo_id")
    per_pr = c.groupby(["type","period","pr_id"]).agg(
        depth=("id","count"), participants=("author_login","nunique")
    ).reset_index()
    depth = per_pr.groupby(["type","period"]).agg(
        avg_thread_depth=("depth","mean"), avg_participants=("participants","mean")
    ).reset_index()

    return mttr.merge(depth, on=["type","period"]).round(2)