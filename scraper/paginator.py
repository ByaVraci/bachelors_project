from scraper.client import run_query

def paginate(query, variables, path, end_date=None, max_pages=9999):
    results, cursor, page_num = [], None, 0

    while page_num < max_pages:
        variables["cursor"] = cursor
        data = run_query(query, variables)

        node = data
        for key in path:
            node = node[key]

        items = node.get("nodes", [])

        # stop early if we passed the date window
        if end_date and items:
            in_range = [i for i in items if i.get("createdAt","") <= end_date]
            results.extend(in_range)
            if len(in_range) < len(items):
                print(f"  Reached end date {end_date} — stopping pagination")
                break
        else:
            results.extend(items)

        if not node.get("pageInfo", {}).get("hasNextPage", False):
            break

        cursor = node["pageInfo"]["endCursor"]
        page_num += 1
        print(f"  Page {page_num}: {len(results)} PRs collected so far")

    return results