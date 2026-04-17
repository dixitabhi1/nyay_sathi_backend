from functools import lru_cache

from app.core.config import Settings, get_settings
from app.db.analytics import init_analytics_db
from app.db.session import init_db
from app.services.audit import AuditService
from app.services.admin import AdminService
from app.services.auth import AuthService
from app.services.crime_pattern import CrimePatternService
from app.services.evidence_intelligence import EvidenceIntelligenceService
from app.services.fir_extraction import FIRExtractionService
from app.services.fir_completeness import FIRCompletenessService
from app.services.fir_generation import FIRGenerationService
from app.services.fir_service import FIRService
from app.services.history import UserHistoryService
from app.services.corpus_registry import CorpusRegistry
from app.services.document_ingestion import DocumentIngestionService
from app.services.document_marketplace import DocumentMarketplaceService
from app.services.embeddings import EmbeddingService
from app.services.inference import InferenceGateway
from app.services.jurisdiction import JurisdictionService
from app.services.legal_section_classifier import LegalSectionClassifier
from app.services.lawyers import LawyerNetworkService
from app.services.legal_engine import LegalEngine
from app.services.messaging import MessagingService
from app.services.page_index import PageIndexStore
from app.services.retriever import Retriever
from app.services.vector_store import FaissVectorStore


@lru_cache
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService(get_settings())


@lru_cache
def get_vector_store() -> FaissVectorStore:
    return FaissVectorStore(get_settings())


@lru_cache
def get_page_index_store() -> PageIndexStore:
    return PageIndexStore(get_settings())


@lru_cache
def get_retriever() -> Retriever:
    return Retriever(get_settings(), get_embedding_service(), get_vector_store(), get_page_index_store())


@lru_cache
def get_inference_gateway() -> InferenceGateway:
    return InferenceGateway(get_settings())


@lru_cache
def get_document_ingestion_service() -> DocumentIngestionService:
    return DocumentIngestionService(get_settings())


@lru_cache
def get_document_marketplace_service() -> DocumentMarketplaceService:
    init_db()
    return DocumentMarketplaceService(get_settings(), get_document_ingestion_service())


@lru_cache
def get_fir_extraction_service() -> FIRExtractionService:
    return FIRExtractionService()


@lru_cache
def get_fir_completeness_service() -> FIRCompletenessService:
    return FIRCompletenessService()


@lru_cache
def get_fir_generation_service() -> FIRGenerationService:
    return FIRGenerationService(get_settings())


@lru_cache
def get_legal_section_classifier() -> LegalSectionClassifier:
    return LegalSectionClassifier(get_retriever(), get_settings().bns_classifier_model_name or None)


@lru_cache
def get_jurisdiction_service() -> JurisdictionService:
    return JurisdictionService(get_settings().jurisdiction_gazetteer_path)


@lru_cache
def get_evidence_intelligence_service() -> EvidenceIntelligenceService:
    return EvidenceIntelligenceService(get_document_ingestion_service())


@lru_cache
def get_crime_pattern_service() -> CrimePatternService:
    init_db()
    return CrimePatternService()


@lru_cache
def get_legal_engine() -> LegalEngine:
    init_db()
    init_analytics_db()
    return LegalEngine(
        settings=get_settings(),
        retriever=get_retriever(),
        inference=get_inference_gateway(),
        document_ingestion=get_document_ingestion_service(),
    )


@lru_cache
def get_audit_service() -> AuditService:
    init_db()
    return AuditService()


@lru_cache
def get_auth_service() -> AuthService:
    init_db()
    return AuthService(get_settings())


@lru_cache
def get_admin_service() -> AdminService:
    init_db()
    return AdminService(get_auth_service())


@lru_cache
def get_history_service() -> UserHistoryService:
    init_db()
    return UserHistoryService()


@lru_cache
def get_fir_service() -> FIRService:
    init_db()
    return FIRService(
        settings=get_settings(),
        document_ingestion=get_document_ingestion_service(),
        extraction_service=get_fir_extraction_service(),
        classifier=get_legal_section_classifier(),
        generation_service=get_fir_generation_service(),
        completeness_service=get_fir_completeness_service(),
        jurisdiction_service=get_jurisdiction_service(),
        evidence_intelligence=get_evidence_intelligence_service(),
        crime_pattern_service=get_crime_pattern_service(),
    )


@lru_cache
def get_lawyer_network_service() -> LawyerNetworkService:
    init_db()
    return LawyerNetworkService(get_fir_service())


@lru_cache
def get_messaging_service() -> MessagingService:
    init_db()
    return MessagingService()


@lru_cache
def get_corpus_registry() -> CorpusRegistry:
    init_analytics_db()
    return CorpusRegistry()


def get_runtime_settings() -> Settings:
    return get_settings()
