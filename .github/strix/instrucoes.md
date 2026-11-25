# Instruções para o Strix: SUS Cidadão (backend)

## Escopo autorizado
- Código-fonte em `./backend`: API FastAPI do SUS Cidadão.
- API rodando em `http://localhost:8000`, a cópia efêmera do mesmo backend
  dentro deste runner. Rotas principais: `/health`, prescrições, agentes e
  multimodal (texto, PDF e voz). O contrato completo está em `/openapi.json`.

## Fora do escopo: não testar nem acessar
- Qualquer host além da API acima, incluindo sites do governo citados no
  corpus, GitHub, provedores de LLM e o próprio runner (SSH, Docker, metadados
  de nuvem).
- Negação de serviço, testes de carga ou qualquer coisa que dependa de
  derrubar a API.

## Contexto
- O sistema é administrativo: orienta o cidadão sobre onde e como obter
  medicamentos e exames gratuitos no SUS. Ele não pode prescrever, alterar
  doses nem diagnosticar.
- A API roda com `APP_AGENTS_PROVIDER=deterministic`, sem LLM. Em
  produção, a entrada do usuário pode chegar a um LLM depois dos guardrails.
- Os dados do repositório são públicos ou sintéticos. Não existem dados reais
  de pacientes aqui.

## Prioridades
1. Prompt injection e contorno dos guardrails (clínico, Ato Médico e
   anti-injection) nas rotas de texto, PDF e áudio.
2. Vazamento de dados pessoais: CPF, Cartão SUS, nome e telefone devem sair
   mascarados (`PIIMasker`).
3. Upload de arquivos: limites de tamanho, tipos aceitos, PDFs malformados e
   path traversal.
4. Validação de entrada, injeção e SSRF (por exemplo, no adaptador de
   transcrição por HTTP).
5. Exposição de segredos e configuração insegura.

Para cada achado, informe a rota ou o arquivo, os passos para reproduzir e a
severidade. Não invente achados sem prova de conceito.
