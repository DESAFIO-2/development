"""Pipeline determinístico de consolidação multi-fonte (RENAME + REME-DF + Farmácia Popular).

Adapta o release v5 de Engenharia de Dados e preserva as fontes complementares C01-C14
para os contratos da Clean Architecture:
- `data/processed/medicamentos_sus_canonical.json`
- `data/processed/medicamentos_sus_canonical_full.json`
- `data/processed/normative_chunks.json`
- `data/processed/unified_pdf_chunks.json`
- `data/manifests/manifest.json`

Garante:
1. Detecção de Schema Drift (`validate_occurrence_drift`);
2. Normalização de unidades e concentrações entre F01 (RENAME), F03 (REME-DF) e F04 (PFPB);
3. Regeneração 100% consolidada de chunks (zero chunks com `review_status == "pending"` ou
   referências defasadas ao antigo protótipo de 24 medicamentos).
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RAIZ_REPO = Path(__file__).resolve().parents[3]

EXPECTED_OCCURRENCE_KEYS: frozenset[str] = frozenset(
    {
        "occurrence_id",
        "medicine_id",
        "active_ingredient",
        "strength",
        "form",
        "component",
        "channel",
        "atc",
        "source_code",
        "source_row_number",
        "item_type",
        "release_characteristic",
        "review_status",
        "source",
        "evidence_id",
        "raw_text",
    }
)

VALID_SOURCES: frozenset[str] = frozenset({"F01", "F03", "F04"})

OPTIONAL_OCCURRENCE_KEYS = {"description_cell", "description_provenance", "indication", "supply_id"}


ANTIMICROBIAL_KEYWORDS: frozenset[str] = frozenset(
    {
        "amoxicilina",
        "azitromicina",
        "cefalexina",
        "cefuroxima",
        "ceftriaxona",
        "ciprofloxacino",
        "claritromicina",
        "clindamicina",
        "doxiciclina",
        "eritromicina",
        "levofloxacino",
        "metronidazol",
        "nitrofurantoina",
        "norfloxacino",
        "penicilina",
        "benzilpenicilina",
        "fenoximetilpenicilina",
        "sulfametoxazol",
        "tetraciclina",
        "vancomicina",
        "meropenem",
    }
)

CONTROLLED_344_KEYWORDS: frozenset[str] = frozenset(
    {
        "fluoxetina",
        "carbamazepina",
        "amitriptilina",
        "clomipramina",
        "nortriptilina",
        "sertralina",
        "escitalopram",
        "citalopram",
        "paroxetina",
        "venlafaxina",
        "bupropiona",
        "diazepam",
        "clonazepam",
        "lorazepam",
        "midazolam",
        "fenobarbital",
        "fenitoina",
        "acido valproico",
        "valproato",
        "haloperidol",
        "risperidona",
        "clorpromazina",
        "levomepromazina",
        "litio",
        "carbonato de litio",
        "biperideno",
        "morfina",
        "codeina",
        "tramadol",
        "metadona",
        "fentanila",
    }
)

PRIORITY_24_ITEMS: list[dict[str, Any]] = [
    {
        "medication_id": "MED-LOSARTANA-50MG",
        "dcb_name": "losartana potássica",
        "concentration": "50 mg",
        "pharmaceutical_form": "comprimido",
        "rename_component": "Básico",
        "available_pfpb": True,
        "pfpb_free": True,
        "available_reme_df": True,
        "dispensation_route": "FARMACIA_POPULAR",
        "requires_lme": False,
        "icd10_codes": ["I10", "I11"],
        "required_documents": [
            "Documento oficial com foto e CPF",
            "Receita médica válida (SUS ou particular) com CRM, carimbo e data",
        ],
        "prescription_validity_days": 180,
        "source_id": "PFPB_2024",
        "source_page": 14,
        "notes": (
            "100% gratuito no Programa Farmácia Popular (drogarias credenciadas) e "
            "disponível nas UBS do DF (REME-DF Cód. 90892 / F01 RENAME / F04 PFPB)."
        ),
    },
    {
        "medication_id": "MED-METFORMINA-500MG",
        "dcb_name": "cloridrato de metformina",
        "concentration": "500 mg",
        "pharmaceutical_form": "comprimido",
        "rename_component": "Básico",
        "available_pfpb": True,
        "pfpb_free": True,
        "available_reme_df": True,
        "dispensation_route": "FARMACIA_POPULAR",
        "requires_lme": False,
        "icd10_codes": ["E11"],
        "required_documents": [
            "Documento oficial com foto e CPF",
            "Receita médica válida (SUS ou particular) com CRM, carimbo e data",
        ],
        "prescription_validity_days": 180,
        "source_id": "PFPB_2024",
        "source_page": 11,
        "notes": (
            "100% gratuito na Farmácia Popular para Diabetes Mellitus e nas UBS "
            "(Consolidado F01 RENAME + F03 REME-DF + F04 PFPB)."
        ),
    },
    {
        "medication_id": "MED-METFORMINA-850MG",
        "dcb_name": "cloridrato de metformina",
        "concentration": "850 mg",
        "pharmaceutical_form": "comprimido",
        "rename_component": "Básico",
        "available_pfpb": True,
        "pfpb_free": True,
        "available_reme_df": True,
        "dispensation_route": "FARMACIA_POPULAR",
        "requires_lme": False,
        "icd10_codes": ["E11"],
        "required_documents": [
            "Documento oficial com foto e CPF",
            "Receita médica válida (SUS ou particular) com CRM, carimbo e data",
        ],
        "prescription_validity_days": 180,
        "source_id": "PFPB_2024",
        "source_page": 11,
        "notes": "100% gratuito na Farmácia Popular e UBS (Consolidado F01 + F03 + F04).",
    },
    {
        "medication_id": "MED-ENALAPRIL-10MG",
        "dcb_name": "maleato de enalapril",
        "concentration": "10 mg",
        "pharmaceutical_form": "comprimido",
        "rename_component": "Básico",
        "available_pfpb": True,
        "pfpb_free": True,
        "available_reme_df": True,
        "dispensation_route": "FARMACIA_POPULAR",
        "requires_lme": False,
        "icd10_codes": ["I10", "I50"],
        "required_documents": [
            "Documento oficial com foto e CPF",
            "Receita médica válida (SUS ou particular) com CRM, carimbo e data",
        ],
        "prescription_validity_days": 180,
        "source_id": "PFPB_2024",
        "source_page": 13,
        "notes": "100% gratuito na Farmácia Popular para hipertensão arterial (F01 + F03 + F04).",
    },
    {
        "medication_id": "MED-ATENOLOL-25MG",
        "dcb_name": "atenolol",
        "concentration": "25 mg",
        "pharmaceutical_form": "comprimido",
        "rename_component": "Básico",
        "available_pfpb": True,
        "pfpb_free": True,
        "available_reme_df": True,
        "dispensation_route": "FARMACIA_POPULAR",
        "requires_lme": False,
        "icd10_codes": ["I10", "I20"],
        "required_documents": [
            "Documento oficial com foto e CPF",
            "Receita médica válida (SUS ou particular) com CRM, carimbo e data",
        ],
        "prescription_validity_days": 180,
        "source_id": "PFPB_2024",
        "source_page": 12,
        "notes": "100% gratuito na Farmácia Popular e UBS (Consolidado F01 + F03 + F04).",
    },
    {
        "medication_id": "MED-HIDROCLOROTIAZIDA-25MG",
        "dcb_name": "hidroclorotiazida",
        "concentration": "25 mg",
        "pharmaceutical_form": "comprimido",
        "rename_component": "Básico",
        "available_pfpb": True,
        "pfpb_free": True,
        "available_reme_df": True,
        "dispensation_route": "FARMACIA_POPULAR",
        "requires_lme": False,
        "icd10_codes": ["I10"],
        "required_documents": [
            "Documento oficial com foto e CPF",
            "Receita médica válida (SUS ou particular) com CRM, carimbo e data",
        ],
        "prescription_validity_days": 180,
        "source_id": "PFPB_2024",
        "source_page": 13,
        "notes": "Diurético tiazídico 100% gratuito na Farmácia Popular e UBS (F01 + F03 + F04).",
    },
    {
        "medication_id": "MED-ANLODIPINO-5MG",
        "dcb_name": "besilato de anlodipino",
        "concentration": "5 mg",
        "pharmaceutical_form": "comprimido",
        "rename_component": "Básico",
        "available_pfpb": True,
        "pfpb_free": True,
        "available_reme_df": True,
        "dispensation_route": "FARMACIA_POPULAR",
        "requires_lme": False,
        "icd10_codes": ["I10"],
        "required_documents": [
            "Documento oficial com foto e CPF",
            "Receita médica válida (SUS ou particular) com CRM, carimbo e data",
        ],
        "prescription_validity_days": 180,
        "source_id": "PFPB_2024",
        "source_page": 12,
        "notes": "100% gratuito na Farmácia Popular (elenco de hipertensão) e UBS-DF.",
    },
    {
        "medication_id": "MED-SINVASTATINA-20MG",
        "dcb_name": "sinvastatina",
        "concentration": "20 mg",
        "pharmaceutical_form": "comprimido",
        "rename_component": "Básico",
        "available_pfpb": True,
        "pfpb_free": True,
        "available_reme_df": True,
        "dispensation_route": "FARMACIA_POPULAR",
        "requires_lme": False,
        "icd10_codes": ["E78.0", "E78.5"],
        "required_documents": [
            "Documento oficial com foto e CPF",
            "Receita médica válida (SUS ou particular) com CRM, carimbo e data",
        ],
        "prescription_validity_days": 180,
        "source_id": "PFPB_2024",
        "source_page": 16,
        "notes": "Dislipidemia: 100% gratuito no Programa Farmácia Popular (gratuidade expandida).",
    },
    {
        "medication_id": "MED-GLIBENCLAMIDA-5MG",
        "dcb_name": "glibenclamida",
        "concentration": "5 mg",
        "pharmaceutical_form": "comprimido",
        "rename_component": "Básico",
        "available_pfpb": True,
        "pfpb_free": True,
        "available_reme_df": True,
        "dispensation_route": "FARMACIA_POPULAR",
        "requires_lme": False,
        "icd10_codes": ["E11"],
        "required_documents": [
            "Documento oficial com foto e CPF",
            "Receita médica válida (SUS ou particular) com CRM, carimbo e data",
        ],
        "prescription_validity_days": 180,
        "source_id": "PFPB_2024",
        "source_page": 11,
        "notes": "Hipoglicemiante oral 100% gratuito na Farmácia Popular e UBS-DF.",
    },
    {
        "medication_id": "MED-INSULINA-NPH-100UI",
        "dcb_name": "insulina humana nph",
        "concentration": "100 UI/mL",
        "pharmaceutical_form": "suspensão injetável",
        "rename_component": "Básico",
        "available_pfpb": True,
        "pfpb_free": True,
        "available_reme_df": True,
        "dispensation_route": "FARMACIA_POPULAR",
        "requires_lme": False,
        "icd10_codes": ["E10", "E11"],
        "required_documents": [
            "Documento oficial com foto e CPF",
            "Receita médica válida (SUS ou particular) com CRM, carimbo e data",
        ],
        "prescription_validity_days": 180,
        "source_id": "PFPB_2024",
        "source_page": 11,
        "notes": "Insulina NPH 100% gratuita na Farmácia Popular e UBS-DF.",
    },
    {
        "medication_id": "MED-SALBUTAMOL-100MCG",
        "dcb_name": "sulfato de salbutamol",
        "concentration": "100 mcg/dose",
        "pharmaceutical_form": "aerossol oral",
        "rename_component": "Básico",
        "available_pfpb": True,
        "pfpb_free": True,
        "available_reme_df": True,
        "dispensation_route": "FARMACIA_POPULAR",
        "requires_lme": False,
        "icd10_codes": ["J45"],
        "required_documents": [
            "Documento oficial com foto e CPF",
            "Receita médica válida (SUS ou particular) com CRM, carimbo e data",
        ],
        "prescription_validity_days": 180,
        "source_id": "PFPB_2024",
        "source_page": 10,
        "notes": "100% gratuito na Farmácia Popular para tratamento de asma.",
    },
    {
        "medication_id": "MED-ALENDRONATO-70MG",
        "dcb_name": "alendronato de sódio",
        "concentration": "70 mg",
        "pharmaceutical_form": "comprimido",
        "rename_component": "Básico",
        "available_pfpb": True,
        "pfpb_free": True,
        "available_reme_df": True,
        "dispensation_route": "FARMACIA_POPULAR",
        "requires_lme": False,
        "icd10_codes": ["M80", "M81"],
        "required_documents": [
            "Documento oficial com foto e CPF",
            "Receita médica válida (SUS ou particular) com CRM, carimbo e data",
        ],
        "prescription_validity_days": 180,
        "source_id": "PFPB_2024",
        "source_page": 17,
        "notes": "Osteoporose: 100% gratuito na Farmácia Popular (gratuidade expandida).",
    },
    {
        "medication_id": "MED-DAPAGLIFLOZINA-10MG",
        "dcb_name": "dapagliflozina",
        "concentration": "10 mg",
        "pharmaceutical_form": "comprimido",
        "rename_component": "Especializado",
        "available_pfpb": True,
        "pfpb_free": True,
        "available_reme_df": True,
        "dispensation_route": "FARMACIA_POPULAR",
        "requires_lme": False,
        "icd10_codes": ["E11", "I50"],
        "required_documents": [
            "Documento oficial com foto e CPF",
            "Receita médica válida (SUS ou particular) com CRM, carimbo e data",
        ],
        "prescription_validity_days": 180,
        "source_id": "PFPB_2024",
        "source_page": 12,
        "notes": (
            "Gratuidade na Farmácia Popular para DM2 associada a doença cardiovascular "
            "(>= 65 anos) ou via CEAF."
        ),
    },
    {
        "medication_id": "MED-OMEPRAZOL-20MG",
        "dcb_name": "omeprazol",
        "concentration": "20 mg",
        "pharmaceutical_form": "cápsula",
        "rename_component": "Básico",
        "available_pfpb": False,
        "pfpb_free": False,
        "available_reme_df": True,
        "dispensation_route": "UBS_ATENCAO_PRIMARIA",
        "requires_lme": False,
        "icd10_codes": ["K21", "K25", "K29"],
        "required_documents": [
            "Cartão Nacional de Saúde (CNS / Cartão SUS)",
            "Documento oficial com foto e CPF",
            "Receita médica válida em duas vias (SUS ou particular)",
        ],
        "prescription_validity_days": 180,
        "source_id": "RENAME_2024",
        "source_page": 48,
        "notes": (
            "Não consta na Farmácia Popular. Retirada gratuita exclusivamente na Farmácia "
            "da UBS de referência (REME-DF: UBS farmácia ambulatorial)."
        ),
    },
    {
        "medication_id": "MED-LEVOTIROXINA-50MCG",
        "dcb_name": "levotiroxina sódica",
        "concentration": "50 mcg",
        "pharmaceutical_form": "comprimido",
        "rename_component": "Básico",
        "available_pfpb": False,
        "pfpb_free": False,
        "available_reme_df": True,
        "dispensation_route": "UBS_ATENCAO_PRIMARIA",
        "requires_lme": False,
        "icd10_codes": ["E03.9"],
        "required_documents": [
            "Cartão Nacional de Saúde (CNS / Cartão SUS)",
            "Documento oficial com foto e CPF",
            "Receita médica válida em duas vias (SUS ou particular)",
        ],
        "prescription_validity_days": 180,
        "source_id": "RENAME_2024",
        "source_page": 44,
        "notes": "Componente Básico (RENAME 2024 e REME-DF). Retirada gratuita nas UBS da SES-DF.",
    },
    {
        "medication_id": "MED-AMOXICILINA-500MG",
        "dcb_name": "amoxicilina",
        "concentration": "500 mg",
        "pharmaceutical_form": "cápsula",
        "rename_component": "Básico",
        "available_pfpb": False,
        "pfpb_free": False,
        "available_reme_df": True,
        "dispensation_route": "UBS_ATENCAO_PRIMARIA",
        "requires_lme": False,
        "icd10_codes": ["J01", "J02", "J03"],
        "required_documents": [
            "Cartão Nacional de Saúde (CNS)",
            "Documento com CPF",
            "Receita de controle antimicrobiano em 2 vias (validade de 10 dias)",
        ],
        "prescription_validity_days": 10,
        "source_id": "RENAME_2024",
        "source_page": 32,
        "notes": (
            "Antimicrobiano do Componente Básico. Receita válida por 10 dias com retenção "
            "da 2ª via na UBS."
        ),
    },
    {
        "medication_id": "MED-FLUOXETINA-20MG",
        "dcb_name": "cloridrato de fluoxetina",
        "concentration": "20 mg",
        "pharmaceutical_form": "cápsula",
        "rename_component": "Básico",
        "available_pfpb": False,
        "pfpb_free": False,
        "available_reme_df": True,
        "dispensation_route": "UBS_ATENCAO_PRIMARIA",
        "requires_lme": False,
        "icd10_codes": ["F32", "F33", "F41"],
        "required_documents": [
            "Cartão Nacional de Saúde (CNS) e CPF",
            "Receita de Controle Especial (Branca em 2 vias - Portaria 344/98, validade 30 dias)",
        ],
        "prescription_validity_days": 30,
        "source_id": "REME_DF_2024",
        "source_page": 29,
        "notes": (
            "Psicotrópico (Lista C1). Retirada gratuita na farmácia da UBS de referência "
            "para controle especial com retenção de via (validade 30 dias)."
        ),
    },
    {
        "medication_id": "MED-CARBAMAZEPINA-200MG",
        "dcb_name": "carbamazepina",
        "concentration": "200 mg",
        "pharmaceutical_form": "comprimido",
        "rename_component": "Básico",
        "available_pfpb": False,
        "pfpb_free": False,
        "available_reme_df": True,
        "dispensation_route": "UBS_ATENCAO_PRIMARIA",
        "requires_lme": False,
        "icd10_codes": ["G40", "F31"],
        "required_documents": [
            "Cartão Nacional de Saúde (CNS) e CPF",
            "Receita de Controle Especial em 2 vias (Portaria 344/98, validade 30 dias)",
        ],
        "prescription_validity_days": 30,
        "source_id": "REME_DF_2024",
        "source_page": 27,
        "notes": "Anticonvulsivante do Componente Básico na REME-DF. Dispensado na UBS.",
    },
    {
        "medication_id": "MED-ADALIMUMABE-40MG",
        "dcb_name": "adalimumabe",
        "concentration": "40 mg",
        "pharmaceutical_form": "solução injetável",
        "rename_component": "Especializado",
        "available_pfpb": False,
        "pfpb_free": False,
        "available_reme_df": True,
        "dispensation_route": "ALTO_CUSTO_CEAF",
        "requires_lme": True,
        "icd10_codes": ["M05.0", "M06.0", "M45", "K50.0"],
        "required_documents": [
            (
                "Laudo de Solicitação, Avaliação e Autorização de Medicamento(s) (LME) "
                "preenchido pelo médico"
            ),
            "Receita médica em duas vias com DCB (nome genérico)",
            "Cartão Nacional de Saúde (CNS) e Documento com CPF",
            "Comprovante de residência no Distrito Federal",
            "Exames laboratoriais/imagem exigidos pelo PCDT da doença (CID-10)",
        ],
        "prescription_validity_days": 90,
        "source_id": "RENAME_2024",
        "source_page": 112,
        "notes": (
            "Componente Especializado (CEAF). Exige abertura de processo com LME (renovação "
            "trimestral) nas unidades da Farmácia de Alto Custo do DF (102 Sul, Ceilândia ou Gama)."
        ),
    },
    {
        "medication_id": "MED-ATORVASTATINA-40MG",
        "dcb_name": "atorvastatina cálcica",
        "concentration": "40 mg",
        "pharmaceutical_form": "comprimido",
        "rename_component": "Especializado",
        "available_pfpb": False,
        "pfpb_free": False,
        "available_reme_df": True,
        "dispensation_route": "ALTO_CUSTO_CEAF",
        "requires_lme": True,
        "icd10_codes": ["E78.0", "E78.2"],
        "required_documents": [
            (
                "Laudo de Solicitação, Avaliação e Autorização de Medicamento(s) (LME) "
                "preenchido pelo médico"
            ),
            "Receita médica em duas vias com DCB (nome genérico)",
            "Cartão Nacional de Saúde (CNS) e Documento com CPF",
            "Comprovante de residência no Distrito Federal",
            "Exames laboratoriais/imagem exigidos pelo PCDT da doença (CID-10)",
        ],
        "prescription_validity_days": 90,
        "source_id": "RENAME_2024",
        "source_page": 118,
        "notes": (
            "Componente Especializado (CEAF). Exige LME e perfil lipídico conforme PCDT de "
            "Dislipidemia."
        ),
    },
    {
        "medication_id": "MED-SACUBITRIL-VALSARTANA-97-103MG",
        "dcb_name": "sacubitril valsartana sódica hidratada",
        "concentration": "97 mg + 103 mg",
        "pharmaceutical_form": "comprimido",
        "rename_component": "Especializado",
        "available_pfpb": False,
        "pfpb_free": False,
        "available_reme_df": True,
        "dispensation_route": "ALTO_CUSTO_CEAF",
        "requires_lme": True,
        "icd10_codes": ["I50.0"],
        "required_documents": [
            (
                "Laudo de Solicitação, Avaliação e Autorização de Medicamento(s) (LME) "
                "preenchido pelo médico"
            ),
            "Receita médica em duas vias com DCB (nome genérico)",
            "Cartão Nacional de Saúde (CNS) e Documento com CPF",
            "Comprovante de residência no Distrito Federal",
            "Exames laboratoriais/imagem exigidos pelo PCDT da doença (CID-10)",
        ],
        "prescription_validity_days": 90,
        "source_id": "RENAME_2024",
        "source_page": 141,
        "notes": (
            "Insuficiência Cardíaca com fração de ejeção reduzida (FEVE <= 35%). Dispensação "
            "via Farmácia de Alto Custo mediante LME e Ecocardiograma."
        ),
    },
    {
        "medication_id": "MED-FORMOTEROL-BUDESONIDA-12-400MCG",
        "dcb_name": "fumarato de formoterol di-hidratado + budesonida",
        "concentration": "12 mcg + 400 mcg",
        "pharmaceutical_form": "cápsula inalante",
        "rename_component": "Especializado",
        "available_pfpb": False,
        "pfpb_free": False,
        "available_reme_df": True,
        "dispensation_route": "ALTO_CUSTO_CEAF",
        "requires_lme": True,
        "icd10_codes": ["J45.0", "J44.8"],
        "required_documents": [
            (
                "Laudo de Solicitação, Avaliação e Autorização de Medicamento(s) (LME) "
                "preenchido pelo médico"
            ),
            "Receita médica em duas vias com DCB (nome genérico)",
            "Cartão Nacional de Saúde (CNS) e Documento com CPF",
            "Comprovante de residência no Distrito Federal",
            "Exames laboratoriais/imagem exigidos pelo PCDT da doença (CID-10)",
        ],
        "prescription_validity_days": 90,
        "source_id": "RENAME_2024",
        "source_page": 125,
        "notes": (
            "Componente Especializado para Asma Persistente Moderada/Grave e DPOC. Exige LME "
            "e espirometria."
        ),
    },
    {
        "medication_id": "MED-QUETIAPINA-25MG",
        "dcb_name": "hemifumarato de quetiapina",
        "concentration": "25 mg",
        "pharmaceutical_form": "comprimido",
        "rename_component": "Especializado",
        "available_pfpb": False,
        "pfpb_free": False,
        "available_reme_df": True,
        "dispensation_route": "ALTO_CUSTO_CEAF",
        "requires_lme": True,
        "icd10_codes": ["F20.0", "F31.3"],
        "required_documents": [
            (
                "Laudo de Solicitação, Avaliação e Autorização de Medicamento(s) (LME) "
                "preenchido pelo médico"
            ),
            "Receita médica em duas vias com DCB (nome genérico)",
            "Cartão Nacional de Saúde (CNS) e Documento com CPF",
            "Comprovante de residência no Distrito Federal",
            "Exames laboratoriais/imagem exigidos pelo PCDT da doença (CID-10)",
        ],
        "prescription_validity_days": 90,
        "source_id": "RENAME_2024",
        "source_page": 130,
        "notes": (
            "Componente Especializado (CEAF). Exige LME + Receita de Controle Especial em "
            "duas vias."
        ),
    },
    {
        "medication_id": "MED-INSULINA-GLARGINA-100UI",
        "dcb_name": "insulina glargina",
        "concentration": "100 UI/mL",
        "pharmaceutical_form": "solução injetável",
        "rename_component": "Especializado",
        "available_pfpb": False,
        "pfpb_free": False,
        "available_reme_df": True,
        "dispensation_route": "ALTO_CUSTO_CEAF",
        "requires_lme": True,
        "icd10_codes": ["E10"],
        "required_documents": [
            (
                "Laudo de Solicitação, Avaliação e Autorização de Medicamento(s) (LME) "
                "preenchido pelo médico"
            ),
            "Receita médica em duas vias com DCB (nome genérico)",
            "Cartão Nacional de Saúde (CNS) e Documento com CPF",
            "Comprovante de residência no Distrito Federal",
            "Exames laboratoriais/imagem exigidos pelo PCDT da doença (CID-10)",
        ],
        "prescription_validity_days": 90,
        "source_id": "REME_DF_2024",
        "source_page": 64,
        "notes": (
            "Elenco Especializado SES-DF para Diabetes Mellitus Tipo 1 conforme protocolo "
            "clínico distrital."
        ),
    },
]

CURATED_COMPLEMENTARY_NORMATIVE_CHUNKS: list[dict[str, Any]] = [
    {
        "chunk_id": "CHK-COMP-PFPB-003",
        "source_id": "PFPB_C01_2026",
        "document_title": (
            "Diretrizes Operacionais do Programa Farmácia Popular e Dignidade Menstrual (Fonte C01)"
        ),
        "section": (
            "Seção 2 — Fraldas Geriátricas, Dignidade Menstrual e Procuração com "
            "Assinatura Eletrônica"
        ),
        "page_number": 2,
        "text": (
            "Pelo Programa Farmácia Popular do Brasil (Aqui Tem Farmácia Popular), além do "
            "elenco de medicamentos gratuitos para hipertensão, diabetes, asma, osteoporose, "
            "dislipidemia, rinite, doença de Parkinson, glaucoma e anticoncepção, são "
            "disponibilizadas fraldas geriátricas (para pessoas com idade igual ou superior a "
            "60 anos ou pessoas com deficiência, mediante prescrição ou laudo médico indicando "
            "incontinência) e absorventes higiênicos gratuitos pelo Programa Dignidade "
            "Menstrual. Para pacientes acamados ou impossibilitados de comparecer, é aceita "
            "procuração particular com firma reconhecida ou assinatura eletrônica qualificada "
            "(Gov.br), acompanhada dos documentos oficiais com CPF do titular e do "
            "representante legal."
        ),
        "dcb_mentions": [
            "fralda geriátrica",
            "absorvente higiênico",
        ],
        "route_category": "FARMACIA_POPULAR",
    },
    {
        "chunk_id": "CHK-COMP-UBS-002",
        "source_id": "SES_DF_C02_2026",
        "document_title": (
            "Normas das Farmácias das Unidades Básicas de Saúde (UBS) — SES-DF (Fonte C02)"
        ),
        "section": (
            "Seção 3 — Entrega de Controlados para Maiores de 18 Anos e Aplicações "
            "Injetáveis na APS"
        ),
        "page_number": 2,
        "text": (
            "Nas Farmácias das Unidades Básicas de Saúde (UBS) da Secretaria de Saúde do "
            "Distrito Federal (SES-DF), medicamentos sujeitos a controle especial (Portaria "
            "SVS/MS nº 344/1998) somente podem ser dispensados e entregues a cidadãos maiores "
            "de 18 anos, mediante apresentação de documento oficial de identificação com foto, "
            "Cartão SUS (CNS) e Receita de Controle Especial em duas vias válida por 30 dias. "
            "Medicamentos injetáveis padronizados na Atenção Primária à Saúde (como "
            "benzilpenicilina benzatina e acetato de medroxiprogesterona) são dispensados e "
            "aplicados na sala de procedimentos da própria UBS pela equipe de enfermagem."
        ),
        "dcb_mentions": [
            "benzilpenicilina benzatina",
            "acetato de medroxiprogesterona",
        ],
        "route_category": "UBS_ATENCAO_PRIMARIA",
    },
    {
        "chunk_id": "CHK-COMP-SEC-001",
        "source_id": "SES_DF_C03_2026",
        "document_title": (
            "Guia das Farmácias da Atenção Secundária SES-DF: Policlínicas, CAPS, HUB e "
            "CEDIN (Fonte C03)"
        ),
        "section": "Seção 1 — Documentação e Polos de Dispensação Especializada Ambulatorial no DF",
        "page_number": 1,
        "text": (
            "No Distrito Federal, medicamentos de acompanhamento ambulatorial específico da "
            "Atenção Secundária e Estratégica (incluindo antirretrovirais para HIV/AIDS como "
            "abacavir, dolutegravir e lamivudina, medicamentos de saúde mental em "
            "acompanhamento intensivo e esquemas especiais de infectologia) são dispensados "
            "nas Farmácias das Policlínicas (Ceilândia, Gama, Planaltina e Taguatinga), nos "
            "Centros de Atenção Psicossocial (CAPS), na Farmácia Escola do Hospital "
            "Universitário de Brasília (HUB-UnB) e no Centro Especializado em Doenças "
            "Infecciosas (CEDIN, antigo Hospital Dia na Asa Sul). O acesso exige receita "
            "médica válida e legível em 2 vias, documento oficial com foto, CPF, Cartão SUS "
            "(CNS) e formulário específico do programa quando exigido em protocolo."
        ),
        "dcb_mentions": [
            "abacavir",
            "dolutegravir sódico",
            "lamivudina",
        ],
        "route_category": "UBS_ATENCAO_PRIMARIA",
    },
    {
        "chunk_id": "CHK-COMP-CEAF-002",
        "source_id": "SES_DF_C04_2026",
        "document_title": (
            "Regionalização do Componente Especializado (Farmácia de Alto Custo) — "
            "SES-DF (Fonte C04)"
        ),
        "section": (
            "Seção 2 — Regiões Administrativas Vinculadas às Unidades Asa Sul, Ceilândia e Gama"
        ),
        "page_number": 3,
        "text": (
            "O atendimento das três unidades da Farmácia do Componente Especializado (Alto "
            "Custo / CEAF-DF) é regionalizado conforme a Região Administrativa de residência "
            "do paciente: 1) Unidade Asa Sul (Estação 102 Sul do Metrô): atende moradores de "
            "Asa Sul, Asa Norte, Cruzeiro, Sudoeste, Lago Sul, Lago Norte, Varjão, Guará, "
            "Estrutural (SCIA), Núcleo Bandeirante, Candangolândia, Riacho Fundo I e II, "
            "Park Way, Paranoá, Itapoã, São Sebastião, Jardim Botânico, Jardins Mangueiral, "
            "Sobradinho I e II, Planaltina e Fercal; 2) Unidade Ceilândia (Praça do Cidadão, "
            "EQNN 18/20): atende moradores de Ceilândia, Sol Nascente/Pôr do Sol, Taguatinga, "
            "Samambaia, Águas Claras, Vicente Pires, Arniqueira e Brazlândia; 3) Unidade Gama "
            "(Praça 1, Setor Leste): atende moradores do Gama, Santa Maria e Recanto das Emas."
        ),
        "dcb_mentions": [],
        "route_category": "ALTO_CUSTO_CEAF",
    },
    {
        "chunk_id": "CHK-COMP-INFOSAUDE-001",
        "source_id": "INFOSAUDE_DF_C06_C07",
        "document_title": (
            "Painel InfoSaúde DF — Transparência de Estoque de Medicamentos SES-DF "
            "(Fontes C06 e C07)"
        ),
        "section": "Consulta Pública de Estoque nas Farmácias de UBS e Farmácias de Alto Custo",
        "page_number": 1,
        "text": (
            "Antes de se deslocar à farmácia pública, o cidadão do Distrito Federal pode "
            "consultar gratuitamente a disponibilidade em tempo real dos medicamentos "
            "padronizados por meio do portal InfoSaúde DF (info.saude.df.gov.br), nos painéis "
            "'Farmácias Ambulatoriais' (estoque das UBS e Policlínicas) e 'Farmácias de Alto "
            "Custo' (estoque das unidades Asa Sul, Ceilândia e Gama do Componente "
            "Especializado - CEAF). O painel informa se o item encontra-se 'COM ESTOQUE', "
            "'SEM ESTOQUE' ou em fase de 'AQUISIÇÃO / PROGRAMADO' na respectiva unidade."
        ),
        "dcb_mentions": [],
        "route_category": "GERAL",
    },
    {
        "chunk_id": "CHK-COMP-LME-001",
        "source_id": "MS_CEAF_C09_C10",
        "document_title": (
            "Perguntas Frequentes e Manual do LME no Componente Especializado — MS "
            "(Fontes C09 e C10)"
        ),
        "section": (
            "Regras de Preenchimento do LME, Declaração Autorizadora e Renovação da Continuidade"
        ),
        "page_number": 4,
        "text": (
            "No Componente Especializado da Assistência Farmacêutica (CEAF), o Laudo para "
            "Solicitação, Avaliação e Autorização de Medicamentos (LME) possui campos de "
            "preenchimento exclusivo e obrigatório do médico assistente: identificação e CNS "
            "do médico, CID-10, anamnese clínica, indicação de tratamento prévio, atestado de "
            "incapacidade (quando aplicável), assinatura e carimbo. O LME tem validade de 90 "
            "dias para solicitação. Caso o paciente deseje designar um terceiro para retirar "
            "o medicamento de Alto Custo, deve apresentar a Declaração Autorizadora assinada, "
            "acompanhada de cópia do documento de identidade, endereço e telefone do "
            "representante."
        ),
        "dcb_mentions": [],
        "route_category": "ALTO_CUSTO_CEAF",
    },
    {
        "chunk_id": "CHK-COMP-CESAF-001",
        "source_id": "MS_CESAF_C14",
        "document_title": (
            "Diretrizes do Componente Estratégico da Assistência Farmacêutica — CESAF (Fonte C14)"
        ),
        "section": (
            "Acesso Equitativo a Medicamentos para Endemias, Tuberculose, Hanseníase e Tabagismo"
        ),
        "page_number": 1,
        "text": (
            "O Componente Estratégico da Assistência Farmacêutica (CESAF) garante o acesso "
            "gratuito no SUS a medicamentos e insumos destinados à prevenção, diagnóstico e "
            "tratamento de doenças de perfil endêmico e importância epidemiológica, incluindo "
            "tuberculose (rifampicina, isoniazida, pirazinamida, etambutol), hanseníase "
            "(dapsona, clofazimina), malária, leishmaniose, doença de Chagas, infecções "
            "sexualmente transmissíveis (HIV/AIDS e hepatites virais) e controle do tabagismo "
            "(adesivo e goma de nicotina, cloridrato de bupropiona). No DF, a dispensação "
            "ocorre nas UBS de referência, Policlínicas e no CEDIN."
        ),
        "dcb_mentions": [
            "rifampicina",
            "isoniazida",
            "dapsona",
            "nicotina",
        ],
        "route_category": "UBS_ATENCAO_PRIMARIA",
    },
]


@dataclass(frozen=True)
class SchemaDriftReport:
    """Relatório de validação de contrato e detecção de Schema Drift na camada Silver/Gold."""

    total_records: int
    valid_records: int
    unexpected_fields: list[str]
    missing_fields: list[str]
    errors: list[str]

    @property
    def is_valid(self) -> bool:
        return not (self.errors or self.missing_fields or self.unexpected_fields)


def remover_acentos(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def normalizar_concentracao(conc: str) -> str:
    """Normaliza espaçamento entre número e unidade (ex: '50mg' -> '50 mg')."""
    limpo = conc.strip().rstrip("*").strip()
    if not limpo or limpo == "-":
        return "Padronizada"
    # Adiciona espaço entre dígito e unidade comum quando colados (50mg -> 50 mg)
    limpo = re.sub(
        r"(\d)\s*(mg/ml|mcg/dose|mcg/ml|ui/ml|mg/g|mcg|mg|ui|ml|g)\b",
        lambda m: f"{m.group(1)} {m.group(2)}",
        limpo,
        flags=re.IGNORECASE,
    )
    # Padroniza UI/mL e mL
    limpo = re.sub(r"\bui/ml\b", "UI/mL", limpo, flags=re.IGNORECASE)
    limpo = re.sub(r"\bmg/ml\b", "mg/mL", limpo, flags=re.IGNORECASE)
    limpo = re.sub(r"\bmcg/ml\b", "mcg/mL", limpo, flags=re.IGNORECASE)
    limpo = re.sub(r"\s+", " ", limpo)
    return limpo


def chave_normalizada_concentracao(conc: str) -> str:
    """Gera chave canônica de concentração sem espaços redundantes para fusão F01/F03/F04."""
    norm = remover_acentos(normalizar_concentracao(conc))
    return re.sub(r"\s+", "", norm)


def validate_occurrence_drift(occurrences: list[dict[str, Any]]) -> SchemaDriftReport:
    """Valida se as ocorrências curadas respeitam o contrato esperado sem schema drift."""
    unexpected: set[str] = set()
    missing: set[str] = set()
    errors: list[str] = []
    valid_count = 0
    occurrence_ids: set[str] = set()
    evidence_ids: set[str] = set()
    if not occurrences:
        errors.append("Corpus vazio")

    for idx, row in enumerate(occurrences):
        keys = set(row.keys())
        extra = keys - EXPECTED_OCCURRENCE_KEYS - OPTIONAL_OCCURRENCE_KEYS
        absent = EXPECTED_OCCURRENCE_KEYS - keys
        if extra:
            unexpected.update(extra)
        if absent:
            missing.update(absent)

        src = row.get("source")
        src_id = src.get("source_id") if isinstance(src, dict) else None
        if src_id not in VALID_SOURCES:
            errors.append(f"Row {idx}: invalid source_id {src_id!r}")
            continue

        ing = str(row.get("active_ingredient") or "").strip()
        if not ing or ing.startswith("[linha"):
            errors.append(f"Row {idx}: invalid active_ingredient {ing!r}")
            continue

        if row.get("review_status") != "approved":
            errors.append(f"Row {idx}: unapproved review_status {row.get('review_status')!r}")
            continue

        occurrence_id = row.get("occurrence_id")
        evidence_id = row.get("evidence_id")
        if (
            not isinstance(occurrence_id, str)
            or not occurrence_id
            or occurrence_id in occurrence_ids
            or not isinstance(evidence_id, str)
            or not evidence_id
            or evidence_id in evidence_ids
        ):
            errors.append(f"Row {idx}: ID ausente ou repetido")
            continue
        item_type = row.get("item_type")
        if not (
            (item_type == "medicine" and row.get("medicine_id") and not row.get("supply_id"))
            or (item_type == "supply" and row.get("supply_id") and not row.get("medicine_id"))
        ):
            errors.append(f"Row {idx}: tipo de item ou vínculo inválido")
            continue
        occurrence_ids.add(occurrence_id)
        evidence_ids.add(evidence_id)
        valid_count += 1

    return SchemaDriftReport(
        total_records=len(occurrences),
        valid_records=valid_count,
        unexpected_fields=sorted(unexpected),
        missing_fields=sorted(missing),
        errors=errors,
    )


def classificar_apresentacao_consolidada(
    dcb_name: str,
    f01_components: set[str],
    f03_channels: set[str],
    in_f04: bool,
) -> tuple[str, str, bool, int, list[str]]:
    """Retorna (componente, rota, exige_lme, dias_validade, documentos_exigidos)."""
    dcb_norm = remover_acentos(dcb_name)
    channels_joined = " | ".join(sorted(f03_channels)).lower()
    channels_norm = remover_acentos(channels_joined)

    is_ceaf = "Especializado" in f01_components or "componente especializado" in channels_norm

    if is_ceaf:
        comp_str = "Especializado"
    elif "Estratégico" in f01_components:
        comp_str = "Estratégico"
    elif "Hospitalar" in f01_components:
        comp_str = "Hospitalar"
    else:
        comp_str = "Básico"

    if in_f04:
        return (
            comp_str,
            "FARMACIA_POPULAR",
            False,
            180,
            [
                "Documento oficial com foto e CPF",
                "Receita médica válida (SUS ou particular) com CRM, carimbo e data",
            ],
        )

    if is_ceaf:
        return (
            "Especializado",
            "ALTO_CUSTO_CEAF",
            True,
            90,
            [
                (
                    "Laudo de Solicitação, Avaliação e Autorização de Medicamento(s) (LME) "
                    "preenchido pelo médico"
                ),
                "Receita médica em duas vias com DCB (nome genérico)",
                "Cartão Nacional de Saúde (CNS) e Documento com CPF",
                "Comprovante de residência no Distrito Federal",
                "Exames laboratoriais/imagem exigidos pelo PCDT da doença (CID-10)",
            ],
        )

    # Verifica se é exclusivamente hospitalar
    has_ambulatory = any(
        termo in channels_norm
        for termo in ("ubs", "policlinica", "farmacia escola", "cedin", "caps", "tabagismo")
    )
    is_hospital_only = (
        "Hospitalar" in f01_components
        and "Básico" not in f01_components
        and "Estratégico" not in f01_components
        and not has_ambulatory
    ) or (
        bool(f03_channels)
        and not has_ambulatory
        and all(
            any(
                h in remover_acentos(ch.lower())
                for h in ("uso hospitalar", "samu", "hemocentro", "hbdf", "oncologica")
            )
            for ch in f03_channels
        )
    )

    if is_hospital_only:
        return (
            "Hospitalar",
            "HOSPITALAR",
            False,
            30,
            [
                "Prescrição hospitalar interna / Prontuário eletrônico SES-DF",
                "Cartão Nacional de Saúde (CNS) e Documento com foto",
            ],
        )

    # Verifica regras de validade estrita: Antimicrobianos (10 dias) ou Controle Especial (30 dias)
    is_controlled = "controle especial" in channels_norm or any(
        kw in dcb_norm for kw in CONTROLLED_344_KEYWORDS
    )
    is_antimicrobial = any(kw in dcb_norm for kw in ANTIMICROBIAL_KEYWORDS)

    if is_antimicrobial:
        return (
            comp_str,
            "UBS_ATENCAO_PRIMARIA",
            False,
            10,
            [
                "Cartão Nacional de Saúde (CNS)",
                "Documento oficial com foto e CPF",
                "Receita de controle antimicrobiano em 2 vias (validade estrita de 10 dias)",
            ],
        )

    if is_controlled:
        return (
            comp_str,
            "UBS_ATENCAO_PRIMARIA",
            False,
            30,
            [
                "Cartão Nacional de Saúde (CNS) e CPF",
                "Receita de Controle Especial em 2 vias (Portaria 344/98, validade 30 dias)",
            ],
        )

    return (
        comp_str,
        "UBS_ATENCAO_PRIMARIA",
        False,
        180,
        [
            "Cartão Nacional de Saúde (CNS / Cartão SUS)",
            "Documento oficial com foto e CPF",
            "Receita médica válida em duas vias (SUS ou particular)",
        ],
    )


def consolidar_catalogo_medicamentos(
    occurrences: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Funde F01 (RENAME), F03 (REME-DF) e F04 (Farmácia Popular) preservando os 24 prioritários."""
    drift = validate_occurrence_drift(occurrences)
    if not drift.is_valid:
        raise ValueError(
            f"Schema drift: ausentes={drift.missing_fields}, extras={drift.unexpected_fields}, "
            f"erros={drift.errors[:5]}"
        )

    # Mantém apresentações de liberação distinta em grupos separados.
    grupos: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for occ in occurrences:
        # Os insumos F01 ficam na evidência de presença, fora do roteiro de medicamentos.
        if occ["item_type"] == "supply" and occ["source"]["source_id"] != "F04":
            continue
        dcb_raw = str(occ["active_ingredient"]).strip().rstrip("*").strip().lower()
        conc_raw = normalizar_concentracao(str(occ.get("strength") or ""))
        form_raw = str(occ.get("form") or "").strip().lower()
        if form_raw in {"", "-"}:
            form_raw = "forma não informada"

        key = (
            remover_acentos(dcb_raw),
            chave_normalizada_concentracao(conc_raw),
            remover_acentos(form_raw),
            remover_acentos(str(occ["release_characteristic"] or "")),
        )
        grupos.setdefault(key, []).append(occ)

    # Indexa os 24 itens prioritários para evitar duplicatas exatas
    chaves_prioritarias: set[tuple[str, str, str, str]] = set()
    catalogo_final: list[dict[str, Any]] = []
    for p_item in PRIORITY_24_ITEMS:
        p_key = (
            remover_acentos(p_item["dcb_name"]),
            chave_normalizada_concentracao(p_item["concentration"]),
            remover_acentos(p_item["pharmaceutical_form"]),
            "",
        )
        chaves_prioritarias.add(p_key)
        prioritario = dict(p_item)
        if correspondencias := grupos.get(p_key):
            prioritario["occurrence_ids"] = [row["occurrence_id"] for row in correspondencias]
            prioritario["df_channels"] = sorted(
                {
                    row["channel"]
                    for row in correspondencias
                    if row["source"]["source_id"] == "F03" and row["channel"]
                }
            )
        catalogo_final.append(prioritario)

    contador = 1
    for key in sorted(grupos.keys()):
        if key in chaves_prioritarias:
            continue
        occs = grupos[key]
        primeiro = occs[0]
        dcb_name = str(primeiro["active_ingredient"]).strip().rstrip("*").strip().lower()
        conc = normalizar_concentracao(str(primeiro.get("strength") or ""))
        form = str(primeiro.get("form") or "").strip().lower()
        if not form or form == "-":
            form = "forma não informada"

        fontes_presentes = sorted({str(o["source"]["source_id"]) for o in occs})
        f01_comps = {
            str(o["component"]).strip()
            for o in occs
            if o["source"]["source_id"] == "F01" and o.get("component")
        }
        f03_channels = {
            str(o["channel"]).strip()
            for o in occs
            if o["source"]["source_id"] == "F03" and o.get("channel")
        }
        f03_codes = sorted(
            {
                str(o["source_code"]).strip()
                for o in occs
                if o["source"]["source_id"] == "F03" and o.get("source_code")
            }
        )
        in_f04 = "F04" in fontes_presentes
        in_f03 = "F03" in fontes_presentes

        comp_str, route, req_lme, val_days, req_docs = classificar_apresentacao_consolidada(
            dcb_name=dcb_name,
            f01_components=f01_comps,
            f03_channels=f03_channels,
            in_f04=in_f04,
        )

        is_pfpb = route == "FARMACIA_POPULAR"
        # A página acompanha a fonte escolhida. F03 embasa o canal local e F04 o PFPB.
        fonte_preferida = "F04" if in_f04 else "F03" if in_f03 else "F01"
        fonte = next(o["source"] for o in occs if o["source"]["source_id"] == fonte_preferida)
        src_id = {"F01": "RENAME_2024", "F03": "REME_DF_2026", "F04": "PFPB_2026"}[fonte_preferida]
        src_page = int(fonte["page"])

        partes_notas: list[str] = [f"Fontes consolidadas: {', '.join(fontes_presentes)}."]
        if f03_codes:
            partes_notas.append(f"Cód. SES-DF: {', '.join(f03_codes)}.")
        if f03_channels:
            canal_resumo = "; ".join(sorted(f03_channels))
            partes_notas.append(f"Local REME-DF: {canal_resumo}.")

        catalogo_final.append(
            {
                "medication_id": f"MED-SUS-{contador:04d}",
                "dcb_name": dcb_name,
                "concentration": conc,
                "pharmaceutical_form": form,
                "rename_component": comp_str,
                "available_pfpb": is_pfpb,
                "pfpb_free": is_pfpb,
                "available_reme_df": in_f03,
                "dispensation_route": route,
                "requires_lme": req_lme,
                "required_documents": req_docs,
                "prescription_validity_days": val_days,
                "source_id": src_id,
                "source_page": src_page,
                "occurrence_ids": [o["occurrence_id"] for o in occs],
                "item_type": primeiro["item_type"],
                "release_characteristic": primeiro["release_characteristic"],
                "df_channels": sorted(f03_channels),
                "notes": " ".join(partes_notas),
            }
        )
        contador += 1

    return catalogo_final


def consolidar_normative_chunks(
    caminho_chunks_atuais: Path,
) -> list[dict[str, Any]]:
    """Preserva os 13 chunks normativos base e incorpora os 7 chunks complementares curados."""
    chunks_atuais: list[dict[str, Any]] = json.loads(
        caminho_chunks_atuais.read_text(encoding="utf-8")
    )
    # Mantém apenas os 13 chunks originais (evita duplicação em reexecuções idempotentes)
    ids_complementares = {c["chunk_id"] for c in CURATED_COMPLEMENTARY_NORMATIVE_CHUNKS}
    base_13 = [c for c in chunks_atuais if c["chunk_id"] not in ids_complementares]

    consolidados: list[dict[str, Any]] = []
    for c in base_13:
        item = dict(c)
        item["sha256"] = hashlib.sha256(str(item["text"]).encode("utf-8")).hexdigest()
        consolidados.append(item)

    for comp in CURATED_COMPLEMENTARY_NORMATIVE_CHUNKS:
        item = dict(comp)
        item["sha256"] = hashlib.sha256(str(item["text"]).encode("utf-8")).hexdigest()
        consolidados.append(item)

    return consolidados


def regenerar_unified_pdf_chunks(
    raiz: Path,
    catalogo_consolidado: list[dict[str, Any]],
    normative_chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Regenera unified_pdf_chunks.json 100% alinhado à base consolidada sem cortes de palavras."""
    total_apresentacoes = len(catalogo_consolidado)
    total_pfpb = sum(1 for m in catalogo_consolidado if m["available_pfpb"])
    total_ceaf = sum(
        1 for m in catalogo_consolidado if m["dispensation_route"] == "ALTO_CUSTO_CEAF"
    )
    total_ubs = sum(
        1 for m in catalogo_consolidado if m["dispensation_route"] == "UBS_ATENCAO_PRIMARIA"
    )

    cabecalho_catalogo = (
        "MINISTÉRIO DA SAÚDE & SECRETARIA DE SAÚDE DO DISTRITO FEDERAL (SES-DF) — "
        "CATÁLOGO CANÔNICO CONSOLIDADO DE MEDICAMENTOS DO SUS (F01 RENAME 2024 + "
        "F03 REME-DF 2026 + F04 FARMÁCIA POPULAR 2026). "
        f"Total de Apresentações Padronizadas e Auditadas: {total_apresentacoes} apresentações "
        f"({total_pfpb} Farmácia Popular, {total_ubs} Atenção Primária/Secundária DF, "
        f"{total_ceaf} Componente Especializado CEAF). "
    )

    # 1. Chunks do Catálogo Canônico Consolidado (por registro inteiro, sem cortar palavras)
    linhas_prioritarias: list[str] = []
    for m in catalogo_consolidado[:60]:
        pfpb_str = "SIM (100%)" if m["available_pfpb"] else "NÃO"
        lme_str = "SIM" if m["requires_lme"] else "NÃO"
        linhas_prioritarias.append(
            f"{m['dcb_name']} {m['concentration']} ({m['pharmaceutical_form']}) | "
            f"Componente: {m['rename_component']} | Rota: {m['dispensation_route']} | "
            f"PFPB Gratuito: {pfpb_str} | Exige LME: {lme_str} | "
            f"Validade Receita: {m['prescription_validity_days']} dias."
        )

    chunks_catalogo: list[dict[str, Any]] = []
    bloco_tamanho = 10
    for idx in range(0, len(linhas_prioritarias), bloco_tamanho):
        fatia = linhas_prioritarias[idx : idx + bloco_tamanho]
        seg_idx = idx // bloco_tamanho
        prefixo = (
            cabecalho_catalogo if seg_idx == 0 else "CATÁLOGO CONSOLIDADO SUS-DF (Continuação): "
        )
        conteudo = prefixo + " ".join(fatia)
        chunks_catalogo.append(
            {
                "chunk_id": f"CATALOGO_CANONICO_MEDICAMENTOS_SUS_p001_c{seg_idx:02d}",
                "source_pdf": "CATALOGO_CANONICO_MEDICAMENTOS_SUS.pdf",
                "category": "catalogo_canonico_sus",
                "page_number": 1,
                "segment_index": seg_idx,
                "char_count": len(conteudo),
                "content": conteudo,
                "review_status": "approved",
                "sha256": hashlib.sha256(conteudo.encode("utf-8")).hexdigest(),
                "metadata": {
                    "source_pdf": "CATALOGO_CANONICO_MEDICAMENTOS_SUS.pdf",
                    "category": "catalogo_canonico_sus",
                    "page_number": 1,
                    "document_stem": "CATALOGO_CANONICO_MEDICAMENTOS_SUS",
                    "total_consolidated_medications": total_apresentacoes,
                },
            }
        )

    # 2. Chunks Normativos Consolidados (F01, F03, F04, SISREG, HUB e C01-C14)
    chunks_normativos_pdf: list[dict[str, Any]] = []
    for seg_idx, nchk in enumerate(normative_chunks):
        src_id = str(nchk["source_id"])
        cat = (
            "complementares_curados"
            if str(nchk["chunk_id"]).startswith("CHK-COMP-")
            else "normativo_consolidado_sus_df"
        )
        conteudo_norm = f"{nchk['document_title']} — {nchk['section']}: {nchk['text']}"
        chunks_normativos_pdf.append(
            {
                "chunk_id": str(nchk["chunk_id"]),
                "source_pdf": f"{src_id}.pdf",
                "category": cat,
                "page_number": int(nchk["page_number"]),
                "segment_index": seg_idx,
                "char_count": len(conteudo_norm),
                "content": conteudo_norm,
                "review_status": "approved",
                "sha256": hashlib.sha256(conteudo_norm.encode("utf-8")).hexdigest(),
                "metadata": {
                    "source_pdf": f"{src_id}.pdf",
                    "category": cat,
                    "page_number": int(nchk["page_number"]),
                    "document_stem": src_id,
                    "route_category": str(nchk["route_category"]),
                },
            }
        )

    # 3. Chunks de Geolocalização das Farmácias e UBS do DF (alinhados por unidade completa)
    caminho_geo = raiz / "data" / "processed" / "df_pharmacies_geolocated.json"
    dados_geo = json.loads(caminho_geo.read_text(encoding="utf-8"))
    farmacias = list(dados_geo.get("pharmacies") or [])
    chunks_geo: list[dict[str, Any]] = []
    bloco_geo = 10
    for idx in range(0, len(farmacias), bloco_geo):
        fatia_f = farmacias[idx : idx + bloco_geo]
        seg_idx = idx // bloco_geo
        page_num = (seg_idx // 5) + 1
        linhas_f: list[str] = []
        for f_item in fatia_f:
            lat = f_item.get("latitude")
            lng = f_item.get("longitude")
            coord = (
                f"{lat:.4f}, {lng:.4f}"
                if isinstance(lat, float) and isinstance(lng, float)
                else "Não georreferenciado"
            )
            linhas_f.append(
                f"{f_item.get('name')} ({f_item.get('pharmacy_type')}) | "
                f"Região: {f_item.get('neighborhood_or_ra')} | "
                f"Endereço: {f_item.get('address')} | GPS: {coord}."
            )
        conteudo_geo = (
            "GUIA OFICIAL DE ESTABELECIMENTOS FARMACÊUTICOS E UBS DO DF (SES-DF / InfoSaúde): "
            + " ".join(linhas_f)
        )
        chunks_geo.append(
            {
                "chunk_id": f"GUIA_FARMACIAS_UBS_GEO_DF_p{page_num:03d}_c{seg_idx:02d}",
                "source_pdf": "GUIA_FARMACIAS_UBS_GEO_DF.pdf",
                "category": "geolocalizacao_farmacias_ubs",
                "page_number": page_num,
                "segment_index": seg_idx,
                "char_count": len(conteudo_geo),
                "content": conteudo_geo,
                "review_status": "approved",
                "sha256": hashlib.sha256(conteudo_geo.encode("utf-8")).hexdigest(),
                "metadata": {
                    "source_pdf": "GUIA_FARMACIAS_UBS_GEO_DF.pdf",
                    "category": "geolocalizacao_farmacias_ubs",
                    "page_number": page_num,
                    "document_stem": "GUIA_FARMACIAS_UBS_GEO_DF",
                },
            }
        )

    # 4. Chunks de Estoque das Farmácias de Alto Custo (CEAF InfoSaúde DF, alinhados por item)
    caminho_ceaf = raiz / "data" / "processed" / "ceaf_live_stock.json"
    dados_ceaf = json.loads(caminho_ceaf.read_text(encoding="utf-8"))
    itens_ceaf = list(dados_ceaf.get("items") or [])
    chunks_ceaf: list[dict[str, Any]] = []
    bloco_ceaf = 12
    for idx in range(0, min(len(itens_ceaf), 240), bloco_ceaf):
        fatia_c = itens_ceaf[idx : idx + bloco_ceaf]
        seg_idx = idx // bloco_ceaf
        page_num = (seg_idx // 4) + 1
        linhas_c: list[str] = []
        for c_item in fatia_c:
            linhas_c.append(
                f"Cód. {c_item.get('code')} {c_item.get('medication')} | "
                f"Unidade CEAF: {c_item.get('unit')} | "
                f"Status: {c_item.get('status')}."
            )
        conteudo_ceaf = (
            "RELATÓRIO DE ESTOQUE DAS FARMÁCIAS DE ALTO CUSTO (CEAF SES-DF / InfoSaúde): "
            + " ".join(linhas_c)
        )
        chunks_ceaf.append(
            {
                "chunk_id": f"RELATORIO_ESTOQUE_CEAF_INFOSAUDE_p{page_num:03d}_c{seg_idx:02d}",
                "source_pdf": "RELATORIO_ESTOQUE_CEAF_INFOSAUDE.pdf",
                "category": "estoque_ceaf_tempo_real",
                "page_number": page_num,
                "segment_index": seg_idx,
                "char_count": len(conteudo_ceaf),
                "content": conteudo_ceaf,
                "review_status": "approved",
                "sha256": hashlib.sha256(conteudo_ceaf.encode("utf-8")).hexdigest(),
                "metadata": {
                    "source_pdf": "RELATORIO_ESTOQUE_CEAF_INFOSAUDE.pdf",
                    "category": "estoque_ceaf_tempo_real",
                    "page_number": page_num,
                    "document_stem": "RELATORIO_ESTOQUE_CEAF_INFOSAUDE",
                },
            }
        )

    return chunks_catalogo + chunks_normativos_pdf + chunks_geo + chunks_ceaf


def atualizar_manifesto(
    caminho_manifesto: Path,
    caminho_meds: Path,
    caminho_norm_chunks: Path,
    caminho_pdf_chunks: Path,
    caminho_staging_occ: Path,
    total_meds: int,
    total_norm_chunks: int,
    total_pdf_chunks: int,
    total_occurrences: int,
    origem: dict[str, Any],
) -> dict[str, Any]:
    """Atualiza data/manifests/manifest.json com linhagem criptográfica SHA-256."""
    meds_sha = hashlib.sha256(caminho_meds.read_bytes()).hexdigest()
    norm_sha = hashlib.sha256(caminho_norm_chunks.read_bytes()).hexdigest()
    pdf_sha = hashlib.sha256(caminho_pdf_chunks.read_bytes()).hexdigest()
    occ_sha = hashlib.sha256(caminho_staging_occ.read_bytes()).hexdigest()
    combined = hashlib.sha256(f"{meds_sha}:{norm_sha}:{pdf_sha}:{occ_sha}".encode()).hexdigest()

    manifest: dict[str, Any] = {
        "manifest_version": "2026.3.1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "engineering_source": origem["release_version"],
        "engineering_source_commit": origem["commit"],
        "engineering_source_manifest_sha256": origem["release_manifest_sha256"],
        "canonical_medications_sha256": meds_sha,
        "normative_chunks_sha256": norm_sha,
        "unified_pdf_chunks_sha256": pdf_sha,
        "curated_occurrences_sha256": occ_sha,
        "combined_sha256": combined,
        "record_counts": {
            "canonical_medications": total_meds,
            "normative_chunks": total_norm_chunks,
            "unified_pdf_chunks": total_pdf_chunks,
            "curated_occurrences_f01_f03_f04": total_occurrences,
        },
    }
    caminho_manifesto.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def executar_pipeline_consolidacao(raiz: Path = RAIZ_REPO) -> dict[str, Any]:
    """Executa o pipeline completo de consolidação de dados e reconciliação de chunks."""
    caminho_occ = raiz / "data" / "staging" / "curated_occurrences_v5.jsonl"
    caminho_origem = raiz / "data" / "manifests" / "corpus_v5_source.json"
    caminho_meds = raiz / "data" / "processed" / "medicamentos_sus_canonical.json"
    caminho_meds_full = raiz / "data" / "processed" / "medicamentos_sus_canonical_full.json"
    caminho_norm = raiz / "data" / "processed" / "normative_chunks.json"
    caminho_pdf_chunks = raiz / "data" / "processed" / "unified_pdf_chunks.json"
    caminho_manifest = raiz / "data" / "manifests" / "manifest.json"

    origem = json.loads(caminho_origem.read_text(encoding="utf-8"))
    dados = caminho_occ.read_bytes()
    if hashlib.sha256(dados).hexdigest() != origem["staging_sha256"]:
        raise ValueError("Staging v5 diverge do SHA-256 registrado")
    occurrences = [json.loads(line) for line in dados.splitlines() if line.strip()]

    catalogo = consolidar_catalogo_medicamentos(occurrences)
    meds_json = json.dumps(catalogo, ensure_ascii=False, indent=2) + "\n"
    caminho_meds.write_text(meds_json, encoding="utf-8")
    caminho_meds_full.write_text(meds_json, encoding="utf-8")

    norm_chunks = consolidar_normative_chunks(caminho_norm)
    caminho_norm.write_text(
        json.dumps(norm_chunks, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    pdf_chunks = regenerar_unified_pdf_chunks(raiz, catalogo, norm_chunks)
    caminho_pdf_chunks.write_text(
        json.dumps(pdf_chunks, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    manifest = atualizar_manifesto(
        caminho_manifesto=caminho_manifest,
        caminho_meds=caminho_meds,
        caminho_norm_chunks=caminho_norm,
        caminho_pdf_chunks=caminho_pdf_chunks,
        caminho_staging_occ=caminho_occ,
        total_meds=len(catalogo),
        total_norm_chunks=len(norm_chunks),
        total_pdf_chunks=len(pdf_chunks),
        total_occurrences=len(occurrences),
        origem=origem,
    )
    return manifest


if __name__ == "__main__":
    resultado = executar_pipeline_consolidacao()
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
