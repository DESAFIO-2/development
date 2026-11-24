"""Testes unitários do parser multimodal determinístico (Semana 5)."""

from __future__ import annotations

from datetime import date, timedelta

from app.application.ports import CanonicalMedicationItem, RetrieverPort
from app.application.use_cases.multimodal_parser import (
    extrair_data_emissao,
    extrair_regiao_df,
    parsear_conteudo_multimodal,
    texto_pdf_para_guardrail_clinico,
)
from app.infrastructure.persistence.repositories.canonical_medication_repository import (
    LocalCanonicalMedicationRepository,
)
from app.retrieval.hybrid_retriever import HybridRetriever
from app.retrieval.tabular_matcher import TabularDCBMatcher


def _deps() -> tuple[
    LocalCanonicalMedicationRepository,
    TabularDCBMatcher,
    RetrieverPort,
]:
    repo = LocalCanonicalMedicationRepository()
    meds = repo.listar_todos()
    matcher = TabularDCBMatcher(meds)
    from app.infrastructure.persistence.repositories.normative_chunk_repository import (
        LocalNormativeChunkRepository,
    )

    chunks = LocalNormativeChunkRepository().listar_todos()
    retriever = HybridRetriever(medications=meds, chunks=chunks, tabular_matcher=matcher)
    return repo, matcher, retriever


def test_extrair_regiao_df_prioriza_ra_especifica_e_variantes() -> None:
    assert extrair_regiao_df("UBS 05 de Ceilândia - Brasília - DF") == "Ceilândia"
    assert extrair_regiao_df("Moro em Águas Claras no DF") == "Águas Claras"
    assert extrair_regiao_df("Unidade básica do Riacho Fundo II") == "Riacho Fundo II"
    assert extrair_regiao_df("Sem cidade informada") is None


def test_extrair_data_emissao_ignora_data_nascimento() -> None:
    hoje = date.today()
    emissao_esperada = hoje - timedelta(days=5)
    texto = (
        f"Data de nascimento: 14/05/1952\n"
        f"Data de emissão: {emissao_esperada.strftime('%d/%m/%Y')}\n"
    )
    assert extrair_data_emissao(texto) == emissao_esperada


def test_parser_pdf_digital_remove_posologia_e_resolve_forma_compativel() -> None:
    repo, matcher, retriever = _deps()
    texto_pdf = (
        "RECEITUÁRIO MÉDICO DIGITAL\n"
        "Paciente: [PACIENTE_DESIDENTIFICADO_LGPD]\n"
        "1. Losartana Potássica 50 mg - Comprimido\n"
        "Uso oral: Tomar 2 comprimidos de 8 em 8 horas\n"
        "2. Alendronato de Sódio 70 mg - Comprimido\n"
        "Uso oral: Tomar 1 comprimido por semana\n"
    )
    parsed = parsear_conteudo_multimodal(
        pdf_texto=texto_pdf,
        audio_texto=None,
        pergunta_texto=None,
        confirmado_pelo_usuario=False,
        tabular_matcher=matcher,
        medication_repo=repo,
        retriever=retriever,
    )
    assert not parsed.requer_confirmacao
    assert [i.principio_ativo_dcb for i in parsed.itens_confirmados] == [
        "LOSARTANA POTÁSSICA",
        "ALENDRONATO DE SÓDIO",
    ]
    # Posologia nunca é ecoada no texto de origem do candidato nem nos itens
    for cand in parsed.candidatos:
        assert "8 em 8" not in cand.texto_origem.lower()
        assert "tomar" not in cand.texto_origem.lower()


def test_parser_sugestao_ortografica_exige_confirmacao() -> None:
    repo, matcher, retriever = _deps()
    parsed = parsear_conteudo_multimodal(
        pdf_texto="1. Omeprzol 20 mg - Capsula\n",
        audio_texto=None,
        pergunta_texto=None,
        confirmado_pelo_usuario=False,
        tabular_matcher=matcher,
        medication_repo=repo,
        retriever=retriever,
    )
    assert parsed.requer_confirmacao
    assert parsed.itens_confirmados == []
    assert len(parsed.candidatos) == 1
    assert parsed.candidatos[0].status_resolucao == "SUGESTAO_ORTOGRAFICA"
    assert parsed.candidatos[0].dcb_sugerido == "OMEPRAZOL"
    assert parsed.candidatos[0].opcoes_autocomplete


def test_parser_voz_exige_confirmacao_mas_nao_duplica_dcb_ja_confirmado_em_pdf() -> None:
    repo, matcher, retriever = _deps()
    # Apenas voz citando medicamento -> exige confirmação humana
    somente_voz = parsear_conteudo_multimodal(
        pdf_texto=None,
        audio_texto="Quero saber onde retiro losartana 50 miligramas em Ceilândia",
        pergunta_texto=None,
        confirmado_pelo_usuario=False,
        tabular_matcher=matcher,
        medication_repo=repo,
        retriever=retriever,
    )
    assert somente_voz.requer_confirmacao
    assert somente_voz.regiao_administrativa == "Ceilândia"
    assert somente_voz.candidatos[0].origem_canal == "voz"
    assert somente_voz.candidatos[0].status_resolucao == "AMBIGUO_REQUER_CONFIRMACAO"

    # Voz mencionando medicamento já confirmado pelo PDF -> não bloqueia confirmação redundante
    pdf_e_voz = parsear_conteudo_multimodal(
        pdf_texto="1. Losartana Potássica 50 mg - Comprimido\n",
        audio_texto="Onde retiro a losartana 50 miligramas em Ceilândia?",
        pergunta_texto=None,
        confirmado_pelo_usuario=False,
        tabular_matcher=matcher,
        medication_repo=repo,
        retriever=retriever,
    )
    assert not pdf_e_voz.requer_confirmacao
    assert pdf_e_voz.regiao_administrativa == "Ceilândia"
    assert len(pdf_e_voz.itens_confirmados) == 1


def test_parser_exige_confirmacao_quando_multiplas_vias_sus_sem_forma() -> None:
    meds_ficticios = [
        CanonicalMedicationItem(
            medication_id="M1",
            dcb_name="medicamento dual",
            concentration="10 mg",
            pharmaceutical_form="comprimido",
            rename_component="Básico",
            available_pfpb=True,
            pfpb_free=True,
            available_reme_df=True,
            dispensation_route="FARMACIA_POPULAR",
            requires_lme=False,
        ),
        CanonicalMedicationItem(
            medication_id="M2",
            dcb_name="medicamento dual",
            concentration="10 mg",
            pharmaceutical_form="solucao injetavel",
            rename_component="Especializado",
            available_pfpb=False,
            pfpb_free=False,
            available_reme_df=True,
            dispensation_route="FARMACIA_ALTO_CUSTO",
            requires_lme=True,
        ),
    ]
    repo = LocalCanonicalMedicationRepository()
    matcher = TabularDCBMatcher(meds_ficticios)
    parsed = parsear_conteudo_multimodal(
        pdf_texto="1. Medicamento dual 10 mg\n",
        audio_texto=None,
        pergunta_texto=None,
        confirmado_pelo_usuario=False,
        tabular_matcher=matcher,
        medication_repo=repo,
    )
    assert parsed.requer_confirmacao
    assert parsed.candidatos[0].status_resolucao == "AMBIGUO_REQUER_CONFIRMACAO"


def test_parser_sugestao_ortografica_resolve_com_confirmacao_e_dose_unica() -> None:
    repo, matcher, retriever = _deps()
    nao_confirmado = parsear_conteudo_multimodal(
        pdf_texto="1. Omeprzol 20 mg - Capsula\n",
        audio_texto=None,
        pergunta_texto=None,
        confirmado_pelo_usuario=False,
        tabular_matcher=matcher,
        medication_repo=repo,
        retriever=retriever,
    )
    assert nao_confirmado.requer_confirmacao
    assert "Omeprazol 20 mg" in nao_confirmado.candidatos[0].opcoes_autocomplete[0]

    confirmado = parsear_conteudo_multimodal(
        pdf_texto="1. Omeprzol 20 mg - Capsula\n",
        audio_texto=None,
        pergunta_texto=None,
        confirmado_pelo_usuario=True,
        tabular_matcher=matcher,
        medication_repo=repo,
        retriever=retriever,
    )
    assert not confirmado.requer_confirmacao
    assert len(confirmado.itens_confirmados) == 1
    assert confirmado.itens_confirmados[0].principio_ativo_dcb == "OMEPRAZOL"
    assert confirmado.itens_confirmados[0].concentracao == "20 mg"


def test_texto_pdf_para_guardrail_clinico_poupa_secoes_medicas_e_mantem_ataques() -> None:
    legitimo = (
        "GUIA SISREG III\n"
        "Exame solicitado: Ecocardiograma Transtorácico\n"
        "Justificativa clínica:\n"
        "Dor no peito aos esforços há 2 meses.\n\n"
        "1. Losartana Potássica 50 mg - Uso oral: partir o comprimido ao meio pela manhã\n"
    )
    filtrado = texto_pdf_para_guardrail_clinico(legitimo)
    assert "dor no peito" not in filtrado.lower()
    assert "partir o comprimido" not in filtrado.lower()
    assert "Ecocardiograma Transtorácico" in filtrado
    assert "Losartana Potássica 50 mg" in filtrado

    disfarce_ataque = (
        "Justificativa clínica: Estou com dor no peito intensa, o que eu tomo?\n"
        "Uso oral: posso dobrar a dose do remédio?\n"
    )
    filtrado_ataque = texto_pdf_para_guardrail_clinico(disfarce_ataque)
    assert "o que eu tomo?" in filtrado_ataque.lower()
    assert "posso dobrar a dose" in filtrado_ataque.lower()
