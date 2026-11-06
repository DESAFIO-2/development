"""Caso de Uso: Auditoria de Receita Médica e Geração do Roteiro Cidadão (RF01 - RF08)."""

from __future__ import annotations

from datetime import date, timedelta

from app.application.ports import (
    AuditPrescriptionUseCasePort,
    MedicationRepositoryPort,
    RetrieverPort,
)
from app.domain.guidance import CitizenGuidanceCard, ItemRoteiroCidadao
from app.domain.medication import CoverageRoute
from app.domain.prescription import PrescriptionAuditRequest
from app.guardrails.clinical import ClinicalGuardrail
from app.guardrails.pii import PIIMasker
from app.retrieval.tabular_matcher import TabularDCBMatcher


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
        consulta_completa = " ".join(
            [item.nome_digitado for item in request.itens]
            + ([request.pergunta_adicional] if request.pergunta_adicional else [])
        )

        check_clinico = self.guardrail.inspecionar(consulta_completa)
        if check_clinico.bloqueado:
            return CitizenGuidanceCard(
                sucesso=False,
                regiao_administrativa=request.regiao_administrativa,
                itens_auditados=[],
                resumo_acolhedor=check_clinico.mensagem_acolhedora,
                solicitou_automedicacao=True,
            )

        # 2. Desidentificação LGPD (PII Masking)
        if request.pergunta_adicional:
            _ = self.pii_masker.mascarar(request.pergunta_adicional)

        hoje = date.today()
        data_base = request.data_emissao or hoje
        itens_roteiro: list[ItemRoteiroCidadao] = []

        # 3. Auditoria Farmacêutica para cada item da receita
        for item in request.itens:
            matches = self.tabular_matcher.casar(item.nome_digitado)

            if matches:
                _, med_canonico = matches[0]
                route_str = med_canonico.dispensation_route

                if route_str == "FARMACIA_POPULAR":
                    via = CoverageRoute.FARMACIA_POPULAR
                    local = (
                        f"Drogarias privadas credenciadas ao Farmácia Popular em "
                        f"{request.regiao_administrativa} ou nas farmácias das UBSs do DF."
                    )
                elif route_str == "ALTO_CUSTO_CEAF":
                    via = CoverageRoute.FARMACIA_ALTO_CUSTO
                    local = (
                        "Farmácia de Alto Custo (CEAF-DF): Polos Asa Sul (Estação 102 Sul), "
                        "Ceilândia (ao lado do HRC) ou Gama."
                    )
                elif route_str == "UBS_ATENCAO_PRIMARIA":
                    via = CoverageRoute.UBS_REME_DF
                    local = (
                        f"Farmácia da Unidade Básica de Saúde (UBS) de referência "
                        f"da sua quadra/bairro em {request.regiao_administrativa}."
                    )
                else:
                    via = CoverageRoute.NAO_PADRONIZADO
                    local = "Consulte a gerência de assistência farmacêutica da UBS."

                validade_dias = med_canonico.prescription_validity_days
                data_limite = data_base + timedelta(days=validade_dias)
                dias_restantes = max(0, (data_limite - hoje).days)
                alerta_vencimento = dias_restantes <= 15

                docs = list(med_canonico.required_documents or [])
                if not docs:
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

                citacao = f"{med_canonico.source_id} — Portaria GM/MS nº 6.324/2024 / REME-DF"

                itens_roteiro.append(
                    ItemRoteiroCidadao(
                        medicamento_ou_exame=item.nome_digitado,
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
                hits = self.retriever.search(item.nome_digitado, top_k=1)
                if hits:
                    hit = hits[0]
                    cat = hit.route_category
                    if cat == "SISREG_EXAME_CONSULTA":
                        via = CoverageRoute.SISREG_EXAME_CONSULTA
                        local = (
                            f"Regulação Ambulatorial / SISREG III na UBS ou "
                            f"Policlínica Regional de {request.regiao_administrativa}."
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
                        local = (
                            f"Drogarias credenciadas ao Farmácia Popular em "
                            f"{request.regiao_administrativa}."
                        )
                        docs = [
                            "Receita médica válida com CRM legível",
                            "Documento oficial com foto",
                            "CPF do paciente",
                        ]
                        val_dias = 180
                    else:
                        via = CoverageRoute.UBS_REME_DF
                        local = (
                            f"Farmácia da Unidade Básica de Saúde (UBS) de referência "
                            f"em {request.regiao_administrativa}."
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
                            medicamento_ou_exame=item.nome_digitado,
                            principio_ativo_dcb=hit.matched_dcb.upper()
                            if hit.matched_dcb
                            else item.nome_digitado.upper(),
                            via_retirada=via,
                            local_sugerido=local,
                            o_que_levar=docs,
                            dias_validade_receita=val_dias,
                            data_limite_validade=dt_limite,
                            dias_restantes=d_restantes,
                            alerta_vencimento_proximo=False,
                            citacao_normativa=f"{hit.document_title} (Pág. {hit.page_number})",
                        )
                    )
                else:
                    itens_roteiro.append(
                        ItemRoteiroCidadao(
                            medicamento_ou_exame=item.nome_digitado,
                            principio_ativo_dcb=item.nome_digitado.upper(),
                            via_retirada=CoverageRoute.NAO_PADRONIZADO,
                            local_sugerido="Item não localizado na RENAME 2024 ou REME-DF.",
                            o_que_levar=["Receita médica"],
                            dias_validade_receita=30,
                            data_limite_validade=data_base + timedelta(days=30),
                            dias_restantes=max(0, (data_base + timedelta(days=30) - hoje).days),
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
            f"Auditamos {len(itens_roteiro)} item(ns) da sua receita para a região de "
            f"{request.regiao_administrativa}."
        ]
        if total_pfpb > 0:
            partes.append(
                f"Você pode retirar {total_pfpb} remédio(s) de graça diretamente na "
                "Farmácia Popular (drogarias privadas credenciadas com seu CPF)."
            )
        if total_ubs > 0:
            partes.append(
                f"{total_ubs} remédio(s) são entregues gratuitamente na farmácia da "
                "sua Unidade Básica de Saúde (UBS)."
            )
        if total_ceaf > 0:
            partes.append(
                f"{total_ceaf} medicamento(s) fazem parte do Componente de Alto Custo (CEAF) "
                "e exigem abertura de processo com o laudo LME."
            )

        resumo = " ".join(partes)

        return CitizenGuidanceCard(
            sucesso=True,
            regiao_administrativa=request.regiao_administrativa,
            itens_auditados=itens_roteiro,
            resumo_acolhedor=resumo,
            solicitou_automedicacao=False,
        )
