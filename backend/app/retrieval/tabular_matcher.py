"""Correspondência determinística de Denominação Comum Brasileira (DCB) na base Gold."""

from __future__ import annotations

import re

from app.application.catalog_labels import label_key, medication_labels
from app.application.ports import CanonicalMedicationItem
from app.retrieval.text_normalizer import normalizar_texto_pt


class TabularDCBMatcher:
    """Busca determinística e fuzzy ponderada por sobreposição de termos de princípios ativos."""

    _IGNORED_SALTS: frozenset[str] = frozenset(
        {
            "cloridrato",
            "maleato",
            "besilato",
            "sulfato",
            "fumarato",
            "hemifumarato",
            "potassica",
            "sodica",
            "sodico",
            "calcica",
            "hidratada",
            "di",
            "hidratado",
            "humana",
            "mg",
            "mcg",
            "ui",
            "ml",
        }
    )

    _DOSE_PART = (
        r"\b\d+(?:[.,]\d+)*(?:/\d+(?:[.,]\d+)*)*\s*"
        r"(?:mcg|mg|g|ui|ml|%)(?!\w)"
        r"(?:\s*/\s*(?:\d+(?:[.,]\d+)*\s*)?(?:ml|g|dose)\b)?"
    )
    _DOSE = re.compile(_DOSE_PART + r"(?:\s*\+\s*" + _DOSE_PART + r")*", re.IGNORECASE)
    _INTERLEAVED_DOSE = re.compile(rf"{_DOSE_PART}\s*\+\s*[a-zA-ZÀ-ÿ]", re.IGNORECASE)
    _PACKAGE_SUFFIX_RE = re.compile(
        r"\((?:sistemadeaplicacao|apresentacoes?de|frasco|ampola|caneta|seringa|dispositivo"
        r"|tubo|bisnaga|bolsa|\d+(?:\.\d+)?%)[^)]*\)$"
    )
    _EQUIVALENCIAS_CONCENTRACAO_SCOPED: dict[str, tuple[frozenset[str], ...]] = {
        "sacubitril valsartana sodica hidratada": (
            frozenset({"97mg+103mg", "200mg"}),
            frozenset({"49mg+51mg", "100mg"}),
            frozenset({"24mg+26mg", "50mg"}),
        ),
        "sulfato de salbutamol": (frozenset({"100mcg", "100mcg/dose"}),),
    }

    @staticmethod
    def normalizar_concentracao(concentracao: str) -> str:
        # Remove separador de milhar brasileiro (5.000, 1.000) preservando decimais (0.25).
        sem_milhar = re.sub(
            r"(?<![\d.,])([1-9]\d{0,2}(?:\.\d{3})+)(?![\d.,])",
            lambda m: m.group(1).replace(".", ""),
            concentracao,
        )
        valor = re.sub(r"\s+", "", sem_milhar.lower().replace(",", "."))
        # Abreviação de composição (97/103 mg), sem somar doses ou converter unidades.
        composto = re.fullmatch(r"(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)(mcg|mg|g|ui)", valor)
        if composto:
            primeiro, segundo, unidade = composto.groups()
            return f"{primeiro}{unidade}+{segundo}{unidade}"
        return valor

    @classmethod
    def normalizar_concentracao_nucleo(cls, concentracao: str) -> str:
        """Extrai o núcleo da concentração sem sufixo documental de embalagem ou percentual."""
        norm = cls.normalizar_concentracao(concentracao)
        sem_sufixo = cls._PACKAGE_SUFFIX_RE.sub("", norm)
        # Trata notação "(5mg+50mg)/ml" -> "5mg+50mg/ml"
        sem_sufixo = re.sub(r"^\(([^()]+)\)(/ml|/dose|/g)$", r"\1\2", sem_sufixo)
        return sem_sufixo

    @classmethod
    def _doses_equivalentes(cls, norm_dcb: str, dose_consulta: str, dose_catalogo: str) -> bool:
        if not dose_consulta or dose_consulta == dose_catalogo:
            return True
        pares = cls._EQUIVALENCIAS_CONCENTRACAO_SCOPED.get(norm_dcb, ())
        if any(dose_consulta in par and dose_catalogo in par for par in pares):
            return True
        nucleo_consulta = cls.normalizar_concentracao_nucleo(dose_consulta)
        nucleo_catalogo = cls.normalizar_concentracao_nucleo(dose_catalogo)
        if nucleo_consulta and nucleo_consulta == nucleo_catalogo:
            # Omitir detalhe é permitido; contradizer detalhe explícito não é.
            sufixo_consulta = cls._PACKAGE_SUFFIX_RE.search(dose_consulta)
            sufixo_catalogo = cls._PACKAGE_SUFFIX_RE.search(dose_catalogo)
            return sufixo_consulta is None or (
                sufixo_catalogo is not None and sufixo_consulta.group() == sufixo_catalogo.group()
            )
        return False

    def doses_compativeis(self, consulta: str, doses_texto: set[str], concentracao: str) -> bool:
        """Confirma ambas as grafias contra a mesma apresentação do catálogo."""
        if not concentracao or not doses_texto:
            return True
        if len(doses_texto) > 1:
            return False
        dose_unica = next(iter(doses_texto))
        dose_item = self.normalizar_concentracao(concentracao)
        if dose_unica == dose_item:
            return True
        return any(
            self._doses_equivalentes(
                normalizar_texto_pt(med.dcb_name),
                dose_unica,
                self.normalizar_concentracao(med.concentration),
            )
            for _, med in self.casar(consulta, concentracao=concentracao, deduplicar=False)
        )

    @classmethod
    def _nome_componente(cls, nome: str) -> tuple[str, ...]:
        return tuple(
            t
            for t in normalizar_texto_pt(nome).split()
            if t not in cls._IGNORED_SALTS and t not in {"de", "do", "da"}
        )

    def _associacoes_intercaladas(self, texto: str) -> list[CanonicalMedicationItem]:
        """Confirma cada par ingrediente/dose, inclusive quando a ordem é invertida."""
        pares: dict[tuple[str, ...], str] = {}
        for trecho in texto.strip().rstrip("?.!").split("+"):
            match = re.fullmatch(rf"\s*([a-zA-ZÀ-ÿ -]+?)\s+({self._DOSE_PART})\s*", trecho)
            if not match:
                return []
            nome, dose = match.groups()
            chave = self._nome_componente(nome)
            if not chave or chave in pares:
                return []
            pares[chave] = self.normalizar_concentracao(dose)
        encontrados = []
        for med in self.medications:
            nomes = med.dcb_name.split("+")
            doses = self.normalizar_concentracao(med.concentration).split("+")
            if len(nomes) != len(doses) or len(nomes) != len(pares):
                continue
            documentados = {
                self._nome_componente(nome): dose for nome, dose in zip(nomes, doses, strict=True)
            }
            if documentados == pares:
                encontrados.append(med)
        return encontrados

    def doses_no_texto(self, texto: str) -> set[str]:
        """Extrai doses; associação intercalada não confirmada exige abstenção."""
        if self._INTERLEAVED_DOSE.search(texto):
            candidatos = self._associacoes_intercaladas(texto)
            doses = {self.normalizar_concentracao(m.concentration) for m in candidatos}
            if len(doses) != 1:
                raise ValueError("Associação intercalada não confirmada no catálogo")
            return doses
        return {self.normalizar_concentracao(dose) for dose in self._DOSE.findall(texto)}

    @classmethod
    def tem_numero_nao_interpretado(cls, texto: str) -> bool:
        """Número sem unidade reconhecida exige confirmação da apresentação."""
        residual = cls._DOSE.sub("", texto)
        residual = re.sub(r"\bdiabetes\s+tipo\s+[12]\b", "", residual, flags=re.IGNORECASE)
        # Quantidade de embalagem não é uma segunda concentração. Só aceitar
        # números administrativos explicitamente identificados; nunca descartar
        # o resto de uma composição porque a primeira dose foi reconhecida.
        residual = re.sub(
            r"\b\d+\s*(?:comprimidos|capsulas|cápsulas|ampolas|unidades)\b",
            "",
            residual,
            flags=re.IGNORECASE,
        )
        return bool(re.search(r"\d", residual))

    def __init__(self, medications: list[CanonicalMedicationItem]) -> None:
        self.medications = medications
        self._labels: dict[str, list[CanonicalMedicationItem]] = {}
        for med in medications:
            for label in medication_labels(med):
                self._labels.setdefault(label_key(label), []).append(med)

    def rotulo_documental(self, texto: str) -> list[CanonicalMedicationItem]:
        """Reconhece inclusive números da DCB e descrições compostas literais."""
        return self._labels.get(label_key(texto), [])

    def filtrar_rotulo(
        self, candidatos: list[CanonicalMedicationItem], *, dcb: str, dose: str, forma: str
    ) -> list[tuple[float, CanonicalMedicationItem]]:
        return [
            (1.0, med)
            for med in candidatos
            if (not dcb or label_key(dcb) == label_key(med.dcb_name))
            and self._doses_equivalentes(
                normalizar_texto_pt(med.dcb_name),
                self.normalizar_concentracao(dose),
                self.normalizar_concentracao(med.concentration),
            )
            and (not forma or label_key(forma) == label_key(med.pharmaceutical_form))
        ]

    def casar(
        self, consulta: str, *, concentracao: str = "", forma: str = "", deduplicar: bool = True
    ) -> list[tuple[float, CanonicalMedicationItem]]:
        """Retorna medicamentos canônicos casados com a consulta e score em [0, 1]."""
        norm_query = normalizar_texto_pt(consulta)
        query_tokens = set(norm_query.split())
        matches: list[tuple[float, CanonicalMedicationItem]] = []

        dose = self.normalizar_concentracao(concentracao)
        forma_norm = normalizar_texto_pt(forma)

        candidatos = (
            self._associacoes_intercaladas(consulta)
            if self._INTERLEAVED_DOSE.search(consulta)
            else self.medications
        )
        for med in candidatos:
            norm_dcb = normalizar_texto_pt(med.dcb_name)
            if not self._doses_equivalentes(
                norm_dcb, dose, self.normalizar_concentracao(med.concentration)
            ):
                continue
            if forma_norm and normalizar_texto_pt(med.pharmaceutical_form) != forma_norm:
                continue
            dcb_tokens = [t for t in norm_dcb.split() if len(t) > 2]
            core_tokens = [t for t in dcb_tokens if t not in self._IGNORED_SALTS] or dcb_tokens
            if not core_tokens:
                continue

            if f" {norm_dcb} " in f" {norm_query} ":
                score = 0.95
            else:
                matched_core = [t for t in core_tokens if t in query_tokens]
                if len(matched_core) < len(core_tokens):
                    continue
                coverage = len(matched_core) / len(core_tokens)
                score = 0.70 + 0.25 * coverage

            norm_conc = normalizar_texto_pt(med.concentration)
            if norm_conc and norm_conc in norm_query:
                score = min(1.0, score + 0.05)

            matches.append((round(score, 4), med))

        matches.sort(key=lambda item: item[0], reverse=True)

        if not deduplicar:
            return matches

        # Deduplica por dcb_name mantendo maior score
        vistos: set[str] = set()
        unicos: list[tuple[float, CanonicalMedicationItem]] = []
        for score, med in matches:
            if med.dcb_name not in vistos:
                vistos.add(med.dcb_name)
                unicos.append((score, med))

        return unicos

    def sugerir_correcao_ortografica(self, consulta: str) -> tuple[str, str] | None:
        """Sugere correção única a distância de edição/transposição 1 sem selecionar o item."""
        if self.casar(consulta):
            return None
        norm_query = normalizar_texto_pt(consulta)
        nomes_unicos: dict[str, str] = {
            normalizar_texto_pt(m.dcb_name): m.dcb_name
            for m in self.medications
            if re.fullmatch(r"[a-z]{6,}", normalizar_texto_pt(m.dcb_name))
        }
        sugestoes: set[tuple[str, str]] = set()
        for token in re.findall(r"\b[a-z]{6,}\b", norm_query):
            for norm_nome, nome_original in nomes_unicos.items():
                if abs(len(token) - len(norm_nome)) > 1:
                    continue
                if len(token) == len(norm_nome):
                    diffs = [
                        i for i, (a, b) in enumerate(zip(token, norm_nome, strict=True)) if a != b
                    ]
                    proximo = len(diffs) == 1 or (
                        len(diffs) == 2
                        and diffs[1] == diffs[0] + 1
                        and token[diffs[0]] == norm_nome[diffs[1]]
                        and token[diffs[1]] == norm_nome[diffs[0]]
                    )
                else:
                    menor, maior = sorted((token, norm_nome), key=len)
                    proximo = any(maior[:i] + maior[i + 1 :] == menor for i in range(len(maior)))
                if proximo:
                    corrigida = re.sub(rf"\b{re.escape(token)}\b", norm_nome, norm_query)
                    sugestoes.add((nome_original, corrigida))
        return next(iter(sugestoes)) if len(sugestoes) == 1 else None


__all__ = ["CanonicalMedicationItem", "TabularDCBMatcher"]
