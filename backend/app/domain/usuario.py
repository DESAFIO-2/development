"""Regras puras de identidade: CPF e política de senha (sem infraestrutura)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

SENHA_MIN = 8
# Argon2 aceita qualquer tamanho, mas um teto evita DoS com senhas gigantes.
SENHA_MAX = 128

# Amostra das senhas mais vazadas em listas públicas (NIST SP 800-63B, 5.1.1.2):
# recusar as óbvias vale mais que exigir símbolo e maiúscula.
SENHAS_COMUNS = frozenset(
    {
        "12345678",
        "123456789",
        "1234567890",
        "87654321",
        "11111111",
        "00000000",
        "password",
        "password1",
        "senha123",
        "senha1234",
        "qwerty123",
        "abc12345",
        "iloveyou",
        "brasil123",
        "mudar123",
        "admin123",
        "remedia123",
        "sus12345",
    }
)


class CpfInvalido(ValueError):
    pass


class SenhaFraca(ValueError):
    pass


def normalizar_cpf(cpf: str) -> str:
    """Devolve só os 11 dígitos de um CPF válido ou levanta CpfInvalido."""
    # Só dígitos e a pontuação usual: letras no meio não são "limpas" em silêncio.
    if not re.fullmatch(r"[\d.\- ]*", cpf or ""):
        raise CpfInvalido("CPF inválido")
    digitos = re.sub(r"\D", "", cpf)
    if len(digitos) != 11 or digitos == digitos[0] * 11:
        raise CpfInvalido("CPF inválido")
    for tamanho in (9, 10):
        pesos = range(tamanho + 1, 1, -1)
        soma = sum(int(d) * peso for d, peso in zip(digitos[:tamanho], pesos, strict=True))
        verificador = (soma * 10) % 11 % 10
        if verificador != int(digitos[tamanho]):
            raise CpfInvalido("CPF inválido")
    return digitos


def validar_senha(senha: str, cpf_digitos: str) -> None:
    """Política mínima: tamanho, não ser comum, não repetir o CPF nem um só caractere."""
    if not isinstance(senha, str) or not (SENHA_MIN <= len(senha) <= SENHA_MAX):
        raise SenhaFraca(f"A senha precisa ter entre {SENHA_MIN} e {SENHA_MAX} caracteres.")
    if senha.lower() in SENHAS_COMUNS:
        raise SenhaFraca("Essa senha é muito comum. Escolha outra.")
    if cpf_digitos in re.sub(r"\D", "", senha):
        raise SenhaFraca("A senha não pode conter o seu CPF.")
    if len(set(senha)) < 3:
        raise SenhaFraca("Use uma senha com mais variedade de caracteres.")


@dataclass(frozen=True)
class Usuario:
    """Registro mínimo: nada de nome, CPF em claro ou dado de saúde (LGPD, art. 6º, III)."""

    id: UUID
    cpf_hmac: bytes
    senha_hash: str
    criado_em: datetime
    tentativas_falhas: int = 0
    bloqueado_ate: datetime | None = None


@dataclass(frozen=True)
class SessaoRefresh:
    """Refresh token guardado só como hash. `familia` liga as rotações de um mesmo login."""

    id: UUID
    usuario_id: UUID
    familia: UUID
    token_hash: bytes
    expira_em: datetime
    revogado_em: datetime | None = None
