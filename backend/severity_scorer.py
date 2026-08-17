"""
severity_scorer.py

Composite severity scoring for drug interactions, replacing the flat
"copy the relation_type into a severity label" heuristic from the
original database build with a transparent, multi-signal score.

This does NOT replace the original severity column from
interactions_db.csv (kept as `source_severity` for provenance/traceability)
— it computes a second, independent `computed_severity` derived from
several weighted signals, plus a numeric `severity_score` (0-100) and a
`score_breakdown` so the reasoning is inspectable, not a black box.

IMPORTANT CAVEAT (state this explicitly in any write-up / demo): none of
these weights have been clinically validated. They encode a reasonable,
explainable heuristic based on publicly known risk factors (e.g.
anticoagulants and MAOIs are broadly recognized as high-risk interaction
classes), not a substitute for pharmacist/clinician judgment.
"""

import re

# Base score by relation_type: mechanism (pharmacokinetic) and effect
# (pharmacodynamic) interactions reflect an actual physiological
# mechanism, so they score higher than "advise" rows, which are often
# administrative timing notes (e.g. "take 2 hours apart") rather than a
# fundamental incompatibility.
RELATION_BASE_SCORE = {
    "mechanism": 45,
    "effect": 40,
    "int": 35,
    "advise": 20,
}
DEFAULT_RELATION_SCORE = 25

# Drug classes with broadly-recognized high interaction risk (narrow
# therapeutic index, or well-documented dangerous combination potential).
# Sourced from general pharmacology knowledge, not a clinical database —
# flagged as such in caveats above.
HIGH_RISK_CLASSES = {
    "anticoagulants", "monoamine oxidase inhibitors", "potassium-sparing diuretics",
}
MODERATE_RISK_CLASSES = {
    "corticosteroids", "beta blockers", "ace inhibitors", "calcium channel blockers",
    "nsaids", "loop diuretics", "thiazide diuretics",
}

# Keyword signals scanned in the evidence sentence. Weighted by how
# strongly the language implies real clinical danger.
HIGH_RISK_KEYWORDS = {
    "contraindicated": 15, "fatal": 20, "death": 20, "life-threatening": 18,
    "toxicity": 12, "severe": 10, "serious": 8,
}
MODERATE_RISK_KEYWORDS = {
    "increased risk": 8, "caution": 5, "monitor": 5, "adjust": 4, "reduce": 3,
}

MENTION_COUNT_CAP = 10  # diminishing returns beyond this many mentions
CLASS_FALLBACK_PENALTY = 8  # scored down since it's a less certain match


def _relation_score(relation_type):
    if not relation_type:
        return DEFAULT_RELATION_SCORE
    return RELATION_BASE_SCORE.get(relation_type.lower(), DEFAULT_RELATION_SCORE)


def _class_risk_score(drug_1_normalized, drug_2_normalized):
    """Bonus if either side of the interaction is a known high/moderate
    risk drug class."""
    names = set()
    for d in (drug_1_normalized, drug_2_normalized):
        if d.is_class:
            names.add(d.normalized)
    if names & HIGH_RISK_CLASSES:
        return 15, f"high-risk class present ({', '.join(names & HIGH_RISK_CLASSES)})"
    if names & MODERATE_RISK_CLASSES:
        return 8, f"moderate-risk class present ({', '.join(names & MODERATE_RISK_CLASSES)})"
    return 0, None


def _keyword_score(evidence_sentence):
    if not evidence_sentence:
        return 0, []
    text = evidence_sentence.lower()
    score = 0
    hits = []
    for kw, weight in HIGH_RISK_KEYWORDS.items():
        if kw in text:
            score += weight
            hits.append(kw)
    for kw, weight in MODERATE_RISK_KEYWORDS.items():
        if kw in text:
            score += weight
            hits.append(kw)
    return score, hits


def _mention_score(mention_count):
    capped = min(mention_count or 0, MENTION_COUNT_CAP)
    return round((capped / MENTION_COUNT_CAP) * 10)


def score_to_band(score):
    if score >= 65:
        return "Critical"
    if score >= 45:
        return "High"
    if score >= 25:
        return "Moderate"
    return "Low"


def compute_severity(interaction_result):
    """Takes an InteractionResult (from interactions.py) with found=True
    and returns a dict with the composite score, band, and a breakdown
    of which signals contributed — so the score is explainable, not a
    black box."""
    if not interaction_result.found:
        return None

    breakdown = {}

    relation_pts = _relation_score(interaction_result.relation_type)
    breakdown["relation_type"] = {
        "value": interaction_result.relation_type,
        "points": relation_pts,
    }

    class_pts, class_reason = _class_risk_score(
        interaction_result.drug_1_normalized, interaction_result.drug_2_normalized
    )
    breakdown["drug_class_risk"] = {"points": class_pts, "reason": class_reason}

    keyword_pts, keyword_hits = _keyword_score(interaction_result.evidence_sentence)
    breakdown["evidence_keywords"] = {"points": keyword_pts, "matched": keyword_hits}

    mention_pts = _mention_score(interaction_result.mention_count)
    breakdown["literature_mentions"] = {
        "value": interaction_result.mention_count,
        "points": mention_pts,
    }

    penalty = 0
    if interaction_result.confidence == "class_fallback":
        penalty = CLASS_FALLBACK_PENALTY
        breakdown["confidence_penalty"] = {
            "points": -penalty,
            "reason": "class-level match, not a confirmed specific-drug pair",
        }

    raw_score = relation_pts + class_pts + keyword_pts + mention_pts - penalty
    score = max(0, min(100, raw_score))
    band = score_to_band(score)

    return {
        "source_severity": interaction_result.severity,  # original heuristic label, kept for provenance
        "computed_severity": band,
        "severity_score": score,
        "score_breakdown": breakdown,
    }


if __name__ == "__main__":
    from interactions import get_db

    db = get_db()
    test_pairs = [
        ("EQUETRO", "ethosuximide"),
        ("digoxin", "sympathomimetics"),
        ("warfarin", "anticoagulants"),
    ]
    for a, b in test_pairs:
        result = db.check(a, b)
        print(f"\n{a} + {b}")
        print(f"  found={result.found}")
        if result.found:
            scored = compute_severity(result)
            print(f"  source_severity={scored['source_severity']} -> "
                  f"computed_severity={scored['computed_severity']} "
                  f"(score={scored['severity_score']}/100)")
            for signal, detail in scored["score_breakdown"].items():
                print(f"    {signal}: {detail}")