"""Optional kNN routing using the existing BGE-M3 model and query vector."""
from functools import lru_cache
import json
from pathlib import Path
import os

import numpy as np

from service.intent_classifier import classify_intent, Intent, Store
from service.store_contract import boundary_intent


def semantic_enabled():
    return os.environ.get('RAG_SEMANTIC_ROUTING_ENABLED','0').lower() in ('1','true','on')


def unit_vector(vector):
    value=np.asarray(vector,dtype=np.float32)
    if value.shape!=(1024,) or not np.isfinite(value).all():
        raise ValueError('Routing requires native 1024-dimensional finite BGE-M3 vector')
    norm=float(np.linalg.norm(value))
    if norm==0: raise ValueError('Zero query vector')
    return value/norm


class SemanticRouter:
    def __init__(self,examples,vectors,threshold=0.60,margin=0.03):
        self.examples=examples
        self.vectors=np.stack([unit_vector(v) for v in vectors])
        self.threshold=threshold
        self.margin=margin
        self.positive=np.array([e['store']==Store.TICKET_RAW.value for e in examples])
        if not self.positive.any() or self.positive.all(): raise ValueError('Both store prototype classes required')

    def scores(self,vector):
        similarity=self.vectors@unit_vector(vector)
        # kNN score is mean of up to three nearest examples in each store class.
        top=lambda values:float(np.mean(np.sort(values)[-min(3,len(values)):]))
        positive,negative=top(similarity[self.positive]),top(similarity[~self.positive])
        return positive,negative

    def classify(self,question,vector):
        guard=boundary_intent(question)
        if guard: return guard
        legacy=classify_intent(question)
        if legacy.store==Store.TICKET_RAW: return legacy
        positive,negative=self.scores(vector)
        if positive>=self.threshold and positive-negative>=self.margin:
            return Intent(Store.TICKET_RAW,method='semantic_knn',reason=f'cosine={positive:.4f};margin={positive-negative:.4f}')
        return Intent(Store.RAG_CHUNKS,method='semantic_fallback',reason=f'cosine={positive:.4f};margin={positive-negative:.4f}')


@lru_cache(maxsize=1)
def load_router():
    from retrieval.search_chunks import load_model
    config=json.loads((Path(__file__).with_name('routing_prototypes.json')).read_text(encoding='utf-8'))
    model=load_model()  # same cached model used for retrieval
    result=model.encode([e['text'] for e in config['examples']],batch_size=8,max_length=8192,
        return_dense=True,return_sparse=False,return_colbert_vecs=False)
    return SemanticRouter(config['examples'],result['dense_vecs'],config['threshold'],config['margin'])


def classify_for_request(question):
    """Returns (Intent, optional query vector), encoding at most once for /ask."""
    from retrieval.search_chunks import load_model, encode_query
    guard=boundary_intent(question)
    if guard: return guard,None
    legacy=classify_intent(question)
    if legacy.store==Store.TICKET_RAW: return legacy,None
    vector=encode_query(load_model(),question)
    return load_router().classify(question,vector),vector
