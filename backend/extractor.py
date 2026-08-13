"""
extractor.py (vocabulary-based version, no torch/transformers)

Step 6 of the build: extract drug names from free text (e.g. a pasted
prescription note) WITHOUT a heavy ML model.

Why not BioBERT here: on this machine, `torch` fails to load
(OSError WinError 4551 — a Windows Application Control / WDAC policy on
a managed laptop blocking torch's DLLs). That's an OS-level restriction,
not fixable from Python, and not worth chasing on a hackathon deadline.

Instead, this builds a vocabulary directly from data/interactions_db.csv
(every drug_1/drug_2 name we already have, ~2000 unique terms) and scans
free text for occurrences of those terms using word-boundary matching.
This has no external ML dependency, runs instantly, and is arguably MORE
reliable than a generic biomedical NER model for THIS dataset, since it
can only ever "find" drugs that interactions.py can actually look up
anyway (no wasted extractions on drugs with no interaction data).

Trade-off vs. real NER: this only recognizes vocabulary present in the
DDI2013-derived dataset (plus common brand names in normalizer.py) — it
won't recognize a totally novel drug name never seen in that data. That's
an acceptable trade-off for this project's scope.
"""

import os
import re

import pandas as pd

from normalizer import normalize_drug, BRAND_TO_GENERIC, DRUG_CLASSES

_CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "interactions_db.csv")

_vocab = None          # sorted list of vocabulary terms, longest first
_vocab_pattern = None  # compiled regex


def _build_vocabulary() -> list:
    """Collect every drug/class name we could plausibly match:
    - all drug_1/drug_2 values from interactions_db.csv
    - all brand names from normalizer.py's BRAND_TO_GENERIC
    - all class alias strings from normalizer.py's DRUG_CLASSES
    Returned sorted longest-first so multi-word terms (e.g. "loop
    diuretics") are matched before a shorter substring could grab part
    of it."""
    terms = set()

    if os.path.exists(_CSV_PATH):
        df = pd.read_csv(_CSV_PATH)
        for col in ("drug_1", "drug_2"):
            terms.update(str(v).strip() for v in df[col].dropna().unique())

    terms.update(BRAND_TO_GENERIC.keys())
    for spec in DRUG_CLASSES.values():
        terms.update(spec["aliases"])

    # Drop very short/ambiguous terms (single letters, 2-char abbreviations)
    # that would cause false-positive matches inside unrelated words.
    terms = {t for t in terms if len(t) >= 4}

    return sorted(terms, key=len, reverse=True)


def _get_vocab_pattern():
    global _vocab, _vocab_pattern
    if _vocab_pattern is None:
        _vocab = _build_vocabulary()
        # Word-boundary alternation. Escaped so terms with parens/hyphens
        # (e.g. "monoamine oxidase (mao) inhibitors") don't break the regex.
        escaped = [re.escape(t) for t in _vocab]
        pattern = r"\b(?:" + "|".join(escaped) + r")\b"
        _vocab_pattern = re.compile(pattern, flags=re.IGNORECASE)
    return _vocab_pattern


def extract_drug_mentions(text: str) -> list:
    """Scan free text for known drug/class vocabulary. Returns raw
    matched strings (original casing from the text), deduplicated, in
    order of first appearance."""
    if not text or not text.strip():
        return []

    pattern = _get_vocab_pattern()
    seen = set()
    mentions = []
    for match in pattern.finditer(text):
        raw = match.group(0)
        key = raw.lower()
        if key not in seen:
            seen.add(key)
            mentions.append(raw)

    return mentions


def extract_and_normalize(text: str) -> list:
    """Full pipeline: free text -> raw drug mentions -> normalized drugs.
    Returns a list of NormalizedDrug objects, exactly like normalizer.py
    already produces for manually-typed input, so interactions.py /
    main.py can consume this the same way."""
    mentions = extract_drug_mentions(text)
    return [normalize_drug(m) for m in mentions]


if __name__ == "__main__":
    sample_note = (
        "Patient is currently on EQUETRO 200mg twice daily and ethosuximide "
        "500mg for seizure control. Also taking low-dose aspirin and reports "
        "occasional use of Crocin for headaches. Consider monitoring digoxin "
        "levels given the sympathomimetics prescribed for her asthma."
    )

    print("Raw text:\n", sample_note, "\n")

    raw_mentions = extract_drug_mentions(sample_note)
    print("Extracted mentions:", raw_mentions, "\n")

    normalized = extract_and_normalize(sample_note)
    for nd in normalized:
        print(f"{nd.original!r:20} -> {nd.normalized!r:25} "
              f"match_type={nd.match_type:15} is_class={nd.is_class}")