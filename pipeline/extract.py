from datetime import date, timedelta
from pathlib import Path
from config import REPOS, PRE_AI_TARGET, POST_AI_TARGET
from scraper.client import run_query
from scraper.queries import PR_SEARCH, PR_COMMENTS, REVIEW_THREADS
from pipeline.load import get_db, is_bot

Path("data").mkdir(exist_ok=True)


def is_promising(pr):
    return (
        pr.get("changedFiles", 0) > 0
        and pr.get("additions", 0) + pr.get("deletions", 0) >= 5
        and not (pr.get("state") == "CLOSED" and not pr.get("mergedAt"))
        and pr["comments"]["totalCount"]
            + pr["reviewThreads"]["totalCount"] >= 2
    )


def is_substantive(comments):
    humans = [
        c for c in comments
        if not is_bot(c.get("author"))
        and len(c["body"].split()) >= 3
    ]
    return (
        len(humans) >= 2
        and len({(c["author"] or {}).get("login") for c in humans}) >= 2
        and any(len(c["body"].split()) > 30 for c in humans)
    )


def get_comments(owner, name, number):
    out = []

    cursor, pages = None, 0
    while pages < 15:
        page = run_query(PR_COMMENTS, {
            "owner": owner, "name": name,
            "pr": number, "cursor": cursor
        })["repository"]["pullRequest"]["comments"]
        for c in page["nodes"]:
            c["comment_type"], c["thread_id"] = "general", None
            out.append(c)
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]
        pages += 1

    cursor, pages = None, 0
    while pages < 15:
        page = run_query(REVIEW_THREADS, {
            "owner": owner, "name": name,
            "pr": number, "cursor": cursor
        })["repository"]["pullRequest"]["reviewThreads"]
        for t in page["nodes"]:
            for c in t["comments"]["nodes"]:
                c["comment_type"], c["thread_id"] = "review", t["id"]
                out.append(c)
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]
        pages += 1

    return out


def save_pr(db, pr, rid, period, humans):
    pr_id = pr["databaseId"]
    db["pull_requests"].upsert({
        "id":           pr_id,
        "repo_id":      rid,
        "number":       pr["number"],
        "created_at":   pr["createdAt"],
        "merged_at":    pr.get("mergedAt"),
        "period":       period,
        "author_login": (pr["author"] or {}).get("login", "ghost"),
        "body":         pr.get("body", ""),
        "additions":    pr.get("additions", 0),
        "deletions":    pr.get("deletions", 0),
    }, pk="id")

    rows = [
        {
            "id":           c["databaseId"],
            "pr_id":        pr_id,
            "repo_id":      rid,
            "body":         c["body"],
            "author_login": (c["author"] or {}).get("login", "ghost"),
            "is_bot":       0,
            "created_at":   c["createdAt"],
            "thread_id":    c.get("thread_id"),
            "comment_type": c["comment_type"],
        }
        for c in humans if len(c["body"].split()) >= 3
    ]
    if rows:
        db["comments"].upsert_all(rows, pk="id")


def month_ranges(start_str, end_str):
    start = date.fromisoformat(start_str)
    end   = date.fromisoformat(end_str)
    cur   = start.replace(day=1)
    while cur <= end:
        nxt = (cur.replace(year=cur.year + 1, month=1)
               if cur.month == 12
               else cur.replace(month=cur.month + 1))
        yield (max(cur, start).isoformat(),
               min(nxt - timedelta(days=1), end).isoformat())
        cur = nxt


def fetch_period(owner, name, cfg, db, period, target,
                 newest_first=False):
    rid   = f"{owner}/{name}"
    start = cfg[f"{period}_start"]
    end   = cfg[f"{period}_end"]

    saved = {r[0] for r in db.execute(
        "SELECT number FROM pull_requests "
        "WHERE repo_id=? AND period=?", [rid, period]
    )}
    count = len(saved)

    if count >= target:
        print(f"  {period}: {count}/{target} — skipping")
        return

    ranges = list(month_ranges(start, end))
    if newest_first:
        ranges.reverse()

    for chunk_start, chunk_end in ranges:
        if count >= target:
            break
        print(f"  {period}: {chunk_start[:7]} ({count}/{target})")
        q = (f"repo:{owner}/{name} type:pr is:merged "
             f"created:{chunk_start}..{chunk_end}")
        cursor = None

        while count < target:
            page = run_query(
                PR_SEARCH, {"q": q, "cursor": cursor}
            )["search"]

            for pr in page["nodes"]:
                if not pr or pr["number"] in saved:
                    continue
                if not is_promising(pr):
                    continue
                comments = get_comments(owner, name, pr["number"])
                humans   = [c for c in comments
                            if not is_bot(c.get("author"))]
                if not is_substantive(humans):
                    continue
                save_pr(db, pr, rid, period, humans)
                saved.add(pr["number"])
                count += 1
                print(f"  {period}: {count}/{target} "
                      f"— PR #{pr['number']}")
                if count >= target:
                    return

            if not page["pageInfo"]["hasNextPage"]:
                break
            cursor = page["pageInfo"]["endCursor"]

    print(f"  {period}: finished — {count}/{target} saved")


def run(owner, name):
    rid = f"{owner}/{name}"
    cfg = REPOS[rid]
    db  = get_db()

    db["repositories"].upsert({
        "id":                 rid,
        "type":               cfg["type"],
        "ai_transition_date": cfg["post_ai_start"],
        "detection_method":   "jetbrains_survey_2025",
    }, pk="id")

    print(f"\n=== {rid} ===")
    fetch_period(owner, name, cfg, db, "pre_ai",  PRE_AI_TARGET)
    fetch_period(owner, name, cfg, db, "post_ai", POST_AI_TARGET,
                 newest_first=True)