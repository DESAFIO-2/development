# Revisão independente da portação pré-Semana 4 — 17/11/2026

**Registro histórico da revisão, anterior às correções.** Os achados abaixo motivaram a correção autorizada pelo usuário; o estado atual e as validações estão no [registro atualizado da portação](portacao_curada_de_ds_semana4.md).

**Parecer original: requer alterações antes de integrar em `main`.** A portação tem benefícios verificáveis, mas introduziu regressões de correspondência e de guardrail. Os testes existentes passam sem cobrir esses defeitos. A integração multiagente continua adiada, conforme solicitado.

## Escopo e identificação

- Conversa examinada: anexo `Texto colado.txt` fornecido nesta revisão, incluindo proposta, autorização e relato de execução.
- Destino: branch `feat/pre-semana4-portacao-curada-de-ds`, HEAD `57859c81370befdf70b87ede4006b106db3d1449`; alterações da portação ainda não commitadas. `main` no GitHub confirma esse mesmo SHA.
- Data-Science: `d1f8fe1bf43b7c45e88d6b6907166845d0281601`, confirmado como `main` remoto; arquivos consultados pelo conector GitHub com ref imutável.
- Engenharia de Dados: `8d76f923354a4707810be38e238a8a3ea035554e`, confirmado por `git ls-remote` e clone isolado em `/private/tmp/portacao-review-data-engineering`.
- Código, dados e arquivos locais preexistentes foram preservados. Esta revisão acrescenta este relatório e reproduções em `output/revisao-portacao-2026-11-17/`; não corrige silenciosamente o objeto da revisão, não faz commit, push ou merge.

## Achados reproduzidos

### R1 — P1: associação intercalada perde a ligação entre ingrediente e dose

Local: `backend/app/retrieval/tabular_matcher.py:126–131`.

`clavulanato de potássio 500 mg + amoxicilina 125 mg` é aprovado pela API como `AMOXICILINA + CLAVULANATO DE POTÁSSIO`, rota `UBS_REME_DF`. A apresentação encontrada tem **amoxicilina 500 mg e clavulanato 125 mg**. O extrator concatena as doses pela ordem de aparição e o matcher verifica os nomes como conjunto, sem vincular cada dose ao ingrediente correspondente.

Na base anterior, a extração retornava duas doses e o caso de uso se abstinha. Na origem DE, `_interleaved_association_matches` associa `components` e `doses` com `zip(..., strict=True)` antes de construir o padrão. Essa garantia se perdeu na adaptação.

Correção necessária: interpretar pares ingrediente–concentração e confirmar a composição completa contra o catálogo. Cobrir inversão legítima da ordem com doses corretas, inversão incorreta, componentes extras/ausentes e associações com três componentes.

### R2 — P1: normalização apaga contradições explícitas da apresentação

Local: `backend/app/retrieval/tabular_matcher.py:96–104`.

Reprodução pela API, usando `concentracao` estruturada:

- `maleato de timolol` + `5 mg/mL (99%)` retorna `UBS_REME_DF`, apesar de o registro encontrado informar `5 mg/mL (0,5%)`.
- `acetato de desmopressina` + `0,1 mg/mL (frasco 999 mL)` retorna `FARMACIA_ALTO_CUSTO`; o matcher aceita o registro de frasco de `2,5 mL`.

O código remove os sufixos tanto da consulta quanto do catálogo e compara apenas a presença da palavra `frasco`, não seu conteúdo. O matcher anterior rejeitava essas concentrações. A origem DE não removia percentuais em `strength_core`; a adaptação ampliou a regra.

Correção necessária: permitir omissão de detalhe documental sem apagar conflito explícito; validar percentual, volume e dispositivo quando fornecidos. Não inferir equivalências químicas para fazer o teste passar.

### R3 — P1: bloqueio clínico passa a impedir navegação administrativa legítima

Local principal: `backend/app/guardrails/clinical.py:120–123`; há também o novo padrão geral de reação adversa.

Antes: permitidas. Depois: bloqueadas pelo guardrail:

- `Como usar a Farmácia Popular?`
- `Como usar o SUS?`
- `Como usar uma procuração para retirar medicamentos?`
- `Onde notifico uma reação adversa?`

O padrão `como usar` usa uma lista estreita de exceções e não exige objeto terapêutico. O padrão de reação adversa não distingue orientação clínica de encaminhamento administrativo para notificação. Isso afeta diretamente o consultor normativo planejado para a Semana 4.

Correção necessária: classificação contextual/composicional, preservando bloqueio de pedidos clínicos misturados à pergunta administrativa e prioridade de emergência. Acrescentar testes administrativos negativos junto dos 19 positivos portados.

### R4 — P2: consolidação perde consultas anteriormente reconhecidas

Local: `backend/app/ingestion/consolidate_curated_corpus.py:142–146` e `166–170`, em conjunto com as equivalências do matcher.

`dipropionato de beclometasona 50 mcg` e `dipropionato de beclometasona 250 mcg` antes encontravam registros `FARMACIA_POPULAR`; agora a API retorna `NAO_PADRONIZADO`. Os aliases fundem `50mcg`/`250mcg` em registros `mcg/dose`, mas a busca não reconhece as grafias originais. As ocorrências F04 preservadas no staging ainda contêm literalmente `50mcg` e `250mcg`.

Correção necessária: validar documentalmente os aliases de concentração/forma e preservar as consultas originais por mapeamento explícito, considerando a distinção oral/nasal. O total de 41 registros não basta para demonstrar que todas as apresentações continuam recuperáveis.

### R5 — P2: correção anunciada para sacubitril só cobre o nome completo

Local: `backend/app/retrieval/tabular_matcher.py:118–123`.

`nome_digitado="sacubitril valsartana 97/103 mg"`, `concentracao="200 mg"` continua retornando `NAO_PADRONIZADO`, exatamente o exemplo apontado na conversa inicial. O teste novo utiliza `sacubitril valsartana sódica hidratada`, fazendo a equivalência funcionar apenas nessa variante. `doses_compativeis` exige todos os tokens longos da chave, inclusive `sodica` e `hidratada`, embora o matcher permita omiti-los.

É uma lacuna preexistente parcialmente corrigida, não uma nova regressão. Vincular a equivalência ao candidato canônico validado e testar a entrada original, sem aceitar nomes de outros medicamentos.

## O que foi confirmado positivamente

- 1.703 IDs canônicos únicos; 2.087 IDs de ocorrência preservados exatamente em relação ao HEAD, sem perda nem duplicação. Distribuição: 866 UBS, 478 CEAF, 318 hospitalares e 41 Farmácia Popular.
- 2.114 chunks com IDs e occurrence IDs únicos. Todas as 2.087 ocorrências do catálogo possuem evidência correspondente.
- Pipeline executado em cópia temporária de `data/`: catálogo, normativos e evidence chunks reproduzidos **byte a byte**. O timestamp do manifesto é volátil; a versão textual continua `2026.4.0`, embora o hash do catálogo tenha mudado.
- Atualização de estoque igual ao JSON do Data-Science no SHA fixado (comparação do conteúdo JSON completo, zero linhas divergentes). Os totais por status conferem com os registros.
- Recuperação de captopril/sinvastatina e casos novos positivos cobertos na suíte existente passam.
- `tipo_prescritor` passou a ser inspecionado pelo guardrail.
- Dockerfile e dockerignore incluem o arquivo de evidências.
- Não houve portação do grafo, da memória SQLite, da voz nem do avaliador sintético proibido.

## Correções necessárias no relato de entrega e nos contratos

1. **Evidências preparadas, ainda não consumidas:** `build_services()` carrega o repositório de evidências, mas passa somente `chunk_repo` (20 normativos) ao `HybridRetriever`. `AuditPrescriptionUseCase` não recebe nem consulta `evidence_chunk_repo`. Portanto, não afirmar que os 2.114 chunks já melhoraram o RAG ou as citações da API. A dependência virou obrigatória no startup/health antes de ter consumidor funcional.
2. **Contrato para os agentes:** não há `EvidenceRepositoryPort`; o repositório é concreto. `medicine_id` de origem não é o `medication_id` canônico do development. Usar os `occurrence_ids` preservados para juntar catálogo e evidência. A busca por ID de medicamento exige explicitar qual namespace recebe. O DTO também descarta a URL da fonte. Não converter presença documental em comprovação de regras administrativas ou clínicas.
3. **Sugestão ortográfica:** existe como método testado, mas não é chamada pela API. Desambiguação progressiva ainda não foi implementada: o caso de uso continua escolhendo `matches[0]` quando há candidatos.
4. **Estoque:** o relatório afirma 286 apresentações distintas; o JSON declara 294 descrições e contém 290 códigos distintos. Há datas por registro de 05/11 e 16/11, apesar do timestamp geral de 16/11. É snapshot, não estoque atual confirmado. Continua sem consumidor ativo e sem hash de estoque no manifesto principal.
5. **Aprovação humana e aliases:** o manifesto anterior delimita aprovação à presença documental e registra revisão humana específica da claritromicina. Isso não aprova automaticamente os novos aliases (por exemplo, `insulina humana` → `insulina humana nph`) nem as regras de dispensação. Registrar evidência/decisão por alias e revisão dos responsáveis.
6. **Reversão:** `git checkout main` não reverte alterações não commitadas e pode carregá-las para outra branch. O registro precisa de reversão por commit real após commit/PR e preservação explícita do trabalho local antes disso. O placeholder de SHA atual não é um procedimento executável.
7. **ADR:** CONTRIBUTING exige ADR para alterações estruturais de recuperação/guardrails; nenhum ADR acompanha este diff. Registrar a decisão e o alcance da normalização e das evidências.

## Pré-exames: decisão de não portar foi adequada

No [pipeline DS no SHA revisado](https://github.com/DESAFIO-2/Data-Science/blob/d1f8fe1bf43b7c45e88d6b6907166845d0281601/src/sus_cidadao_ds/ingestion/pdf_pipeline.py), `convert_pre_exam_protocols` escreve os textos dos chunks JSON em PDF com título de guia oficial. O mesmo pipeline possui materialização de PDFs com texto embutido quando o download falha. Isso não constitui fonte primária independente.

O [levantamento de fontes da mesma revisão](https://github.com/DESAFIO-2/Data-Science/blob/d1f8fe1bf43b7c45e88d6b6907166845d0281601/specs/levantamento-fontes.md) limita F12 a documentos e preparo comunicado no agendamento; não sustenta horas específicas de jejum. Confirmei a justificativa para rejeitar os chunks. O código, isoladamente, não prova quem escreveu o texto nem que ele foi gerado por IA; o defeito verificável é a falta de lastro primário para as afirmações.

## Validações executadas nesta revisão

`uv` não está no PATH desta sessão. Usei os ambientes `.venv` existentes, sem reinstalar dependências; portanto não atribuir estes resultados a uma nova sincronização `uv --locked`.

| Checagem | Resultado |
| --- | --- |
| `cd backend && .venv/bin/python -m pytest -q` | 290 passed |
| `evals/.venv/bin/python -m pytest evals/tests -q` | 1 passed |
| Ruff check backend/evals/observability | Passou |
| Ruff format --check | 102 arquivos já formatados |
| Mypy com os caminhos de CONTRIBUTING | 99 arquivos, sem erros |
| `validar_datasets.py` | 5 datasets íntegros |
| Guardrail clínico no dataset existente | Recall 100%, falso bloqueio 0% nesse conjunto |
| Anti-injection em `injecao_v1.jsonl` | Recall 100%, falso bloqueio 0% nesse conjunto |
| Golden v1 (16 casos) e v2 (22 casos) | Gates determinísticos passaram; não medem geração por LLM |
| `comparar_semana3.py --synthetic-smoke` | 0 pares inválidos; RAGAS/factualidade NÃO AVALIADOS |
| `suite_seguranca.py --synthetic-smoke --fail-on-api-elim` | API real C: 4/4 em cada dimensão; A/B/D são fixtures |
| Reproduções adicionais de revisão | 10 contraexemplos/lacunas registrados; não são estimativa de desempenho |
| Docker build/smoke | NÃO EXECUTADO: daemon indisponível (`docker.sock` ausente) |
| Nova avaliação com LLM real / RAGAS oficial | NÃO EXECUTADA; não confundir com smoke |

Reprodução dos achados, a partir da raiz:

```bash
PYTHONPATH=backend backend/.venv/bin/python output/revisao-portacao-2026-11-17/reproduzir.py
```

Saída observada preservada em `output/revisao-portacao-2026-11-17/resultados.json`. `ok=false` evidencia o desvio esperado nesta revisão. Os resultados do protocolo sintético estão em `/private/tmp/portacao-review-smoke` e `/private/tmp/portacao-review-security`. Os runners determinísticos também reexecutam seus relatórios locais ignorados pelo Git.

## Condições para receber a Semana 4

1. Corrigir R1–R4, fechar R5 e acrescentar regressões positivas e negativas no consumidor HTTP. Revisar aliases com responsáveis pelos dados, sem perseguir contagem fixa como meta de qualidade.
2. Publicar contrato de integração: evidências por occurrence ID, distinção entre catálogo e normas, resposta a `pergunta_adicional`, desambiguação, elegibilidade por prescritor e escopo real de estoque. Atualmente pergunta adicional só é inspecionada; tipo de prescritor não decide elegibilidade.
3. Preservar decisões determinísticas e sanitização; aplicar validação de saída à geração futura. Exigir testes de falha/timeout, emergência, prompt injection, PII, isolamento e exclusão de sessões quando a memória chegar. Fallback de produção deve ser explícito; avaliação não pode mascarar falha de provedor.
4. Corrigir documentação, ADR, rastreabilidade dos aliases e reversão; executar build/smoke Docker e CI no commit final e obter revisão do squad conforme CONTRIBUTING/CODEOWNERS.
5. Portar o grafo do colega somente quando estabilizado e fixado em SHA, sem trazer automaticamente corpus antigo, PDFs materializados, avaliação sintética ou infraestrutura desnecessária. A curadoria pendente de `CHK-COMP-PFPB-003`, já registrada na portação v9, também continua pendente.

Há uma base aproveitável para trabalhar nos agentes, mas não evidência para declarar esta portação pronta para merge ou a Semana 4 integralmente validada. Esta é revisão de código, dados e comportamento; não substitui auditoria humana integral de cada documento primário nem avaliação científica dos agentes futuros.
