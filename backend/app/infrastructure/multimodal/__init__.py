"""Adaptadores de extração documental e transcrição de áudio (Semana 5)."""

from app.infrastructure.multimodal.audio_transcriber import (
    FasterWhisperTranscriberAdapter,
    WhisperHTTPTranscriberAdapter,
    build_audio_transcriber,
)
from app.infrastructure.multimodal.pdf_extractor import PyPDFDigitalExtractor

__all__ = [
    "FasterWhisperTranscriberAdapter",
    "PyPDFDigitalExtractor",
    "WhisperHTTPTranscriberAdapter",
    "build_audio_transcriber",
]
