# Especificação de aceitação — agentes Semana 4

Escopo aprovado: LangGraph, backend/API/CLI, sem interface e sem sessão persistente.

| ID | Comportamento verificável | Evidência de aceitação |
| --- | --- | --- |
| S4-01 | Bloqueio precede recuperação e geração; emergência tem prioridade | Testes clínico/injeção e emergência entre campos |
| S4-02 | Auditoria preserva concentração, associação e catálogo oficial | Regressões existentes + abstenção na API de agentes |
| S4-03 | Medicamento+exame produz roteiro multicanal | Teste HTTP com dois itens e smoke de servidor |
| S4-04 | Evidência pertence à ocorrência da apresentação escolhida | Comparação com repositório literal e trio exato de citação |
| S4-05 | Dúvida administrativa usa recuperação normativa | Pergunta sem itens e geração com contexto sanitizado |
| S4-06 | Dois ramos concorrentes e síntese única | Barrier de teste sem depender de limiar de velocidade |
| S4-07 | Sem herança de tópico ou mistura de requisições | Requisições sequenciais e concorrentes |
| S4-08 | Erro de provedor é visível; modo estrito não usa fallback | Metadados por chamada e GenerationFailure |
| S4-09 | Validar texto generativo e determinístico | PII, posologia, citações fora do contexto e metadados adulterados |
| S4-10 | Sem regressão do consumidor anterior | Suíte completa, Golden Sets, smoke HTTP, tipos/lint |
| S4-11 | Não apresentar fixtures como ciência | scientific_status=NAO_AVALIADO; avaliação real pendente |

Sequência executada: fixar SHAs e baseline; definir contratos; integrar evidências
no caso de uso existente; compor quatro nós; expor rota/CLI; testar e revisar;
documentar limites, modelos, validação e reversão. A revisão do squad e os gates de
CI são necessários para merge. Aprovação científica não é consequência de pytest.
