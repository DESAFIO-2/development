# Política de Segurança e Privacidade de Dados de Saúde

## 🛡️ Conformidade com a LGPD e Ética em Saúde

O **SUS Cidadão** lida com informações potencialmente sensíveis de saúde (receitas médicas, nomes de medicamentos, CIDs e dados demográficos de pacientes).

### 1. Diretrizes Inegociáveis
1. **Preservação do Ato Médico:** O sistema é estritamente administrativo e logístico. É terminantemente proibido prescrever tratamentos, alterar dosagens ou recomendar diagnósticos clínicos.
2. **Processamento Efêmero & Anonimização Prévia (PII Masking):** Nenhum dado pessoal identificável (Nome, CPF, Cartão SUS, telefone, endereço) pode ser transmitido para modelos externos de LLM sem prévia desidentificação por Regex/NER.
3. **Sem Retenção de Prescrições Reais:** Receitas reais enviadas em testes devem ser processadas em memória volátil e descartadas imediatamente após a geração do roteiro.
4. **Proteção de Segredos:** Nenhuma chave de API (`OPENAI_API_KEY`, etc.) deve ser commitada. Utilize o arquivo `.env`.

Para relatar qualquer vulnerabilidade ou risco de privacidade, contate os mantenedores do projeto no repositório.
