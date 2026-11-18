"""Rótulos documentais exatos; não inferem equivalências terapêuticas."""

import unicodedata

from app.application.ports import CanonicalMedicationItem


def label_key(text: str) -> str:
    # Preservar operadores, decimais e pontuação; só caixa, acento e espaços variam.
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in normalized if not c.isspace() and not unicodedata.combining(c))


def medication_labels(med: CanonicalMedicationItem) -> tuple[str, ...]:
    label = f"{med.dcb_name} {med.concentration}"
    return (
        med.dcb_name,
        label,
        f"{label} {med.pharmaceutical_form}",
        f"{label} - {med.pharmaceutical_form}",
    )
