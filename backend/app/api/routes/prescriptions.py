"""Rotas da API para auditoria de receitas e busca com autocomplete."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.autenticacao import ROTA_COM_LOGIN
from app.api.schemas.erro import ROTA_PROTEGIDA
from app.api.schemas.medication_response import (
    MedicationAutocompleteItemDTO,
    MedicationAutocompleteResponseDTO,
)
from app.api.schemas.prescription_request import PrescriptionAuditRequestDTO
from app.api.schemas.prescription_response import (
    ItemRoteiroDTO,
    PrescriptionAuditResponseDTO,
)
from app.container import get_services
from app.domain.medication import route_from_dispensation
from app.domain.prescription import MedicationItemInput, PrescriptionAuditRequest

router = APIRouter(prefix="/api/v1", tags=["prescriptions"])


@router.post(
    "/prescriptions/audit",
    response_model=PrescriptionAuditResponseDTO,
    responses=ROTA_PROTEGIDA,
    dependencies=ROTA_COM_LOGIN,
)
def audit_prescription(payload: PrescriptionAuditRequestDTO) -> PrescriptionAuditResponseDTO:
    """Audita itens da receita médica e entrega o roteiro de obtenção gratuita no SUS."""
    services = get_services()
    domain_items = [
        MedicationItemInput(
            nome_digitado=it.nome_digitado,
            principio_ativo_dcb=it.principio_ativo_dcb,
            concentracao=it.concentracao,
            forma_farmaceutica=it.forma_farmaceutica,
            posologia=it.posologia,
            quantidade_prescrita=it.quantidade_prescrita,
        )
        for it in payload.itens
    ]

    domain_request = PrescriptionAuditRequest(
        itens=domain_items,
        data_emissao=payload.data_emissao,
        regiao_administrativa=payload.regiao_administrativa,
        tipo_prescritor=payload.tipo_prescritor,
        pergunta_adicional=payload.pergunta_adicional,
    )

    guidance = services.audit_use_case.executar(domain_request)

    dto_itens = [
        ItemRoteiroDTO(
            medicamento=it.medicamento_ou_exame,
            principio_ativo_dcb=it.principio_ativo_dcb,
            via_retirada=it.via_retirada,
            local_sugerido=it.local_sugerido,
            o_que_levar=it.o_que_levar,
            dias_validade_receita=it.dias_validade_receita,
            data_limite_validade=it.data_limite_validade,
            dias_restantes=it.dias_restantes,
            alerta_vencimento_proximo=it.alerta_vencimento_proximo,
            citacao_normativa=it.citacao_normativa,
        )
        for it in guidance.itens_auditados
    ]

    return PrescriptionAuditResponseDTO(
        sucesso=guidance.sucesso,
        regiao_administrativa=guidance.regiao_administrativa,
        itens=dto_itens,
        resumo_acolhedor=guidance.resumo_acolhedor,
        aviso_preservacao_ato_medico=guidance.aviso_preservacao_ato_medico,
    )


@router.get("/medications/autocomplete", response_model=MedicationAutocompleteResponseDTO)
def autocomplete_medications(
    q: str = Query(..., min_length=1, max_length=200, description="Termo digitado pelo cidadão"),
    limite: int = Query(default=10, ge=1, le=50),
) -> MedicationAutocompleteResponseDTO:
    """Sugestão assistida de medicamentos padronizados (DCB) para o autocomplete do app."""
    services = get_services()
    sugestoes = services.medication_repo.sugerir_autocomplete(q, limite=limite)

    itens = [
        MedicationAutocompleteItemDTO(
            dcb_principio_ativo=med.dcb_name.upper(),
            concentracao=med.concentration,
            forma_farmaceutica=med.pharmaceutical_form.upper(),
            via_retirada=route_from_dispensation(med.dispensation_route),
            dispensacao_gratuita_prevista=med.available_pfpb or med.available_reme_df,
            exige_lme=med.requires_lme,
            texto_exibicao=(
                f"{med.dcb_name.title()} {med.concentration} - {med.pharmaceutical_form.title()}"
            ),
        )
        for med in sugestoes
    ]

    consulta_segura = services.guardrail.desidentificar_dados_pessoais(q).texto_sanitizado
    return MedicationAutocompleteResponseDTO(
        consulta=consulta_segura,
        total_encontrados=len(itens),
        resultados=itens,
    )
