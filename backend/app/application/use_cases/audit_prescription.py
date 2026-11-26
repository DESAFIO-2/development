"""Caso de Uso: Auditoria de Receita Médica e Geração do Roteiro Cidadão (RF01 - RF08)."""

from __future__ import annotations

from datetime import date, timedelta

from app.application.evidence import literal_hit
from app.application.ports import (
    AuditPrescriptionUseCasePort,
    AuditResult,
    EvidenceRepositoryPort,
    GuardrailPort,
    MedicationRepositoryPort,
    RetrievalHitDTO,
    RetrieverPort,
)
from app.application.use_cases.triage import inspect_request
from app.core.telemetry import trace_operation
from app.domain.guidance import CitizenGuidanceCard, ItemRoteiroCidadao
from app.domain.medication import CoverageRoute, route_from_dispensation
from app.domain.prescription import PrescriptionAuditRequest
from app.retrieval.tabular_matcher import TabularDCBMatcher
from app.retrieval.text_normalizer import normalizar_texto_pt
from app.seguranca.contexto import PublicContextRegistry, extract_public_processes
from app.seguranca.saida import validar_saida


def _default_guardrail() -> GuardrailPort:
    from app.guardrails.adapter import LocalGuardrailAdapter

    return LocalGuardrailAdapter()


def _sanitize_blocked_card(card: CitizenGuidanceCard) -> CitizenGuidanceCard:
    updates: dict[str, str] = {}
    if not validar_saida(card.resumo_acolhedor).aprovada:
        updates["resumo_acolhedor"] = (
            "Não é possível orientar sobre essa solicitação. Procure atendimento de saúde."
        )
    if not validar_saida(card.regiao_administrativa).aprovada:
        updates["regiao_administrativa"] = "Distrito Federal"
    return card.model_copy(update=updates) if updates else card


class AuditPrescriptionUseCase(AuditPrescriptionUseCasePort):
    """Executa a auditoria: Guardrails -> Recuperação Híbrida -> Auditoria -> Síntese."""

    def __init__(
        self,
        medication_repo: MedicationRepositoryPort,
        retriever: RetrieverPort,
        guardrail: GuardrailPort | None = None,
        tabular_matcher: TabularDCBMatcher | None = None,
        evidence_repo: EvidenceRepositoryPort | None = None,
        public_context: PublicContextRegistry | None = None,
    ) -> None:
        self.evidence_repo = evidence_repo
        self.medication_repo = medication_repo
        self.retriever = retriever
        self.guardrail = guardrail or _default_guardrail()
        self.tabular_matcher = tabular_matcher or TabularDCBMatcher(medication_repo.listar_todos())
        self.public_context = public_context or PublicContextRegistry(
            public_processes=extract_public_processes(
                channel for med in self.tabular_matcher.medications for channel in med.df_channels
            )
        )

    def executar(self, request: PrescriptionAuditRequest) -> CitizenGuidanceCard:
        return self.executar_com_evidencias(request).card

    def executar_com_evidencias(
        self, request: PrescriptionAuditRequest, *, already_triaged: bool = False
    ) -> AuditResult:
        evidences: list[RetrievalHitDTO] = []
        card = self._executar(request, evidences, already_triaged=already_triaged)
        return AuditResult(card, tuple(evidences))

    def _executar(
        self,
        request: PrescriptionAuditRequest,
        evidences: list[RetrievalHitDTO],
        *,
        already_triaged: bool = False,
    ) -> CitizenGuidanceCard:
        if not already_triaged:
            blocked = inspect_request(request, self.guardrail)
            if blocked:
                return _sanitize_blocked_card(blocked)
        regiao = (
            request.regiao_administrativa
            if already_triaged
            else self.guardrail.desidentificar_dados_pessoais(
                request.regiao_administrativa
            ).texto_sanitizado
        )

        hoje = date.today()
        data_base = request.data_emissao or hoje
        itens_roteiro: list[ItemRoteiroCidadao] = []

        # 3. Auditoria Farmacêutica para cada item da receita
        for item in request.itens:
            if already_triaged:
                nome = item.nome_digitado
                dcb = item.principio_ativo_dcb or ""
                forma = item.forma_farmaceutica or ""
            else:
                nome = self.guardrail.desidentificar_dados_pessoais(
                    item.nome_digitado
                ).texto_sanitizado
                dcb = self.guardrail.desidentificar_dados_pessoais(
                    item.principio_ativo_dcb or ""
                ).texto_sanitizado
                forma = self.guardrail.desidentificar_dados_pessoais(
                    item.forma_farmaceutica or ""
                ).texto_sanitizado
            with trace_operation("retrieval"):
                documentados = self.tabular_matcher.rotulo_documental(nome)
                if documentados:
                    dose = item.concentracao or ""
                    matches = self.tabular_matcher.filtrar_rotulo(
                        documentados, dcb=dcb, dose=dose, forma=forma
                    )
                    dose_ambigua = not matches
                else:
                    associacao_invalida = False
                    try:
                        doses = self.tabular_matcher.doses_no_texto(nome)
                    except ValueError:
                        doses = set()
                        associacao_invalida = True
                    dose = item.concentracao or (next(iter(doses)) if len(doses) == 1 else "")
                    consulta = dcb or nome
                    # Nunca retirar o filtro quando o texto contém concentrações ambíguas.
                    dose_ambigua = (
                        associacao_invalida
                        or self.tabular_matcher.tem_numero_nao_interpretado(nome)
                        or len(doses) > 1
                        or not self.tabular_matcher.doses_compativeis(
                            consulta, doses, item.concentracao or ""
                        )
                    )
                    matches = (
                        self.tabular_matcher.casar(
                            consulta, concentracao=dose, forma=forma, deduplicar=False
                        )
                        if not dose_ambigua
                        else []
                    )
            if dcb:
                dcb_norm = normalizar_texto_pt(dcb)
                matches = [
                    (score, med)
                    for score, med in matches
                    if normalizar_texto_pt(med.dcb_name) == dcb_norm
                ]

            if matches:
                _, med_canonico = matches[0]
                item_hits: list[RetrievalHitDTO] = []
                if self.evidence_repo:
                    for evidence in self.evidence_repo.buscar_por_occurrence_ids(
                        med_canonico.occurrence_ids
                    ):
                        item_hits.append(
                            literal_hit(
                                evidence, med_canonico.dispensation_route, med_canonico.dcb_name
                            )
                        )
                evidences.extend(item_hits)
                via = route_from_dispensation(med_canonico.dispensation_route)
                if via == CoverageRoute.FARMACIA_POPULAR:
                    local = f"Drogarias privadas credenciadas ao Farmácia Popular em {regiao}."
                elif via == CoverageRoute.FARMACIA_ALTO_CUSTO:
                    local = (
                        "Farmácia de Alto Custo (CEAF-DF): Polos Asa Sul (Estação 102 Sul), "
                        "Ceilândia (ao lado do HRC) ou Gama."
                    )
                elif via == CoverageRoute.UBS_REME_DF:
                    local = (
                        f"Canal registrado na REME-DF: {'; '.join(med_canonico.df_channels)}. "
                        "Confirme as condições de atendimento com o serviço."
                        if med_canonico.df_channels
                        else "Confirme na UBS de referência qual unidade atende esta apresentação."
                    )
                elif via == CoverageRoute.HOSPITALAR:
                    local = "Consulte o serviço hospitalar responsável pelo atendimento."
                else:
                    local = "Consulte a gerência de assistência farmacêutica da UBS."

                insumo = med_canonico.item_type == "supply"
                validade_dias = None if insumo else med_canonico.prescription_validity_days
                data_limite = (
                    data_base + timedelta(days=validade_dias) if validade_dias is not None else None
                )
                dias_restantes = max(0, (data_limite - hoje).days) if data_limite else None
                alerta_vencimento = dias_restantes is not None and dias_restantes <= 15

                docs = list(med_canonico.required_documents or [])
                if insumo:
                    docs = ["Confira a documentação e os critérios do programa para este insumo."]
                elif not docs:
                    if via == CoverageRoute.FARMACIA_POPULAR:
                        docs = [
                            "Receita médica válida com CRM legível",
                            "Documento oficial com foto",
                            "CPF do paciente",
                        ]
                    elif via == CoverageRoute.FARMACIA_ALTO_CUSTO:
                        docs = [
                            "Laudo de Medicamento Especializado (LME) preenchido pelo médico",
                            "Receita médica em 2 vias",
                            "Cartão Nacional de Saúde (CNS)",
                            "Documento com foto e CPF",
                            "Comprovante de residência no DF",
                        ]
                    else:
                        docs = [
                            "Receita médica original",
                            "Cartão Nacional de Saúde (CNS)",
                            "Documento oficial com foto e CPF",
                        ]

                citacao = f"{med_canonico.source_id} (p. {med_canonico.source_page})"

                if item_hits:
                    citacao = " ".join(
                        f"[Fonte: {hit.chunk_id} | {hit.document_title}, p. {hit.page_number}]"
                        for hit in item_hits
                    )

                itens_roteiro.append(
                    ItemRoteiroCidadao(
                        medicamento_ou_exame=nome,
                        principio_ativo_dcb=med_canonico.dcb_name.upper(),
                        via_retirada=via,
                        local_sugerido=local,
                        o_que_levar=docs,
                        dias_validade_receita=validade_dias,
                        data_limite_validade=data_limite,
                        dias_restantes=dias_restantes,
                        alerta_vencimento_proximo=alerta_vencimento,
                        citacao_normativa=citacao,
                    )
                )
            else:
                # Consulta busca híbrida para itens não tabulados diretamente
                with trace_operation("retrieval"):
                    hits = (
                        self.retriever.search(nome, top_k=1)
                        if not (dcb or forma or dose_ambigua)
                        else []
                    )
                if dose:
                    # Evidência textual genérica não confirma uma concentração fora do catálogo.
                    hits = [hit for hit in hits if hit.route_category == "SISREG_EXAME_CONSULTA"]
                if hits and hits[0].route_category == "SISREG_EXAME_CONSULTA":
                    hit = hits[0]
                    evidences.append(hit)
                    via = CoverageRoute.SISREG_EXAME_CONSULTA
                    local = (
                        f"Regulação Ambulatorial / SISREG III na UBS ou "
                        f"Policlínica Regional de {regiao}."
                    )
                    docs = [
                        "Pedido médico com CID-10 e justificativa clínica",
                        "Documento oficial com foto",
                        "CPF e Cartão Nacional de Saúde (CNS)",
                        "Exames complementares prévios exigidos pelo protocolo",
                    ]
                    val_dias = 90

                    dt_limite = data_base + timedelta(days=val_dias)
                    d_restantes = max(0, (dt_limite - hoje).days)
                    itens_roteiro.append(
                        ItemRoteiroCidadao(
                            medicamento_ou_exame=nome,
                            principio_ativo_dcb=hit.matched_dcb.upper()
                            if hit.matched_dcb
                            else "NAO_IDENTIFICADO",
                            via_retirada=via,
                            local_sugerido=local,
                            o_que_levar=docs,
                            dias_validade_receita=val_dias,
                            data_limite_validade=dt_limite,
                            dias_restantes=d_restantes,
                            alerta_vencimento_proximo=d_restantes <= 15,
                            citacao_normativa=(
                                f"[Fonte: {hit.chunk_id} | {hit.document_title}, "
                                f"p. {hit.page_number}]"
                                if self.evidence_repo
                                else f"{hit.document_title} (Pág. {hit.page_number})"
                            ),
                        )
                    )
                else:
                    itens_roteiro.append(
                        ItemRoteiroCidadao(
                            medicamento_ou_exame=nome,
                            principio_ativo_dcb="NAO_IDENTIFICADO",
                            via_retirada=CoverageRoute.NAO_PADRONIZADO,
                            local_sugerido=(
                                "Apresentação ou cobertura não confirmada no catálogo consultado."
                            ),
                            o_que_levar=[],
                            dias_validade_receita=None,
                            data_limite_validade=None,
                            dias_restantes=None,
                            alerta_vencimento_proximo=False,
                            citacao_normativa=(
                                "Sem cobertura de gratuidade localizada nas relações públicas."
                            ),
                        )
                    )

        # 4. Redação de Resumo Acolhedor
        total_pfpb = sum(
            1 for it in itens_roteiro if it.via_retirada == CoverageRoute.FARMACIA_POPULAR
        )
        total_ubs = sum(1 for it in itens_roteiro if it.via_retirada == CoverageRoute.UBS_REME_DF)
        total_ceaf = sum(
            1 for it in itens_roteiro if it.via_retirada == CoverageRoute.FARMACIA_ALTO_CUSTO
        )

        partes: list[str] = [
            f"Auditamos {len(itens_roteiro)} item(ns) da sua receita para a região de {regiao}."
            if itens_roteiro
            else f"Consultamos as orientações administrativas para {regiao}."
        ]
        if total_pfpb > 0:
            partes.append(
                f"{total_pfpb} item(ns) constam no elenco do Farmácia Popular. "
                "Confira os critérios de acesso de cada item."
            )
        if total_ubs > 0:
            partes.append(f"Para {total_ubs} item(ns), confira o canal de atendimento no roteiro.")
        if total_ceaf > 0:
            partes.append(
                f"{total_ceaf} medicamento(s) fazem parte do Componente de Alto Custo (CEAF) "
                "e exigem abertura de processo com o laudo LME."
            )

        total_hosp = sum(it.via_retirada == CoverageRoute.HOSPITALAR for it in itens_roteiro)
        if total_hosp:
            partes.append(
                f"{total_hosp} medicamento(s) são de uso hospitalar; "
                "consulte o serviço hospitalar responsável pelo atendimento."
            )
        total_sisreg = sum(
            it.via_retirada == CoverageRoute.SISREG_EXAME_CONSULTA for it in itens_roteiro
        )
        if total_sisreg:
            partes.append(
                f"{total_sisreg} exame(s)/consulta(s) seguem a regulação SISREG pela UBS."
            )
        total_outros = sum(it.via_retirada == CoverageRoute.NAO_PADRONIZADO for it in itens_roteiro)
        if total_outros:
            partes.append(f"Não confirmamos a cobertura de {total_outros} item(ns) no catálogo.")
        resumo = " ".join(partes)

        card = CitizenGuidanceCard(
            sucesso=True,
            regiao_administrativa=regiao,
            itens_auditados=itens_roteiro,
            resumo_acolhedor=resumo,
            solicitou_automedicacao=False,
        )
        if not already_triaged:
            evidence_ids = [hit.chunk_id for hit in evidences]
            texts = [card.resumo_acolhedor, card.regiao_administrativa]
            for it in card.itens_auditados:
                texts.extend(
                    [
                        it.medicamento_ou_exame,
                        it.principio_ativo_dcb,
                        self.public_context.scrub_approved_processes(it.local_sugerido),
                        it.citacao_normativa,
                        *it.o_que_levar,
                    ]
                )
            if not all(validar_saida(text, evidence_ids).aprovada for text in texts):
                evidences.clear()
                return CitizenGuidanceCard(
                    sucesso=False,
                    regiao_administrativa="Distrito Federal",
                    itens_auditados=[],
                    resumo_acolhedor=(
                        "Não foi possível apresentar uma orientação segura. Consulte sua UBS."
                    ),
                )
        return card
