import json
from pathlib import Path

DATA_FILE = Path(__file__).parent.parent / "data" / "ddi_processed" / "data" / "train.jsonl"

interaction_db = []


def load_database():
    global interaction_db

    if interaction_db:
        return

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        for line in f:
            interaction_db.append(json.loads(line))


load_database()


def check_interactions(drugs):
    """
    drugs = ["aspirin","warfarin","ibuprofen"]
    """

    results = []

    drugs = [d.lower().strip() for d in drugs]

    for i in range(len(drugs)):
        for j in range(i + 1, len(drugs)):

            d1 = drugs[i]
            d2 = drugs[j]

            for record in interaction_db:

                a = record["drug1"].lower()
                b = record["drug2"].lower()

                if (d1 == a and d2 == b) or (d1 == b and d2 == a):

                    results.append({
                        "drug1": record["drug1"],
                        "drug2": record["drug2"],
                        "relation": record["relation"],
                        "sentence": record["sentence"]
                    })

    return results