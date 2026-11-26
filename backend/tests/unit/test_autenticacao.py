"""Serviço de autenticação sobre o repositório em memória (mesmo contrato do Postgres)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from argon2 import PasswordHasher

from app.application.autenticacao import (
    AutenticacaoService,
    CadastroIndisponivel,
    ConfigAutenticacao,
    CredenciaisInvalidas,
    TokenInvalido,
)
from app.domain.usuario import CpfInvalido, SenhaFraca, normalizar_cpf, validar_senha
from app.infrastructure.persistence.repositories.usuario_repository import (
    MemoriaUsuarioRepository,
)

# CPFs sintéticos com dígitos verificadores válidos (gerados para teste).
CPF = "529.982.247-25"
CPF_2 = "168.995.350-09"
SENHA = "girassol-azul-42"
SEGREDO = b"s" * 32
PIMENTA = b"p" * 32


class Relogio:
    def __init__(self) -> None:
        self.agora = datetime.now(UTC)

    def __call__(self) -> datetime:
        return self.agora


def _config(**extra: object) -> ConfigAutenticacao:
    base: dict[str, object] = {
        "jwt_secret": SEGREDO,
        "cpf_pepper": PIMENTA,
        "issuer": "remedia-api",
        "audience": "remedia-app",
        "access_ttl": timedelta(minutes=15),
        "refresh_ttl": timedelta(days=30),
        "max_tentativas": 3,
        "bloqueio": timedelta(minutes=15),
    }
    base.update(extra)
    return ConfigAutenticacao(**base)  # type: ignore[arg-type]


@pytest.fixture
def relogio() -> Relogio:
    return Relogio()


@pytest.fixture
def repo() -> MemoriaUsuarioRepository:
    return MemoriaUsuarioRepository()


@pytest.fixture
def svc(repo: MemoriaUsuarioRepository, relogio: Relogio) -> AutenticacaoService:
    # Argon2 leve só nos testes, para a suíte continuar rápida.
    hasher = PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1)
    return AutenticacaoService(repo, _config(), hasher=hasher, relogio=relogio)


# --- Domínio ------------------------------------------------------------------


@pytest.mark.parametrize("cpf", [CPF, "52998224725", " 529 982 247 25 "])
def test_cpf_valido_e_normalizado(cpf: str) -> None:
    assert normalizar_cpf(cpf) == "52998224725"


@pytest.mark.parametrize("cpf", ["", "123", "111.111.111-11", "529.982.247-26", "5299822472a5x"])
def test_cpf_invalido(cpf: str) -> None:
    with pytest.raises(CpfInvalido):
        normalizar_cpf(cpf)


@pytest.mark.parametrize(
    "senha",
    ["curta", "x" * 129, "12345678", "Senha123", "aaaaaaaaaa", "ab52998224725"],
)
def test_senha_fraca(senha: str) -> None:
    with pytest.raises(SenhaFraca):
        validar_senha(senha, "52998224725")


def test_senha_aceita() -> None:
    validar_senha(SENHA, "52998224725")


def test_config_recusa_segredo_curto() -> None:
    with pytest.raises(ValueError, match="JWT_SECRET"):
        _config(jwt_secret=b"curto")
    with pytest.raises(ValueError, match="CPF_PEPPER"):
        _config(cpf_pepper=b"curto")


# --- Cadastro e login -----------------------------------------------------------


def test_cadastro_guarda_so_hmac_do_cpf_e_hash_argon2id(
    svc: AutenticacaoService, repo: MemoriaUsuarioRepository
) -> None:
    tokens = svc.cadastrar(CPF, SENHA)
    (usuario,) = repo._usuarios.values()
    assert b"52998224725" not in usuario.cpf_hmac
    assert len(usuario.cpf_hmac) == 32
    assert usuario.senha_hash.startswith("$argon2id$")
    assert SENHA not in usuario.senha_hash
    assert svc.validar_access(tokens.access_token) == usuario.id


def test_cadastro_duplicado(svc: AutenticacaoService) -> None:
    svc.cadastrar(CPF, SENHA)
    with pytest.raises(CadastroIndisponivel):
        svc.cadastrar("52998224725", "outra-senha-boa")


def test_login_ok_com_cpf_em_qualquer_formato(svc: AutenticacaoService) -> None:
    svc.cadastrar(CPF, SENHA)
    assert svc.entrar("52998224725", SENHA).access_token


@pytest.mark.parametrize(
    ("cpf", "senha"),
    [(CPF, "senha-errada!"), (CPF_2, SENHA), ("123", SENHA), ("111.111.111-11", SENHA)],
)
def test_login_recusado_sempre_com_o_mesmo_erro(
    svc: AutenticacaoService, cpf: str, senha: str
) -> None:
    svc.cadastrar(CPF, SENHA)
    with pytest.raises(CredenciaisInvalidas):
        svc.entrar(cpf, senha)


def test_bloqueio_apos_falhas_e_liberacao_depois(
    svc: AutenticacaoService, relogio: Relogio
) -> None:
    svc.cadastrar(CPF, SENHA)
    for _ in range(3):
        with pytest.raises(CredenciaisInvalidas):
            svc.entrar(CPF, "senha-errada!")
    # Bloqueado: nem a senha certa entra.
    with pytest.raises(CredenciaisInvalidas):
        svc.entrar(CPF, SENHA)
    relogio.agora += timedelta(minutes=16)
    assert svc.entrar(CPF, SENHA).access_token


def test_acerto_zera_o_contador_de_falhas(
    svc: AutenticacaoService, repo: MemoriaUsuarioRepository
) -> None:
    svc.cadastrar(CPF, SENHA)
    for _ in range(2):
        with pytest.raises(CredenciaisInvalidas):
            svc.entrar(CPF, "senha-errada!")
    svc.entrar(CPF, SENHA)
    (usuario,) = repo._usuarios.values()
    assert usuario.tentativas_falhas == 0


def test_login_rehash_quando_parametros_mudam(repo: MemoriaUsuarioRepository) -> None:
    fraco = PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1)
    AutenticacaoService(repo, _config(), hasher=fraco).cadastrar(CPF, SENHA)
    forte = PasswordHasher(time_cost=2, memory_cost=2048, parallelism=1)
    AutenticacaoService(repo, _config(), hasher=forte).entrar(CPF, SENHA)
    (usuario,) = repo._usuarios.values()
    assert "m=2048,t=2" in usuario.senha_hash


# --- Refresh ----------------------------------------------------------------------


def test_refresh_troca_o_par_e_invalida_o_usado(svc: AutenticacaoService) -> None:
    t1 = svc.cadastrar(CPF, SENHA)
    t2 = svc.renovar(t1.refresh_token)
    assert t2.refresh_token != t1.refresh_token
    assert svc.validar_access(t2.access_token)


def test_reuso_de_refresh_derruba_o_login_inteiro(svc: AutenticacaoService) -> None:
    t1 = svc.cadastrar(CPF, SENHA)
    t2 = svc.renovar(t1.refresh_token)
    # Alguém reapresenta o refresh antigo (vazado): os dois perdem a sessão.
    with pytest.raises(CredenciaisInvalidas):
        svc.renovar(t1.refresh_token)
    with pytest.raises(CredenciaisInvalidas):
        svc.renovar(t2.refresh_token)


def test_reuso_nao_afeta_outro_login_do_mesmo_usuario(svc: AutenticacaoService) -> None:
    celular = svc.cadastrar(CPF, SENHA)
    tablet = svc.entrar(CPF, SENHA)
    svc.renovar(celular.refresh_token)
    with pytest.raises(CredenciaisInvalidas):
        svc.renovar(celular.refresh_token)
    assert svc.renovar(tablet.refresh_token).access_token


def test_refresh_expirado(svc: AutenticacaoService, relogio: Relogio) -> None:
    t1 = svc.cadastrar(CPF, SENHA)
    relogio.agora += timedelta(days=31)
    with pytest.raises(CredenciaisInvalidas):
        svc.renovar(t1.refresh_token)


def test_refresh_desconhecido(svc: AutenticacaoService) -> None:
    with pytest.raises(CredenciaisInvalidas):
        svc.renovar("x" * 43)


def test_sair_revoga_e_e_idempotente(svc: AutenticacaoService) -> None:
    t1 = svc.cadastrar(CPF, SENHA)
    svc.sair(t1.refresh_token)
    svc.sair(t1.refresh_token)
    svc.sair("token-que-nunca-existiu-0000000000")
    with pytest.raises(CredenciaisInvalidas):
        svc.renovar(t1.refresh_token)


# --- Access token ---------------------------------------------------------------


def test_access_expirado(svc: AutenticacaoService, relogio: Relogio) -> None:
    relogio.agora -= timedelta(hours=1)
    tokens = svc.cadastrar(CPF, SENHA)
    with pytest.raises(TokenInvalido):
        svc.validar_access(tokens.access_token)


def test_access_adulterado_ou_de_outra_chave(svc: AutenticacaoService) -> None:
    tokens = svc.cadastrar(CPF, SENHA)
    cabeca, corpo, assinatura = tokens.access_token.split(".")
    adulterado = f"{cabeca}.{corpo}.{assinatura[:-2]}AA"
    claims = jwt.decode(tokens.access_token, options={"verify_signature": False})
    outra_chave = jwt.encode(claims, b"o" * 32, algorithm="HS256")
    for token in (adulterado, outra_chave, "", "a.b.c", tokens.refresh_token):
        with pytest.raises(TokenInvalido):
            svc.validar_access(token)


def test_access_alg_none_e_recusado(svc: AutenticacaoService) -> None:
    tokens = svc.cadastrar(CPF, SENHA)
    claims = jwt.decode(tokens.access_token, options={"verify_signature": False})
    sem_assinatura = jwt.encode(claims, None, algorithm="none")
    with pytest.raises(TokenInvalido):
        svc.validar_access(sem_assinatura)


@pytest.mark.parametrize(
    ("campo", "valor"), [("aud", "outro-app"), ("iss", "outra-api"), ("typ", "refresh")]
)
def test_access_com_claim_trocada(svc: AutenticacaoService, campo: str, valor: str) -> None:
    tokens = svc.cadastrar(CPF, SENHA)
    claims = jwt.decode(tokens.access_token, options={"verify_signature": False})
    claims[campo] = valor
    with pytest.raises(TokenInvalido):
        svc.validar_access(jwt.encode(claims, SEGREDO, algorithm="HS256"))
