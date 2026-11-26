"""Reexecuções do bot preservam revisão e invalidam propostas obsoletas."""

from app.ingestion.stock_sync_plan import decide


def test_retorno_a_base_fecha_proposta_obsoleta() -> None:
    assert decide([{"stock": "A"}], [{"stock": "A"}], [{"stock": "B"}]) == "close"


def test_recoleta_identica_preserva_pr_e_ignora_apenas_instante_de_coleta() -> None:
    base = [{"stock": "A"}]
    proposal = [{"stock": "B", "synced_at_utc": "ontem"}]
    latest = [{"stock": "B", "synced_at_utc": "hoje"}]
    assert decide(base, latest, proposal) == "noop"
    assert latest[0]["synced_at_utc"] == "hoje"
    assert decide(base, latest, None) == "update"


def test_nova_posicao_e_mudanca_de_unidades_atualizam_proposta() -> None:
    assert decide([{"stock": "A"}], [{"stock": "C"}], [{"stock": "B"}]) == "update"
    assert decide([{}, {"units": 1}], [{}, {"units": 2}], None) == "update"
    assert decide([{"updated_at": "ontem"}], [{"updated_at": "hoje"}], None) == "update"
