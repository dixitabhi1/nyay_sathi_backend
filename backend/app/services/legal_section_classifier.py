from __future__ import annotations

from functools import cached_property

from app.schemas.fir import FIRSectionSuggestion
from app.services.retriever import Retriever


SECTION_RULES = [
    {
        "title": "Theft",
        "fallback_section": "BNS - Theft",
        "keywords": ["stole", "stolen", "theft", "snatched", "phone", "wallet", "bike"],
        "reasoning": "The complaint describes unauthorized taking of movable property from the complainant.",
    },
    {
        "title": "Criminal Intimidation",
        "fallback_section": "BNS - Criminal Intimidation",
        "keywords": ["threat", "threatened", "intimidation", "kill", "harm", "extortion"],
        "reasoning": "The complaint describes threats intended to cause alarm or coerce the complainant.",
    },
    {
        "title": "Cheating",
        "fallback_section": "BNS - Cheating",
        "keywords": ["fraud", "cheated", "scam", "dishonest", "investment", "money"],
        "reasoning": "The complaint suggests deception or dishonest inducement leading to wrongful loss.",
    },
    {
        "title": "Voluntarily Causing Hurt / Assault",
        "fallback_section": "BNS - Hurt / Assault",
        "keywords": ["hit", "beat", "assault", "injury", "hurt", "slapped", "attack"],
        "reasoning": "The complaint includes physical violence or bodily injury.",
    },
    {
        "title": "Sexual Harassment / Stalking",
        "fallback_section": "BNS - Sexual Harassment / Stalking",
        "keywords": ["harass", "molest", "stalk", "obscene", "touch", "sexual"],
        "reasoning": "The complaint indicates unwelcome sexual conduct, harassment, or repeated following/contact.",
    },
    {
        "title": "Criminal Trespass",
        "fallback_section": "BNS - Criminal Trespass",
        "keywords": ["trespass", "entered", "broke into", "house", "premises"],
        "reasoning": "The complaint suggests unlawful entry into property or premises.",
    },
    {
        "title": "Mischief / Property Damage",
        "fallback_section": "BNS - Mischief / Property Damage",
        "keywords": ["damage", "destroyed", "vandalized", "broke", "fire"],
        "reasoning": "The complaint involves damage or destruction of property.",
    },
]


class LegalSectionClassifier:
    def __init__(self, retriever: Retriever, model_name: str | None = None) -> None:
        self.retriever = retriever
        self.model_name = model_name

    def classify(self, incident_description: str) -> tuple[list[FIRSectionSuggestion], str]:
        model_predictions = self._predict_with_model(incident_description)
        if model_predictions:
            reasoning = " ".join(suggestion.reasoning for suggestion in model_predictions[:3])
            return model_predictions[:3], reasoning

        lowered = incident_description.lower()
        matched: list[FIRSectionSuggestion] = []
        for rule in SECTION_RULES:
            hits = sum(1 for keyword in rule["keywords"] if keyword in lowered)
            if hits == 0:
                continue
            section_label = self._resolve_section_label(incident_description, rule["fallback_section"])
            matched.append(
                FIRSectionSuggestion(
                    section=section_label,
                    title=rule["title"],
                    reasoning=rule["reasoning"],
                    confidence=min(0.55 + (hits * 0.1), 0.95),
                )
            )
        if not matched:
            retrieved = self.retriever.search(incident_description, 3)
            if retrieved:
                matched.append(
                    FIRSectionSuggestion(
                        section=retrieved[0]["citation"],
                        title=retrieved[0]["title"],
                        reasoning="The suggestion is based on the closest retrieved legal provision from the corpus.",
                        confidence=0.5,
                    )
                )
            else:
                matched.append(
                    FIRSectionSuggestion(
                        section="BNS - Section lookup pending",
                        title="Further legal review required",
                        reasoning="No confident rule-based mapping matched the complaint. Manual legal review is required.",
                        confidence=0.35,
                    )
                )
        reasoning = " ".join(suggestion.reasoning for suggestion in matched[:3])
        return matched[:3], reasoning

    def _resolve_section_label(self, description: str, fallback: str) -> str:
        retrieved = self.retriever.search(description, 5)
        for item in retrieved:
            citation = item.get("citation", "")
            if "BNS" in citation or "Bharatiya Nyaya Sanhita" in citation:
                return citation
        return fallback

    @cached_property
    def zero_shot_classifier(self):
        if not self.model_name:
            return None
        try:
            from transformers import pipeline

            return pipeline(
                "zero-shot-classification",
                model=self.model_name,
                device_map="auto",
            )
        except Exception:
            return None

    def _predict_with_model(self, incident_description: str) -> list[FIRSectionSuggestion]:
        classifier = self.zero_shot_classifier
        if classifier is None:
            return []

        candidate_labels = [rule["title"] for rule in SECTION_RULES]
        try:
            result = classifier(incident_description, candidate_labels=candidate_labels, multi_label=True)
        except Exception:
            return []

        suggestions: list[FIRSectionSuggestion] = []
        for label, score in zip(result["labels"], result["scores"], strict=False):
            if score < 0.45:
                continue
            rule = next((item for item in SECTION_RULES if item["title"] == label), None)
            if not rule:
                continue
            suggestions.append(
                FIRSectionSuggestion(
                    section=self._resolve_section_label(incident_description, rule["fallback_section"]),
                    title=label,
                    reasoning=f"Model prediction suggests {label.lower()} based on the legal incident description.",
                    confidence=float(score),
                )
            )
        return suggestions
