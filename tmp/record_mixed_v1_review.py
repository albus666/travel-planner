import collections
import hashlib
import json
from pathlib import Path
import shutil

root=Path(__file__).resolve().parents[1]
p=root/'rag/eval/reports/mixed_v1_live_fault_scope_followup.json'
md=p.with_suffix('.md')
report=json.loads(p.read_text(encoding='utf-8'))
assert report['run_complete'] and len(report['challenge'])==4
assert report.get('human_review_status')!='completed'
fields=['fact_support','citation_support','poi_isolation','refusal_correct','freshness_correct','key_points_covered']
original_hash=hashlib.sha256(p.read_bytes()).hexdigest()
payload_hash=hashlib.sha256(json.dumps([r['response'] for r in report['challenge']],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
for original in (p,md):
    backup=original.with_name(original.stem+'_unreviewed'+original.suffix)
    assert not backup.exists()
    shutil.copyfile(original,backup)
scores={}
for row in report['challenge']:
    cid=row['case']['id']
    assert cid in [f'challenge-v1-{n}' for n in (27,28,29,30)]
    review={field:'pass' for field in fields}
    review.update(attribution='na',source='user supplied per-case re-review table',review_date='2026-10-12',
        notes='按回答是否正确覆盖全部子问题评分；本次调用所需SQL与RAG，引用匹配，无景点串扰。')
    if cid.endswith('29'):
        review['notes']+='轮椅部分查过但缺少支持证据，无法确认不等于没有轮椅设施；queried_no_evidence不等于零检索片段。'
    row['human_review']=review
    scores[cid]=review
for row in report['mixed_acceptance']:row['human_review']=scores[row['id']]
report.update(human_review_status='completed',answer_quality='user_review_passed_on_four_cases',
    human_review_summary={'count':4,'all_applicable_pass':4,'pass_cells':24,'fail_cells':0,'na_cells':0,
        'source':'user supplied per-case re-review table','scope':'these four synthetic mixed cases only',
        'original_unreviewed_report_sha256':original_hash,'response_payload_sha256':payload_hash,
        'acceptance_status':'mixed_v1_accepted'})
report['summary']['new_answer_human_review']='completed_4_of_4_pass'
assert payload_hash==hashlib.sha256(json.dumps([r['response'] for r in report['challenge']],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
p.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
text=md.read_text(encoding='utf-8').replace('新回答需重新评分，未沿用之前的用户分数。自动检查工具调用、原文与引用，不将它们等同于事实与完整性人工验收。',
    '用户已对本文件这四个回答逐题复评，按“正确覆盖全部子问题”口径均通过。原始回答与证据未修改；结果仅适用于这四道合成题，不代表真实问题整体准确率。')
text=text.replace('"new_answer_human_review": "pending"','"new_answer_human_review": "completed_4_of_4_pass"')
text=text.replace('人工评分：事实 __；引用 __；景点隔离 __；拒答 __；时效 __；覆盖 __；归因 __',
    '用户评分：事实 pass；引用 pass；景点隔离 pass；拒答 pass；时效 pass；覆盖 pass；归因 na')
intro='\n\n用户复评：4/4通过，六项评分共24 pass、0 fail、0 na，混合问答v1本轮验收通过。第29题RAG有返回片段，但没有支持轮椅需求的相关证据；queried_no_evidence不表示没有检索片段。冻结基线：rag/eval/baselines/mixed_v1/。\n\n'
text=text.replace('\n## challenge-v1-27',intro+'## challenge-v1-27',1)
md.write_text(text,encoding='utf-8')
print(json.dumps(report['human_review_summary'],ensure_ascii=False))
