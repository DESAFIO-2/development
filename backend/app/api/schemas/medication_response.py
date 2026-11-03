from pydantic import BaseModel, Field


class MedicationAutocompleteItemDTO(BaseModel):
    """Item sugerido na barra de busca do app com autocomplete."""

    dcb_principio_ativo: str = Field(..., examples=["LOSARTANA POTASSICA"])
    concentracao: str = Field(..., examples=["50 MG"])
    forma_farmaceutica: str = Field(..., examples=["COMPRIMIDO"])
    dispensacao_gratuita_prevista: bool = True
    texto_exibicao: str = Field(
        ...,
        description="Texto formatado amigável para a lista do app",
        examples=["Losartana Potássica 50mg - Comprimido"],
    )


class MedicationAutocompleteResponseDTO(BaseModel):
    """Resposta com lista de sugestões de medicamentos."""

    consulta: str
    total_encontrados: int
    resultados: list[MedicationAutocompleteItemDTO]
