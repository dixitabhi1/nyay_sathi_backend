from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from math import asin, cos, radians, sin, sqrt

from app.db.session import SessionLocal
from app.models.fir import FIRIntelligence, FIRRecord
from app.schemas.fir import FIRCrimePatternResponse, FIRCrimePatternSummary, FIRHeatmapPoint


class CrimePatternService:
    def get_patterns(self, window_days: int = 7) -> FIRCrimePatternResponse:
        session = SessionLocal()
        try:
            records = session.query(FIRRecord, FIRIntelligence).outerjoin(
                FIRIntelligence, FIRIntelligence.fir_id == FIRRecord.id
            ).all()
        finally:
            session.close()

        cutoff = datetime.utcnow() - timedelta(days=window_days)
        grouped: dict[tuple[str, str], list[tuple[FIRRecord, FIRIntelligence | None]]] = defaultdict(list)
        heatmap_counter: Counter[tuple[str, str]] = Counter()
        heatmap_coords: dict[tuple[str, str], tuple[float | None, float | None]] = {}

        recent_records = 0
        for record, intelligence in records:
            if record.created_at < cutoff:
                continue
            recent_records += 1
            crime_category = (intelligence.crime_category if intelligence and intelligence.crime_category else self._derive_crime_category(record))
            location = (
                intelligence.incident_location
                if intelligence and intelligence.incident_location
                else json.loads(record.extracted_payload).get("incident_location")
                or "Unknown location"
            )
            grouped[(crime_category, location)].append((record, intelligence))
            heatmap_counter[(crime_category, location)] += 1
            heatmap_coords[(crime_category, location)] = (
                intelligence.latitude if intelligence else None,
                intelligence.longitude if intelligence else None,
            )

        hotspot_alerts: list[FIRCrimePatternSummary] = []
        for (crime_category, location), entries in sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True):
            count = len(entries)
            if count < 2:
                continue
            hotspot_alerts.append(
                FIRCrimePatternSummary(
                    crime_category=crime_category,
                    incident_count=count,
                    location=location,
                    window_days=window_days,
                    insight=f"{count} {crime_category.lower()} incidents were recorded around {location} in the last {window_days} days.",
                    suggested_attention_area=f"Increase patrol and surveillance around {location}.",
                )
            )

        heatmap_points = [
            FIRHeatmapPoint(
                location=location,
                latitude=heatmap_coords[(crime_category, location)][0],
                longitude=heatmap_coords[(crime_category, location)][1],
                intensity=count,
                crime_category=crime_category,
            )
            for (crime_category, location), count in heatmap_counter.items()
        ]
        return FIRCrimePatternResponse(
            total_records=recent_records,
            hotspot_alerts=hotspot_alerts[:10],
            heatmap_points=sorted(heatmap_points, key=lambda item: item.intensity, reverse=True),
        )

    def _derive_crime_category(self, record: FIRRecord) -> str:
        try:
            sections = json.loads(record.suggested_sections)
            if sections:
                return sections[0].get("title", "General Crime")
        except Exception:
            pass
        return "General Crime"

    def nearby_records(self, latitude: float, longitude: float, radius_km: float = 1.0, window_days: int = 7) -> int:
        session = SessionLocal()
        try:
            rows = session.query(FIRIntelligence).all()
        finally:
            session.close()

        cutoff = datetime.utcnow() - timedelta(days=window_days)
        count = 0
        for row in rows:
            if row.latitude is None or row.longitude is None or row.created_at < cutoff:
                continue
            if self._haversine(latitude, longitude, row.latitude, row.longitude) <= radius_km:
                count += 1
        return count

    def _haversine(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        d_lat = radians(lat2 - lat1)
        d_lon = radians(lon2 - lon1)
        a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
        return 6371 * 2 * asin(sqrt(a))
