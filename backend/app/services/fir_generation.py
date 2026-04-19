from __future__ import annotations

import io
import json
from functools import cached_property
from pathlib import Path

import httpx
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from app.core.config import Settings
from app.schemas.fir import FIRComparativeSectionsResponse, FIRGeneratedDocument, FIRSectionSuggestion, FIRStructuredData


class FIRGenerationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate_document_bundle(
        self,
        structured: FIRStructuredData,
        comparative_sections: FIRComparativeSectionsResponse,
        language: str = "en",
        source_application_text: str | None = None,
    ) -> list[FIRGeneratedDocument]:
        language = self._normalize_language(language)
        if self.settings.fir_inference_provider.lower() != "mock":
            generated = self._generate_via_model(structured, comparative_sections, language, source_application_text)
            if generated:
                return generated
        return self._generate_with_templates(structured, comparative_sections, language, source_application_text)

    def render_pdf(self, title: str, content: str, language: str = "en") -> bytes:
        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        font_name = self._font_for_language(language)
        width, height = A4
        top = height - 48
        pdf.setFont(font_name, 16)
        pdf.drawString(48, top, title[:80])
        pdf.setFont(font_name, 10)
        y = top - 28
        for raw_line in content.splitlines():
            line = raw_line or " "
            segments = [line[index : index + 100] for index in range(0, len(line), 100)] or [" "]
            for segment in segments:
                if y < 60:
                    pdf.showPage()
                    pdf.setFont(font_name, 10)
                    y = height - 48
                pdf.drawString(48, y, segment)
                y -= 14
        pdf.save()
        return buffer.getvalue()

    def _generate_via_model(
        self,
        structured: FIRStructuredData,
        comparative_sections: FIRComparativeSectionsResponse,
        language: str,
        source_application_text: str | None,
    ) -> list[FIRGeneratedDocument]:
        system_prompt = (
            "You are NyayaSetu FIR Studio, a legal drafting model specialized in Indian police complaints, FIR drafting, "
            "and lawyer review. Stay grounded in the provided facts and sections, keep the output human-readable, and "
            "never invent facts that are not in the complaint record."
        )
        payload = {
            "facts": structured.model_dump(),
            "comparative_sections": comparative_sections.model_dump(),
            "language": language,
            "source_application_text": source_application_text,
            "required_outputs": [
                "citizen_application",
                "police_fir",
                "lawyer_analysis",
            ],
        }
        prompt = (
            "Generate three grounded documents in JSON with keys citizen_application, police_fir, and lawyer_analysis. "
            "Each key must contain a polished legal draft in the requested language. Complaint data:\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )
        try:
            response = self._generate(system_prompt, prompt)
            parsed = json.loads(response)
            outputs: list[FIRGeneratedDocument] = []
            for kind, title in (
                ("citizen_application", "Citizen Complaint Application"),
                ("police_fir", "Police FIR Draft"),
                ("lawyer_analysis", "Lawyer FIR Analysis"),
            ):
                content = str(parsed.get(kind, "")).strip()
                if not content:
                    return []
                outputs.append(
                    FIRGeneratedDocument(
                        kind=kind,
                        title=title,
                        language=language,
                        content=content,
                        download_ready=(kind == "citizen_application"),
                    )
                )
            return outputs
        except Exception:
            return []

    def _generate(self, system_prompt: str, user_prompt: str) -> str:
        provider = self.settings.fir_inference_provider.lower()
        timeout = httpx.Timeout(
            connect=min(5.0, self.settings.fir_inference_timeout_seconds),
            read=self.settings.fir_inference_timeout_seconds,
            write=self.settings.fir_inference_timeout_seconds,
            pool=min(5.0, self.settings.fir_inference_timeout_seconds),
        )
        if provider in {"vllm", "tgi"}:
            payload = {
                "model": self.settings.fir_inference_model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": self.settings.fir_temperature,
                "max_tokens": self.settings.fir_max_generation_tokens,
            }
            with httpx.Client(timeout=timeout) as client:
                response = client.post(f"{self.settings.fir_inference_base_url.rstrip('/')}/chat/completions", json=payload)
                if not response.is_success:
                    raise RuntimeError(self._format_upstream_error(response, "FIR generation"))
                if "application/json" not in response.headers.get("content-type", "").lower():
                    raise RuntimeError(
                        "FIR generation endpoint returned non-JSON content. "
                        "Check FIR_INFERENCE_PROVIDER and FIR_INFERENCE_BASE_URL; the URL should be an API endpoint."
                    )
                data = response.json()
            return data["choices"][0]["message"]["content"]
        if provider == "ollama":
            payload = {
                "model": self.settings.fir_inference_model_name or self.settings.ollama_model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "options": {"temperature": self.settings.fir_temperature},
            }
            with httpx.Client(timeout=timeout) as client:
                response = client.post(f"{self.settings.ollama_base_url.rstrip('/')}/api/chat", json=payload)
                if not response.is_success:
                    raise RuntimeError(self._format_upstream_error(response, "FIR Ollama generation"))
                if "application/json" not in response.headers.get("content-type", "").lower():
                    raise RuntimeError("Ollama endpoint returned non-JSON content. Check OLLAMA_BASE_URL.")
                data = response.json()
            return data["message"]["content"]
        if provider == "local_pipeline":
            outputs = self.local_pipeline(
                f"System: {system_prompt}\nUser: {user_prompt}\nAssistant:",
                max_new_tokens=self.settings.fir_max_generation_tokens,
                temperature=self.settings.fir_temperature,
                do_sample=True,
            )
            return outputs[0]["generated_text"].split("Assistant:", 1)[-1].strip()
        raise ValueError(f"Unsupported FIR inference provider: {self.settings.fir_inference_provider}")

    def _format_upstream_error(self, response: httpx.Response, context: str) -> str:
        text = response.text[:500]
        if "<!doctype html" in text.lower() or "<html" in text.lower():
            text = "HTML page returned instead of API JSON."
        return f"{context} failed with HTTP {response.status_code}: {text}"

    @cached_property
    def local_pipeline(self):
        if self.settings.fir_inference_provider.lower() != "local_pipeline":
            return None
        from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

        model_name = self.settings.fir_local_model_name or self.settings.local_model_name
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForCausalLM.from_pretrained(model_name, device_map="auto")
        return pipeline("text-generation", model=model, tokenizer=tokenizer)

    def _generate_with_templates(
        self,
        structured: FIRStructuredData,
        comparative_sections: FIRComparativeSectionsResponse,
        language: str,
        source_application_text: str | None,
    ) -> list[FIRGeneratedDocument]:
        headings = self._headings(language)
        comparison_lines = self._comparison_lines(comparative_sections)
        citizen_text = (
            f"{headings['to']}\n{headings['sho']}\n{headings['police_station']}: {structured.police_station or '[Police Station]'}\n\n"
            f"{headings['subject']}: {headings['citizen_subject']}\n\n"
            f"{headings['salutation']}\n\n"
            f"{headings['intro']} {structured.complainant_name or '[Name]'}, {headings['address_label']} "
            f"{structured.address or '[Address]'}. {headings['incident_intro']} {structured.incident_date or '[Date]'}"
            f"{' ' + headings['time_connector'] + ' ' + structured.incident_time if structured.incident_time else ''} "
            f"{headings['location_connector']} {structured.incident_location or '[Location]'}.\n\n"
            f"{structured.incident_description}\n\n"
            f"{headings['accused']}: {', '.join(structured.accused_details) or headings['not_available']}\n"
            f"{headings['witnesses']}: {', '.join(structured.witness_details) or headings['not_available']}\n"
            f"{headings['evidence']}: {', '.join(structured.evidence_information) or headings['not_available']}\n\n"
            f"{headings['sections_heading']}:\n{comparison_lines}\n\n"
            f"{headings['request_line']}\n\n"
            f"{headings['signature']}\n{structured.complainant_name or '[Name]'}"
        )
        police_text = (
            f"{headings['fir_title']}\n\n"
            f"{headings['complainant']}: {structured.complainant_name or '[Name]'}\n"
            f"{headings['police_station']}: {structured.police_station or '[Police Station]'}\n"
            f"{headings['date_time']}: {structured.incident_date or '[Date]'}"
            f"{' / ' + structured.incident_time if structured.incident_time else ''}\n"
            f"{headings['location']}: {structured.incident_location or '[Location]'}\n\n"
            f"{headings['gist']}: {structured.incident_description}\n\n"
            f"{headings['source_application']}: {source_application_text or headings['source_fallback']}\n\n"
            f"{headings['sections_heading']}:\n{comparison_lines}\n\n"
            f"{headings['police_note']}"
        )
        lawyer_text = (
            f"{headings['analysis_title']}\n\n"
            f"{headings['facts_summary']}: {structured.incident_description}\n\n"
            f"{headings['analysis_sections']}:\n{comparison_lines}\n\n"
            f"{headings['lawyer_findings']}\n"
            f"- {headings['check_identity']}\n"
            f"- {headings['check_timeline']}\n"
            f"- {headings['check_evidence']}\n"
            f"- {headings['check_procedure']}\n"
        )
        return [
            FIRGeneratedDocument(
                kind="citizen_application",
                title="Citizen Complaint Application",
                language=language,
                content=citizen_text,
                download_ready=True,
            ),
            FIRGeneratedDocument(
                kind="police_fir",
                title="Police FIR Draft",
                language=language,
                content=police_text,
                download_ready=False,
            ),
            FIRGeneratedDocument(
                kind="lawyer_analysis",
                title="Lawyer FIR Analysis",
                language=language,
                content=lawyer_text,
                download_ready=False,
            ),
        ]

    def _comparison_lines(self, comparative_sections: FIRComparativeSectionsResponse) -> str:
        groups = [
            ("BNS", comparative_sections.bns),
            ("BNSS", comparative_sections.bnss),
            ("IPC", comparative_sections.ipc),
            ("CrPC", comparative_sections.crpc),
        ]
        lines: list[str] = []
        for statute, items in groups:
            if not items:
                continue
            for item in items:
                lines.append(f"- {statute}: {item.section} - {item.title}")
        return "\n".join(lines) or "- Manual legal classification required."

    def _normalize_language(self, language: str) -> str:
        normalized = (language or "en").strip().lower()
        return normalized if normalized in {"en", "hi"} else "en"

    def _headings(self, language: str) -> dict[str, str]:
        if language == "hi":
            return {
                "to": "प्रति",
                "sho": "थाना प्रभारी अधिकारी",
                "police_station": "पुलिस स्टेशन",
                "subject": "विषय",
                "citizen_subject": "संज्ञेय अपराध के संबंध में प्रार्थना पत्र",
                "salutation": "महोदय/महोदया,",
                "intro": "मैं",
                "address_label": "निवासी",
                "incident_intro": "यह निवेदन करता/करती हूँ कि दिनांक",
                "time_connector": "समय",
                "location_connector": "स्थान",
                "accused": "आरोपी विवरण",
                "witnesses": "गवाह",
                "evidence": "साक्ष्य",
                "sections_heading": "लागू धाराएँ",
                "request_line": "कृपया इस आवेदन पर उचित कार्रवाई करते हुए प्राथमिकी दर्ज करने की कृपा करें।",
                "signature": "हस्ताक्षर",
                "fir_title": "पुलिस FIR ड्राफ्ट",
                "complainant": "शिकायतकर्ता",
                "date_time": "दिनांक / समय",
                "location": "घटनास्थल",
                "gist": "घटना का संक्षेप",
                "source_application": "आधार आवेदन",
                "source_fallback": "उपलब्ध शिकायत आवेदन के आधार पर FIR मसौदा तैयार किया गया है।",
                "police_note": "पुलिस अधिकारी को आवेदन, उपलब्ध साक्ष्य, और लागू प्रक्रिया की पुष्टि के बाद FIR का अंतिम पंजीकरण करना चाहिए।",
                "analysis_title": "वकील समीक्षा नोट",
                "facts_summary": "तथ्य सार",
                "analysis_sections": "तुलनात्मक धाराएँ",
                "lawyer_findings": "प्राथमिक समीक्षा बिंदु:",
                "check_identity": "शिकायतकर्ता, आरोपी, और गवाहों की पहचान सामग्री की पुष्टि करें।",
                "check_timeline": "तारीख, समय, और घटनाक्रम को FIR ड्राफ्ट से मिलाएँ।",
                "check_evidence": "अपलोड साक्ष्य, OCR पाठ, और मूल आवेदन के बीच सामंजस्य जाँचें।",
                "check_procedure": "BNSS/CrPC प्रक्रिया और क्षेत्राधिकार की पुष्टि करें।",
                "not_available": "उपलब्ध नहीं",
            }
        return {
            "to": "To",
            "sho": "Station House Officer",
            "police_station": "Police Station",
            "subject": "Subject",
            "citizen_subject": "Application requesting registration of a cognizable complaint",
            "salutation": "Respected Sir/Madam,",
            "intro": "I am",
            "address_label": "residing at",
            "incident_intro": "and I respectfully submit that on",
            "time_connector": "at",
            "location_connector": "near",
            "accused": "Accused details",
            "witnesses": "Witnesses",
            "evidence": "Evidence",
            "sections_heading": "Suggested comparative sections",
            "request_line": "Kindly acknowledge this complaint application and take appropriate legal action under the applicable law.",
            "signature": "Signature",
            "fir_title": "Police FIR Draft",
            "complainant": "Complainant",
            "date_time": "Date / Time",
            "location": "Place of occurrence",
            "gist": "Gist of incident",
            "source_application": "Source application",
            "source_fallback": "This FIR draft was prepared from the citizen complaint record and supporting materials.",
            "police_note": "The police officer should verify the complaint application, OCR output, evidence references, and applicable sections before final FIR registration.",
            "analysis_title": "Lawyer FIR Review Note",
            "facts_summary": "Facts summary",
            "analysis_sections": "Comparative sections",
            "lawyer_findings": "Primary review points:",
            "check_identity": "Verify complainant, accused, and witness particulars against the application and available documents.",
            "check_timeline": "Check the incident timeline, place, and sequence before filing or defending the FIR.",
            "check_evidence": "Assess whether the OCR extract, uploaded evidence, and complaint narrative remain consistent.",
            "check_procedure": "Confirm the BNSS/CrPC procedure, jurisdiction, and registration steps before advice is finalized.",
            "not_available": "Not available",
        }

    def _font_for_language(self, language: str) -> str:
        if language != "hi":
            return "Helvetica"
        for candidate in (Path("C:/Windows/Fonts/mangal.ttf"), Path("C:/Windows/Fonts/Nirmala.ttf")):
            if not candidate.exists():
                continue
            font_name = candidate.stem
            try:
                pdfmetrics.getFont(font_name)
            except KeyError:
                pdfmetrics.registerFont(TTFont(font_name, str(candidate)))
            return font_name
        return "Helvetica"
