"""
interactions.py

Runtime lookup module for the polypharmacy interaction checker.

Given two (or more) raw drug name strings as typed by a user, this:
  1. Normalizes each name via normalizer.py (brand -> generic, class
     detection, artifact cleanup)
  2. Looks up the pair against data/interactions_db.csv
  3. If no exact pair is found and one/both sides normalized to a drug
     CLASS, falls back to checking the class's representative members
  4. Returns a structured result with a confidence level, since matches
     range from "exact generic pair, high mention count" down to
     "class-level fallback, single mention" and the explainer/UI need to
     know the difference.

This module is intentionally dependency-light (pandas only) so main.py
can import check_interaction() directly.
"""

import os
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from normalizer import normalize_drug, NormalizedDrug

_CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "interactions_db.csv")

# Confidence tiers, most to least trustworthy. Used by explainer.py / the
# frontend to decide how strongly to word a warning.
CONFIDENCE_EXACT = "exact"                # both drugs matched directly (brand/generic)
CONFIDENCE_CLASS_FALLBACK = "class_fallback"  # one or both sides matched via a drug class
CONFIDENCE_NONE = "none"                  # no interaction found in db


@dataclass
class InteractionResult:
    drug_1_input: str
    drug_2_input: str
    drug_1_normalized: NormalizedDrug
    drug_2_normalized: NormalizedDrug
    found: bool
    relation_type: Optional[str] = None
    severity: Optional[str] = None
    mention_count: int = 0
    evidence_sentence: Optional[str] = None
    confidence: str = CONFIDENCE_NONE
    note: Optional[str] = None  # human-readable caveat, e.g. "matched via drug class"


class InteractionDB:
    """Loads interactions_db.csv once and answers pairwise lookups."""

    def __init__(self, csv_path: str = _CSV_PATH):
        self.csv_path = csv_path
        self._df = None
        self._pair_index = {}  # (generic_a, generic_b) sorted tuple -> list of row dicts
        self._load()

    def _load(self):
        if not os.path.exists(self.csv_path):
            raise FileNotFoundError(
                f"interactions_db.csv not found at {self.csv_path}. "
                f"Run build_interactions_db.py first."
            )
        self._df = pd.read_csv(self.csv_path)

        # Pre-normalize every row's drug names once at load time and build
        # a lookup index, so runtime queries don't re-scan the full CSV.
        for _, row in self._df.iterrows():
            n1 = normalize_drug(str(row["drug_1"])).normalized
            n2 = normalize_drug(str(row["drug_2"])).normalized
            key = tuple(sorted([n1, n2]))
            self._pair_index.setdefault(key, []).append(row.to_dict())

    def _lookup_pair(self, name_a: str, name_b: str):
        """Direct index lookup for a normalized pair. Returns list of
        matching rows (usually 0 or 1, occasionally more if the same pair
        appears with different relation types)."""
        key = tuple(sorted([name_a, name_b]))
        return self._pair_index.get(key, [])

    def check(self, raw_drug_1: str, raw_drug_2: str) -> InteractionResult:
        d1 = normalize_drug(raw_drug_1)
        d2 = normalize_drug(raw_drug_2)

        # 1. Exact normalized-name match (both sides specific drugs, or
        #    exact class-vs-class match)
        rows = self._lookup_pair(d1.normalized, d2.normalized)
        if rows:
            best = max(rows, key=lambda r: r.get("mention_count", 0))
            confidence = CONFIDENCE_EXACT
            note = None
            if d1.is_class or d2.is_class:
                confidence = CONFIDENCE_CLASS_FALLBACK
                note = "Matched at the drug-class level, not a specific drug pair."
            return InteractionResult(
                drug_1_input=raw_drug_1, drug_2_input=raw_drug_2,
                drug_1_normalized=d1, drug_2_normalized=d2,
                found=True,
                relation_type=best.get("relation_type"),
                severity=best.get("severity"),
                mention_count=int(best.get("mention_count", 0)),
                evidence_sentence=best.get("evidence_sentence"),
                confidence=confidence,
                note=note,
            )

        # 2. Class fallback: if one side is a class and the direct pair
        #    wasn't found, try each of that class's representative members
        #    against the other drug. This catches cases like
        #    ("digoxin", "sympathomimetics") where the db has the class
        #    but the user typed a specific drug, or vice versa.
        candidates = []
        if d1.is_class and d1.class_members:
            candidates.extend((m, d2.normalized) for m in d1.class_members)
        if d2.is_class and d2.class_members:
            candidates.extend((d1.normalized, m) for m in d2.class_members)

        for a, b in candidates:
            rows = self._lookup_pair(a, b)
            if rows:
                best = max(rows, key=lambda r: r.get("mention_count", 0))
                return InteractionResult(
                    drug_1_input=raw_drug_1, drug_2_input=raw_drug_2,
                    drug_1_normalized=d1, drug_2_normalized=d2,
                    found=True,
                    relation_type=best.get("relation_type"),
                    severity=best.get("severity"),
                    mention_count=int(best.get("mention_count", 0)),
                    evidence_sentence=best.get("evidence_sentence"),
                    confidence=CONFIDENCE_CLASS_FALLBACK,
                    note=(
                        f"No direct match found; matched via class member "
                        f"'{a if a != d1.normalized else b}'."
                    ),
                )

        # 3. Nothing found
        return InteractionResult(
            drug_1_input=raw_drug_1, drug_2_input=raw_drug_2,
            drug_1_normalized=d1, drug_2_normalized=d2,
            found=False, confidence=CONFIDENCE_NONE,
            note="No known interaction found in database. This does NOT mean the "
                 "combination is safe — it may simply be absent from our source data.",
        )

    def check_many(self, drug_list: list) -> list:
        """Check all pairwise combinations for a list of >=2 drugs.
        Used when a user enters a full medication list, not just a pair."""
        results = []
        for i in range(len(drug_list)):
            for j in range(i + 1, len(drug_list)):
                results.append(self.check(drug_list[i], drug_list[j]))
        return results


# Module-level singleton so main.py can just call check_interaction(a, b)
# without managing DB loading itself.
_db_instance = None


def get_db() -> InteractionDB:
    global _db_instance
    if _db_instance is None:
        _db_instance = InteractionDB()
    return _db_instance


def check_interaction(drug_1: str, drug_2: str) -> InteractionResult:
    return get_db().check(drug_1, drug_2)


def check_medication_list(drugs: list) -> list:
    return get_db().check_many(drugs)


if __name__ == "__main__":
    db = get_db()
    print(f"Loaded {len(db._df)} rows, {len(db._pair_index)} unique normalized pairs.\n")

    test_pairs = [
        ("digoxin", "sympathomimetics"),
        ("EQUETROTM", "ethosuximide"),
        ("Crocin", "Ecosprin"),
        ("aspirin", "ibuprofen"),  # likely not in db — tests "not found" path
    ]
    for a, b in test_pairs:
        result = db.check(a, b)
        print(f"{a!r} + {b!r}")
        print(f"  found={result.found} confidence={result.confidence}")
        if result.found:
            print(f"  severity={result.severity} relation={result.relation_type} "
                  f"mentions={result.mention_count}")
            print(f"  evidence: {result.evidence_sentence}")
        if result.note:
            print(f"  note: {result.note}")
        print()