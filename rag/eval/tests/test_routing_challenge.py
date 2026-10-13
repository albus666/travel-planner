"""Check that evaluation never counts partial mixed routing as success."""
import unittest
from eval.runners.run_routing_challenge import RAG, SQL, store_metrics


def row(expected, predicted):
    return {'case':{'expected_stores':expected}, 'predicted_store':predicted,
            'store_correct':expected == [predicted]}


class ChallengeMetricsTests(unittest.TestCase):
    def test_mixed_not_counted_as_single_store_success(self):
        metrics = store_metrics([row([SQL,RAG],RAG),row([SQL,RAG],SQL)])
        self.assertEqual(metrics['single_store_count'],0)
        self.assertEqual(metrics['mixed_count'],2)
        self.assertEqual(metrics['mixed_full_store_coverage'],0)
        self.assertEqual(metrics['ticket_false_positive'],0)
        self.assertEqual(metrics['ticket_false_negative'],0)

    def test_false_positive_and_negative_are_separate(self):
        metrics = store_metrics([row([SQL],RAG),row([RAG],SQL),row([SQL],SQL)])
        self.assertEqual(metrics['single_store_correct'],1)
        self.assertEqual(metrics['ticket_false_positive'],1)
        self.assertEqual(metrics['ticket_false_negative'],1)

    def test_route_match_never_implies_answer_pass(self):
        self.assertEqual(store_metrics([row([RAG],RAG)])['answer_quality'],'pending_human_review')


if __name__ == '__main__':
    unittest.main()
