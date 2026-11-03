from datetime import date

from pydantic import BaseModel, Field

from app.domain.medication import CoverageRoute


class ItemRoteiroCidadao(BaseModel):
    """Cartão individual de orientação para cada medicamento ou exame solicitado."""

    medicamento_ou_exame: str = Field(
        ...,
        description="Nome do item prescrito",
        examples=["Losartana Potássica 50mg"],
    )
    principio_ativo_dcb: str = Field(
        ...,
        description="Princípio ativo auditado",
        examples=["LOSARTANA POTASSICA"],
    )
    via_retirada: CoverageRoute = Field(
        ...,
        description="Onde retirar o medicamento gratuitamente",
    )
    local_sugerido: str = Field(
        ...,
        description="Explicação simples de onde ir (ex: Farmácia Popular com CPF)",
    )
    o_que_levar: list[str] = Field(
        ...,
        description="Checklist documental exato para não perder a viagem",
    )
    dias_validade_receita: int = Field(
        ...,
        description="Validade total da receita em dias conforme a norma",
    )
    data_limite_validade: date = Field(
        ...,
        description="Data limite calculada a partir da emissão",
    )
    dias_restantes: int = Field(
        ...,
        description="Dias restantes até o vencimento da receita médica",
    )
    alerta_vencimento_proximo: bool = Field(
        default=False,
        description="Indica se faltam 15 dias ou menos para o vencimento",
    )
    citacao_normativa: str = Field(
        ...,
        description="Base legal governamental que ampara o direito de gratuidade",
    )


class CitizenGuidanceCard(BaseModel):
    """Resposta consolidada entregue ao cidadão no App Mobile."""

    sucesso: bool = True
    regiao_administrativa: str
    itens_auditados: list[ItemRoteiroCidadao]
    resumo_acolhedor: str = Field(
        ...,
        description="Mensagem em linguagem simples e empática para Dona Helena ou Lucas",
    )
    aviso_preservacao_ato_medico: str = Field(
        default=(
            "Aviso Importante: Este sistema atua exclusivamente na orientação logística "
            "e administrativa de acesso ao SUS. Não realizamos diagnósticos, prescrições clínicas "
            "nem alteração de dosagens. Siga rigorosamente as orientações do seu médico prescritor."
        ),
        description="Guardrail ético inegociável do projeto",
    )
    solicitou_automedicacao: bool = Field(
        default=False,
        description="Flag indicando se houve tentativa de substituição clínica barrada",
    )
