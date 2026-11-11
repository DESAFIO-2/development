"""Portão de arquivos enviados pelo cidadão (receita em PDF e áudio de voz).

Roda ANTES de qualquer parser. Só olha bytes: não abre, não executa e não
interpreta o arquivo. A extração de texto vem depois, e o texto extraído
passa por `inspecionar_entrada` como qualquer outra entrada.
"""

import re
from dataclasses import dataclass

MAX_BYTES_PDF = 5 * 1024 * 1024
MAX_PAGINAS_PDF = 10
MAX_BYTES_AUDIO = 10 * 1024 * 1024

# Conteúdo ativo: código, ações automáticas, arquivos embutidos, formulários.
_PDF_PROIBIDOS = frozenset(
    {
        "JavaScript",
        "JS",
        "Launch",
        "EmbeddedFile",
        "EmbeddedFiles",
        "RichMedia",
        "XFA",
        "SubmitForm",
        "ImportData",
        "GoToR",
        "GoToE",
    }
)
# Comuns em PDF legítimo, mas vale registrar.
_PDF_SUSPEITOS = frozenset({"OpenAction", "AA", "Encrypt", "ObjStm"})
_NOME_PDF = re.compile(rb"/([A-Za-z0-9#]+)")
_PAGINA = re.compile(rb"/Type\s*/Page(?![A-Za-z])")
_HEX = re.compile(r"#([0-9A-Fa-f]{2})")


@dataclass(frozen=True)
class ResultadoArquivo:
    aceito: bool
    motivos: tuple[str, ...]
    alertas: tuple[str, ...] = ()


def _nomes_pdf(conteudo: bytes) -> set[str]:
    """Nomes PDF com escapes #xx decodificados: /J#61vaScript vira JavaScript."""
    nomes = set()
    for bruto in _NOME_PDF.findall(conteudo):
        texto = bruto.decode("latin-1")
        nomes.add(_HEX.sub(lambda m: chr(int(m.group(1), 16)), texto))
    return nomes


def validar_pdf(conteudo: bytes) -> ResultadoArquivo:
    if len(conteudo) > MAX_BYTES_PDF:
        return ResultadoArquivo(False, ("PDF_GRANDE_DEMAIS",))
    if b"%PDF-" not in conteudo[:1024]:
        return ResultadoArquivo(False, ("NAO_E_PDF",))

    nomes = _nomes_pdf(conteudo)
    motivos = sorted(f"PDF_{nome.upper()}" for nome in nomes & _PDF_PROIBIDOS)
    if len(_PAGINA.findall(conteudo)) > MAX_PAGINAS_PDF:
        motivos.append("PDF_PAGINAS_DEMAIS")
    alertas = tuple(sorted(f"PDF_{nome.upper()}" for nome in nomes & _PDF_SUSPEITOS))
    return ResultadoArquivo(not motivos, tuple(motivos), alertas)


def _formato_audio(conteudo: bytes) -> str | None:
    if conteudo[:4] == b"RIFF" and conteudo[8:12] == b"WAVE":
        return "wav"
    if conteudo[:4] == b"OggS":
        return "ogg"
    if conteudo[:4] == b"fLaC":
        return "flac"
    if conteudo[:4] == b"\x1a\x45\xdf\xa3":
        return "webm"
    if conteudo[4:8] == b"ftyp":
        return "m4a"
    if conteudo[:3] == b"ID3" or conteudo[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "mp3"
    return None


def validar_audio(conteudo: bytes) -> ResultadoArquivo:
    if len(conteudo) > MAX_BYTES_AUDIO:
        return ResultadoArquivo(False, ("AUDIO_GRANDE_DEMAIS",))
    formato = _formato_audio(conteudo)
    if formato is None:
        return ResultadoArquivo(False, ("FORMATO_DE_AUDIO_DESCONHECIDO",))
    return ResultadoArquivo(True, (), (f"AUDIO_{formato.upper()}",))
