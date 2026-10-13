"""Typed adapters over existing tools; no SQL or retrieval implementation here."""
from dataclasses import dataclass, field
from typing import Any, Literal

from service.intent_classifier import Intent

EvidenceState = Literal['not_queried','queried_no_evidence','queried_with_evidence','query_failed']


@dataclass(frozen=True)
class TicketInput:
    question: str
    intent: Intent
    entity_question: str


@dataclass(frozen=True)
class RetrieveInput:
    question: str
    top_k: int
    query_vector: Any = None


@dataclass
class ToolOutput:
    store: str
    state: EvidenceState = 'not_queried'
    tool_called: bool = False
    query_executed: bool = False
    reason: str = 'not_required'
    evidence_ids: list[str] = field(default_factory=list)
    payload: dict | None = None
    hits: list[dict] = field(default_factory=list)

    def task(self, question):
        return {'store':self.store,'question':question,'state':self.state,
            'tool_called':self.tool_called,'query_executed':self.query_executed,
            'reason':self.reason,'evidence_ids':self.evidence_ids,
            'answer_status':(self.payload or {}).get('status'), 'retrieved_count':len(self.hits)}

    def public(self):
        return {'state':self.state,'tool_called':self.tool_called,'query_executed':self.query_executed,
            'reason':self.reason,'evidence_ids':self.evidence_ids,'retrieved_count':len(self.hits),
            'result':self.payload}


def ticket_sql(request: TicketInput, implementation) -> ToolOutput:
    output=ToolOutput('ticket_sql',tool_called=True,reason='')
    try:
        output.payload=implementation(request.question,intent=request.intent,entity_question=request.entity_question)
        if output.payload is None:
            output.reason='ticket_sql_disabled'
        elif not output.payload.get('ticket_lookup_executed',True):
            output.reason='entity_unresolved'
        else:
            output.query_executed=True
            output.evidence_ids=[c['source_id'] for c in output.payload['citations']]
            output.state='queried_with_evidence' if output.evidence_ids else 'queried_no_evidence'
    except Exception:
        output.state='query_failed';output.reason='ticket_tool_failed'
        output.payload=None
    return output


def retrieve_chunks(request: RetrieveInput, implementation) -> ToolOutput:
    output=ToolOutput('rag',tool_called=True,reason='awaiting_answer_validation')
    try:
        kwargs={'top_k':request.top_k}
        if request.query_vector is not None:kwargs['query_vector']=request.query_vector
        output.hits=implementation(request.question,**kwargs)
        output.query_executed=True
        # Candidate chunks are not yet evidence for the requested fact.
        output.state='queried_no_evidence'
    except Exception:
        output.state='query_failed';output.reason='rag_retrieval_failed'
    return output
