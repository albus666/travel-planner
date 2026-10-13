"""Pure legacy-rule adapter; labels describe data stores, not entity resolution."""
from dataclasses import dataclass
from enum import Enum


class Store(str, Enum):
    TICKET_RAW = 'v2.poi_details.ticket_raw'
    RAG_CHUNKS = 'v2.rag_chunks'


@dataclass(frozen=True)
class Intent:
    store: Store
    method: str = 'legacy_rule'
    reason: str = ''


def classify_intent(question: str) -> Intent:
    # Lazy import keeps the classifier dependent on the existing rule, with no cycle.
    from service.ticket_service import is_ticket_question
    if is_ticket_question(question):
        return Intent(Store.TICKET_RAW, reason='Existing ticket rule matched')
    return Intent(Store.RAG_CHUNKS, reason='Existing ticket rule did not match')
