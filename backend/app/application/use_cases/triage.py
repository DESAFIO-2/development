"""Inspeção granular compartilhada entre auditoria e orquestração."""

from app.application.ports import GuardrailPort
from app.core.telemetry import trace_operation
from app.domain.guidance import CitizenGuidanceCard
from app.domain.prescription import PrescriptionAuditRequest


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
