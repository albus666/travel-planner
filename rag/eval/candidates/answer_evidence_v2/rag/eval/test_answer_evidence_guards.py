import unittest
from unittest.mock import patch
from service.answer_evidence_guards import evidence_guard
from service.answer_service import answer_question, validate_answer


def source(text,theme='preferential',name='龙门石窟',poi=77498,sid='S1'):
    return {'text':text,'theme':theme,'name':name,'poi_id':poi,'source_id':sid,'chunk_id':'fixture-'+sid,
            'source_url':'https://example.com/fixture','collected_at':'2026-10-11T20:00:00+08:00','verify_status':'unverified'}


class EvidenceGuardTests(unittest.TestCase):
    allow='- 老人：免费（60周岁（含）以上老年人（含中华人民共和国外国人永久居留身份证））'
    deny='补充说明：以上免票范围，除身高1.4米以下未成年人不限国籍，其他仅限中国公民享有。'

    def test_same_chunk_conflict_has_two_quotes_and_no_resolved_eligibility(self):
        sources=[source(self.allow+'\n'+self.deny)]
        raw,metadata=evidence_guard('龙门石窟老人免票条件',sources)
        result=validate_answer(raw,sources,'龙门石窟老人免票条件')
        self.assertEqual(result['status'],'insufficient_evidence')
        self.assertIn('口径存在冲突',result['answer']);self.assertIn('向景区官方核实',result['answer'])
        self.assertEqual(set(result['citations'][0]['quotes']),{self.allow,self.deny})
        self.assertEqual(metadata['evidence_scope'],'conflicting_policy')

    def test_conflict_across_two_same_poi_chunks(self):
        sources=[source(self.allow),source(self.deny,sid='S2')]
        raw,_=evidence_guard('龙门石窟外籍老人免票吗',sources)
        result=validate_answer(raw,sources,'龙门石窟外籍老人免票吗')
        self.assertEqual({c['source_id'] for c in result['citations']},{'S1','S2'})

    def test_other_poi_restriction_cannot_create_target_conflict(self):
        sources=[source(self.allow),source(self.deny,name='其他景点',poi=2,sid='S2')]
        self.assertIsNone(evidence_guard('龙门石窟老人免票',sources))

    def test_unilateral_or_negative_foreign_residency_text_not_conflict(self):
        for text in (self.allow,self.deny,self.allow.replace('（含中华人民共和国','（不含中华人民共和国')+'\n'+self.deny):
            self.assertIsNone(evidence_guard('龙门石窟老人免票',[source(text)]))

    def test_ambiguous_target_never_auto_assigned(self):
        self.assertIsNone(evidence_guard('龙门老人免票',[source(self.allow+'\n'+self.deny)]))
        self.assertIsNone(evidence_guard('龙门石窟老人游览路线怎么走',[source(self.allow+'\n'+self.deny)]))

    def test_wheelchair_gap_has_facilities_citation_but_no_capability_evidence(self):
        text='【凤翔温泉 · 设施服务】\n- 停车场：参考价格：免费；库位：200'
        sources=[source(text,'facilities','凤翔温泉',10615019,'S2')]
        raw,metadata=evidence_guard('凤翔温泉有没有轮椅设施',sources)
        result=validate_answer(raw,sources,'凤翔温泉有没有轮椅设施')
        self.assertIn('本次提供的凤翔温泉设施条目仅列出停车场',result['answer'])
        self.assertIn('不等于现场没有',result['answer'])
        self.assertEqual(result['citations'][0]['quotes'],[text])
        self.assertEqual(metadata['evidence_state'],'queried_no_evidence')

    def test_facilities_with_other_entries_not_described_as_parking_only(self):
        for text in ('- 停车场：免费\n- 淋浴：有','- 停车场：免费\n还有淋浴设施。'):
            sources=[source(text,'facilities','凤翔温泉',10615019)]
            raw,_=evidence_guard('凤翔温泉轮椅设施',sources)
            self.assertNotIn('仅列出停车场',raw['statements'][0]['text'])

    def test_explicit_wheelchair_evidence_uses_normal_generation(self):
        sources=[source('- 轮椅：可借用','facilities','凤翔温泉',10615019)]
        self.assertIsNone(evidence_guard('凤翔温泉轮椅设施',sources))

    def test_uncited_source_content_in_limitations_is_rejected(self):
        s=source('- 停车场：免费','facilities','凤翔温泉',10615019)
        raw={'status':'insufficient_evidence','statements':[],
            'limitations':'提供的设施条目仅记载停车场，不能确认轮椅。'}
        result=validate_answer(raw,[s],'凤翔温泉轮椅')
        self.assertEqual(result['citations'],[])
        self.assertNotIn('仅记载停车场',result['answer'])

    def test_valid_limitation_evidence_cited_invalid_quote_rejected(self):
        s=source('- 停车场：免费','facilities','凤翔温泉',10615019)
        raw={'status':'insufficient_evidence','statements':[],
            'limitations':'提供的设施条目仅记载停车场，不能确认轮椅。',
            'limitations_evidence':[{'source_id':'S1','quote':s['text']}]}
        self.assertIn('[S1：凤翔温泉／facilities]',validate_answer(raw,[s])['answer'])
        raw['limitations_evidence'][0]['quote']='轮椅：可免费借用'
        self.assertEqual(validate_answer(raw,[s])['citations'],[])

    def test_guard_skips_llm_and_preserves_sources_and_time(self):
        s=source(self.allow+'\n'+self.deny)
        with patch('service.answer_service.attach_sources',return_value=[s]),patch('service.answer_service.call_llm') as llm:
            result=answer_question('龙门石窟老人免票',[s])
        llm.assert_not_called()
        self.assertEqual(result['retrieved_sources'],[s])
        self.assertEqual(result['citations'][0]['collected_at'],s['collected_at'])
