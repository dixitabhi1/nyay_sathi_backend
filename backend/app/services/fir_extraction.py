from __future__ import annotations

import re

from app.schemas.fir import FIRStructuredData


class FIRExtractionService:
    def clean_text(self, text: str) -> str:
        cleaned = text.replace("\r", "\n").replace("\xa0", " ")
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    def extract_from_text(self, text: str, defaults: dict | None = None) -> FIRStructuredData:
        defaults = defaults or {}
        cleaned = self.clean_text(text)
        complainant_name = defaults.get("complainant_name") or self._extract_name(cleaned)
        parent_name = self._extract_parent_name(cleaned)
        address = self._extract_field(cleaned, ["address", "resident of"]) or defaults.get("address")
        contact_number = self._extract_phone(cleaned) or defaults.get("contact_number")
        police_station = defaults.get("police_station") or self._extract_field(cleaned, ["police station", "ps"])
        incident_date = self._extract_date(cleaned) or defaults.get("incident_date")
        incident_time = self._extract_time(cleaned) or defaults.get("incident_time")
        incident_location = self._extract_location(cleaned) or defaults.get("incident_location")
        accused_details = self._extract_list(cleaned, ["accused", "suspect", "unknown person"])
        witness_details = self._extract_list(cleaned, ["witness", "seen by"])
        evidence_information = self._extract_list(cleaned, ["evidence", "attached", "annexed", "screenshot", "photo", "video"])
        return FIRStructuredData(
            complainant_name=complainant_name,
            parent_name=parent_name,
            address=address,
            contact_number=contact_number,
            police_station=police_station,
            incident_date=incident_date,
            incident_time=incident_time,
            incident_location=incident_location,
            incident_description=cleaned,
            accused_details=accused_details,
            witness_details=witness_details,
            evidence_information=evidence_information,
        )

    def _extract_name(self, text: str) -> str | None:
        patterns = [
            r"\bmy name is ([A-Z][A-Za-z ]{2,50})",
            r"\bi[, ]+([A-Z][A-Za-z ]{2,50})[,]?\s+(?:resident|residing|would like)",
            r"\bname[:\-]?\s*([A-Z][A-Za-z ]{2,50})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _extract_parent_name(self, text: str) -> str | None:
        match = re.search(r"(?:father|mother)(?:'s)?\s+name[:\-]?\s*([A-Z][A-Za-z ]{2,50})", text, re.IGNORECASE)
        return match.group(1).strip() if match else None

    def _extract_field(self, text: str, labels: list[str]) -> str | None:
        for label in labels:
            pattern = rf"{re.escape(label)}[:\-]?\s*([^\n,.]{{4,120}})"
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _extract_phone(self, text: str) -> str | None:
        match = re.search(r"\b(?:\+91[- ]?)?\d{10}\b", text)
        return match.group(0).strip() if match else None

    def _extract_date(self, text: str) -> str | None:
        patterns = [
            r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
            r"\b\d{1,2}\s+[A-Za-z]+\s+\d{4}\b",
            r"\b(?:yesterday|today|last night|last evening)\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0).strip()
        return None

    def _extract_time(self, text: str) -> str | None:
        patterns = [
            r"\b\d{1,2}[:.]\d{2}\s*(?:AM|PM|am|pm)\b",
            r"\b\d{1,2}\s*(?:AM|PM|am|pm)\b",
            r"\b(?:morning|afternoon|evening|night)\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0).strip()
        return None

    def _extract_location(self, text: str) -> str | None:
        match = re.search(r"(?:near|at|in)\s+([A-Z][A-Za-z0-9 ,.-]{3,80})", text)
        return match.group(1).strip(" ,.-") if match else None

    def _extract_list(self, text: str, labels: list[str]) -> list[str]:
        matches: list[str] = []
        for label in labels:
            pattern = rf"{re.escape(label)}[:\-]?\s*([^\n]{{4,160}})"
            for match in re.finditer(pattern, text, re.IGNORECASE):
                value = match.group(1).strip()
                if value and value not in matches:
                    matches.append(value)
        return matches

