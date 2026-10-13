import os
import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from service.intent_classifier import Intent, Store
from service.mixed_service import build_mixed_plan, execute_mixed, MixedPlan
from service.ticket_service import try_ticket_answer, CATALOG_SQL, TICKET_SQL
from service import retrieval_server as server


def result(answer, citations=None, status='answered'):
    return {'answer':answer,'citations':citations or [],'status':status,'warnings':[], 'retrieved_sources':[]}


class MixedTests(unittest.TestCase):
    def plan(self, question):
        return build_mixed_plan(question, lambda q:Intent(Store.TICKET_RAW))

    def test_four_explicit_compound_requests(self):
        for q in ('龙门石窟门票资料原文是什么，游览路线怎么安排？',
                  '老君山景区入场花多少钱，同时给我讲讲历史。',
                  '凤翔温泉门票资料怎么写，有没有轮椅设施？',
                  '龙门石窟票价资料和老人免票条件分别是什么？'):
            plan = self.plan(q)
            self.assertIsNotNone(plan,q)
            self.assertEqual(plan.required_stores,('ticket_sql','rag'))
            self.assertNotIn('老人',plan.ticket_question)

    def test_single_non_ticket_and_negated_price_do_not_gain_sql_tool(self):
        for q in ('龙门石窟票价资料多少钱？','龙门石窟游览路线怎么走？',
                  '龙门石窟餐饮价格高吗？不要给门票价格。',
                  '木札岭旅游区小交通含在大门票里吗？资料中的往返参考价是多少？'):
            self.assertIsNone(self.plan(q),q)

    def tools(self):
        sql = {**result('门票￥90起',[{'source_id':'SQL1','poi_id':77498}]),
               'structured_data':{'name':'龙门石窟','poi_id':77498},
               'ticket_lookup_executed':True, 'entity_resolution':{'status':'resolved','matches':[]}}
        rag = result('资料未说明轮椅设施',status='insufficient_evidence')
        return MagicMock(return_value=sql),MagicMock(return_value=[{'chunk_id':'x'}]),MagicMock(return_value=rag)

    def test_partial_refusal_keeps_price_and_separate_task_states(self):
        ticket,search,answer=self.tools()
        output=execute_mixed('龙门石窟门票资料，轮椅设施？',MixedPlan('龙门石窟门票资料','轮椅设施？'),5,
            ticket_tool=ticket,search_tool=search,answer_tool=answer)
        self.assertIn('门票￥90起',output['answer'])
        self.assertEqual([t['state'] for t in output['tasks']],['queried_with_evidence','queried_no_evidence'])
        self.assertEqual(output['status'],'insufficient_evidence')
        self.assertEqual(output['tasks'][0]['evidence_ids'],['SQL1'])
        search.assert_called_once_with('龙门石窟：轮椅设施？',top_k=5)

    def test_cited_documentation_gap_retains_no_capability_evidence_state(self):
        ticket,search,answer=self.tools()
        answer.return_value={**result('设施条目未提到轮椅',[{'source_id':'S2','poi_id':77498}],status='insufficient_evidence'),
            'evidence_state':'queried_no_evidence','evidence_scope':'documentation_gap'}
        output=execute_mixed('龙门石窟门票，轮椅设施',MixedPlan('龙门石窟门票','轮椅设施'),5,
            ticket_tool=ticket,search_tool=search,answer_tool=answer)
        self.assertEqual(output['tasks'][1]['state'],'queried_no_evidence')
        self.assertEqual(output['tasks'][1]['evidence_ids'],['S2'])

    def test_rag_failure_keeps_successful_sql(self):
        ticket,search,answer=self.tools(); search.side_effect=RuntimeError('private DB failure')
        output=execute_mixed('龙门石窟门票，路线？',MixedPlan('龙门石窟门票','路线'),5,
            ticket_tool=ticket,search_tool=search,answer_tool=answer)
        self.assertIn('门票￥90起',output['answer'])
        self.assertEqual(output['tasks'][1]['state'],'query_failed')
        self.assertNotIn('private DB failure',output['answer'])

    def test_sql_failure_keeps_successful_rag(self):
        ticket,search,answer=self.tools();ticket.side_effect=RuntimeError('private error')
        answer.return_value=result('路线证据',[{'source_id':'S1','poi_id':77498}])
        output=execute_mixed('龙门石窟门票，路线？',MixedPlan('龙门石窟门票','路线'),5,
            ticket_tool=ticket,search_tool=search,answer_tool=answer)
        self.assertIn('路线证据',output['answer'])
        self.assertEqual(output['tasks'][0]['state'],'query_failed')
        self.assertEqual(output['tasks'][1]['state'],'queried_with_evidence')
        search.assert_called_once_with('龙门石窟：路线',top_k=5)

    def test_disabled_sql_not_confused_with_empty_field(self):
        ticket,search,answer=self.tools();ticket.return_value=None
        output=execute_mixed('龙门石窟门票，路线？',MixedPlan('龙门石窟门票','路线'),5,
            ticket_tool=ticket,search_tool=search,answer_tool=answer)
        self.assertEqual(output['tasks'][0]['state'],'not_queried')
        self.assertIn('停用',output['answer'])
        ticket,search,answer=self.tools();ticket.return_value['citations']=[]
        ticket.return_value['answer']='门票字段为空';ticket.return_value['status']='insufficient_evidence'
        output=execute_mixed('龙门石窟门票，路线？',MixedPlan('龙门石窟门票','路线'),5,
            ticket_tool=ticket,search_tool=search,answer_tool=answer)
        self.assertEqual(output['tasks'][0]['state'],'queried_no_evidence')

    def test_entity_conflict_blocks_both_record_lookup_and_rag(self):
        conn=MagicMock();conn.execute.return_value.fetchall.return_value=[(1,'龙门石窟'),(2,'老君山景区')]
        with patch.dict(os.environ,{'RAG_SQL_TICKET_ENABLED':'1'}),patch('service.ticket_service.require_database_url',return_value='private'),patch('service.ticket_service.psycopg.connect') as connect:
            connect.return_value.__enter__.return_value=conn
            ticket=try_ticket_answer('龙门石窟门票资料',intent=Intent(Store.TICKET_RAW),
                entity_question='龙门石窟和老君山景区门票资料，路线怎么走')
            self.assertIn('一次只支持一个景点',ticket['answer'])
            self.assertIn('龙门石窟、老君山景区',ticket['answer'])
            conn.execute.assert_called_once_with(CATALOG_SQL)
        search=MagicMock();answer=MagicMock()
        output=execute_mixed('两个景点门票与路线',MixedPlan('门票','路线'),5,
            ticket_tool=MagicMock(return_value=ticket),search_tool=search,answer_tool=answer)
        self.assertEqual([t['state'] for t in output['tasks']],['not_queried','not_queried'])
        search.assert_not_called();answer.assert_not_called()

    def test_cross_poi_rag_facts_rejected_without_losing_ticket(self):
        ticket,search,answer=self.tools();answer.return_value=result('其他景点政策',[{'source_id':'S1','poi_id':123}])
        output=execute_mixed('龙门石窟门票，老人优待',MixedPlan('龙门石窟门票','老人优待'),5,
            ticket_tool=ticket,search_tool=search,answer_tool=answer)
        self.assertEqual([c['source_id'] for c in output['citations']],['SQL1'])
        self.assertNotIn('其他景点政策',output['answer'])

    def test_http_mixed_dispatch_and_response_contract(self):
        ticket,search,answer=self.tools()
        with patch.object(server,'_MODEL_READY',True),patch.object(server,'mixed_enabled',return_value=True), \
             patch.object(server,'build_mixed_plan',return_value=MixedPlan('龙门石窟门票资料','轮椅设施')), \
             patch.object(server,'try_ticket_answer',ticket),patch.object(server,'search',search),patch.object(server,'answer_question',answer):
            response=TestClient(server.app).post('/ask',json={'question':'龙门石窟门票资料与轮椅设施'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['route'],'mixed')
        self.assertEqual(response.json()['required_stores'],['ticket_sql','rag'])
        ticket.assert_called_once();search.assert_called_once();answer.assert_called_once()


if __name__=='__main__':unittest.main()
