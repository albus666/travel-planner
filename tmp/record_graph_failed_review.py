from pathlib import Path
import hashlib,json,shutil
root=Path(__file__).resolve().parents[1]
p=root/'rag/eval/reports/langgraph_v1_schema_followup.json';md=p.with_suffix('.md')
r=json.loads(p.read_text(encoding='utf-8'))
assert r.get('human_review_status')!='completed'
for f in (p,md):
    dest=f.with_name(f.stem+'_unreviewed'+f.suffix);assert not dest.exists();shutil.copyfile(f,dest)
fields=['fact_support','citation_support','poi_isolation','refusal_correct','freshness_correct','key_points_covered']
payload_sha=hashlib.sha256(json.dumps([c['response'] for c in r['challenge']],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
reviews={}
for c in r['challenge']:
    n=int(c['case']['id'][-2:]);scores=dict.fromkeys(fields,'pass')
    if n==29:scores['citation_support']='fail'
    if n==30:scores['fact_support']=scores['key_points_covered']='fail'
    scores.update(attribution_marker='fail' if n==29 else 'pass',source='user supplied new LangGraph re-review table',
        notes='限制说明中的设施资料观察未引用。' if n==29 else '原文国籍/永久居留适用范围冲突未暴露，仍下确定老人免票结论。' if n==30 else '')
    c['human_review']=scores;reviews[c['case']['id']]=scores
for c in r['mixed_acceptance']:c['human_review']=reviews[c['id']]
r.update(human_review_status='completed',answer_quality='user_review_failed_2_of_4_cases',
    human_review_summary={'cases':4,'all_six_dimensions_pass':2,'six_dimension_pass':21,'six_dimension_fail':3,
        'including_user_attribution_marker_pass':24,'including_user_attribution_marker_fail':4,
        'attribution_column_semantics':'preserved user pass/fail marker, not replaced by a causal label',
        'scope':'latest four LangGraph answers only','response_payload_sha256':payload_sha,
        'acceptance':'not_accepted_do_not_freeze'})
r['summary']['new_answer_human_review']='completed_with_failures'
p.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
text=md.read_text(encoding='utf-8')
text=text.replace('新回答需重新评分，未沿用之前的用户分数。自动检查工具调用、原文与引用，不将它们等同于事实与完整性人工验收。',
    '用户已对本文件新回答逐题复评，未沿用混合v1分数：27、28六项通过；29引用失败；30事实与要点覆盖失败。暂不验收或冻结。')
text=text.replace('"new_answer_human_review": "pending"','"new_answer_human_review": "completed_with_failures"')
for cid,scores in reviews.items():
    old='人工评分：事实 __；引用 __；景点隔离 __；拒答 __；时效 __；覆盖 __；归因 __'
    labels=('事实','引用','景点隔离','拒答/不确定性','时效','覆盖')
    new='用户评分：'+'；'.join(f'{label} {scores[f]}' for label,f in zip(labels,fields))+'；归因标记 '+scores['attribution_marker']
    if scores['notes']:new+='\n\n评审说明：'+scores['notes']
    text=text.replace(old,new,1)
text=text.replace('\n## challenge-v1-27','\n\n用户表含归因标记共28格：24 pass、4 fail；六项答案评分共24格：21 pass、3 fail。归因栏pass/fail原样保留，不解释为错误类别。原回答与证据未改，修复后必须另存新报告重新评审。\n\n## challenge-v1-27',1)
md.write_text(text,encoding='utf-8')
assert payload_sha==hashlib.sha256(json.dumps([c['response'] for c in r['challenge']],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
print(json.dumps(r['human_review_summary'],ensure_ascii=False))
