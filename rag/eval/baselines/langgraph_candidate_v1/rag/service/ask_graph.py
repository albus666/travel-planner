"""Small deterministic LangGraph; keep off-switch and frozen routing unchanged."""
from functools import lru_cache
import os
import re
from typing import Any, TypedDict

from service.graph_tools import TicketInput, RetrieveInput, ToolOutput, ticket_sql, retrieve_chunks
from service.intent_classifier import Intent, Store, classify_intent
from service.mixed_service import build_mixed_plan, mixed_enabled
from service.semantic_router import classify_for_request, semantic_enabled


def langgraph_enabled():
    return os.environ.get('RAG_LANGGRAPH_ENABLED','0').lower() in ('1','true','on')


class AskState(TypedDict, total=False):
    question: str
    top_k: int
    required_stores: list[str]
    mixed: bool
    ticket_question: str
    rag_question: str
    intent: Intent
    query_vector: Any
    sql: ToolOutput
    rag: ToolOutput
    node_trace: list[str]
    result: dict


def unavailable(text):
    return {'status':'insufficient_evidence','answer':text,'citations':[],
        'warnings':[],'retrieved_sources':[]}


def create_graph(ticket_implementation, search_implementation, answer_implementation,
                 *, classifier=None, mixed_builder=None):
    # Dependency is imported only when the graph is actually used.
    from langgraph.graph import StateGraph, START, END

    def plan_node(state):
        question=state['question']
        plan=(mixed_builder or build_mixed_plan)(question) if mixed_enabled() else None
        vector=None
        if plan:
            intent=Intent(Store.TICKET_RAW,method='mixed_plan')
            stores=list(plan.required_stores);tq=plan.ticket_question;rq=plan.rag_question
        else:
            intent,vector=(classifier(question) if classifier else classify_for_request(question)
                if semantic_enabled() else (classify_intent(question),None))
            sql_enabled=os.environ.get('RAG_SQL_TICKET_ENABLED','1').lower() not in ('0','false','off')
            stores=['ticket_sql'] if intent.store==Store.TICKET_RAW and sql_enabled else ['rag']
            tq=rq=question
        return {'required_stores':stores,'mixed':bool(plan),'ticket_question':tq,'rag_question':rq,
            'intent':intent,'query_vector':vector,'sql':ToolOutput('ticket_sql'),
            'rag':ToolOutput('rag'),'node_trace':['plan']}

    def ticket_node(state):
        output=ticket_sql(TicketInput(state['ticket_question'],state['intent'],state['question']),ticket_implementation)
        updates={'sql':output,'node_trace':state['node_trace']+['ticket_sql']}
        if state['mixed']:
            data=(output.payload or {}).get('structured_data') or {}
            prefix=re.split(r'门票|票价|票钱|入场|入园|进景区|进大门|进去|进园',state['ticket_question'],maxsplit=1)[0].strip()
            name=data.get('name') or prefix
            updates['rag_question']=(name+'：' if name else '')+state['rag_question']
            resolution=(output.payload or {}).get('entity_resolution')
            if resolution and resolution['status']!='resolved':
                rag=ToolOutput('rag',reason='entity_unresolved',payload=unavailable(
                    '文本子任务未执行：请先明确一个景点，再分别查询所需资料。'))
                updates['rag']=rag
        return updates

    def retrieve_node(state):
        output=retrieve_chunks(RetrieveInput(state['rag_question'],state['top_k'],
            None if state['mixed'] else state.get('query_vector')),search_implementation)
        return {'rag':output,'node_trace':state['node_trace']+['retrieve_chunks']}

    def answer_node(state):
        prior=state['rag']
        # Copy state objects; graph stages never mutate earlier node output.
        output=ToolOutput(**{**prior.__dict__})
        if prior.state=='query_failed':
            output.payload=unavailable('无法确认：文本查询暂不可用；不能据此认定资料不存在。')
        else:
            try:
                output.payload=answer_implementation(state['rag_question'],prior.hits)
                data=(state['sql'].payload or {}).get('structured_data') or {}
                if state['mixed'] and data.get('poi_id') and any(c['poi_id']!=data['poi_id'] for c in output.payload['citations']):
                    output.payload={**output.payload,**unavailable('无法确认：文本回答的引用涉及其他景点，未展示该部分事实。'),
                        'retrieved_sources':output.payload.get('retrieved_sources',[])}
                output.evidence_ids=[c['source_id'] for c in output.payload['citations']]
                output.state='queried_with_evidence' if output.evidence_ids else 'queried_no_evidence'
                output.reason=''
            except Exception:
                output.state='query_failed';output.reason='rag_answer_failed'
                output.payload=unavailable('无法确认：文本回答暂不可用；不能据此认定资料不存在。')
        return {'rag':output,'node_trace':state['node_trace']+['answer_validate']}

    def merge_node(state):
        sql,rag=state['sql'],state['rag']
        sql_payload=sql.payload or {**unavailable('门票子任务未执行：门票查询已停用。' if sql.state=='not_queried'
            else '门票查询暂不可用；本次未取得票价资料，不能据此认定数据库没有记录。'), 'structured_data':None}
        rag_payload=rag.payload or unavailable('无法确认：文本子任务未执行。')
        if state['mixed']:
            complete=sql_payload['status']=='answered' and rag_payload['status']=='answered'
            result={'route':'mixed','status':'answered' if complete else 'insufficient_evidence',
                'answer':'门票资料：\n'+sql_payload['answer']+'\n\n文本资料：\n'+rag_payload['answer'],
                'citations':sql_payload['citations']+rag_payload['citations'],
                'warnings':list(dict.fromkeys(sql_payload['warnings']+rag_payload['warnings'])),
                'structured_data':sql_payload.get('structured_data'),
                'retrieved_sources':rag_payload['retrieved_sources'],
                'entity_resolution':sql_payload.get('entity_resolution')}
        elif 'ticket_sql' in state['required_stores']:
            result={**sql_payload,'route':'sql_ticket'}
        else:
            result={**rag_payload,'route':'vector'}
        trace=state['node_trace']+['merge']
        result.update(required_stores=state['required_stores'],workflow='langgraph_v1',node_trace=trace,
            tasks=[sql.task(state['ticket_question']),rag.task(state['rag_question'])],
            tool_results={'ticket_sql':sql.public(),'rag':rag.public()})
        return {'result':result,'node_trace':trace}

    def after_plan(state):return 'ticket_sql' if 'ticket_sql' in state['required_stores'] else 'retrieve_chunks'
    def after_ticket(state):
        if 'rag' in state['required_stores'] and state['rag'].reason!='entity_unresolved':return 'retrieve_chunks'
        return 'merge'

    graph=StateGraph(AskState)
    for name,node in (('plan',plan_node),('ticket_sql',ticket_node),('retrieve_chunks',retrieve_node),
                      ('answer_validate',answer_node),('merge',merge_node)):
        graph.add_node(name,node)
    graph.add_edge(START,'plan')
    graph.add_conditional_edges('plan',after_plan,{'ticket_sql':'ticket_sql','retrieve_chunks':'retrieve_chunks'})
    graph.add_conditional_edges('ticket_sql',after_ticket,{'retrieve_chunks':'retrieve_chunks','merge':'merge'})
    graph.add_edge('retrieve_chunks','answer_validate');graph.add_edge('answer_validate','merge');graph.add_edge('merge',END)
    return graph.compile()


@lru_cache(maxsize=4)
def cached_graph(ticket_implementation,search_implementation,answer_implementation):
    return create_graph(ticket_implementation,search_implementation,answer_implementation)


def run_graph(question,top_k,*,ticket_tool,search_tool,answer_tool):
    state=cached_graph(ticket_tool,search_tool,answer_tool).invoke({'question':question,'top_k':top_k},
        config={'recursion_limit':12})
    return state['result']
