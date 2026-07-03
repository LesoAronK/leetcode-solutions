import os
import sys
import time
import json
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
    "referer": "https://leetcode.com",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "origin": "https://leetcode.com",
}

GRAPHQL_URL = "https://leetcode.com/graphql"
BASE_DIR = "problems"
STATE_FILE = os.path.join(BASE_DIR, ".sync_state.json")

# Budget per run so a single Action run never hangs/times out or hammers LeetCode
MAX_REQUESTS_PER_RUN = 60
CONSECUTIVE_KNOWN_TO_STOP_FRESH_PASS = 6  # "we've caught up" heuristic

ext_map = {
    "python3": "py", "python": "py", "java": "java", "cpp": "cpp", "c": "c",
    "csharp": "cs", "javascript": "js", "typescript": "ts", "golang": "go",
    "rust": "rs", "kotlin": "kt", "swift": "swift", "ruby": "rb",
    "scala": "scala", "mysql": "sql",
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

request_count = 0


class Blocked(Exception):
    pass


def graphql(query, variables):
    global request_count
    if request_count >= MAX_REQUESTS_PER_RUN:
        raise Blocked("Hit this run's request budget, stopping cleanly.")
    request_count += 1

    resp = requests.post(GRAPHQL_URL, json={"query": query, "variables": variables},
                          headers=HEADERS, timeout=20)
    if resp.status_code != 200:
        raise Blocked(f"HTTP {resp.status_code} from LeetCode (likely blocked/rate-limited).")
    try:
        payload = resp.json()
    except ValueError:
        raise Blocked("Non-JSON response (likely a block/challenge page).")
    if "errors" in payload:
        raise Blocked(f"GraphQL errors: {payload['errors']}")
    return payload["data"]


def load_state():
    defaults = {"processed_slugs": [], "backlog_offset": 0, "backlog_last_key": None,
                "backlog_exhausted": False, "full_cycles_completed": 0}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
        defaults.update(state)
        return defaults
    return defaults


def save_state(state):
    os.makedirs(BASE_DIR, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def write_solution(sub):
    """Fetch code for one accepted submission and write its folder. Returns True on success."""
    data = graphql(SUBMISSION_DETAIL_QUERY, {"submissionId": int(sub["id"])})
    detail = data.get("submissionDetails")
    if not detail or not detail.get("code"):
        print(f"  [warn] No code returned for {sub['titleSlug']}, skipping this run.")
        return False

    qid = (detail.get("question") or {}).get("questionId") or "0"
    title = sub["title"]
    folder = os.path.join(BASE_DIR, f"{qid}_{title.replace(' ', '_').lower()}")
    os.makedirs(folder, exist_ok=True)

    with open(os.path.join(folder, "README.md"), "w", encoding="utf-8") as f:
        f.write(f"# {title} (Problem #{qid})\n\n")
        f.write(f"Link: https://leetcode.com/problems/{sub['titleSlug']}/\n")

    ext = ext_map.get(sub["lang"], "txt")
    with open(os.path.join(folder, f"solution.{ext}"), "w", encoding="utf-8") as f:
        f.write(detail["code"])

    time.sleep(0.5)
    return True


def fresh_pass(processed):
    """Walk from the newest submission backward, stop once we hit a run of
    already-known problems -- that means we've caught up to existing coverage."""
    print("Fresh pass: checking for newly solved problems...")
    offset, last_key = 0, None
    consecutive_known = 0
    new_count = 0

    while True:
        data = graphql(SUBMISSION_LIST_QUERY, {"offset": offset, "limit": 20, "lastKey": last_key})
        block = data.get("submissionList")
        if not block:
            break
        submissions = block.get("submissions", [])
        if not submissions:
            break

        for sub in submissions:
            if sub.get("statusDisplay") != "Accepted":
                continue
            slug = sub["titleSlug"]
            if slug in processed:
                consecutive_known += 1
                continue
            consecutive_known = 0
            if write_solution(sub):
                processed.add(slug)
                new_count += 1

        if consecutive_known >= CONSECUTIVE_KNOWN_TO_STOP_FRESH_PASS:
            print(f"  Caught up to known problems ({new_count} new found). Fresh pass done.")
            return new_count

        if not block.get("hasNext"):
            print(f"  Reached end of submission history ({new_count} new found).")
            return new_count

        last_key = block.get("lastKey")
        offset += 20
        time.sleep(1)


def backlog_pass(state, processed):
    """Resume older submission history from where the previous run stopped."""
    if state.get("backlog_exhausted"):
        print("Backlog pass: already fully covered older history, nothing to resume.")
        return 0

    print(f"Backlog pass: resuming from offset {state['backlog_offset']}...")
    offset = state["backlog_offset"]
    last_key = state["backlog_last_key"]
    new_count = 0

    while True:
        data = graphql(SUBMISSION_LIST_QUERY, {"offset": offset, "limit": 20, "lastKey": last_key})
        block = data.get("submissionList")
        if not block:
            break
        submissions = block.get("submissions", [])
        if not submissions:
            state["backlog_exhausted"] = True
            break

        for sub in submissions:
            if sub.get("statusDisplay") != "Accepted":
                continue
            slug = sub["titleSlug"]
            if slug in processed:
                continue
            if write_solution(sub):
                processed.add(slug)
                new_count += 1

        last_key = block.get("lastKey")
        offset += 20
        state["backlog_offset"] = offset
        state["backlog_last_key"] = last_key

        if not block.get("hasNext"):
            state["backlog_exhausted"] = True
            break

        time.sleep(1)

    if state.get("backlog_exhausted"):
        # We've scanned all submission history. Restart the cycle from the
        # beginning next run -- already-known problems get skipped instantly
        # via `processed`, so this just keeps re-checking for anything missed.
        cycles = state.get("full_cycles_completed", 0) + 1
        print(f"  Backlog fully scanned (cycle #{cycles} complete). "
              f"Resetting cursor to restart from the beginning next run.")
        state["backlog_offset"] = 0
        state["backlog_last_key"] = None
        state["backlog_exhausted"] = False
        state["full_cycles_completed"] = cycles

    print(f"  Backlog pass added {new_count} problem(s) this run.")
    return new_count


def main():
    os.makedirs(BASE_DIR, exist_ok=True)
    state = load_state()
    processed = set(state["processed_slugs"])
    starting_count = len(processed)

    try:
        fresh_pass(processed)
        backlog_pass(state, processed)
    except Blocked as e:
        print(f"  [stopping this run] {e}")
        print("  Progress made so far is saved; the next scheduled run will continue from here.")

    state["processed_slugs"] = sorted(processed)
    save_state(state)

    added = len(processed) - starting_count
    print(f"Run complete. {added} new problem(s) added, {len(processed)} total synced so far.")
    if not state.get("backlog_exhausted"):
        print("Older submission history not fully covered yet -- next scheduled run will resume.")
    else:
        print(f"Full history scan cycle #{state.get('full_cycles_completed', 0)} complete "
              f"-- next run restarts the scan from the beginning.")


if __name__ == "__main__":
    main()
