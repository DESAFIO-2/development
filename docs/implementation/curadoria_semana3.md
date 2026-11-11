# Curadoria e limites do conjunto da semana 3

Revisão técnica em 2026-11-11. Conjunto: `golden_set_v2_consolidado.jsonl`, 22 casos.
As perguntas e os gabaritos históricos foram preservados; não há alegação de
validação clínica ou atualização normativa integral. O manifesto da coleta
congela o texto do dataset e os hashes do corpus/código antes da primeira geração.

Este conjunto já orientou implementação e testes. Seu papel é desenvolvimento e
regressão. Não deve ser apresentado como teste independente de generalização.
Os chunks recuperados são evidência para Faithfulness, mas não substituem a
consulta aos documentos oficiais na auditoria factual.

| Casos | Revisão técnica e cuidado obrigatório na auditoria |
| --- | --- |
| GOLD-001–004 | Conferir apresentação, gratuidade e documentos; distinguir acesso administrativo de atendimento de crise. Não inferir estoque. |
| GOLD-005–007 | Conferir apresentação e canal; validade de receita depende da classe e das fontes, não de uma regra genérica única. |
| GOLD-008–010 | Conferir elegibilidade/PCDT, apresentação, unidade e documentos; distinguir validade do LME de periodicidade de renovação. |
| GOLD-011–012 | Conferir cada exame/consulta; requisitos clínicos de encaminhamento podem variar entre protocolos. |
| GOLD-013–014 | Ausência no corpus é ausência de evidência no escopo congelado, não prova universal de inexistência de cobertura. Revisar também o braço sem RAG. |
| GOLD-015–016 | Controles de segurança; revisar preservação do ato médico e orientação de urgência. Não contar texto do guardrail como qualidade intrínseca do modelo. |
| GOLD-017 | Conferir elegibilidade de fralda e representação; não equiparar automaticamente assinatura Gov.br a assinatura qualificada. |
| GOLD-018 | `expected_documents` contém autorização do programa, omitida no texto de referência. Revisar a exigência nas fontes; o gabarito não deve justificar a omissão. |
| GOLD-019 | A categoria interna UBS agrupa também canais ambulatoriais. Conferir o canal concreto para cada medicamento; não exigir retirada em qualquer UBS. |
| GOLD-020 | A pergunta não fixa concentração/apresentação de medroxiprogesterona. O catálogo contém comprimido e injetáveis, além de canal PFPB para outra representação. Não interpretar a rota única esperada como prova de cobertura de qualquer apresentação. Aceitar incerteza fundamentada na auditoria; conferir cada item. |
| GOLD-021 | Conferir canal e requisitos de cada programa; não generalizar documentos/dispensação de um item aos demais. |
| GOLD-022 | Conferir o formulário de representante e distinguir validade de solicitação, dispensação e renovação do LME. |

O dataset v2 permite coletar uma linha de base reproduzível, mas essas limitações
precisam acompanhar os resultados. A revisão humana exige documento, página/seção
e fato conferido em `evidencias`, com observações para divergências do gabarito.
Os escores de Context Recall/Precision são relativos à referência congelada e
devem ser interpretados com essas limitações, sem serem chamados de verdade factual.

Se a equipe decidir corrigir perguntas/gabaritos antes da coleta definitiva,
criar uma nova versão do dataset com registro de alterações e fontes verificadas.
Não editar a versão congelada nem modificar rótulos depois de observar respostas
para melhorar métricas. O piloto é separado e não integra a evidência final.
