"""Explicit compound requests; existing store classifiers and tools are unchanged."""
from dataclasses import dataclass
import os
import re

from service.intent_classifier import Intent, Store, classify_intent
from service.store_contract import boundary_intent


@dataclass(frozen=True)
class MixedPlan:
    ticket_question: str
    rag_question: str
    required_stores: tuple = ('ticket_sql', 'rag')


def mixed_enabled():
    return os.environ.get('RAG_MIXED_ENABLED', '0').lower() in ('1', 'true', 'on')


def build_mixed_plan(question, classifier=None):
    """Conservative clause decomposition, not a replacement for single-store routing."""
    parts = [p.strip(' ，,；;。？?') for p in re.split(
        r'[，,；;。？?]|同时|并且|以及|和(?=游览|路线|历史|设施|老人|老年|优待|优惠)|(?=有没有)', question) if p.strip()]
    if len(parts) < 2:
        return None
    rag_parts = [p for p in parts if boundary_intent(p) is not None]
    if not rag_parts:
        return None
    if classifier is None:
        from service.semantic_router import classify_for_request, semantic_enabled
        classifier = lambda p: classify_for_request(p)[0] if semantic_enabled() else classify_intent(p)
    prices = [p for p in parts if p not in rag_parts
        and any(w in p for w in ('门票','票价','票钱','入场','入园','进景区','进大门','进去','进园'))
        and not re.search(r'不要|不问|不需要|不是问|别给|不查', p)
        and classifier(p).store == Store.TICKET_RAW]
    if len(prices) != 1:
        return None
    return MixedPlan(prices[0], '；'.join(rag_parts))


def execute_mixed(question, plan, top_k, *, ticket_tool, search_tool, answer_tool):
    """Keep deterministic SQL answer separate from evidence-validated RAG output."""
    tasks = [{'store': store, 'question': subq, 'state': 'not_queried',
        'tool_called': False, 'answer_status': None, 'evidence_ids': []}
        for store, subq in zip(plan.required_stores, (plan.ticket_question, plan.rag_question))]
    sql_task, rag_task = tasks
    sql = None
    try:
        sql_task['tool_called'] = True
        sql = ticket_tool(plan.ticket_question, intent=Intent(Store.TICKET_RAW, method='mixed_plan'),
            entity_question=question)
        if sql is None:
            sql_task.update(state='not_queried', reason='ticket_sql_disabled', answer_status='insufficient_evidence')
        elif sql.get('ticket_lookup_executed', True):
            sql_task.update(state='queried_with_evidence' if sql['citations'] else 'queried_no_evidence',
                answer_status=sql['status'], evidence_ids=[c['source_id'] for c in sql['citations']])
        else:
            sql_task.update(reason='entity_unresolved', answer_status=sql['status'])
    except Exception:
        sql_task.update(state='query_failed', reason='ticket_tool_failed', answer_status='insufficient_evidence')
    # A known entity conflict blocks text execution as well, instead of mixing POIs.
    resolution = (sql or {}).get('entity_resolution')
    blocked = resolution and resolution['status'] != 'resolved'
    rag = {'status':'insufficient_evidence','answer':'无法确认：文本子任务未执行。',
        'citations':[], 'retrieved_sources':[], 'warnings':[]}
    if blocked:
        rag_task.update(reason='entity_unresolved', answer_status='insufficient_evidence')
        rag['answer'] = '文本子任务未执行：请先明确一个景点，再分别查询所需资料。'
    else:
        data = (sql or {}).get('structured_data') or {}
        # Keep price requests out of the text-only question even if SQL is down.
        # This is literal context extraction, not an alias/entity mapping.
        prefix = re.split(r'门票|票价|票钱|入场|入园|进景区|进大门|进去|进园',
            plan.ticket_question, maxsplit=1)[0].strip()
        name_context = data.get('name') or prefix
        rag_q = (name_context + '：' if name_context else '') + plan.rag_question
        rag_task['question'] = rag_q
        try:
            rag_task['tool_called'] = True
            hits = search_tool(rag_q, top_k=top_k)
            rag = answer_tool(rag_q, hits)
            if data.get('poi_id') and any(c['poi_id'] != data['poi_id'] for c in rag['citations']):
                rag = {**rag, 'status':'insufficient_evidence',
                    'answer':'无法确认：文本回答的引用涉及其他景点，未展示该部分事实。', 'citations':[]}
            rag_task.update(state='queried_with_evidence' if rag['citations'] else 'queried_no_evidence',
                answer_status=rag['status'], evidence_ids=[c['source_id'] for c in rag['citations']],
                retrieved_count=len(hits))
        except Exception:
            rag_task.update(state='query_failed', reason='rag_tool_failed', answer_status='insufficient_evidence')
            rag = {**rag, 'answer':'无法确认：文本查询或回答暂不可用；不能据此认定资料不存在。',
                'citations':[], 'retrieved_sources':[]}
    sql_text = sql['answer'] if sql else ('门票子任务未执行：门票查询已停用。' if sql_task['state']=='not_queried'
        else '门票查询暂不可用；本次未取得票价资料，不能据此认定数据库没有记录。')
    complete = all(t['answer_status']=='answered' for t in tasks)
    return {'route':'mixed', 'status':'answered' if complete else 'insufficient_evidence',
        'answer':'门票资料：\n'+sql_text+'\n\n文本资料：\n'+rag['answer'],
        'citations':(sql or {}).get('citations',[])+rag['citations'],
        'warnings':list(dict.fromkeys((sql or {}).get('warnings',[])+rag['warnings'])),
        'structured_data':(sql or {}).get('structured_data'),
        'retrieved_sources':rag['retrieved_sources'], 'required_stores':list(plan.required_stores),
        'tasks':tasks, 'entity_resolution':resolution}
