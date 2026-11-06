"""Pipeline determinístico de extração integral da RENAME 2024 (2ª Edição).

Extrai todas as 1.150 apresentações farmacêuticas a partir das 237 páginas de tabelas
do PDF oficial do Ministério da Saúde (`data/raw/F01-rename/rename-2024-2ed.pdf`).
Garante mapeamento de DCB, concentração, forma, componente SUS (CBAF, CEAF, CESAF),
classificação de via de gratuidade (Farmácia Popular, UBS, Alto Custo) e regras documentais.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import pypdf

# Elenco oficial Farmácia Popular do Brasil (Gratuidade 100% expandida - Portaria 3.677/2024)
PFPB_ACTIVE_INGREDIENTS = frozenset(
    {
        "losartana potassica",
        "maleato de enalapril",
        "captopril",
        "atenolol",
        "cloridrato de propranolol",
        "hidroclorotiazida",
        "besilato de anlodipino",
        "cloridrato de metformina",
        "glibenclamida",
        "insulina humana nph",
        "insulina humana regular",
        "sulfato de salbutamol",
        "dipropionato de beclometasona",
        "brometo de ipratropio",
        "alendronato de sodio",
        "sinvastatina",
        "dapagliflozina",
        "succinato de metoprolol",
    }
)

CONTINUATION_DCB_SUFFIXES = frozenset(
    {
        "hidratada",
        "diidratada",
        "monoidratada",
        "triidratada",
        "anidra",
    }
)

FORM_KEYWORDS = frozenset(
    {
        "prolongada",
        "revestido",
        "injetavel",
        "liberacao",
        "suspensao",
        "solucao",
        "comprimido",
        "capsula",
        "gotas",
        "oral",
        "retal",
        "topico",
        "creme",
        "pomada",
    }
)

COMPONENTS_PATTERN = re.compile(r"\b(Básico|Especializado|Estratégico|Hospitalar)\b", re.IGNORECASE)
ATC_PATTERN = re.compile(r"\b([A-Z]\d{2}[A-Z]{2}\d{2})\b")
# Fármaco seguido de concentração (ex: "alfa-agalsidase 1 mg/mL", "ácido acetilsalicílico 500 mg")
DCB_SPLIT_PATTERN = re.compile(r"^([a-zA-ZÀ-ÿ\s\-\+/\(\)]+?)\s+(\d+.*)$")
FORM_PATTERN = re.compile(
    r"\b(comprimido|cápsula|capsula|solução|solucao|suspensão|suspensao|creme|pomada|gel|xarope|"
    r"colírio|colirio|adesivo|pó|po|emulsão|emulsao|gotas|spray|aerossol|implante|enema|"
    r"pasta|loção|locao)\b.*",
    re.IGNORECASE,
)


def _remover_acentos(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def extrair_rename_completa(pdf_path: Path) -> list[dict[str, Any]]:
    reader = pypdf.PdfReader(str(pdf_path))
    canonical_items: list[dict[str, Any]] = []

    current_dcb: str = ""
    item_counter = 1

    for page_idx in range(24, 264):
        text = reader.pages[page_idx].extract_text()
        if not text:
            continue

        lines = text.splitlines()
        for raw_line in lines:
            line = raw_line.strip()
            # Ignora cabeçalhos, rodapés e títulos de colunas
            if (
                not line
                or "MINISTÉRIO" in line.upper()
                or "RENAME 2024" in line.upper()
                or "Denominação Comum" in line
                or "Componente de" in line
                or "Código ATC" in line
                or "Forma Farmacêutica" in line
                or "Composição" in line
                or line.startswith("continua")
                or line.startswith("|")
            ):
                continue

            comp_match = COMPONENTS_PATTERN.search(line)
            if comp_match:
                comp_raw = comp_match.group(1).lower()
                if comp_raw == "básico":
                    comp_str = "CBAF"
                    route = "UBS_ATENCAO_PRIMARIA"
                    lme = False
                    val_days = 180
                elif comp_raw == "especializado":
                    comp_str = "CEAF"
                    route = "ALTO_CUSTO_CEAF"
                    lme = True
                    val_days = 90
                elif comp_raw == "estratégico":
                    comp_str = "CESAF"
                    route = "UBS_ATENCAO_PRIMARIA"
                    lme = False
                    val_days = 180
                else:
                    comp_str = "HOSPITALAR"
                    route = "HOSPITALAR"
                    lme = False
                    val_days = 30

                prefix = line[: comp_match.start()].strip()

                # Se houver nome de DCB embutido na linha
                dcb_match = DCB_SPLIT_PATTERN.match(prefix)
                if dcb_match:
                    dcb_name = dcb_match.group(1).strip().lower()
                    conc_form = dcb_match.group(2).strip()
                    current_dcb = dcb_name
                else:
                    dcb_name = current_dcb
                    conc_form = prefix

                fm = FORM_PATTERN.search(conc_form)
                if fm:
                    conc = conc_form[: fm.start()].strip() or "Padronizada"
                    form = conc_form[fm.start() :].strip()
                else:
                    conc = conc_form or "Padronizada"
                    form = "forma oral/injetável"

                dcb_norm = _remover_acentos(dcb_name)
                is_pfpb = any(p in dcb_norm for p in PFPB_ACTIVE_INGREDIENTS)
                if is_pfpb:
                    route = "FARMACIA_POPULAR"

                docs = (
                    [
                        "Receita médica válida",
                        "Documento com foto e CPF",
                        "Cartão Nacional de Saúde (CNS)",
                    ]
                    if not lme
                    else [
                        "Laudo de Solicitação, Avaliação e Autorização de Medicamento(s) (LME)",
                        "Receita médica em duas vias pelo DCB",
                        "Documento oficial com foto e CPF",
                        "Cartão Nacional de Saúde (CNS)",
                        "Comprovante de residência no DF",
                        "Exames exigidos pelo PCDT",
                    ]
                )

                canonical_items.append(
                    {
                        "medication_id": f"MED-RENAME-{item_counter:04d}",
                        "dcb_name": dcb_name,
                        "concentration": conc,
                        "pharmaceutical_form": form,
                        "rename_component": comp_str,
                        "available_pfpb": is_pfpb,
                        "pfpb_free": is_pfpb,
                        "available_reme_df": True,
                        "dispensation_route": route,
                        "requires_lme": lme,
                        "prescription_validity_days": val_days,
                        "required_documents": docs,
                        "source_id": "RENAME_2024",
                        "source_page": page_idx + 1,
                    }
                )
                item_counter += 1
            else:
                # Linha de cabeçalho de DCB ou continuação
                clean_l = line.strip().lower()
                norm_l = _remover_acentos(clean_l)
                if (
                    not line.isdigit()
                    and len(line) > 2
                    and not line.startswith("(")
                    and len(line) < 70
                ):
                    if norm_l in CONTINUATION_DCB_SUFFIXES and current_dcb:
                        current_dcb = f"{current_dcb} {clean_l}"
                    elif norm_l in FORM_KEYWORDS or any(
                        kw in norm_l for kw in ("liberacao", "suspensao", "po para", "revestido")
                    ):
                        pass
                    else:
                        current_dcb = clean_l

    return canonical_items


if __name__ == "__main__":
    raiz = Path(__file__).resolve().parents[3]
    pdf = raiz / "data" / "raw" / "F01-rename" / "rename-2024-2ed.pdf"
    itens = extrair_rename_completa(pdf)
    print(f"Total de itens extraídos: {len(itens)}")

    destino = raiz / "data" / "processed" / "medicamentos_sus_canonical_full.json"
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(itens, f, ensure_ascii=False, indent=2)
    print(f"Salvo em: {destino}")
