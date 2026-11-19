"""Síntese opcional e controles de saída; nenhuma decisão de cobertura vem da LLM."""

from __future__ import annotations

import re
import time

from app.application.agents import (
    AgentRequest,
    AgentResponse,
    GenerationFailure,
    GenerationMetadata,
)
from app.application.ports import GeneratorPort, RetrievalHitDTO
from app.domain.guidance import CitizenGuidanceCard
from app.domain.medication import CoverageRoute
from app.seguranca.citacoes import expandir_citacoes, remover_citacoes
from app.seguranca.contexto import PublicContextRegistry
from app.seguranca.saida import validar_saida

_CITATION = re.compile(r"\[\s*fonte\s*:[^\]]*\]", re.IGNORECASE)
NO_EVIDENCE = (
    "Não localizamos evidência suficiente para responder à dúvida. "
    "Confirme com a UBS de referência."
)


def citation(hit: RetrievalHitDTO) -> str:
    return f"[Fonte: {hit.chunk_id} | {hit.document_title}, p. {hit.page_number}]"


def synthesize(
    *,
    request: AgentRequest,
    card: CitizenGuidanceCard,
    audit_hits: list[RetrievalHitDTO],
    normative_hits: list[RetrievalHitDTO],
    generator: GeneratorPort | None,
    strict: bool,
    public_context: PublicContextRegistry | None = None,
) -> AgentResponse:
    hits = list({h.chunk_id: h for h in [*audit_hits, *normative_hits]}.values())
    # Também inspecionar o canal recuperado antes de enviar texto ao provedor
    # ou devolvê-lo como trecho literal. Reutilizar os controles oficiais.
    registry = public_context or PublicContextRegistry()
    unsafe_context = any(not registry.approved(hit) for hit in hits)
    if unsafe_context:
        rejected = GenerationMetadata(status="CONTEXTO_REJEITADO", error_code="VALIDACAO_CONTEXTO")
        if strict:
            raise GenerationFailure(rejected)
        return AgentResponse(
            card=CitizenGuidanceCard(
                sucesso=False,
                regiao_administrativa="Distrito Federal",
                itens_auditados=[],
                resumo_acolhedor=(
                    "Não foi possível validar as fontes recuperadas. Consulte sua UBS."
                ),
            ),
            primary_route="BLOQUEADO",
            generation=rejected,
        )
    # Evidência literal comprova presença documental, não benefício/estoque atual.
    citations = [citation(hit) for hit in hits]
    ids = [hit.chunk_id for hit in hits]
    additional = None
    if request.pergunta_adicional:
        additional = (
            (
                "Trechos normativos recuperados para consulta:\n"
                + "\n".join(f"{hit.text} {citation(hit)}" for hit in normative_hits)
            )
            if normative_hits
            else NO_EVIDENCE
        )
    metadata = GenerationMetadata()
    if not hits:
        metadata.status = "ABSTENCAO"
    # Se há pergunta_adicional, foca o prompt apenas nos trechos normativos
    # para não diluir o contexto da LLM com linhas literais de outros itens.
    candidates = list(normative_hits) if request.pergunta_adicional else list(audit_hits)
    context: list[RetrievalHitDTO] = []
    budget = 6000
    for hit in {hit.chunk_id: hit for hit in candidates}.values():
        size = len(hit.text) + len(citation(hit)) + 200
        if size <= budget:
            context.append(hit)
            budget -= size
    context_truncated = len(context) < len({hit.chunk_id for hit in candidates})
    can_generate = bool(context) and (not request.pergunta_adicional or bool(normative_hits))
    prompt_version: str | None = getattr(generator, "prompt_version", None) if generator else None
    if generator and can_generate:
        start = time.perf_counter()
        try:
            result = generator.generate(
                request.pergunta_adicional
                or "Explique apenas a presença documental dos itens consultados.",
                tuple(context),
                rag_mode=True,
            )
            metadata = GenerationMetadata(
                status="GERADO",
                provider=result.provider,
                model=result.model_name,
                latency_ms=result.latency_ms,
                error_code=result.error_code,
                prompt_version=prompt_version,
                context_chunk_ids=[hit.chunk_id for hit in context],
                context_truncated=context_truncated,
            )
            text, _ = expandir_citacoes(result.text, context)
            allowed = {citation(hit) for hit in context}
            valid = (
                bool(remover_citacoes(text).strip())
                and result.execution_kind == "llm"
                and validar_saida(text, [hit.chunk_id for hit in context]).aprovada
                and all(match.group() in allowed for match in _CITATION.finditer(text))
            )
            if result.error_code:
                metadata.status = "FALHA_PROVEDOR"
            elif not valid:
                metadata.status = "SAIDA_REJEITADA"
                metadata.error_code = "VALIDACAO_SAIDA"
            else:
                additional = remover_citacoes(text)
        except (OSError, TimeoutError, ValueError, RuntimeError):
            metadata = GenerationMetadata(
                status="FALHA_PROVEDOR",
                error_code="ERRO_GERADOR",
                latency_ms=round((time.perf_counter() - start) * 1000, 2),
                prompt_version=prompt_version,
                context_chunk_ids=[hit.chunk_id for hit in context],
                context_truncated=context_truncated,
            )
        if metadata.status in {"FALHA_PROVEDOR", "SAIDA_REJEITADA"}:
            if strict:
                raise GenerationFailure(metadata)
            metadata.fallback_used = True
    elif strict and generator is None:
        raise GenerationFailure(
            GenerationMetadata(status="FALHA_PROVEDOR", error_code="GERADOR_NAO_CONFIGURADO")
        )
    elif generator and not can_generate:
        metadata.status = "ABSTENCAO"
        metadata.prompt_version = prompt_version
        metadata.context_truncated = context_truncated

    routes = {item.via_retirada.value for item in card.itens_auditados}
    routes.discard(CoverageRoute.NAO_PADRONIZADO.value)
    if any(hit.route_category == "SISREG_EXAME_CONSULTA" for hit in normative_hits):
        routes.add(CoverageRoute.SISREG_EXAME_CONSULTA.value)
    primary = (
        "ROTEIRO_MISTO_MULTICANAL" if len(routes) > 1 else next(iter(routes), "NAO_PADRONIZADO")
    )
    if not request.itens and normative_hits and not routes:
        primary = "ORIENTACAO_NORMATIVA"
    # Validar também o caminho determinístico e todos os campos exibidos do cartão.
    validation_additional = additional or ""
    if metadata.status != "GERADO":
        for hit in normative_hits:
            validation_additional = validation_additional.replace(
                hit.text, registry.validation_text(hit)
            )
    texts = [card.resumo_acolhedor, card.regiao_administrativa, validation_additional, *citations]
    for item in card.itens_auditados:
        texts.extend(
            [
                item.medicamento_ou_exame,
                item.principio_ativo_dcb,
                registry.scrub_approved_processes(item.local_sugerido),
                item.citacao_normativa,
                *item.o_que_levar,
            ]
        )
    if not all(validar_saida(text, ids).aprovada for text in texts):
        metadata.status = "SAIDA_REJEITADA"
        metadata.error_code = "VALIDACAO_RESPOSTA_FINAL"
        if strict:
            raise GenerationFailure(metadata)
        metadata.fallback_used = True
        card = CitizenGuidanceCard(
            sucesso=False,
            regiao_administrativa="Distrito Federal",
            itens_auditados=[],
            resumo_acolhedor="Não foi possível apresentar uma orientação segura. Consulte sua UBS.",
        )
        additional, citations, hits, primary = None, [], [], "BLOQUEADO"
    return AgentResponse(
        card=card,
        resposta_adicional=additional,
        primary_route=primary,
        evidencias=hits,
        citacoes=citations,
        generation=metadata,
    )
