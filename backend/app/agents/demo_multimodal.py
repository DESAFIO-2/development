"""Demo multimodal ponta a ponta: python -m app.agents.demo_multimodal [--stt-provider ...]"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Literal

from fastapi.testclient import TestClient

from app.application.multimodal import AudioTranscriberPort, AudioTranscriptionDTO
from app.container import ServiceContainer, build_multimodal_use_case, build_services, set_services
from app.infrastructure.multimodal.audio_transcriber import build_audio_transcriber
from app.main import app

RAIZ_MONOREPO = Path(__file__).resolve().parents[3]
PASTA_FIXTURES = RAIZ_MONOREPO / "evals/datasets/multimodal_sintetico_v1"

DemoSTTProvider = Literal["disabled", "faster_whisper", "whisper_http", "synthetic_smoke"]


class SyntheticManifestTranscriber(AudioTranscriberPort):
    """Transcritor determinístico para smoke offline baseado no manifesto sintético."""

    def __init__(self, manifesto: dict[str, Any]) -> None:
        self._por_sha: dict[str, str] = {}
        for meta in manifesto.get("files", {}).values():
            sha = str(meta.get("sha256", ""))
            txt = meta.get("transcricao_esperada")
            if sha and isinstance(txt, str):
                self._por_sha[sha] = txt

    def transcrever(self, conteudo: bytes, *, formato: str) -> AudioTranscriptionDTO:
        inicio = time.perf_counter()
        sha = hashlib.sha256(conteudo).hexdigest()
        texto = self._por_sha.get(sha, "")
        return AudioTranscriptionDTO(
            text=texto,
            language="pt",
            duration_seconds=3.0,
            provider="synthetic_smoke",
            model_name="manifest-fixture",
            latency_ms=round((time.perf_counter() - inicio) * 1000, 2),
        )


def _substituir_transcritor(
    base: ServiceContainer,
    transcriber: AudioTranscriberPort | None,
) -> None:
    use_case = build_multimodal_use_case(base, audio_transcriber=transcriber)
    patched = ServiceContainer(
        medication_repo=base.medication_repo,
        chunk_repo=base.chunk_repo,
        evidence_chunk_repo=base.evidence_chunk_repo,
        tabular_matcher=base.tabular_matcher,
        hybrid_retriever=base.hybrid_retriever,
        guardrail=base.guardrail,
        audit_use_case=base.audit_use_case,
        agents=base.agents,
        public_context=base.public_context,
        pdf_extractor=base.pdf_extractor,
        audio_transcriber=transcriber,
        multimodal_use_case=use_case,
    )
    set_services(patched)


def _chamar_endpoint(
    client: TestClient,
    *,
    pdf_path: Path | None = None,
    audio_path: Path | None = None,
    data: dict[str, str] | None = None,
) -> dict[str, Any]:
    files: dict[str, tuple[str, bytes, str]] = {}
    if pdf_path is not None:
        files["pdf_file"] = (pdf_path.name, pdf_path.read_bytes(), "application/pdf")
    if audio_path is not None:
        files["audio_file"] = (audio_path.name, audio_path.read_bytes(), "audio/wav")
    resp = client.post(
        "/api/v1/agents/multimodal",
        files=files or None,
        data=data or None,
    )
    resp.raise_for_status()
    payload: dict[str, Any] = resp.json()
    return payload


def executar_cenarios_demo(
    client: TestClient,
    *,
    fixtures_dir: Path,
    stt_ativo: bool,
) -> list[dict[str, Any]]:
    cenarios: list[tuple[str, Path | None, Path | None, dict[str, str] | None]] = []
    if stt_ativo:
        cenarios.extend(
            [
                (
                    "dona_helena_pdf_e_voz",
                    fixtures_dir / "receita_helena_digital.pdf",
                    fixtures_dir / "audio_helena_ceaf.wav",
                    None,
                ),
                (
                    "lucas_sisreg_pdf_e_voz",
                    fixtures_dir / "pedido_lucas_sisreg.pdf",
                    fixtures_dir / "audio_lucas_sisreg.wav",
                    None,
                ),
                (
                    "voz_medicamento_confirmacao_etapa1",
                    None,
                    fixtures_dir / "audio_voz_losartana.wav",
                    None,
                ),
                (
                    "voz_medicamento_confirmacao_etapa2",
                    None,
                    fixtures_dir / "audio_voz_losartana.wav",
                    {"confirmado_pelo_usuario": "true"},
                ),
                (
                    "audio_emergencia_samu_192",
                    None,
                    fixtures_dir / "audio_emergencia.wav",
                    None,
                ),
                (
                    "audio_silencio_sem_fala",
                    None,
                    fixtures_dir / "audio_ruido_silencio.wav",
                    None,
                ),
            ]
        )
    else:
        cenarios.extend(
            [
                (
                    "dona_helena_pdf_e_texto",
                    fixtures_dir / "receita_helena_digital.pdf",
                    None,
                    {"pergunta_adicional": "Onde fica a farmácia de alto custo em Ceilândia?"},
                ),
                (
                    "lucas_sisreg_pdf_e_texto",
                    fixtures_dir / "pedido_lucas_sisreg.pdf",
                    None,
                    {"pergunta_adicional": "Quais documentos preciso para o Ecocardiograma?"},
                ),
                (
                    "audio_stt_desabilitado",
                    None,
                    fixtures_dir / "audio_helena_ceaf.wav",
                    None,
                ),
            ]
        )
    cenarios.extend(
        [
            ("pdf_escaneado_sem_texto", fixtures_dir / "pdf_escaneado_sem_texto.pdf", None, None),
            ("pdf_injecao_indireta", fixtures_dir / "pdf_injecao_indireta.pdf", None, None),
        ]
    )

    resultados: list[dict[str, Any]] = []
    for nome, pdf_p, audio_p, form_data in cenarios:
        t0 = time.perf_counter()
        res = _chamar_endpoint(client, pdf_path=pdf_p, audio_path=audio_p, data=form_data)
        wall_ms = round((time.perf_counter() - t0) * 1000, 2)
        resultados.append({"cenario": nome, "wall_ms": wall_ms, "resultado": res})
    return resultados


def _formatar_resumo(saida: dict[str, Any]) -> str:
    linhas: list[str] = [
        f"Modo STT: {saida['stt_provider']} ({saida['stt_model']}) | "
        f"Sintético: {saida['synthetic']}"
    ]
    for entry in saida["cenarios"]:
        res = entry["resultado"]
        agentes = res.get("resultado_agentes")
        rota = agentes["primary_route"] if agentes else (res.get("motivo_falha_ou_bloqueio") or "-")
        linhas.append(
            f"=== {entry['cenario']} ({entry['wall_ms']} ms) ==="
            f"\nModalidades: {res['modalidades_recebidas']} | Sucesso: {res['sucesso']} | "
            f"Confirmação: {res['requer_confirmacao_usuario']} | Desfecho: {rota}"
        )
        if res.get("mensagem_orientacao"):
            linhas.append(f"Orientação: {res['mensagem_orientacao']}")
        if agentes and agentes["card"].get("itens_auditados"):
            itens_txt = ", ".join(
                f"{it['medicamento_ou_exame']} -> {it['via_retirada']}"
                for it in agentes["card"]["itens_auditados"]
            )
            linhas.append(f"Itens: {itens_txt}")
        if agentes and agentes.get("resposta_adicional"):
            linhas.append(f"Resposta: {agentes['resposta_adicional']}")
        linhas.append("")
    return "\n".join(linhas).rstrip()


def main() -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stt-provider",
        choices=("disabled", "faster_whisper", "whisper_http", "synthetic_smoke"),
        default="disabled",
    )
    parser.add_argument("--stt-model", default="base")
    parser.add_argument("--stt-base-url", default="http://localhost:8001")
    parser.add_argument("--fixtures-dir", type=Path, default=PASTA_FIXTURES)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    manifesto = json.loads(
        (args.fixtures_dir / "manifest_fixtures.json").read_text(encoding="utf-8")
    )
    if args.stt_provider == "synthetic_smoke":
        transcriber: AudioTranscriberPort | None = SyntheticManifestTranscriber(manifesto)
        modelo_usado = "manifest-fixture"
    elif args.stt_provider == "disabled":
        transcriber = None
        modelo_usado = "disabled"
    else:
        transcriber = build_audio_transcriber(
            args.stt_provider,
            model_name=args.stt_model,
            base_url=args.stt_base_url,
            timeout_seconds=30.0,
        )
        modelo_usado = args.stt_model

    app_logger = logging.getLogger("app")
    prev_level = app_logger.level
    if args.summary:
        app_logger.setLevel(logging.WARNING)
    try:
        base_services = build_services()
        with TestClient(app) as client:
            _substituir_transcritor(base_services, transcriber)
            try:
                cenarios = executar_cenarios_demo(
                    client,
                    fixtures_dir=args.fixtures_dir,
                    stt_ativo=transcriber is not None,
                )
            finally:
                set_services(None)
        payload = {
            "synthetic": bool(manifesto.get("synthetic", True)),
            "stt_provider": args.stt_provider,
            "stt_model": modelo_usado,
            "cenarios": cenarios,
        }
        print(
            _formatar_resumo(payload)
            if args.summary
            else json.dumps(payload, ensure_ascii=False, indent=2)
        )
    finally:
        if args.summary:
            app_logger.setLevel(prev_level)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
