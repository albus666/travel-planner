import os
import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from service.ask_graph import create_graph
from service.graph_tools import TicketInput, RetrieveInput, ticket_sql, retrieve_chunks
from service.intent_classifier import Intent, Store
from service.mixed_service import MixedPlan, execute_mixed
from service import retrieval_server as server


def answer(text='路线证据',citations=None,status='answered'):
    return {'answer':text,'citations':citations or [],'status':status,'warnings':[], 'retrieved_sources':[]}


class GraphTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'RAG_MIXED_ENABLED':'1','RAG_SQL_TICKET_ENABLED':'1','RAG_LANGGRAPH_ENABLED':'0'})
        self.env.start();self.addCleanup(self.env.stop)

    def tools(self):
        sql={**answer('门票￥90起',[{'source_id':'SQL1','poi_id':77498}]),'route':'sql_ticket',
             'structured_data':{'poi_id':77498,'name':'龙门石窟','ticket_raw':'门票￥90起'},
             'ticket_lookup_executed':True,'entity_resolution':{'status':'resolved','matches':[]}}
        return MagicMock(return_value=sql),MagicMock(return_value=[{'chunk_id':'x'}]),MagicMock(return_value=answer(citations=[{'source_id':'S1','poi_id':77498}]))

    def invoke(self,tools,store=Store.RAG_CHUNKS,mixed=False,vector=None):
        graph=create_graph(*tools,classifier=lambda q:(Intent(store),vector),
            mixed_builder=lambda q:MixedPlan('龙门石窟门票原文','路线') if mixed else None)
        return graph.invoke({'question':'龙门石窟门票原文，路线','top_k':5})['result']

    def test_sql_only_skips_retrieval_and_generation_nodes(self):
        tools=self.tools();result=self.invoke(tools,Store.TICKET_RAW)
        self.assertEqual(result['node_trace'],['plan','ticket_sql','merge'])
        self.assertEqual(result['required_stores'],['ticket_sql'])
        self.assertEqual(result['tool_results']['rag']['state'],'not_queried')
        tools[0].assert_called_once();tools[1].assert_not_called();tools[2].assert_not_called()

    def test_rag_only_skips_sql_and_forwards_same_vector(self):
        tools=self.tools();vector=object();result=self.invoke(tools,vector=vector)
        self.assertEqual(result['node_trace'],['plan','retrieve_chunks','answer_validate','merge'])
        self.assertEqual(result['tool_results']['ticket_sql']['state'],'not_queried')
        tools[0].assert_not_called();self.assertIs(tools[1].call_args.kwargs['query_vector'],vector)

    def test_mixed_has_all_five_nodes_and_one_call_per_tool(self):
        tools=self.tools();result=self.invoke(tools,mixed=True)
        self.assertEqual(result['node_trace'],['plan','ticket_sql','retrieve_chunks','answer_validate','merge'])
        self.assertEqual([t['state'] for t in result['tasks']],['queried_with_evidence']*2)
        for tool in tools:tool.assert_called_once()
        tools[1].assert_called_once_with('龙门石窟：路线',top_k=5)

    def test_graph_merge_matches_frozen_mixed_behavior(self):
        graph_result=self.invoke(self.tools(),mixed=True)
        old_result=execute_mixed('龙门石窟门票原文，路线',MixedPlan('龙门石窟门票原文','路线'),5,
            ticket_tool=self.tools()[0],search_tool=self.tools()[1],answer_tool=self.tools()[2])
        for key in ('route','status','answer','citations','warnings','structured_data','retrieved_sources','required_stores','entity_resolution'):
            self.assertEqual(graph_result[key],old_result[key],key)

    def test_no_related_evidence_is_not_zero_hits(self):
        tools=self.tools();tools[2].return_value=answer('无法确认轮椅',status='insufficient_evidence')
        result=self.invoke(tools,mixed=True)
        rag=result['tool_results']['rag']
        self.assertEqual(rag['state'],'queried_no_evidence');self.assertEqual(rag['retrieved_count'],1)
        self.assertIn('门票￥90起',result['answer']);self.assertIn('无法确认轮椅',result['answer'])

    def test_documentary_citation_does_not_claim_wheelchair_support(self):
        tools=self.tools()
        tools[2].return_value={**answer('设施条目未提轮椅',[{'source_id':'S2','poi_id':77498}],status='insufficient_evidence'),
            'evidence_state':'queried_no_evidence','evidence_scope':'documentation_gap'}
        result=self.invoke(tools,mixed=True)
        self.assertEqual(result['tool_results']['rag']['state'],'queried_no_evidence')
        self.assertEqual(result['tool_results']['rag']['evidence_ids'],['S2'])
        self.assertEqual(result['tool_results']['rag']['result']['evidence_scope'],'documentation_gap')

    def test_sql_failure_preserves_text(self):
        tools=self.tools();tools[0].side_effect=RuntimeError('secret failure')
        result=self.invoke(tools,mixed=True)
        self.assertEqual(result['tool_results']['ticket_sql']['state'],'query_failed')
        self.assertIn('路线证据',result['answer']);self.assertNotIn('secret failure',str(result))
        tools[1].assert_called_once_with('龙门石窟：路线',top_k=5)

    def test_retrieval_failure_preserves_sql(self):
        tools=self.tools();tools[1].side_effect=RuntimeError('secret failure')
        result=self.invoke(tools,mixed=True)
        self.assertEqual(result['tool_results']['rag']['state'],'query_failed')
        self.assertIn('门票￥90起',result['answer']);tools[2].assert_not_called()

    def test_generation_failure_preserves_sql_and_query_fact(self):
        tools=self.tools();tools[2].side_effect=RuntimeError('secret failure')
        result=self.invoke(tools,mixed=True)
        self.assertEqual(result['tool_results']['rag']['state'],'query_failed')
        self.assertTrue(result['tool_results']['rag']['query_executed'])
        self.assertIn('门票￥90起',result['answer']);self.assertNotIn('secret failure',str(result))

    def test_sql_disabled_single_path_calls_only_rag(self):
        tools=self.tools()
        with patch.dict(os.environ,{'RAG_SQL_TICKET_ENABLED':'0'}):result=self.invoke(tools,Store.TICKET_RAW)
        self.assertEqual(result['required_stores'],['rag']);tools[0].assert_not_called();tools[1].assert_called_once()

    def test_disabled_sql_mixed_not_queried(self):
        tools=self.tools();tools[0].return_value=None
        result=self.invoke(tools,mixed=True)
        self.assertEqual(result['tool_results']['ticket_sql']['state'],'not_queried')
        self.assertIn('停用',result['answer']);self.assertIn('路线证据',result['answer'])

    def test_empty_sql_field_not_confused_with_not_queried(self):
        tools=self.tools();tools[0].return_value.update(answer='门票字段为空',citations=[],status='insufficient_evidence')
        result=self.invoke(tools,mixed=True)
        self.assertEqual(result['tool_results']['ticket_sql']['state'],'queried_no_evidence')
        self.assertTrue(result['tool_results']['ticket_sql']['query_executed'])

    def test_ambiguous_entity_blocks_rag(self):
        tools=self.tools();tools[0].return_value.update(ticket_lookup_executed=False,
            entity_resolution={'status':'multiple_matches','matches':[]},structured_data=None,citations=[],status='insufficient_evidence')
        result=self.invoke(tools,mixed=True)
        self.assertEqual(result['node_trace'],['plan','ticket_sql','merge'])
        self.assertEqual(result['tool_results']['rag']['reason'],'entity_unresolved')
        tools[1].assert_not_called();tools[2].assert_not_called()

    def test_other_poi_evidence_rejected(self):
        tools=self.tools();tools[2].return_value=answer('其他景点政策',[{'source_id':'S1','poi_id':22}])
        result=self.invoke(tools,mixed=True)
        self.assertEqual([c['source_id'] for c in result['citations']],['SQL1'])
        self.assertNotIn('其他景点政策',result['answer'])

    def test_off_switch_runs_current_ask_without_graph(self):
        tools=self.tools()
        with patch.object(server,'_MODEL_READY',True),patch.object(server,'mixed_enabled',return_value=False), \
             patch.object(server,'semantic_enabled',return_value=False),patch.object(server,'try_ticket_answer',tools[0]), \
             patch('service.ask_graph.run_graph') as run:
            response=TestClient(server.app).post('/ask',json={'question':'龙门石窟门票原文'})
        self.assertEqual(response.status_code,200)
        self.assertFalse({'workflow','node_trace','tool_results'} & response.json().keys())
        run.assert_not_called();tools[0].assert_called_once_with('龙门石窟门票原文')

    def test_search_never_runs_graph_even_when_enabled(self):
        with patch.dict(os.environ,{'RAG_LANGGRAPH_ENABLED':'1'}),patch.object(server,'_MODEL_READY',True), \
             patch.object(server,'search',return_value=[]) as search,patch('service.ask_graph.run_graph') as run:
            response=TestClient(server.app).post('/search',json={'question':'历史'})
        self.assertEqual(response.status_code,200);search.assert_called_once();run.assert_not_called()

    def test_graph_metadata_serializes_only_when_graph_used(self):
        payload={**answer(), 'question':'路线','top_k':5,'elapsed_ms':1.0}
        old=server.AskResponse(**payload).model_dump()
        self.assertFalse({'workflow','node_trace','tool_results'} & old.keys())
        new=server.AskResponse(**payload,workflow='langgraph_v1',node_trace=['plan'],tool_results={}).model_dump()
        self.assertEqual(new['workflow'],'langgraph_v1');self.assertEqual(new['node_trace'],['plan'])


if __name__=='__main__':unittest.main()
