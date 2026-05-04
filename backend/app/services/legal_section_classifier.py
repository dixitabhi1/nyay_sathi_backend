from __future__ import annotations

from functools import cached_property

from app.schemas.fir import FIRComparativeSectionsResponse, FIRSectionSuggestion
from app.services.retriever import Retriever


SECTION_RULES = [
    {
        "title": "Theft",
        "keywords": ["stole", "stolen", "theft", "snatched", "phone", "wallet", "bike", "robbed"],
        "reasoning": "The complaint describes dishonest removal of movable property without consent.",
        "bns": "BNS Section 303 - Theft",
        "ipc": "IPC Section 379 - Theft",
        "bnss": "BNSS Section 173 - Information in cognizable cases",
        "crpc": "CrPC Section 154 - Information in cognizable cases",
        "title_hint": "theft",
    },
    {
        "title": "Criminal Intimidation",
        "keywords": ["threat", "threatened", "kill", "harm", "intimidation", "extortion", "menace"],
        "reasoning": "The narrative suggests threats intended to cause alarm or compel action.",
        "bns": "BNS Section 351 - Criminal intimidation",
        "ipc": "IPC Section 506 - Criminal intimidation",
        "bnss": "BNSS Section 173 - Information in cognizable cases",
        "crpc": "CrPC Section 154 - Information in cognizable cases",
        "title_hint": "criminal intimidation",
    },
    {
        "title": "Cheating / Online Fraud",
        "keywords": ["fraud", "cheated", "scam", "otp", "payment", "investment", "bank", "transaction"],
        "reasoning": "The facts suggest deception causing wrongful loss and digital or financial misuse.",
        "bns": "BNS Section 318 - Cheating",
        "ipc": "IPC Section 420 - Cheating and dishonestly inducing delivery of property",
        "bnss": "BNSS Section 173 - Information in cognizable cases",
        "crpc": "CrPC Section 154 - Information in cognizable cases",
        "title_hint": "cheating",
    },
    {
        "title": "Voluntarily Causing Hurt / Assault",
        "keywords": ["hit", "beat", "assault", "injury", "hurt", "slapped", "attack", "punch"],
        "reasoning": "The complaint includes bodily violence, assault, or injuries.",
        "bns": "BNS Section 115 - Voluntarily causing hurt",
        "ipc": "IPC Section 323 - Voluntarily causing hurt",
        "bnss": "BNSS Section 173 - Information in cognizable cases",
        "crpc": "CrPC Section 154 - Information in cognizable cases",
        "title_hint": "hurt",
    },
    {
        "title": "Sexual Harassment / Stalking",
        "keywords": ["harass", "molest", "stalk", "obscene", "touch", "sexual", "followed"],
        "reasoning": "The complaint indicates unwelcome sexual behaviour, harassment, or stalking.",
        "bns": "BNS Section 75 - Sexual harassment",
        "ipc": "IPC Section 354A - Sexual harassment",
        "bnss": "BNSS Section 173 - Information in cognizable cases",
        "crpc": "CrPC Section 154 - Information in cognizable cases",
        "title_hint": "sexual harassment",
    },
    {
        "title": "Criminal Trespass",
        "keywords": ["trespass", "entered", "broke into", "house", "premises", "property"],
        "reasoning": "The allegations point to unlawful entry into property or premises.",
        "bns": "BNS Section 329 - Criminal trespass",
        "ipc": "IPC Section 447 - Criminal trespass",
        "bnss": "BNSS Section 173 - Information in cognizable cases",
        "crpc": "CrPC Section 154 - Information in cognizable cases",
        "title_hint": "trespass",
    },
    {
        "title": "Mischief / Property Damage",
        "keywords": ["damage", "destroyed", "vandalized", "broke", "fire", "property damage"],
        "reasoning": "The complaint involves damage or destruction of property.",
        "bns": "BNS Section 324 - Mischief",
        "ipc": "IPC Section 427 - Mischief causing damage",
        "bnss": "BNSS Section 173 - Information in cognizable cases",
        "crpc": "CrPC Section 154 - Information in cognizable cases",
        "title_hint": "mischief",
    },
]


STATUTE_ALIASES = {
    "BNS": ("BNS", "Bharatiya Nyaya Sanhita", "Act No. 45 of 2023"),
    "BNSS": ("BNSS", "Bharatiya Nagarik Suraksha Sanhita", "Act No. 46 of 2023"),
    "IPC": ("IPC", "Indian Penal Code"),
    "CrPC": ("CrPC", "Code of Criminal Procedure"),
}


class LegalSectionClassifier:
    def __init__(self, retriever: Retriever, model_name: str | None = None) -> None:
        self.retriever = retriever
        self.model_name = model_name

    def classify(self, incident_description: str) -> tuple[list[FIRSectionSuggestion], str]:
        model_predictions = self._predict_with_model(incident_description)
        if model_predictions:
            reasoning = " ".join(suggestion.reasoning for suggestion in model_predictions[:3])
            return model_predictions[:3], reasoning

        rules = self._matched_rules(incident_description)
        if rules:
            suggestions = [self._build_bns_suggestion(incident_description, rule, confidence=0.72 + index * 0.05) for index, rule in enumerate(rules[:3])]
            reasoning = " ".join(item.reasoning for item in suggestions)
            return suggestions, reasoning

        retrieved = self.retriever.search(incident_description, 3)
        if retrieved:
            suggestion = FIRSectionSuggestion(
                statute_code="BNS",
                section=retrieved[0]["citation"],
                title=retrieved[0]["title"],
                reasoning="The suggestion is based on the closest retrieved legal provision from the corpus.",
                confidence=0.5,
            )
            return [suggestion], suggestion.reasoning

        fallback = FIRSectionSuggestion(
            statute_code="BNS",
            section="BNS - Section lookup pending",
            title="Further legal review required",
            reasoning="No confident classification matched the complaint. Manual legal review is required.",
            confidence=0.35,
        )
        return [fallback], fallback.reasoning

    def compare_sections(
        self,
        incident_description: str,
        primary_sections: list[FIRSectionSuggestion] | None = None,
    ) -> FIRComparativeSectionsResponse:
        rules = self._matched_rules(incident_description)
        if not rules and primary_sections:
            rules = [self._rule_for_section(primary_sections[0].title)] if primary_sections else []
            rules = [rule for rule in rules if rule]
        if not rules:
            primary_bns = primary_sections[:3] if primary_sections else []
            return FIRComparativeSectionsResponse(
                bns=primary_bns,
                bnss=[
                    FIRSectionSuggestion(
                        statute_code="BNSS",
                        section="BNSS Section 173 - Information in cognizable cases",
                        title="FIR registration process",
                        reasoning="Procedural FIR registration usually begins with information relating to a cognizable offence.",
                        confidence=0.46,
                    )
                ],
                ipc=[],
                crpc=[
                    FIRSectionSuggestion(
                        statute_code="CrPC",
                        section="CrPC Section 154 - Information in cognizable cases",
                        title="FIR registration process",
                        reasoning="Legacy comparison uses the CrPC provision traditionally cited for FIR registration.",
                        confidence=0.46,
                    )
                ],
            )

        bns = [self._build_bns_suggestion(incident_description, rule, confidence=0.78 - index * 0.05) for index, rule in enumerate(rules[:3])]
        bnss = [self._build_statute_suggestion(incident_description, rule, "BNSS", confidence=0.7 - index * 0.05) for index, rule in enumerate(rules[:2])]
        ipc = [self._build_statute_suggestion(incident_description, rule, "IPC", confidence=0.74 - index * 0.05) for index, rule in enumerate(rules[:3])]
        crpc = [self._build_statute_suggestion(incident_description, rule, "CrPC", confidence=0.68 - index * 0.05) for index, rule in enumerate(rules[:2])]
        return FIRComparativeSectionsResponse(bns=bns, bnss=bnss, ipc=ipc, crpc=crpc)

    @cached_property
    def zero_shot_classifier(self):
        if not self.model_name:
            return None
        try:
            from transformers import pipeline

            return pipeline("zero-shot-classification", model=self.model_name, device_map="auto")
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
            rule = self._rule_for_section(label)
            if not rule:
                continue
            suggestions.append(self._build_bns_suggestion(incident_description, rule, confidence=float(score)))
        return suggestions

    def _matched_rules(self, incident_description: str) -> list[dict]:
        lowered = incident_description.lower()
        scored: list[tuple[int, dict]] = []
        for rule in SECTION_RULES:
            hits = sum(1 for keyword in rule["keywords"] if keyword in lowered)
            if hits > 0:
                scored.append((hits, rule))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [rule for _, rule in scored]

    def _build_bns_suggestion(self, description: str, rule: dict, confidence: float) -> FIRSectionSuggestion:
        return self._build_statute_suggestion(description, rule, "BNS", confidence)

    def _build_statute_suggestion(
        self,
        description: str,
        rule: dict,
        statute_code: str,
        confidence: float,
    ) -> FIRSectionSuggestion:
        resolved = str(rule[statute_code.lower()])
        return FIRSectionSuggestion(
            statute_code=statute_code,
            section=resolved,
            title=rule["title"] if statute_code in {"BNS", "IPC"} else "FIR registration process",
            reasoning=rule["reasoning"] if statute_code in {"BNS", "IPC"} else "Procedural comparison for FIR registration and complaint handling.",
            confidence=max(0.35, min(confidence, 0.95)),
        )

    def _resolve_section_label(
        self,
        description: str,
        fallback: str,
        preferred_title: str,
        statute_code: str,
    ) -> str:
        retrieved = self.retriever.search(description, 6)
        aliases = STATUTE_ALIASES.get(statute_code, (statute_code,))
        for item in retrieved:
            citation = item.get("citation", "")
            haystack = f"{item.get('title', '')} {citation} {item.get('text', '')}".lower()
            if preferred_title and preferred_title.lower() not in haystack:
                continue
            if any(alias.lower() in haystack for alias in aliases):
                return citation
        for item in retrieved:
            citation = item.get("citation", "")
            haystack = f"{item.get('title', '')} {citation} {item.get('text', '')}".lower()
            if any(alias.lower() in haystack for alias in aliases):
                return citation
        return fallback

    def _rule_for_section(self, title: str | None) -> dict | None:
        if not title:
            return None
        lowered = title.lower()
        return next((rule for rule in SECTION_RULES if rule["title"].lower() == lowered), None)
