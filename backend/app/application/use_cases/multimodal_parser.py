"""Parser determinístico de conteúdo extraído de PDF digital e transcrição de áudio.

Extrai Região Administrativa do DF, data de emissão, candidatos a medicamentos/exames
e dúvida administrativa preservando a blindagem contra ecos de posologia.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from app.application.multimodal import (
    CanalMultimodal,
    ExtractedCandidateItem,
    StatusResolucaoItem,
)
from app.application.ports import (
    CanonicalMedicationItem,
    MedicationRepositoryPort,
    RetrieverPort,
)
from app.domain.prescription import MedicationItemInput
from app.retrieval.tabular_matcher import TabularDCBMatcher
from app.retrieval.text_normalizer import normalizar_texto_pt

# Regiões Administrativas oficiais do DF ordenadas da mais específica para a mais genérica.
_RAS_DF: tuple[tuple[str, str], ...] = (
    ("sol nascente e por do sol", "Sol Nascente/Pôr do Sol"),
    ("sol nascente/por do sol", "Sol Nascente/Pôr do Sol"),
    ("sol nascente", "Sol Nascente/Pôr do Sol"),
    ("nucleo bandeirante", "Núcleo Bandeirante"),
    ("recanto das emas", "Recanto das Emas"),
    ("sudoeste/octogonal", "Sudoeste/Octogonal"),
    ("sudoeste octogonal", "Sudoeste/Octogonal"),
    ("scia/estrutural", "SCIA/Estrutural"),
    ("jardim botanico", "Jardim Botânico"),
    ("riacho fundo ii", "Riacho Fundo II"),
    ("riacho fundo 2", "Riacho Fundo II"),
    ("candangolandia", "Candangolândia"),
    ("vicente pires", "Vicente Pires"),
    ("sobradinho ii", "Sobradinho II"),
    ("sobradinho 2", "Sobradinho II"),
    ("sao sebastiao", "São Sebastião"),
    ("riacho fundo i", "Riacho Fundo"),
    ("riacho fundo", "Riacho Fundo"),
    ("aguas claras", "Águas Claras"),
    ("agua quente", "Água Quente"),
    ("plano piloto", "Plano Piloto"),
    ("santa maria", "Santa Maria"),
    ("estrutural", "SCIA/Estrutural"),
    ("brazlandia", "Brazlândia"),
    ("taguatinga", "Taguatinga"),
    ("sobradinho", "Sobradinho"),
    ("planaltina", "Planaltina"),
    ("arniqueira", "Arniqueira"),
    ("arapoanga", "Arapoanga"),
    ("lago norte", "Lago Norte"),
    ("asa norte", "Asa Norte"),
    ("samambaia", "Samambaia"),
    ("ceilandia", "Ceilândia"),
    ("park way", "Park Way"),
    ("lago sul", "Lago Sul"),
    ("cruzeiro", "Cruzeiro"),
    ("sudoeste", "Sudoeste/Octogonal"),
    ("paranoa", "Paranoá"),
    ("asa sul", "Asa Sul"),
    ("itapoa", "Itapoã"),
    ("varjao", "Varjão"),
    ("fercal", "Fercal"),
    ("guara", "Guará"),
    ("gama", "Gama"),
    ("brasilia", "Brasília"),
)

_RA_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(rf"\b{re.escape(chave)}\b"), rotulo) for chave, rotulo in _RAS_DF
)

_DATE_BR_RE = re.compile(r"\b(\d{2})[/-](\d{2})[/-](\d{4})\b")
_DATE_ISO_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")

_BOILERPLATE_PREFIX_RE = re.compile(
    r"^(?:receitu[aá]rio|receita\s+m[eé]dica|secretaria\s+de\s+(?:estado\s+de\s+)?sa[uú]de"
    r"|governo\s+do\s+distrito|sus[-\s]*df|paciente|nome\s+do\s+paciente|titular"
    r"|cpf|cns|cart[aã]o\s+sus|rg\b|crm|cid-?10|cep|endere[cç]o|telefone|e-?mail"
    r"|data\s+de\s+nascimento|nascimento|assinad[oa]|icp-?brasil|carimbo|validade"
    r"|observa[cç][oõ]es|justificativa(?:\s+cl[ií]nica)?|hip[oó]tese\s+diagn[oó]stica"
    r"|data(?:\s+de\s+emiss[aã]o)?|emiss[aã]o|local\s+de\s+atendimento)\b",
    re.IGNORECASE,
)

_ITEM_PREFIX_RE = re.compile(
    r"^\s*(?:\d+[.)-]|\-\s*|\*\s*)"
    r"|^(?:medicamento|f[aá]rmaco|item|prescri[cç][aã]o|exame(?:\s+solicitado)?|procedimento)\s*:\s*",
    re.IGNORECASE,
)

_POSOLOGIA_CORTE_RE = re.compile(
    r"(?:^|\s*[-–—;,]\s*|\s+)"
    r"(?:uso\s+(?:oral|t[oó]pico|nasal|retal|oft[aá]lmico|subcut[aâ]neo|injet[aá]vel|externo)"
    r"|posologia\b|tomar\b|tom[ea]\b|aplicar\b|ingerir\b|administrar\b|usar\s+\d"
    r"|de\s+\d+\s+em\s+\d+\s*h(?:oras)?|\d+\s*(?:x|vezes)\s*(?:ao|por)\s*dia"
    r"|comprimidos?\s+(?:por|ao)\s+dia|caixa\b|dispensar\b)",
    re.IGNORECASE,
)

_PERGUNTA_VOZ_RE = re.compile(
    r"^\s*(?:onde|quais|qual|como|quando|quem|preciso|posso)\b",
    re.IGNORECASE,
)

_FORMAS_CONHECIDAS: tuple[str, ...] = (
    "comprimido revestido",
    "comprimido mastigavel",
    "comprimido efervescente",
    "comprimido",
    "capsula dura",
    "capsula",
    "solucao injetavel",
    "solucao oral",
    "solucao nasal",
    "solucao",
    "suspensao oral",
    "suspensao",
    "xarope",
    "gotas",
    "creme dermatologico",
    "creme vaginal",
    "creme",
    "pomada",
    "gel",
    "colirio",
    "seringa preenchida",
    "caneta aplicadora",
    "caneta",
    "aerossol",
    "supositorio",
    "adesivo",
)

_SISREG_EXTRA_KEYWORDS: frozenset[str] = frozenset(
    {
        "ecocardiograma",
        "endoscopia",
        "ressonancia",
        "cardiologia",
        "reumatologia",
        "endocrinologia",
        "ultrassonografia",
        "ultrassom",
        "tomografia",
        "mamografia",
        "eletrocardiograma",
        "ergometrico",
        "holter",
        "densitometria",
        "colonoscopia",
        "espirometria",
        "cateterismo",
    }
)

_UNIDADES_FALADAS_RE: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bmiligramas?\b", re.IGNORECASE), "mg"),
    (re.compile(r"\bmicrogramas?\b", re.IGNORECASE), "mcg"),
    (re.compile(r"\bmililitros?\b", re.IGNORECASE), "ml"),
    (re.compile(r"\bgramas?\b", re.IGNORECASE), "g"),
)

_ITEM_SUSPEITO_NAO_LISTADO_RE = re.compile(
    r"(?:\b\d+(?:[.,]\d+)?\s*(?:mg|mcg|g|ml|ui|meq|%)\b"
    r"|\b(?:comprimido|capsula|xarope|solucao|seringa|caneta|pomada|creme|colirio|exame)\b)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedMultimodalContent:
    """Resultado consolidado da análise estrutural de PDF e áudio."""

    itens_confirmados: list[MedicationItemInput]
    candidatos: list[ExtractedCandidateItem]
    regiao_administrativa: str | None
    data_emissao: date | None
    pergunta_extraida: str | None
    requer_confirmacao: bool


def extrair_regiao_df(texto: str) -> str | None:
    """Identifica uma Região Administrativa oficial do DF no texto fornecido."""
    norm = normalizar_texto_pt(texto)
    if not norm:
        return None
    fallback_brasilia: str | None = None
    for pattern, rotulo in _RA_PATTERNS:
        if pattern.search(norm):
            if rotulo in {"Brasília", "Plano Piloto"}:
                fallback_brasilia = fallback_brasilia or rotulo
                continue
            return rotulo
    return fallback_brasilia


def _parse_data_match(dia: int, mes: int, ano: int, hoje: date) -> date | None:
    if not (2000 <= ano <= hoje.year):
        return None
    try:
        candidato = date(ano, mes, dia)
    except ValueError:
        return None
    return candidato if candidato <= hoje else None


def extrair_data_emissao(texto: str) -> date | None:
    """Extrai a data de emissão da receita, ignorando datas de nascimento."""
    hoje = date.today()
    prioridade_alta: list[date] = []
    outras: list[date] = []
    for linha in texto.splitlines():
        norm = normalizar_texto_pt(linha)
        if not norm or "nascimento" in norm or "nasc" in norm.split():
            continue
        eh_emissao = any(k in norm for k in ("emiss", "emitid", "data da receita", "data"))
        destino = prioridade_alta if eh_emissao else outras
        for d_s, m_s, y_s in _DATE_BR_RE.findall(linha):
            dt = _parse_data_match(int(d_s), int(m_s), int(y_s), hoje)
            if dt is not None:
                destino.append(dt)
        for y_s, m_s, d_s in _DATE_ISO_RE.findall(linha):
            dt = _parse_data_match(int(d_s), int(m_s), int(y_s), hoje)
            if dt is not None:
                destino.append(dt)
    if prioridade_alta:
        return prioridade_alta[0]
    return outras[0] if outras else None


def _normalizar_unidades_faladas(texto: str) -> str:
    resultado = texto
    for regex, subst in _UNIDADES_FALADAS_RE:
        resultado = regex.sub(subst, resultado)
    return resultado


def _cortar_posologia(texto: str) -> str:
    corte = _POSOLOGIA_CORTE_RE.search(texto)
    return texto[: corte.start()].strip(" -–—;,.") if corte else texto.strip(" -–—;,.")


def _limpar_linha_item(linha: str) -> tuple[str, bool]:
    """Remove prefixos numéricos e corta cauda posológica; retorna (texto_limpo, tinha_marcador)."""
    bruta = " ".join(linha.strip().split())
    if not bruta:
        return "", False
    sem_prefixo = _ITEM_PREFIX_RE.sub("", bruta).strip()
    tinha_marcador = sem_prefixo != bruta
    while True:
        proxima = _ITEM_PREFIX_RE.sub("", sem_prefixo).strip()
        if proxima == sem_prefixo:
            break
        tinha_marcador = True
        sem_prefixo = proxima
    return _cortar_posologia(sem_prefixo), tinha_marcador


def _extrair_forma_linha(texto: str) -> str:
    norm = normalizar_texto_pt(texto)
    for forma in _FORMAS_CONHECIDAS:
        if re.search(rf"\b{re.escape(forma)}\b", norm):
            return forma
    return ""


def _formatar_opcoes_autocomplete(
    meds: list[CanonicalMedicationItem], limite: int = 5
) -> list[str]:
    opcoes: list[str] = []
    vistos: set[str] = set()
    for med in meds:
        texto = f"{med.dcb_name.title()} {med.concentration} - {med.pharmaceutical_form.title()}"
        if texto not in vistos:
            vistos.add(texto)
            opcoes.append(texto)
        if len(opcoes) >= limite:
            break
    return opcoes


def _resolver_segmento(
    segmento: str,
    *,
    canal: CanalMultimodal,
    confirmado_pelo_usuario: bool,
    dcbs_confirmados_norm: set[str],
    tinha_marcador_item: bool,
    tabular_matcher: TabularDCBMatcher,
    medication_repo: MedicationRepositoryPort,
    retriever: RetrieverPort | None,
) -> tuple[ExtractedCandidateItem | None, MedicationItemInput | None]:
    """Analisa um segmento textual limpo e tenta resolver medicamento ou exame."""
    texto_unidades = _normalizar_unidades_faladas(segmento)
    forma = _extrair_forma_linha(texto_unidades)
    norm_seg = normalizar_texto_pt(texto_unidades)
    if not norm_seg:
        return None, None

    # 1. Tenta rótulo documental exato primeiro (catálogo oficial)
    rotulo_hits = tabular_matcher.rotulo_documental(texto_unidades)
    if rotulo_hits:
        med = rotulo_hits[0]
        ja_confirmado = normalizar_texto_pt(med.dcb_name) in dcbs_confirmados_norm
        multi_rotulo = (
            len({m.dispensation_route for m in rotulo_hits}) > 1
            or len({m.concentration for m in rotulo_hits}) > 1
            or len({m.dcb_name for m in rotulo_hits}) > 1
        )
        ambiguo_rotulo = multi_rotulo or (
            canal == "voz" and not confirmado_pelo_usuario and not ja_confirmado
        )
        status: StatusResolucaoItem = (
            "AMBIGUO_REQUER_CONFIRMACAO" if ambiguo_rotulo else "EXATO_CATALOGO"
        )
        opcoes = _formatar_opcoes_autocomplete(rotulo_hits) if ambiguo_rotulo else []
        cand = ExtractedCandidateItem(
            texto_origem=segmento,
            dcb_sugerido=med.dcb_name.upper(),
            concentracao_sugerida=med.concentration,
            forma_sugerida=med.pharmaceutical_form,
            origem_canal=canal,
            status_resolucao=status,
            opcoes_autocomplete=opcoes,
        )
        item = (
            MedicationItemInput(
                nome_digitado=f"{med.dcb_name.title()} {med.concentration}".strip(),
                principio_ativo_dcb=med.dcb_name.upper(),
                concentracao=med.concentration,
                forma_farmaceutica=med.pharmaceutical_form,
            )
            if not ambiguo_rotulo
            else None
        )
        return cand, item

    # 2. Extrai doses e casa contra catálogo DCB
    try:
        doses = tabular_matcher.doses_no_texto(texto_unidades)
    except ValueError:
        doses = set()

    dose_unica = next(iter(doses)) if len(doses) == 1 else ""
    numero_solto = tabular_matcher.tem_numero_nao_interpretado(texto_unidades)
    matches = tabular_matcher.casar(
        texto_unidades,
        concentracao=dose_unica,
        forma=forma,
        deduplicar=False,
    )
    if not matches and forma:
        matches = tabular_matcher.casar(
            texto_unidades,
            concentracao=dose_unica,
            forma="",
            deduplicar=False,
        )

    if matches:
        concentracoes_distintas = {m.concentration for _, m in matches}
        dcb_distintas = {m.dcb_name for _, m in matches}
        vias_distintas = {m.dispensation_route for _, m in matches}
        top_med = matches[0][1]
        ja_confirmado = normalizar_texto_pt(top_med.dcb_name) in dcbs_confirmados_norm
        precisa_confirmar = (
            (canal == "voz" and not confirmado_pelo_usuario and not ja_confirmado)
            or len(dcb_distintas) > 1
            or (len(concentracoes_distintas) > 1 and not dose_unica)
            or (len(doses) > 1 and len(dcb_distintas) == 1)
            or (len(vias_distintas) > 1 and not forma)
            or numero_solto
        )
        status = "AMBIGUO_REQUER_CONFIRMACAO" if precisa_confirmar else "EXATO_CATALOGO"
        meds_ordenados = [m for _, m in matches]
        opcoes = _formatar_opcoes_autocomplete(meds_ordenados) if precisa_confirmar else []
        cand = ExtractedCandidateItem(
            texto_origem=segmento,
            dcb_sugerido=top_med.dcb_name.upper(),
            concentracao_sugerida=top_med.concentration,
            forma_sugerida=top_med.pharmaceutical_form,
            origem_canal=canal,
            status_resolucao=status,
            opcoes_autocomplete=opcoes,
        )
        item = (
            MedicationItemInput(
                nome_digitado=f"{top_med.dcb_name.title()} {top_med.concentration}".strip(),
                principio_ativo_dcb=top_med.dcb_name.upper(),
                concentracao=top_med.concentration,
                forma_farmaceutica=top_med.pharmaceutical_form,
            )
            if not precisa_confirmar
            else None
        )
        return cand, item

    # 3. Sugestão ortográfica (distância 1) antes de desistir
    sugestao = tabular_matcher.sugerir_correcao_ortografica(texto_unidades)
    if sugestao is not None:
        dcb_original, consulta_corrigida = sugestao
        meds_sug = medication_repo.sugerir_autocomplete(dcb_original, limite=5)
        if confirmado_pelo_usuario and len(meds_sug) == 1:
            med_u = meds_sug[0]
            cand = ExtractedCandidateItem(
                texto_origem=segmento,
                dcb_sugerido=med_u.dcb_name.upper(),
                concentracao_sugerida=med_u.concentration,
                forma_sugerida=med_u.pharmaceutical_form,
                origem_canal=canal,
                status_resolucao="EXATO_CATALOGO",
                opcoes_autocomplete=[],
            )
            item = MedicationItemInput(
                nome_digitado=f"{med_u.dcb_name.title()} {med_u.concentration}".strip(),
                principio_ativo_dcb=med_u.dcb_name.upper(),
                concentracao=med_u.concentration,
                forma_farmaceutica=med_u.pharmaceutical_form,
            )
            return cand, item
        cand = ExtractedCandidateItem(
            texto_origem=segmento,
            dcb_sugerido=dcb_original.upper(),
            concentracao_sugerida=dose_unica or None,
            forma_sugerida=forma or None,
            origem_canal=canal,
            status_resolucao="SUGESTAO_ORTOGRAFICA",
            opcoes_autocomplete=_formatar_opcoes_autocomplete(meds_sug)
            or [consulta_corrigida.title()],
        )
        return cand, None

    # 4. Exames / Regulação Ambulatorial SISREG
    tokens_seg = set(norm_seg.split())
    eh_sisreg = bool(tokens_seg & _SISREG_EXTRA_KEYWORDS) or "sisreg" in tokens_seg
    if eh_sisreg:
        confirmado_retriever = True
        if retriever is not None:
            hits = retriever.search(segmento, top_k=1)
            confirmado_retriever = bool(hits and hits[0].route_category == "SISREG_EXAME_CONSULTA")
        if confirmado_retriever:
            ambiguo_voz = canal == "voz" and not confirmado_pelo_usuario and tinha_marcador_item
            cand = ExtractedCandidateItem(
                texto_origem=segmento,
                dcb_sugerido="EXAME_SISREG",
                origem_canal=canal,
                status_resolucao=(
                    "AMBIGUO_REQUER_CONFIRMACAO" if ambiguo_voz else "EXATO_CATALOGO"
                ),
            )
            item = MedicationItemInput(nome_digitado=segmento) if not ambiguo_voz else None
            return cand, item

    # 5. Item explícito não encontrado no catálogo oficial (ex.: Tirzepatida 5 mg em PDF)
    if canal == "pdf" and (
        tinha_marcador_item or _ITEM_SUSPEITO_NAO_LISTADO_RE.search(texto_unidades)
    ):
        cand = ExtractedCandidateItem(
            texto_origem=segmento,
            dcb_sugerido=None,
            concentracao_sugerida=dose_unica or None,
            forma_sugerida=forma or None,
            origem_canal=canal,
            status_resolucao="NAO_IDENTIFICADO",
        )
        return cand, MedicationItemInput(
            nome_digitado=segmento,
            concentracao=dose_unica or None,
            forma_farmaceutica=forma or None,
        )

    return None, None


def _eh_boilerplate(linha: str) -> bool:
    if _BOILERPLATE_PREFIX_RE.match(linha.strip()):
        return True
    norm = normalizar_texto_pt(linha)
    return not norm or len(norm) < 3


def parsear_conteudo_multimodal(
    *,
    pdf_texto: str | None,
    audio_texto: str | None,
    pergunta_texto: str | None,
    confirmado_pelo_usuario: bool,
    tabular_matcher: TabularDCBMatcher,
    medication_repo: MedicationRepositoryPort,
    retriever: RetrieverPort | None = None,
    dcbs_ja_confirmados: set[str] | None = None,
) -> ParsedMultimodalContent:
    """Consolida entidades, candidatos e dúvida administrativa de múltiplos canais."""
    itens_confirmados: list[MedicationItemInput] = []
    candidatos: list[ExtractedCandidateItem] = []
    vistos_itens: set[tuple[str, str]] = set()
    dcbs_confirmados_norm: set[str] = {
        normalizar_texto_pt(dcb) for dcb in (dcbs_ja_confirmados or set()) if dcb.strip()
    }
    regiao_encontrada: str | None = None
    data_encontrada: date | None = None

    if audio_texto:
        regiao_encontrada = extrair_regiao_df(audio_texto)
    if not regiao_encontrada and pergunta_texto:
        regiao_encontrada = extrair_regiao_df(pergunta_texto)
    if not regiao_encontrada and pdf_texto:
        regiao_encontrada = extrair_regiao_df(pdf_texto)

    if pdf_texto:
        data_encontrada = extrair_data_emissao(pdf_texto)
        for linha_bruta in pdf_texto.splitlines():
            linha_str = " ".join(linha_bruta.strip().split())
            if not linha_str or _eh_boilerplate(linha_str):
                continue
            limpa, tinha_marcador = _limpar_linha_item(linha_str)
            if not limpa or _eh_boilerplate(limpa) or len(limpa) > 160:
                continue
            # Ignora perguntas explícitas do PDF como candidato de medicamento
            if limpa.endswith("?") and not tinha_marcador:
                continue
            cand, item = _resolver_segmento(
                limpa,
                canal="pdf",
                confirmado_pelo_usuario=confirmado_pelo_usuario,
                dcbs_confirmados_norm=dcbs_confirmados_norm,
                tinha_marcador_item=tinha_marcador,
                tabular_matcher=tabular_matcher,
                medication_repo=medication_repo,
                retriever=retriever,
            )
            if cand is not None:
                candidatos.append(cand)
            if item is not None:
                if item.principio_ativo_dcb:
                    dcbs_confirmados_norm.add(normalizar_texto_pt(item.principio_ativo_dcb))
                chave = (
                    normalizar_texto_pt(item.principio_ativo_dcb or item.nome_digitado),
                    (item.concentracao or "").lower(),
                )
                if chave not in vistos_itens:
                    vistos_itens.add(chave)
                    itens_confirmados.append(item)

    if audio_texto:
        # Na fala, dividimos apenas por pontuação forte para extrair eventual medicamento citado.
        segmentos_voz = [seg.strip() for seg in re.split(r"[.;!\n]+", audio_texto) if seg.strip()]
        for seg_bruto in segmentos_voz:
            limpa, _ = _limpar_linha_item(seg_bruto)
            if not limpa:
                continue
            # Na voz, perguntas sobre exame já presente no PDF ou dúvida direta vão para pergunta.
            texto_u = _normalizar_unidades_faladas(limpa)
            norm_u = normalizar_texto_pt(texto_u)
            eh_pergunta_voz = seg_bruto.strip().endswith("?") or bool(_PERGUNTA_VOZ_RE.match(limpa))
            tem_exame_so = bool(set(norm_u.split()) & _SISREG_EXTRA_KEYWORDS) and not (
                tabular_matcher.casar(texto_u)
            )
            if tem_exame_so and (itens_confirmados or eh_pergunta_voz):
                continue
            cand, item = _resolver_segmento(
                limpa,
                canal="voz",
                confirmado_pelo_usuario=confirmado_pelo_usuario,
                dcbs_confirmados_norm=dcbs_confirmados_norm,
                tinha_marcador_item=False,
                tabular_matcher=tabular_matcher,
                medication_repo=medication_repo,
                retriever=retriever,
            )
            if cand is not None:
                candidatos.append(cand)
            if item is not None:
                chave = (
                    normalizar_texto_pt(item.principio_ativo_dcb or item.nome_digitado),
                    (item.concentracao or "").lower(),
                )
                if chave not in vistos_itens:
                    vistos_itens.add(chave)
                    itens_confirmados.append(item)

    # Consolida pergunta administrativa já sanitizada.
    partes_pergunta: list[str] = []
    if pergunta_texto and pergunta_texto.strip():
        partes_pergunta.append(" ".join(pergunta_texto.split()))
    if audio_texto and audio_texto.strip():
        limpa_v = " ".join(audio_texto.split())
        if limpa_v and limpa_v not in partes_pergunta:
            partes_pergunta.append(limpa_v)

    pergunta_final = " | ".join(partes_pergunta)[:500].strip() if partes_pergunta else None
    requer_confirmacao = not confirmado_pelo_usuario and any(
        c.status_resolucao in {"SUGESTAO_ORTOGRAFICA", "AMBIGUO_REQUER_CONFIRMACAO"}
        for c in candidatos
    )
    return ParsedMultimodalContent(
        itens_confirmados=itens_confirmados,
        candidatos=candidatos,
        regiao_administrativa=regiao_encontrada,
        data_emissao=data_encontrada,
        pergunta_extraida=pergunta_final,
        requer_confirmacao=requer_confirmacao,
    )
