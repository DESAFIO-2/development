"""Extrator de camada de texto digital de PDFs em memória via pypdf (ADR 0008)."""

from __future__ import annotations

import io
import time

from pypdf import PdfReader

from app.application.multimodal import PDFExtractionDTO, PDFExtractorPort
from app.seguranca.arquivos import MAX_PAGINAS_PDF, MAX_TEXTO_PDF_EXTRAIDO


class PyPDFDigitalExtractor(PDFExtractorPort):
    """Extrai exclusivamente camada textual nativa em memória (sem OCR e sem disco)."""

    def extrair_texto(self, conteudo: bytes) -> PDFExtractionDTO:
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
