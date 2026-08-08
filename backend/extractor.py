import re

# Words to ignore
IGNORE_WORDS = {
    "tablet", "tablets", "tab",
    "capsule", "capsules", "cap",
    "mg", "ml", "g",
    "morning", "night", "daily",
    "once", "twice", "thrice",
    "before", "after", "food",
    "breakfast", "lunch", "dinner",
    "take"
}

# Common drugs (expand later)
KNOWN_DRUGS = {
    "crocin",
    "dolo",
    "warfarin",
    "ibuprofen",
    "augmentin",
    "paracetamol",
    "aspirin",
    "metformin",
    "atorvastatin",
    "amoxicillin",
    "clavulanic",
    "digoxin",
    "sympathomimetics"
}

def extract_drugs(text: str):
    words = re.findall(r"[A-Za-z]+", text)

    drugs = []

    for word in words:
        w = word.lower()

        if w in IGNORE_WORDS:
            continue

        if w in KNOWN_DRUGS:
            drugs.append(w)   # Return lowercase

    return list(dict.fromkeys(drugs))