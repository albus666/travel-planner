import collections
import hashlib
import json
from pathlib import Path
import shutil

root=Path(__file__).resolve().parents[1]
path=root/'rag/eval/reports/routing_challenge_v1_run1.json'
md=path.with_suffix('.md')
fields=['fact_support','citation_support','poi_isolation','refusal_correct','freshness_correct','key_points_covered']
report=json.loads(path.read_text(encoding='utf-8'))
assert len(report['cases'])==30 and report['run_complete']
if report.get('human_review_status')=='completed': raise SystemExit('Already reviewed')
for original in (path,md):
    backup=original.with_name(original.stem+'_unreviewed'+original.suffix)
    if backup.exists(): raise SystemExit('Backup exists')
    shutil.copyfile(original,backup)
responses_before=hashlib.sha256(json.dumps([r['response'] for r in report['cases']],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
notes={25:'景点名已经给出，系统仍要求补充完整名称；实体处理与错误提示不准确。',
26:'没有明确解释当前一次只支持单景点查询。',
27:'混合题未查询SQL票价原文；把片段未提供扩大为资料未提供。',
28:'混合题未查询SQL票价原文；数据库实际存在原文，拒答范围过宽。',
29:'轮椅证据不足的说明合理，但遗漏门票原文。',
30:'混合题只答优待等文本，未查询SQL票价原文；资料缺失的声明过宽。'}
table=[]
for n,row in enumerate(report['cases'],1):
    assert row['case']['id']==f'challenge-v1-{n:02}'
    scores=['pass']*6
    if n in (12,15,16,17,18,21,23,24,25,26): scores[1]='na'
    if n in (12,13,14,18,21,22,23,24,25,26): scores[4]='na'
    if n>=25: scores[5]='fail'
    if n in (27,28,30):
        for i in (0,1,3): scores[i]='fail'
    attribution='na' if n<25 else '实体解析' if n==25 else '能力缺口／实体处理' if n==26 else '能力缺口／路由'
    review=dict(zip(fields,scores))
    review.update(attribution=attribution,source='user supplied per-case table',notes=notes.get(n,''))
    row['human_review']=review
    table.append(f"| {n:02} | "+' | '.join(scores)+f' | {attribution} |')
totals={field:dict(collections.Counter(r['human_review'][field] for r in report['cases'])) for field in fields}
all_counts=dict(collections.Counter(s for row in report['cases'] for field in fields for s in [row['human_review'][field]]))
summary={'source':'user supplied per-case table','date':'2026-10-12','per_dimension':totals,'all_cells':all_counts,
    'all_applicable_dimensions_pass':24,'single_store_all_applicable_pass':24,'single_store_count':26,
    'mixed_all_applicable_pass':0,'mixed_count':4,
    'failing_case_ids':[r['case']['id'] for r in report['cases'] if 'fail' in [r['human_review'][f] for f in fields]],
    'na_excluded_from_pass_rate':True,'scope':'synthetic challenge only; not overall system accuracy'}
report['human_review_status']='completed'
report['human_review_summary']=summary
report['summary']['answer_quality']='user_review_completed'
report['response_payload_sha256']=responses_before
assert responses_before==hashlib.sha256(json.dumps([r['response'] for r in report['cases']],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
text=md.read_text(encoding='utf-8')
text=text.replace('人工项填写 pass / fail / na：','用户人工评分已记录（2026-10-12）。评分口径 pass / fail / na：')
text=text.replace('"answer_quality": "pending_human_review"','"answer_quality": "user_review_completed"')
for row in report['cases']:
    review=row['human_review']
    old='人工评分：事实 __；引用 __；景点隔离 __；拒答 __；时效 __；覆盖 __；归因 __'
    score='人工评分：'+ '；'.join(f'{label} {review[field]}' for label,field in zip(('事实','引用','景点隔离','拒答','时效','覆盖'),fields))+'；归因 '+review['attribution']
    if review['notes']:score+='\n\n评审备注：'+review['notes']
    text=text.replace(old,score,1)
review_header='\n\n## 用户人工评审汇总\n\n24/26道单路径题各可评项全通过；25、26题要点覆盖失败。4道混合题完整覆盖0/4；27、28、30另有事实、引用与拒答失败。景点隔离30/30通过。\n\n'+f"六项评分共145 pass、15 fail、20 na；na不计通过率。该统计仅适用于本批合成题。\n\n"+'| 题号 | 事实支持 | 引用支持 | 景点隔离 | 拒答正确 | 时效正确 | 要点覆盖 | 归因 |\n|---|---|---|---|---|---|---|---|\n'+'\n'.join(table)+'\n\n第20题保留了停车费资料数值并说明计费单位不明；数据层后续需补充金额单位。\n\n'
text=text.replace('\n## challenge-v1-01',review_header+'## challenge-v1-01',1)
md.write_text(text,encoding='utf-8')
assert all_counts=={'pass':145,'na':20,'fail':15},all_counts
print(json.dumps(summary,ensure_ascii=False,indent=2))
