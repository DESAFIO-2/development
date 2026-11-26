"""Entrada HTTP aditiva multipart/form-data 100% em memória (Semana 5 — ADR 0008)."""

from __future__ import annotations

import json
from contextlib import aclosing
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from python_multipart.multipart import parse_options_header
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.formparsers import FormParser, MultiPartException, MultiPartParser

from app.api.autenticacao import ROTA_COM_LOGIN
from app.api.schemas.erro import ERROS_MULTIMODAL, MUITAS_REQUISICOES, NAO_AUTENTICADO
from app.api.schemas.prescription_request import DataISO, MedicationItemDTO
from app.application.multimodal import MultimodalRequest, MultimodalResponse
from app.container import get_services
from app.domain.prescription import MedicationItemInput
from app.seguranca.arquivos import MAX_BYTES_AUDIO, MAX_BYTES_PDF

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])

_CHUNK_BYTES = 65_536
_MAX_FILE_BYTES = MAX_BYTES_AUDIO + _CHUNK_BYTES
_MAX_FIELD_BYTES = 256 * 1024

_MULTIMODAL_OPENAPI_EXTRA: dict[str, Any] = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "pdf_file": {"type": "string", "format": "binary"},
                        "audio_file": {"type": "string", "format": "binary"},
                        "itens_json": {"type": "string"},
                        "pergunta_adicional": {"type": "string", "maxLength": 500},
                        "regiao_administrativa": {"type": "string", "maxLength": 150},
                        # Vazio = não informado (o campo de formulário vem em branco).
                        "data_emissao": {
                            "anyOf": [
                                {"type": "string", "format": "date"},
                                {"type": "string", "maxLength": 0},
                            ]
                        },
                        "tipo_prescritor": {"type": "string", "default": "SUS"},
                        "confirmado_pelo_usuario": {"type": "boolean", "default": False},
                    },
                }
            }
        },
    }
}


class _InMemoryMultiPartParser(MultiPartParser):
    """Mantém uploads de PDF (<= 5 MB) e áudio (<= 10 MB) estritamente em RAM."""

    spool_max_size = _MAX_FILE_BYTES

    def on_part_begin(self) -> None:
        super().on_part_begin()
        self._current_file_bytes = 0

    def on_part_data(self, data: bytes, start: int, end: int) -> None:
        if self._current_part.file is not None:
            self._current_file_bytes += end - start
            if self._current_file_bytes > _MAX_FILE_BYTES:
                raise MultiPartException("File exceeded maximum size in memory.")
        super().on_part_data(data, start, end)


class _MultimodalFormFields(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    itens_json: str | None = None
    pergunta_adicional: Annotated[str | None, Field(default=None, max_length=500)] = None
    regiao_administrativa: Annotated[str | None, Field(default=None, max_length=150)] = None
    data_emissao: DataISO | None = None
    tipo_prescritor: Annotated[str, Field(default="SUS", min_length=1, max_length=50)] = "SUS"
    confirmado_pelo_usuario: bool = False

    @field_validator(
        "itens_json",
        "pergunta_adicional",
        "regiao_administrativa",
        mode="before",
    )
    @classmethod
    def _vazio_para_none(cls, valor: Any) -> Any:
        if isinstance(valor, str) and not valor.strip():
            return None
        return valor

    @field_validator("data_emissao", mode="before")
    @classmethod
    def _data_vazia_para_none(cls, valor: Any) -> Any:
        # Só o campo vazio conta como "não informado", como diz o contrato.
        # Espaços ou qualquer outro texto passam pela validação AAAA-MM-DD.
        return None if valor == "" else valor

    @field_validator("confirmado_pelo_usuario", mode="before")
    @classmethod
    def _booleano_estrito(cls, valor: Any) -> Any:
        """Só "true" ou "false": é a confirmação do usuário sobre o que foi extraído.

        No modo permissivo, o Pydantic aceitava "0", "1", "yes", "on" etc.
        (Schemathesis ST201). Todos os clientes do repositório já mandam
        "true"/"false".
        """
        if isinstance(valor, bool):
            return valor
        if valor in ("true", "false"):
            return valor == "true"
        raise ValueError("confirmado_pelo_usuario deve ser 'true' ou 'false'")


async def _ler_upload_limitado(upload: UploadFile, limite: int) -> bytes:
    """Lê o upload em blocos com teto de memória (limite + 1 bytes) sem gravar em disco."""
    buf = bytearray()
    alvo = limite + 1
    while len(buf) < alvo:
        bloco = await upload.read(min(_CHUNK_BYTES, alvo - len(buf)))
        if not bloco:
            break
        buf.extend(bloco)
    return bytes(buf)


def _parsear_itens_json(itens_json: str | None) -> list[MedicationItemInput]:
    if not itens_json or not itens_json.strip():
        return []
    try:
        bruto = json.loads(itens_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="itens_json não contém JSON válido",
        ) from exc
    if not isinstance(bruto, list) or len(bruto) > 50:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="itens_json deve ser uma lista com até 50 itens",
        )
    itens: list[MedicationItemInput] = []
    for entry in bruto:
        try:
            dto = MedicationItemDTO.model_validate(entry)
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=exc.errors(include_input=False, include_context=False, include_url=False),
            ) from exc
        itens.append(MedicationItemInput.model_validate(dto.model_dump()))
    return itens


@router.post(
    "/multimodal",
    response_model=MultimodalResponse,
    responses={**ERROS_MULTIMODAL, **MUITAS_REQUISICOES, **NAO_AUTENTICADO},
    openapi_extra=_MULTIMODAL_OPENAPI_EXTRA,
    dependencies=ROTA_COM_LOGIN,
)
async def orchestrate_multimodal(request: Request) -> MultimodalResponse:
    content_type_raw = request.headers.get("Content-Type", "")
    content_type, _ = parse_options_header(content_type_raw)
    if content_type not in (b"multipart/form-data", b"application/x-www-form-urlencoded"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Content-Type deve ser multipart/form-data ou application/x-www-form-urlencoded",
        )

    try:
        async with aclosing(request.stream()) as stream:
            if content_type == b"multipart/form-data":
                parser: MultiPartParser | FormParser = _InMemoryMultiPartParser(
                    request.headers,
                    stream,
                    max_files=4,
                    max_fields=20,
                    max_part_size=_MAX_FIELD_BYTES,
                )
            else:
                parser = FormParser(
                    request.headers,
                    stream,
                    max_fields=20,
                    max_part_size=_MAX_FIELD_BYTES,
                )
            form = await parser.parse()
    except MultiPartException as exc:
        if "maximum size" in exc.message.lower():
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Arquivo ou campo excedeu o limite máximo em memória",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc

    pdf_bytes: bytes | None = None
    audio_bytes: bytes | None = None
    audio_filename: str | None = None
    try:
        pdf_part = form.get("pdf_file")
        audio_part = form.get("audio_file")
        # Campo de texto no lugar do arquivo era ignorado em silêncio e a
        # requisição seguia (Schemathesis ST201). Agora é erro do cliente.
        for nome, parte in (("pdf_file", pdf_part), ("audio_file", audio_part)):
            if parte is not None and not isinstance(parte, UploadFile):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"{nome} deve ser enviado como arquivo",
                )
        pdf_file = pdf_part if isinstance(pdf_part, UploadFile) else None
        audio_file = audio_part if isinstance(audio_part, UploadFile) else None

        if pdf_file is not None:
            lido_pdf = await _ler_upload_limitado(pdf_file, MAX_BYTES_PDF)
            if pdf_file.filename or len(lido_pdf) > 0:
                pdf_bytes = lido_pdf
        if audio_file is not None:
            lido_audio = await _ler_upload_limitado(audio_file, MAX_BYTES_AUDIO)
            if audio_file.filename or len(lido_audio) > 0:
                audio_bytes = lido_audio
                audio_filename = audio_file.filename

        campos_brutos = {
            chave: valor
            for chave in (
                "itens_json",
                "pergunta_adicional",
                "regiao_administrativa",
                "data_emissao",
                "tipo_prescritor",
                "confirmado_pelo_usuario",
            )
            if isinstance((valor := form.get(chave)), str)
        }
        try:
            campos = _MultimodalFormFields.model_validate(campos_brutos)
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=exc.errors(include_input=False, include_context=False, include_url=False),
            ) from exc

        itens = _parsear_itens_json(campos.itens_json)
        try:
            req = MultimodalRequest(
                itens=itens,
                pergunta_adicional=campos.pergunta_adicional,
                regiao_administrativa=campos.regiao_administrativa,
                data_emissao=campos.data_emissao,
                tipo_prescritor=campos.tipo_prescritor,
                pdf_bytes=pdf_bytes,
                audio_bytes=audio_bytes,
                audio_filename=audio_filename,
                confirmado_pelo_usuario=campos.confirmado_pelo_usuario,
            )
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=exc.errors(include_input=False, include_context=False, include_url=False),
            ) from exc

        services = get_services()
        return await run_in_threadpool(services.multimodal_use_case.executar, req)
    finally:
        pdf_bytes = None
        audio_bytes = None
        await form.close()
