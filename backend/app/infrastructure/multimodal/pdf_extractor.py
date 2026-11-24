"""Extrator de camada de texto digital de PDFs em memória via pypdf (ADR 0008)."""

from __future__ import annotations

import io
import threading
import time

from pypdf import PdfReader, apply_configuration

from app.application.multimodal import PDFExtractionDTO, PDFExtractorPort
from app.seguranca.arquivos import MAX_PAGINAS_PDF, MAX_TEXTO_PDF_EXTRAIDO

_PDF_EXTRACTION_LOCK = threading.Lock()


class PyPDFDigitalExtractor(PDFExtractorPort):
    """Extrai exclusivamente camada textual nativa em memória (sem OCR e sem disco)."""

    def extrair_texto(self, conteudo: bytes) -> PDFExtractionDTO:
        with (
            _PDF_EXTRACTION_LOCK,
            apply_configuration(
                maximum_declared_stream_length=262144,
                zlib_maximum_output_length=262144,
                lzw_maximum_output_length=262144,
                run_length_maximum_output_length=262144,
                brotli_maximum_output_length=262144,
                array_based_stream_maximum_output_length=262144,
                stream_decoding_work_maximum_length=524288,
                stream_parsing_work_maximum_count=20000,
            ),
        ):
            return self._extrair_limitado(conteudo)

    def _extrair_limitado(self, conteudo: bytes) -> PDFExtractionDTO:
        inicio = time.perf_counter()
        reader = PdfReader(io.BytesIO(conteudo), strict=False)
        paginas = reader.pages[:MAX_PAGINAS_PDF]
        partes: list[str] = []
        total_chars = 0
        truncado = len(reader.pages) > MAX_PAGINAS_PDF

        for pagina in paginas:
            bruto = pagina.extract_text() or ""
            if not bruto:
                continue
            restante = MAX_TEXTO_PDF_EXTRAIDO - total_chars
            if restante <= 0:
                truncado = True
                break
            if len(bruto) > restante:
                partes.append(bruto[:restante])
                total_chars += restante
                truncado = True
                break
            partes.append(bruto)
            total_chars += len(bruto)

        texto = "\n".join(partes)
        latencia_ms = round((time.perf_counter() - inicio) * 1000, 2)
        return PDFExtractionDTO(
            text=texto,
            page_count=len(reader.pages),
            truncated=truncado,
            extractor="pypdf",
            latency_ms=latencia_ms,
        )
