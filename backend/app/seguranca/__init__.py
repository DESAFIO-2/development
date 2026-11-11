"""Camada anti-injection do SUS Cidadão (OWASP LLM01).

Toda entrada que vai chegar ao LLM passa por aqui, venha de onde vier:
texto digitado, texto extraído de PDF ou transcrição de voz.
"""

from app.seguranca.esteira import Canal, inspecionar_entrada
from app.seguranca.injecao import ResultadoInjecao, deve_bloquear

__all__ = ["Canal", "ResultadoInjecao", "deve_bloquear", "inspecionar_entrada"]
