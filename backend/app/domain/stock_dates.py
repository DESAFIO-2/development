"""Datas de posição do estoque público; ausência nunca implica atualização."""

import math
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

_BRT_TZ = ZoneInfo("America/Sao_Paulo")


def parse_source_timestamp_utc(raw_value: Any) -> datetime | None:
    """Converte timestamp da fonte InfoSaúde-DF (BRT/ISO/epoch) para UTC sem fabricar data atual."""
    if raw_value is None or isinstance(raw_value, bool):
        return None
    if isinstance(raw_value, int | float):
        if not math.isfinite(raw_value) or raw_value <= 0:
            return None
        seconds = raw_value / 1000.0 if abs(raw_value) >= 1e11 else float(raw_value)
        try:
            return datetime.fromtimestamp(seconds, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    text = str(raw_value).strip()
    if not text:
        return None
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=_BRT_TZ).astimezone(UTC)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_BRT_TZ)
    return parsed.astimezone(UTC)
