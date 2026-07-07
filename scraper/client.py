import os, time
import requests_cache
from dotenv import load_dotenv
from requests.exceptions import ChunkedEncodingError, ConnectionError

load_dotenv()
ENDPOINT = "https://api.github.com/graphql"
TOKEN    = os.getenv("GITHUB_TOKEN")

session = requests_cache.CachedSession(
    "data/github_cache", backend="sqlite",
    allowable_methods=["POST"], match_headers=False,
    expire_after=None,
)

def run_query(query, variables={}):
    headers = {"Authorization": f"bearer {TOKEN}"}
    for attempt in range(7):
        try:
            resp = session.post(
                ENDPOINT,
                json={"query": query, "variables": variables},
                headers=headers, timeout=60
            )
            if not getattr(resp, "from_cache", False):
                remaining = int(resp.headers.get("X-RateLimit-Remaining", 1))
                if remaining < 50:
                    wait = max(int(resp.headers.get(
                        "X-RateLimit-Reset", 0)) - time.time(), 0) + 5
                    print(f"  Rate limit — waiting {wait:.0f}s")
                    time.sleep(wait)
            if resp.status_code == 200:
                data = resp.json()
                if "errors" in data:
                    raise ValueError(data["errors"])
                return data["data"]
            if resp.status_code in (502, 503):
                time.sleep(2 ** attempt)
            else:
                resp.raise_for_status()
        except (ChunkedEncodingError, ConnectionError):
            print(f"  Network error — retrying ({attempt + 1}/7)")
            time.sleep(2 ** attempt)
    raise RuntimeError("Max retries exceeded")