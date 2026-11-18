"""Recuperação contextual por requisição, sem herdar medicamento de outro turno."""

from app.application.ports import RetrievalHitDTO, RetrieverPort
from app.domain.prescription import PrescriptionAuditRequest
from app.retrieval.text_normalizer import normalizar_texto_pt


def consult_norms(
    request: PrescriptionAuditRequest, retriever: RetrieverPort
) -> list[RetrievalHitDTO]:
    question = request.pergunta_adicional or ""
    if not question:
        return []
    normalized = normalizar_texto_pt(question)
    expanded = question
    if "alto custo" in normalized:
        expanded += " CEAF polos regionalização"
    if "receita" in normalized and any(
        termo in normalized for termo in ("particular", "privad", "convenio")
    ):
        expanded += " clinicas privadas convenios Farmacia Popular terceiros"
    hits = retriever.search(expanded, top_k=3)
    if hits or not request.itens:
        return hits[:3]
    # Só recorre aos itens da requisição se a pergunta isolada não tiver evidência,
    # evitando diluir exames/normas com o fármaco de outro item nem multiplicar buscas.
    hints = " ".join(
        dict.fromkeys(
            label
            for item in request.itens
            if (label := (item.principio_ativo_dcb or item.nome_digitado).strip())
        )
    )
    if not hints:
        return []
    return retriever.search(f"{expanded} {hints}", top_k=3)[:3]
