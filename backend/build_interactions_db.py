"""
build_interactions_db.py

One-time data prep script: parses the DDI2013 corpus (already downloaded
locally under data/ddi_processed/data/*.jsonl) into a real, dataset-derived
drug interaction database (CSV), instead of a hand-curated interaction list.

WHY THIS MATTERS FOR YOUR PROJECT:
DDI2013 sentences are drawn from real drug labels/medical text and each
one is annotated with whether two drug mentions interact, and (if so) what
KIND of interaction it is (mechanism / effect / advise / int). Aggregating
these gives you a genuinely dataset-derived interaction table you can point
to and say "built from DDI2013", not something you typed by hand.

USAGE:
    cd backend
    python build_interactions_db.py

OUTPUT:
    data/interactions_db.csv with columns:
        drug_1, drug_2, relation_type, severity, evidence_sentence, mention_count

NOTE ON SEVERITY:
DDI2013 relation types are NOT a severity scale. This script uses a
reasonable, documented heuristic mapping below. You should sanity-check
this mapping against a few examples and adjust it — don't present it as
clinically validated without review. That's an honest caveat to mention
in your hackathon presentation too.
"""

import json
import csv
import os
import re
from collections import defaultdict

# ---- adjust these if your paths differ ----
DDI_PROCESSED_DIR = os.path.join("..", "data", "ddi_processed", "data")
TRAIN_FILE = os.path.join(DDI_PROCESSED_DIR, "train.jsonl")
TEST_FILE = os.path.join(DDI_PROCESSED_DIR, "test.jsonl")
OUTPUT_CSV = os.path.join("..", "data", "interactions_db.csv")

# Heuristic severity mapping — REVIEW THIS, it's a starting assumption,
# not a medically validated severity scale.
RELATION_TO_SEVERITY = {
    "mechanism": "High",     # pharmacokinetic mechanism described — usually significant
    "effect": "Moderate",    # describes a resulting clinical effect
    "advise": "Moderate",    # source text recommends caution/action
    "int": "Low",            # interaction stated with no further detail given
}


def load_jsonl(path):
    records = []
    if not os.path.exists(path):
        print(f"  [skip] {path} not found")
        return records
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def detect_schema(sample):
    """Return 'bigbio' if the record has entities+relations lists,
    'tagged' if it has inline <e1>/<e2> tags with a label field,
    'flat' if it has direct drug1/drug2/relation fields,
    else 'unknown'."""
    if not sample:
        return "unknown"
    keys = set(sample.keys())
    if "entities" in keys and "relations" in keys:
        return "bigbio"
    if {"drug1", "drug2", "relation"}.issubset(keys):
        return "flat"
    text_field = sample.get("text") or sample.get("sentence") or ""
    if "<e1>" in text_field or "<e2>" in text_field:
        return "tagged"
    return "unknown"


def extract_flat(records):
    """Format: {"sentence": ..., "drug1": ..., "drug2": ...,
    "relation": "EFFECT"/"MECHANISM"/"ADVISE"/"INT"/"NULL" (or similar negative label)}"""
    pairs = []
    negative_labels = {"null", "none", "negative", "no_rel", "false", "0", ""}
    for rec in records:
        d1 = str(rec.get("drug1", "")).strip()
        d2 = str(rec.get("drug2", "")).strip()
        rel_type = str(rec.get("relation", "")).strip().lower()
        sentence = str(rec.get("sentence", "")).strip()
        if not d1 or not d2 or rel_type in negative_labels:
            continue
        pairs.append((d1, d2, rel_type, sentence))
    return pairs


def extract_bigbio(records):
    """Format: {"text": ..., "entities": [{"id","text","type","offsets"}],
    "relations": [{"type","arg1_id","arg2_id"}]}"""
    pairs = []
    for rec in records:
        text = rec.get("text", "")
        entities = {e["id"]: e for e in rec.get("entities", [])}
        for rel in rec.get("relations", []):
            rel_type = str(rel.get("type", "")).lower()
            if not rel_type or rel_type in ("negative", "no_rel", "none", "false"):
                continue
            e1 = entities.get(rel.get("arg1_id"))
            e2 = entities.get(rel.get("arg2_id"))
            if not e1 or not e2:
                continue
            d1 = e1.get("text", "").strip()
            d2 = e2.get("text", "").strip()
            if not d1 or not d2:
                continue
            pairs.append((d1, d2, rel_type, text))
    return pairs


def extract_tagged(records):
    """Format: {"sentence"/"text": "... <e1>Drug1</e1> ... <e2>Drug2</e2> ...",
    "label"/"relation": "mechanism"}"""
    pairs = []
    tag_re = re.compile(r"<e[12]>(.*?)</e[12]>")
    for rec in records:
        text = rec.get("text") or rec.get("sentence") or ""
        label = str(rec.get("label") or rec.get("relation") or "").lower()
        if not label or label in ("negative", "no_rel", "none", "false", "0"):
            continue
        matches = tag_re.findall(text)
        if len(matches) < 2:
            continue
        d1, d2 = matches[0].strip(), matches[1].strip()
        clean_text = re.sub(r"</?e[12]>", "", text)
        pairs.append((d1, d2, label, clean_text))
    return pairs


def normalize_pair_key(d1, d2):
    a, b = d1.strip().lower(), d2.strip().lower()
    return tuple(sorted([a, b]))


def build_database():
    print("Loading DDI2013 splits...")
    train = load_jsonl(TRAIN_FILE)
    test = load_jsonl(TEST_FILE)
    all_records = train + test
    print(f"  loaded {len(train)} train + {len(test)} test = {len(all_records)} records")

    if not all_records:
        print("No records found. Check DDI_PROCESSED_DIR path at the top of this script.")
        return

    schema = detect_schema(all_records[0])
    print(f"Detected schema: {schema}")
    print(f"Sample record keys: {list(all_records[0].keys())}")

    if schema == "bigbio":
        pairs = extract_bigbio(all_records)
    elif schema == "tagged":
        pairs = extract_tagged(all_records)
    elif schema == "flat":
        pairs = extract_flat(all_records)
    else:
        print("\nCould not auto-detect schema.")
        print("Here is a raw sample record so we can adapt the parser:")
        print(json.dumps(all_records[0], indent=2)[:2000])
        return

    print(f"Extracted {len(pairs)} raw interacting drug-pair mentions")

    # aggregate: same pair may appear in multiple sentences / relation types
    agg = defaultdict(lambda: {"relation_types": defaultdict(int), "example_sentence": ""})
    for d1, d2, rel_type, sentence in pairs:
        key = normalize_pair_key(d1, d2)
        agg[key]["relation_types"][rel_type] += 1
        agg[key]["d1_display"] = d1
        agg[key]["d2_display"] = d2
        if not agg[key]["example_sentence"]:
            agg[key]["example_sentence"] = sentence.strip()[:300]

    print(f"Aggregated into {len(agg)} unique drug pairs")

    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "drug_1", "drug_2", "relation_type", "severity",
            "mention_count", "evidence_sentence"
        ])
        for key, data in agg.items():
            # pick the most frequent relation type for this pair
            top_relation = max(data["relation_types"].items(), key=lambda kv: kv[1])[0]
            mention_count = sum(data["relation_types"].values())
            severity = RELATION_TO_SEVERITY.get(top_relation, "Low")
            writer.writerow([
                data["d1_display"], data["d2_display"], top_relation,
                severity, mention_count, data["example_sentence"]
            ])

    print(f"\nDone. Wrote {len(agg)} interaction pairs to {OUTPUT_CSV}")
    print("Next: sanity-check a few rows, then wire interactions.py to load this CSV.")


if __name__ == "__main__":
    build_database()
