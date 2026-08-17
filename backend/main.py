"""
main.py

FastAPI entrypoint for the polypharmacy interaction checker.
"""

import os
import tempfile
from typing import List, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from interactions import check_medication_list, get_db
from explainer import explain_interaction
from extractor import extract_and_normalize, extract_drug_mentions
from ocr_processor import extract_text_from_image
from severity_scorer import compute_severity

app = FastAPI(
    title="Polypharmacy Interaction Checker API",
    description="Checks a medication list for known drug-drug interactions.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class MedicationCheckRequest(BaseModel):
    drugs: List[str] = Field(
        ..., min_length=2,
        description="List of drug names as typed by the user (brand or generic, any casing).",
        examples=[["EQUETRO", "ethosuximide", "Crocin"]],
    )


class NoteExtractRequest(BaseModel):
    text: str = Field(
        ..., min_length=1,
        description="Free text (e.g. a clinical note) to scan for drug mentions.",
        examples=["Patient is on EQUETRO 200mg and ethosuximide 500mg for seizure control."],
    )


class NormalizedDrugOut(BaseModel):
    original: str
    normalized: str
    match_type: str
    is_class: bool


class InteractionOut(BaseModel):
    drug_1: str
    drug_2: str
    drug_1_normalized: NormalizedDrugOut
    drug_2_normalized: NormalizedDrugOut
    found: bool
    relation_type: Optional[str] = None
    severity: Optional[str] = None
    mention_count: int = 0
    evidence_sentence: Optional[str] = None
    confidence: str
    note: Optional[str] = None
    doctor_explanation: Optional[str] = None
    patient_explanation: Optional[str] = None
    computed_severity: Optional[str] = None
    severity_score: Optional[int] = None
    score_breakdown: Optional[dict] = None


class MedicationCheckResponse(BaseModel):
    drug_count: int
    pairs_checked: int
    interactions_found: int
    results: List[InteractionOut]


def _to_normalized_out(nd) -> NormalizedDrugOut:
    return NormalizedDrugOut(
        original=nd.original,
        normalized=nd.normalized,
        match_type=nd.match_type,
        is_class=nd.is_class,
    )


def _to_interaction_out(result) -> InteractionOut:
    explanation = explain_interaction(result) if result.found else {}
    scored = compute_severity(result) if result.found else None
    return InteractionOut(
        drug_1=result.drug_1_input,
        drug_2=result.drug_2_input,
        drug_1_normalized=_to_normalized_out(result.drug_1_normalized),
        drug_2_normalized=_to_normalized_out(result.drug_2_normalized),
        found=result.found,
        relation_type=result.relation_type,
        severity=result.severity,
        mention_count=result.mention_count,
        evidence_sentence=result.evidence_sentence,
        confidence=result.confidence,
        note=result.note,
        doctor_explanation=explanation.get("doctor_explanation"),
        patient_explanation=explanation.get("patient_explanation"),
        computed_severity=scored["computed_severity"] if scored else None,
        severity_score=scored["severity_score"] if scored else None,
        score_breakdown=scored["score_breakdown"] if scored else None,
    )


@app.on_event("startup")
def _preload_db():
    get_db()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/check-interactions", response_model=MedicationCheckResponse)
def check_interactions(payload: MedicationCheckRequest):
    drugs = [d.strip() for d in payload.drugs if d.strip()]
    if len(drugs) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 non-empty drug names are required to check interactions.",
        )

    raw_results = check_medication_list(drugs)
    results = [_to_interaction_out(r) for r in raw_results]
    found_count = sum(1 for r in results if r.found)

    return MedicationCheckResponse(
        drug_count=len(drugs),
        pairs_checked=len(results),
        interactions_found=found_count,
        results=results,
    )


@app.post("/extract-and-check", response_model=MedicationCheckResponse)
def extract_and_check(payload: NoteExtractRequest):
    raw_mentions = extract_drug_mentions(payload.text)

    if len(raw_mentions) < 2:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Found only {len(raw_mentions)} recognizable drug name(s) in the "
                f"text. At least 2 are needed to check for interactions. "
                f"Detected: {raw_mentions}"
            ),
        )

    raw_results = check_medication_list(raw_mentions)
    results = [_to_interaction_out(r) for r in raw_results]
    found_count = sum(1 for r in results if r.found)

    return MedicationCheckResponse(
        drug_count=len(raw_mentions),
        pairs_checked=len(results),
        interactions_found=found_count,
        results=results,
    )


@app.post("/ocr-and-check", response_model=MedicationCheckResponse)
async def ocr_and_check(file: UploadFile = File(...)):
    allowed_types = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file.content_type}'. Upload a PNG, JPEG, or WEBP image.",
        )

    suffix = os.path.splitext(file.filename or "")[1] or ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        contents = await file.read()
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        try:
            ocr_text = extract_text_from_image(tmp_path)
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))

        raw_mentions = extract_drug_mentions(ocr_text)

        if len(raw_mentions) < 2:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"OCR found only {len(raw_mentions)} recognizable drug name(s) "
                    f"in the image. At least 2 are needed to check for interactions. "
                    f"Detected: {raw_mentions}. OCR text was: {ocr_text[:300]!r}"
                ),
            )

        raw_results = check_medication_list(raw_mentions)
        results = [_to_interaction_out(r) for r in raw_results]
        found_count = sum(1 for r in results if r.found)

        return MedicationCheckResponse(
            drug_count=len(raw_mentions),
            pairs_checked=len(results),
            interactions_found=found_count,
            results=results,
        )
    finally:
        os.unlink(tmp_path)