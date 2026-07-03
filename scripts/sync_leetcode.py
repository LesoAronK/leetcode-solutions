import os
import sys
import time
import shutil
import requests

# ---- Auth ----
CSRFTOKEN = os.getenv("LEETCODE_CSRF_TOKEN")
LEETCODE_SESSION = os.getenv("LEETCODE_SESSION")

if not CSRFTOKEN or not LEETCODE_SESSION:
    print("ERROR: LEETCODE_CSRF_TOKEN or LEETCODE_SESSION is missing/empty.")
    sys.exit(1)

HEADERS = {
    "content-type": "application/json",
    "x-csrftoken": CSRFTOKEN,
    "cookie": f"LEETCODE_SESSION={LEETCODE_SESSION}; csrftoken={CSRFTOKEN}",
    # These two matter a lot: requests without them get blocked/challenged
    # far more aggressively, especially from GitHub Actions IPs.
    "referer": "https://leetcode.com",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "origin": "https://leetcode.com",
}

GRAPHQL_URL = "https://leetcode.com/graphql"

ext_map = {
    "python3": "py",
    "python": "py",
    "java": "java",
    "cpp": "cpp",
    "c": "c",
    "csharp": "cs",
    "javascript": "js",
    "typescript": "ts",
    "golang": "go",
    "rust": "rs",
    "kotlin": "kt",
    "swift": "swift",
    "ruby": "rb",
    "scala": "scala",
    "mysql": "sql",
}

SUBMISSION_LIST_QUERY = """
query submissionList($offset: Int!, $limit: Int!, $lastKey: String) {
  submissionList(offset: $offset, limit: $limit, lastKey: $lastKey) {
    lastKey
    hasNext
    submissions {
      id
      statusDisplay
      lang
      timestamp
      title
      titleSlug
    }
  }
}
"""

SUBMISSION_DETAIL_QUERY = """
query submissionDetails($submissionId: Int!) {
  submissionDetails(submissionId: $submissionId) {
    code
    question {
      questionId
    }
  }
}
"""


def graphql(query, variables, retries=3):
    for attempt in range(1, retries + 1):
        resp = requests.post(
            GRAPHQL_URL,
            json={"query": query, "variables": variables},
            headers=HEADERS,
            timeout=20,
        )
        if resp.status_code != 200:
            print(f"  [warn] HTTP {resp.status_code} on attempt {attempt}, retrying...")
            time.sleep(2 * attempt)
            continue
        try:
            payload = resp.json()
        except ValueError:
            print(f"  [warn] Non-JSON response on attempt {attempt} "
                  f"(likely blocked/challenge page), retrying...")
            time.sleep(2 * attempt)
            continue
        if "errors" in payload:
            print(f"  [warn] GraphQL errors: {payload['errors']}")
            time.sleep(2 * attempt)
            continue
        return payload["data"]
    raise RuntimeError(f"GraphQL request failed after {retries} attempts: {query[:40]}...")


def fetch_all_accepted_submissions():
    """Fetch every submission via cursor pagination, keep latest Accepted per problem slug."""
    latest_by_slug = {}
    offset = 0
    limit = 20  # LeetCode's own frontend uses 20; larger limits get throttled harder
    last_key = None
    page = 0

    while True:
        page += 1
        print(f"Fetching submissions page {page} (offset={offset})...")
        data = graphql(
            SUBMISSION_LIST_QUERY,
            {"offset": offset, "limit": limit, "lastKey": last_key},
        )
        block = data.get("submissionList")
        if not block:
            print("  [warn] Empty submissionList block, stopping.")
            break

        submissions = block.get("submissions", [])
        for sub in submissions:
            if sub.get("statusDisplay") == "Accepted":
                slug = sub["titleSlug"]
                # keep the most recent accepted submission per problem
                if slug not in latest_by_slug or int(sub["timestamp"]) > int(latest_by_slug[slug]["timestamp"]):
                    latest_by_slug[slug] = sub

        has_next = block.get("hasNext")
        last_key = block.get("lastKey")
        offset += limit

        if not has_next or not submissions:
            break

        time.sleep(1)  # be gentle, avoid tripping rate limits

    print(f"Found {len(latest_by_slug)} unique solved problems from submission history.")
    return latest_by_slug


def fetch_code(submission_id):
    data = graphql(SUBMISSION_DETAIL_QUERY, {"submissionId": int(submission_id)})
    detail = data.get("submissionDetails")
    if not detail:
        return None, None
    return detail.get("code"), (detail.get("question") or {}).get("questionId")


def main():
    latest_by_slug = fetch_all_accepted_submissions()

    if not latest_by_slug:
        print("ERROR: No accepted submissions fetched. Not touching the problems/ folder "
              "to avoid wiping existing solutions due to a failed run.")
        sys.exit(1)

    base_dir = "problems"
    tmp_dir = "problems_tmp"

    if os.path.exists(tmp_dir):
        shutil.rmtree(tmp_dir)
    os.makedirs(tmp_dir, exist_ok=True)

    written = 0
    for slug, sub in latest_by_slug.items():
        code, qid = fetch_code(sub["id"])
        if code is None:
            print(f"  [warn] Could not fetch code for {slug} (submission {sub['id']}), skipping.")
            continue

        qid = qid or "0"
        title = sub["title"]
        lang = sub["lang"]

        folder = os.path.join(tmp_dir, f"{qid}_{title.replace(' ', '_').lower()}")
        os.makedirs(folder, exist_ok=True)

        with open(os.path.join(folder, "README.md"), "w", encoding="utf-8") as f:
            f.write(f"# {title} (Problem #{qid})\n\n")
            f.write(f"Link: https://leetcode.com/problems/{slug}/\n")

        ext = ext_map.get(lang, "txt")
        with open(os.path.join(folder, f"solution.{ext}"), "w", encoding="utf-8") as f:
            f.write(code)

        written += 1
        time.sleep(0.5)  # one detail request per problem, stay gentle

    if written == 0:
        print("ERROR: Fetched submissions but couldn't write any solution files. Aborting rebuild.")
        shutil.rmtree(tmp_dir)
        sys.exit(1)

    # Only swap in the new folder once we know the run actually produced something,
    # so a partial/failed run never wipes out a previously good state.
    if os.path.exists(base_dir):
        shutil.rmtree(base_dir)
    os.rename(tmp_dir, base_dir)

    print(f"Done. Wrote {written} problem folders into '{base_dir}/'.")


if __name__ == "__main__":
    main()
