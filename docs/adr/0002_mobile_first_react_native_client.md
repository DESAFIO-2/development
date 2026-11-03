# ADR 0002: Adoção de React Native (Expo) para Interface Mobile Cidadã e Suporte Multimodal

* **Status:** Aprovado
* **Data:** 2026-11-03
* **Decisores:** Samuel de Souza Rodrigues (AI Engineer / Tech Lead), Mickeias Paiva (Arquiteto de Software), Marlon Marques (Cientista de Dados), Jhiovana Ribeiro (Engenheira de Dados), Tayrine Zitkoski (MLOps/LLMOps)

---

## 1. Contexto e Problema
Na Semana 1, definimos as Personas do projeto:
- **Dona Helena (58 anos, diarista em Ceilândia - DF):** Usuária exclusiva de smartphone, alfabetização digital intermediária, orientada a áudios de WhatsApp e fotos de documentos.
- **Lucas Mendes (29 anos, Taguatinga Sul - DF):** Cuidador que precisa de respostas rápidas na palma da mão antes de pedir dispensa no trabalho para retirar remédios ou marcar exames.

Além disso, os Requisitos Funcionais do PDR exigem:
- **RF01 (Ingestão Multimodal):** Envio de fotos de receituários via câmera e gravação de áudio com a localidade (Região Administrativa);
- **RF08 (Gestão da Prescrição e Adesão):** Notificações preventivas a 15 e 7 dias antes do vencimento da receita e apoio aos horários das doses.

Uma interface puramente web não oferece suporte confiável a notificações push/locais nem a integração fluida com câmera e microfone para o perfil de vulnerabilidade socioeconômica atendido.

---

## 2. Decisão Técnica
1. **Adoção do React Native com Expo (`mobile/`):**
   - Criação do cliente mobile do cidadão na pasta `mobile/` do monorepo;
   - Utilização do ecossistema Expo para agilidade de desenvolvimento, testes via Expo Go e compilação cross-platform (Android e iOS).
2. **Arquitetura Desacoplada (Backend-for-Frontend):**
   - O aplicativo mobile consumirá a API FastAPI (`backend/app/`) estritamente via requisições HTTP RESTful documentadas no Swagger/OpenAPI;
   - Toda a inteligência artificial (RAG híbrido, auditoria de normas e guardrails) permanece centralizada no backend Python, garantindo segurança e desempenho em dispositivos de baixo custo.
3. **Hardware Nativo para a Semana 5:**
   - Integração com `expo-camera` para captura de imagens de receituários;
   - Integração com `expo-av` para gravação de mensagens de voz com a RA do paciente;
   - Integração com `expo-notifications` para os alertas da contagem regressiva da receita (RF08).

---

## 3. Consequências e Benefícios
- **Experiência Real Cidadã:** Acesso direto na UBS ou na fila da drogaria credenciada ao Farmácia Popular.
- **Preparação Cirúrgica para a Semana 5 (Multimodalidade):** As entradas de fotos e áudios já nascerão prontas no canal onde o usuário realmente as gera.
- **Independência Técnica:** O time de IA pode evoluir o RAG no backend sem quebrar a camada visual, respeitando os contratos de API.
