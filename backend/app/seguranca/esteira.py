"""Ponto único de entrada: texto digitado, texto de PDF e transcrição de voz.

Também registra cada decisão em log estruturado SEM o texto do cidadão
(LGPD): só canal, decisão, motivos e a versão das regras. Quando o PR de
observabilidade entrar, esse log sai em JSON com trace_id.
"""

import hashlib
import html
import logging
from enum import StrEnum
from pathlib import Path

from app.seguranca.injecao import ResultadoInjecao, detectar
from app.seguranca.texto import limpar

MAX_CARACTERES = {"texto": 2_000, "pdf": 20_000, "voz": 2_000}

logger = logging.getLogger("app.seguranca")

# Hash das regras: diz no log e no MLflow qual versão do detector decidiu.
VERSAO_REGRAS = hashlib.sha256(
    (Path(__file__).parent / "injecao.py").read_bytes().replace(b"\r\n", b"\n")
).hexdigest()[:12]


class Canal(StrEnum):
    TEXTO = "texto"
    PDF = "pdf"
    VOZ = "voz"


def inspecionar_entrada(texto: str, canal: Canal) -> ResultadoInjecao:
    if len(texto) > MAX_CARACTERES[canal]:
        resultado = ResultadoInjecao(bloqueado=True, motivos=("TEXTO_GRANDE_DEMAIS",))
    else:
        resultado = detectar(texto)
    logger.info(
        "decisao_anti_injection",
        extra={
            "seguranca_canal": str(canal),
            "seguranca_bloqueado": resultado.bloqueado,
            "seguranca_motivos": list(resultado.motivos),
            "seguranca_versao_regras": VERSAO_REGRAS,
        },
    )
    return resultado


def delimitar_nao_confiavel(texto: str, canal: Canal) -> str:
    """Embrulha conteúdo de PDF/voz para o prompt, deixando claro que é DADO.

    `html.escape` impede que o texto feche a tag e "saia" do envelope.
    """
    seguro = html.escape(limpar(texto), quote=True)
    return f'<documento_nao_confiavel origem="{canal}">\n{seguro}\n</documento_nao_confiavel>'
