"""
explainer.py (MOCK / template-based version)

Same purpose and same function signatures as the Claude-API version:
generate a doctor-facing and patient-facing explanation for a found drug
interaction. This version uses rule-based templates instead of calling
the Claude API, so it's free to run for demos/development.

Swap-in note: if you later get API credits, replace the body of
explain_interaction() with the anthropic.messages.create() call — main.py
and the frontend don't need to change at all, since the return shape
({"doctor_explanation": ..., "patient_explanation": ...}) is identical.
"""

SEVERITY_LANGUAGE = {
    "High": {
        "doctor": "high clinical significance",
        "patient": "considered a significant interaction",
        "urgency": "should be reviewed before these are taken together",
    },
    "Moderate": {
        "doctor": "moderate clinical significance",
        "patient": "worth being aware of",
        "urgency": "may need monitoring or dose adjustment",
    },
    "Low": {
        "doctor": "low clinical significance",
        "patient": "generally minor",
        "urgency": "is unlikely to require action, but is still worth noting",
    },
}

RELATION_LANGUAGE = {
    "effect": "an altered pharmacological effect",
    "mechanism": "a pharmacokinetic mechanism (affecting absorption, metabolism, or clearance)",
    "advise": "a specific dosing or administration precaution",
    "int": "a documented interaction",
}


def _severity_info(severity):
    return SEVERITY_LANGUAGE.get(severity, SEVERITY_LANGUAGE["Moderate"])


def _relation_phrase(relation_type):
    if not relation_type:
        return "a documented interaction"
    return RELATION_LANGUAGE.get(relation_type.lower(), f"a documented '{relation_type}' interaction")


def _build_doctor_explanation(interaction) -> str:
    d1 = interaction.drug_1_normalized
    d2 = interaction.drug_2_normalized
    sev = _severity_info(interaction.severity)
    relation_phrase = _relation_phrase(interaction.relation_type)

    class_note = ""
    if d1.is_class or d2.is_class:
        class_note = (
            " Note: this match involves a drug CLASS rather than a specific "
            "confirmed drug pair, so treat this as a class-level signal, not "
            "a verified specific-drug interaction."
        )

    confidence_note = ""
    if interaction.confidence == "class_fallback":
        confidence_note = " This was resolved via class-level fallback matching."

    return (
        f"Interaction between {d1.normalized} and {d2.normalized}: source data "
        f"indicates {relation_phrase}, rated {sev['doctor']} "
        f"(mentioned {interaction.mention_count} time"
        f"{'s' if interaction.mention_count != 1 else ''} in reference material). "
        f"Documented evidence: \"{interaction.evidence_sentence}\" "
        f"Recommended action: {sev['urgency']}.{class_note}{confidence_note}"
    )


def _urgency_patient_phrase(severity):
    """Patient-friendly phrasing of urgency, avoiding the awkward
    string-replace hack that produced double phrasing before."""
    phrases = {
        "High": "your doctor or pharmacist should review this combination before you take them together",
        "Moderate": "this combination may need some monitoring or a dose adjustment",
        "Low": "this combination is generally low-risk, but it's still worth mentioning to your doctor",
    }
    return phrases.get(severity, phrases["Moderate"])


def _build_patient_explanation(interaction) -> str:
    d1 = interaction.drug_1_normalized
    d2 = interaction.drug_2_normalized
    sev = _severity_info(interaction.severity)
    urgency_phrase = _urgency_patient_phrase(interaction.severity)

    hedge = ""
    if d1.is_class or d2.is_class:
        hedge = (
            " This was matched based on a general drug category rather than "
            "your exact medication, so it may not apply precisely to you."
        )

    return (
        f"{interaction.drug_1_input} and {interaction.drug_2_input} have a known "
        f"interaction that is {sev['patient']}. In practice, this means "
        f"{urgency_phrase}.{hedge} Please tell your doctor or pharmacist that "
        f"you're taking both of these so they can advise you — don't stop or "
        f"change either medication on your own."
    )


def explain_interaction(interaction) -> dict:
    """Generate doctor/patient explanations for a single found interaction
    using templates (no API call, no cost).

    Returns the same shape as the real Claude-API version:
    {"doctor_explanation": str, "patient_explanation": str}
    """
    if not interaction.found:
        return {"doctor_explanation": None, "patient_explanation": None}

    return {
        "doctor_explanation": _build_doctor_explanation(interaction),
        "patient_explanation": _build_patient_explanation(interaction),
    }


def explain_many(interactions: list) -> list:
    """Attach explanations to a list of InteractionResult objects."""
    explained = []
    for interaction in interactions:
        if interaction.found:
            explanation = explain_interaction(interaction)
        else:
            explanation = {"doctor_explanation": None, "patient_explanation": None}
        explained.append((interaction, explanation))
    return explained


if __name__ == "__main__":
    from interactions import get_db

    db = get_db()
    result = db.check("EQUETRO", "ethosuximide")
    print(f"Interaction found: {result.found}, severity: {result.severity}\n")

    if result.found:
        explanation = explain_interaction(result)
        print("=== DOCTOR EXPLANATION ===")
        print(explanation["doctor_explanation"])
        print("\n=== PATIENT EXPLANATION ===")
        print(explanation["patient_explanation"])

    # Also test a class-fallback case
    print("\n---\n")
    result2 = db.check("digoxin", "sympathomimetics")
    print(f"Interaction found: {result2.found}, confidence: {result2.confidence}\n")
    if result2.found:
        explanation2 = explain_interaction(result2)
        print("=== DOCTOR EXPLANATION ===")
        print(explanation2["doctor_explanation"])
        print("\n=== PATIENT EXPLANATION ===")
        print(explanation2["patient_explanation"])