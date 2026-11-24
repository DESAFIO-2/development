# ADR 0008 — Pipeline Multimodal Conservador da Semana 5 (Texto, PDF Digital e Áudio)

- **Data:** 2026-11-24
- **Status:** Implementado na branch `feat/semana5-multimodalidade` (aguardando revisão de PR e CI).
- **Complementa:** [ADR 0001](0001_enterprise_clean_architecture_and_rag.md), [ADR 0002](0002_mobile_first_react_native_client.md), [ADR 0004](0004_integridade_comparativo_semana3.md), [ADR 0005](0005_escopo_clinico_e_inspecao_pdf.md) e [ADR 0007](0007_orquestracao_semana4.md).

---

## 1. Contexto e Confronto com os ADRs Vigentes

O entregável da Semana 5 exige um **Agente Multimodal** capaz de processar pelo menos duas modalidades entre Texto, PDF, Áudio, Vídeo e Imagem, demonstrando o fluxo integrado e documentando limitações e casos de falha.

No projeto **SUS Cidadão (NavegaSUS)** existem duas restrições prévias de segurança e responsabilidade civil:
1. **[ADR 0002](0002_mobile_first_react_native_client.md):** veda submeter fotos de receitas manuscritas a OCR clínico em nuvem por risco jurídico/ético de erro algorítmico de leitura de caligrafia médica, prevendo suporte a **áudio via Whisper** na Semana 5 e preenchimento assistido por autocomplete.
2. **[ADR 0005](0005_escopo_clinico_e_inspecao_pdf.md):** estabelece portão defensivo em memória para PDFs (`backend/app/seguranca/arquivos.py`), alertando que a BFS estrutural em `pypdf` não constitui sandbox completo de CPU/memória para PDFs arbitrários.

## 2. Decisão Arquitetural

1. **Preservação integral do ADR 0002:** Não é implementado OCR de imagem sobre receitas manuscritas nem envio obrigatório de imagens médicas a APIs de nuvem.
2. **Três modalidades suportadas (superando o mínimo de duas):**
   - **Texto estruturado e dúvida administrativa** (fluxo existente endurecido na Fase 0);
   - **PDF digital nativo** (receitas digitais padrão CFM/ICP-Brasil, guias e pedidos SISREG digitais com camada textual extraída em memória via `PDFExtractorPort` / `pypdf`);
   - **Áudio de voz** (gravações curtas de cidadãos com Região Administrativa, dúvida ou nome de fármaco transcritas via `AudioTranscriberPort` com adaptadores plugáveis `faster_whisper` local ou `whisper_http` local; padrão `disabled` sem download automático em runtime).
3. **Reforço de segurança binária e textual (`OWASP LLM01` + `LGPD Art. 11`):**
   - Gate binário anterior à extração em `arquivos.py`: teto de bytes (`5 MB` PDF / `10 MB` áudio), máximo `10` páginas, bloqueio de conteúdo ativo (`/JavaScript`, `/AA`, `/Launch`, `/EmbeddedFile`, `/Encrypt`, `/OpenAction` ativo, BFS estrutural), teto de `20.000` caracteres extraídos do PDF e duração máxima de `60 s` no áudio (`AUDIO_VAZIO`, `AUDIO_LONGO_DEMAIS`), além de corte durante decodificação *streamed* de formatos comprimidos (`_MAX_PCM16_BYTES ~ 1,92 MB`).
   - Processamento **100% em memória e stateless**: parser HTTP dedicado `_InMemoryMultiPartParser` eleva `spool_max_size` acima do teto máximo de upload (`10 MB + 64 KB`) e rejeita partes excedentes com HTTP `413`, impedindo *spill* em `/tmp` do `MultiPartParser` padrão (`1 MB`); bytes nunca são gravados em disco, nem expostos em logs JSON, traces OpenTelemetry, LangSmith ou MLflow.
   - Todo texto extraído de PDF ou transcrito de áudio passa obrigatoriamente por: (a) `inspecionar_entrada` e detecção de `JAILBREAK` sobre o texto integral por canal (`Canal.PDF`, `Canal.VOZ`) + agregação de sinais fracos *cross-channel*; (b) `ClinicalGuardrail` (Ato Médico + prioridade absoluta SAMU `192`), com `texto_pdf_para_guardrail_clinico` poupando exclusivamente seções documentais do prescritor (`Justificativa clínica:`, `Uso oral:`, `Posologia:`) sem perguntas/comandos cidadãos; (c) `PIIMasker` (mascaramento de CPF, CNS, RG, CRM, CID-10, CEP, endereço, telefone, e-mail e nomes) antes do parser ou orquestrador; e (d) `validar_saida`.
4. **Blindagem determinística preservada:**
   - As rotas existentes `POST /api/v1/prescriptions/audit` e `POST /api/v1/agents/orchestrate` permanecem 100% preservadas; a entrada multimodal é aditiva em `POST /api/v1/agents/multimodal` (`multipart/form-data`).
   - `CitizenGuidanceCard` continua 100% determinístico. Candidatos vindos de áudio, com desvio ortográfico (`sugerir_correcao_ortografica`) ou concentração ambígua disparam `requer_confirmacao_usuario = true` com opções do autocomplete oficial, jamais chutando cobertura SUS silenciosamente.
   - PDFs puramente escaneados (sem camada textual) retornam falha controlada (`PDF_SEM_TEXTO_DIGITAL`) orientando o preenchimento assistido.

## 3. Consequências, Limites e Reversão

- **Dependências:** `pypdf` já integra o lockfile principal. `faster-whisper` entra apenas como extra opcional (`[project.optional-dependencies] stt`) para manter a imagem Docker padrão leve.
- **Limites conhecidos:** PDFs escaneados sem texto são recusados com abstenção segura; ruído/sotaque severo em áudio pode exigir confirmação ou nova gravação; em CPU local, a transcrição Whisper soma latência variável que precisa ser medida explicitamente frente à meta `RNF04` (`p95 <= 8 s`).
- **Reversão:** Reverter os commits da feature multimodal (`git revert`) remove a rota `/api/v1/agents/multimodal`, casos de uso e adaptadores novos sem impactar `/prescriptions/audit`, `/agents/orchestrate` ou o corpus `v10`.

## Endurecimento após revisão independente (2026-11-24)

- Forma farmacêutica explícita incompatível não é descartada para obter cobertura.
- Confirmação entre PDF e voz exige a mesma apresentação (DCB, concentração e forma).
  O booleano de confirmação não resolve ambiguidade de catálogo: o cliente deve enviar
  a apresentação escolhida em `itens_json`. Ao reenviar o PDF, uma seleção única
  compatível com os candidatos do catálogo resolve a pendência; uma concentração
  inexistente não resolve a ambiguidade.
- Novos medicamentos sem numeração encerram a seção de posologia quando reconhecidos
  pelo catálogo. Comandos imperativos e relatos pessoais de emergência permanecem
  inspecionáveis nas seções documentais. A classificação é heurística, não universal.
- Inspeção clínica de PDF usa o limite do canal PDF, sem reaplicar o teto de texto.
- Erros 422 excluem entrada bruta e contexto de exceção, evitando eco de PII e erros 500.
- pypdf >= 7 aplica limites contextuais de 256 KiB por stream, 512 KiB de trabalho de
  decodificação e 20.000 unidades de parsing. Extrações são serializadas por processo;
  PDFs truncados são recusados. Isso reduz amplificação e pode recusar PDFs legítimos
  complexos; não constitui sandbox de CPU/RAM nem limite global de memória do servidor.
- O runner multimodal retorna falha quando o gate funcional ou RNF04 reprova.

Validação local: 518 testes backend aprovados offline (incluindo regressões
adversariais, parser, confirmação estruturada e runner multimodal), Ruff, Mypy e
Bandit (`-ll`) aprovados. Smoke sintético permanece teste de protocolo. Whisper
`base` continua sujeito à limitação de reconhecimento de losartana descrita no
entregável; estas correções não constituem melhoria medida de ASR nem validação
com fala humana.

O fechamento pós-revisão substituiu o filtro textual simples por separação entre
seção narrativa clínica (`clinica`) e instrução posológica (`posologia`), restringiu
exceções documentais a fracionamento posológico impessoal sem escalonamento e a
justificativas eletivas sem relato pessoal ou urgência aguda, bloqueou menções
negadas/alérgicas fora e dentro de seções, preservou itens catalogados ou com
concentração explícita após posologia sem numeração, vinculou `itens_json` à
apresentação completa (inclusive por `nome_digitado`, forma alternativa e erro
ortográfico) com bloqueio de divergências de dose entre PDF e voz não arbitradas,
e adicionou deduplicação canônica no merge final. A classificação continua
heurística: os testes não certificam compreensão de toda linguagem clínica.
