"""Caso de uso principal do pipeline multimodal (Semana 5 — ADR 0008)."""

from __future__ import annotations

import re
from datetime import date

from app.application.agents import AgentRequest, OrchestratorPort
from app.application.multimodal import (
    AudioTranscriberPort,
    CanalMultimodal,
    ExtractedCandidateItem,
    ExtractedFileReport,
    MultimodalRequest,
    MultimodalResponse,
    PDFExtractorPort,
)
from app.application.ports import GuardrailPort, MedicationRepositoryPort, RetrieverPort
from app.application.use_cases.multimodal_parser import (
    parsear_conteudo_multimodal,
    texto_pdf_para_guardrail_clinico,
)
from app.core.telemetry import trace_operation
from app.domain.prescription import MedicationItemInput
from app.guardrails.clinical import ClinicalGuardrail
from app.retrieval.tabular_matcher import TabularDCBMatcher
from app.retrieval.text_normalizer import normalizar_texto_pt
from app.seguranca.arquivos import (
    MAX_DURACAO_AUDIO_SEGUNDOS,
    validar_audio,
    validar_pdf,
)
from app.seguranca.esteira import Canal, inspecionar_entrada
from app.seguranca.injecao import FORTES, detectar
from app.seguranca.saida import validar_saida

_MSG_BLOQUEIO_INJECAO = (
    "Aviso de Segurança (Preservação do Ato Médico — Lei nº 12.842/2013): "
    "A solicitação contém instruções incompatíveis com o escopo de navegação "
    "administrativa do SUS Cidadão. Envie apenas a receita digital oficial, nome "
    "do medicamento ou dúvida administrativa para consultar as rotas gratuitas."
)

_FALLBACK_CLINICAL_GUARDRAIL = ClinicalGuardrail()

_MSG_PDF_ESCANEADO = (
    "Não identificamos camada de texto digital legível neste PDF (documento provavelmente "
    "escaneado como imagem ou foto). Pelo protocolo de segurança do SUS Cidadão (ADR 0002), "
    "não realizamos OCR sobre imagens de receitas; informe o medicamento pelo campo de "
    "autocomplete ou envie o PDF digital emitido pelo sistema prescritor."
)

_MSG_ERRO_ARQUIVO_PADRAO = (
    "O arquivo enviado foi recusado pelas barreiras estruturais de segurança do SUS Cidadão. "
    "Verifique o formato e o limite de tamanho antes de tentar novamente."
)


def _extensao_audio(alertas: tuple[str, ...], audio_filename: str | None) -> str:
    for alerta in alertas:
        if alerta.startswith("AUDIO_"):
            ext = alerta.removeprefix("AUDIO_").lower()
            if ext:
                return ext
    if audio_filename and "." in audio_filename:
        return audio_filename.rsplit(".", 1)[-1].lower()
    return "wav"


def _validar_mensagem_segura(texto: str, padrao: str) -> str:
    return texto if validar_saida(texto).aprovada else padrao


def _sanitizar_candidatos(
    candidatos: list[ExtractedCandidateItem],
) -> list[ExtractedCandidateItem]:
    seguros: list[ExtractedCandidateItem] = []
    for cand in candidatos:
        origem_limpa = (
            cand.texto_origem
            if validar_saida(cand.texto_origem).aprovada
            else "[TRECHO_REMOVIDO_POR_SEGURANCA]"
        )
        opcoes_limpas = [op for op in cand.opcoes_autocomplete if validar_saida(op).aprovada]
        seguros.append(
            cand.model_copy(
                update={
                    "texto_origem": origem_limpa,
                    "opcoes_autocomplete": opcoes_limpas,
                }
            )
        )
    return seguros


class ProcessMultimodalUseCase:
    """Executa ingestão multimodal em memória: gates binários, segurança, parser e orquestração."""

    def __init__(
        self,
        *,
        orchestrator: OrchestratorPort,
        guardrail: GuardrailPort,
        tabular_matcher: TabularDCBMatcher,
        medication_repo: MedicationRepositoryPort,
        retriever: RetrieverPort,
        pdf_extractor: PDFExtractorPort,
        audio_transcriber: AudioTranscriberPort | None = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.guardrail = guardrail
        self.tabular_matcher = tabular_matcher
        self.medication_repo = medication_repo
        self.retriever = retriever
        self.pdf_extractor = pdf_extractor
        self.audio_transcriber = audio_transcriber

    def _coletar_modalidades(self, request: MultimodalRequest) -> list[CanalMultimodal]:
        modalidades: list[CanalMultimodal] = []
        if request.itens or (request.pergunta_adicional or "").strip():
            modalidades.append("texto")
        if request.pdf_bytes is not None:
            modalidades.append("pdf")
        if request.audio_bytes is not None:
            modalidades.append("voz")
        return modalidades

    def _inspecionar_seguranca_textual(
        self, entradas: list[tuple[Canal, str]]
    ) -> tuple[str, str] | None:
        """Retorna (motivo, mensagem_segura) em caso de emergência, ato médico ou injection."""
        weak_families: set[str] = set()
        emergencia_msg: str | None = None
        clinico_msg: str | None = None
        injection_hit = False

        for canal, texto in entradas:
            if not texto.strip():
                continue
            inj = inspecionar_entrada(texto, canal)
            if inj.bloqueado:
                injection_hit = True
            for motivo in detectar(texto).motivos:
                if motivo not in FORTES:
                    weak_families.add(motivo)
            texto_clinico = texto_pdf_para_guardrail_clinico(texto) if canal == Canal.PDF else texto
            clin_inst = getattr(self.guardrail, "_clinical", None)
            pdf_clinico = (
                clin_inst
                if isinstance(clin_inst, ClinicalGuardrail)
                else _FALLBACK_CLINICAL_GUARDRAIL
            )
            if canal == Canal.PDF and texto_clinico != texto:
                check_raw = pdf_clinico.inspecionar_clinico(texto, injection_blocked=inj.bloqueado)
                if check_raw.bloqueado and check_raw.motivo in {"PROMPT_INJECTION", "JAILBREAK"}:
                    injection_hit = True
            check = (
                (
                    pdf_clinico.inspecionar_clinico(texto_clinico, injection_blocked=inj.bloqueado)
                    if canal == Canal.PDF
                    else self.guardrail.verificar_ato_medico(texto_clinico)
                )
                if texto_clinico.strip()
                else None
            )
            if check is not None and check.bloqueado:
                if check.alerta_emergencia and emergencia_msg is None:
                    emergencia_msg = check.mensagem_acolhedora
                elif check.motivo not in {"PROMPT_INJECTION", "JAILBREAK"} and clinico_msg is None:
                    clinico_msg = check.mensagem_acolhedora
                elif check.motivo in {"PROMPT_INJECTION", "JAILBREAK"}:
                    injection_hit = True

        if emergencia_msg is not None:
            return "EMERGENCIA_MEDICA", _validar_mensagem_segura(
                emergencia_msg, _MSG_BLOQUEIO_INJECAO
            )
        if clinico_msg is not None:
            return "ATO_MEDICO", _validar_mensagem_segura(clinico_msg, _MSG_BLOQUEIO_INJECAO)
        if injection_hit or len(weak_families) >= 2:
            return "PROMPT_INJECTION", _MSG_BLOQUEIO_INJECAO
        return None

    def _mascarar_item(self, item: MedicationItemInput) -> MedicationItemInput:
        updates: dict[str, str | None] = {}
        for campo in (
            "nome_digitado",
            "principio_ativo_dcb",
            "concentracao",
            "forma_farmaceutica",
            "quantidade_prescrita",
        ):
            valor = getattr(item, campo)
            if isinstance(valor, str) and valor:
                updates[campo] = self.guardrail.desidentificar_dados_pessoais(
                    valor
                ).texto_sanitizado
        # Preserva sem eco de posologia livre na rota multimodal.
        updates["posologia"] = None
        return item.model_copy(update=updates)

    def _chave_item_canonica(self, item: MedicationItemInput) -> tuple[str, str]:
        conc_item = self.tabular_matcher.normalizar_concentracao(item.concentracao or "")
        if item.principio_ativo_dcb:
            return normalizar_texto_pt(item.principio_ativo_dcb), conc_item
        if not conc_item and item.nome_digitado:
            try:
                doses = self.tabular_matcher.doses_no_texto(item.nome_digitado)
            except ValueError:
                doses = set()
            if len(doses) == 1:
                conc_item = next(iter(doses))
        if item.nome_digitado:
            forma = item.forma_farmaceutica or ""
            casados = self.tabular_matcher.casar(
                item.nome_digitado,
                concentracao=conc_item,
                forma=forma,
                deduplicar=False,
            )
            chaves = {
                (
                    normalizar_texto_pt(m.dcb_name),
                    self.tabular_matcher.normalizar_concentracao(m.concentration),
                )
                for _, m in casados
            }
            if len(chaves) == 1:
                return next(iter(chaves))
        return normalizar_texto_pt(item.nome_digitado), conc_item

    def _mesclar_itens(
        self,
        itens_explicitos: list[MedicationItemInput],
        itens_extraidos: list[MedicationItemInput],
    ) -> list[MedicationItemInput]:
        mesclados: list[MedicationItemInput] = []
        vistos: set[tuple[str, str]] = set()
        for item in (*itens_explicitos, *itens_extraidos):
            chave = self._chave_item_canonica(item)
            if chave not in vistos:
                vistos.add(chave)
                mesclados.append(item)
        return mesclados[:50]

    def executar(
        self,
        request: MultimodalRequest,
        *,
        strict: bool = False,
    ) -> MultimodalResponse:
        modalidades = self._coletar_modalidades(request)
        relatorios: list[ExtractedFileReport] = []
        pdf_raw_text: str | None = None
        audio_raw_text: str | None = None

        # 1. PDF Digital (gate estrutural -> extração em memória)
        if request.pdf_bytes is not None:
            res_pdf = validar_pdf(request.pdf_bytes)
            if not res_pdf.aceito:
                relatorios.append(
                    ExtractedFileReport(
                        canal="pdf",
                        aceito=False,
                        motivos_rejeicao=list(res_pdf.motivos),
                        alertas=list(res_pdf.alertas),
                        extrator_usado="gate_binario",
                    )
                )
                return MultimodalResponse(
                    sucesso=False,
                    modalidades_recebidas=modalidades,
                    relatorios_entrada=relatorios,
                    motivo_falha_ou_bloqueio=res_pdf.motivos[0],
                    mensagem_orientacao=_MSG_ERRO_ARQUIVO_PADRAO,
                )
            with trace_operation("multimodal_pdf_extract"):
                try:
                    pdf_dto = self.pdf_extractor.extrair_texto(request.pdf_bytes)
                except Exception:
                    relatorios.append(
                        ExtractedFileReport(
                            canal="pdf",
                            aceito=False,
                            motivos_rejeicao=["PDF_ESTRUTURA_INVALIDA"],
                            alertas=list(res_pdf.alertas),
                            extrator_usado="pypdf",
                        )
                    )
                    return MultimodalResponse(
                        sucesso=False,
                        modalidades_recebidas=modalidades,
                        relatorios_entrada=relatorios,
                        motivo_falha_ou_bloqueio="PDF_ESTRUTURA_INVALIDA",
                        mensagem_orientacao=_MSG_ERRO_ARQUIVO_PADRAO,
                    )

            texto_util = re.sub(r"\s+", "", pdf_dto.text)
            if len(texto_util) < 10:
                relatorios.append(
                    ExtractedFileReport(
                        canal="pdf",
                        aceito=False,
                        motivos_rejeicao=["PDF_SEM_TEXTO_DIGITAL"],
                        alertas=list(res_pdf.alertas),
                        paginas=pdf_dto.page_count,
                        caracteres_extraidos=len(pdf_dto.text),
                        extrator_usado=pdf_dto.extractor,
                        latencia_ms=pdf_dto.latency_ms,
                    )
                )
                return MultimodalResponse(
                    sucesso=False,
                    modalidades_recebidas=modalidades,
                    relatorios_entrada=relatorios,
                    motivo_falha_ou_bloqueio="PDF_SEM_TEXTO_DIGITAL",
                    mensagem_orientacao=_MSG_PDF_ESCANEADO,
                )
            pdf_raw_text = pdf_dto.text
            alertas_pdf = list(res_pdf.alertas)
            if pdf_dto.truncated:
                return MultimodalResponse(
                    sucesso=False,
                    modalidades_recebidas=modalidades,
                    motivo_falha_ou_bloqueio="PDF_TEXTO_TRUNCADO",
                    mensagem_orientacao=(
                        "Documento excede o limite de texto. Use o preenchimento assistido."
                    ),
                )
            relatorios.append(
                ExtractedFileReport(
                    canal="pdf",
                    aceito=True,
                    alertas=alertas_pdf,
                    paginas=pdf_dto.page_count,
                    caracteres_extraidos=len(pdf_dto.text),
                    extrator_usado=pdf_dto.extractor,
                    latencia_ms=pdf_dto.latency_ms,
                )
            )

        # 2. Áudio de voz (gate binário -> transcrição STT local/HTTP em memória)
        if request.audio_bytes is not None:
            res_audio = validar_audio(request.audio_bytes)
            if not res_audio.aceito:
                relatorios.append(
                    ExtractedFileReport(
                        canal="voz",
                        aceito=False,
                        motivos_rejeicao=list(res_audio.motivos),
                        alertas=list(res_audio.alertas),
                        extrator_usado="gate_binario",
                    )
                )
                return MultimodalResponse(
                    sucesso=False,
                    modalidades_recebidas=modalidades,
                    relatorios_entrada=relatorios,
                    motivo_falha_ou_bloqueio=res_audio.motivos[0],
                    mensagem_orientacao=(
                        "O áudio ultrapassa os limites aceitos (máximo 60 segundos / 10 MB) "
                        "ou está em formato inválido."
                    ),
                )
            if self.audio_transcriber is None:
                relatorios.append(
                    ExtractedFileReport(
                        canal="voz",
                        aceito=False,
                        motivos_rejeicao=["STT_NAO_CONFIGURADO"],
                        alertas=list(res_audio.alertas),
                        extrator_usado="disabled",
                    )
                )
                return MultimodalResponse(
                    sucesso=False,
                    modalidades_recebidas=modalidades,
                    relatorios_entrada=relatorios,
                    motivo_falha_ou_bloqueio="STT_NAO_CONFIGURADO",
                    mensagem_orientacao=(
                        "A transcrição de áudio não está habilitada neste ambiente. "
                        "Use a busca assistida ou envie a receita em PDF digital."
                    ),
                )

            formato = _extensao_audio(res_audio.alertas, request.audio_filename)
            with trace_operation("multimodal_audio_stt"):
                audio_dto = self.audio_transcriber.transcrever(request.audio_bytes, formato=formato)

            if audio_dto.error_code:
                relatorios.append(
                    ExtractedFileReport(
                        canal="voz",
                        aceito=False,
                        motivos_rejeicao=[audio_dto.error_code],
                        alertas=list(res_audio.alertas),
                        duracao_segundos=audio_dto.duration_seconds,
                        extrator_usado=f"{audio_dto.provider}:{audio_dto.model_name}",
                        latencia_ms=audio_dto.latency_ms,
                    )
                )
                return MultimodalResponse(
                    sucesso=False,
                    modalidades_recebidas=modalidades,
                    relatorios_entrada=relatorios,
                    motivo_falha_ou_bloqueio=audio_dto.error_code,
                    mensagem_orientacao=(
                        "Não foi possível transcrever o áudio enviado com segurança. "
                        "Tente uma gravação curta (até 60 s) ou utilize a busca por texto."
                    ),
                )

            if (
                audio_dto.duration_seconds is not None
                and audio_dto.duration_seconds > MAX_DURACAO_AUDIO_SEGUNDOS
            ):
                relatorios.append(
                    ExtractedFileReport(
                        canal="voz",
                        aceito=False,
                        motivos_rejeicao=["AUDIO_LONGO_DEMAIS"],
                        alertas=list(res_audio.alertas),
                        duracao_segundos=audio_dto.duration_seconds,
                        extrator_usado=f"{audio_dto.provider}:{audio_dto.model_name}",
                        latencia_ms=audio_dto.latency_ms,
                    )
                )
                return MultimodalResponse(
                    sucesso=False,
                    modalidades_recebidas=modalidades,
                    relatorios_entrada=relatorios,
                    motivo_falha_ou_bloqueio="AUDIO_LONGO_DEMAIS",
                    mensagem_orientacao=(
                        "O áudio excedeu o limite máximo de 60 segundos. "
                        "Grave uma pergunta objetiva mais curta ou use a busca assistida."
                    ),
                )

            if len(re.findall(r"[A-Za-zÀ-ÿ0-9]", audio_dto.text)) < 3:
                relatorios.append(
                    ExtractedFileReport(
                        canal="voz",
                        aceito=False,
                        motivos_rejeicao=["AUDIO_SEM_FALA_IDENTIFICADA"],
                        alertas=list(res_audio.alertas),
                        duracao_segundos=audio_dto.duration_seconds,
                        caracteres_extraidos=len(audio_dto.text),
                        extrator_usado=f"{audio_dto.provider}:{audio_dto.model_name}",
                        latencia_ms=audio_dto.latency_ms,
                    )
                )
                return MultimodalResponse(
                    sucesso=False,
                    modalidades_recebidas=modalidades,
                    relatorios_entrada=relatorios,
                    motivo_falha_ou_bloqueio="AUDIO_SEM_FALA_IDENTIFICADA",
                    mensagem_orientacao=(
                        "Não identificamos fala audível no áudio enviado. "
                        "Tente gravar em ambiente silencioso ou utilize o campo de texto."
                    ),
                )

            audio_raw_text = audio_dto.text
            relatorios.append(
                ExtractedFileReport(
                    canal="voz",
                    aceito=True,
                    alertas=list(res_audio.alertas),
                    duracao_segundos=audio_dto.duration_seconds,
                    caracteres_extraidos=len(audio_dto.text),
                    extrator_usado=f"{audio_dto.provider}:{audio_dto.model_name}",
                    latencia_ms=audio_dto.latency_ms,
                )
            )

        # 3. Inspeção unificada de prompt injection cross-channel e Ato Médico
        entradas_seguranca: list[tuple[Canal, str]] = []
        if pdf_raw_text:
            entradas_seguranca.append((Canal.PDF, pdf_raw_text))
        if audio_raw_text:
            entradas_seguranca.append((Canal.VOZ, audio_raw_text))
        if request.pergunta_adicional:
            entradas_seguranca.append((Canal.TEXTO, request.pergunta_adicional))
        if request.regiao_administrativa:
            entradas_seguranca.append((Canal.TEXTO, request.regiao_administrativa))
        if request.tipo_prescritor:
            entradas_seguranca.append((Canal.TEXTO, request.tipo_prescritor))
        for item in request.itens:
            for val in item.model_dump().values():
                if isinstance(val, str) and val.strip():
                    entradas_seguranca.append((Canal.TEXTO, val))

        bloqueio = self._inspecionar_seguranca_textual(entradas_seguranca)
        if bloqueio is not None:
            motivo_bloq, msg_bloq = bloqueio
            return MultimodalResponse(
                sucesso=False,
                modalidades_recebidas=modalidades,
                relatorios_entrada=relatorios,
                motivo_falha_ou_bloqueio=motivo_bloq,
                mensagem_orientacao=msg_bloq,
            )

        # 4. Mascaramento LGPD antes de parser e orquestração
        pdf_limpo: str | None = None
        audio_limpo: str | None = None
        for rel in relatorios:
            if rel.canal == "pdf" and pdf_raw_text is not None:
                pii_pdf = self.guardrail.desidentificar_dados_pessoais(pdf_raw_text)
                pdf_limpo = pii_pdf.texto_sanitizado
                rel.pii_tipos_mascarados = list(pii_pdf.tipos_detectados)
            elif rel.canal == "voz" and audio_raw_text is not None:
                pii_audio = self.guardrail.desidentificar_dados_pessoais(audio_raw_text)
                audio_limpo = pii_audio.texto_sanitizado
                rel.pii_tipos_mascarados = list(pii_audio.tipos_detectados)

        pergunta_limpa = (
            self.guardrail.desidentificar_dados_pessoais(
                request.pergunta_adicional
            ).texto_sanitizado
            if request.pergunta_adicional
            else None
        )
        regiao_explicita = (
            self.guardrail.desidentificar_dados_pessoais(
                request.regiao_administrativa
            ).texto_sanitizado
            if request.regiao_administrativa
            else None
        )
        tipo_prescritor_limpo = self.guardrail.desidentificar_dados_pessoais(
            request.tipo_prescritor
        ).texto_sanitizado
        itens_explicitos_limpos = [self._mascarar_item(item) for item in request.itens]

        # 5. Parser multimodal e checagem de confirmação humana obrigatória
        parsed = parsear_conteudo_multimodal(
            pdf_texto=pdf_limpo,
            audio_texto=audio_limpo,
            pergunta_texto=pergunta_limpa,
            confirmado_pelo_usuario=request.confirmado_pelo_usuario,
            tabular_matcher=self.tabular_matcher,
            medication_repo=self.medication_repo,
            retriever=self.retriever,
            itens_explicitos=itens_explicitos_limpos,
        )
        candidatos_seguros = _sanitizar_candidatos(parsed.candidatos)
        itens_finais = self._mesclar_itens(itens_explicitos_limpos, parsed.itens_confirmados)

        if parsed.requer_confirmacao:
            return MultimodalResponse(
                sucesso=True,
                modalidades_recebidas=modalidades,
                requer_confirmacao_usuario=True,
                candidatos_extraidos=candidatos_seguros,
                relatorios_entrada=relatorios,
                resultado_agentes=None,
                mensagem_orientacao=(
                    "Confirme os medicamentos ou concentrações identificados no áudio/documento "
                    "antes de gerar a orientação oficial no SUS."
                ),
            )

        if not itens_finais and not (parsed.pergunta_extraida or "").strip():
            return MultimodalResponse(
                sucesso=False,
                modalidades_recebidas=modalidades,
                candidatos_extraidos=candidatos_seguros,
                relatorios_entrada=relatorios,
                motivo_falha_ou_bloqueio="CONTEUDO_SEM_ITEM_OU_PERGUNTA",
                mensagem_orientacao=(
                    "Não identificamos medicamentos, exames ou dúvidas administrativas válidas "
                    "no material enviado. Utilize o autocomplete ou descreva sua dúvida."
                ),
            )

        regiao_final = (
            regiao_explicita
            if regiao_explicita and regiao_explicita != "Distrito Federal"
            else (parsed.regiao_administrativa or regiao_explicita or "Distrito Federal")
        )
        data_final = request.data_emissao or parsed.data_emissao or date.today()
        agent_request = AgentRequest(
            itens=itens_finais,
            regiao_administrativa=regiao_final,
            data_emissao=data_final,
            tipo_prescritor=tipo_prescritor_limpo,
            pergunta_adicional=parsed.pergunta_extraida,
        )
        agent_response = self.orchestrator.executar(agent_request, strict=strict)
        motivo_final = "BLOQUEADO" if agent_response.primary_route == "BLOQUEADO" else None
        return MultimodalResponse(
            sucesso=agent_response.card.sucesso,
            modalidades_recebidas=modalidades,
            requer_confirmacao_usuario=False,
            candidatos_extraidos=candidatos_seguros,
            relatorios_entrada=relatorios,
            resultado_agentes=agent_response,
            motivo_falha_ou_bloqueio=motivo_final,
        )
