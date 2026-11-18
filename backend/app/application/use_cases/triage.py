"""Inspeção granular compartilhada entre auditoria e orquestração."""

from app.application.ports import GuardrailPort
from app.core.telemetry import trace_operation
from app.domain.guidance import CitizenGuidanceCard
from app.domain.prescription import PrescriptionAuditRequest
from app.seguranca.injecao import FORTES, detectar


def inspect_request(
    request: PrescriptionAuditRequest, guardrail: GuardrailPort
) -> CitizenGuidanceCard | None:
    fields = [
        value
        for item in request.itens
        for value in item.model_dump().values()
        if isinstance(value, str) and value
    ] + [
        request.pergunta_adicional or "",
        request.regiao_administrativa,
        request.tipo_prescritor,
    ]
    with trace_operation("guardrail"):
        blocks = [
            check
            for field in fields
            if field
            if (check := guardrail.verificar_ato_medico(field)).bloqueado
        ]
        if not blocks and len(fields) > 1:
            weak_families: set[str] = set()
            for field in fields:
                if field:
                    for motivo in detectar(field).motivos:
                        if motivo not in FORTES:
                            weak_families.add(motivo)
            if len(weak_families) >= 2:
                return CitizenGuidanceCard(
                    sucesso=False,
                    regiao_administrativa="Distrito Federal",
                    itens_auditados=[],
                    resumo_acolhedor=(
                        "Aviso de Segurança (Preservação do Ato Médico — Lei nº 12.842/2013): "
                        "A solicitação contém instruções incompatíveis com o escopo de navegação "
                        "administrativa do SUS Cidadão. Informe apenas o nome do medicamento ou "
                        "exame prescrito para consultar as rotas oficiais de acesso gratuito."
                    ),
                    solicitou_automedicacao=False,
                )
    if not blocks:
        return None
    check = next((check for check in blocks if check.alerta_emergencia), blocks[0])
    return CitizenGuidanceCard(
        sucesso=False,
        regiao_administrativa=guardrail.desidentificar_dados_pessoais(
            request.regiao_administrativa
        ).texto_sanitizado,
        itens_auditados=[],
        resumo_acolhedor=check.mensagem_acolhedora,
        solicitou_automedicacao=check.motivo != "PROMPT_INJECTION",
    )


def sanitize_request(
    request: PrescriptionAuditRequest, guardrail: GuardrailPort
) -> PrescriptionAuditRequest:
    def clean(value: str) -> str:
        return guardrail.desidentificar_dados_pessoais(value).texto_sanitizado

    return request.model_copy(
        update={
            "itens": [
                item.model_copy(
                    update={
                        key: clean(value)
                        for key, value in item.model_dump().items()
                        if isinstance(value, str)
                    }
                )
                for item in request.itens
            ],
            "pergunta_adicional": clean(request.pergunta_adicional or ""),
            "regiao_administrativa": clean(request.regiao_administrativa),
            "tipo_prescritor": clean(request.tipo_prescritor),
        }
    )
