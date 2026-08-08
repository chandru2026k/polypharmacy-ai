from rapidfuzz import process

# Brand -> Generic Database
BRAND_TO_GENERIC = {
    "crocin": "Paracetamol",
    "dolo": "Paracetamol",
    "calpol": "Paracetamol",

    "augmentin": "Amoxicillin + Clavulanic Acid",
    "amoxyclav": "Amoxicillin + Clavulanic Acid",

    "combiflam": "Ibuprofen + Paracetamol",

    "brufen": "Ibuprofen",
    "ibuprofen": "Ibuprofen",

    "warfarin": "Warfarin",

    "ecosprin": "Aspirin",
    "aspirin": "Aspirin",

    "glycomet": "Metformin",
    "metformin": "Metformin",

    "atorva": "Atorvastatin",
    "atorvastatin": "Atorvastatin",

    "amoxicillin": "Amoxicillin"
}


def normalize_drugs(drugs):

    normalized = []

    keys = list(BRAND_TO_GENERIC.keys())

    for drug in drugs:

        match = process.extractOne(
            drug.lower(),
            keys,
            score_cutoff=80
        )

        if match:

            normalized.append(BRAND_TO_GENERIC[match[0]])

        else:

            normalized.append(drug)

    return normalized