from pydantic import BaseModel, Field


AI_FIR_DISCLAIMER = (
    "This document is an AI-generated draft intended to assist police officers and citizens. "
    "It is not an official FIR until verified and registered by the appropriate authority."
)


class FIRStructuredData(BaseModel):
    complainant_name: str | None = None
    parent_name: str | None = None
    address: str | None = None
    contact_number: str | None = None
    police_station: str | None = None
    incident_date: str | None = None
    incident_time: str | None = None
    incident_location: str | None = None
    incident_description: str
    accused_details: list[str] = Field(default_factory=list)
    witness_details: list[str] = Field(default_factory=list)
    evidence_information: list[str] = Field(default_factory=list)


class FIRJurisdictionSuggestion(BaseModel):
    suggested_police_station: str
    district: str | None = None
    state: str | None = None
    source: str
    confidence: float
    latitude: float | None = None
    longitude: float | None = None


class FIRSectionSuggestion(BaseModel):
    section: str
    title: str
    reasoning: str
    confidence: float


class FIREvidenceItem(BaseModel):
    evidence_id: int
    file_name: str
    file_path: str
    media_type: str
    uploaded_at: str


class FIRVersionItem(BaseModel):
    version_number: int
    draft_text: str
    edited_by: str | None = None
    edit_summary: str | None = None
    created_at: str


class FIRCompletenessResponse(BaseModel):
    completeness_score: int
    missing_fields: list[str]
    suggestions: list[str]


class FIRCrimePatternSummary(BaseModel):
    crime_category: str
    incident_count: int
    location: str
    window_days: int
    insight: str
    suggested_attention_area: str


class FIRHeatmapPoint(BaseModel):
    location: str
    latitude: float | None = None
    longitude: float | None = None
    intensity: int
    crime_category: str


class FIREvidenceInsight(BaseModel):
    file_name: str
    media_type: str
    file_category: str
    extracted_text: str | None = None
    transcript_text: str | None = None
    detected_entities: list[str] = Field(default_factory=list)
    detected_objects: list[str] = Field(default_factory=list)
    event_markers: list[str] = Field(default_factory=list)
    threat_indicators: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class FIRIntelligenceResponse(BaseModel):
    fir_id: str
    jurisdiction: FIRJurisdictionSuggestion | None = None
    completeness: FIRCompletenessResponse
    bns_prediction: list[FIRSectionSuggestion]
    crime_pattern: FIRCrimePatternSummary | None = None


class FIRRecordResponse(BaseModel):
    fir_id: str
    workflow: str
    status: str
    extracted_data: FIRStructuredData
    transcript_text: str | None = None
    sections: list[FIRSectionSuggestion]
    legal_reasoning: str
    draft_text: str
    disclaimer: str = AI_FIR_DISCLAIMER
    jurisdiction: FIRJurisdictionSuggestion | None = None
    completeness: FIRCompletenessResponse | None = None
    case_strength_score: int
    case_strength_reasoning: list[str]
    evidence_items: list[FIREvidenceItem]
    current_version: int
    last_edited_at: str


class FIRRecordSummary(BaseModel):
    fir_id: str
    workflow: str
    status: str
    complainant_name: str | None = None
    police_station: str | None = None
    incident_date: str | None = None
    incident_location: str | None = None
    case_strength_score: int
    current_version: int
    last_edited_at: str
    draft_excerpt: str


class FIRRecordListResponse(BaseModel):
    records: list[FIRRecordSummary]


class FIRManualRequest(BaseModel):
    complainant_name: str
    parent_name: str | None = None
    address: str
    contact_number: str | None = None
    police_station: str
    incident_date: str
    incident_time: str | None = None
    incident_location: str
    incident_description: str
    accused_details: list[str] = Field(default_factory=list)
    witness_details: list[str] = Field(default_factory=list)
    evidence_information: list[str] = Field(default_factory=list)
    user_id: str | None = None


class FIRUploadIntakeResponse(BaseModel):
    extracted_data: FIRStructuredData
    transcript_text: str | None = None
    cleaned_text: str
    sections: list[FIRSectionSuggestion]
    legal_reasoning: str
    jurisdiction: FIRJurisdictionSuggestion | None = None
    completeness: FIRCompletenessResponse | None = None
    case_strength_score: int
    case_strength_reasoning: list[str]
    draft_text: str
    disclaimer: str = AI_FIR_DISCLAIMER


class FIRVoiceTranscriptRequest(BaseModel):
    transcript_text: str
    police_station: str | None = None
    complainant_name: str | None = None
    user_id: str | None = None


class FIRDraftUpdateRequest(BaseModel):
    draft_text: str
    edited_by: str | None = None
    edit_summary: str | None = None


class FIRVersionsResponse(BaseModel):
    fir_id: str
    versions: list[FIRVersionItem]


class FIRVoiceProcessingResponse(BaseModel):
    transcript_text: str
    cleaned_text: str
    extracted_data: FIRStructuredData
    sections: list[FIRSectionSuggestion]
    jurisdiction: FIRJurisdictionSuggestion | None = None
    completeness: FIRCompletenessResponse | None = None


class FIRSectionPredictionRequest(BaseModel):
    incident_description: str


class FIRJurisdictionRequest(BaseModel):
    incident_location: str


class FIREvidenceAnalysisResponse(BaseModel):
    fir_id: str | None = None
    analyses: list[FIREvidenceInsight]


class FIRCrimePatternResponse(BaseModel):
    total_records: int
    hotspot_alerts: list[FIRCrimePatternSummary]
    heatmap_points: list[FIRHeatmapPoint]
