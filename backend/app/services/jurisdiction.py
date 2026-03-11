from __future__ import annotations

import json
from functools import cached_property
from pathlib import Path

from app.schemas.fir import FIRJurisdictionSuggestion


class JurisdictionService:
    def __init__(self, gazetteer_path: Path) -> None:
        self.gazetteer_path = gazetteer_path

    @cached_property
    def gazetteer(self) -> list[dict]:
        if not self.gazetteer_path.exists():
            return []
        return json.loads(self.gazetteer_path.read_text(encoding="utf-8"))

    def suggest(self, incident_location: str | None) -> FIRJurisdictionSuggestion | None:
        if not incident_location:
            return None
        lowered = incident_location.lower()
        for row in self.gazetteer:
            aliases = [row["location"].lower(), *[alias.lower() for alias in row.get("aliases", [])]]
            if any(alias in lowered or lowered in alias for alias in aliases):
                return FIRJurisdictionSuggestion(
                    suggested_police_station=row["police_station"],
                    district=row.get("district"),
                    state=row.get("state"),
                    source="local_gazetteer",
                    confidence=float(row.get("confidence", 0.84)),
                    latitude=row.get("latitude"),
                    longitude=row.get("longitude"),
                )

        try:
            from geopy.geocoders import Nominatim
        except Exception:
            return FIRJurisdictionSuggestion(
                suggested_police_station="Nearest police station to be confirmed",
                state=None,
                district=None,
                source="fallback",
                confidence=0.3,
            )

        try:
            geolocator = Nominatim(user_agent="nyayasetu-jurisdiction")
            location = geolocator.geocode(incident_location, country_codes="in", timeout=10)
            if not location:
                return FIRJurisdictionSuggestion(
                    suggested_police_station="Nearest police station to be confirmed",
                    source="fallback",
                    confidence=0.3,
                )
            display_name = location.address.split(",")[0]
            return FIRJurisdictionSuggestion(
                suggested_police_station=f"{display_name} Police Station",
                district=None,
                state=None,
                source="nominatim",
                confidence=0.45,
                latitude=location.latitude,
                longitude=location.longitude,
            )
        except Exception:
            return FIRJurisdictionSuggestion(
                suggested_police_station="Nearest police station to be confirmed",
                source="fallback",
                confidence=0.3,
            )

