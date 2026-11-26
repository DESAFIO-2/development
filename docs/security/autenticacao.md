# Autenticação e proteções da API (RemedIA)

Branch `feat/seguranca`. Este documento registra o que foi implementado, por quê, como configurar e o que ainda falta.

## Regra geral: rígido fora do local

| Proteção | `APP_ENVIRONMENT=local` | Qualquer outro ambiente | Forçar |
| --- | --- | --- | --- |
| Login nas rotas sensíveis | opcional (sem token = anônimo; token inválido = 401) | obrigatório | `APP_AUTH_OBRIGATORIA` |
| Rate limit por IP | desligado | ligado | `APP_RATE_LIMIT_ATIVO` |
| `/docs`, `/redoc`, `/openapi.json` | expostos | 404 | `APP_EXPOR_DOCS` |
| HSTS | não | sim | — |
| Banco e segredos | opcionais (memória e chaves aleatórias por subida) | obrigatórios: a API não sobe sem eles | — |

Com isso, testes, DAST (`make dast`) e os runners de `evals/` continuam rodando no local sem token.

## Rotas

Públicas: `GET /health` e `GET /api/v1/medications/autocomplete`.

Com login: `POST /api/v1/prescriptions/audit`, `POST /api/v1/agents/orchestrate`, `POST /api/v1/agents/multimodal`, `GET /api/v1/pharmacies/nearby` (recebe a localização) e `GET /api/v1/ceaf-stock`.

Autenticação (`/api/v1/auth`):

| Rota | Corpo | Resposta |
| --- | --- | --- |
| `POST /cadastro` | `{cpf, senha}` | 201 + tokens; 409 se o CPF já tem conta; 422 se CPF/senha inválidos |
| `POST /login` | `{cpf, senha}` | 200 + tokens; 401 com mensagem única |
| `POST /refresh` | `{refresh_token}` | 200 + par novo; o refresh usado deixa de valer |
| `POST /sair` | `{refresh_token}` | 204 (idempotente) |
| `GET /eu` | `Authorization: Bearer` | `{id}` |

## Decisões

- **Dados mínimos (LGPD, art. 6º, III).** O banco guarda só `HMAC-SHA256(CPF, pimenta)` e o hash Argon2id da senha. Nome, celular, CNS e demais dados do cadastro ficam só no aparelho, cifrados no SecureStore.
- **Senha.** Argon2id (argon2-cffi, perfil RFC 9106 de baixa memória), de 8 a 128 caracteres. São recusadas as senhas mais comuns, as que contêm o CPF e as com menos de 3 caracteres distintos (NIST SP 800-63B). O hash é refeito no login quando os parâmetros mudam.
- **Tokens.** O access token é um JWT HS256 de 15 minutos, validado sem consulta ao banco, com `iss`, `aud`, `exp`, `nbf`, `jti` e `typ` obrigatórios e algoritmo fixo (`none` é recusado). O refresh é opaco (256 bits), guardado só como SHA-256, vale 30 dias e é trocado a cada uso.
- **Reuso de refresh = roubo.** Reapresentar um refresh já trocado, ou duas trocas simultâneas do mesmo token, revoga a família inteira daquele login. Outros aparelhos do mesmo usuário não são afetados.
- **Sem enumeração.** A mensagem é sempre "CPF ou senha inválidos.", e o hash é verificado mesmo quando o CPF não existe, para o tempo de resposta não revelar quem tem cadastro. O cadastro ainda responde 409 para CPF existente: é o custo de dizer ao cidadão por que não deu certo, mitigado pelo rate limit de 5/min.
- **Bloqueio.** Após 5 falhas seguidas, a conta fica bloqueada por 15 minutos, mesmo com a senha certa. O contador é atômico no Postgres.
- **Token só no cabeçalho `Authorization`**, nunca em cookie. Por isso CSRF não se aplica, e o CORS segue com `allow_credentials=False`.

## Proteções de borda (`backend/app/api/protecao.py`)

- **Teto de corpo:** 64 KB nas rotas JSON e cerca de 16 MB no multimodal. Responde 413 pelo `Content-Length` e também conta os bytes quando o envio vem em partes.
- **Rate limit:** janela de 60 s por IP: 120/min nas rotas gerais, 20/min nas pesadas (auditoria, orquestração, multimodal) e 5/min no `/auth`. Responde 429 com `Retry-After`. Fica em memória e vale por réplica; em produção, repita a regra no proxy/gateway.
- **Atrás de proxy:** rode o uvicorn com `--proxy-headers --forwarded-allow-ips=<ip do proxy>`. Assim o IP é o do cliente real, sem confiar em qualquer `X-Forwarded-For`.
- **Cabeçalhos:** `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store` (as respostas trazem dado de saúde), `Permissions-Policy`, CSP `default-src 'none'` (fora da UI do `/docs`) e HSTS fora do local.

## App (`mobile/`)

- O refresh token fica no `expo-secure-store` (Keychain/Keystore, `WHEN_UNLOCKED_THIS_DEVICE_ONLY`, sem backup). O access token fica só em memória.
- Ao abrir o app com sessão salva, ele não entra sozinho: pede a biometria do aparelho ou a senha. Sem biometria cadastrada no aparelho, só a senha entra.
- Depois de 5 minutos em segundo plano, o app bloqueia.
- Fora do `expo start` (build de produção), toda chamada que não for HTTPS é bloqueada.
- Sair revoga a sessão na API e apaga o refresh e o perfil do aparelho.
- O campo de senha não usa corretor nem sugestões, e a tela de login limpa a senha após cada tentativa.
- Na web não há armazenamento seguro equivalente: a sessão fica só em memória e cai ao recarregar a página.

## Rodar localmente com Postgres

```bash
# .env da raiz
POSTGRES_PASSWORD=<gere com: python -c "import secrets; print(secrets.token_urlsafe(24))">

make db-up

# backend/.env
APP_DATABASE_URL=postgresql://remedia:<mesma senha>@127.0.0.1:5432/remedia
APP_AUTH_JWT_SECRET=<python -c "import secrets; print(secrets.token_urlsafe(48))">
APP_AUTH_CPF_PEPPER=<outro valor gerado do mesmo jeito>

make run-api
```

O schema é criado na subida (`CREATE TABLE IF NOT EXISTS`). Para os testes de contrato contra o banco: `APP_TESTE_DATABASE_URL=<dsn> make test-db`. Cada teste cria e apaga um schema próprio.

## Checklist de produção

- [ ] `APP_ENVIRONMENT` diferente de `local`.
- [ ] `APP_DATABASE_URL`, `APP_AUTH_JWT_SECRET` e `APP_AUTH_CPF_PEPPER` num cofre de segredos, nunca no repositório.
- [ ] O pepper com backup tão protegido quanto o banco: perder ou trocar o pepper invalida todos os cadastros.
- [ ] TLS terminando no proxy, uvicorn com `--proxy-headers --forwarded-allow-ips`.
- [ ] Rate limit também no proxy/gateway, se houver mais de uma réplica.
- [ ] `EXPO_PUBLIC_API_URL` com `https://` no build do app.

## Limitações conhecidas e próximos passos

- **Revogação do access token:** depois de "sair", o access token emitido continua válido até expirar (no máximo 15 minutos), porque é validado sem consulta ao banco.
- **Login em aparelho novo:** o perfil exibido é o de demonstração (`mobile/src/data/mock.ts`) com o CPF da pessoa, porque o perfil completo só existe no aparelho onde foi feito o cadastro. Definir com o time se o perfil passa a ser sincronizado, cifrado, pela API.
- **DAST:** o `make dast` sobe a API com `APP_AUTH_OBRIGATORIA=true`, cadastra um usuário sintético e passa o token ao ZAP (`ZAP_AUTH_HEADER_VALUE`) e ao Schemathesis (`-H`). Assim o ZAP e o Schemathesis exercitam a autenticação de verdade. O rate limit segue desligado no DAST, senão o fuzzing viraria uma sequência de 429. O Postgres fica de fora: a API do DAST usa o repositório em memória.
- **Recuperação de senha:** "Esqueci minha senha" continua simulado. Depende de um canal verificado (SMS/e-mail/gov.br).
- **Login gov.br:** continua planejado. Com ele, a senha local pode virar alternativa.
## Achados já corrigidos (primeira execução no CI, PR #42)

- **Trivy:** CVE-2026-124851 (alta) na `libzstd1` da imagem `python:3.12-slim`. O Dockerfile passa a aplicar `apt-get upgrade` no build.
- **Schemathesis ST401:** um cabeçalho `Authorization` presente mas não Bearer (ex.: `Basic ...`) era tratado como anônimo no modo local. Agora recebe 401 em qualquer modo.
- **Schemathesis ST108:** o 422 do cadastro devolvia `detail` em texto, fora do contrato. O OpenAPI agora documenta os dois formatos.
- **Semgrep, Gitleaks e `npm audit`:** sem achados.
