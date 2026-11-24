"""Entrada HTTP aditiva multipart/form-data para o pipeline multimodal (Semana 5)."""

from __future__ import annotations

import json
from datetime import date
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from app.api.schemas.prescription_request import MedicationItemDTO
from app.application.multimodal import MultimodalRequest, MultimodalResponse
from app.container import get_services
from app.domain.prescription import MedicationItemInput
from app.seguranca.arquivos import MAX_BYTES_AUDIO, MAX_BYTES_PDF

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])

_CHUNK_BYTES = 65_536


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
                detail=exc.errors(),
            ) from exc
        itens.append(MedicationItemInput.model_validate(dto.model_dump()))
    return itens


@router.post("/multimodal", response_model=MultimodalResponse)
async def orchestrate_multimodal(
    pdf_file: Annotated[UploadFile | None, File()] = None,
    audio_file: Annotated[UploadFile | None, File()] = None,
    itens_json: Annotated[str | None, Form()] = None,
    pergunta_adicional: Annotated[str | None, Form(max_length=500)] = None,
    regiao_administrativa: Annotated[str | None, Form(max_length=150)] = None,
    data_emissao: Annotated[date | None, Form()] = None,
    tipo_prescritor: Annotated[str, Form(min_length=1, max_length=50)] = "SUS",
    confirmado_pelo_usuario: Annotated[bool, Form()] = False,
) -> MultimodalResponse:
    pdf_bytes: bytes | None = None
    audio_bytes: bytes | None = None
    audio_filename: str | None = None
    try:
        if pdf_file is not None:
            lido_pdf = await _ler_upload_limitado(pdf_file, MAX_BYTES_PDF)
            if pdf_file.filename or len(lido_pdf) > 0:
                pdf_bytes = lido_pdf
        if audio_file is not None:
            lido_audio = await _ler_upload_limitado(audio_file, MAX_BYTES_AUDIO)
            if audio_file.filename or len(lido_audio) > 0:
                audio_bytes = lido_audio
                audio_filename = audio_file.filename

        itens = _parsear_itens_json(itens_json)
        try:
            req = MultimodalRequest(
                itens=itens,
                pergunta_adicional=pergunta_adicional,
                regiao_administrativa=regiao_administrativa,
                data_emissao=data_emissao,
                tipo_prescritor=tipo_prescritor,
                pdf_bytes=pdf_bytes,
                audio_bytes=audio_bytes,
                audio_filename=audio_filename,
                confirmado_pelo_usuario=confirmado_pelo_usuario,
            )
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=exc.errors(),
            ) from exc

        services = get_services()
        return await run_in_threadpool(services.multimodal_use_case.executar, req)
    finally:
        pdf_bytes = None
        audio_bytes = None
        if pdf_file is not None:
            await pdf_file.close()
        if audio_file is not None:
            await audio_file.close()
