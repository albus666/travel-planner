import os
import unittest
from datetime import datetime, timezone
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from service import retrieval_server as server
from service.ticket_service import is_ticket_question, resolve_poi, format_ticket, try_ticket_answer, CATALOG_SQL, TICKET_SQL


class TicketTests(unittest.TestCase):
    def row(self, raw='门票￥90起', detail=77498):
        return (77498, '龙门石窟', 'https://example.com/catalog', detail, raw,
                {'source_url':'https://example.com/detail', 'source':'ctrip'},
                datetime(2026,10,11,12,36,44,tzinfo=timezone.utc), 'unverified')

    def test_rule_preserves_vector_topics(self):
        for q in ('龙门石窟门票资料记载是什么？', '龙门石窟今天成人门票准确多少钱？'):
            self.assertTrue(is_ticket_question(q))
        for q in ('龙门石窟门票免票政策是什么？', '龙门石窟路线介绍', '木札岭旅游区停车价格', '今天是否开放？'):
            self.assertFalse(is_ticket_question(q))

    def test_all_frozen_answer_cases_keep_vector_routing(self):
        dataset = Path(__file__).resolve().parents[1] / 'cases/answer_holdout_v1.jsonl'
        if not dataset.exists():
            dataset = Path('/home/ubuntu/apps/travel-planner/rag/eval/cases/answer_holdout_v1.jsonl')
        for line in dataset.read_text(encoding='utf-8').splitlines():
            case = json.loads(line)
            self.assertFalse(is_ticket_question(case['question']), case['id'])

    def test_exact_entity_nested_names_and_ambiguity(self):
        catalog = [(1,'老君山'),(2,'老君山景区'),(3,'龙门石窟'),(4,'卢舍那大佛')]
        self.assertEqual(resolve_poi('老君山景区门票价格',catalog),(2,'老君山景区'))
        self.assertIsNone(resolve_poi('老君山和龙门石窟门票价格',catalog))
        self.assertIsNone(resolve_poi('龙门石窟卢舍那大佛门票价格',catalog))
        self.assertIsNone(resolve_poi('龙门门票多少钱',catalog))
        self.assertIsNone(resolve_poi('老君山门票',[(1,'老君山'),(2,'老君山')]))

    def test_raw_preserved_and_metadata(self):
        result = format_ticket(self.row(), '龙门石窟门票资料原文是什么？')
        self.assertEqual(result['structured_data']['ticket_raw'], '门票￥90起')
        self.assertEqual(result['citations'][0]['quotes'], ['门票￥90起'])
        self.assertEqual(result['citations'][0]['source_url'], 'https://example.com/detail')
        self.assertEqual(result['structured_data']['collected_at'],'2026-10-11T20:36:44+08:00')
        self.assertEqual(result['status'],'answered')
        self.assertNotIn('amount',result['structured_data'])

    def test_null_empty_missing_not_free(self):
        for raw, detail in ((None,None),(None,77498),('',77498),('  ',77498)):
            result = format_ticket(self.row(raw,detail),'龙门石窟门票资料')
            self.assertEqual(result['status'],'insufficient_evidence')
            self.assertEqual(result['structured_data']['ticket_raw'],raw)
            self.assertEqual(result['citations'],[])
            self.assertIn('不能据此推断免费',result['answer'])

    def test_realtime_and_ticket_type_not_inferred(self):
        for question in ('龙门石窟今天门票多少钱？','龙门石窟成人门票价格？'):
            result = format_ticket(self.row(),question)
            self.assertEqual(result['status'],'insufficient_evidence')
            self.assertIn('门票￥90起',result['answer'])

    def test_free_text_and_qualifiers_preserved(self):
        raw = '免费开放，具体收费情况以现场公示为主'
        result = format_ticket(self.row(raw),'龙门石窟门票资料')
        self.assertEqual(result['structured_data']['ticket_raw'],raw)
        self.assertIn(raw,result['answer'])
        self.assertNotIn('amount',result['structured_data'])

    def test_fixed_sql_bound_id_and_readonly_option(self):
        conn = MagicMock()
        conn.execute.side_effect = [MagicMock(fetchall=lambda:[(77498,'龙门石窟')]),
                                   MagicMock(fetchone=lambda:self.row())]
        with patch('service.ticket_service.require_database_url',return_value='redacted'), \
             patch('service.ticket_service.psycopg.connect') as connect:
            connect.return_value.__enter__.return_value=conn
            result = try_ticket_answer("龙门石窟门票价格'; DROP TABLE v2.poi_details; --")
            self.assertEqual(result['structured_data']['poi_id'],77498)
            connect.assert_called_once_with('redacted',options='-c default_transaction_read_only=on -c statement_timeout=5000')
            self.assertEqual(conn.execute.call_args_list[0].args,(CATALOG_SQL,))
            self.assertEqual(conn.execute.call_args_list[1].args,(TICKET_SQL,(77498,)))

    def test_disabled_and_sql_endpoint_skips_vector_llm(self):
        with patch.dict(os.environ,{'RAG_SQL_TICKET_ENABLED':'0'}), patch('service.ticket_service.psycopg.connect') as connect:
            self.assertIsNone(try_ticket_answer('龙门石窟门票价格'))
            connect.assert_not_called()
        result = format_ticket(self.row(),'龙门石窟门票资料')
        with patch.object(server,'_MODEL_READY',True), patch.object(server,'try_ticket_answer',return_value=result), \
             patch.object(server,'search') as search, patch.object(server,'answer_question') as llm:
            response = TestClient(server.app).post('/ask',json={'question':'龙门石窟门票资料'})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['route'],'sql_ticket')
            search.assert_not_called()
            llm.assert_not_called()


if __name__ == '__main__':
    unittest.main()
