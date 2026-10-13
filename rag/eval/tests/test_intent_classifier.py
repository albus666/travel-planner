import ast
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from service.intent_classifier import classify_intent, Store
from service.ticket_service import is_ticket_question

ROOT = Path(__file__).resolve().parents[3]


class IntentTests(unittest.TestCase):
    def test_25_and_73_identical_rule_behavior(self):
        count = 0
        for filename in ('answer_holdout_v1.jsonl', 'eval_questions.jsonl'):
            for line in (ROOT/'rag/eval/cases'/filename).read_text(encoding='utf-8').splitlines():
                if not line.strip() or line.lstrip().startswith('#'):
                    continue
                question = json.loads(line)['question']
                self.assertEqual(classify_intent(question).store == Store.TICKET_RAW, is_ticket_question(question))
                count += 1
        self.assertEqual(count, 98)

    def test_classifier_does_not_access_db_or_model(self):
        with patch('service.ticket_service.psycopg.connect') as db:
            self.assertEqual(classify_intent('龙门石窟门票资料是什么？').store, Store.TICKET_RAW)
            self.assertEqual(classify_intent('龙门石窟历史介绍').store, Store.RAG_CHUNKS)
            db.assert_not_called()

    def test_adapter_invokes_existing_rule_verbatim(self):
        question = ' 龙门石窟门票价格 '
        with patch('service.ticket_service.is_ticket_question', return_value=True) as rule:
            self.assertEqual(classify_intent(question).store, Store.TICKET_RAW)
            rule.assert_called_once_with(question)


if __name__ == '__main__': unittest.main()
