import os, requests

CSRFTOKEN = os.getenv("LEETCODE_CSRF_TOKEN")
LEETCODE_SESSION = os.getenv("LEETCODE_SESSION")

headers = {
    "x-csrftoken": CSRFTOKEN,
    "cookie": f"LEETCODE_SESSION={LEETCODE_SESSION}; csrftoken={CSRFTOKEN}"
}

ext_map = {
    "python3": "py",
    "java": "java",
    "cpp": "cpp",
    "c": "c",
    "csharp": "cs",
    "javascript": "js"
}

offset = 0
limit = 50
latest_solutions = {}

# Fetch all submissions
while True:
    url = f"https://leetcode.com/api/submissions/?offset={offset}&limit={limit}"
    resp = requests.get(url, headers=headers)
    data = resp.json()
    submissions = data.get("submissions_dump", [])
    if not submissions:
        break

    for sub in submissions:
        if sub["status_display"] == "Accepted":
            qid = sub["question_id"]
            # overwrite older with newer → keeps latest accepted
            latest_solutions[qid] = sub

    offset += limit

# Base directory for problems
base_dir = "problems"
os.makedirs(base_dir, exist_ok=True)

# Write one folder per problem
for qid, sub in latest_solutions.items():
    title = sub["title"]
    slug = sub["title_slug"]
    lang = sub["lang"]
    code = sub["code"]

    folder = os.path.join(base_dir, f"{qid}_{title.replace(' ', '_').lower()}")
    if os.path.exists(folder):
        continue  # skip if already present

    os.makedirs(folder, exist_ok=True)

    with open(os.path.join(folder, "README.md"), "w", encoding="utf-8") as f:
        f.write(f"# {title} (Problem #{qid})\n\n")
        f.write(f"Link: https://leetcode.com/problems/{slug}/\n")

    ext = ext_map.get(lang, "txt")
    with open(os.path.join(folder, f"solution.{ext}"), "w", encoding="utf-8") as f:
        f.write(code)
