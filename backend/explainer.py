def generate_explanations(interactions):
    """
    Convert interaction records into
    Doctor View and Patient View.
    """

    doctor = []
    patient = []

    if not interactions:
        return {
            "doctor": "No known drug interactions found.",
            "patient": "No harmful medicine combinations were detected."
        }

    for item in interactions:

        doctor_text = f"""
Drug Pair:
{item['drug1']} + {item['drug2']}

Interaction Type:
{item['relation']}

Clinical Description:
{item['sentence']}

Recommendation:
Monitor the patient and consider an alternative medication if clinically necessary.
"""

        patient_text = f"""
The medicines {item['drug1']} and {item['drug2']} may not work well together.

Possible Risk:
{item['sentence']}

Please talk to your doctor before taking these medicines together.
Do not stop your medication without medical advice.
"""

        doctor.append(doctor_text.strip())
        patient.append(patient_text.strip())

    return {
        "doctor": "\n\n-----------------------\n\n".join(doctor),
        "patient": "\n\n-----------------------\n\n".join(patient)
    }
