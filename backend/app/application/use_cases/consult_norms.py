"""Recuperação contextual por requisição, sem herdar medicamento de outro turno."""

from app.application.ports import RetrievalHitDTO, RetrieverPort
from app.domain.prescription import PrescriptionAuditRequest
from app.retrieval.tabular_matcher import TabularDCBMatcher
from app.retrieval.text_normalizer import normalizar_texto_pt

_ROUTE_QUERY_HINTS: dict[str, str] = {
    "FARMACIA_POPULAR": "Farmacia Popular drogaria credenciada PFPB",
    "ALTO_CUSTO_CEAF": "Alto Custo CEAF LME polo",
    "UBS_ATENCAO_PRIMARIA": "UBS Unidade Basica de Saude REME-DF",
}

_DOMAIN_FALLBACK_PREFIXES = (
    "medicament",
    "remedi",
    "farmac",
    "exame",
    "consult",
    "receit",
    "prescric",
    "lme",
    "pcdt",
    "document",
    "retir",
    "peg",
    "busc",
    "onde",
    "ubs",
    "polo",
    "ceaf",
    "sisreg",
    "prazo",
    "validad",
    "venc",
    "procurac",
    "terceir",
    "estoq",
    "disponib",
    "sus",
    "gratuit",
    "fralda",
    "absorvent",
    "esse",
    "este",
    "desse",
    "deste",
    "dessa",
    "desta",
    "item",
    "itens",
)


def question_supports_item_fallback(normalized_question: str) -> bool:
    tokens = normalized_question.split()
    return any(tok.startswith(_DOMAIN_FALLBACK_PREFIXES) for tok in tokens)


def _question_supports_item_fallback(normalized_question: str) -> bool:
    return question_supports_item_fallback(normalized_question)


def _route_hints_from_items(
    request: PrescriptionAuditRequest, retriever: RetrieverPort
) -> list[str]:
    tabular = getattr(retriever, "tabular", None)
    if not isinstance(tabular, TabularDCBMatcher):
        return []
    hints: list[str] = []
    for item in request.itens:
        nome = item.nome_digitado
        dcb = item.principio_ativo_dcb or ""
        forma = item.forma_farmaceutica or ""
        documentados = tabular.rotulo_documental(nome)
        if documentados:
            matches = tabular.filtrar_rotulo(
                documentados, dcb=dcb, dose=item.concentracao or "", forma=forma
            )
        else:
            try:
                doses = tabular.doses_no_texto(nome)
            except ValueError:
                continue
            dose = item.concentracao or (next(iter(doses)) if len(doses) == 1 else "")
            consulta = dcb or nome
            if (
                tabular.tem_numero_nao_interpretado(nome)
                or len(doses) > 1
                or not tabular.doses_compativeis(consulta, doses, item.concentracao or "")
            ):
                continue
            matches = tabular.casar(consulta, concentracao=dose, forma=forma, deduplicar=False)
        if dcb:
            dcb_norm = normalizar_texto_pt(dcb)
            matches = [
                (score, med)
                for score, med in matches
                if normalizar_texto_pt(med.dcb_name) == dcb_norm
            ]
        if matches:
            route_hint = _ROUTE_QUERY_HINTS.get(matches[0][1].dispensation_route)
            if route_hint and route_hint not in hints:
                hints.append(route_hint)
    return hints


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
    if hits or not request.itens or not question_supports_item_fallback(normalized):
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
    hits = retriever.search(f"{expanded} {hints}", top_k=3)
    if hits:
        return hits[:3]
    route_hints = _route_hints_from_items(request, retriever)
    if not route_hints:
        return []
    return retriever.search(f"{expanded} {hints} {' '.join(route_hints)}", top_k=3)[:3]
