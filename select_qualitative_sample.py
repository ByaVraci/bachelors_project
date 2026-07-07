"""
Selects the qualitative coding sample by stratified random sampling
from the quantitative data corpus. Input: results/pr_level_for_r.csv.
reproducible via fixed SEED.
"""
import pandas as pd

SEED = 42
PER_CELL = 13                       # 13 × 8 cells ≈ 100 threads
KEEP = ["home-assistant/core", "microsoft/vscode"]
MIN_COMMENTS = 5                    # screen out content-free threads

pr = pd.read_csv("results/pr_level_for_r.csv")
pr = pr[pr["repo_id"].isin(KEEP)].copy()

# High/low push-pull split using each repo's own median
pr["pp_median"]  = pr.groupby("repo_id")["pushpull_ratio"].transform("median")
pr["pp_stratum"] = (pr["pushpull_ratio"] >= pr["pp_median"]).map(
    {True: "high", False: "low"})

# screen out mechanical / content-free threads (e.g. dependency bumps)
pr = pr[pr["comment_count"] >= MIN_COMMENTS]

# Draw from each repo × period × stratum cell
parts = []
for (repo, period, stratum), g in pr.groupby(["repo_id","period","pp_stratum"]):
    parts.append(g.sample(n=min(PER_CELL, len(g)), random_state=SEED))
sample = pd.concat(parts, ignore_index=True)

cols = ["pr_id","pr_number","repo_id","period","pp_stratum",
        "pushpull_ratio","comment_count"]
sample = sample[[c for c in cols if c in sample.columns]]

# Watch for thin cells before committing to the sample
print("Threads selected per cell:")
print(sample.groupby(["repo_id","period","pp_stratum"]).size())
print(f"\nTotal: {len(sample)} threads")

sample.to_csv("results/qualitative_sample.csv", index=False)
print("Wrote results/qualitative_sample.csv")