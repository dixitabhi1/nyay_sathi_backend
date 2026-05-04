from app.services.legal_section_classifier import LegalSectionClassifier


class FailingRetriever:
    def search(self, *_args, **_kwargs):
        raise AssertionError("Rule-based FIR classification should not call retrieval.")


def test_rule_based_fir_classification_does_not_block_on_retrieval():
    classifier = LegalSectionClassifier(FailingRetriever())

    sections, reasoning = classifier.classify("My mobile phone was stolen near the market.")
    comparative = classifier.compare_sections("My mobile phone was stolen near the market.", sections)

    assert sections[0].section == "BNS Section 303 - Theft"
    assert "dishonest removal" in reasoning
    assert comparative.bns[0].section == "BNS Section 303 - Theft"
    assert comparative.bnss[0].section == "BNSS Section 173 - Information in cognizable cases"
    assert comparative.ipc[0].section == "IPC Section 379 - Theft"
    assert comparative.crpc[0].section == "CrPC Section 154 - Information in cognizable cases"


def test_unmatched_fir_classification_uses_retrieval_fallback():
    class StubRetriever:
        def search(self, *_args, **_kwargs):
            return [
                {
                    "citation": "BNS Section 999",
                    "title": "Retrieved fallback",
                }
            ]

    classifier = LegalSectionClassifier(StubRetriever())

    sections, reasoning = classifier.classify("A sparse narrative without known offence keywords.")

    assert sections[0].section == "BNS Section 999"
    assert sections[0].title == "Retrieved fallback"
    assert reasoning == "The suggestion is based on the closest retrieved legal provision from the corpus."
