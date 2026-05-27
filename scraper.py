import requests
import pandas as pd
from datetime import datetime, timedelta
import os
import time
import sys

GITHUB_API = "https://api.github.com/search/repositories"
MAX_RETRIES = 3
TIMEOUT = 30
CSV_FILE = "github_trending_history.csv"


def get_headers():
    headers = {"Accept": "application/vnd.github.v3+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def fetch_with_retry(url, params, headers):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)

            if resp.status_code == 403:
                reset_time = int(resp.headers.get("X-RateLimit-Reset", 0))
                wait = max(reset_time - int(time.time()), 10)
                print(f"Rate limited. Waiting {wait}s... (attempt {attempt}/{MAX_RETRIES})")
                time.sleep(wait)
                continue

            if resp.status_code == 200:
                return resp.json()

            print(f"HTTP {resp.status_code}: {resp.text[:200]}")
            return None

        except requests.exceptions.Timeout:
            print(f"Timeout (attempt {attempt}/{MAX_RETRIES})")
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e} (attempt {attempt}/{MAX_RETRIES})")

        if attempt < MAX_RETRIES:
            time.sleep(2 ** attempt)

    print("All retries exhausted.")
    return None


def scrape_github_trending():
    headers = get_headers()
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")

    # Query 1: Repo baru (< 7 hari) yang sudah populer → "newly hot"
    params_new = {
        "q": f"created:>{yesterday} stars:>10",
        "sort": "stars",
        "order": "desc",
        "per_page": 25,
    }

    # Query 2: Repo aktif dengan banyak bintang → "established trending"
    params_popular = {
        "q": f"stars:>500 pushed:>{yesterday}",
        "sort": "stars",
        "order": "desc",
        "per_page": 25,
    }

    print("Fetching newly created trending repos...")
    data_new = fetch_with_retry(GITHUB_API, params_new, headers)

    print("Fetching popular active repos...")
    data_popular = fetch_with_retry(GITHUB_API, params_popular, headers)

    scrape_date = datetime.utcnow().strftime("%Y-%m-%d")
    records = []
    seen = set()

    def extract_items(data, category):
        if not data or "items" not in data:
            return
        for rank, item in enumerate(data["items"], start=1):
            full_name = item.get("full_name", "N/A")
            if full_name in seen:
                continue
            seen.add(full_name)
            records.append({
                "date": scrape_date,
                "rank": len(records) + 1,
                "full_name": full_name,
                "language": item.get("language") or "N/A",
                "stars_total": item.get("stargazers_count", 0),
                "description": (item.get("description") or "")[:200],
                "topics": ",".join(item.get("topics", [])),
                "created_at": item.get("created_at", ""),
                "url": item.get("html_url", ""),
                "category": category,
            })

    extract_items(data_new, "newly_hot")
    extract_items(data_popular, "established")

    if not records:
        print("No data fetched. Check API status or rate limits.")
        return

    df = pd.DataFrame(records)

    if os.path.exists(CSV_FILE):
        df.to_csv(CSV_FILE, mode="a", header=False, index=False)
        print(f"Appended {len(df)} repos for {scrape_date}.")
    else:
        df.to_csv(CSV_FILE, mode="w", header=True, index=False)
        print(f"Created {CSV_FILE}. Saved {len(df)} repos for {scrape_date}.")

    # Summary
    print(f"\n--- Summary ({scrape_date}) ---")
    print(f"Total repos: {len(df)}")
    top_langs = df["language"].value_counts().head(5)
    print(f"Top languages:\n{top_langs.to_string()}")
    top3 = df.nlargest(3, "stars_total")[["full_name", "stars_total"]]
    print(f"\nTop 3 by stars:")
    for _, row in top3.iterrows():
        print(f"  {row['full_name']} ({row['stars_total']:,} stars)")


if __name__ == "__main__":
    scrape_github_trending()
