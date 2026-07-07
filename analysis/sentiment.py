import sys
import os
import pandas as pd
import sqlite3

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SENTICR_DIR  = os.path.join(PROJECT_ROOT, "SentiCR", "SentiCR")

os.chdir(SENTICR_DIR)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "SentiCR"))

from SentiCR.SentiCR import SentiCR

print("Loading SentiCR model...")
_analyzer = SentiCR()

os.chdir(PROJECT_ROOT)
print("SentiCR ready.")

def get_sentiment(text: str) -> int:
    try:
        result = _analyzer.get_sentiment_polarity(str(text))
        # Extract scalar from numpy array e.g. [0.] -> 0
        return int(result[0])
    except Exception as e:
        print(f"  SentiCR error: {e}")
        return 0

def classify_sentiment(polarity: int) -> str:
    """Converts SentiCR numeric output to a label."""
    if polarity == 1:
        return "positive"
    elif polarity == -1:
        return "negative"
    return "neutral"


def compute_sentiment_arc(group: pd.DataFrame) -> float:
    """
    Tracks how sentiment shifts across a PR thread.
    Converts labels to numbers for slope calculation:
    positive=1, neutral=0, negative=-1
    """
    label_map = {"positive": 1, "neutral": 0, "negative": -1}

    if len(group) < 2:
        return 0.0

    scores = (
        group.sort_values("created_at")["sentiment_label"]
        .map(label_map)
        .fillna(0)
    )
    return (scores.iloc[-1] - scores.iloc[0]) / len(scores)


def run_sentiment_analysis(df: pd.DataFrame) -> pd.DataFrame:
    print(f"  Analysing {len(df)} comments with SentiCR...")

    df["polarity"]        = df["body_clean"].apply(get_sentiment)
    df["sentiment_label"] = df["polarity"].apply(classify_sentiment)

    dist = df["sentiment_label"].value_counts(normalize=True)
    print("\n  Sentiment distribution:")
    for label, pct in dist.items():
        print(f"    {label}: {pct:.1%}")

    return df


def summarise_sentiment(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregates sentiment by repo and period.
    """
    df = df[df["word_count"] > 0]   # prose only

    summary = df.groupby(["repo_id", "period"]).agg(
        total_comments=("id",              "count"),
        pct_positive  =("sentiment_label",
            lambda x: (x == "positive").mean()),
        pct_negative  =("sentiment_label",
            lambda x: (x == "negative").mean()),
        pct_neutral   =("sentiment_label",
            lambda x: (x == "neutral").mean()),
    ).round(4).reset_index()

    # Sentiment arc = how tone shifts within threads
    arcs = df.groupby(
        ["repo_id", "period", "pr_id"]
    ).apply(compute_sentiment_arc, include_groups=False).reset_index()
    arcs.columns = ["repo_id", "period", "pr_id", "arc"]

    arc_summary = arcs.groupby(
        ["repo_id", "period"]
    )["arc"].mean().reset_index()
    arc_summary.rename(
        columns={"arc": "avg_sentiment_arc"}, inplace=True
    )

    return summary.merge(arc_summary, on=["repo_id", "period"])

def summarise_sentiment_by_type(df, db_path="data/thesis.db"):
    df = df[df["word_count"] > 0]   # prose only

    conn = sqlite3.connect(db_path)
    types = pd.read_sql("SELECT id AS repo_id, type FROM repositories", conn)
    conn.close()
    d = df.merge(types, on="repo_id")
    return d.groupby(["type","period"]).agg(
        total_comments=("id","count"),
        pct_negative=("sentiment_label", lambda x: (x=="negative").mean()),
        pct_neutral =("sentiment_label", lambda x: (x=="neutral").mean()),
        pct_positive=("sentiment_label", lambda x: (x=="positive").mean()),
    ).round(4).reset_index()