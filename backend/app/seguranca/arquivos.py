"""Portão de arquivos enviados pelo cidadão (receita em PDF e áudio de voz).

Roda ANTES de qualquer extração textual completa. Inspeciona bytes crus primeiro
e, quando o PDF usa objetos comprimidos (/ObjStm) ou /OpenAction, inspeciona a
árvore estrutural via `pypdf` em memória sem executar código nem gravar em disco.
"""

from __future__ import annotations

import io
import re
from collections import deque
from dataclasses import dataclass
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject, NullObject

MAX_BYTES_PDF = 5 * 1024 * 1024
MAX_PAGINAS_PDF = 10
MAX_BYTES_AUDIO = 10 * 1024 * 1024
_MAX_OBJETOS_PDF = 5_000
_MAX_PROFUNDIDADE_PDF = 12

# Conteúdo ativo: código, ações automáticas, arquivos embutidos, criptografia opaca.
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
        "AA",
        "Encrypt",
    }
)
_ACOES_OPENACTION_SUSPEITAS = frozenset(
    {
        "/JavaScript",
        "/JS",
        "/Launch",
        "/URI",
        "/GoToR",
        "/GoToE",
        "/SubmitForm",
        "/ImportData",
        "/Named",
        "/ResetForm",
        "/Sound",
        "/Movie",
        "/Rendition",
    }
)
_PDF_SUSPEITOS = frozenset({"OpenAction", "ObjStm"})
_NOME_PDF = re.compile(rb"/([A-Za-z0-9#]+)")
_PAGINA = re.compile(rb"/Type\s*/Page(?![A-Za-z])")
_OPENACTION_RAW_ACAO = re.compile(rb"/OpenAction\s*<<[^>]*/(?:S|JS|JavaScript|URI|Launch)\b")
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


def _resolver(obj: Any) -> Any:
    if isinstance(obj, IndirectObject):
        resolvido = obj.get_object()
        if resolvido is None or isinstance(resolvido, NullObject):
            raise PdfReadError("Referência indireta não resolvida")
        return resolvido
    return obj


def _inspecionar_open_action_estrutural(reader: PdfReader) -> tuple[bool, bool]:
    """Retorna (tem_open_action, bloquear_por_acao)."""
    root = _resolver(reader.trailer.get("/Root"))
    if not isinstance(root, DictionaryObject):
        raise PdfReadError("Catálogo ausente ou inválido")
    if "/OpenAction" not in root:
        return False, False
    acao = _resolver(root.get("/OpenAction"))
    # Destinos de navegação/zoom ([page_ref /Fit] ou /XYZ) são legítimos em PDFs clínicos.
    if isinstance(acao, ArrayObject):
        for item in acao:
            resolvido = _resolver(item)
            if isinstance(resolvido, DictionaryObject) and (
                str(_resolver(resolvido.get("/Type", ""))) != "/Page"
                or "/S" in resolvido
                or "/Next" in resolvido
            ):
                return True, True
        return True, False
    if isinstance(acao, DictionaryObject):
        tipo_acao = str(_resolver(acao.get("/S", "")))
        if tipo_acao in _ACOES_OPENACTION_SUSPEITAS or "/S" in acao or "/Next" in acao:
            return True, True
        return True, False
    return True, True


def _nomes_proibidos_estruturais(reader: PdfReader) -> tuple[set[str], bool]:
    """BFS limitada; nenhuma interrupção da inspeção é interpretada como aprovação.

    O orçamento inclui entradas enfileiradas, não apenas objetos já resolvidos.
    Referências repetidas são descartadas antes de verificar a profundidade.
    """
    encontrados: set[str] = set()
    proibidos_slash = {f"/{nome}" for nome in _PDF_PROIBIDOS}
    visitados: set[tuple[int, int]] = set()
    containers: set[int] = set()
    fila: deque[tuple[Any, int]] = deque([(reader.trailer, 0)])
    agendados = 1
    incompleta = False

    while fila:
        atual, profundidade = fila.popleft()
        if isinstance(atual, IndirectObject):
            chave = (atual.idnum, atual.generation)
            if chave in visitados:
                continue
            visitados.add(chave)
            try:
                atual = _resolver(atual)
            except Exception:
                incompleta = True
                continue
        if isinstance(atual, (DictionaryObject, ArrayObject)):
            if id(atual) in containers:
                continue
            containers.add(id(atual))
        if profundidade > _MAX_PROFUNDIDADE_PDF:
            incompleta = True
            continue
        if isinstance(atual, DictionaryObject):
            for k in atual:
                k_str = str(k)
                if k_str in proibidos_slash:
                    encontrados.add(f"PDF_{k_str.lstrip('/').upper()}")
            filhos = iter(atual.values())
        elif isinstance(atual, ArrayObject):
            filhos = iter(atual)
        else:
            continue
        for item in filhos:
            if agendados >= _MAX_OBJETOS_PDF:
                incompleta = True
                break
            fila.append((item, profundidade + 1))
            agendados += 1
    return encontrados, incompleta


def validar_pdf(conteudo: bytes) -> ResultadoArquivo:
    if len(conteudo) > MAX_BYTES_PDF:
        return ResultadoArquivo(False, ("PDF_GRANDE_DEMAIS",))
    if b"%PDF-" not in conteudo[:1024]:
        return ResultadoArquivo(False, ("NAO_E_PDF",))

    nomes = _nomes_pdf(conteudo)
    motivos_set: set[str] = {f"PDF_{nome.upper()}" for nome in nomes & _PDF_PROIBIDOS}
    if len(_PAGINA.findall(conteudo)) > MAX_PAGINAS_PDF:
        motivos_set.add("PDF_PAGINAS_DEMAIS")

    alertas_set: set[str] = {f"PDF_{nome.upper()}" for nome in nomes & _PDF_SUSPEITOS}
    if "OpenAction" in nomes and _OPENACTION_RAW_ACAO.search(conteudo):
        motivos_set.add("PDF_OPENACTION_ACAO")

    # Inspeção estrutural em memória quando há /ObjStm, /OpenAction ou estrutura completa.
    exige_parser = "ObjStm" in nomes or "OpenAction" in nomes
    try:
        reader = PdfReader(io.BytesIO(conteudo), strict=False)
    except Exception:
        if exige_parser:
            motivos_set.add("PDF_ESTRUTURA_INVALIDA")
    else:
        if reader.is_encrypted:
            motivos_set.add("PDF_ENCRYPT")
        else:
            encontrados, incompleta = _nomes_proibidos_estruturais(reader)
            motivos_set.update(encontrados)
            try:
                _, bloquear_open_action = _inspecionar_open_action_estrutural(reader)
                if bloquear_open_action:
                    motivos_set.add("PDF_OPENACTION_ACAO")
                # Não percorrer novamente uma árvore cujo orçamento já foi excedido.
                if not incompleta and len(reader.pages) > MAX_PAGINAS_PDF:
                    motivos_set.add("PDF_PAGINAS_DEMAIS")
            except Exception:
                incompleta = True
            if incompleta:
                motivos_set.add("PDF_ESTRUTURA_INCOMPLETA")

    motivos = tuple(sorted(motivos_set))
    alertas = tuple(sorted(alertas_set))
    return ResultadoArquivo(not motivos, motivos, alertas)


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
