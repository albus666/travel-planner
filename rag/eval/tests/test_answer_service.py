"""Contract checks: reject fabricated evidence and keep the search API unchanged."""
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from service.answer_service import AnswerUnavailable, validate_answer, answer_question
from service.quote_match import locate_quote
from service import retrieval_server as server


class AnswerTests(unittest.TestCase):
    def setUp(self):
        self.sources = [{'source_id': 'S1', 'chunk_id': 'c1', 'poi_id': 1,
            'name': '龙门石窟', 'theme': 'preferential', 'text': '老人：免费（60周岁（含）以上）。',
            'source_url': 'https://example.com/poi', 'collected_at': '2026-10-10T00:00:00Z',
            'verify_status': 'unverified'}]
        self.raw = {'status': 'answered', 'statements': [{'text': '资料记载60周岁及以上老人免费。',
            'evidence': [{'source_id': 'S1', 'quote': '老人：免费（60周岁（含）以上）'}]}], 'limitations': ''}

    def test_real_quotes_and_server_owned_metadata(self):
        result = validate_answer(self.raw, self.sources)
        self.assertEqual(result['status'], 'answered')
        self.assertIn('[S1：龙门石窟／preferential]', result['answer'])
        self.assertEqual(result['citations'][0]['source_url'], self.sources[0]['source_url'])
        self.assertEqual(len(result['warnings']), 2)

    def test_fabricated_source_or_quote_is_rejected(self):
        for evidence in ([{'source_id': 'S99', 'quote': '老人：免费'}],
                         [{'source_id': 'S1', 'quote': '所有游客今天免费'}], []):
            self.raw['statements'][0]['evidence'] = evidence
            result = validate_answer(self.raw, self.sources)
            self.assertEqual(result['status'], 'insufficient_evidence')
            self.assertEqual(result['citations'], [])

    def test_invalid_output_and_uncited_claim_is_rejected(self):
        for raw in (None, {}, {'status': 'answered', 'statements': [], 'limitations': ''},
                    {'status': 'answered', 'statements': [{'text': '今天开放'}], 'limitations': ''}):
            self.assertEqual(validate_answer(raw, self.sources)['citations'], [])

    def test_refusal(self):
        result = validate_answer({'status': 'insufficient_evidence', 'statements': [],
                                 'limitations': '资料未包含今天的营业状态。'}, self.sources)
        self.assertIn('无法确认', result['answer'])
        self.assertEqual(result['citations'], [])

    def test_ambiguous_multi_poi_policy_is_refused(self):
        sources = self.sources + [{**self.sources[0], 'source_id': 'S2', 'poi_id': 2, 'name': '龙门牡丹园'}]
        self.raw['statements'].append({'text': '龙门牡丹园老人免费。',
            'evidence': [{'source_id': 'S2', 'quote': '老人：免费（60周岁（含）以上）'}]})
        result = validate_answer(self.raw, sources, '去龙门老人免票吗')
        self.assertEqual(result['status'], 'insufficient_evidence')
        self.assertEqual(result['citations'], [])
        self.assertEqual(validate_answer(self.raw, sources, '比较龙门石窟和龙门牡丹园政策')['status'], 'answered')

    def test_non_breaking_space_in_source_does_not_reject_a_true_quote(self):
        # 真实案例：采集文本用 U+00A0，模型只能复述成普通空格，不能因此丢掉有据可查的事实。
        sources = [{**self.sources[0], 'theme': 'facilities', 'name': '老君山景区',
            'text': '【老君山景区 · 设施服务】\n- 停车场：名称：老君山停车场；参考价格：¥10/次\xa0；\xa0库位：1000。'}]
        raw = {'status': 'answered', 'statements': [{'text': '资料记载，老君山停车场参考价格为¥10/次。',
            'evidence': [{'source_id': 'S1', 'quote': '停车场：名称：老君山停车场；参考价格：¥10/次 ； 库位：1000。'}]}],
            'limitations': ''}
        result = validate_answer(raw, sources, '老君山停车场多少钱')
        self.assertEqual(result['status'], 'answered')
        # 展示的是原文切片，仍带 U+00A0，引用与来源逐字一致。
        self.assertIn('\xa0', result['citations'][0]['quotes'][0])

    def test_whitespace_tolerance_does_not_accept_altered_text(self):
        sources = [{**self.sources[0], 'text': '参考价格：¥10/次'}]
        for quote in ('参考价格：¥20/次', '参考价格：¥10/小时', '停车免费'):
            raw = {'status': 'answered', 'limitations': '',
                'statements': [{'text': '停车费10元。', 'evidence': [{'source_id': 'S1', 'quote': quote}]}]}
            self.assertEqual(validate_answer(raw, sources)['citations'], [], quote)

    def test_empty_retrieval_skips_llm(self):
        with patch('service.answer_service.call_llm') as llm:
            self.assertEqual(answer_question('今天开放吗', [])['status'], 'insufficient_evidence')
            llm.assert_not_called()

    def test_ask_defaults_errors_and_search_contract(self):
        client = TestClient(server.app)
        result = {'status': 'insufficient_evidence', 'answer': '无法确认', 'citations': [],
                  'warnings': [], 'retrieved_sources': []}
        with patch.object(server, 'try_ticket_answer', return_value=None), patch.object(server, '_MODEL_READY', True), patch.object(server, 'search', return_value=[]) as search, \
             patch.object(server, 'answer_question', return_value=result):
            response = client.post('/ask', json={'question': '今天开放吗'})
            self.assertEqual(response.status_code, 200)
            search.assert_called_with('今天开放吗', top_k=5)
            self.assertEqual(client.post('/ask', json={'question': '  '}).status_code, 422)
            response = client.post('/search', json={'question': '路线'})
            self.assertEqual(set(response.json()), {'question', 'top_k', 'hits', 'elapsed_ms'})
            search.assert_called_with('路线', top_k=3)
        with patch.object(server, 'try_ticket_answer', return_value=None), patch.object(server, '_MODEL_READY', True), patch.object(server, 'search', return_value=[]), \
             patch.object(server, 'answer_question', side_effect=AnswerUnavailable('模型暂不可用')):
            self.assertEqual(client.post('/ask', json={'question': '路线'}).status_code, 502)
        with patch.object(server, '_MODEL_READY', False):
            self.assertEqual(client.post('/ask', json={'question': '路线'}).status_code, 503)


class QuoteMatchTests(unittest.TestCase):
    def test_exact_and_whitespace_tolerant_spans(self):
        text = '参考价格：¥10/次\xa0；\xa0库位：1000。'
        self.assertEqual(locate_quote(text, '参考价格：¥10/次'), '参考价格：¥10/次')
        self.assertEqual(locate_quote(text, '¥10/次 ； 库位'), '¥10/次\xa0；\xa0库位')
        self.assertEqual(locate_quote(text, ' 库位：1000。 '), '库位：1000。')

    def test_invisible_separators_and_line_breaks(self):
        text = '停车场\n- 蓝牌车：10元/次\u200b；黄牌车：20元/次'
        self.assertEqual(locate_quote(text, '蓝牌车：10元/次；黄牌车：20元/次'), '蓝牌车：10元/次\u200b；黄牌车：20元/次')

    def test_unrelated_or_empty_quote_is_rejected(self):
        text = '参考价格：¥10/次'
        for quote in ('参考价格：¥20/次', '库位：1000', '', '\xa0'):
            self.assertIsNone(locate_quote(text, quote), quote)


if __name__ == '__main__':
    unittest.main()
