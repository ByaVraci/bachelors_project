import os, sqlite3
import pandas as pd
from analysis.loader     import load_comments, load_pull_requests, load_comments_with_pr_body
from analysis.linguistic import run_linguistic_analysis, summarise_by_period, summarise_by_type
from analysis.sentiment  import run_sentiment_analysis, summarise_sentiment, summarise_sentiment_by_type
from analysis.dynamics   import run_dynamics_analysis, summarise_dynamics_by_type, pushpull_per_pr

os.makedirs("results", exist_ok=True)

print("=== Loading ===")
comments    = load_comments()
full_convos = load_comments_with_pr_body()
prs         = load_pull_requests()

print("=== Linguistic ===")
comments = run_linguistic_analysis(comments)
summarise_by_period(comments).to_csv("results/linguistic_summary.csv", index=False)
summarise_by_type(comments).to_csv("results/type_summary.csv", index=False)

print("=== Dynamics ===")
run_dynamics_analysis(full_convos, prs).to_csv("results/dynamics_summary.csv", index=False)
summarise_dynamics_by_type(full_convos, prs).to_csv("results/dynamics_type_summary.csv", index=False)

print("=== Sentiment (once, on comments, on cleaned text) ===")
comments = run_sentiment_analysis(comments)            # full_convos sentiment removed
summarise_sentiment(comments).to_csv("results/sentiment_summary.csv", index=False)
summarise_sentiment_by_type(comments).to_csv("results/sentiment_type_summary.csv", index=False)

conn = sqlite3.connect("data/thesis.db")
comments[["id","polarity","sentiment_label"]].to_sql("sentiment_scores", conn,
                                                      if_exists="replace", index=False)
types = pd.read_sql("SELECT id AS repo_id, type FROM repositories", conn)
conn.close()

print("=== Export for R ===")
# structural metrics -> ALL from full_convos
struct_pr = full_convos.groupby(["repo_id","period","pr_id"]).agg(
    pr_number=("pr_number","first"),
    comment_count=("id","count"),
    unique_authors=("author_login","nunique")).reset_index()
struct_pr = struct_pr.merge(pushpull_per_pr(full_convos),
                            on=["repo_id","period","pr_id"], how="left")

# Linguistic aggregates: from comments, prose only
ling_pr = comments[comments["word_count"] > 0].groupby(["repo_id","period","pr_id"]).agg(
    avg_word_count=("word_count","mean"), avg_lex_div=("lexical_diversity","mean"),
    avg_q_ratio=("question_ratio","mean"), avg_hedging=("hedging_ratio","mean"),
    avg_polarity=("polarity","mean")).reset_index()

pr_level = struct_pr.merge(ling_pr, on=["repo_id","period","pr_id"], how="left") \
                    .merge(types, on="repo_id", how="left")
comments = comments.merge(types, on="repo_id", how="left")

comments.to_csv("results/comments_for_r.csv", index=False)
prs.to_csv("results/prs_for_r.csv", index=False)
pr_level.to_csv("results/pr_level_for_r.csv", index=False)
print("Done — run analysis.R")