from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from backend.extractor import extract_drugs
from backend.interactions import check_interactions
from backend.explainer import generate_explanations

app = FastAPI(title="Polypharmacy AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Prescription(BaseModel):
    text: str

@app.get("/")
def home():
    return {"message": "Polypharmacy AI Backend Running"}

@app.post("/analyze")
def analyze(data: Prescription):

    drugs = extract_drugs(data.text)

    interactions = check_interactions(drugs)

    explanation = generate_explanations(interactions)

    return {
        "drugs": drugs,
        "interactions": interactions,
        "explanations": explanation
    }