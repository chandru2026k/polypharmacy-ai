"""
scan_unresolved.py

Runs every unique drug_1/drug_2 value from interactions_db.csv through
normalize_drug() and reports:
  - how many are unresolved (no brand/class/generic match)
  - how many are class-level matches
  - the actual unresolved names, sorted by frequency, so we know what to
    add to BRAND_TO_GENERIC / KNOWN_GENERICS next.

Run from backend/ (same folder as normalizer.py and data/interactions_db.csv).
"""

import pandas as pd
from collections import Counter
from normalizer import normalize_drug
df = pd.read_csv("../data/interactions_db.csv")

names = pd.concat([df["drug_1"], df["drug_2"]]).tolist()
counts = Counter(names)

results = {name: normalize_drug(name) for name in counts}

by_type = Counter(r.match_type for r in results.values())

print("=== Match type breakdown (unique names) ===")
for match_type, count in by_type.most_common():
    print(f"  {match_type:15} {count}")

print(f"\nTotal unique drug names: {len(results)}")

unresolved = [
    (name, counts[name])
    for name, r in results.items()
    if r.match_type == "unresolved"
]
unresolved.sort(key=lambda x: -x[1])

print(f"\n=== Top 40 unresolved names by frequency (of {len(unresolved)} total) ===")
for name, freq in unresolved[:40]:
    print(f"  {freq:4d}  {name}")

classes_found = [
    (name, counts[name])
    for name, r in results.items()
    if r.match_type == "class"
]
classes_found.sort(key=lambda x: -x[1])

print(f"\n=== Class-level matches found ({len(classes_found)}) ===")
for name, freq in classes_found:
    print(f"  {freq:4d}  {name}")

# Save full unresolved list to file for easier review / dictionary building
with open("../data/unresolved_drugs.txt", "w") as f:
    for name, freq in unresolved:
        f.write(f"{freq}\t{name}\n")

print("\nFull unresolved list written to data/unresolved_drugs.txt")