"""Conversão única da evidência literal; identidade estável para auditoria e validação."""

from app.application.ports import EvidenceChunkDTO, RetrievalHitDTO


def literal_hit(
    evidence: EvidenceChunkDTO, route: str = "", dcb: str | None = None
) -> RetrievalHitDTO:
    return RetrievalHitDTO(
        chunk_id=evidence.chunk_id,
        score=1.0,
        source_id=evidence.source_id,
        document_title=evidence.source_version,
        section="Presença documental; não confirma elegibilidade/estoque",
        page_number=evidence.page_number,
        route_category=route,
        text=evidence.literal_text,
        matched_dcb=dcb,
        retriever_name="occurrence_id_exact",
    )
