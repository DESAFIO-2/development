# ADR 0005 — Escopo de exceções clínicas e inspeção limitada de PDF

- Status: implementado; validação do container pendente de ambiente Docker/CI.
- Data: 2026-11-16.
- Escopo: correção pré-Semana 4, sem ativar multiagentes ou mudar o corpus.

## Problema

A presença de uma expressão administrativa liberava toda a cláusula, inclusive
pedidos de alteração de dose. A busca literal por sinais de emergência também
bloqueava perguntas logísticas com negação explícita ou histórico. Na inspeção
de PDFs, limites de profundidade e erros de resolução eram ignorados, permitindo
aprovar arquivos com partes não inspecionadas.

## Decisão

- Exceções administrativas removem somente os gatilhos ambíguos de horário e
  esquecimento quando acompanhados de contexto explícito. Seus objetos e verbos
  vizinhos continuam sujeitos às regras, sem criar uma fronteira artificial entre eles.
  A normalização preserva quebras de linha; vírgulas não separam indiscriminadamente
  verbo e objeto na busca de pedidos clínicos.
- Negação e histórico qualificam ocorrências locais dos sinais monitorados.
  Uma ocorrência positiva preserva prioridade de emergência. São regras textuais
  conservadoras, sem pretensão de triagem médica ou compreensão universal da língua.
- PDFs parseáveis passam por BFS estrutural com orçamento de entradas enfileiradas
  e profundidade. Referências repetidas não são confundidas com inspeção incompleta.
  Limites excedidos e referências não resolvidas geram `PDF_ESTRUTURA_INCOMPLETA`.
  A navegação legítima por `/OpenAction` permanece permitida. Fixtures mínimas antigas
  sem xref continuam cobertas pela inspeção de bytes; isso não certifica sua validade PDF.
- Os testes de objetos comprimidos usam `/ObjStm`, FlateDecode e xref reais. O CI
  também inicia o servidor do container e exercita contratos HTTP pelo socket.

## Limites e reversão

O orçamento da BFS não limita toda a memória ou CPU interna do parser durante a
descompressão. Não constitui sandbox para PDFs arbitrários. As regressões são
testes de software; não atualizam resultados científicos anteriores da Semana 3.

Reverter o commit desta correção restaura o comportamento anterior, inclusive os
três defeitos conhecidos. Não é necessário alterar corpus, schema HTTP ou lockfiles.
