"""
normalizer.py

Normalizes messy drug name strings from DDI2013 / user input into a
consistent form the interaction lookup (interactions.py) can match against.

Handles three problems seen in the real data:
  1. Trademark/OCR artifacts on brand names (e.g. "EQUETROTM" -> "Equetro")
  2. Brand -> generic mapping
  3. Drug CLASS entries (e.g. "corticosteroids") which aren't a single drug
     and need a fallback strategy instead of a normal fuzzy match

Returns a NormalizedDrug object per input so downstream code knows whether
a match was exact, fuzzy, class-level, or unresolved (important for
confidence in the doctor/patient explanations later).
"""

import re
from dataclasses import dataclass
from rapidfuzz import process, fuzz

# ---------------------------------------------------------------------------
# 1. Brand -> Generic mapping
#    Includes common OTC brands + the specific brands that showed up in
#    interactions_db.csv (EQUETRO, OMNICEF, SULAR). Extend this as more
#    unmatched brands turn up during testing.
# ---------------------------------------------------------------------------
BRAND_TO_GENERIC = {
    # common OTC / general
    "crocin": "paracetamol",
    "dolo": "paracetamol",
    "calpol": "paracetamol",
    "augmentin": "amoxicillin + clavulanic acid",
    "amoxyclav": "amoxicillin + clavulanic acid",
    "combiflam": "ibuprofen + paracetamol",
    "brufen": "ibuprofen",
    "ecosprin": "aspirin",
    "glycomet": "metformin",
    "atorva": "atorvastatin",

    # brands present in interactions_db.csv
    "equetro": "carbamazepine",
    "omnicef": "cefdinir",
    "sular": "nisoldipine",
}

# NOTE: We do NOT maintain a whitelist of "known generics" anymore.
# Scanning the real interactions_db.csv showed ~93% of names (ketoconazole,
# lithium, erythromycin, cyclosporine, etc.) are already generic drug names
# that simply weren't on a hand-picked list. Maintaining an exhaustive
# generic whitelist doesn't scale. Instead: if a name isn't a brand and
# isn't a drug class, we ASSUME it's already a generic name (see step 6
# in normalize_drug). "unresolved" is now reserved for genuinely garbled
# fragments (e.g. stray abbreviations like "T.A.").

# ---------------------------------------------------------------------------
# 2. Drug classes -> representative member drugs + alias variants.
#    The real data has heavy spelling/casing/pluralization drift for the
#    SAME class (e.g. "anticoagulant" / "anticoagulants" / "coumarin-type
#    anticoagulants" / "warfarin-type anticoagulant" all mean the same
#    thing). A flat fuzzy match doesn't reliably collapse these, so each
#    canonical class has an explicit alias list built from what actually
#    showed up in scan_unresolved.py's "class-level matches" output.
# ---------------------------------------------------------------------------
DRUG_CLASSES = {
    "anticoagulants": {
        "members": ["warfarin", "heparin"],
        "aliases": [
            "anticoagulant", "anticoagulants", "coumarin-type anticoagulants",
            "coumarin anticoagulants", "coumarin anticoagulant",
            "anticoagulants of the coumarin type", "anti-coagulants",
            "warfarin-type anticoagulant", "warfarin-type anticoagulants",
            "coumarin-derivative anticoagulants", "anticoagulant agents",
            "anticoagulant medication", "anticoagulant drugs",
        ],
    },
    "corticosteroids": {
        "members": ["prednisone", "dexamethasone", "hydrocortisone"],
        "aliases": [
            "corticosteroid", "corticosteroids", "steroids", "steroid",
            "cortico-steroids",
        ],
    },
    "nsaids": {
        "members": ["ibuprofen", "naproxen", "diclofenac"],
        "aliases": [
            "nsaid", "nsaids", "non-steroidal anti-inflammatory agent",
            "non-steroidal anti-inflammatory agents",
            "non- steroidal antiinflammatory agent",
            "non- steroidal anti- inflammatory agents",
            "nonsteroidal anti-inflammatory drugs",
            "nonsteroidal anti-inflammatory drug",
            "nonsteroidal anti-inflammatory agents",
            "nonsteroidal antiinflammatory agents",
            "nonsteroidal antiinflammatory drugs",
            "nonsteroial anti-inflammatory drugs",
            "nonsteroidal anti inflammatory drug",
            "steroidal anti-inflammatory agent", "nonsteroidal anti-inflammatory",
        ],
    },
    "monoamine oxidase inhibitors": {
        "members": ["phenelzine", "tranylcypromine"],
        "aliases": [
            "mao inhibitors", "mao-a inhibitors", "monoamine oxidase inhibitors",
            "monoamine oxidase inhibitor", "monoamine oxidase (mao) inhibitors",
            "monoamine oxi-dase inhibitors", "monoamine oxidase inhibiting drugs",
        ],
    },
    "diuretics": {
        "members": ["furosemide", "hydrochlorothiazide", "spironolactone"],
        "aliases": ["diuretic", "diuretics"],
    },
    "loop diuretics": {
        "members": ["furosemide", "bumetanide"],
        "aliases": ["loop diuretics", "loop diuretic"],
    },
    "thiazide diuretics": {
        "members": ["hydrochlorothiazide", "chlorthalidone"],
        "aliases": [
            "thiazide diuretics", "thiazide diuretic", "thiazides",
            "thiazide-type diuretics",
        ],
    },
    "potassium-sparing diuretics": {
        "members": ["spironolactone", "amiloride"],
        "aliases": [
            "potassium-sparing diuretics", "potassium- sparing diuretics",
            "potassium sparing diuretics", "non-potassium sparing diuretics",
            "potassium-depleting diuretics",
        ],
    },
    "beta blockers": {
        "members": ["propranolol", "metoprolol", "atenolol"],
        "aliases": [
            "beta-blockers", "beta-blocker", "beta blocker", "beta blockers",
            "beta-adrenergic blockers", "beta adrenergic blockers",
            "beta adrenergic blocking agents", "beta adrenergic antagonists",
            "beta-blocking agent", "beta blocking agents",
            "noncardioselective beta-blockers",
        ],
    },
    "ace inhibitors": {
        "members": ["lisinopril", "enalapril", "ramipril"],
        "aliases": [
            "ace inhibitors", "ace inhibitor",
            "angiotensin converting enzyme (ace) inhibitors",
            "angiotensin-converting enzyme (ace) inhibitors",
        ],
    },
    "calcium channel blockers": {
        "members": ["amlodipine", "diltiazem", "verapamil"],
        "aliases": [
            "calcium channel blockers", "dihydropyridine calcium channel blockers",
        ],
    },
    "antacids": {
        "members": ["aluminum hydroxide", "magnesium hydroxide", "calcium carbonate"],
        "aliases": ["antacid", "antacids"],
    },
    "anticonvulsants": {
        "members": ["phenytoin", "carbamazepine", "valproate"],
        "aliases": ["anticonvulsants", "anticonvulsant"],
    },
    "sympathomimetics": {
        "members": ["epinephrine", "pseudoephedrine", "albuterol"],
        "aliases": [
            "sympathomimetics", "sympathomimetic", "sympathomimetic agents",
            "sympathomimetic drugs", "sympathomimetic amines",
            "sympathomimetic amine", "sympathomimetic bronchodilators",
            "sympathomimetic pressor amines", "sympathomimetic medication",
            "beta adrenergic aerosol bronchodilators",
            "short-acting beta adrenergic aerosol bronchodilators",
            "beta adrenergic agonists",
        ],
    },
    "h2 blockers": {
        "members": ["ranitidine", "famotidine", "cimetidine"],
        "aliases": ["h2 blockers"],
    },
    "h1 blockers": {
        "members": ["diphenhydramine", "loratadine"],
        "aliases": ["h1 blockers"],
    },
    "hmg-coa reductase inhibitors": {
        "members": ["atorvastatin", "simvastatin"],
        "aliases": ["hydroxymethylglutaryl coenzyme a (hmg-coa) reductase inhibitors"],
    },
}

# Flat alias -> canonical class lookup, built once at import time.
_CLASS_ALIAS_LOOKUP = {}
for canonical, spec in DRUG_CLASSES.items():
    for alias in spec["aliases"]:
        _CLASS_ALIAS_LOOKUP[alias] = canonical

# ---------------------------------------------------------------------------
# 3. Known brand names that showed up as high-frequency "unresolved" in
#    scan_unresolved.py (all-caps trade names DDI2013 didn't spell out).
# ---------------------------------------------------------------------------
BRAND_TO_GENERIC.update({
    "sprycel": "dasatinib",
    "nimbex": "cisatracurium",
    "viracept": "nelfinavir",
    "levo-dromoran": "levorphanol",
})

FUZZY_SCORE_CUTOFF = 85


@dataclass
class NormalizedDrug:
    original: str          # raw input string, untouched
    cleaned: str            # after artifact stripping + lowercasing
    normalized: str         # best resolved generic name (or cleaned name if unresolved)
    match_type: str         # "brand" | "class" | "fuzzy_brand" | "fuzzy_class" | "assumed_generic" | "unresolved"
    is_class: bool = False
    class_members: list = None   # populated only when is_class is True


def _strip_artifacts(name: str) -> str:
    """Remove trademark/registered symbols and stray artifacts like the
    'EQUETROTM' -> 'EQUETRO' + 'TM' mashup seen in the DDI2013 text."""
    cleaned = name.strip()
    cleaned = cleaned.replace("™", "").replace("®", "").replace("©", "")
    # catches a trailing "TM"/"®"-as-text artifact stuck to an all-caps brand,
    # e.g. "EQUETROTM" -> "EQUETRO". Only applied to caps-heavy tokens to
    # avoid mangling normal words that legitimately end in "tm".
    if cleaned.isupper() and cleaned.endswith("TM") and len(cleaned) > 4:
        cleaned = cleaned[:-2]
    cleaned = re.sub(r"[^A-Za-z0-9\s\-+]", "", cleaned)  # drop stray punctuation
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _normalize_class_text(text: str) -> str:
    """Extra normalization on top of _strip_artifacts, specifically for
    matching class aliases: drop parenthetical abbreviations like '(MAO)',
    collapse hyphens/extra spaces so 'non- steroidal anti- inflammatory
    agents' lines up with 'non-steroidal anti-inflammatory agents'."""
    t = text.lower()
    t = re.sub(r"\([^)]*\)", "", t)          # drop "(MAO)", "(ACE)" etc.
    t = t.replace("-", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def normalize_drug(raw_name: str) -> NormalizedDrug:
    """Normalize a single drug/class string."""
    cleaned = _strip_artifacts(raw_name)
    lower = cleaned.lower()
    class_text = _normalize_class_text(cleaned)

    # 1. Exact brand match (checked first — brand names are the most
    #    specific/confident match type)
    if lower in BRAND_TO_GENERIC:
        return NormalizedDrug(raw_name, cleaned, BRAND_TO_GENERIC[lower], "brand")

    # 2. Drug class — exact alias match (both raw-lower and the extra
    #    normalized text, since alias lists are written without parens/hyphens)
    if lower in _CLASS_ALIAS_LOOKUP:
        canonical = _CLASS_ALIAS_LOOKUP[lower]
        return NormalizedDrug(
            raw_name, cleaned, canonical, "class",
            is_class=True, class_members=DRUG_CLASSES[canonical]["members"],
        )
    if class_text in _CLASS_ALIAS_LOOKUP:
        canonical = _CLASS_ALIAS_LOOKUP[class_text]
        return NormalizedDrug(
            raw_name, cleaned, canonical, "class",
            is_class=True, class_members=DRUG_CLASSES[canonical]["members"],
        )

    # Fuzzy matching is unreliable on very short/fragmentary strings
    # (e.g. "T.A." falsely matching "beta blockers"), so skip it below
    # a minimum length rather than trusting the score cutoff alone.
    fuzzy_eligible = len(lower) >= 5

    # 3. Fuzzy brand match
    if fuzzy_eligible:
        match = process.extractOne(
            lower, BRAND_TO_GENERIC.keys(), scorer=fuzz.WRatio, score_cutoff=FUZZY_SCORE_CUTOFF
        )
        if match:
            matched_key = match[0]
            return NormalizedDrug(raw_name, cleaned, BRAND_TO_GENERIC[matched_key], "fuzzy_brand")

    # 4. Fuzzy class alias match (catches typos/minor drift not in the
    #    alias list, e.g. "monoamine oxi-dase inhibitors")
    if fuzzy_eligible:
        class_match = process.extractOne(
            class_text, _CLASS_ALIAS_LOOKUP.keys(), scorer=fuzz.WRatio,
            score_cutoff=FUZZY_SCORE_CUTOFF,
        )
        if class_match:
            canonical = _CLASS_ALIAS_LOOKUP[class_match[0]]
            return NormalizedDrug(
                raw_name, cleaned, canonical, "fuzzy_class",
                is_class=True, class_members=DRUG_CLASSES[canonical]["members"],
            )

    # 5. Not a brand, not a class -> assume it's already a generic drug
    #    name (this covers the vast majority: ketoconazole, lithium,
    #    erythromycin, etc.). Reject obviously non-drug fragments
    #    (too short / no letters) as genuinely unresolved.
    if len(lower) >= 3 and re.search(r"[a-z]{3,}", lower):
        return NormalizedDrug(raw_name, cleaned, lower, "assumed_generic")

    # 6. Genuinely unresolved (stray fragments like "T.A.")
    return NormalizedDrug(raw_name, cleaned, lower, "unresolved")


def normalize_drugs(drugs: list) -> list:
    """Batch version. Returns a list of NormalizedDrug objects (not plain
    strings) so interactions.py / main.py can branch on match_type and
    is_class when deciding how confident to be in a flagged interaction."""
    return [normalize_drug(d) for d in drugs]


if __name__ == "__main__":
    test_cases = [
        "EQUETROTM", "OMNICEF", "SULAR", "digoxin", "corticosteroids",
        "sympathomimetics", "loop diuretics", "Crocin", "ketoconazole",
        "anticoagulant", "anticoagulants", "MAO inhibitors",
        "monoamine oxidase inhibitors", "non- steroidal anti- inflammatory agents",
        "SPRYCEL", "T.A.",
    ]
    for t in test_cases:
        result = normalize_drug(t)
        print(f"{t!r:20} -> normalized={result.normalized!r:35} "
              f"match_type={result.match_type:12} is_class={result.is_class}")