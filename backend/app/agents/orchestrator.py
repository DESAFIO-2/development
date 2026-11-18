"""Grafo sem persistência: triagem -> (auditoria || normas) -> síntese."""

from __future__ import annotations

import operator
import time
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context

from app.application.agents import (
    AgentRequest,
    AgentResponse,
    AgentTrace,
    AuditorPort,
    GenerationMetadata,
)
from app.application.ports import GeneratorPort, GuardrailPort, RetrievalHitDTO, RetrieverPort
from app.application.use_cases.consult_norms import consult_norms
from app.application.use_cases.synthesize_guidance import synthesize
from app.application.use_cases.triage import inspect_request, sanitize_request
from app.core.telemetry import trace_operation
from app.domain.guidance import CitizenGuidanceCard
from app.seguranca.contexto import PublicContextRegistry
from app.seguranca.saida import validar_saida


class AgentState(TypedDict, total=False):
    request: AgentRequest
    strict: bool
    blocked: bool
    card: CitizenGuidanceCard
    audit_hits: list[RetrievalHitDTO]
    normative_hits: list[RetrievalHitDTO]
    agent_trace: Annotated[list[AgentTrace], operator.add]
    response: AgentResponse


def _trace(name: str, start: float) -> list[AgentTrace]:
    return [AgentTrace(agent=name, elapsed_ms=round((time.perf_counter() - start) * 1000, 3))]


class LangGraphOrchestrator:
    def __init__(
        self,
        *,
        auditor: AuditorPort,
        guardrail: GuardrailPort,
        retriever: RetrieverPort,
        generator: GeneratorPort | None = None,
        public_context: PublicContextRegistry | None = None,
    ) -> None:
        self.auditor = auditor
        self.guardrail = guardrail
        self.retriever = retriever
        self.generator = generator
        self.public_context = public_context or PublicContextRegistry()
        graph = StateGraph(AgentState)
        graph.add_node("triagem", self._triage)
        graph.add_node("auditor_farmaceutico", self._audit)
        graph.add_node("consultor_normativo", self._consult)
        graph.add_node("sintetizador_cidadao", self._synthesize)
        graph.add_edge(START, "triagem")
        graph.add_conditional_edges(
            "triagem",
            self._route,
            ["auditor_farmaceutico", "consultor_normativo", "sintetizador_cidadao"],
        )
        # Barreira explícita: síntese só começa após os DOIS ramos.
        graph.add_edge(["auditor_farmaceutico", "consultor_normativo"], "sintetizador_cidadao")
        graph.add_edge("sintetizador_cidadao", END)
        self.graph = graph.compile()

    def executar(self, request: AgentRequest, *, strict: bool = False) -> AgentResponse:
        # O estado contém entrada bruta na triagem: nunca exportar para LangSmith,
        # inclusive quando houver variáveis de tracing no ambiente do operador.
        # OTel continua registrando somente nomes de operações e durações.
        with tracing_context(enabled=False):
            state = self.graph.invoke(AgentState(request=request, strict=strict, agent_trace=[]))
        response: AgentResponse = state["response"]
        return response.model_copy(update={"agent_trace": state["agent_trace"]})

    @staticmethod
    def _route(state: AgentState) -> list[str]:
        return (
            ["sintetizador_cidadao"]
            if state["blocked"]
            else ["auditor_farmaceutico", "consultor_normativo"]
        )

    def _triage(self, state: AgentState) -> AgentState:
        start = time.perf_counter()
        with trace_operation("agent.triagem"):
            blocked = inspect_request(state["request"], self.guardrail)
            sanitized = sanitize_request(state["request"], self.guardrail)
            result = AgentState(
                request=AgentRequest.model_validate(sanitized.model_dump()),
                blocked=blocked is not None,
                agent_trace=_trace("triagem", start),
            )
            if blocked:
                result["card"] = blocked
            return result

    def _audit(self, state: AgentState) -> AgentState:
        start = time.perf_counter()
        with trace_operation("agent.auditor_farmaceutico"):
            result = self.auditor.executar_com_evidencias(state["request"])
            return AgentState(
                card=result.card,
                audit_hits=list(result.evidences),
                agent_trace=_trace("auditor_farmaceutico", start),
            )

    def _consult(self, state: AgentState) -> AgentState:
        start = time.perf_counter()
        with trace_operation("agent.consultor_normativo"):
            hits = consult_norms(state["request"], self.retriever)
            return AgentState(normative_hits=hits, agent_trace=_trace("consultor_normativo", start))

    def _synthesize(self, state: AgentState) -> AgentState:
        start = time.perf_counter()
        with trace_operation("agent.sintetizador_cidadao"):
            if state["blocked"]:
                card = state["card"]
                if not validar_saida(card.resumo_acolhedor).aprovada:
                    card = card.model_copy(
                        update={
                            "resumo_acolhedor": (
                                "Não é possível orientar sobre essa solicitação. "
                                "Procure atendimento de saúde."
                            )
                        }
                    )
                response = AgentResponse(
                    card=card,
                    primary_route="BLOQUEADO",
                    generation=GenerationMetadata(status="BLOQUEADO"),
                )
            else:
                response = synthesize(
                    request=state["request"],
                    card=state["card"],
                    audit_hits=state.get("audit_hits", []),
                    normative_hits=state.get("normative_hits", []),
                    generator=self.generator,
                    strict=state["strict"],
                    public_context=self.public_context,
                )
            return AgentState(response=response, agent_trace=_trace("sintetizador_cidadao", start))
