import sqlite3
import pandas as pd
from analysis.cleaning import clean_for_linguistics

DB_PATH = "data/thesis.db"

def load_comments() -> pd.DataFrame:
    """
    Loads all human comments joined with their
    PR period label into a single DataFrame.
    """
    conn  = sqlite3.connect(DB_PATH)
    query = """
        SELECT
            c.id,
            c.body,
            c.author_login,
            c.created_at,
            c.thread_id,
            c.comment_type,
            c.pr_id,
            p.period,
            p.repo_id,
            p.number       AS pr_number,
            p.created_at   AS pr_created_at,
            p.merged_at    AS pr_merged_at
        FROM comments c
        JOIN pull_requests p ON c.pr_id = p.id
        WHERE c.is_bot   = 0
        AND   p.period  != 'transition'
    """
    # left c.is_bot and p.period filters as guards, if I change things
    # in the data extraction part
    df = pd.read_sql(query, conn)
    conn.close()
    df["body_clean"] = df["body"].apply(clean_for_linguistics)
    df["word_count"] = df["body_clean"].apply(lambda x: len(x.split()))
    return df

def load_pull_requests() -> pd.DataFrame:
    """
    Loads all PRs with timing information
    for response dynamics calculations.
    """
    conn  = sqlite3.connect(DB_PATH)
    query = """
        SELECT
            id, number, repo_id, period,
            created_at, merged_at, author_login,
            additions, deletions
        FROM pull_requests
        WHERE period != 'transition'
    """
    df = pd.read_sql(query, conn)
    conn.close()

    df["created_at"] = pd.to_datetime(df["created_at"])
    df["merged_at"]  = pd.to_datetime(df["merged_at"])
    return df

def load_comments_with_pr_body() -> pd.DataFrame:
    """
    Loads all comments plus PR bodies as synthetic
    opening comments, so full conversations are captured.
    PR bodies get comment_type = 'pr_body' so they can
    be filtered separately when needed.
    """
    conn = sqlite3.connect(DB_PATH)

    # Regular comments
    comments_query = """
        SELECT
            c.id,
            c.body,
            c.author_login,
            c.created_at,
            c.thread_id,
            c.comment_type,
            c.pr_id,
            p.period,
            p.repo_id,
            p.number       AS pr_number,
            p.created_at   AS pr_created_at,
            p.merged_at    AS pr_merged_at
        FROM comments c
        JOIN pull_requests p ON c.pr_id = p.id
        WHERE c.is_bot   = 0
        AND   p.period  != 'transition'
        AND   LENGTH(TRIM(c.body)) > 0
    """

    # PR bodies as synthetic opening comments
    body_query = """
        SELECT
            -(p.id)        AS id,
            p.body,
            p.author_login,
            p.created_at,
            NULL           AS thread_id,
            'pr_body'      AS comment_type,
            p.id           AS pr_id,
            p.period,
            p.repo_id,
            p.number       AS pr_number,
            p.created_at   AS pr_created_at,
            p.merged_at    AS pr_merged_at
        FROM pull_requests p
        WHERE p.period != 'transition'
        AND   p.body   IS NOT NULL
        AND   LENGTH(TRIM(p.body)) > 10
    """

    comments = pd.read_sql(comments_query, conn)
    bodies   = pd.read_sql(body_query,   conn)
    conn.close()

    df = pd.concat([comments, bodies], ignore_index=True)
    df = df.sort_values(["pr_id", "created_at"]).reset_index(drop=True)
    df["body_clean"] = df["body"].apply(clean_for_linguistics)
    df["word_count"] = df["body_clean"].apply(lambda x: len(x.split()))
    return df