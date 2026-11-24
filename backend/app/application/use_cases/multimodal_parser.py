"""Parser determinístico de conteúdo extraído de PDF digital e transcrição de áudio.

Extrai Região Administrativa do DF, data de emissão, candidatos a medicamentos/exames
e dúvida administrativa preservando a blindagem contra ecos de posologia.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal

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
from app.guardrails.clinical import ClinicalGuardrail
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
    r"^(?:receitu[aá]rio|receita\s+m[eé]dica|guia\s+(?:de\s+)?solicita[cç][aã]o"
    r"|solicita[cç][aã]o\s+ambulatorial|secretaria\s+de\s+(?:estado\s+de\s+)?sa[uú]de"
    r"|governo\s+do\s+distrito|sus[-\s]*df|paciente|nome\s+do\s+paciente|titular"
    r"|cpf|cns|cart[aã]o\s+sus|rg\b|crm|cid-?10|cep|endere[cç]o|telefone|e-?mail"
    r"|data\s+de\s+nascimento|nascimento|assinad[oa]|icp-?brasil|carimbo|validade"
    r"|observa[cç][oõ]es|justificativa(?:\s+cl[ií]nica)?|hip[oó]tese\s+diagn[oó]stica"
    r"|indica[cç][aã]o\s+cl[ií]nica|hist[oó]rico\s+cl[ií]nico|quadro\s+cl[ií]nico"
    r"|anamnese|motivo\s+do\s+exame|sinais?\s+e\s+sintomas?|modo\s+de\s+usar"
    r"|data(?:\s+de\s+emiss[aã]o)?|emiss[aã]o|local\s+de\s+atendimento)\b",
    re.IGNORECASE,
)

_SECAO_CLINICA_PREFIX_RE = re.compile(
    r"^(?:justificativa(?:\s+cl[ií]nica)?|hip[oó]tese\s+diagn[oó]stica"
    r"|indica[cç][aã]o\s+cl[ií]nica|hist[oó]rico\s+cl[ií]nico|quadro\s+cl[ií]nico"
    r"|anamnese|motivo\s+do\s+exame|sinais?\s+e\s+sintomas?|cid-?10)\s*:",
    re.IGNORECASE,
)

_SECAO_POSOLOGIA_PREFIX_RE = re.compile(
    r"^(?:uso\s+(?:oral|t[oó]pico|nasal|retal|oft[aá]lmico|subcut[aâ]neo|injet[aá]vel"
    r"|externo|cont[ií]nuo)|posologia|modo\s+de\s+usar)\s*:",
    re.IGNORECASE,
)

_PDF_CLINICAL_GUARDRAIL = ClinicalGuardrail()

_PERGUNTA_OU_PEDIDO_CIDADAO_RE = re.compile(
    r"\?|\b(?:o\s+que|qual|quais|posso|devo|quero|gostaria|preciso\s+saber"
    r"|pode\s+(?:me|nos|tomar|dar|usar|partir|quebrar|dobrar|trocar"
    r"|substituir|passar|indicar|receitar|prescrever)"
    r"|como\s+(?:eu\s+)?(?:usar|uso|tomar|tomo|aplicar|aplico|faco|fazer)"
    r"|me\s+(?:indique|receite|passe|passa|recomende)"
    r"|esqueci|atrasad\w*|faz\s+mal"
    r"|interac(?:ao|oes)|interage\w*\s+com|efeito\w*\s+colatera\w*"
    r"|reac(?:ao|oes)\s+adversa\w*"
    r"|regras|instrucoes|prompt|hipotetica|desenvolvedor)\b",
    re.IGNORECASE,
)

_POSOLOGIA_INSEGURA_RE = re.compile(
    r"\b(?:dobr\w*|duplic\w*|triplic\w*|aument\w*|diminu\w*|reduz\w*"
    r"|interromp\w*|parar|pare|suspender|suspenda|por\s+conta\s+propria"
    r"|repetir|repita|duas\s+vezes|2\s*x|em\s+dobro|de\s+uma\s+vez"
    r"|eu|meu|minha|estou|sinto|senti|tenho|tive)\b",
    re.IGNORECASE,
)

_POSOLOGIA_IMPERATIVE_START_RE = re.compile(
    r"^(?:partir|cortar|dividir|fracionar|amassar|dissolver|diluir"
    r"|tomar|usar|aplicar|administrar|ingerir"
    r"|\d+(?:[.,]\d+)?\s*(?:comprimidos?|capsulas?|gotas?|ml|cp|comp))\b",
    re.IGNORECASE,
)

_CONTEXTO_CLINICO_ELETIVO_RE = re.compile(
    r"\b(?:paciente|acompanhamento|investigac\w*|avaliac\w*|controle|rastreio"
    r"|eletiv\w*|ambulatorial|cronic\w*|atipic\w*|aos\s+esforcos|esforcos"
    r"|previ[oa]s?|historico|antecedente|angina|coronarian\w*|isquemi\w*"
    r"|ecocardiograma|cardiologia|holter|ergometric\w*|cid\b|evoluir"
    r"|refer[ei]|queixa\s+de|relato\s+de)\b"
    r"|\bha\s+\d+\s+(?:dias?|semanas?|mes(?:es)?|anos?)\b",
    re.IGNORECASE,
)

_EMERGENCIA_PESSOAL_OU_AGUDA_RE = re.compile(
    r"\b(?:eu|meu|minha|me|estou|sinto|senti|sentindo|tenho|tive|tendo|fiquei"
    r"|agora|neste\s+momento|socorro|ajuda|emergencia|urgente|samu|upa"
    r"|tomo|tomar|faco|fazer|chamar)\b",
    re.IGNORECASE,
)

_NARRATIVA_NEGATIVA_CLINICA_RE = re.compile(
    r"\b(?:"
    r"(?:nao|nunca)\s+(?:usar|tomar|administrar|utilizar|prescrever|fazer\s+uso)"
    r"|evitar|contraindicad[oa]s?|intoleran\w*|alergi[ac]\w*"
    r"|suspender|suspens[oa]|interromp\w*"
    r"|historico\s+(?:de|previo)|uso\s+previo"
    r"|sem\s+(?:resposta|melhora|adesao)"
    r"|relata\s+(?:uso|alergia|intolerancia)"
    r")\b",
    re.IGNORECASE,
)

_CONT_POSOLOGIA_RE = re.compile(
    r"^(?:"
    r"tomar|tome|usar|use|aplicar|aplique|ingerir|ingira|administrar|administre"
    r"|diluir|dissolver|manter|mastigar|engolir|agitar|pingar|inalar"
    r"|partir|cortar|dividir|amassar"
    r"|de\s+\d+\s+em\s+\d+|a\s+cada\s+\d+|pela\s+manha|a\s+noite|em\s+jejum"
    r"|antes\s+d|apos\s+|durante\s+|por\s+\d+\s+(?:dias?|semanas?|mes)"
    r"|\d+(?:[.,]\d+)?\s*(?:comprimidos?|capsulas?|gotas?|ml|cp|comp|doses?|x\b|vezes)"
    r")\b",
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


def _linha_eh_documental_segura(texto: str, tipo_secao: Literal["clinica", "posologia"]) -> bool:
    """Autoriza omissão no guardrail clínico apenas para texto documental impessoal estrito.

    Nunca dispensa `PRESCRICAO`, `DIAGNOSTICO`, `TROCA_TERAPEUTICA`, `JAILBREAK`,
    dúvidas/comandos cidadãos ou relatos de emergência pessoal/aguda.
    """
    norm = normalizar_texto_pt(texto)
    if "?" in texto or _PERGUNTA_OU_PEDIDO_CIDADAO_RE.search(norm):
        return False
    check = _PDF_CLINICAL_GUARDRAIL.inspecionar_clinico(texto)
    if not check.bloqueado:
        return True
    if tipo_secao == "posologia" and check.motivo == "DOSAGEM":
        if _POSOLOGIA_INSEGURA_RE.search(norm):
            return False
        sem_prefixo = re.sub(
            r"^(?:uso\s+[a-z]+\s*:?\s*|posologia\s*:?\s*|modo\s+de\s+usar\s*:?\s*)",
            "",
            norm,
        ).lstrip(" -–—;,.")
        return bool(_POSOLOGIA_IMPERATIVE_START_RE.match(sem_prefixo))
    if tipo_secao == "clinica" and check.alerta_emergencia:
        if _EMERGENCIA_PESSOAL_OU_AGUDA_RE.search(norm):
            return False
        return bool(_CONTEXTO_CLINICO_ELETIVO_RE.search(norm))
    return False


def _linha_eh_novo_item_pos_posologia(linha: str, tabular_matcher: TabularDCBMatcher) -> bool:
    """Identifica novo item prescrito após seção de posologia sem numeração."""
    norm = normalizar_texto_pt(linha)
    if not norm or _eh_boilerplate(linha):
        return False
    if _NARRATIVA_NEGATIVA_CLINICA_RE.search(norm) or _CONT_POSOLOGIA_RE.match(norm):
        return False
    texto_u = _normalizar_unidades_faladas(linha)
    if _ITEM_SUSPEITO_NAO_LISTADO_RE.search(texto_u):
        return True
    if tabular_matcher.rotulo_documental(texto_u) or tabular_matcher.casar(texto_u):
        return True
    tokens = set(norm.split())
    return bool(tokens & _SISREG_EXTRA_KEYWORDS) or "sisreg" in tokens


def texto_pdf_para_guardrail_clinico(texto_pdf: str) -> str:
    """Remove seções documentais do prescritor sem ocultar perguntas ou comandos cidadãos.

    A inspeção contra prompt injection continua rodando no texto bruto integral.
    """
    linhas_filtradas: list[str] = []
    secao_tipo: Literal["clinica", "posologia"] | None = None
    for linha_bruta in texto_pdf.splitlines():
        linha = " ".join(linha_bruta.strip().split())
        if not linha:
            secao_tipo = None
            continue
        if _ITEM_PREFIX_RE.match(linha):
            secao_tipo = None
        elif _SECAO_CLINICA_PREFIX_RE.match(linha):
            secao_tipo = "clinica"
            if not _linha_eh_documental_segura(linha, "clinica"):
                linhas_filtradas.append(linha)
            continue
        elif _SECAO_POSOLOGIA_PREFIX_RE.match(linha):
            secao_tipo = "posologia"
            if not _linha_eh_documental_segura(linha, "posologia"):
                linhas_filtradas.append(linha)
            continue
        elif _BOILERPLATE_PREFIX_RE.match(linha):
            secao_tipo = None

        if secao_tipo is not None:
            if not _linha_eh_documental_segura(linha, secao_tipo):
                linhas_filtradas.append(linha)
            continue

        corte = _POSOLOGIA_CORTE_RE.search(linha)
        if corte:
            prefixo = linha[: corte.start()].strip()
            cauda = linha[corte.start() :].strip()
            if not _linha_eh_documental_segura(cauda, "posologia"):
                linhas_filtradas.append(linha)
            elif prefixo:
                linhas_filtradas.append(prefixo)
            continue

        linhas_filtradas.append(linha)
    return "\n".join(linhas_filtradas)


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


def _apresentacao_chave(
    med: CanonicalMedicationItem, tabular_matcher: TabularDCBMatcher
) -> tuple[str, str, str]:
    return (
        normalizar_texto_pt(med.dcb_name),
        tabular_matcher.normalizar_concentracao(med.concentration),
        med.dispensation_route,
    )


def _selecao_para_atributos(
    selecao: MedicationItemInput,
    tabular_matcher: TabularDCBMatcher,
) -> tuple[set[str], str, str]:
    conc = tabular_matcher.normalizar_concentracao(selecao.concentracao or "")
    if not conc and selecao.nome_digitado:
        try:
            doses_sel = tabular_matcher.doses_no_texto(selecao.nome_digitado)
        except ValueError:
            doses_sel = set()
        if len(doses_sel) == 1:
            conc = next(iter(doses_sel))
    forma = selecao.forma_farmaceutica or _extrair_forma_linha(selecao.nome_digitado)
    dcbs: set[str] = set()
    if selecao.principio_ativo_dcb:
        dcbs.add(normalizar_texto_pt(selecao.principio_ativo_dcb))
    elif selecao.nome_digitado:
        casados = tabular_matcher.casar(
            selecao.nome_digitado,
            concentracao=conc,
            forma=forma,
            deduplicar=False,
        )
        if not casados and forma:
            casados = tabular_matcher.casar(
                selecao.nome_digitado,
                concentracao=conc,
                forma="",
                deduplicar=False,
            )
        dcbs.update(normalizar_texto_pt(m.dcb_name) for _, m in casados)
    return dcbs, conc, forma


def _filtrar_por_selecoes(
    candidatos: list[CanonicalMedicationItem],
    selecoes: Sequence[MedicationItemInput],
    tabular_matcher: TabularDCBMatcher,
) -> list[CanonicalMedicationItem]:
    selecionados: list[CanonicalMedicationItem] = []
    for selecao in selecoes:
        dcbs, conc, forma = _selecao_para_atributos(selecao, tabular_matcher)
        if not dcbs:
            continue
        for dcb in dcbs:
            matches = tabular_matcher.filtrar_rotulo(
                candidatos,
                dcb=dcb,
                dose=conc,
                forma=forma,
            )
            for _, med in matches:
                if med not in selecionados:
                    selecionados.append(med)
    return selecionados


def _resolver_com_selecao_unica(
    candidatos: list[CanonicalMedicationItem],
    selecoes: Sequence[MedicationItemInput],
    tabular_matcher: TabularDCBMatcher,
) -> list[CanonicalMedicationItem] | None:
    selecionados = _filtrar_por_selecoes(candidatos, selecoes, tabular_matcher)
    if not selecionados:
        return None
    unicos = {_apresentacao_chave(med, tabular_matcher) for med in selecionados}
    return selecionados if len(unicos) == 1 else None


def _item_para_med(med: CanonicalMedicationItem) -> MedicationItemInput:
    return MedicationItemInput(
        nome_digitado=f"{med.dcb_name.title()} {med.concentration}".strip(),
        principio_ativo_dcb=med.dcb_name.upper(),
        concentracao=med.concentration,
        forma_farmaceutica=med.pharmaceutical_form,
    )


def _resolver_segmento(
    segmento: str,
    *,
    canal: CanalMultimodal,
    confirmado_pelo_usuario: bool,
    dcbs_confirmados_norm: set[str],
    itens_explicitos: Sequence[MedicationItemInput],
    confirmados_por_dcb: dict[str, list[CanonicalMedicationItem]],
    tinha_marcador_item: bool,
    tabular_matcher: TabularDCBMatcher,
    medication_repo: MedicationRepositoryPort,
    retriever: RetrieverPort | None,
) -> tuple[
    ExtractedCandidateItem | None, MedicationItemInput | None, list[CanonicalMedicationItem]
]:
    """Analisa um segmento textual limpo e tenta resolver medicamento ou exame."""
    texto_unidades = _normalizar_unidades_faladas(segmento)
    forma = _extrair_forma_linha(texto_unidades)
    norm_seg = normalizar_texto_pt(texto_unidades)
    if not norm_seg:
        return None, None, []

    def _avaliar_candidatos_catalogo(
        meds_ordenados: list[CanonicalMedicationItem],
        *,
        forcar_multi: bool,
    ) -> tuple[ExtractedCandidateItem, MedicationItemInput | None, list[CanonicalMedicationItem]]:
        resolvidos = (
            _resolver_com_selecao_unica(meds_ordenados, itens_explicitos, tabular_matcher)
            if confirmado_pelo_usuario and itens_explicitos
            else None
        )
        meds_efetivos = resolvidos or meds_ordenados
        med = meds_efetivos[0]
        dcb_norm = normalizar_texto_pt(med.dcb_name)
        chaves_distintas = {_apresentacao_chave(m, tabular_matcher) for m in meds_efetivos}
        chaves_confirmadas = {
            _apresentacao_chave(m, tabular_matcher) for m in confirmados_por_dcb.get(dcb_norm, ())
        }
        ja_confirmado = normalizar_texto_pt(
            f"{med.dcb_name} {med.concentration} {med.pharmaceutical_form}"
        ) in dcbs_confirmados_norm or bool(chaves_distintas & chaves_confirmadas)
        # Divergência entre PDF/explícitos e voz: exige resolução estruturada se não arbitrada.
        divergencia_voz = (
            canal == "voz"
            and bool(chaves_confirmadas)
            and not bool(chaves_distintas & chaves_confirmadas)
        )
        explicitos_da_dcb = _filtrar_por_selecoes(
            confirmados_por_dcb.get(dcb_norm, []) + meds_efetivos,
            itens_explicitos,
            tabular_matcher,
        )
        arbitrado_por_selecao = bool(
            divergencia_voz and confirmado_pelo_usuario and explicitos_da_dcb
        )
        if arbitrado_por_selecao:
            escolhido = explicitos_da_dcb[0]
            cand_arb = ExtractedCandidateItem(
                texto_origem=segmento,
                dcb_sugerido=escolhido.dcb_name.upper(),
                concentracao_sugerida=escolhido.concentration,
                forma_sugerida=escolhido.pharmaceutical_form,
                origem_canal=canal,
                status_resolucao="EXATO_CATALOGO",
                opcoes_autocomplete=[],
            )
            return cand_arb, None, [escolhido]

        ambiguidade_catalogo = len(chaves_distintas) > 1 or (
            forcar_multi
            and len(meds_efetivos) > 1
            and (
                len({m.dispensation_route for m in meds_efetivos}) > 1
                or len({m.concentration for m in meds_efetivos}) > 1
                or len({m.dcb_name for m in meds_efetivos}) > 1
            )
        )
        precisa_confirmar = (
            ambiguidade_catalogo
            or divergencia_voz
            or (canal == "voz" and not confirmado_pelo_usuario and not ja_confirmado)
        )
        status: StatusResolucaoItem = (
            "AMBIGUO_REQUER_CONFIRMACAO" if precisa_confirmar else "EXATO_CATALOGO"
        )
        opcoes_meds = (
            confirmados_por_dcb.get(dcb_norm, []) + meds_efetivos
            if divergencia_voz
            else meds_efetivos
        )
        opcoes = _formatar_opcoes_autocomplete(opcoes_meds) if precisa_confirmar else []
        cand = ExtractedCandidateItem(
            texto_origem=segmento,
            dcb_sugerido=med.dcb_name.upper(),
            concentracao_sugerida=med.concentration,
            forma_sugerida=med.pharmaceutical_form,
            origem_canal=canal,
            status_resolucao=status,
            opcoes_autocomplete=opcoes,
        )
        item = _item_para_med(med) if not precisa_confirmar else None
        return cand, item, ([] if precisa_confirmar else [med])

    # 1. Tenta rótulo documental exato primeiro (catálogo oficial)
    rotulo_hits = tabular_matcher.rotulo_documental(texto_unidades)
    if rotulo_hits:
        return _avaliar_candidatos_catalogo(rotulo_hits, forcar_multi=True)

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
    if matches:
        meds_ordenados = [m for _, m in matches]
        dcb_distintas = {m.dcb_name for m in meds_ordenados}
        concentracoes_distintas = {m.concentration for m in meds_ordenados}
        vias_distintas = {m.dispensation_route for m in meds_ordenados}
        forcar_multi = (
            len(dcb_distintas) > 1
            or (len(concentracoes_distintas) > 1 and not dose_unica)
            or (len(doses) > 1 and len(dcb_distintas) == 1)
            or (len(vias_distintas) > 1 and not forma)
            or numero_solto
        )
        if numero_solto and not forcar_multi:
            forcar_multi = True
        resolvidos = (
            _resolver_com_selecao_unica(meds_ordenados, itens_explicitos, tabular_matcher)
            if confirmado_pelo_usuario and itens_explicitos
            else None
        )
        if resolvidos is not None:
            return _avaliar_candidatos_catalogo(resolvidos, forcar_multi=False)
        if forcar_multi:
            # Preserva exigência de confirmação se concentração ambígua foi marcada sem seleção.
            cand_m, item_m, resolved_m = _avaliar_candidatos_catalogo(
                meds_ordenados, forcar_multi=True
            )
            if cand_m.status_resolucao == "EXATO_CATALOGO":
                cand_m = cand_m.model_copy(
                    update={
                        "status_resolucao": "AMBIGUO_REQUER_CONFIRMACAO",
                        "opcoes_autocomplete": _formatar_opcoes_autocomplete(meds_ordenados),
                    }
                )
                return cand_m, None, []
            return cand_m, item_m, resolved_m
        return _avaliar_candidatos_catalogo(meds_ordenados, forcar_multi=False)

    # 3. Sugestão ortográfica (distância 1) antes de desistir
    sugestao = tabular_matcher.sugerir_correcao_ortografica(texto_unidades)
    if sugestao is not None:
        dcb_original, consulta_corrigida = sugestao
        matches_filtrados = tabular_matcher.casar(
            consulta_corrigida,
            concentracao=dose_unica,
            forma=forma,
            deduplicar=False,
        )
        meds_filtrados = [m for _, m in matches_filtrados]
        meds_sug = meds_filtrados or medication_repo.sugerir_autocomplete(dcb_original, limite=5)
        apresentacoes_unicas = {_apresentacao_chave(m, tabular_matcher) for m in meds_sug}
        selecionados_typo = (
            _resolver_com_selecao_unica(meds_sug, itens_explicitos, tabular_matcher)
            if confirmado_pelo_usuario and itens_explicitos
            else None
        )
        if selecionados_typo is not None:
            med_u = selecionados_typo[0]
            cand = ExtractedCandidateItem(
                texto_origem=segmento,
                dcb_sugerido=med_u.dcb_name.upper(),
                concentracao_sugerida=med_u.concentration,
                forma_sugerida=med_u.pharmaceutical_form,
                origem_canal=canal,
                status_resolucao="EXATO_CATALOGO",
                opcoes_autocomplete=[],
            )
            return cand, _item_para_med(med_u), [med_u]
        if confirmado_pelo_usuario and meds_filtrados and len(apresentacoes_unicas) == 1:
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
            return cand, _item_para_med(med_u), [med_u]
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
        return cand, None, []

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
            return cand, item, []

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
        return (
            cand,
            MedicationItemInput(
                nome_digitado=segmento,
                concentracao=dose_unica or None,
                forma_farmaceutica=forma or None,
            ),
            [],
        )

    return None, None, []


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
    itens_explicitos: Sequence[MedicationItemInput] = (),
) -> ParsedMultimodalContent:
    """Consolida entidades, candidatos e dúvida administrativa de múltiplos canais."""
    itens_confirmados: list[MedicationItemInput] = []
    candidatos: list[ExtractedCandidateItem] = []
    vistos_itens: set[tuple[str, str]] = set()
    dcbs_confirmados_norm: set[str] = {
        normalizar_texto_pt(dcb) for dcb in (dcbs_ja_confirmados or set()) if dcb.strip()
    }
    confirmados_por_dcb: dict[str, list[CanonicalMedicationItem]] = {}

    def _registrar_confirmados(meds: Sequence[CanonicalMedicationItem]) -> None:
        for med in meds:
            chave_dcb = normalizar_texto_pt(med.dcb_name)
            lista = confirmados_por_dcb.setdefault(chave_dcb, [])
            if med not in lista:
                lista.append(med)
            dcbs_confirmados_norm.add(
                normalizar_texto_pt(f"{med.dcb_name} {med.concentration} {med.pharmaceutical_form}")
            )

    _registrar_confirmados(
        _filtrar_por_selecoes(tabular_matcher.medications, itens_explicitos, tabular_matcher)
    )
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
        secao_atual: Literal["clinica", "posologia"] | None = None
        for linha_bruta in pdf_texto.splitlines():
            linha_str = " ".join(linha_bruta.strip().split())
            if not linha_str:
                secao_atual = None
                continue
            if _ITEM_PREFIX_RE.match(linha_str):
                secao_atual = None
            elif _SECAO_CLINICA_PREFIX_RE.match(linha_str):
                secao_atual = "clinica"
                continue
            elif _SECAO_POSOLOGIA_PREFIX_RE.match(linha_str):
                secao_atual = "posologia"
                continue
            elif _BOILERPLATE_PREFIX_RE.match(linha_str):
                secao_atual = None
                continue

            if secao_atual == "clinica":
                continue
            if secao_atual == "posologia":
                if _linha_eh_novo_item_pos_posologia(linha_str, tabular_matcher):
                    secao_atual = None
                else:
                    continue

            if _NARRATIVA_NEGATIVA_CLINICA_RE.search(normalizar_texto_pt(linha_str)):
                continue
            limpa, tinha_marcador = _limpar_linha_item(linha_str)
            if not limpa or _eh_boilerplate(limpa) or len(limpa) > 160:
                continue
            # Ignora perguntas explícitas do PDF como candidato de medicamento
            if limpa.endswith("?") and not tinha_marcador:
                continue
            cand, item, resolved_meds = _resolver_segmento(
                limpa,
                canal="pdf",
                confirmado_pelo_usuario=confirmado_pelo_usuario,
                dcbs_confirmados_norm=dcbs_confirmados_norm,
                itens_explicitos=itens_explicitos,
                confirmados_por_dcb=confirmados_por_dcb,
                tinha_marcador_item=tinha_marcador,
                tabular_matcher=tabular_matcher,
                medication_repo=medication_repo,
                retriever=retriever,
            )
            if cand is not None:
                candidatos.append(cand)
            if item is not None:
                _registrar_confirmados(resolved_meds)
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
            cand, item, resolved_meds = _resolver_segmento(
                limpa,
                canal="voz",
                confirmado_pelo_usuario=confirmado_pelo_usuario,
                dcbs_confirmados_norm=dcbs_confirmados_norm,
                itens_explicitos=itens_explicitos,
                confirmados_por_dcb=confirmados_por_dcb,
                tinha_marcador_item=False,
                tabular_matcher=tabular_matcher,
                medication_repo=medication_repo,
                retriever=retriever,
            )
            if cand is not None:
                candidatos.append(cand)
            if item is not None:
                _registrar_confirmados(resolved_meds)
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
    requer_confirmacao = any(
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
