# Comparativo dos quatro braços (semana 3)

| Braço | Segurança | Acerto de rota | Metas ADR 0003 | Latência mediana |
| --- | --- | ---: | ---: | ---: |
| A. LLM sem RAG | ELIMINADO | 38.89% (n=18) | 0/4 | 10.62 s |
| B. LLM com RAG | ELIMINADO | 100.00% (n=18) | 2/4 | 22.06 s |
| C. RAG sem LLM (API determinística) | ELIMINADO | não medido | 0/4 | não medido |
| D. LLM com RAG blindado | ELIMINADO | 100.00% (n=18) | 2/4 | 22.15 s |

**Braço escolhido:** nenhum. Nenhum braço aprovado na suíte de segurança (eliminados ou não avaliados).

Regra: 1) segurança elimina; 2) maior acerto de rota; 3) mais metas do ADR 0003 (sem RAGAS conta 0); 4) menor latência mediana (sem medida fica por último).

Limitações: acerto de rota de A, B e D é heurística sobre o texto, e o de C vem da rota estruturada da API; o mesmo modelo gera e julga no RAGAS; os 22 casos são de desenvolvimento; a suíte de segurança é sintética e escrita junto com as regras; a auditoria factual humana continua pendente.
