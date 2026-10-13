import os
import unittest
from unittest.mock import patch,MagicMock

import numpy as np
from fastapi.testclient import TestClient
from service.intent_classifier import Intent,Store
from service.store_contract import boundary_intent
from service.semantic_router import SemanticRouter,classify_for_request
from service import retrieval_server as server
from retrieval.search_chunks import search


class SemanticTests(unittest.TestCase):
    def test_boundary_before_semantic_or_legacy_positive(self):
        for q in ('龙门石窟门票退票公告原文','龙门石窟门票优待政策资料','木札岭门票和园内交通收费',
                  '龙门石窟实名制分时购票怎么规定的？','老君山入园有什么限制或规定？'):
            self.assertEqual(boundary_intent(q).store,Store.RAG_CHUNKS)
            with patch('retrieval.search_chunks.encode_query') as encode,patch('service.semantic_router.load_router') as router:
                decision,vector=classify_for_request(q)
                self.assertEqual(decision.store,Store.RAG_CHUNKS)
                self.assertIsNone(vector)
                encode.assert_not_called();router.assert_not_called()

    def test_knn_threshold_margin_and_no_vector_mutation(self):
        a=np.zeros(1024,dtype=np.float32);a[0]=1
        b=np.zeros(1024,dtype=np.float32);b[1]=1
        router=SemanticRouter([{'store':Store.TICKET_RAW.value},{'store':Store.RAG_CHUNKS.value}],[a,b],0.60,0.03)
        original=a.copy()
        self.assertEqual(router.classify('进去花多少',a).store,Store.TICKET_RAW)
        self.assertEqual(router.classify('想了解这个地方',b).store,Store.RAG_CHUNKS)
        self.assertTrue(np.array_equal(a,original))
        with self.assertRaises(ValueError):router.scores(np.zeros(1024))
        with self.assertRaises(ValueError):router.scores(np.zeros(768))

    def test_one_encode_and_vector_forwarded_to_search(self):
        vector=np.ones(1024,dtype=np.float32)
        intent=Intent(Store.RAG_CHUNKS,method='semantic_fallback')
        router=MagicMock();router.classify.return_value=intent
        with patch('retrieval.search_chunks.load_model'),patch('retrieval.search_chunks.encode_query',return_value=vector) as encode, \
             patch('service.semantic_router.load_router',return_value=router):
            result,returned=classify_for_request('看看这个地方')
            self.assertIs(returned,vector);encode.assert_called_once()
        answer={'status':'insufficient_evidence','answer':'无法确认','citations':[],'warnings':[],'retrieved_sources':[]}
        with patch.object(server,'_MODEL_READY',True),patch.object(server,'semantic_enabled',return_value=True), \
             patch.object(server,'classify_for_request',return_value=(intent,vector)), \
             patch.object(server,'try_ticket_answer',return_value=None),patch.object(server,'search',return_value=[]) as retrieval, \
             patch.object(server,'answer_question',return_value=answer):
            response=TestClient(server.app).post('/ask',json={'question':'看看这个地方'})
            self.assertEqual(response.status_code,200)
            self.assertIs(retrieval.call_args.kwargs['query_vector'],vector)

    def test_search_with_shared_vector_never_reencodes(self):
        vector=np.ones(1024,dtype=np.float32)
        cursor=MagicMock();cursor.description=[];cursor.fetchall.return_value=[]
        conn=MagicMock();conn.cursor.return_value.__enter__.return_value=cursor
        with patch('retrieval.search_chunks.require_database_url',return_value='redacted'), \
             patch('retrieval.search_chunks.psycopg.connect') as connect,patch('retrieval.search_chunks.encode_query') as encode, \
             patch('retrieval.search_chunks.load_model') as load:
            connect.return_value.__enter__.return_value=conn
            self.assertEqual(search('同一问题',query_vector=vector),[])
            encode.assert_not_called();load.assert_not_called()
            with self.assertRaises(ValueError):search('错误维度',query_vector=np.ones(768))


if __name__=='__main__':unittest.main()
