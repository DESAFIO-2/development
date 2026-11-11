"""Fixture de encanamento do runner. Não simula capacidade nem erros de modelos reais."""

from app.application.ports import GenerationResultDTO, GeneratorPort, RetrievalHitDTO


class SyntheticSmokeGenerator(GeneratorPort):
    def generate(
        self,
        question: str,
        evidences: tuple[RetrievalHitDTO, ...] = (),
        *,
        rag_mode: bool | None = None,
    ) -> GenerationResultDTO:
        text = "Fixture sintética sem resposta factual."
        if evidences:
            hit = evidences[0]
            text = f"[Fonte: {hit.chunk_id} | {hit.document_title}, p. {hit.page_number}]"
        return GenerationResultDTO(
            text, "synthetic_fixture", "smoke-v1", bool(evidences), execution_kind="synthetic"
        )
