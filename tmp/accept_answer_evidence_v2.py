from pathlib import Path
import hashlib,json,shutil
root=Path(__file__).resolve().parents[1]
p=root/'rag/eval/reports/langgraph_answer_v2_scope_followup.json';md=p.with_suffix('.md')
r=json.loads(p.read_text(encoding='utf-8'));assert r['run_complete'] and len(r['challenge'])==4
assert r.get('human_review_status')!='completed'
for f in (p,md):
    b=f.with_name(f.stem+'_unreviewed'+f.suffix);assert not b.exists();shutil.copyfile(f,b)
payload_sha=hashlib.sha256(json.dumps([c['response'] for c in r['challenge']],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
fields=['fact_support','citation_support','poi_isolation','refusal_correct','freshness_correct','key_points_covered']
scores={}
for c in r['challenge']:
    assert c['case']['id'] in ('challenge-v1-27','challenge-v1-28','challenge-v1-29','challenge-v1-30')
    review={f:'pass' for f in fields};review.update(attribution_marker='pass',review_date='2026-10-13',source='user independent re-review of latest answer_evidence_v2 four-case report')
    c['human_review']=review;scores[c['case']['id']]=review
for c in r['mixed_acceptance']:c['human_review']=scores[c['id']]
r.update(human_review_status='completed',answer_quality='accepted_on_four_cases',human_review_summary={
    'all_four_cases_pass':True,'six_dimension_pass':24,'including_user_attribution_marker_pass':28,
    'fail':0,'scope':'latest four report cases only','response_payload_sha256':payload_sha,
    'guard_scope':'known wheelchair documentation gap and elderly nationality conflict; not general contradiction detection',
    'acceptance':'human_accepted_frozen','review_date':'2026-10-13'})
r['summary']['new_answer_human_review']='completed_4_of_4_pass'
p.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
text=md.read_text(encoding='utf-8')
text=text.replace('新回答需重新评分，未沿用之前的用户分数。自动检查工具调用、原文与引用，不将它们等同于事实与完整性人工验收。','用户于2026-10-13独立复评本文件四题，六项与归因标记共28项全部pass，无fail。answer_evidence_v2本轮验收通过并冻结；仅代表这四题，guard不是通用矛盾检测。')
text=text.replace('"new_answer_human_review": "pending"','"new_answer_human_review": "completed_4_of_4_pass"')
text=text.replace('人工评分：事实 __；引用 __；景点隔离 __；拒答 __；时效 __；覆盖 __；归因 __','用户评分：事实 pass；引用 pass；景点隔离 pass；不确定性处理 pass；时效 pass；覆盖 pass；归因标记 pass')
md.write_text(text,encoding='utf-8')
print(json.dumps(r['human_review_summary'],ensure_ascii=False))
