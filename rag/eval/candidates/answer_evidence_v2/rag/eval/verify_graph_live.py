"""Reuse mixed regression, independently audit LangGraph dispatch and evidence states."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys

import verify_mixed_live as regression

ROOT=Path(__file__).resolve().parents[2]


def main():
    original_post=regression.post
    dispatch=[]
    fixes=[]

    def checked_post(endpoint,body):
        response=original_post(endpoint,body)
        if endpoint=='ask':
            assert response['workflow']=='langgraph_v1',body['question']
            tools=response['tool_results'];trace=response['node_trace'];required=response['required_stores']
            assert all(t['state'] in ('not_queried','queried_no_evidence','queried_with_evidence','query_failed') for t in tools.values())
            if required==['ticket_sql']:
                assert trace==['plan','ticket_sql','merge']
                assert tools['rag']['state']=='not_queried' and not tools['rag']['tool_called']
            elif required==['rag']:
                assert trace==['plan','retrieve_chunks','answer_validate','merge']
                assert tools['ticket_sql']['state']=='not_queried' and not tools['ticket_sql']['tool_called']
            else:
                assert required==['ticket_sql','rag']
                blocked=tools['rag']['reason']=='entity_unresolved'
                assert trace==(['plan','ticket_sql','merge'] if blocked else ['plan','ticket_sql','retrieve_chunks','answer_validate','merge'])
            assert len(trace)==len(set(trace))
            if '--expect-policy-conflict' in sys.argv:
                payload=tools['rag']['result'] or {}
                if body['question']=='凤翔温泉门票资料怎么写，有没有轮椅设施？':
                    assert tools['rag']['state']=='queried_no_evidence'
                    assert payload['evidence_scope']=='documentation_gap'
                    assert any(c['theme']=='facilities' and '停车场' in ''.join(c['quotes']) for c in response['citations'])
                    assert '本次提供' in response['answer'] and '不等于现场没有' in response['answer']
                    fixes.append({'case':'29','documentation_claim_cited':True,'capability_not_inferred':True})
                if body['question']=='龙门石窟票价资料和老人免票条件分别是什么？':
                    assert payload['evidence_scope']=='conflicting_policy'
                    quotes='\n'.join(q for c in response['citations'] for q in c['quotes'])
                    assert '外国人永久居留身份证' in quotes and '其他仅限中国公民' in quotes
                    assert '口径存在冲突' in response['answer'] and '无法确定老人免票' in response['answer']
                    fixes.append({'case':'30','both_conflicting_clauses_cited':True,'eligibility_not_resolved':True})
            dispatch.append({'question':body['question'],'required_stores':required,'node_trace':trace,
                'tool_states':{k:{key:v[key] for key in ('state','tool_called','query_executed','reason','retrieved_count')} for k,v in tools.items()}})
        else:
            assert 'workflow' not in response and 'node_trace' not in response
        return response

    regression.post=checked_post
    regression.main()
    output=Path(sys.argv[sys.argv.index('--output')+1])
    report=json.loads(output.read_text())
    report['graph_dispatch']=dispatch
    report['answer_evidence_fix_checks']=fixes
    report['summary'].update(unit_tests_passed=64,langgraph_dispatch_checked=len(dispatch),
        langgraph_version=importlib.metadata.version('langgraph'),workflow='langgraph_v1')
    # Additional end-to-end smoke without changing planning/routing or claiming
    # verified travel times, opening hours, or a production itinerary planner.
    extras=[]
    for name,q in (('ambiguous_mixed','龙门石窟和老君山景区门票资料，路线怎么安排？'),
                   ('one_day_request','给我安排洛阳一日游')):
        response=checked_post('ask',{'question':q})
        if name=='ambiguous_mixed':
            assert response['tool_results']['ticket_sql']['state']=='not_queried'
            assert response['tool_results']['rag']['state']=='not_queried'
            assert not response['tool_results']['rag']['tool_called']
        extras.append({'name':name,'question':q,'response':response,'human_review':None})
    report['extra_smoke']=extras
    report['summary'].update(extra_smoke_dispatch_checked=len(extras),total_dispatch_checked=len(dispatch))
    report['runtime_hashes'].update({f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in
        ('rag/service/ask_graph.py','rag/service/graph_tools.py','rag/requirements-langgraph.txt')})
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    text=regression.render(report).replace('# 最小混合问题支持：','# LangGraph集成：')
    for row in report['challenge']:
        text=text.replace('## '+row['case']['id']+'\n', '## '+row['case']['id']+'\n\n图节点：'+
            ' → '.join(row['response']['node_trace'])+'\n',1)
    for row in extras:
        text+='\n\n## 额外端到端冒烟：'+row['name']+'\n\n'+row['question']+'\n\n'+row['response']['answer']+'\n\n```json\n'+json.dumps(row['response'],ensure_ascii=False,indent=2)+'\n```\n\n人工评分：待评。'
    output.with_suffix('.md').write_text(text,encoding='utf-8')
    print(json.dumps(report['summary'],ensure_ascii=False),flush=True)


if __name__=='__main__':main()
