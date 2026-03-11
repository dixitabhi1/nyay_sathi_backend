from __future__ import annotations

from app.schemas.fir import FIRCompletenessResponse, FIRStructuredData


class FIRCompletenessService:
    def evaluate(self, structured: FIRStructuredData) -> FIRCompletenessResponse:
        checks = {
            "complainant name": bool(structured.complainant_name),
            "address": bool(structured.address),
            "police station": bool(structured.police_station),
            "incident date": bool(structured.incident_date),
            "incident time": bool(structured.incident_time),
            "incident location": bool(structured.incident_location),
            "incident description": bool(structured.incident_description and len(structured.incident_description) > 40),
            "accused details": bool(structured.accused_details),
            "witness information": bool(structured.witness_details),
            "evidence information": bool(structured.evidence_information),
            "contact number": bool(structured.contact_number),
        }
        passed = sum(1 for value in checks.values() if value)
        score = int(round((passed / len(checks)) * 100))
        missing_fields = [field for field, present in checks.items() if not present]
        suggestions = [
            self._suggestion_for(field)
            for field in missing_fields
        ]
        if not suggestions:
            suggestions.append("FIR contains the key details needed for preliminary review.")
        return FIRCompletenessResponse(
            completeness_score=score,
            missing_fields=missing_fields,
            suggestions=suggestions,
        )

    def _suggestion_for(self, field: str) -> str:
        mapping = {
            "complainant name": "Add the complainant's full name as per identity proof.",
            "address": "Add a serviceable residential address for follow-up.",
            "police station": "Confirm the police station handling the FIR.",
            "incident date": "Specify the date or approximate date of the incident.",
            "incident time": "Add the exact or approximate time of occurrence.",
            "incident location": "Mention a specific incident location or nearby landmark.",
            "incident description": "Provide a clearer narrative of what happened and how.",
            "accused details": "Include any known accused description, identifiers, or note unknown accused.",
            "witness information": "Add witness names or state that no witness is available.",
            "evidence information": "List any documents, photos, CCTV, or digital evidence.",
            "contact number": "Provide a reachable mobile number for updates.",
        }
        return mapping.get(field, f"Add the missing field: {field}.")

