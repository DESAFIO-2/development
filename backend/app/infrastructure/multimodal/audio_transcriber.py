"""Adaptadores plugáveis de transcrição de áudio (STT) em memória."""

from __future__ import annotations

import importlib
import io
import json
import logging
import time
import urllib.error
import urllib.request
import uuid
from typing import Any, Literal

from app.application.multimodal import AudioTranscriberPort, AudioTranscriptionDTO
from app.seguranca.arquivos import MAX_DURACAO_AUDIO_SEGUNDOS

logger = logging.getLogger("app.multimodal.stt")

STTProviderName = Literal["disabled", "faster_whisper", "whisper_http"]


class FasterWhisperTranscriberAdapter(AudioTranscriberPort):
    """Transcrição local em CPU via faster-whisper (extra opcional `stt`)."""

    def __init__(
        self,
        *,
        model_name: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
        beam_size: int = 1,
        language: str = "pt",
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.beam_size = beam_size
        self.language = language
        self._modelo: Any | None = None

    def _carregar_modelo(self) -> Any:
        if self._modelo is None:
            modulo = importlib.import_module("faster_whisper")
            whisper_cls = modulo.WhisperModel
            self._modelo = whisper_cls(
                self.model_name,
                device=self.device,
                compute_type=self.compute_type,
            )
        return self._modelo

    def transcrever(self, conteudo: bytes, *, formato: str) -> AudioTranscriptionDTO:
        inicio = time.perf_counter()
        try:
            modelo = self._carregar_modelo()
        except ImportError:
            latencia_ms = round((time.perf_counter() - inicio) * 1000, 2)
            return AudioTranscriptionDTO(
                text="",
                language=self.language,
                duration_seconds=None,
                provider="faster_whisper",
                model_name=self.model_name,
                latency_ms=latencia_ms,
                error_code="STT_DEPENDENCIA_AUSENTE",
            )
        except Exception as exc:
            logger.warning("stt_init_error", extra={"erro_tipo": type(exc).__name__})
            latencia_ms = round((time.perf_counter() - inicio) * 1000, 2)
            return AudioTranscriptionDTO(
                text="",
                language=self.language,
                duration_seconds=None,
                provider="faster_whisper",
                model_name=self.model_name,
                latency_ms=latencia_ms,
                error_code="STT_INDISPONIVEL",
            )

        try:
            segmentos, info = modelo.transcribe(
                io.BytesIO(conteudo),
                language=self.language,
                beam_size=self.beam_size,
                vad_filter=True,
            )
            duracao_bruta = getattr(info, "duration", None)
            duracao = round(float(duracao_bruta), 3) if duracao_bruta is not None else None
            if duracao is not None and duracao > MAX_DURACAO_AUDIO_SEGUNDOS:
                latencia_ms = round((time.perf_counter() - inicio) * 1000, 2)
                return AudioTranscriptionDTO(
                    text="",
                    language=getattr(info, "language", self.language),
                    duration_seconds=duracao,
                    provider="faster_whisper",
                    model_name=self.model_name,
                    latency_ms=latencia_ms,
                    error_code="AUDIO_LONGO_DEMAIS",
                )
            texto = " ".join(
                seg.text.strip() for seg in segmentos if getattr(seg, "text", "").strip()
            ).strip()
            latencia_ms = round((time.perf_counter() - inicio) * 1000, 2)
            return AudioTranscriptionDTO(
                text=texto,
                language=getattr(info, "language", self.language),
                duration_seconds=duracao,
                provider="faster_whisper",
                model_name=self.model_name,
                latency_ms=latencia_ms,
            )
        except Exception as exc:
            logger.warning("stt_transcribe_error", extra={"erro_tipo": type(exc).__name__})
            latencia_ms = round((time.perf_counter() - inicio) * 1000, 2)
            return AudioTranscriptionDTO(
                text="",
                language=self.language,
                duration_seconds=None,
                provider="faster_whisper",
                model_name=self.model_name,
                latency_ms=latencia_ms,
                error_code="STT_INDISPONIVEL",
            )


def _montar_multipart(
    conteudo: bytes,
    *,
    filename: str,
    campos: dict[str, str],
) -> tuple[bytes, str]:
    boundary = f"----RemediaBoundary{uuid.uuid4().hex}"
    partes: list[bytes] = []
    for nome, valor in campos.items():
        cabecalho = f'--{boundary}\r\nContent-Disposition: form-data; name="{nome}"\r\n\r\n'
        partes.append(f"{cabecalho}{valor}\r\n".encode())
    partes.append(
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode()
    )
    partes.append(conteudo)
    partes.append(f"\r\n--{boundary}--\r\n".encode())
    return b"".join(partes), f"multipart/form-data; boundary={boundary}"


class WhisperHTTPTranscriberAdapter(AudioTranscriberPort):
    """Cliente HTTP compatível com OpenAI Whisper (/v1/audio/transcriptions)."""

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:8001",
        model_name: str = "whisper-1",
        timeout_seconds: float = 30.0,
        language: str = "pt",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        self.language = language

    def transcrever(self, conteudo: bytes, *, formato: str) -> AudioTranscriptionDTO:
        inicio = time.perf_counter()
        ext = "".join(ch for ch in formato.lower() if ch.isalnum()) or "wav"
        body, content_type = _montar_multipart(
            conteudo,
            filename=f"audio.{ext}",
            campos={
                "model": self.model_name,
                "language": self.language,
                "response_format": "verbose_json",
            },
        )
        req = urllib.request.Request(
            f"{self.base_url}/v1/audio/transcriptions",
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                raw_payload = resp.read().decode("utf-8")
            parsed = json.loads(raw_payload)
            if not isinstance(parsed, dict) or "text" not in parsed:
                raise ValueError("Resposta STT sem campo 'text'")
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            json.JSONDecodeError,
            ValueError,
            OSError,
        ) as exc:
            logger.warning("stt_http_error", extra={"erro_tipo": type(exc).__name__})
            latencia_ms = round((time.perf_counter() - inicio) * 1000, 2)
            return AudioTranscriptionDTO(
                text="",
                language=self.language,
                duration_seconds=None,
                provider="whisper_http",
                model_name=self.model_name,
                latency_ms=latencia_ms,
                error_code="STT_INDISPONIVEL",
            )

        dur_raw = parsed.get("duration")
        duracao = round(float(dur_raw), 3) if isinstance(dur_raw, int | float) else None
        latencia_ms = round((time.perf_counter() - inicio) * 1000, 2)
        if duracao is not None and duracao > MAX_DURACAO_AUDIO_SEGUNDOS:
            return AudioTranscriptionDTO(
                text="",
                language=str(parsed.get("language") or self.language),
                duration_seconds=duracao,
                provider="whisper_http",
                model_name=self.model_name,
                latency_ms=latencia_ms,
                error_code="AUDIO_LONGO_DEMAIS",
            )
        return AudioTranscriptionDTO(
            text=str(parsed.get("text", "")).strip(),
            language=str(parsed.get("language") or self.language),
            duration_seconds=duracao,
            provider="whisper_http",
            model_name=self.model_name,
            latency_ms=latencia_ms,
        )


def build_audio_transcriber(
    provider: STTProviderName,
    *,
    model_name: str,
    base_url: str,
    timeout_seconds: float,
) -> AudioTranscriberPort | None:
    """Constrói adaptador STT explícito; padrão `disabled` retorna None sem downloads."""
    if provider == "disabled":
        return None
    if provider == "faster_whisper":
        return FasterWhisperTranscriberAdapter(model_name=model_name)
    if provider == "whisper_http":
        return WhisperHTTPTranscriberAdapter(
            base_url=base_url,
            model_name=model_name,
            timeout_seconds=timeout_seconds,
        )
    raise ValueError(f"Provedor STT inválido: {provider}")
