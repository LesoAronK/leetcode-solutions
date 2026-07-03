import os
import re

BASE_DIR = "problems"

pattern = re.compile(r"^(\d+)_(.+)$")

renamed = 0
skipped = 0

for name in sorted(os.listdir(BASE_DIR)):
    full_path = os.path.join(BASE_DIR, name)
    if not os.path.isdir(full_path):
        continue  # skip .sync_state.json etc.

    match = pattern.match(name)
    if not match:
        print(f"  [skip] '{name}' doesn't match expected '<number>_<title>' pattern.")
        skipped += 1
        continue

    number, rest = match.groups()
    padded = number.zfill(2)

    if number == padded:
        continue  # already padded correctly

    new_name = f"{padded}_{rest}"
    new_path = os.path.join(BASE_DIR, new_name)

    if os.path.exists(new_path):
        print(f"  [skip] Target '{new_name}' already exists, not overwriting.")
        skipped += 1
        continue

    os.rename(full_path, new_path)
    print(f"  Renamed '{name}' -> '{new_name}'")
    renamed += 1

print(f"\nDone. Renamed {renamed} folder(s), skipped {skipped}.")
