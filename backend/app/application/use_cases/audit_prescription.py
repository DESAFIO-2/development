"""Caso de Uso: Auditoria de Receita Médica e Geração do Roteiro Cidadão (RF01 - RF08)."""

from __future__ import annotations

from datetime import date, timedelta

from app.application.ports import (
    AuditPrescriptionUseCasePort,
    MedicationRepositoryPort,
    RetrieverPort,
)
from app.core.telemetry import trace_operation
from app.domain.guidance import CitizenGuidanceCard, ItemRoteiroCidadao
from app.domain.medication import CoverageRoute
from app.domain.prescription import PrescriptionAuditRequest
from app.guardrails.clinical import ClinicalGuardrail
from app.guardrails.pii import PIIMasker
from app.retrieval.tabular_matcher import TabularDCBMatcher
from app.retrieval.text_normalizer import normalizar_texto_pt


class AuditPrescriptionUseCase(AuditPrescriptionUseCasePort):
    """Executa a auditoria: Guardrails -> Recuperação Híbrida -> Auditoria -> Síntese."""

    def __init__(
        self,
        medication_repo: MedicationRepositoryPort,
        retriever: RetrieverPort,
        guardrail: ClinicalGuardrail | None = None,
        pii_masker: PIIMasker | None = None,
    ) -> None:
        self.medication_repo = medication_repo
        self.retriever = retriever
        self.guardrail = guardrail or ClinicalGuardrail()
        self.pii_masker = pii_masker or PIIMasker()
        self.tabular_matcher = TabularDCBMatcher(medication_repo.listar_todos())

    def executar(self, request: PrescriptionAuditRequest) -> CitizenGuidanceCard:
        # 1. Guardrail Clínico e de Ato Médico
        campos = [
            value
            for item in request.itens
            for value in (
                item.nome_digitado,
                item.principio_ativo_dcb,
                item.concentracao,
                item.forma_farmaceutica,
                item.posologia,
                item.quantidade_prescrita,
            )
            if value
        ] + [request.pergunta_adicional or "", request.regiao_administrativa]

        regiao = self.pii_masker.mascarar(request.regiao_administrativa).texto_sanitizado
        with trace_operation("guardrail"):
            bloqueios = [
                check
                for campo in campos
                if campo
                if (check := self.guardrail.inspecionar(campo)).bloqueado
            ]
        if bloqueios:
            check_clinico = next(
                (check for check in bloqueios if check.alerta_emergencia), bloqueios[0]
            )
            return CitizenGuidanceCard(
                sucesso=False,
                regiao_administrativa=regiao,
                itens_auditados=[],
                resumo_acolhedor=check_clinico.mensagem_acolhedora,
                solicitou_automedicacao=check_clinico.motivo != "PROMPT_INJECTION",
            )

        hoje = date.today()
        data_base = request.data_emissao or hoje
        itens_roteiro: list[ItemRoteiroCidadao] = []

        # 3. Auditoria Farmacêutica para cada item da receita
        for item in request.itens:
            nome = self.pii_masker.mascarar(item.nome_digitado).texto_sanitizado
            dcb = self.pii_masker.mascarar(item.principio_ativo_dcb or "").texto_sanitizado
            forma = self.pii_masker.mascarar(item.forma_farmaceutica or "").texto_sanitizado
            doses = self.tabular_matcher.doses_no_texto(nome)
            dose = item.concentracao or (next(iter(doses)) if len(doses) == 1 else "")
            # Nunca retirar o filtro quando o texto contém concentrações ambíguas.
            dose_ambigua = (
                self.tabular_matcher.tem_numero_nao_interpretado(nome)
                or len(doses) > 1
                or bool(
                    item.concentracao
                    and doses
                    and doses != {self.tabular_matcher.normalizar_concentracao(item.concentracao)}
                )
            )
            consulta = dcb or nome
            with trace_operation("retrieval"):
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
                route_str = med_canonico.dispensation_route

                if route_str == "FARMACIA_POPULAR":
                    via = CoverageRoute.FARMACIA_POPULAR
                    local = f"Drogarias privadas credenciadas ao Farmácia Popular em {regiao}."
                elif route_str == "ALTO_CUSTO_CEAF":
                    via = CoverageRoute.FARMACIA_ALTO_CUSTO
                    local = (
                        "Farmácia de Alto Custo (CEAF-DF): Polos Asa Sul (Estação 102 Sul), "
                        "Ceilândia (ao lado do HRC) ou Gama."
                    )
                elif route_str == "UBS_ATENCAO_PRIMARIA":
                    via = CoverageRoute.UBS_REME_DF
                    local = (
                        f"Canal registrado na REME-DF: {'; '.join(med_canonico.df_channels)}. "
                        "Confirme as condições de atendimento com o serviço."
                        if med_canonico.df_channels
                        else "Confirme na UBS de referência qual unidade atende esta apresentação."
                    )
                elif route_str == "HOSPITALAR":
                    via = CoverageRoute.HOSPITALAR
                    local = "Consulte o serviço hospitalar responsável pelo atendimento."
                else:
                    via = CoverageRoute.NAO_PADRONIZADO
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
                if hits and hits[0].route_category in {
                    "SISREG_EXAME_CONSULTA",
                    "ALTO_CUSTO_CEAF",
                    "FARMACIA_POPULAR",
                    "UBS_ATENCAO_PRIMARIA",
                }:
                    hit = hits[0]
                    cat = hit.route_category
                    if cat == "SISREG_EXAME_CONSULTA":
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
                    elif cat == "ALTO_CUSTO_CEAF":
                        via = CoverageRoute.FARMACIA_ALTO_CUSTO
                        local = (
                            "Farmácia de Alto Custo (CEAF-DF): Polos Asa Sul, Ceilândia ou Gama."
                        )
                        docs = [
                            "Laudo de Medicamento Especializado (LME) com CID-10",
                            "Receita médica em 2 vias",
                            "Cartão Nacional de Saúde (CNS)",
                            "Documento oficial com foto e CPF",
                            "Comprovante de residência no DF",
                        ]
                        val_dias = 90
                    elif cat == "FARMACIA_POPULAR":
                        via = CoverageRoute.FARMACIA_POPULAR
                        local = f"Drogarias credenciadas ao Farmácia Popular em {regiao}."
                        docs = [
                            "Receita médica válida com CRM legível",
                            "Documento oficial com foto",
                            "CPF do paciente",
                        ]
                        val_dias = 180
                    else:
                        via = CoverageRoute.UBS_REME_DF
                        local = (
                            f"Farmácia da Unidade Básica de Saúde (UBS) de referência em {regiao}."
                        )
                        docs = [
                            "Receita médica válida",
                            "Cartão Nacional de Saúde (CNS)",
                            "Documento oficial com foto e CPF",
                        ]
                        val_dias = 180

                    dt_limite = data_base + timedelta(days=val_dias)
                    d_restantes = max(0, (dt_limite - hoje).days)
                    itens_roteiro.append(
                        ItemRoteiroCidadao(
                            medicamento_ou_exame=nome,
                            principio_ativo_dcb=hit.matched_dcb.upper()
                            if hit.matched_dcb
                            else nome.upper(),
                            via_retirada=via,
                            local_sugerido=local,
                            o_que_levar=docs,
                            dias_validade_receita=val_dias,
                            data_limite_validade=dt_limite,
                            dias_restantes=d_restantes,
                            alerta_vencimento_proximo=d_restantes <= 15,
                            citacao_normativa=f"{hit.document_title} (Pág. {hit.page_number})",
                        )
                    )
                else:
                    itens_roteiro.append(
                        ItemRoteiroCidadao(
                            medicamento_ou_exame=nome,
                            principio_ativo_dcb=nome.upper(),
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

        resumo = " ".join(partes)

        return CitizenGuidanceCard(
            sucesso=True,
            regiao_administrativa=regiao,
            itens_auditados=itens_roteiro,
            resumo_acolhedor=resumo,
            solicitou_automedicacao=False,
        )
